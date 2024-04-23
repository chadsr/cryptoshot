import time
from enum import Enum
from typing import NamedTuple, TypedDict
from logging import Logger

from ..exceptions import (
    InvalidServiceConfigException,
    NoSupportedAssetsException,
    NoValueFoundException,
    RequestException,
    PriceOracleException,
    UnsupportedAssetIDException,
    UnsupportedBaseCurrencyException,
)
from ..types import (
    AssetBalanceAtTime,
    Assets,
    AssetID,
    AssetPairs,
    AssetValueAtTime,
    HttpHeaders,
    KrakenConfig,
)

from .requests import JSON_HEADERS, get_json_request
from .interfaces import BalanceOracleInterface, PriceOracleInterface

KRAKEN_API_BASE_URL = "https://api.kraken.com/0"
KRAKEN_API_PUBLIC_BASE_URL = f"{KRAKEN_API_BASE_URL}/public"

# Negative offset applied to the original timestamp, when no trades are found in the current window
OFFSET_TIMESTAMP_SECONDS = 60

# Offset cumulative limit to stop searching at and return an exception
OFFSET_TIMESTAMP_MAX_SECONDS = 3600

WAIT_TIME_INCREMENT_SECONDS = 5


class KrakenResponseError(Enum):
    TOO_MANY_REQUESTS = "EGeneral:Too many requests"


class KrakenAssetClass(Enum):
    CURRENCY = "currency"


class KrakenTradeType(Enum):
    BUY = "b"
    SELL = "s"


class KrakenOrderType(Enum):
    MARKET = "m"
    LIMIT = "l"


class ResponseAsset(TypedDict):
    altname: AssetID | AssetID
    aclass: str
    decimals: int


class ResponseAssets(TypedDict):
    # https://docs.kraken.com/rest/#tag/Spot-Market-Data/operation/getAssetInfo
    result: dict[str, ResponseAsset]


class ResponseAssetPair(TypedDict):
    base: AssetID | AssetID
    altname: str
    wsname: str
    base: str
    aclass_base: str
    quote: str
    aclass_quote: str


class ResponseAssetPairs(TypedDict):
    # https://docs.kraken.com/rest/#tag/Spot-Market-Data/operation/getTradableAssetPairs
    result: dict[str, ResponseAssetPair]


class Trade(NamedTuple):
    price: float
    quantity: float
    timestamp: float
    trade_type: str
    order_type: str
    unknown: str
    nonce: int


class ResponseTrades(TypedDict):
    # https://docs.kraken.com/rest/#tag/Spot-Market-Data/operation/getRecentTrades
    result: dict[str, list[list]]


class KrakenAPI(PriceOracleInterface, BalanceOracleInterface):
    def __init__(self, config: KrakenConfig, log: Logger) -> None:
        super().__init__(config=config, log=log)

        if not config["private_key"]:
            raise InvalidServiceConfigException("Expected 'private_key'")

        self.config = config

        self.base_url_api: str = KRAKEN_API_BASE_URL
        self.base_url_api_public: str = KRAKEN_API_PUBLIC_BASE_URL

        self.auth_headers: HttpHeaders = {}
        self.auth_headers.update(JSON_HEADERS)
        self.auth_headers["APIKey"] = self.config["api_token"]
        self.auth_headers["Authent"] = self.config["private_key"]

        self.assets = self._get_assets()
        self.asset_pairs: AssetPairs = self._get_asset_pairs()

    def _get_assets(self) -> Assets:
        assets: Assets = {}

        url = f"{self.base_url_api_public}/Assets"

        try:
            res_assets: ResponseAssets = get_json_request(url=url, headers=self.auth_headers)

            for asset_info in res_assets["result"].values():
                asset_id = asset_info["altname"]
                asset_class = asset_info["aclass"]

                if asset_class == KrakenAssetClass.CURRENCY.value:
                    if asset_id in assets:
                        self.log.warn(f"Asset '{asset_id}' already indexed")

                    asset_name = asset_info["altname"]
                    asset_decimals = asset_info["decimals"]

                    assets[asset_id] = {
                        "id": asset_id,
                        "name": asset_name,
                        "decimals": asset_decimals,
                    }
                else:
                    self.log.debug(f"skipping asset {asset_id} with class {asset_class}")

            return assets
        except RequestException as e:
            raise PriceOracleException(e)

    def _get_asset_pairs(self) -> AssetPairs:
        available_asset_pairs: AssetPairs = {}

        url = f"{self.base_url_api_public}/AssetPairs"

        try:
            res_asset_pairs: ResponseAssetPairs = get_json_request(
                url=url, headers=self.auth_headers
            )

            for asset_pair in res_asset_pairs["result"].values():
                base_asset_id, quote_asset_id = asset_pair["wsname"].split("/")
                base_asset_class = asset_pair["aclass_base"]
                quote_asset_class = asset_pair["aclass_quote"]

                if (
                    base_asset_class == KrakenAssetClass.CURRENCY.value
                    and quote_asset_class == KrakenAssetClass.CURRENCY.value
                ):
                    if base_asset_id not in available_asset_pairs:
                        available_asset_pairs[base_asset_id] = set()

                    available_asset_pairs[base_asset_id].add(quote_asset_id)

                    # some base assets are not listed on the /Assets endpoint so populate them
                    if self.assets and base_asset_id not in self.assets:
                        self.assets[base_asset_id] = {"id": base_asset_id, "name": base_asset_id}

            return available_asset_pairs
        except RequestException as e:
            raise PriceOracleException(e)

    def supported_assets(self) -> Assets:
        if self.assets is None:
            raise NoSupportedAssetsException()

        return self.assets

    def supported_asset_pairs(self) -> AssetPairs:
        return self.asset_pairs

    def value_at(self, asset_id, quote_asset_id, timestamp_unix_seconds) -> AssetValueAtTime:
        if self.assets is None:
            raise NoSupportedAssetsException()

        if asset_id not in self.asset_pairs:
            raise UnsupportedAssetIDException(
                f"Asset ID '{asset_id}' is not supported by price oracle service '{self.config['type']}'"
            )

        if quote_asset_id not in self.asset_pairs[asset_id]:
            raise UnsupportedBaseCurrencyException(
                f"Pair {asset_id}/{quote_asset_id} is not supported by price oracle service '{self.config['type']}'"
            )

        asset_pair = f"{asset_id}{quote_asset_id}"
        url = f"{self.base_url_api_public}/Trades"

        asset_value_at_time: AssetValueAtTime | None = None
        offset_timestamp_unix_seconds = timestamp_unix_seconds
        wait_time_seconds = 0
        while asset_value_at_time is None:
            if (
                timestamp_unix_seconds - offset_timestamp_unix_seconds
            ) >= OFFSET_TIMESTAMP_MAX_SECONDS:
                raise NoValueFoundException(
                    f"no asset trade value found within window {offset_timestamp_unix_seconds} -> {timestamp_unix_seconds}"
                )

            params = {
                "pair": asset_pair,
                "since": offset_timestamp_unix_seconds,
            }

            try:
                res_trades_json: ResponseTrades = get_json_request(
                    url=url, params=params, headers=self.auth_headers
                )

                # successful request, so reset wait time
                wait_time_seconds = 0

                pair_key = list(res_trades_json["result"].keys())[0]
                trades_obj = res_trades_json["result"][pair_key]
                if len(trades_obj) == 0:
                    self.log.debug(
                        f"No trades found between {offset_timestamp_unix_seconds} -> {timestamp_unix_seconds}"
                    )
                    continue

                # Store the current closest values to timestamp_unix_seconds
                closest_trade_price: float | None = None
                closest_trade_timestamp_seconds: int | None = None

                for trade_list in trades_obj:
                    trade = Trade._make(trade_list)
                    trade_timestamp_seconds = int(trade.timestamp)

                    if trade_timestamp_seconds > timestamp_unix_seconds:
                        # Need a value closest to, but less than timestamp_unix_seconds, so stop
                        break

                    if trade_timestamp_seconds < offset_timestamp_unix_seconds:
                        # This really shouldn't happen, but handle it anyway
                        self.log.warn(
                            f"Trade is older than the offset timestamp ({trade_timestamp_seconds} < {offset_timestamp_unix_seconds})"
                        )
                        continue

                    if trade.order_type == KrakenOrderType.MARKET.value:
                        # Use market orders since their trade price reflects the market price
                        closest_trade_price = float(trade.price)
                        closest_trade_timestamp_seconds = trade_timestamp_seconds
                    else:
                        self.log.debug(
                            f"ignoring trade of order type '{trade.order_type}' and trade type '{trade.trade_type}'"
                        )
                        continue

                if closest_trade_price and closest_trade_timestamp_seconds:
                    asset_value_at_time = {
                        "asset": self.assets[asset_id],
                        "quote_asset": quote_asset_id,
                        "timestamp": closest_trade_timestamp_seconds,
                        "value": closest_trade_price,
                    }

                    self.log.debug(
                        f"Using trade value {closest_trade_price} at {closest_trade_timestamp_seconds} as {asset_pair} value."
                    )

                    break
                else:
                    offset_timestamp_unix_seconds -= OFFSET_TIMESTAMP_SECONDS
                    continue

            except RequestException as e:
                if (
                    e.error_messages
                    and KrakenResponseError.TOO_MANY_REQUESTS.value in e.error_messages
                ):
                    wait_time_seconds += WAIT_TIME_INCREMENT_SECONDS
                    self.log.warn(
                        f"API rate-limit hit. waiting {wait_time_seconds}s until next request..."
                    )
                    time.sleep(wait_time_seconds)
                    continue

                raise PriceOracleException(e)

        if asset_value_at_time is None:
            raise PriceOracleException("no asset value found")

        return asset_value_at_time

    def balance_at(self, asset_id, timestamp_unix_seconds) -> AssetBalanceAtTime:
        if self.assets is None:
            raise NoSupportedAssetsException()

        asset_balance_at_time: AssetBalanceAtTime = {
            "asset": self.assets[asset_id],
            "timestamp": timestamp_unix_seconds,
            "value": 0,
        }
        return asset_balance_at_time
