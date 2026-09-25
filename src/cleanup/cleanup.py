import logging
import os
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SLEEP_TIME = int(os.environ.get("CLEANUP_POLL_SECONDS", "600"))
ANPR_RETENTION_SECONDS = int(os.environ.get("ANPR_RETENTION_SECONDS", str(60 * 60 * 24 * 15)))
UPLOAD_RETENTION_SECONDS = int(os.environ.get("UPLOAD_RETENTION_SECONDS", str(60 * 60 * 24)))

def cleanup_folder(folder_path_location, time_threshold, extensions=None):
    logger.info(f'Cleaning up folder {folder_path_location}')
    folder_path = Path(folder_path_location)
    cut_off_time = time.time() - time_threshold

    for file in folder_path.rglob("*"):
        if file.is_file():
            if (
                extensions is None
                or file.suffix.lower() in extensions
            ) and file.stat().st_mtime < cut_off_time:

                logger.info(f"Removing file: {file.resolve()}")
                file.unlink()


if __name__ == '__main__':
    logger.info(f"Cleanup service script")

    while True:
        cleanup_folder('/anpr_images', ANPR_RETENTION_SECONDS)
        logger.info('ANPR Images clean up done. ')

        cleanup_folder('/uploads', UPLOAD_RETENTION_SECONDS)
        logger.info('Upload Images clean up done.')

        cleanup_folder('/anpr', UPLOAD_RETENTION_SECONDS, extensions=['.jpeg', '.jpg', '.png'])
        logger.info('ANPR Images clean up done. Sleeping again for a while.')

        time.sleep(SLEEP_TIME)
        logger.info(f"Back from sleep after {SLEEP_TIME//60} mins")
