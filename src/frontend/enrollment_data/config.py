import os
from pathlib import Path

ROOT = Path(os.environ.get('ENROLLMENT_DATA_ROOT', '/maintenance')).resolve()
PROJECT = Path(os.environ.get('PROJECT_BASE_PATH', '/project/finalfrsproject')).resolve()
REDIS_URL = os.environ.get('ENROLLMENT_REDIS_URL', 'redis://census_counters_enrollment_redis:6379/0')
MILVUS_URI = os.environ.get('ENROLLMENT_MILVUS_URI', 'http://census_counters_facedb:19530')
EMBEDDING_MODEL = os.environ.get('ENROLLMENT_EMBEDDING_MODEL', 'auraface_glintr100')
QUEUE = 'enrollment-maintenance'
LOCK_KEY = 74109321
MAX_BYTES = int(os.environ.get('ENROLLMENT_MAX_BYTES', str(512 * 1024 * 1024)))
TIMEOUT = int(os.environ.get('ENROLLMENT_JOB_TIMEOUT', '7200'))


def initialize_storage():
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ('uploads', 'exports', 'work'):
        (ROOT / name).mkdir(exist_ok=True, mode=0o700)
