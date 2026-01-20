import time
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import NamedTuple, NotRequired, TypedDict, TypeAlias, cast
from logging import Logger
import urllib.parse
import hashlib
import hmac
import base64

from ...services.exceptions import (
    BalanceProviderException,
    NoSupportedAssetsException,
    NoSupportedAssetsPairsException,
    NoValueFoundException,
    PriceOracleException,
    UnsupportedAssetIDException,
    UnsupportedQuoteAssetIDException,
)
from ...services.types import (
    ApiConfig,
    Asset,
    AssetBalanceAtTime,
    AssetBalancesAtTime,
    AssetID,
    AssetPairs,
    Assets,
    AssetValueAtTime,
    HttpHeaders,
)

from .interfaces import BalanceProviderApiInterface, PriceOracleApiInterface
from .exceptions import (
    InvalidAPIConfigException,
    InvalidAPIKeyException,
    RequestException,
    TooManyRequestsException,
)
from .requestutils import HEADERS_JSON, HEADERS_URL_ENCODED, get_json_request, post_json_request

KRAKEN_API_BASE_URL = "https://api.kraken.com"
KRAKEN_API_VERSION_PATH = "/0"
KRAKEN_API_PUBLIC_BASE_URL = f"{KRAKEN_API_BASE_URL}{KRAKEN_API_VERSION_PATH}/public"

# Negative offset applied to the original timestamp, when no trades are found in the current window
OFFSET_TIMESTAMP_SECONDS = 60

# Offset cumulative limit to stop searching at and return an exception
OFFSET_TIMESTAMP_MAX_SECONDS = 3600

WAIT_TIME_INCREMENT_SECONDS: float = 12.0

KrakenAssetID: TypeAlias = str

KrakenAssetIDMap: MappingProxyType[KrakenAssetID, AssetID] = MappingProxyType(
    {
        # mapping of internal IDs, to asset ID to which take precedence in lookups
        "XXBT": "BTC",
    }
)


class KrakenConfig(ApiConfig):
    private_key: str


class KrakenResponseError(StrEnum):
    INVALID_KEY = "EAPI:Invalid key"
    RATE_LIMIT_EXCEEDED = "EAPI:Rate limit exceeded"
    TOO_MANY_REQUESTS = "EGeneral:Too many requests"


class KrakenAssetClass(StrEnum):
    CURRENCY = "currency"


class KrakenTradeType(StrEnum):
    BUY = "b"
    SELL = "s"


class KrakenOrderType(StrEnum):
    MARKET = "m"
    LIMIT = "l"


class KrakenLedgerEntryType(StrEnum):
    ALL = "all"  # used for requesting all types, not a valid entry type
    ADJUSTMENT = "adjustment"
    CREDIT = "credit"
    DEPOSIT = "deposit"
    DIVIDEND = "dividend"
    MARGIN = "margin"
    NFT_REBATE = "nft_rebate"
    ROLLOVER = "rollover"
    SALE = "sale"
    SETTLED = "settled"
    STAKING = "staking"
    TRADE = "trade"
    TRANSFER = "transfer"
    WITHDRAWAL = "withdrawal"


class KrakenLedgerAssetSuffix(StrEnum):
    STAKED = ".S"
    STAKED_7 = "07.S"
    STAKED_14 = "14.S"
    STAKED_28 = "28.S"
    YIELD_BEARING = ".B"
    OPT_IN_REWARD = ".M"
    AUTO_REWARD = ".F"


class ResponseAsset(TypedDict):
    aclass: str
    altname: AssetID | AssetID
    decimals: int


KrakenAssets: TypeAlias = dict[KrakenAssetID, ResponseAsset]


class ResponseAssets(TypedDict):
    # https://docs.kraken.com/rest/#tag/Spot-Market-Data/operation/getAssetInfo
    result: KrakenAssets


class ResponseAssetPair(TypedDict):
    aclass_base: str
    aclass_quote: str
    altname: str
    base: str
    quote: str
    wsname: str


class ResponseAssetPairs(TypedDict):
    # https://docs.kraken.com/rest/#tag/Spot-Market-Data/operation/getTradableAssetPairs
    result: dict[str, ResponseAssetPair]


class Trade(NamedTuple):
    price: float
    volume: float
    timestamp: float
    trade_type: KrakenTradeType
    order_type: KrakenOrderType
    misc: str
    trade_id: int


class ResponseTrades(TypedDict):
    # https://docs.kraken.com/rest/#tag/Spot-Market-Data/operation/getRecentTrades
    result: dict[str, list[list[float | int | str]]]


KrakenLedgerAssetsAll: KrakenAssetID = "all"


class RequestGetLedgersInfo(TypedDict):
    aclass: NotRequired[str]  # KrakenAssetClass
    asset: NotRequired[str]  # KrakenLedgerAssets
    end: NotRequired[int]
    ofs: NotRequired[int]
    start: NotRequired[int]
    type: NotRequired[str]  # KrakenLedgerEntryType
    without_count: NotRequired[bool]


RequestWithNonce: TypeAlias = dict[str, str]


KrakenLedgerEntryID: TypeAlias = str
KrakenRefID: TypeAlias = str


class KrakenLedgerEntry(TypedDict):
    aclass: KrakenAssetClass
    amount: float
    asset: AssetID
    balance: float
    fee: float
    refid: KrakenRefID
    subtype: str
    time: float
    type: KrakenLedgerEntryType


KrakenLedger: TypeAlias = dict[KrakenLedgerEntryID, KrakenLedgerEntry]


class ResponseLedgerObjs(TypedDict):
    ledger: KrakenLedger
    count: int


class ResponseLedgersInfo(TypedDict):
    result: ResponseLedgerObjs


SignedHttpHeaders = TypedDict(
    "SignedHttpHeaders",
    {
        "API-Sign": str,
    },
)


class KrakenAPI(BalanceProviderApiInterface, PriceOracleApiInterface):
    def __init__(self, config: KrakenConfig, log: Logger) -> None:
        super().__init__(config=config, log=log)

        if not config["private_key"]:
            raise InvalidAPIConfigException("Expected 'private_key'")

        self.__private_key = config["private_key"]

        self.__base_url_api: str = KRAKEN_API_BASE_URL
        self.__base_url_api_public: str = KRAKEN_API_PUBLIC_BASE_URL

        self.__auth_headers_json: HttpHeaders = {}
        self.__auth_headers_json.update(HEADERS_JSON)
        self.__auth_headers_json["API-Key"] = config["api_token"]

        self.__auth_headers_url_encoded: HttpHeaders = {}
        self.__auth_headers_url_encoded.update(HEADERS_URL_ENCODED)
        self.__auth_headers_url_encoded["API-Key"] = config["api_token"]

        res_assets = self.__get_kraken_assets()
        self.__kraken_assets: KrakenAssets = res_assets["result"]

        self.__assets__ = self.__get_assets(res_assets)
        if len(self.__assets__) == 0:
            raise NoSupportedAssetsException()

        self.__asset_pairs__: AssetPairs = self.__get_asset_pairs()
        if len(self.__asset_pairs__) == 0:
            raise NoSupportedAssetsPairsException()

    def __get_kraken_signature(self, urlpath: str, payload: RequestWithNonce) -> str:
        postdata = urllib.parse.urlencode(payload)
        encoded = (payload["nonce"] + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()

        mac = hmac.new(base64.b64decode(self.__private_key), message, hashlib.sha512)
        sigdigest = base64.b64encode(mac.digest())

        return sigdigest.decode()

    def __set_signature_header(
        self, urlpath: str, payload: RequestWithNonce, headers: HttpHeaders
    ) -> SignedHttpHeaders:
        signature = self.__get_kraken_signature(urlpath, payload)
        h = cast(SignedHttpHeaders, headers)
        h["API-Sign"] = signature
        return h

    @staticmethod
    def __set_nonce(payload: Mapping[str, str | int | bool]) -> RequestWithNonce:
        req: RequestWithNonce = {"nonce": str(int(1000 * time.time()))}
        for k, v in payload.items():
            req[str(k)] = str(v)
        return req

    def __get_kraken_assets(self) -> ResponseAssets:
        url = f"{self.__base_url_api_public}/Assets"
        try:
            res_assets = get_json_request(url=url, headers=self.__auth_headers_json)
            return cast(ResponseAssets, res_assets)
        except RequestException as e:
            raise PriceOracleException(e) from e

    def __get_assets(self, res_assets: ResponseAssets) -> Assets:
        assets: Assets = {}

        for kraken_asset_id, asset_info in res_assets["result"].items():
            asset_id = asset_info["altname"]
            if kraken_asset_id in KrakenAssetIDMap:
                asset_id = KrakenAssetIDMap[kraken_asset_id]

            asset_class = asset_info["aclass"]

            if asset_class == KrakenAssetClass.CURRENCY:
                if asset_id in assets:
                    self.__log__.warning(f"Asset '{asset_id}' already indexed")

                asset_name = asset_info["altname"]
                asset_decimals = asset_info["decimals"]

                assets[asset_id] = {
                    "id": asset_id,
                    "name": asset_name,
                    "decimals": asset_decimals,
                    "service_asset_id": kraken_asset_id,
                }
            else:
                self.__log__.debug(f"skipping asset {asset_id} with class {asset_class}")

        return assets

    def __get_asset_pairs(self) -> AssetPairs:
        available_asset_pairs: AssetPairs = {}

        url = f"{self.__base_url_api_public}/AssetPairs"

        try:
            res_asset_pairs = get_json_request(url=url, headers=self.__auth_headers_json)
            res_asset_pairs = cast(ResponseAssetPairs, res_asset_pairs)

            for asset_pair in res_asset_pairs["result"].values():
                base_asset_id = asset_pair["base"]
                quote_asset_id = asset_pair["quote"]

                if base_asset_id in KrakenAssetIDMap:
                    base_asset_id = KrakenAssetIDMap[base_asset_id]
                elif base_asset_id in self.__kraken_assets:
                    base_asset_id = self.__kraken_assets[base_asset_id]["altname"]

                if quote_asset_id in KrakenAssetIDMap:
                    quote_asset_id = KrakenAssetIDMap[quote_asset_id]
                elif quote_asset_id in self.__kraken_assets:
                    quote_asset_id = self.__kraken_assets[quote_asset_id]["altname"]

                base_asset_class = asset_pair["aclass_base"]
                quote_asset_class = asset_pair["aclass_quote"]

                if (
                    base_asset_class == KrakenAssetClass.CURRENCY
                    and quote_asset_class == KrakenAssetClass.CURRENCY
                ):
                    if base_asset_id not in available_asset_pairs:
                        available_asset_pairs[base_asset_id] = set()

                    available_asset_pairs[base_asset_id].add(quote_asset_id)

            return available_asset_pairs
        except RequestException as e:
            raise PriceOracleException(e) from e

    def __wait_requests(self, wait_time_seconds: float):
        self.__log__.warning(
            f"API rate-limit hit. waiting {wait_time_seconds}s until next request..."
        )
        time.sleep(wait_time_seconds)

    def value_at(self, asset_id, quote_asset_id, timestamp_unix_seconds) -> AssetValueAtTime:
        if asset_id not in self.__assets__:
            raise UnsupportedAssetIDException(asset_id=asset_id)

        if quote_asset_id not in self.__asset_pairs__[asset_id]:
            raise UnsupportedQuoteAssetIDException(quote_asset_id=quote_asset_id)

        asset_pair = f"{asset_id}{quote_asset_id}"
        url = f"{self.__base_url_api_public}/Trades"

        asset_value_at_time: AssetValueAtTime | None = None
        offset_timestamp_unix_seconds: int = timestamp_unix_seconds
        wait_time_seconds: float = 0
        while asset_value_at_time is None:
            if (
                timestamp_unix_seconds - offset_timestamp_unix_seconds
            ) >= OFFSET_TIMESTAMP_MAX_SECONDS:
                raise NoValueFoundException(
                    f"No trades found between {offset_timestamp_unix_seconds} -> {timestamp_unix_seconds}"
                )

            params = {
                "pair": asset_pair,
                "since": str(offset_timestamp_unix_seconds),
            }

            try:
                res_trades_json = get_json_request(
                    url=url, params=params, headers=self.__auth_headers_json
                )
                res_trades_json = cast(ResponseTrades, res_trades_json)

                # successful request, so reset wait time
                wait_time_seconds = 0

                pair_key = list(res_trades_json["result"].keys())[0]
                trades_obj = res_trades_json["result"][pair_key]
                if len(trades_obj) == 0:
                    self.__log__.debug(
                        f"No trades found between {offset_timestamp_unix_seconds} -> {timestamp_unix_seconds}"
                    )
                    offset_timestamp_unix_seconds -= OFFSET_TIMESTAMP_SECONDS
                    continue

                # Store the current closest values to timestamp_unix_seconds
                closest_trade_price: float | None = None
                closest_trade_timestamp_seconds: int | None = None

                for trade_list in trades_obj:
                    trade = Trade._make(trade_list)
                    trade_timestamp_seconds = int(float(trade.timestamp))

                    if trade_timestamp_seconds > timestamp_unix_seconds:
                        # Need a value closest to, but less than timestamp_unix_seconds, so stop
                        break

                    if trade_timestamp_seconds < offset_timestamp_unix_seconds:
                        # This really shouldn't happen, but handle it anyway
                        self.__log__.warning(
                            f"Trade is older than the offset timestamp ({trade_timestamp_seconds} < {offset_timestamp_unix_seconds})"
                        )
                        continue

                    if trade.order_type == KrakenOrderType.MARKET:
                        # Use market orders since their trade price reflects the market price
                        closest_trade_price = float(trade.price)
                        closest_trade_timestamp_seconds = trade_timestamp_seconds
                    else:
                        self.__log__.debug(
                            f"ignoring trade of order type '{trade.order_type}' and trade type '{trade.trade_type}'"
                        )
                        continue

                if closest_trade_price and closest_trade_timestamp_seconds:
                    asset_value_at_time = {
                        "asset": self.__assets__[asset_id],
                        "quote_asset": quote_asset_id,
                        "timestamp": closest_trade_timestamp_seconds,
                        "value": closest_trade_price,
                    }

                    self.__log__.debug(
                        f"Using trade value {closest_trade_price} at {closest_trade_timestamp_seconds} as {asset_pair} value."
                    )

                    break
                else:
                    offset_timestamp_unix_seconds -= OFFSET_TIMESTAMP_SECONDS
                    continue

            except TooManyRequestsException as e:
                # Respect server-provided retry delay when available
                if e.retry_after_seconds is not None:
                    self.__wait_requests(e.retry_after_seconds)
                    # After a successful wait on Retry-After, reset incremental backoff
                    wait_time_seconds = 0
                else:
                    wait_time_seconds += WAIT_TIME_INCREMENT_SECONDS
                    self.__wait_requests(wait_time_seconds)
                continue
            except RequestException as e:
                if e.error_messages:
                    if (
                        KrakenResponseError.TOO_MANY_REQUESTS in e.error_messages
                        or KrakenResponseError.RATE_LIMIT_EXCEEDED in e.error_messages
                    ):
                        wait_time_seconds += WAIT_TIME_INCREMENT_SECONDS
                        self.__wait_requests(wait_time_seconds)
                        continue

                raise PriceOracleException(e) from e

        return asset_value_at_time

    def __get_account_ledger_at_offset(
        self,
        assets: list[KrakenAssetID] | KrakenAssetID = KrakenLedgerAssetsAll,
        start_unix_timestamp_seconds: int | None = None,
        end_unix_timestamp_seconds: int | None = None,
        offset: int = 0,
    ) -> ResponseLedgersInfo:
        urlpath = f"{KRAKEN_API_VERSION_PATH}/private/Ledgers"
        url = f"{self.__base_url_api}{urlpath}"

        if isinstance(assets, list):
            assets = ",".join(assets)

        payload: dict[str, str | int | bool] = {
            "asset": str(assets),
            "aclass": str(KrakenAssetClass.CURRENCY),
            "type": str(KrakenLedgerEntryType.ALL),
            "ofs": offset,
        }

        if start_unix_timestamp_seconds:
            payload["start"] = start_unix_timestamp_seconds
        if end_unix_timestamp_seconds:
            payload["end"] = end_unix_timestamp_seconds

        # TODO: Refactor into post_private

        payload_nonce = self.__set_nonce(payload)
        headers = dict(self.__auth_headers_url_encoded)

        signed_headers = self.__set_signature_header(
            urlpath=urlpath, payload=payload_nonce, headers=headers
        )

        try:
            res_json = post_json_request(
                url=url,
                data=urllib.parse.urlencode(payload_nonce).encode(),
                headers=cast(HttpHeaders, signed_headers),
            )

            return cast(ResponseLedgersInfo, res_json)
        except RequestException as e:
            if e.error_messages:
                if KrakenResponseError.INVALID_KEY in e.error_messages:
                    raise InvalidAPIKeyException(e) from e
                elif (
                    KrakenResponseError.TOO_MANY_REQUESTS in e.error_messages
                    or KrakenResponseError.RATE_LIMIT_EXCEEDED in e.error_messages
                ):
                    raise TooManyRequestsException(
                        "too many requests",
                        status_code=e.status_code,
                        result=e.result_json,
                        error_messages=e.error_messages,
                        exception=e,
                    ) from e

            raise BalanceProviderException(e) from e

    # def __asset_id_to_kraken_id(self, asset_id: AssetID) -> KrakenAssetID:
    #     if asset_id not in self.__assets__:
    #         raise UnsupportedAssetIDException(asset_id)

    #     asset = self.__assets__[asset_id]
    #     if "platform_id" not in asset:
    #         raise BalanceOracleException("no platform_id found")

    #     return asset["platform_id"]

    def __kraken_id_to_asset_id(self, kraken_asset_id: KrakenAssetID) -> AssetID:
        if kraken_asset_id not in self.__kraken_assets:
            raise UnsupportedAssetIDException(f"Kraken asset ID '{kraken_asset_id}' not listed")

        alt_name = self.__kraken_assets[kraken_asset_id]["altname"]
        if kraken_asset_id in KrakenAssetIDMap:
            alt_name = KrakenAssetIDMap[kraken_asset_id]
        if alt_name not in self.__assets__:
            raise UnsupportedAssetIDException(f"asset ID {alt_name} not supported")

        return self.__assets__[alt_name]["id"]

    def __get_account_ledger(
        self,
        assets: list[KrakenAssetID] | KrakenAssetID = KrakenLedgerAssetsAll,
        start_unix_timestamp_seconds: int | None = None,
        end_unix_timestamp_seconds: int | None = None,
    ) -> KrakenLedger:
        ledger_entries: KrakenLedger = {}
        ledger_entry_count: int | None = None
        page_offset = 0
        wait_time_seconds = 0

        while ledger_entry_count is None or len(ledger_entries) < ledger_entry_count:
            try:
                ledger_info = self.__get_account_ledger_at_offset(
                    assets=assets,
                    start_unix_timestamp_seconds=start_unix_timestamp_seconds,
                    end_unix_timestamp_seconds=end_unix_timestamp_seconds,
                    offset=page_offset,
                )
            except TooManyRequestsException:
                wait_time_seconds += WAIT_TIME_INCREMENT_SECONDS
                self.__wait_requests(wait_time_seconds)
                continue

            wait_time_seconds = 0

            for ledger_entry_id, ledger_entry in ledger_info["result"]["ledger"].items():
                if ledger_entry_id not in ledger_entries:
                    ledger_entries[ledger_entry_id] = ledger_entry
                else:
                    self.__log__.warning(f"ledger entry '{ledger_entry_id}' already processed")

            page_ledger_count = ledger_info["result"]["count"]
            if ledger_entry_count != page_ledger_count:
                if ledger_entry_count:
                    self.__log__.warning(
                        f"Ledger entry count changed from {ledger_entry_count} to {page_ledger_count}"
                    )

                ledger_entry_count = page_ledger_count

            self.__log__.debug(
                f"Got {len(ledger_entries)} out of {ledger_entry_count} ledger entries"
            )

            page_offset = len(ledger_entries)

        if len(ledger_entries) != ledger_entry_count:
            raise BalanceProviderException()

        return ledger_entries

    @staticmethod
    def __get_kraken_id_suffix(kraken_asset_id: KrakenAssetID) -> KrakenLedgerAssetSuffix | None:
        suffix_offset = 3
        suffix_set = set(iter(KrakenLedgerAssetSuffix))

        while suffix_offset < len(kraken_asset_id):
            suffix = kraken_asset_id[suffix_offset:]
            if suffix in suffix_set:
                return cast(KrakenLedgerAssetSuffix, suffix)

            suffix_offset += 1

        return None

    def __get_balances_at_time(
        self, ledger_entries: KrakenLedger, timestamp_unix_seconds: int
    ) -> AssetBalancesAtTime:
        asset_balances_at_time: AssetBalancesAtTime = {}

        delisted_kraken_ids = []

        for ledger_entry in ledger_entries.values():
            entry_timestamp = int(float(ledger_entry["time"]))
            if entry_timestamp > timestamp_unix_seconds:
                continue

            entry_kraken_asset_id = ledger_entry["asset"]
            entry_kraken_asset_id_stripped = entry_kraken_asset_id
            kraken_asset_id_suffix = self.__get_kraken_id_suffix(entry_kraken_asset_id)
            if kraken_asset_id_suffix:
                # strip the suffix
                entry_kraken_asset_id_stripped = entry_kraken_asset_id[
                    : -len(kraken_asset_id_suffix)
                ]

            try:
                asset_id = self.__kraken_id_to_asset_id(entry_kraken_asset_id_stripped)
            except UnsupportedAssetIDException:
                if entry_kraken_asset_id_stripped in self.__assets__:
                    asset_id = entry_kraken_asset_id_stripped
                elif entry_kraken_asset_id_stripped not in delisted_kraken_ids:
                    self.__log__.warning(
                        f"Asset {entry_kraken_asset_id_stripped} is not listed as supported. It is probably de-listed. skipping."
                    )
                    delisted_kraken_ids.append(entry_kraken_asset_id_stripped)
                    continue
                else:
                    continue

            # Resulting balance after entry is applied
            entry_balance = float(ledger_entry["balance"])

            asset: Asset = {
                "id": asset_id,
                "name": asset_id,
                "service_asset_id": entry_kraken_asset_id,
            }

            if asset_id not in asset_balances_at_time:
                asset_balances_at_time[asset_id] = {}

            if entry_kraken_asset_id not in asset_balances_at_time[asset_id]:
                asset_balance_at_time: AssetBalanceAtTime = {
                    "asset": asset,
                    "quantity": entry_balance,
                    "timestamp": entry_timestamp,
                }
                asset_balances_at_time[asset_id][entry_kraken_asset_id] = asset_balance_at_time
            else:
                current_balance_at_time = asset_balances_at_time[asset_id][entry_kraken_asset_id]
                if entry_timestamp < current_balance_at_time["timestamp"]:
                    # existing entry is newer
                    continue

                current_balance_at_time["quantity"] = entry_balance
                current_balance_at_time["timestamp"] = entry_timestamp
                asset_balances_at_time[asset_id][entry_kraken_asset_id] = current_balance_at_time

        return asset_balances_at_time

    def all_balances_at(self, timestamp_unix_seconds: int) -> AssetBalancesAtTime:
        ledger_entries = self.__get_account_ledger(
            end_unix_timestamp_seconds=timestamp_unix_seconds + 1
        )

        return self.__get_balances_at_time(ledger_entries, timestamp_unix_seconds)
