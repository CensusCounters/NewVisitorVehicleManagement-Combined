import uuid
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor, Json

from . import config


@contextmanager
def connection(job_id=None):
    import os
    conn = psycopg2.connect(host=os.getenv('POSTGRESQL_URL', 'census_counters_postgres_db'),
        port=os.getenv('DB_PORT', '5432'), dbname=os.getenv('DB_NAME', 'postgres_visitor_vehicle'),
        user=os.getenv('DB_USER_NAME', 'postgres'), password=os.getenv('DB_PASSWORD', 'postgres'),
        connect_timeout=10, options='-c statement_timeout=60000 -c lock_timeout=10000')
    try:
        if job_id:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('enrollment_data.job_id', %s, false)", (str(job_id),))
            conn.commit()
        yield conn
    finally:
        conn.close()


def query(sql, args=(), one=False):
    with connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, args)
        return cur.fetchone() if one else cur.fetchall()


def create(operation, actor, input_id=None, preview_id=None):
    job_id = str(uuid.uuid4())
    config.initialize_storage()
    from .guard import set_marker
    with connection() as conn, conn, conn.cursor() as cur:
        cur.execute('INSERT INTO enrollment_data_jobs(id,operation,requested_by,input_id,preview_id) VALUES (%s,%s,%s,%s,%s)',
                    (job_id, operation, actor, input_id, preview_id))
        # Publish before committing the dispatchable row, so a fast worker cannot
        # have its active marker overwritten by the submitter's queued marker.
        # If the commit fails, dispatcher reconciliation clears the orphan marker.
        set_marker(job_id, phase='queued')
    return job_id


def get(job_id):
    return query('SELECT * FROM enrollment_data_jobs WHERE id=%s', (str(uuid.UUID(str(job_id))),), one=True)


def history():
    return query('SELECT * FROM enrollment_data_jobs ORDER BY created_at DESC LIMIT 30')


def update(job_id, **values):
    allowed = {'status','step','checkpoint','error_summary','heartbeat_at','completed_at','dispatched_at'}
    if not values or not set(values) <= allowed:
        raise ValueError('Invalid job update')
    with connection() as conn, conn, conn.cursor() as cur:
        cur.execute('UPDATE enrollment_data_jobs SET ' + ','.join(f'{k}=%s' for k in values) + ' WHERE id=%s',
                    (*values.values(), job_id))


def checkpoint(job_id, step, conn=None):
    def write(db):
        with db.cursor() as cur:
            cur.execute('UPDATE enrollment_data_jobs SET checkpoint=%s, step=%s, heartbeat_at=now() WHERE id=%s', (step, step, job_id))
            cur.execute('INSERT INTO enrollment_data_steps(job_id,step) VALUES (%s,%s)', (job_id, step))
    if conn is not None:
        write(conn)
    else:
        with connection() as db, db:
            write(db)


def complete(job_id, result):
    with connection() as conn, conn, conn.cursor() as cur:
        cur.execute("UPDATE enrollment_data_jobs SET result=%s,checkpoint='verified',step='Complete',status='completed',completed_at=now(),error_summary=NULL WHERE id=%s", (Json(result), job_id))


def resume(job_id):
    with connection() as conn, conn, conn.cursor() as cur:
        cur.execute("UPDATE enrollment_data_jobs SET status='queued',dispatched_at=NULL,error_summary=NULL WHERE id=%s AND status='recovery_required' RETURNING id", (job_id,))
        if not cur.fetchone():
            raise ValueError('Only an interrupted operation can be resumed.')


def cancel(job_id):
    from .guard import guard, read_marker, MaintenanceBusy
    with guard(exclusive=True), connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(%s)', (config.LOCK_KEY,))
            if not cur.fetchone()[0]:
                raise MaintenanceBusy('The operation is already starting.')
        conn.commit()
        with conn, conn.cursor() as cur:
            cur.execute("UPDATE enrollment_data_jobs SET status='cancelled',step='Cancelled before execution',completed_at=now() WHERE id=%s AND status='queued' AND checkpoint='pending' RETURNING id", (job_id,))
            if not cur.fetchone():
                raise ValueError('Only a queued operation that has not started can be cancelled.')
        marker = config.ROOT / 'active-job'
        if marker.exists() and read_marker(config.ROOT).get('job_id') == str(job_id):
            marker.unlink()


def save_plan(conn, job_id, plan, step):
    # Caller owns the transaction; do not nest psycopg2 connection contexts.
    with conn.cursor() as cur:
        cur.execute('UPDATE enrollment_data_jobs SET import_plan=%s WHERE id=%s', (Json(plan), job_id))
    checkpoint(job_id, step, conn)
