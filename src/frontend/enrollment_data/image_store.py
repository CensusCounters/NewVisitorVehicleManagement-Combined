import hashlib
import shutil
import os
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

from . import config, package

PRIVATE_FOLDERS = {'known_persons','known_vehicles','aadhars','drivers_licenses','other_ids'}
SOURCE_FOLDERS = PRIVATE_FOLDERS | {'anpr_vehicles','images'}


def source_path(value):
    raw = urlsplit(str(value)).path
    marker = raw.find('/static/')
    if marker < 0:
        raise ValueError('Enrollment image has an unsupported location.')
    relative = raw[marker + len('/static/'):]
    if not package.safe_name(relative) or relative.split('/')[0] not in SOURCE_FOLDERS:
        raise ValueError('Enrollment image is outside the supported directories.')
    static = (config.PROJECT / 'static').resolve()
    path = static / relative
    if path.is_symlink() or not path.resolve().is_relative_to(static) or not path.is_file():
        # Vehicle images can have a historic URL but have been promoted to known_vehicles.
        fallback = static / 'known_vehicles' / Path(relative).name
        if fallback.is_symlink() or not fallback.resolve().is_relative_to(static) or not fallback.is_file():
            raise ValueError('A required enrollment image is missing or unsafe.')
        return fallback
    return path


def collect(data, work):
    """Normalize exported paths while recording original private files for reset."""
    originals = set()
    for table, fields in package.IMAGE_FIELDS.items():
        for row in data[table]:
            for field, folder in fields.items():
                value = row[field]
                if not value:
                    continue
                source = source_path(value)
                filename = f"{row['enrollment_id']}.png" if field == 'person_image_location' else source.name
                if not package.safe_name(filename) or '/' in filename:
                    raise ValueError('Unsafe image filename.')
                target = work / 'images' / folder / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and package.digest(target) != package.digest(source):
                    raise ValueError('Two enrollment images have conflicting destination filenames.')
                shutil.copyfile(source, target)
                row[field] = f'/static/{folder}/{filename}'
                relative = source.relative_to(config.PROJECT / 'static')
                # Shared ANPR/snapshot sources and placeholders remain owned by their existing cleanup.
                if relative.parts[0] in PRIVATE_FOLDERS and source.name.lower() not in {'no-image-available.jpg','no-image-available.png'}:
                    originals.add(relative.as_posix())
    return sorted(originals)


def destination(name):
    relative = name[len('images/'):]
    if not package.safe_name(relative) or relative.split('/')[0] not in PRIVATE_FOLDERS:
        raise ValueError('Unsafe image destination.')
    static = (config.PROJECT / 'static').resolve()
    result = static / relative
    if result.is_symlink() or not result.resolve().is_relative_to(static):
        raise ValueError('Image destination escapes the application directory.')
    return result


def targets(data):
    if 'bindings' in data:
        for binding in data['bindings']:
            yield binding['source'], binding['target'], binding
    else:
        for name, meta in data['files'].items():
            if name.startswith('images/'):
                yield name, name, meta


def restore(path, data, job_id='restore'):
    with zipfile.ZipFile(path) as z:
        for name, target_name, meta in targets(data):
            target = destination(target_name)
            target.parent.mkdir(parents=True, exist_ok=True)
            token = hashlib.sha256(target_name.encode()).hexdigest()[:16]
            temporary = target.with_name(f'.enrollment-{job_id}-{token}.partial')
            if temporary.is_symlink():
                raise ValueError('Unsafe image staging file.')
            if target.exists():
                if package.digest(target) != meta['sha256']:
                    raise ValueError('A restored image conflicts with an existing file.')
                temporary.unlink(missing_ok=True)
                continue
            temporary.unlink(missing_ok=True)
            try:
                with temporary.open('xb') as out:
                    with z.open(name) as source:
                        shutil.copyfileobj(source, out, 1024 * 1024)
                    out.flush()
                    os.fsync(out.fileno())
                if package.digest(temporary) != meta['sha256']:
                    raise ValueError('Image checksum mismatch during restoration.')
                temporary.replace(target)
                fd = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            finally:
                temporary.unlink(missing_ok=True)



def remove_originals(names):
    for name in names:
        if not package.safe_name(name) or name.split('/')[0] not in PRIVATE_FOLDERS:
            raise ValueError('Unsafe reset file inventory.')
        path = destination('images/' + name)
        path.unlink(missing_ok=True)


def verify(data):
    for _, target_name, meta in targets(data):
        target = destination(target_name)
        if not target.is_file() or package.digest(target) != meta['sha256']:
            raise ValueError('Restored image verification failed.')
