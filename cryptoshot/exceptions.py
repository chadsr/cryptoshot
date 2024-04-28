class CryptoshotException(Exception):
    pass


class InvalidConfigException(CryptoshotException):
    pass


class InvalidServiceTypeException(CryptoshotException):
    pass


class InvalidPriceOracleException(CryptoshotException):
    pass


class InvalidTimeZoneException(CryptoshotException):
    pass


class LoadConfigException(CryptoshotException):
    pass
