from types import MappingProxyType

from .interfaces import ServiceInterface
from .types import ServiceType

from .apis.coinapi import CoinAPI
from .apis.coingecko import CoinGeckoAPI
from .apis.kraken import KrakenAPI
from .apis.routescan import RoutescanAPI

SERVICES: MappingProxyType[ServiceType, type[ServiceInterface]] = MappingProxyType(
    {
        # SERVICES identifies the mapping between a ServiceType value and a class implementing ServiceInterface
        ServiceType.COINAPI: CoinAPI,
        ServiceType.COINGECKO: CoinGeckoAPI,
        ServiceType.KRAKEN: KrakenAPI,
        ServiceType.ROUTESCAN: RoutescanAPI,
    }
)
