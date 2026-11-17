"""RQ entry point: queue payloads contain a UUID only."""
import logging
import threading
from datetime import datetime, timezone

from psycopg2.extras import RealDictCursor
from . import config, jobs
from .guard import guard, set_marker, MaintenanceBusy

logger = logging.getLogger(__name__)


def heartbeat(job_id, stop):
    while not stop.wait(15):
        try:
            jobs.update(job_id, heartbeat_at=datetime.now(timezone.utc))
        except Exception:
            logger.exception('Heartbeat failed for job %s', job_id)


def execute(job_id):
    from .service import run
    config.initialize_storage()
    try:
        with guard(exclusive=True), jobs.connection(job_id) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT pg_try_advisory_lock(%s)', (config.LOCK_KEY,))
                if not cur.fetchone()[0]:
                    return
            conn.commit()
            existing = jobs.get(job_id)
            if not existing or existing['status'] != 'queued':
                return
            # Persist the fail-closed marker before the running claim: a power
            # loss must not leave a partially started operation without its guard.
            marker = config.ROOT / 'active-job'
            set_marker(job_id)
            with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("UPDATE enrollment_data_jobs SET status='running',heartbeat_at=now(),attempts=attempts+1 WHERE id=%s AND status='queued' RETURNING *", (job_id,))
                job = cur.fetchone()
            if not job:
                return
            stop = threading.Event()
            thread = threading.Thread(target=heartbeat, args=(job_id, stop), daemon=True)
            thread.start()
            try:
                result = run(job, conn)
                jobs.complete(job_id, result)
                try:
                    marker.unlink(missing_ok=True)
                except OSError:
                    logger.error('Completed job %s left a marker; dispatcher will reconcile it', job_id)
            except Exception as exc:
                conn.rollback()
                latest = jobs.get(job_id)
                recovery = latest['checkpoint'] not in {'pending', 'prepared'} and job['operation'] not in {'export', 'validate'}
                # Only expected validation messages are exposed. Driver exceptions may include data.
                message = str(exc) if isinstance(exc, ValueError) else 'Operation failed. Inspect the worker log using this job ID.'
                logger.error('Enrollment job %s failed (%s)', job_id, type(exc).__name__)
                jobs.update(job_id, status='recovery_required' if recovery else 'failed', error_summary=message)
                if not recovery:
                    marker.unlink(missing_ok=True)
            finally:
                stop.set()
                thread.join(timeout=20)
    except MaintenanceBusy:
        # Leave queued; dispatcher retries delivery without starting overlapping work.
        logger.info('Maintenance busy; deferring %s', job_id)
