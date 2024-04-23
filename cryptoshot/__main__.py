import logging
import argparse
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from .__init__ import __version__, __description__
from .utils import prices_to_csv, timezones, unix_timestamp_seconds_from_str
from .cryptoshot import Cryptoshot
from .config import load_config
from .logger import LoggerAdapter
from .exceptions import CryptoshotException

logger = logging.getLogger("rich")

DEFAULT_CONFIG_PATH = "./config.json"
DEFAULT_DATETIME_STRING_FORMAT: str = "%d-%m-%Y/%H:%M:%S"
DEFAULT_DATETIME_STRING: str = datetime.now().strftime(DEFAULT_DATETIME_STRING_FORMAT)


def print_timezones(args: argparse.Namespace) -> None:
    tzs = timezones()
    print(*tzs, sep="\n")


def get(args: argparse.Namespace) -> None:
    log_level: int = args.log_level
    log = LoggerAdapter(logger)
    log.setLevel(log_level)

    config_path: str = args.config_path
    config = load_config(config_path=config_path)

    date_time: str = args.datetime
    date_time_format: str = config["formatting"]["timestamp"]
    timezone: str = args.timezone

    timestamp_unix_seconds = unix_timestamp_seconds_from_str(
        date_time=date_time,
        date_time_format=date_time_format,
        timezone=timezone,
    )

    show_prices: bool = args.prices
    show_balances: bool = args.balances
    save_to_csv: bool = args.csv

    try:
        cryptoshot = Cryptoshot(
            config=config, logger=log.logger, timestamp_unix_seconds=timestamp_unix_seconds
        )

        if show_balances:
            balances = cryptoshot.balances()
            print(balances)
        if show_prices:
            prices = cryptoshot.prices()
            print(prices)

            if save_to_csv:
                csv_path = (
                    f"./prices_{date_time}_{datetime.now(tz=ZoneInfo(timezone)).isoformat()}.csv"
                )
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

    timezone_parser = sub_parsers.add_parser("timezones", help="List valid timezone strings")
    timezone_parser.set_defaults(func=timezones)

    return parser


def main() -> None:
    arg_parser = init_argparse()
    args = arg_parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
