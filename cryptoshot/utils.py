from datetime import datetime
from calendar import timegm
from zoneinfo import ZoneInfo, available_timezones
import csv
import json

from .types import Prices
from .exceptions import InvalidTimeZoneException


def timezones() -> list[str]:
    return list(available_timezones())


def unix_timestamp_seconds_from_str(date_time: str, date_time_format: str, timezone: str) -> int:
    if timezone not in available_timezones():
        raise InvalidTimeZoneException(f"Invalid timezone: {timezone}")

    datetime_obj = datetime.strptime(date_time, date_time_format)
    datetime_obj = datetime_obj.replace(tzinfo=ZoneInfo(timezone))
    timestamp = timegm(datetime_obj.astimezone(ZoneInfo("GMT")).timetuple())
    return timestamp


def prices_to_csv(prices: Prices, file_path: str):
    csv_dict: dict[str, float] = {}
    for asset_id, asset_prices in prices.items():
        for service_id, asset_value_at_time in asset_prices.items():
            key = f"{asset_id}_{asset_value_at_time['quote_asset']}_{service_id}_{asset_value_at_time['timestamp']}"
            value = asset_value_at_time["value"]
            csv_dict[key] = value

    csv_dict_sorted = dict(sorted(csv_dict.items()))

    with open(file_path, "w") as f:
        w = csv.DictWriter(f, csv_dict_sorted.keys())
        w.writeheader()
        w.writerow(csv_dict_sorted)


def dict_to_json(dict_obj: dict, file_path: str):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(dict_obj, f, ensure_ascii=False, sort_keys=True, indent=4)
