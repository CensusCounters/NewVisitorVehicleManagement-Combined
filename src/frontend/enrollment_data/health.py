"""Container health probes; no application data is read or modified."""
import socket
import sys
import time
from redis import Redis
from rq import Worker
from . import config, jobs


def main(kind):
    with jobs.connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT 1 FROM enrollment_data_jobs LIMIT 0')
    if kind == 'dispatcher':
        return time.time() - (config.ROOT / 'dispatcher-heartbeat').stat().st_mtime < 45
    redis = Redis.from_url(config.REDIS_URL, socket_connect_timeout=3, socket_timeout=3)
    redis.ping()
    return any(w.hostname == socket.gethostname() and w.last_heartbeat and
               time.time() - w.last_heartbeat.timestamp() < 600 for w in Worker.all(connection=redis))


if __name__ == '__main__':
    try:
        sys.exit(0 if main(sys.argv[1]) else 1)
    except Exception:
        sys.exit(1)
