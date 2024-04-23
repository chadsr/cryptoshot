from enum import IntEnum
from logging import Logger
from datetime import datetime
from typing import TypeAlias, TypedDict
from zoneinfo import ZoneInfo

from ..exceptions import (
    NoSupportedAssetsException,
    PriceOracleException,
    RequestException,
    UnsupportedAssetIDException,
)
from ..types import (
    Assets,
    AssetValueAtTime,
    HttpHeaders,
    ServiceConfig,
)

from .interfaces import PriceOracleInterface
from .requests import JSON_HEADERS, get_json_request

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


class CoinAPI(PriceOracleInterface):
    def __init__(self, config: ServiceConfig, log: Logger) -> None:
        super().__init__(config=config, log=log)

        self.base_url_api: str = COINAPI_BASE_URL

        self.auth_headers: HttpHeaders = {}
        self.auth_headers.update(JSON_HEADERS)
        self.auth_headers["X-CoinAPI-Key"] = self.config["api_token"]

        self.assets = self._get_assets()

    def _get_assets(self) -> Assets:
        assets: Assets = {}

        try:
            url = f"{self.base_url_api}/assets"
            res_assets: ResponseAssets = get_json_request(url=url, headers=self.auth_headers)

            for asset in res_assets:
                if asset["type_is_crypto"] == TypeIsCrypto.TRUE:
                    asset_id = asset["asset_id"]
                    asset_name = asset["name"]
                    assets[asset_id] = {"id": asset_id, "name": asset_name}

            return assets
        except RequestException as e:
            raise PriceOracleException(e)

    def supported_assets(self) -> Assets:
        if self.assets is None:
            raise NoSupportedAssetsException()

        return self.assets

    def value_at(self, asset_id, quote_asset_id, timestamp_unix_seconds) -> AssetValueAtTime:
        if self.assets is None:
            raise NoSupportedAssetsException()

        if asset_id not in self.assets:
            raise UnsupportedAssetIDException()

        url = f"{self.base_url_api}/exchangerate/{asset_id}/{quote_asset_id}"

        timestamp_str = datetime.fromtimestamp(timestamp_unix_seconds, ZoneInfo("UTC")).isoformat()
        params = {"time": timestamp_str}

        try:
            res_exchangerate: ResponseExchangeRate = get_json_request(
                url=url, params=params, headers=self.auth_headers
            )

            asset_value = res_exchangerate["rate"]
            asset_value_timestamp_str = datetime.fromisoformat(res_exchangerate["time"])

            asset_value_timestamp = int(asset_value_timestamp_str.timestamp())

            asset_value_at_time: AssetValueAtTime = {
                "asset": {"id": asset_id, "name": self.assets[asset_id]["name"]},
                "value": asset_value,
                "quote_asset": quote_asset_id,
                "timestamp": asset_value_timestamp,
            }

            return asset_value_at_time

        except RequestException as e:
            raise PriceOracleException(e)
