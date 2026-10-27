import pytz
from datetime import datetime, timedelta

DEFAULT_TIMEZONE = pytz.timezone('Asia/Kolkata')

def convert_seconds_to_hms(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60
    return f"{hours}h {minutes}m {remaining_seconds}s"


def parse_datestring(date_str):
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"time data '{date_str}' does not match expected formats")


# timezone helpers
def utc_to_local(utc_dt: datetime, tz: pytz.BaseTzInfo = DEFAULT_TIMEZONE) -> datetime:
    """Convert a naive or UTC-aware datetime in UTC → aware datetime in tz."""
    if utc_dt.tzinfo is None:
        # treat as UTC
        utc_dt = pytz.utc.localize(utc_dt)
    return utc_dt.astimezone(tz)


def local_to_utc(local_dt: datetime, tz: pytz.BaseTzInfo = DEFAULT_TIMEZONE) -> datetime:
    """Convert a naive or tz-aware datetime in tz → aware datetime in UTC."""
    if local_dt.tzinfo is None:
        local_dt = tz.localize(local_dt)
    return local_dt.astimezone(pytz.utc)

def get_day_boundaries_in_utc(tz: pytz.BaseTzInfo = DEFAULT_TIMEZONE) -> (datetime, datetime):
    # Get the current time in the specified local timezone
    now_local = datetime.now(tz)

    # Determine the start of the day (midnight) in the local timezone
    start_of_day_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    # Determine the start of the next day, which serves as the exclusive end boundary
    start_of_next_day_local = start_of_day_local + timedelta(days=1)

    # Convert the local start and end times to UTC using your helper
    start_of_day_utc = local_to_utc(start_of_day_local, tz)
    start_of_next_day_utc = local_to_utc(start_of_next_day_local, tz)

    return start_of_day_utc, start_of_next_day_utc