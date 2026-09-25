"""Feature-gated ANPR trip closer used by the Ganganagar deployment."""

import logging
import os
import time
from contextlib import closing
from datetime import datetime, timedelta

import psycopg2


logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
LOGGER = logging.getLogger(__name__)


def database_config():
    return {
        "host": os.environ.get("POSTGRESQL_URL", "census_counters_postgres_db"),
        "port": os.environ.get("DB_PORT", "5432"),
        "database": os.environ.get("DB_NAME", "postgres_visitor_vehicle"),
        "user": os.environ.get("DB_USER_NAME", "postgres"),
        "password": os.environ.get("DB_PASSWORD", "postgres"),
    }


def close_recent_anpr_trips(reading_window_seconds=60):
    cutoff = datetime.now() - timedelta(seconds=reading_window_seconds)
    exit_time = datetime.now()
    total_updates = 0

    with closing(psycopg2.connect(**database_config())) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (plate) plate, timestamp
                FROM anpr_vehicle_readings
                WHERE timestamp::timestamp >= %s
                  AND plate IS NOT NULL
                  AND plate != ''
                ORDER BY plate, timestamp DESC
                """,
                (cutoff,),
            )
            for plate, reading_time in cursor.fetchall():
                cursor.execute(
                    """
                    UPDATE trips
                    SET is_finished = TRUE, exit_time = %s
                    WHERE vehicle_number_plate = %s
                      AND is_finished = FALSE
                      AND entry_time < %s
                    """,
                    (exit_time, plate, reading_time),
                )
                total_updates += cursor.rowcount
        connection.commit()

    return total_updates


def main():
    site_profile = os.environ.get("SITE_PROFILE", "").lower()
    closure_mode = os.environ.get("TRIP_CLOSURE_MODE", "manual").lower()
    if closure_mode != "manual_and_anpr":
        raise RuntimeError(
            f"ANPR auto-close is disabled for SITE_PROFILE={site_profile or 'unknown'} "
            f"because TRIP_CLOSURE_MODE={closure_mode!r}"
        )

    poll_seconds = int(os.environ.get("AUTO_CLOSE_POLL_SECONDS", "600"))
    reading_window_seconds = int(os.environ.get("AUTO_CLOSE_READING_WINDOW_SECONDS", "60"))
    while True:
        try:
            updated = close_recent_anpr_trips(reading_window_seconds)
            LOGGER.info("Auto-close completed; trips updated=%s", updated)
        except Exception:
            LOGGER.exception("Auto-close cycle failed")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
