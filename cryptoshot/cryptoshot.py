from logging import Logger
from zoneinfo import ZoneInfo
from datetime import datetime

from .exceptions import (
    InvalidPriceOracleException,
    InvalidServiceConfigException,
    NoValueFoundException,
    PriceOracleException,
    UnsupportedBaseCurrencyException,
)
from .types import AssetID, Config, Prices
from .apis import APIS

from .apis.interfaces import PriceOracleInterface


class Cryptoshot:
    def __init__(self, config: Config, logger: Logger, timestamp_unix_seconds: int) -> None:
        self.log: Logger = logger
        self.config: Config = config
        self.timestamp_unix_seconds: int = timestamp_unix_seconds

        timestamp_iso = datetime.fromtimestamp(
            timestamp_unix_seconds, tz=ZoneInfo("UTC")
        ).isoformat()
        self.log.info(f"Checking at {timestamp_iso} (UTC)")

    def prices(self) -> Prices:
        prices: Prices = {}
        price_oracles: list[PriceOracleInterface] = []
        quote_asset_id = self.config["price_oracle"]["quote_asset"]
        asset_ids_include = set(self.config["assets"]["include"])
        asset_ids_exclude = set(self.config["assets"]["exclude"])

        for service_id in self.config["price_oracle"]["priority"]:
            if service_id in APIS:
                if not self.config["services"][service_id]:
                    raise InvalidServiceConfigException(
                        f"Expected services config entry for '{service_id}'"
                    )

                price_oracle_class = APIS[service_id]
                price_oracle = price_oracle_class(
                    config=self.config["services"][service_id], log=self.log
                )

                if not isinstance(price_oracle, PriceOracleInterface):
                    raise InvalidPriceOracleException(
                        f"Service {service_id} is not a valid price oracle service"
                    )

                price_oracles.append(price_oracle)
            else:
                self.log.warn(f"Unsupported price oracle service: {service_id}")

        asset_ids: list[AssetID] = []
        for asset_id in asset_ids_include:
            if asset_id in asset_ids_exclude:
                self.log.warn(f"Asset '{asset_id} is both included and excluded!")
                continue

            asset_ids.append(asset_id)

        for asset_id in asset_ids:
            for price_oracle in price_oracles:
                service_id = price_oracle.service_id()
                supported_assets = price_oracle.supported_assets()
                price_oracle_asset_id = asset_id

                if price_oracle_asset_id not in supported_assets:
                    found_supported_asset_id = False
                    if price_oracle_asset_id in self.config["assets"]["group"]:
                        grouped_asset_ids = self.config["assets"]["group"][price_oracle_asset_id]
                        for grouped_asset_id in grouped_asset_ids:
                            if grouped_asset_id in supported_assets:
                                price_oracle_asset_id = grouped_asset_id
                                self.log.info(
                                    f"Using supported asset ID '{price_oracle_asset_id}' from configured asset group of'{asset_id}' for price oracle '{service_id}'"
                                )
                                found_supported_asset_id = True
                                break

                    if not found_supported_asset_id:
                        self.log.debug(
                            f"skipping unsupported asset ID {price_oracle_asset_id} for price oracle {service_id}"
                        )
                        continue

                try:
                    asset_value = price_oracle.value_at(
                        asset_id=price_oracle_asset_id,
                        quote_asset_id=quote_asset_id,
                        timestamp_unix_seconds=self.timestamp_unix_seconds,
                    )

                    if asset_id not in prices:
                        prices[asset_id] = {}

                    prices[asset_id][service_id] = asset_value
                except NoValueFoundException:
                    self.log.warn(
                        f"No usable value found for asset pair {asset_id}/{quote_asset_id} for service {service_id}"
                    )
                except UnsupportedBaseCurrencyException:
                    self.log.warn(
                        f"Unsupported asset pair {price_oracle_asset_id}/{quote_asset_id} for service '{service_id}'"
                    )
                except PriceOracleException as e:
                    self.log.exception(e)

        return prices

    def balances(self) -> dict:
        return {}
