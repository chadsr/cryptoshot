from abc import ABC, abstractmethod
from logging import Logger
from typing import Literal

from .types import (
    AccountAddress,
    AddressType,
    AssetBalancesAtTime,
    AssetID,
    AssetPairs,
    Assets,
    AssetValueAtTime,
    ServiceConfig,
    ServiceName,
    ServiceType,
)
from .exceptions import InvalidServiceConfigException

REQUIRED_CONFIG_FIELDS: tuple[Literal["type", "name"], ...] = ("type", "name")


class ServiceInterface(ABC):
    __name__: ServiceName
    __type__: ServiceType
    __assets__: Assets
    __config__: ServiceConfig
    __log__: Logger

    def __init__(self, config: ServiceConfig, log: Logger) -> None:
        self.__validate_config(config)
        self.__name__ = config["name"]
        self.__type__ = config["type"]
        self.__assets__ = {}
        self.__config__ = config
        self.__log__ = log

    @staticmethod
    def __validate_config(config: ServiceConfig) -> None:
        for key in REQUIRED_CONFIG_FIELDS:
            value = config[key]
            if value is None or value == "":
                raise InvalidServiceConfigException(
                    f"service configuration missing value for field '{key}'"
                )

    def get_name(self) -> ServiceName:
        return self.__name__

    def get_type(self) -> ServiceType:
        return self.__type__

    def supported_assets(self) -> Assets:
        return self.__assets__

    def asset_supported(self, asset_id: AssetID) -> bool:
        # TODO: normalise assetID casing (casefold) before storing
        if asset_id.upper() in self.__assets__ or asset_id.casefold() in self.__assets__:
            return True

        return False


class PriceOracleInterface(ABC):
    __asset_pairs__: AssetPairs

    def supported_asset_pairs(self) -> AssetPairs:
        return self.__asset_pairs__

    def asset_pair_supported(self, asset_id: AssetID, quote_asset_id: AssetID) -> bool:
        # TODO: normalise assetID casing (casefold) before storing
        asset_ids = [asset_id.upper(), asset_id.casefold()]
        quote_asset_ids = [quote_asset_id.upper(), quote_asset_id.casefold()]

        for aid in asset_ids:
            if aid in self.__asset_pairs__:
                for qid in quote_asset_ids:
                    if qid in self.__asset_pairs__[aid]:
                        return True

        return False

    @abstractmethod
    def value_at(
        self, asset_id: AssetID, quote_asset_id: AssetID, timestamp_unix_seconds: int
    ) -> AssetValueAtTime:
        pass


class BalanceServiceInterface(ABC):
    pass


class BalanceProviderInterface(BalanceServiceInterface, ABC):
    # @abstractmethod
    # def balance_at(self, asset_id: AssetID, timestamp_unix_seconds: int) -> AssetBalanceAtTime:
    #     pass

    @abstractmethod
    def all_balances_at(self, timestamp_unix_seconds: int) -> AssetBalancesAtTime:
        pass


class BalanceOracleInterface(BalanceServiceInterface, ABC):
    __supported_address_types: set[AddressType]

    @abstractmethod
    def supported_address_types(self) -> set[AddressType]:
        pass

    # @abstractmethod
    # def balance_at(
    #     self, address: AccountAddress, asset_id: AssetID, timestamp_unix_seconds: int
    # ) -> AssetBalanceAtTime:
    #     pass

    @abstractmethod
    def all_balances_at(
        self, account: AccountAddress, timestamp_unix_seconds: int
    ) -> AssetBalancesAtTime:
        pass
