"""Bounded, read-only service checks for admission and admin status."""
import time

from . import config

HELP = ('Wait a moment and select Check again. If this continues, ask the person '
        'who manages this system to restart the enrollment maintenance services.')


class BackgroundUnavailable(RuntimeError):
    def __init__(self, state):
        self.state = state
        super().__init__(state['message'])


def unavailable(code):
    return {'ready': False, 'code': code,
            'message': 'Export and import are temporarily unavailable because the '
                       'background service is not responding. ' + HELP}


def availability():
    client = None
    try:
        from redis import Redis
        from rq import Worker
        client = Redis.from_url(config.REDIS_URL, socket_connect_timeout=1,
                                socket_timeout=1, retry_on_timeout=False)
        client.ping()
        now = time.time()
        alive = False
        for worker in Worker.all(connection=client):
            if config.QUEUE not in worker.queue_names() or not worker.last_heartbeat:
                continue
            age = now - worker.last_heartbeat.timestamp()
            if (-30 <= age < 90
                    and worker.get_state() in {'idle', 'busy', 'started'}):
                alive = True
                break
        if not alive:
            return unavailable('worker_unavailable')
        try:
            age = now - (config.ROOT / 'dispatcher-heartbeat').stat().st_mtime
            if not -30 <= age < 45:
                return unavailable('dispatcher_unavailable')
        except OSError:
            return unavailable('dispatcher_unavailable')
        return {'ready': True, 'code': 'ready', 'message': ''}
    except Exception:
        return unavailable('queue_unavailable')
    finally:
        if client is not None:
            client.close()


def require_available():
    state = availability()
    if not state['ready']:
        raise BackgroundUnavailable(state)
