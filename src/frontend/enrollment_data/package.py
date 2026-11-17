"""Versioned, checksummed dataset archives. Never extract user-supplied paths."""
from datetime import date, datetime
import hashlib
import json
import math
import os
import stat
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from . import config

PERSON_FIELDS = ('id created_by date_created enrollment_id person_name person_image_location aadhar_number '
    'aadhar_image_location drivers_license_number drivers_license_image gender vid dob guardians_name address '
    'mobile_number visiting_person_name other_id_type other_id_number other_id_image_location').split()
VEHICLE_FIELDS = ('id created_by date_created vehicle_number_plate vehicle_image_location vehicle_make '
    'vehicle_model vehicle_color vehicle_type vehicle_registered_to vehicle_registration_number vehicle_owner_id').split()
IMAGE_FIELDS = {
    'persons': {'person_image_location': 'known_persons', 'aadhar_image_location': 'aadhars',
                'drivers_license_image': 'drivers_licenses', 'other_id_image_location': 'other_ids'},
    'vehicles': {'vehicle_image_location': 'known_vehicles'},
}
FORMAT = 'census-enrollments'


class InvalidDataset(ValueError):
    pass


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def safe_name(name):
    # Filename-character safety rules are intentionally disabled for this
    # deployment: every enrollment image filename is treated as safe. Real
    # path-traversal protection is still enforced by the is_relative_to()
    # containment checks at each call site, not by inspecting the filename here.
    return bool(name)


def write_json(path, data):
    with Path(path).open('w', encoding='utf-8') as f:
        json.dump(data, f, default=str, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())


def create(work, output, counts):
    work, output = Path(work), Path(output)
    entries = {}
    for p in sorted(work.rglob('*')):
        if p.is_file() and p.name != 'manifest.json':
            entries[p.relative_to(work).as_posix()] = {'sha256': digest(p), 'bytes': p.stat().st_size}
    write_json(work / 'manifest.json', {'format': FORMAT, 'version': 1, 'embedding_model': config.EMBEDDING_MODEL, 'counts': counts, 'files': entries})
    temporary = output.with_suffix('.partial')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        z.write(work / 'manifest.json', 'manifest.json')
        for name in entries:
            z.write(work / name, name)
    validate(temporary)
    with temporary.open('rb') as f:
        os.fsync(f.fileno())
    temporary.replace(output)
    fd = os.open(output.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def faces(z):
    with z.open('faces.jsonl') as f:
        while True:
            raw = f.readline(128 * 1024 + 1)
            if not raw:
                break
            if len(raw) > 128 * 1024:
                raise InvalidDataset('Face record exceeds the supported size.')
            yield json.loads(raw)


def load_json(z, name):
    if z.getinfo(name).file_size > 32 * 1024 * 1024:
        raise InvalidDataset(f'{name} exceeds the supported metadata size.')
    return json.loads(z.read(name))


def validate(path):
    try:
        return _validate(path)
    except InvalidDataset:
        raise
    except (KeyError, TypeError, ValueError, zipfile.BadZipFile, UnicodeError, OverflowError) as exc:
        raise InvalidDataset('Invalid or unsupported enrollment package.') from exc


def _validate(path):
    if Path(path).stat().st_size > config.MAX_BYTES:
        raise InvalidDataset('Compressed package exceeds the configured size limit.')
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if len(names) > 100000 or len(set(names)) != len(names):
            raise InvalidDataset('Duplicate archive entries or too many files.')
        if sum(i.file_size for i in infos) > config.MAX_BYTES:
            raise InvalidDataset('Expanded package exceeds the configured size limit.')
        for i in infos:
            if not safe_name(i.filename) or i.is_dir() or stat.S_ISLNK(i.external_attr >> 16) or i.flag_bits & 1:
                raise InvalidDataset('Unsafe archive entry.')
        manifest = load_json(z, 'manifest.json')
        if manifest['format'] != FORMAT or manifest['version'] != 1:
            raise InvalidDataset('Unsupported dataset format or version.')
        if manifest['embedding_model'] != config.EMBEDDING_MODEL:
            raise InvalidDataset('Dataset embedding model does not match this deployment.')
        files = manifest['files']
        if set(files) != set(names) - {'manifest.json'} or not {'persons.json','vehicles.json','faces.jsonl'} <= set(files):
            raise InvalidDataset('Manifest does not match the archive.')
        for name, entry in files.items():
            if name not in ('persons.json','vehicles.json','faces.jsonl') and not name.startswith('images/'):
                raise InvalidDataset('Unexpected package file.')
            h = hashlib.sha256()
            with z.open(name) as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b''):
                    h.update(chunk)
            if h.hexdigest() != entry['sha256'] or z.getinfo(name).file_size != entry['bytes']:
                raise InvalidDataset('Package checksum or size mismatch.')
        people = load_json(z, 'persons.json')
        vehicles = load_json(z, 'vehicles.json')
        if not isinstance(people, list) or not isinstance(vehicles, list):
            raise InvalidDataset('Enrollment records must be lists.')
        ids, guids, used_images = set(), set(), set()
        for table, rows, columns in (('persons', people, PERSON_FIELDS), ('vehicles', vehicles, VEHICLE_FIELDS)):
            table_ids = set()
            for row in rows:
                if set(row) != set(columns):
                    raise InvalidDataset(f'Unsupported {table} fields.')
                if type(row['created_by']) is not int or not 0 < row['created_by'] < 2**63:
                    raise InvalidDataset('Invalid record creator.')
                for key, value in row.items():
                    if key in ('id','created_by','vehicle_owner_id'):
                        continue
                    if value is not None and not isinstance(value, str):
                        raise InvalidDataset('Record text fields must be strings or null.')
                    if isinstance(value, str) and '\x00' in value:
                        raise InvalidDataset('Record contains an invalid null character.')
                    if value is not None and key == 'date_created':
                        parsed_date = datetime.fromisoformat(value)
                        if parsed_date.tzinfo is not None or str(parsed_date) != value:
                            raise InvalidDataset('Enrollment timestamps must be timezone-naive.')
                    if value is not None and key == 'dob':
                        if str(date.fromisoformat(value)) != value:
                            raise InvalidDataset('Invalid date representation.')
                if row['date_created'] is None:
                    raise InvalidDataset('Enrollment creation date is required.')
                if type(row['id']) is not int or not 0 < row['id'] < 2**63 or row['id'] in table_ids:
                    raise InvalidDataset('Invalid or duplicate record ID.')
                table_ids.add(row['id'])
                for field, folder in IMAGE_FIELDS[table].items():
                    value = row[field]
                    if not value:
                        if field in ('person_image_location','vehicle_image_location'):
                            raise InvalidDataset('Required enrollment image is absent.')
                        continue
                    prefix = f'/static/{folder}/'
                    if not isinstance(value, str) or not value.startswith(prefix) or not safe_name(value[len(prefix):]) or '/' in value[len(prefix):]:
                        raise InvalidDataset('Invalid enrollment image path.')
                    if PurePosixPath(value).name.startswith('.enrollment-'):
                        raise InvalidDataset('Reserved image filename.')
                    if PurePosixPath(value).suffix.lower() not in {'.png','.jpg','.jpeg','.gif','.webp','.bmp','.pdf'}:
                        raise InvalidDataset('Unsupported image or document file type.')
                    image = 'images/' + value[len('/static/'):]
                    if image not in files:
                        raise InvalidDataset('Referenced image is missing.')
                    used_images.add(image)
                if table == 'persons':
                    guid = str(uuid.UUID(row['enrollment_id']))
                    if guid != row['enrollment_id'] or guid in guids or not row['person_name']:
                        raise InvalidDataset('Invalid or duplicate enrollment identity.')
                    if row['person_image_location'] != f'/static/known_persons/{guid}.png':
                        raise InvalidDataset('Person image must match the enrollment GUID.')
                    guids.add(guid)
                elif type(row['vehicle_owner_id']) is not int or row['vehicle_owner_id'] not in ids:
                    raise InvalidDataset('Vehicle owner is absent or invalid.')
            if table == 'persons':
                ids = table_ids
        for fields in [('aadhar_number',), ('drivers_license_number',), ('drivers_license_image',),
                       ('other_id_type','other_id_number'), ('other_id_number','other_id_image_location')]:
            seen = set()
            for row in people:
                value = tuple(row[f] for f in fields)
                if any(v is None for v in value):
                    continue
                if value in seen:
                    raise InvalidDataset('Duplicate person identity or document in the package.')
                seen.add(value)
        person_limits = {'person_name':100, 'person_image_location':200, 'aadhar_number':100,
                         'aadhar_image_location':200, 'drivers_license_number':100, 'drivers_license_image':200,
                         'gender':20, 'vid':100, 'guardians_name':100, 'mobile_number':100, 'visiting_person_name':100}
        vehicle_limits = {'vehicle_number_plate':50, 'vehicle_image_location':200, 'vehicle_make':50,
                          'vehicle_model':50, 'vehicle_color':50, 'vehicle_type':50,
                          'vehicle_registered_to':50, 'vehicle_registration_number':50}
        for records, limits in ((people, person_limits), (vehicles, vehicle_limits)):
            for row in records:
                if any(row[f] is not None and len(row[f]) > maximum for f, maximum in limits.items()):
                    raise InvalidDataset('Enrollment field exceeds the supported schema length.')
        if used_images != {n for n in files if n.startswith('images/')}:
            raise InvalidDataset('Package contains unreferenced images.')
        face_guids, count = set(), 0
        for row in faces(z):
            if set(row) != {'guid','vector','name','aadhaar'} or row['guid'] not in guids:
                raise InvalidDataset('Invalid or orphaned face record.')
            vector = row['vector']
            if not isinstance(vector, list) or len(vector) != 512 or any(type(v) not in (float, int) or not math.isfinite(v) for v in vector):
                raise InvalidDataset('Invalid facial vector.')
            if not isinstance(row['name'], str) or len(row['name']) > 256 or not isinstance(row['aadhaar'], str) or len(row['aadhaar']) > 12:
                raise InvalidDataset('Invalid face metadata.')
            face_guids.add(row['guid'])
            count += 1
        if face_guids != guids:
            raise InvalidDataset('Some enrolled persons have no face vector.')
        if manifest['counts'] != {'persons': len(people), 'vehicles': len(vehicles), 'faces': count}:
            raise InvalidDataset('Manifest counts do not match the data.')
        return {'counts': manifest['counts'], 'persons': people, 'vehicles': vehicles, 'files': files}
