"""The queued job row is a transactional outbox; Redis delivery is repeatable.

A job is accepted and dispatchable in a single PostgreSQL INSERT. Duplicate
queue deliveries are harmless because execute() atomically claims queued rows.
"""
import logging
import time
from datetime import datetime, timezone

from redis import Redis
from rq import Queue
from rq.serializers import JSONSerializer
from . import config, jobs
from .guard import guard, set_marker, MaintenanceBusy

logger = logging.getLogger(__name__)


def reconcile():
    # A heartbeat is advisory. Both the file guard and database lock must be
    # obtainable before concluding that the former executor has stopped.
    try:
        with guard(exclusive=True), jobs.connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT pg_try_advisory_lock(%s)', (config.LOCK_KEY,))
                if not cur.fetchone()[0]:
                    return
            conn.commit()
            with conn, conn.cursor() as cur:
                cur.execute("UPDATE enrollment_data_jobs SET status='recovery_required',error_summary='Worker interrupted. Review the last step and explicitly resume.' WHERE status='running' AND heartbeat_at < now() - interval '90 seconds'")
                cur.execute("SELECT id,status,checkpoint FROM enrollment_data_jobs WHERE status IN ('queued','running','recovery_required') LIMIT 1")
                active = cur.fetchone()
            marker = config.ROOT / 'active-job'
            if active:
                set_marker(str(active[0]), phase='queued' if active[1] == 'queued' and active[2] == 'pending' else 'active')
            else:
                marker.unlink(missing_ok=True)
    except MaintenanceBusy:
        pass


def tick(queue):
    reconcile()
    # dispatched_at is a delivery lease, not an execution lease. Lost queue
    # messages are resent; the permanent PostgreSQL row remains authoritative.
    rows = jobs.query("SELECT id FROM enrollment_data_jobs WHERE status='queued' AND (dispatched_at IS NULL OR dispatched_at < now() - interval '60 seconds')")
    for row in rows:
        job_id = str(row['id'])
        queue.enqueue('enrollment_data.tasks.execute', job_id, job_timeout=config.TIMEOUT,
                      result_ttl=3600, failure_ttl=604800)
        jobs.update(job_id, dispatched_at=datetime.now(timezone.utc))


def main():
    logging.basicConfig(level=logging.INFO)
    config.initialize_storage()
    queue = Queue(config.QUEUE, connection=Redis.from_url(config.REDIS_URL), serializer=JSONSerializer)
    while True:
        try:
            tick(queue)
            (config.ROOT / 'dispatcher-heartbeat').touch()
        except Exception:
            logger.exception('Enrollment dispatcher unavailable; durable requests will be retried')
        time.sleep(5)


if __name__ == '__main__':
    main()
