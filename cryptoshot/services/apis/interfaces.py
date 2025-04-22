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


class EvmBalanceOracleApiInterface(BalanceOracleApiInterface):
    __include_chain_ids__: set[int] | None
    __exclude_chain_ids__: set[int] | None

    def __init__(
        self,
        config: ApiConfig,
        log: Logger,
        include_chain_ids: set[int] | None = None,
        exclude_chain_ids: set[int] | None = None,
    ) -> None:
        super().__init__(config=config, log=log)
        self.__include_chain_ids__ = include_chain_ids
        self.__exclude_chain_ids__ = exclude_chain_ids
