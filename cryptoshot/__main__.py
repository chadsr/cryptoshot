import logging
import argparse
import sys
from datetime import datetime

from .__init__ import __version__, __description__
from .utils import timezoned_datetime_from_str, get_timezones
from .cryptoshot import Cryptoshot
from .config import get_config
from .logger import LoggerAdapter
from .exceptions import CryptoshotException

logger = logging.getLogger(__name__)
log = LoggerAdapter(logger)

DEFAULT_CONFIG_PATH = "./config.json"
DEFAULT_DATETIME_STRING_FORMAT: str = "%d-%m-%Y/%H:%M:%S"
DEFAULT_DATETIME_STRING: str = datetime.now().strftime(DEFAULT_DATETIME_STRING_FORMAT)


def timezones(args: argparse.Namespace) -> None:
    timezones = get_timezones()
    print(*timezones, sep="\n")


def run(args: argparse.Namespace) -> None:
    config_path: str = args.config_path
    config = get_config(config_path=config_path)

    date_time: str = args.datetime
    date_time_format: str = config["formatting"]["timestamp"]
    timezone: str = args.timezone

    datetime_tzd = timezoned_datetime_from_str(
        date_time=date_time,
        date_time_format=date_time_format,
        timezone=timezone,
    )

    try:
        cryptoshot = Cryptoshot(config=config, logger=log.logger, datetime_tzd=datetime_tzd)
        cryptoshot.print_balances()
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

    sub_parsers = parser.add_subparsers()
    run_parser = sub_parsers.add_parser("run", help="Run cryptoshot")
    run_parser.set_defaults(func=run)
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

    timezone_parser = sub_parsers.add_parser("timezones", help="List valid timezone strings")
    timezone_parser.set_defaults(func=timezones)

    return parser


def main() -> None:
    arg_parser = init_argparse()
    args = arg_parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
