from logging import Logger
from zoneinfo import ZoneInfo
from datetime import datetime

from cryptoshot.services.apis.exceptions import ApiRateLimitException

from .services import SERVICES
from .services.types import (
    AssetBalancesAtTime,
    AssetID,
    ServiceName,
)
from .services.interfaces import (
    ServiceInterface,
    PriceOracleInterface,
    BalanceOracleInterface,
    BalanceProviderInterface,
)
from .services.exceptions import (
    BalanceOracleException,
    InvalidServiceConfigException,
    NoBalancesFoundException,
    NoValueFoundException,
    PriceOracleException,
    UnsupportedAssetIDException,
    UnsupportedQuoteAssetIDException,
)

from .exceptions import (
    InvalidConfigException,
    InvalidPriceOracleException,
)
from .types import Config, Prices, Balances, ServicesConfig

REQUIRED_SERVICE_CONFIG_FIELDS = ["name", "type"]


class Cryptoshot:
    def __init__(self, config: Config, logger: Logger, timestamp_unix_seconds: int) -> None:
        self.__log__: Logger = logger
        self.__config: Config = config
        self.__timestamp_unix_seconds: int = timestamp_unix_seconds

        timestamp_iso = datetime.fromtimestamp(
            timestamp_unix_seconds, tz=ZoneInfo("UTC")
        ).isoformat()
        self.__log__.info(f"Checking at {timestamp_iso} (UTC)")

        self.__asset_ids_include = set(self.__config["assets"]["include"])
        self.__asset_ids_exclude = set(self.__config["assets"]["exclude"])

        self.__services: dict[ServiceName, ServiceInterface] = {}
        self.__init_services()

    def __init_services(self):
        if "services" not in self.__config:
            raise InvalidConfigException

        services_config: ServicesConfig = self.__config["services"]
        for service_config in services_config:
            for field_name in REQUIRED_SERVICE_CONFIG_FIELDS:
                if field_name not in service_config:
                    raise InvalidServiceConfigException(
                        f"field '{field_name}' missing from service configuration"
                    )
            service_name = service_config["name"]
            service_type = service_config["type"]

            if service_type not in SERVICES:
                self.__log__.warning(
                    f"service name '{service_name}' of type '{service_type}' is not a supported type'"
                )
                continue

            if service_name in self.__services:
                self.__log__.warning(
                    f"service name '{service_name}' of type '{service_type}' already initialised. Is the service name duplicated in the config?"
                )
                continue

            service_class = SERVICES[service_type]

            try:
                service = service_class(config=service_config, log=self.__log__)
                self.__services[service_name] = service
            except ApiRateLimitException:
                self.__log__.warning(f"service '{service_name}' is rate-limited. skipping.")
                continue

    def __add_balances_at_time(
        self, service_name: ServiceName, balances_at_time: AssetBalancesAtTime, balances: Balances
    ) -> Balances:
        for asset_id, balance_at_time_dict in balances_at_time.items():
            if asset_id in self.__asset_ids_exclude:
                self.__log__.info(f"skipping balance output for {asset_id} (exclude list)")
                continue

            for account_id, balance_at_time in balance_at_time_dict.items():
                if balance_at_time["quantity"] == 0:
                    continue

                # add this asset ID to the include list for the price oracles to acquire data on
                self.__asset_ids_include.add(asset_id)

                if asset_id not in balances:
                    balances[asset_id] = {}
                if service_name not in balances[asset_id]:
                    balances[asset_id][service_name] = {}
                if account_id in balances[asset_id][service_name]:
                    self.__log__.error(
                        f"got duplicate balance entry for asset ID {asset_id} on service {service_name} with account ID {account_id}"
                    )

                balances[asset_id][service_name][account_id] = balance_at_time

        return balances

    def balances(self) -> Balances:
        balances: Balances = {}

        for service_name, service in self.__services.items():
            if isinstance(service, BalanceOracleInterface):
                for account in self.__config["accounts"]:
                    address_type = account["type"]

                    if address_type not in service.supported_address_types():
                        continue

                    try:
                        balances_at_time = service.all_balances_at(
                            account=account,
                            timestamp_unix_seconds=self.__timestamp_unix_seconds,
                        )

                        balances = self.__add_balances_at_time(
                            service_name, balances_at_time, balances
                        )
                    except NoBalancesFoundException as e:
                        self.__log__.warning(
                            f"no balances found with service '{service_name}' for address {account['address']}: {e}"
                        )
                        continue
                    except BalanceOracleException as e:
                        self.__log__.error(
                            f"could not fetch balances from service '{service_name}' for address {account['address']}: {e}"
                        )
                        continue

            elif isinstance(service, BalanceProviderInterface):
                balances_at_time = service.all_balances_at(
                    timestamp_unix_seconds=self.__timestamp_unix_seconds
                )

                balances = self.__add_balances_at_time(service_name, balances_at_time, balances)
            else:
                continue

        return balances

    def prices(self) -> Prices:
        prices: Prices = {}
        quote_asset_id = self.__config["price_oracle"]["quote_asset"]

        price_oracles_prioritized: set[ServiceName] = set()
        for service_name in self.__config["price_oracle"]["priority"]:
            if service_name not in self.__services:
                self.__log__.error(
                    f"service '{service_name} is not available. Is the config entry missing?"
                )
                continue

            if not isinstance(self.__services[service_name], PriceOracleInterface):
                self.__log__.error(
                    f"service '{service_name}' is not a valid price oracle! skipping."
                )
                continue

            price_oracles_prioritized.add(service_name)

        asset_ids: list[AssetID] = []
        for asset_id in self.__asset_ids_include:
            if asset_id in self.__asset_ids_exclude:
                self.__log__.warning(f"Asset '{asset_id} is both included and excluded!")
                continue

            asset_ids.append(asset_id)

        for asset_id in asset_ids:
            if asset_id == quote_asset_id:
                continue

            for price_oracle_name in price_oracles_prioritized:
                price_oracle = self.__services[price_oracle_name]
                if not isinstance(price_oracle, PriceOracleInterface):
                    raise InvalidPriceOracleException(
                        f"Service {price_oracle} is not a valid price oracle service"
                    )

                price_oracle_asset_id = asset_id
                if not price_oracle.asset_supported(price_oracle_asset_id):
                    found_supported_asset_id = False
                    if price_oracle_asset_id in self.__config["assets"]["group"]:
                        grouped_asset_ids = self.__config["assets"]["group"][price_oracle_asset_id]
                        for grouped_asset_id in grouped_asset_ids:
                            if price_oracle.asset_supported(grouped_asset_id):
                                price_oracle_asset_id = grouped_asset_id
                                self.__log__.info(
                                    f"Using supported asset ID '{price_oracle_asset_id}' from configured asset group of'{asset_id}' for price oracle '{price_oracle_name}'"
                                )
                                found_supported_asset_id = True
                                break

                    if not found_supported_asset_id:
                        self.__log__.debug(
                            f"skipping unsupported asset ID {price_oracle_asset_id} for price oracle {price_oracle_name}"
                        )
                        continue

                try:
                    asset_value = price_oracle.value_at(
                        asset_id=price_oracle_asset_id,
                        quote_asset_id=quote_asset_id,
                        timestamp_unix_seconds=self.__timestamp_unix_seconds,
                    )

                    if asset_id not in prices:
                        prices[asset_id] = {}

                    prices[asset_id][price_oracle_name] = asset_value
                except NoValueFoundException as e:
                    self.__log__.warning(
                        f"No usable value found for asset pair {asset_id}/{quote_asset_id} for service {price_oracle_name}: {e}"
                    )
                    continue
                except UnsupportedAssetIDException:
                    self.__log__.warning(
                        f"Unsupported asset {price_oracle_asset_id} for service '{price_oracle_name}'"
                    )
                    continue
                except UnsupportedQuoteAssetIDException:
                    self.__log__.warning(
                        f"Unsupported asset pair {price_oracle_asset_id}/{quote_asset_id} for service '{price_oracle_name}'"
                    )
                    continue
                except ApiRateLimitException:
                    self.__log__.error(
                        f"price oracle {price_oracle_name} is rate-limited. skipping."
                    )
                    continue
                except PriceOracleException as e:
                    self.__log__.exception(e)
                    continue

        return prices
