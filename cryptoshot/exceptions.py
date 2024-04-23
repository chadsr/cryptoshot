from .types import JSON


class CryptoshotException(Exception):
    pass


class RequestException(CryptoshotException):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        result: JSON | None = None,
        error_messages: list[str] | None = None,
        exception: Exception | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.result_json = result
        self.exception = exception
        self.error_messages = error_messages


class InvalidServiceConfigException(CryptoshotException):
    pass


class InvalidPriceOracleException(CryptoshotException):
    pass


class InvalidBalanceOracleException(CryptoshotException):
    pass


class UnsupportedAssetIDException(CryptoshotException):
    pass


class UnsupportedBaseCurrencyException(CryptoshotException):
    pass


class NoSupportedAssetsException(CryptoshotException):
    pass


class NoValueFoundException(CryptoshotException):
    pass


class PriceOracleException(CryptoshotException):
    pass


class InvalidTimeZoneException(CryptoshotException):
    pass


class LoadConfigException(CryptoshotException):
    pass


class MalformedAssetPairException(CryptoshotException):
    pass
