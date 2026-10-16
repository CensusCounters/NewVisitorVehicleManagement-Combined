import logging
import os
import time
from pathlib import Path

import psycopg2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SLEEP_TIME = int(os.environ.get("CLEANUP_POLL_SECONDS", "600"))
UPLOAD_RETENTION_SECONDS = int(os.environ.get("UPLOAD_RETENTION_SECONDS", str(60 * 60 * 24)))
SNAPSHOT_ORPHAN_SECONDS = int(os.environ.get("SNAPSHOT_ORPHAN_SECONDS", str(60 * 60 * 24 * 7)))
SNAPSHOT_REFERENCED_SECONDS = int(os.environ.get("SNAPSHOT_REFERENCED_SECONDS", str(60 * 60 * 24 * 90)))
SNAPSHOT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".json"}

DB_USER = "postgres"
DB_PASSWORD = "postgres"
DB_HOST = os.getenv("POSTGRESQL_URL", "census_counters_postgres_db")
DB_PORT = "5432"
DB_NAME = "postgres"


def cleanup_folder(folder_path_location, time_threshold, extensions=None):
    logger.info(f'Cleaning up folder {folder_path_location}')
    folder_path = Path(folder_path_location)
    if not folder_path.is_dir():
        logger.info(f"Folder {folder_path_location} is not present")
        return
    cut_off_time = time.time() - time_threshold

    for file in folder_path.rglob("*"):
        if file.is_file():
            if (
                extensions is None
                or file.suffix.lower() in extensions
            ) and file.stat().st_mtime < cut_off_time:
                logger.info(f"Removing file: {file.resolve()}")
                file.unlink()


def fetch_referenced_snapshots(table, field):
    """Return referenced paths and basenames, or None if the query fails."""
    query = f"SELECT {field} FROM {table};"
    try:
        with psycopg2.connect(
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
        referenced_paths = {
            path.strip()
            for row in results if row[0]
            for path in str(row[0]).split(',') if path.strip()
        }
        referenced_names = {Path(path).name for path in referenced_paths}
        logger.info(f"Fetched {len(referenced_paths)} referenced files from {table}.{field}")
        return referenced_paths, referenced_names
    except Exception as e:
        logger.error(f"Failed to fetch referenced files from {table}.{field}: {e}")
        return None


def snapshot_is_referenced(file, referenced_paths, referenced_names):
    file_path_str = str(file)
    if file_path_str in referenced_paths or ('/static/images' + file_path_str) in referenced_paths:
        return True
    return file.name in referenced_names


def cleanup_snapshots(folder_path_location, orphan_seconds, referenced_seconds, table, field):
    """Delete unreferenced snapshots after orphan_seconds and referenced ones after referenced_seconds."""
    logger.info(f"Cleaning snapshots in folder {folder_path_location}")
    folder_path = Path(folder_path_location)
    if not folder_path.is_dir():
        logger.info(f"Snapshot folder {folder_path_location} is not present")
        return

    referenced = fetch_referenced_snapshots(table, field)
    if referenced is None:
        return
    referenced_paths, referenced_names = referenced
    now = time.time()

    for file in folder_path.iterdir():
        if not file.is_file() or file.suffix.lower() not in SNAPSHOT_EXTENSIONS:
            continue
        age = now - file.stat().st_mtime
        referenced_file = snapshot_is_referenced(file, referenced_paths, referenced_names)
        if referenced_file and age <= referenced_seconds:
            continue
        if not referenced_file and age <= orphan_seconds:
            continue
        logger.info(f"Removing snapshot file: {file}")
        try:
            file.unlink()
        except Exception as e:
            logger.error(f"Failed to remove file {file}: {e}")


if __name__ == '__main__':
    logger.info(f"Cleanup service script")

    while True:
        cleanup_folder('/uploads', UPLOAD_RETENTION_SECONDS)
        logger.info('Upload Images clean up done.')

        cleanup_snapshots(
            '/project/frontend/finalfrsproject/static/images/snapshots',
            SNAPSHOT_ORPHAN_SECONDS,
            SNAPSHOT_REFERENCED_SECONDS,
            table='public.detections',
            field='detection_image_location'
        )
        logger.info('Snapshot clean up done. Sleeping again for a while.')

        time.sleep(SLEEP_TIME)
        logger.info(f"Back from sleep after {SLEEP_TIME//60} mins")
