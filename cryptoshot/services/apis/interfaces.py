from logging import Logger

from ..types import ApiConfig
from ..exceptions import InvalidApiConfigException
from ..interfaces import (
    BalanceOracleInterface,
    PriceOracleInterface,
    BalanceProviderInterface,
    ServiceInterface,
)


class ApiInterface(ServiceInterface):
    def __init__(self, config: ApiConfig, log: Logger) -> None:
        super().__init__(config=config, log=log)
        if not config["api_token"]:
            raise InvalidApiConfigException("Expected 'api_token'")


class PriceOracleApiInterface(ApiInterface, PriceOracleInterface):
    def __init__(self, config: ApiConfig, log: Logger) -> None:
        super().__init__(config=config, log=log)


class BalanceProviderApiInterface(ApiInterface, BalanceProviderInterface):
    def __init__(self, config: ApiConfig, log: Logger) -> None:
        super().__init__(config=config, log=log)


class BalanceOracleApiInterface(ApiInterface, BalanceOracleInterface):
    def __init__(self, config: ApiConfig, log: Logger) -> None:
        super().__init__(config=config, log=log)
