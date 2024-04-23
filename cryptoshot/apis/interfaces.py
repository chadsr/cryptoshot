from abc import abstractmethod
from typing import Protocol
from logging import Logger

from ..exceptions import InvalidServiceConfigException
from ..types import (
    AssetID,
    AssetValueAtTime,
    Assets,
    ServiceConfig,
    ServiceID,
    AssetBalanceAtTime,
)


class ApiInterface(Protocol):
    config: ServiceConfig
    log: Logger
    assets: Assets | None

    def __init__(self, config: ServiceConfig, log: Logger) -> None:
        if not config["api_token"]:
            raise InvalidServiceConfigException("Expected 'api_token'")

        self.config = config
        self.log = log
        self.assets = None

    def service_id(self) -> ServiceID:
        return self.config["type"]


class PriceOracleInterface(ApiInterface):
    @abstractmethod
    def supported_assets(self) -> Assets:
        pass

    @abstractmethod
    def value_at(
        self, asset_id: AssetID, quote_asset_id: AssetID, timestamp_unix_seconds: int
    ) -> AssetValueAtTime:
        pass


class BalanceOracleInterface(ApiInterface):
    @abstractmethod
    def balance_at(self, asset_id: AssetID, timestamp_unix_seconds: int) -> AssetBalanceAtTime:
        pass
