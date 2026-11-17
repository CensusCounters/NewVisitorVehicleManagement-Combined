"""POSIX file guard shared by Flask, the face API, cleanup and maintenance.

The lock file is never removed. The marker deliberately survives worker crashes.
All containers must mount the same local /maintenance volume.
"""
import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path


class MaintenanceBusy(RuntimeError):
    pass


@contextmanager
def guard(exclusive=False, allow_queued=False):
    root = Path(os.environ.get('ENROLLMENT_DATA_ROOT', '/maintenance'))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / 'operation.lock').open('a') as handle:
        try:
            fcntl.flock(handle, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise MaintenanceBusy('Enrollment maintenance is in progress.') from exc
        try:
            if not exclusive and (root / 'active-job').exists():
                state = read_marker(root)
                if not (allow_queued and state.get('phase') == 'queued'):
                    raise MaintenanceBusy('Enrollment maintenance is queued, active or awaiting recovery. Open Enrollment Data.')
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def set_marker(job_id, phase='active'):
    root = Path(os.environ.get('ENROLLMENT_DATA_ROOT', '/maintenance'))
    temporary = root / 'active-job.partial'
    with temporary.open('w') as out:
        json.dump({'job_id': str(job_id), 'phase': phase}, out)
        out.flush()
        os.fsync(out.fileno())
    temporary.replace(root / 'active-job')
    fd = os.open(root, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read_marker(root):
    value = (root / 'active-job').read_text()
    try:
        state = json.loads(value)
        return state if isinstance(state, dict) else {'job_id': value, 'phase': 'active'}
    except ValueError:
        return {'job_id': value, 'phase': 'active'}
