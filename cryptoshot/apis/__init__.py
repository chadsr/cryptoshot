from .interfaces import ApiInterface

from .coinapi import CoinAPI
from .kraken import KrakenAPI
# from .coingecko import CoinGeckoAPI

from ..types import PriceOracleID, ServiceID

APIS: dict[ServiceID, type[ApiInterface]] = {
    PriceOracleID.KRAKEN.value: KrakenAPI,
    PriceOracleID.COINAPI.value: CoinAPI,
    # PriceOracleID.COINGECKO.value: CoinGeckoAPI,
}
