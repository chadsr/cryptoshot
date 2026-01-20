from enum import StrEnum
from logging import Logger
from typing import TypedDict, NotRequired, cast, override

from ...services.apis.requestutils import HEADERS_JSON, get_json_request
from ...services.apis.interfaces import BalanceOracleApiInterface
from ...services.apis.exceptions import RequestException
from ...services.exceptions import (
    BalanceOracleException,
    NoBalancesFoundException,
    UnsupportedAddressTypeException,
)
from ...services.types import (
    AccountAddress,
    AddressType,
    ApiConfig,
    Asset,
    AssetBalancesAtTime,
    HttpHeaders,
)


class AvaxNetworkType(StrEnum):
    MAINNET = "mainnet"


class AvaxChainType(StrEnum):
    P_CHAIN = "p-chain"
    X_CHAIN = "x-chain"


AVAX_NETWORK_DATA_API_BASE_URL = "https://data-api.avax.network/v1"


# TypedDicts based on balances.ts
class ChainInfo(TypedDict):
    chainName: str
    network: str


class ResponseAssetAmount(TypedDict):
    assetId: str
    name: str
    symbol: str
    denomination: int
    type: str
    amount: str
    utxoCount: int
    sharedWithChainId: NotRequired[str]
    status: NotRequired[str]


class PChainBalances(TypedDict):
    unlockedUnstaked: list[ResponseAssetAmount]
    unlockedStaked: list[ResponseAssetAmount]
    lockedPlatform: list[ResponseAssetAmount]
    lockedStakeable: list[ResponseAssetAmount]
    lockedStaked: list[ResponseAssetAmount]
    pendingStaked: list[ResponseAssetAmount]
    atomicMemoryUnlocked: list[ResponseAssetAmount]
    atomicMemoryLocked: list[ResponseAssetAmount]


class XChainBalances(TypedDict):
    locked: list[ResponseAssetAmount]
    unlocked: list[ResponseAssetAmount]
    atomicMemoryUnlocked: list[ResponseAssetAmount]
    atomicMemoryLocked: list[ResponseAssetAmount]


class ResponsePChainBalances(TypedDict):
    balances: PChainBalances
    chainInfo: ChainInfo


class ResponseXChainBalances(TypedDict):
    balances: XChainBalances
    chainInfo: ChainInfo


class AvaxNetworkAPI(BalanceOracleApiInterface):
    def __init__(
        self,
        config: ApiConfig,
        log: Logger,
    ) -> None:
        super().__init__(
            config=config,
            log=log,
        )

        self.__base_url_api: str = (
            f"{AVAX_NETWORK_DATA_API_BASE_URL}/networks/{AvaxNetworkType.MAINNET}/blockchains"
        )

        self.__auth_headers: HttpHeaders = {}
        self.__auth_headers.update(HEADERS_JSON)
        self.__auth_headers["x-glacier-api-key"] = config["api_token"]

        self.__supported_address_types = set[AddressType]([AddressType.AVAX])

    @override
    def supported_address_types(self) -> set[AddressType]:
        return self.__supported_address_types

    def __list_p_chain_balances(
        self, address: str, timestamp_unix_seconds: int
    ) -> ResponsePChainBalances:
        url = f"{self.__base_url_api}/{AvaxChainType.P_CHAIN}/balances"
        params = {
            "blockTimestamp": timestamp_unix_seconds,
            "addresses": address,
        }
        try:
            res_json = get_json_request(url=url, params=params, headers=self.__auth_headers)
            return cast(ResponsePChainBalances, res_json)
        except RequestException as e:
            raise BalanceOracleException(e) from e

    def __list_x_chain_balances(
        self, address: str, timestamp_unix_seconds: int
    ) -> ResponseXChainBalances:
        url = f"{self.__base_url_api}/{AvaxChainType.X_CHAIN}/balances"
        params = {
            "blockTimestamp": timestamp_unix_seconds,
            "addresses": address,
        }
        try:
            res_json = get_json_request(url=url, params=params, headers=self.__auth_headers)
            return cast(ResponseXChainBalances, res_json)
        except RequestException as e:
            raise BalanceOracleException(e) from e

    @staticmethod
    def __sum_amounts(
        entries: list[ResponseAssetAmount],
    ) -> dict[str, tuple[ResponseAssetAmount, int]]:
        total_by_asset: dict[str, tuple[ResponseAssetAmount, int]] = {}
        for entry in entries:
            asset_key = entry["assetId"]
            if asset_key not in total_by_asset:
                total_by_asset[asset_key] = (entry, 0)
            prev_entry, prev_total = total_by_asset[asset_key]
            try:
                amt = int(entry["amount"])  # amounts are returned as strings
            except ValueError:
                amt = 0
            total_by_asset[asset_key] = (prev_entry, prev_total + amt)
        return total_by_asset

    @staticmethod
    def __aggregate_p_chain(
        bal: PChainBalances,
    ) -> dict[str, tuple[ResponseAssetAmount, int]]:
        combined: list[ResponseAssetAmount] = []
        combined.extend(bal.get("unlockedUnstaked", []))
        combined.extend(bal.get("unlockedStaked", []))
        combined.extend(bal.get("lockedPlatform", []))
        combined.extend(bal.get("lockedStakeable", []))
        combined.extend(bal.get("lockedStaked", []))
        combined.extend(bal.get("pendingStaked", []))
        combined.extend(bal.get("atomicMemoryUnlocked", []))
        combined.extend(bal.get("atomicMemoryLocked", []))
        return AvaxNetworkAPI.__sum_amounts(combined)

    @staticmethod
    def __aggregate_x_chain(
        bal: XChainBalances,
    ) -> dict[str, tuple[ResponseAssetAmount, int]]:
        combined: list[ResponseAssetAmount] = []
        combined.extend(bal.get("locked", []))
        combined.extend(bal.get("unlocked", []))
        combined.extend(bal.get("atomicMemoryUnlocked", []))
        combined.extend(bal.get("atomicMemoryLocked", []))
        return AvaxNetworkAPI.__sum_amounts(combined)

    @override
    def all_balances_at(
        self, account: AccountAddress, timestamp_unix_seconds: int
    ) -> AssetBalancesAtTime:
        # Checks all AvaxChainType chains for balances and returns the overall total
        # balance for the address across P and X chains. C-Chain is ignored.
        address = account["address"]
        address_type = account["type"]
        if address_type not in self.__supported_address_types:
            raise UnsupportedAddressTypeException(address_type)

        # Fetch balances for P-Chain and X-Chain
        p_chain_res = self.__list_p_chain_balances(address, timestamp_unix_seconds)
        x_chain_res = self.__list_x_chain_balances(address, timestamp_unix_seconds)

        # Aggregate totals per asset (by symbol) for each chain separately
        p_totals = (
            self.__aggregate_p_chain(p_chain_res["balances"]) if "balances" in p_chain_res else {}
        )
        x_totals = (
            self.__aggregate_x_chain(x_chain_res["balances"]) if "balances" in x_chain_res else {}
        )

        balances_at_time: AssetBalancesAtTime = {}

        def add_chain_totals(
            source: dict[str, tuple[ResponseAssetAmount, int]], chain_label: str
        ) -> None:
            for _, (entry_sample, total_amount_smallest) in source.items():
                if total_amount_smallest == 0:
                    continue

                denomination = entry_sample.get("denomination", 0)
                quantity = (
                    total_amount_smallest / (10**denomination)
                    if denomination
                    else float(total_amount_smallest)
                )

                asset_name_with_chain = f"{entry_sample['name']} ({chain_label})"

                asset: Asset = {
                    "id": entry_sample["symbol"],
                    "name": asset_name_with_chain,
                    "decimals": denomination,
                    "service_asset_id": entry_sample["assetId"],
                }

                if asset["id"] not in balances_at_time:
                    balances_at_time[asset["id"]] = {}

                balances_at_time[asset["id"]][address] = {
                    "asset": asset,
                    "quantity": quantity,
                    "timestamp": timestamp_unix_seconds,
                }

        add_chain_totals(source=p_totals, chain_label=AvaxChainType.P_CHAIN.title())
        add_chain_totals(source=x_totals, chain_label=AvaxChainType.X_CHAIN.title())

        if len(balances_at_time) == 0:
            raise NoBalancesFoundException()

        return balances_at_time
