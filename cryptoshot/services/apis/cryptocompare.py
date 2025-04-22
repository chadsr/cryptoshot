# from logging import Logger
# from datetime import datetime
# from typing import TypeAlias, TypedDict
# from zoneinfo import ZoneInfo

# from ..exceptions import (
#     NoSupportedAssetsException,
#     NoSupportedAssetsPairsException,
#     PriceOracleException,
#     RequestException,
#     UnsupportedAssetIDException,
# )
# from ..types import (
#     Assets,
#     AssetPairs,
#     AssetValueAtTime,
#     HttpHeaders,
#     ServiceConfig,
# )

# from .interfaces import PriceOracleInterface
# from .requests import JSON_HEADERS, get_json_request

# CRYPTOCOMPARE_BASE_URL = "https://min-api.cryptocompare.com/data/v4"


# class ResponseCoin(TypedDict):
#     asset_id: str
#     name: str


# # https://min-api.cryptocompare.com/documentation?key=Other&cat=allCoinsWithContentEndpoint
# ResponseCoins: TypeAlias = list[ResponseCoin]


# class ResponseOHLCV(TypedDict):
#     # https://min-api.cryptocompare.com/documentation?key=Historical&cat=dataHistohour
#     pass


# class CryptoCompareAPI(PriceOracleInterface):
#     def __init__(self, config: ServiceConfig, log: Logger) -> None:
#         super().__init__(config=config, log=log)

#         self.__base_url_api: str = CRYPTOCOMPARE_BASE_URL

#         self.__auth_headers: HttpHeaders = {}
#         self.__auth_headers.update(JSON_HEADERS)
#         self.__auth_headers[""] = self.__config["api_token"]

#         self.__assets__ = self._get_assets()
#         if len(self.__assets__) == 0:
#             raise NoSupportedAssetsException()

#         self.__asset_pairs: AssetPairs = self._get_asset_pairs()
#         if len(self.__asset_pairs) == 0:
#             raise NoSupportedAssetsPairsException()

#     def _get_assets(self) -> Assets:
#         assets: Assets = {}

#         url = f"{self.__base_url_api}/Assets"

#         try:
#             res_assets: ResponseCoins = get_json_request(url=url, headers=self.__auth_headers)

#             for asset_info in res_assets["result"].values():
#                 asset_id = asset_info["altname"]
#                 asset_class = asset_info["aclass"]

#                 if asset_class == KrakenAssetClass.CURRENCY.value:
#                     if asset_id in assets:
#                         self.__log__.warning(f"Asset '{asset_id}' already indexed")

#                     asset_name = asset_info["altname"]
#                     asset_decimals = asset_info["decimals"]

#                     assets[asset_id] = {
#                         "id": asset_id,
#                         "name": asset_name,
#                         "decimals": asset_decimals,
#                     }
#                 else:
#                     self.__log__.debug(f"skipping asset {asset_id} with class {asset_class}")

#             return assets
#         except RequestException as e:
#             raise PriceOracleException(e)

#     def _get_asset_pairs(self) -> AssetPairs:
#         available_asset_pairs: AssetPairs = {}

#         url = f"{self.__base_url_api_public}/AssetPairs"

#         try:
#             res_asset_pairs: ResponseAssetPairs = get_json_request(
#                 url=url, headers=self.__auth_headers
#             )

#             for asset_pair in res_asset_pairs["result"].values():
#                 base_asset_id, quote_asset_id = asset_pair["wsname"].split("/")
#                 base_asset_class = asset_pair["aclass_base"]
#                 quote_asset_class = asset_pair["aclass_quote"]

#                 if (
#                     base_asset_class == KrakenAssetClass.CURRENCY.value
#                     and quote_asset_class == KrakenAssetClass.CURRENCY.value
#                 ):
#                     if base_asset_id not in available_asset_pairs:
#                         available_asset_pairs[base_asset_id] = set()

#                     available_asset_pairs[base_asset_id].add(quote_asset_id)

#                     # some base assets are not listed on the /Assets endpoint so populate them
#                     if self.__assets__ and base_asset_id not in self.__assets__:
#                         self.__assets__[base_asset_id] = {"id": base_asset_id, "name": base_asset_id}

#             return available_asset_pairs
#         except RequestException as e:
#             raise PriceOracleException(e)

#     def supported_assets(self) -> Assets:
#         return self.__assets__

#     def supported_asset_pairs(self) -> AssetPairs:
#         return self.__asset_pairs

#     def value_at(self, asset_id, quote_asset_id, timestamp_unix_seconds) -> AssetValueAtTime:
#         if asset_id not in self.__assets__:
#             raise UnsupportedAssetIDException()

#         url = f"{self.__base_url_api}/exchangerate/{asset_id}/{quote_asset_id}"

#         timestamp_str = datetime.fromtimestamp(timestamp_unix_seconds, ZoneInfo("UTC")).isoformat()
#         params = {"time": timestamp_str}

#         try:
#             res_exchangerate: ResponseExchangeRate = get_json_request(
#                 url=url, params=params, headers=self.__auth_headers
#             )

#             asset_value = res_exchangerate["rate"]
#             asset_value_timestamp_str = datetime.fromisoformat(res_exchangerate["time"])

#             asset_value_timestamp = int(asset_value_timestamp_str.timestamp())

#             asset_value_at_time: AssetValueAtTime = {
#                 "asset": {"id": asset_id, "name": self.__assets__[asset_id]["name"]},
#                 "value": asset_value,
#                 "quote_asset": quote_asset_id,
#                 "timestamp": asset_value_timestamp,
#             }

#             return asset_value_at_time

#         except RequestException as e:
#             raise PriceOracleException(e)
