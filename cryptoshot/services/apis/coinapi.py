from enum import IntEnum
from logging import Logger
from datetime import datetime
from typing import TypeAlias, TypedDict, cast
from zoneinfo import ZoneInfo

from ...services.exceptions import (
    NoSupportedAssetsException,
    NoValueFoundException,
    PriceOracleException,
    UnsupportedAssetIDException,
)
from ...services.types import (
    ApiConfig,
    Assets,
    AssetValueAtTime,
    HttpHeaders,
)

from .interfaces import PriceOracleApiInterface
from .exceptions import ApiRateLimitException, RequestException, TooManyRequestsException
from .requests import HEADERS_JSON, get_json_request

COINAPI_BASE_URL = "https://rest.coinapi.io/v1"


class TypeIsCrypto(IntEnum):
    FALSE = 0
    TRUE = 1


class ResponseAsset(TypedDict):
    asset_id: str
    name: str
    type_is_crypto: TypeIsCrypto


ResponseAssets: TypeAlias = list[ResponseAsset]


class ResponseExchangeRate(TypedDict):
    time: str
    asset_id_base: str
    asset_id_quote: str
    rate: float


class CoinAPI(PriceOracleApiInterface):
    def __init__(self, config: ApiConfig, log: Logger) -> None:
        super().__init__(config=config, log=log)
        self.__base_url_api: str = COINAPI_BASE_URL

        self.__auth_headers: HttpHeaders = {}
        self.__auth_headers.update(HEADERS_JSON)
        self.__auth_headers["X-CoinAPI-Key"] = config["api_token"]

        self.__assets__ = self._get_assets()
        if len(self.__assets__) == 0:
            raise NoSupportedAssetsException()

    def _get_assets(self) -> Assets:
        assets: Assets = {}

        try:
            url = f"{self.__base_url_api}/assets"
            res_assets = get_json_request(url=url, headers=self.__auth_headers)
            res_assets = cast(ResponseAssets, res_assets)

            for asset in res_assets:
                if asset["type_is_crypto"] == TypeIsCrypto.TRUE:
                    asset_id = asset["asset_id"]
                    asset_name = asset_id
                    if "name" in asset:
                        asset_name = asset["name"]

                    assets[asset_id] = {
                        "id": asset_id,
                        "name": asset_name,
                        "service_asset_id": asset_id,
                    }

            return assets
        except TooManyRequestsException as e:
            raise ApiRateLimitException(e)
        except RequestException as e:
            raise PriceOracleException(e)

    def value_at(self, asset_id, quote_asset_id, timestamp_unix_seconds) -> AssetValueAtTime:
        if asset_id not in self.__assets__:
            raise UnsupportedAssetIDException(asset_id=asset_id)

        url = f"{self.__base_url_api}/exchangerate/{asset_id}/{quote_asset_id}"

        timestamp_str = datetime.fromtimestamp(timestamp_unix_seconds, ZoneInfo("UTC")).isoformat()
        params = {"time": timestamp_str}

        try:
            res_exchangerate = get_json_request(url=url, params=params, headers=self.__auth_headers)
            res_exchangerate = cast(ResponseExchangeRate, res_exchangerate)

            asset_value = res_exchangerate["rate"]
            asset_value_timestamp_str = datetime.fromisoformat(res_exchangerate["time"])

            asset_value_timestamp = int(asset_value_timestamp_str.timestamp())

            asset_value_at_time: AssetValueAtTime = {
                "asset": {"id": asset_id, "name": self.__assets__[asset_id]["name"]},
                "value": asset_value,
                "quote_asset": quote_asset_id,
                "timestamp": asset_value_timestamp,
            }

            return asset_value_at_time

        except RequestException as e:
            if e.status_code == 550:
                msg = ""
                if e.error_messages:
                    msg = e.error_messages[0]
                raise NoValueFoundException(msg)

            raise PriceOracleException(e)
