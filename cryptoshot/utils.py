from datetime import datetime
import pytz

from .exceptions import InvalidTimeZoneException


def get_timezones() -> list[str]:
    """
    Return a list of valid timezone strings
    """

    return pytz.all_timezones


def timezoned_datetime_from_str(date_time: str, date_time_format: str, timezone: str) -> datetime:
    """
    Return a TimezonedDatetime object from the given date/time, format and timezone strings
    """

    tz_info = pytz.UTC
    try:
        tz_info = pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError as e:
        raise InvalidTimeZoneException(e)

    dt: datetime = datetime.strptime(date_time, date_time_format)
    return datetime.combine(date=dt.date(), time=dt.time(), tzinfo=tz_info)
