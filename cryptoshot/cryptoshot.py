from datetime import datetime
import logging

from .types import Config


class Cryptoshot:
    def __init__(self, config: Config, logger: logging.Logger, datetime_tzd: datetime) -> None:
        self.config: Config = config
        self.datetime_tzd: datetime = datetime_tzd

    def print_balances(self) -> None:
        print("yay")
