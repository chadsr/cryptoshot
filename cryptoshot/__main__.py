import logging
import argparse
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from .__init__ import __version__, __description__
from .utils import dict_to_json, prices_to_csv, timezones, unix_timestamp_seconds_from_str
from .cryptoshot import Cryptoshot
from .config import load_config
from .logger import LOGGER, LoggerAdapter
from .exceptions import CryptoshotException


DEFAULT_CONFIG_PATH = "./config.json"
DEFAULT_DATETIME_STRING_FORMAT: str = "%d-%m-%Y/%H:%M:%S"
DEFAULT_DATETIME_STRING: str = datetime.now().strftime(DEFAULT_DATETIME_STRING_FORMAT)


def print_timezones() -> None:
    tzs = timezones()
    print(*tzs, sep="\n")


def get(args: argparse.Namespace) -> None:
    log_level: int = args.log_level
    for name in logging.root.manager.loggerDict:
        logging.getLogger(name).setLevel(log_level)

    log = LoggerAdapter(LOGGER)
    log.setLevel(log_level)

    config_path: str = args.config_path
    config = load_config(config_path=config_path)

    date_time: str = args.datetime
    date_time_format: str = config["formatting"]["timestamp"]
    timezone: str = args.timezone

    datetime_obj = datetime.strptime(date_time, date_time_format)
    datetime_obj = datetime_obj.replace(tzinfo=ZoneInfo(timezone))

    timestamp_unix_seconds = unix_timestamp_seconds_from_str(
        date_time=date_time,
        date_time_format=date_time_format,
        timezone=timezone,
    )

    show_prices: bool = args.prices
    show_balances: bool = args.balances
    save_to_json: bool = args.json
    save_to_csv: bool = args.csv

    try:
        cryptoshot = Cryptoshot(
            config=config, logger=log.logger, timestamp_unix_seconds=timestamp_unix_seconds
        )

        file_path_format = (
            f"{datetime_obj.isoformat()}_{datetime.now(tz=ZoneInfo(timezone)).isoformat()}"
        )
        if show_balances:
            balances = cryptoshot.balances()
            print(balances)

            balances_file_path = "./balances"
            if save_to_json:
                json_path = f"{balances_file_path}_{file_path_format}.json"
                dict_to_json(balances, json_path)

        if show_prices:
            prices = cryptoshot.prices()
            print(prices)

            prices_file_path = "./prices"
            if save_to_json:
                json_path = f"{prices_file_path}_{file_path_format}.json"
                dict_to_json(prices, json_path)

            if save_to_csv:
                csv_path = f"{prices_file_path}_{file_path_format}.csv"
                prices_to_csv(prices, csv_path)

    except CryptoshotException as e:
        log.logger.exception(e)
        sys.exit(1)


def init_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"{__description__}")
    parser.add_argument("-v", "--version", action="version", version=f"{__version__}")
    parser.add_argument(
        "-c",
        "--config-path",
        type=str,
        default=DEFAULT_CONFIG_PATH,
        help="The path to the configuration file",
    )
    parser.add_argument(
        "-l",
        "--log-level",
        type=int,
        default=logging.INFO,
        help="The log level to output",
    )

    sub_parsers = parser.add_subparsers()
    run_parser = sub_parsers.add_parser("get", help="Run cryptoshot")
    run_parser.set_defaults(func=get)
    run_parser.add_argument(
        "-d",
        "--datetime",
        type=str,
        default=DEFAULT_DATETIME_STRING,
        help="The date/time to check balances at",
    )
    run_parser.add_argument(
        "-t",
        "--timezone",
        type=str,
        required=True,
        help="The timezone to use",
    )
    run_parser.add_argument(
        "-p",
        "--prices",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Print price information",
    )
    run_parser.add_argument(
        "-b",
        "--balances",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Print balance information",
    )
    run_parser.add_argument(
        "-c",
        "--csv",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Save output to CSV file",
    )
    run_parser.add_argument(
        "-j",
        "--json",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Save output to JSON file",
    )

    timezone_parser = sub_parsers.add_parser("timezones", help="List valid timezone strings")
    timezone_parser.set_defaults(func=timezones)

    return parser


def main() -> None:
    arg_parser = init_argparse()
    args = arg_parser.parse_args()

    try:
        args.func(args)
    except AttributeError:
        arg_parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
