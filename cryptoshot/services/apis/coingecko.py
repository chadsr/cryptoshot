from enum import IntEnum, StrEnum
from logging import Logger
from types import MappingProxyType
from typing import TypeAlias, TypedDict, cast

from ...services.utils import unix_timestamp_seconds_from_int
from ...services.types import (
    ApiConfig,
    AssetID,
    Assets,
    AssetPairs,
    AssetValueAtTime,
    HttpHeaders,
)
from ...services.exceptions import (
    NoSupportedAssetsException,
    NoSupportedAssetsPairsException,
    NoValueFoundException,
    PriceOracleException,
    UnsupportedAssetIDException,
    UnsupportedQuoteAssetIDException,
)

from .interfaces import PriceOracleApiInterface
from .exceptions import ApiRateLimitException, RequestException, TooManyRequestsException
from .requestutils import HEADERS_JSON, get_json_request

COINGECKO_API_BASE_URL = "https://api.coingecko.com/api/v3"

CoinGeckoCoinID: TypeAlias = str


class ResponseCoin(TypedDict):
    id: CoinGeckoCoinID
    name: str
    symbol: AssetID


ResponseCoins: TypeAlias = list[ResponseCoin]
ResponseCurrencies: TypeAlias = list[AssetID]


ParamsCoinHistoricalChartRange = TypedDict(
    "ParamsCoinHistoricalChartRange",
    {
        "vs_currency": AssetID,
        "from": int,
        "to": int,
    },
)


class ResponseCoinHistoricalChartRange(TypedDict):
    prices: list[tuple[int, float]]
    market_caps: list[tuple[int, float]]
    total_volumes: list[tuple[int, float]]


CGCoinIDs: TypeAlias = dict[AssetID, CoinGeckoCoinID]


class CoinGeckoApiError(TypedDict):
    timestamp: str
    error_code: int
    error_message: str


class ResponseError(TypedDict):
    status: CoinGeckoApiError


class CoinGeckoErrorCode(IntEnum):
    EXCEEDS_TIME_RANGE = 10012


class CoinGeckoErrors(StrEnum):
    COIN_NOT_FOUND = "coin not found"


CoinGeckoCoinIDMap: MappingProxyType[AssetID, CoinGeckoCoinID] = MappingProxyType(
    {
        # mapping of asset ID to internal IDs, which take precedence in lookups
        "btc": "bitcoin",
        "bch": "bitcoin-cash",
        "eth": "ethereum",
        "ksm": "kusama",
        "dot": "polkadot",
    }
)


class CoinGeckoAPI(PriceOracleApiInterface):
    def __init__(self, config: ApiConfig, log: Logger) -> None:
        super().__init__(config=config, log=log)

        self.__base_url_api: str = COINGECKO_API_BASE_URL

        self.__auth_headers: HttpHeaders = {}
        self.__auth_headers.update(HEADERS_JSON)
        self.__auth_headers["x-cg-demo-api-key"] = config["api_token"]

        res_coins = self.__get_coins()

        self.cg_coin_ids: CGCoinIDs = self.__cg_coin_ids(res_coins)
        self.__assets__ = self.__get_assets(res_coins)
        if len(self.__assets__) == 0:
            raise NoSupportedAssetsException()

        self.__asset_pairs__ = self.__get_asset_pairs(self.__assets__)
        if len(self.__asset_pairs__) == 0:
            raise NoSupportedAssetsPairsException()

    def __get_coins(self) -> ResponseCoins:
        try:
            url = f"{self.__base_url_api}/coins/list"
            res_coins = get_json_request(url=url, headers=self.__auth_headers)
            return cast(ResponseCoins, res_coins)
        except TooManyRequestsException as e:
            raise ApiRateLimitException(e)
        except RequestException as e:
            raise PriceOracleException(e)

    @staticmethod
    def __cg_coin_ids(res_coins: ResponseCoins) -> CGCoinIDs:
        cg_coin_ids: CGCoinIDs = {}

        for res_coin in res_coins:
            asset_id = res_coin["symbol"].casefold()
            cg_coin_id = res_coin["id"].casefold()

            if asset_id in CoinGeckoCoinIDMap:
                cg_coin_id = CoinGeckoCoinIDMap[asset_id]
            elif asset_id in cg_coin_ids:
                # TODO: find a better solution to dupe symbols
                asset_id = cg_coin_id

            cg_coin_ids[asset_id] = cg_coin_id

        return cg_coin_ids

    @staticmethod
    def __get_assets(res_coins: ResponseCoins) -> Assets:
        assets: Assets = {}

        for res_coin in res_coins:
            cg_asset_id = res_coin["id"].casefold()
            asset_id = res_coin["symbol"].casefold()
            asset_name = res_coin["name"]

            # if the symbol has already been stored, store subsequent under the internal CG ID
            if asset_id not in CoinGeckoCoinIDMap and asset_id in assets:
                # TODO: find a better solution to dupe symbols
                asset_id = cg_asset_id

            assets[asset_id] = {
                "id": asset_id,
                "name": asset_name,
                "service_asset_id": cg_asset_id,
            }

        return assets

    def __get_asset_pairs(self, assets: Assets) -> AssetPairs:
        available_asset_pairs: AssetPairs = {}

        try:
            url = f"{self.__base_url_api}/simple/supported_vs_currencies"
            res_currencies = get_json_request(url=url, headers=self.__auth_headers)
            res_currencies = cast(ResponseCurrencies, res_currencies)

            for asset_id in assets:
                available_asset_pairs[asset_id] = set([c.casefold() for c in res_currencies])

                if asset_id in available_asset_pairs[asset_id]:
                    # remove asset_id/asset_id 1-1 pairing
                    available_asset_pairs[asset_id].remove(asset_id)

        except TooManyRequestsException as e:
            raise ApiRateLimitException(e)
        except RequestException as e:
            raise PriceOracleException(e)

        return available_asset_pairs

    def value_at(self, asset_id, quote_asset_id, timestamp_unix_seconds) -> AssetValueAtTime:
        asset_id = asset_id.casefold()
        quote_asset_id = quote_asset_id.casefold()

        if not self.asset_supported(asset_id):
            raise UnsupportedAssetIDException(asset_id=asset_id)

        if not self.asset_pair_supported(asset_id, quote_asset_id):
            raise UnsupportedQuoteAssetIDException(quote_asset_id=quote_asset_id)

        cg_coin_id = self.cg_coin_ids[asset_id]
        params_chart_range: ParamsCoinHistoricalChartRange = {
            "from": timestamp_unix_seconds - 3600,
            "to": timestamp_unix_seconds,
            "vs_currency": quote_asset_id,
        }

        try:
            url = f"{self.__base_url_api}/coins/{cg_coin_id}/market_chart/range"
            res_chart_range = get_json_request(
                url=url, params=params_chart_range, headers=self.__auth_headers
            )
            res_chart_range = cast(ResponseCoinHistoricalChartRange, res_chart_range)

            closest_timestamp_seconds = 0
            closest_price: float | None = None
            for timestamp, asset_price in res_chart_range["prices"]:
                # format timestamp to seconds
                price_timestamp_seconds = unix_timestamp_seconds_from_int(timestamp)

                if price_timestamp_seconds > timestamp_unix_seconds:
                    break

                if price_timestamp_seconds > closest_timestamp_seconds:
                    closest_timestamp_seconds = price_timestamp_seconds
                    closest_price = asset_price

            if closest_price is None:
                raise NoValueFoundException()

            asset = self.__assets__[asset_id]
            asset_value_at_time: AssetValueAtTime = {
                "asset": asset,
                "quote_asset": quote_asset_id,
                "timestamp": closest_timestamp_seconds,
                "value": closest_price,
            }
            return asset_value_at_time

        except TooManyRequestsException as e:
            raise ApiRateLimitException(e)
        except RequestException as e:
            if e.error_messages and len(e.error_messages) > 0:
                error_obj = e.error_messages[0]
                if isinstance(error_obj, str):
                    match error_obj:
                        case CoinGeckoErrors.COIN_NOT_FOUND:
                            raise UnsupportedAssetIDException(asset_id)
                if isinstance(error_obj, dict):
                    status_obj = error_obj.get("status")
                    if isinstance(status_obj, dict):
                        error_code = status_obj.get("error_code")
                        if isinstance(error_code, int):
                            if error_code == CoinGeckoErrorCode.EXCEEDS_TIME_RANGE:
                                raise NoValueFoundException("Available time range exceeded")

            raise PriceOracleException(e)
