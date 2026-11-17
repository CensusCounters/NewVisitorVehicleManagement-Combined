import json
import shutil
import zipfile
from pathlib import Path

from . import config, image_store, jobs, package, postgres_store, merge
from .milvus_store import Faces


def progress(job_id, step):
    jobs.update(job_id, step=step)


def export_dataset(conn, face_store, output, work, job_id):
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, mode=0o700)
    progress(job_id, 'Reading enrollment records and images')
    data = postgres_store.snapshot(conn)
    originals = image_store.collect(data, work)
    package.write_json(work / 'persons.json', data['persons'])
    package.write_json(work / 'vehicles.json', data['vehicles'])
    count = 0
    with (work / 'faces.jsonl').open('w') as f:
        for row in face_store.rows():
            f.write(json.dumps(row, allow_nan=False) + '\n')
            count += 1
            if count % 200 == 0:
                progress(job_id, f'Exporting facial vectors: {count}')
    counts = {'persons': len(data['persons']), 'vehicles': len(data['vehicles']), 'faces': count}
    progress(job_id, 'Checking package completeness and checksums')
    package.create(work, output, counts)
    # The private reset inventory is outside the portable package.
    package.write_json(work.parent / 'original-images.json', originals)
    return counts


def build_import_plan(conn, face_store, archive, data):
    with zipfile.ZipFile(archive) as z:
        plan = merge.build(data, postgres_store.snapshot(conn), package.faces(z), face_store.rows())
    plan['package_sha256'] = package.digest(archive)
    plan['plan_digest'] = merge.stable_hash({key: value for key, value in plan.items() if key != 'plan_digest'})
    return plan


def verify_import(conn, face_store, archive, plan):
    restored = json.loads(json.dumps(postgres_store.snapshot(conn), default=str))
    baseline = plan['baseline']
    original = {}
    for table, key in (('persons','person_ids'), ('vehicles','vehicle_ids')):
        old_ids = set(baseline[key])
        original[table] = [row for row in restored[table] if row['id'] in old_ids]
        added = [row for row in restored[table] if row['id'] not in old_ids]
        if added != plan['inserted'][table]:
            raise ValueError('Imported PostgreSQL records do not match their ownership journal.')
    if merge.stable_hash(original) != baseline.get('repaired_records_sha256', baseline['records_sha256']):
        raise ValueError('Existing PostgreSQL records changed during import.')
    image_store.verify({'bindings': plan['bindings']})
    new_guids = set(plan['new_guids']) | set(plan.get('face_repairs', {}))
    actual = merge.face_index(face_store.rows())
    if merge.face_digest(actual, exclude=new_guids) != baseline['faces_sha256']:
        raise ValueError('Existing face vectors changed during import.')
    with zipfile.ZipFile(archive) as z:
        expected = merge.face_index(row for row in package.faces(z) if row['guid'] in new_guids)
    if {guid: rows for guid, rows in actual.items() if guid in new_guids} != expected:
        raise ValueError('Imported face vectors do not match the package.')


def import_dataset(job, conn, face_store, archive, data):
    job_id, checkpoint = str(job['id']), job['checkpoint']
    plan = job.get('import_plan')
    if checkpoint == 'pending':
        plan = build_import_plan(conn, face_store, archive, data)
        if job.get('preview_id'):
            preview = jobs.get(job['preview_id'])
            if not preview or preview['operation'] != 'validate' or preview['status'] != 'completed' or str(preview['input_id']) != str(job['input_id']):
                raise ValueError('A completed preview for this package is required.')
            if preview['result'].get('plan_digest') != plan['plan_digest']:
                raise ValueError('Enrollment data changed after preview. Check the package again before importing.')
        with conn:
            jobs.save_plan(conn, job_id, plan, 'prepared')
        checkpoint = 'prepared'
    if not plan or plan.get('version') != 1 or 'baseline' not in plan:
        raise ValueError('Legacy import has no additive recovery journal. Finish recovery using the original version before upgrading.')
    if plan.get('package_sha256') != package.digest(archive):
        raise ValueError('The saved package changed after import planning. Restore the original package before recovery.')
    if checkpoint == 'prepared':
        progress(job_id, 'Adding non-conflicting persons and vehicles')
        postgres_store.restore(conn, plan, job['requested_by'], job_id)
        checkpoint = 'records_loaded'
    if checkpoint == 'records_loaded':
        progress(job_id, 'Restoring new and missing enrollment images')
        image_store.restore(archive, {'bindings': plan['bindings']}, job_id)
        jobs.checkpoint(job_id, 'images_loaded')
        checkpoint = 'images_loaded'
    if checkpoint == 'images_loaded':
        progress(job_id, 'Restoring facial vectors for newly imported persons')
        new_guids = set(plan['new_guids'])
        if new_guids:
            with zipfile.ZipFile(archive) as z:
                face_store.restore((row for row in package.faces(z) if row['guid'] in new_guids),
                    plan['new_guids'], lambda step: progress(job_id, step))
        repairs = plan.get('face_repairs', {})
        if repairs:
            progress(job_id, 'Restoring missing face data for existing enrollments')
            with zipfile.ZipFile(archive) as z:
                face_store.restore_missing(
                    (row for row in package.faces(z) if row['guid'] in repairs), repairs,
                    lambda step: progress(job_id, step))
        jobs.checkpoint(job_id, 'faces_loaded')
    progress(job_id, 'Verifying new enrollments and preservation of existing data')
    verify_import(conn, face_store, archive, plan)
    if plan['persons'] or plan['vehicles'] or any(plan.get('repairs', {}).values()):
        invalidate_workflow_sessions(conn)
    return dict(plan['report'], counts=data['counts'])


def invalidate_workflow_sessions(conn):
    # Existing UI workflow state is stored under numeric user IDs. Preserve
    # active_login:* keys, other Redis users, and the separate RQ queue.
    import os
    from redis import Redis
    redis = Redis.from_url(os.environ.get('REDIS_URL', 'redis://census_counters_redis:6379/0'),
                           socket_connect_timeout=5, socket_timeout=10)
    with conn.cursor() as cur:
        cur.execute('SELECT id FROM users')
        keys = [str(row[0]) for row in cur.fetchall()]
    if keys:
        redis.delete(*keys)


def run(job, conn):
    job_id, operation = str(job['id']), job['operation']
    checkpoint = job['checkpoint']
    postgres_store.ensure_schema(conn)
    work = config.ROOT / 'work' / job_id
    work.mkdir(parents=True, exist_ok=True, mode=0o700)
    if operation == 'validate':
        archive = config.ROOT / 'uploads' / f"{job['input_id']}.zip"
        progress(job_id, 'Checking dataset and planning duplicates and conflicts')
        data = package.validate(archive)
        faces = Faces()
        try:
            plan = build_import_plan(conn, faces, archive, data)
        finally:
            faces.close()
        return dict(plan['report'], counts=data['counts'], input_id=str(job['input_id']), plan_digest=plan['plan_digest'])
    face_store = Faces()
    try:
        if operation == 'export':
            output = config.ROOT / 'exports' / f'{job_id}.zip'
            counts = export_dataset(conn, face_store, output, work / 'dataset', job_id)
            return {'counts': counts, 'download': True}
        if operation == 'import':
            archive = config.ROOT / 'uploads' / f"{job['input_id']}.zip"
            progress(job_id, 'Validating saved dataset')
            data = package.validate(archive)
            return import_dataset(job, conn, face_store, archive, data)
        if operation == 'reset':
            archive = config.ROOT / 'exports' / f'{job_id}.zip'
            if checkpoint == 'pending':
                postgres_store.check_reset(conn)
                progress(job_id, 'Creating and validating recovery export before reset')
                export_dataset(conn, face_store, archive, work / 'dataset', job_id)
                jobs.checkpoint(job_id, 'prepared')
                checkpoint = 'prepared'
            data = package.validate(archive)
            originals = json.loads((work / 'original-images.json').read_text())
            if checkpoint == 'prepared':
                progress(job_id, 'Clearing enrollment records')
                postgres_store.clear(conn, job_id)
                checkpoint = 'records_cleared'
            if checkpoint == 'records_cleared':
                progress(job_id, 'Clearing enrolled facial vectors')
                face_store.delete_guids([r['enrollment_id'] for r in data['persons']])
                jobs.checkpoint(job_id, 'faces_cleared')
                checkpoint = 'faces_cleared'
            if checkpoint == 'faces_cleared':
                progress(job_id, 'Removing enrollment image files')
                image_store.remove_originals(originals)
                jobs.checkpoint(job_id, 'images_cleared')
            postgres_store.check_empty(conn)
            if not face_store.empty():
                raise ValueError('Unexpected facial records remain; reset requires investigation.')
            invalidate_workflow_sessions(conn)
            return {'counts': data['counts'], 'download': True, 'recovery_export': True}
        raise ValueError('Unsupported operation')
    finally:
        face_store.close()
