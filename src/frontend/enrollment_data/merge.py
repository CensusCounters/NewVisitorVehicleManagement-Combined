"""Additive import planning with missing-content repair for matching enrollments.

SQL IDs, creator IDs and timestamps describe storage/provenance, not identity.
Person GUIDs identify enrollments; document collisions with a different GUID are
conflicts, never an excuse to link two identities. Plate matches are conservative:
ambiguous plates and ownership differences are reported, not silently merged.
Existing business fields are preserved; missing image references may be repaired.
"""
import hashlib
import json
import re
import struct
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from . import image_store, package

PROVENANCE = {'id', 'created_by', 'date_created'}


def stable_hash(value):
    return hashlib.sha256(json.dumps(value, default=str, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def face_fingerprint(row):
    vector = b''.join(struct.pack('<f', float(v)) for v in row['vector'])
    metadata = json.dumps([row['guid'], row['name'], row['aadhaar']], ensure_ascii=True).encode()
    return hashlib.sha256(metadata + vector).hexdigest()


def face_index(rows):
    result = defaultdict(Counter)
    for row in rows:
        result[row['guid']][face_fingerprint(row)] += 1
    return dict(result)


def face_digest(index, exclude=()):
    excluded = set(exclude)
    return stable_hash({guid: dict(counts) for guid, counts in index.items() if guid not in excluded})


def normalized(value):
    return re.sub(r'[\s-]+', '', str(value or '')).upper()


def document_keys(row):
    result = []
    for field in ('aadhar_number', 'drivers_license_number'):
        if row.get(field):
            result.append((field, normalized(row[field])))
    if row.get('other_id_type') and row.get('other_id_number'):
        result.append(('other_id', row['other_id_type'].strip().casefold(), normalized(row['other_id_number'])))
    return result


def sql_unique_keys(row):
    # Mirror every public.persons UNIQUE constraint, including nullable/blank
    # distinctions and legacy image paths that are not identity documents.
    constraints = [('enrollment_id',), ('person_image_location',), ('aadhar_number',),
                   ('drivers_license_number',), ('drivers_license_image',),
                   ('other_id_type','other_id_number'), ('other_id_number','other_id_image_location')]
    return [(fields, tuple(str(row[f]) for f in fields)) for fields in constraints
            if all(row.get(f) is not None for f in fields)]


def business(row, table):
    result = {k: v for k, v in row.items() if k not in PROVENANCE and k not in package.IMAGE_FIELDS[table]}
    for field in ('aadhar_number','drivers_license_number','other_id_number','vehicle_number_plate','vehicle_registration_number'):
        if field in result and result[field]:
            result[field] = normalized(result[field])
    return result


def prepare_image(row, field, folder, data):
    source = 'images/' + row[field][len('/static/'):]
    metadata = data['files'][source]
    extension = PurePosixPath(row[field]).suffix.lower()
    if field == 'person_image_location':
        filename = f"{row['enrollment_id']}.png"
    elif 'enrollment_id' in row:
        filename = f"{row['enrollment_id']}-{metadata['sha256'][:16]}{extension}"
    else:
        filename = f"{metadata['sha256']}{extension}"
    target = f'images/{folder}/{filename}'
    destination = image_store.destination(target)
    if destination.exists() and package.digest(destination) != metadata['sha256']:
        raise ValueError('Image destination contains different content.')
    return '/static/' + target[len('images/'):], dict(source=source, target=target, **metadata)


def prepare_images(row, table, data):
    """Use GUIDs/content hashes, not imported numeric IDs or untrusted basenames."""
    mapped, bindings = dict(row), []
    for field, folder in package.IMAGE_FIELDS[table].items():
        if row[field]:
            mapped[field], binding = prepare_image(row, field, folder, data)
            bindings.append(binding)
    return mapped, bindings


def plan_image_repairs(incoming, local, table, data, cache):
    """Plan missing content only; different or unsafe existing files are conflicts."""
    updates, bindings = {}, []
    for field, folder in package.IMAGE_FIELDS[table].items():
        source, destination = incoming.get(field), local.get(field)
        if not source and not destination:
            continue
        if not source:
            raise ValueError('Existing image or document is absent from the package.')
        if destination:
            try:
                path = image_store.source_path(destination)
            except ValueError:
                # Do not mistake unsafe/symlinked/out-of-scope paths for missing
                # content. Only an ordinary supported, absent file is repairable.
                raw = urlsplit(str(destination)).path
                marker = raw.find('/static/')
                relative = raw[marker + len('/static/'):] if marker >= 0 else ''
                root = (image_store.config.PROJECT / 'static').resolve()
                candidate = root / relative
                if (not relative or relative.split('/')[0] not in image_store.SOURCE_FOLDERS
                        or candidate.is_symlink() or not candidate.resolve().is_relative_to(root)
                        or candidate.exists()):
                    raise ValueError('Existing image path is unsafe or unsupported.')
            else:
                if path not in cache:
                    cache[path] = package.digest(path)
                metadata = data['files']['images/' + source[len('/static/'):]]
                if cache[path] != metadata['sha256']:
                    raise ValueError('Existing image or document content differs.')
                continue
        target, binding = prepare_image(incoming, field, folder, data)
        bindings.append(binding)
        if target != destination:
            updates[field] = target
    return updates, bindings


def build(data, existing, incoming_faces, local_faces):
    incoming_index, local_index = face_index(incoming_faces), face_index(local_faces)
    plan = {'version': 1, 'persons': [], 'vehicles': [], 'bindings': [], 'person_id_map': {},
            'repairs': {'persons': [], 'vehicles': []}, 'face_repairs': {},
            'baseline': {'person_ids': [r['id'] for r in existing['persons']],
                         'vehicle_ids': [r['id'] for r in existing['vehicles']],
                         'records_sha256': stable_hash(existing), 'faces_sha256': face_digest(local_index)},
            'report': {'imported': {'persons': 0, 'vehicles': 0},
                       'skipped': {'persons': 0, 'vehicles': 0},
                       'repaired': {'persons': 0, 'vehicles': 0}, 'conflicts': []}}
    report = plan['report']
    people = defaultdict(list)
    keys = defaultdict(set)
    sql_keys = defaultdict(set)
    for row in existing['persons']:
        people[str(row['enrollment_id'])].append(row)
        for key in document_keys(row):
            keys[key].add(str(row['enrollment_id']))
        for key in sql_unique_keys(row):
            sql_keys[key].add(str(row['enrollment_id']))
    incoming_keys = defaultdict(set)
    for row in data['persons']:
        for key in document_keys(row):
            incoming_keys[key].add(row['enrollment_id'])
    cache = {}

    def conflict(table, row, reason):
        report['conflicts'].append({'entity': table, 'source_id': row['id'],
            'identity': row.get('enrollment_id') if table == 'persons' else row.get('vehicle_number_plate'),
            'reason': reason})

    for row in data['persons']:
        guid = row['enrollment_id']
        candidates = people.get(guid, [])
        collisions = any((keys[key] | incoming_keys[key]) - {guid} for key in document_keys(row))
        if collisions:
            conflict('persons', row, 'Identity document belongs to a different enrollment GUID.')
            continue
        if candidates:
            if len(candidates) != 1:
                conflict('persons', row, 'Existing enrollment GUID is ambiguous.')
                continue
            local = candidates[0]
            local_business = json.loads(json.dumps(business(local, 'persons'), default=str))
            if local_business != business(row, 'persons'):
                conflict('persons', row, 'Existing person details differ.')
                continue
            expected_faces = incoming_index.get(guid, Counter())
            actual_faces = local_index.get(guid, Counter())
            if actual_faces - expected_faces:
                conflict('persons', row, 'Existing face vectors or face metadata differ.')
                continue
            try:
                updates, bindings = plan_image_repairs(row, local, 'persons', data, cache)
                repaired_row = dict(local, **updates)
                if any(sql_keys[key] - {guid} for key in sql_unique_keys(repaired_row)):
                    raise ValueError('Repaired image reference belongs to another enrollment.')
            except (OSError, ValueError):
                conflict('persons', row, 'Existing person images or documents differ or are unsafe.')
                continue
            missing_faces = expected_faces - actual_faces
            if bindings or missing_faces:
                plan['repairs']['persons'].append({'id': local['id'], 'updates': updates})
                plan['bindings'].extend(bindings)
                if missing_faces:
                    plan['face_repairs'][guid] = dict(expected_faces)
                report['repaired']['persons'] += 1
                for key in sql_unique_keys(repaired_row):
                    sql_keys[key].add(guid)
            else:
                report['skipped']['persons'] += 1
            plan['person_id_map'][str(row['id'])] = local['id']
            continue
        # A face vector for this enrollment GUID is still present in the facial
        # database although its person record was deleted: an orphaned
        # enrollment. Restoring from the package recreates the person and
        # replaces the existing face vector, so treat it as a restorable record
        # instead of a conflict.
        try:
            mapped, bindings = prepare_images(row, 'persons', data)
        except (OSError, ValueError):
            conflict('persons', row, 'An enrollment image destination is unsafe or contains different content.')
            continue
        if any(sql_keys[key] - {guid} for key in sql_unique_keys(mapped)):
            conflict('persons', row, 'A unique identity or document image is already assigned to another person.')
            continue
        for key in sql_unique_keys(mapped):
            sql_keys[key].add(guid)
        plan['persons'].append(mapped)
        plan['bindings'].extend(bindings)
        report['imported']['persons'] += 1

    plates = defaultdict(list)
    source_plates = Counter(normalized(r['vehicle_number_plate']) for r in data['vehicles'])
    for row in existing['vehicles']:
        plates[normalized(row['vehicle_number_plate'])].append(row)
    accepted_person_ids = {r['id'] for r in plan['persons']} | {int(k) for k in plan['person_id_map']}
    for row in data['vehicles']:
        plate = normalized(row['vehicle_number_plate'])
        if row['vehicle_owner_id'] not in accepted_person_ids:
            conflict('vehicles', row, 'Imported owner has an unresolved conflict; vehicle was not linked.')
            continue
        candidates = plates.get(plate, [])
        if source_plates[plate] != 1 or len(candidates) > 1:
            conflict('vehicles', row, 'Vehicle plate is ambiguous in the package or existing records.')
            continue
        if candidates:
            local = candidates[0]
            expected = business(row, 'vehicles')
            expected['vehicle_owner_id'] = plan['person_id_map'].get(str(row['vehicle_owner_id']))
            actual = json.loads(json.dumps(business(local, 'vehicles'), default=str))
            if actual != expected:
                conflict('vehicles', row, 'Existing vehicle details or owner differ.')
                continue
            try:
                updates, bindings = plan_image_repairs(row, local, 'vehicles', data, cache)
            except (OSError, ValueError):
                conflict('vehicles', row, 'Existing vehicle image differs or is unsafe.')
                continue
            if bindings:
                plan['repairs']['vehicles'].append({'id': local['id'], 'updates': updates})
                plan['bindings'].extend(bindings)
                report['repaired']['vehicles'] += 1
            else:
                report['skipped']['vehicles'] += 1
            continue
        try:
            mapped, bindings = prepare_images(row, 'vehicles', data)
        except (OSError, ValueError):
            conflict('vehicles', row, 'Vehicle image destination is unsafe or contains different content.')
            continue
        plan['vehicles'].append(mapped)
        plan['bindings'].extend(bindings)
        report['imported']['vehicles'] += 1
    # Deduplicate identical copies while supporting one source mapped to several targets.
    plan['bindings'] = list({(b['source'], b['target']): b for b in plan['bindings']}.values())
    plan['new_guids'] = [r['enrollment_id'] for r in plan['persons']]
    # The faces this import restores or replaces were part of the local face set
    # at plan time (e.g. an orphaned enrollment re-imported after deletion).
    # Exclude them from the baseline so the "existing faces unchanged" check
    # compares only the faces this operation did not touch.
    plan['baseline']['faces_sha256'] = face_digest(local_index, exclude=set(plan['new_guids']) | set(plan['face_repairs']))
    expected_records = {}
    for table in ('persons', 'vehicles'):
        updates = {item['id']: item['updates'] for item in plan['repairs'][table]}
        expected_records[table] = [dict(row, **updates.get(row['id'], {})) for row in existing[table]]
    plan['baseline']['repaired_records_sha256'] = stable_hash(expected_records)
    plan['plan_digest'] = stable_hash(plan)
    return plan
