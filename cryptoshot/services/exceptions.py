from ..exceptions import CryptoshotException, InvalidConfigException
from .types import AddressType, AssetID


class ServiceException(CryptoshotException):
    pass


class InvalidServiceConfigException(InvalidConfigException):
    pass


class InvalidApiConfigException(InvalidServiceConfigException):
    pass


class PriceOracleException(ServiceException):
    pass


class BalanceServiceException(ServiceException):
    pass


class ZeroBalanceException(BalanceServiceException):
    pass


class BalanceOracleException(BalanceServiceException):
    pass


class EthRPCException(BalanceServiceException):
    pass


class UnsupportedAddressTypeException(BalanceOracleException):
    def __init__(self, address_type: AddressType) -> None:
        self.address_type = address_type


class NoBalancesFoundException(BalanceOracleException):
    pass


class NoClosestBlockException(BalanceOracleException):
    def __init__(self, timestamp_unix_seconds: int | None = None) -> None:
        self.timestamp_unix_seconds = timestamp_unix_seconds


class BalanceProviderException(BalanceServiceException):
    pass


class NoSupportedAssetsException(ServiceException):
    pass


class NoSupportedAssetsPairsException(PriceOracleException):
    pass


class UnsupportedAssetIDException(ServiceException):
    def __init__(self, asset_id: AssetID) -> None:
        self.asset_id = asset_id


class UnsupportedQuoteAssetIDException(PriceOracleException):
    def __init__(self, quote_asset_id: AssetID) -> None:
        self.quote_asset_id = quote_asset_id


class NoValueFoundException(PriceOracleException):
    pass
