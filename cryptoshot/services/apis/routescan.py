from enum import StrEnum
from logging import Logger
from typing import NotRequired, TypedDict, cast

from ...services.constants import EVM_BASE_ASSET_DECIMALS
from ...services.exceptions import (
    BalanceOracleException,
    EthRPCException,
    NoBalancesFoundException,
    NoClosestBlockException,
    UnsupportedAddressTypeException,
    ZeroBalanceException,
)
from ...services.types import (
    AccountAddress,
    Address,
    AddressType,
    ApiConfig,
    Asset,
    AssetBalanceAtTime,
    AssetBalancesAtTime,
    AssetID,
    BlockNumber,
    EVMChain,
    EVMChainID,
    HttpHeaders,
)

from .interfaces import BalanceOracleApiInterface
from .exceptions import ApiException, ApiUnavailableException, RequestException
from .requests import HEADERS_JSON, get_json_request, post_json_request

ROUTESCAN_API_BASE_URL = "https://api.routescan.io/v2"
ROUTESCAN_CDN_BASE_URL = "https://cdn.routescan.io"


class RoutescanNetworkType(StrEnum):
    MAINNET = "mainnet"
    TESTNET = "testnet"


class ResponseBlockchain(TypedDict):
    chainId: str
    name: str
    symbol: AssetID
    rpcs: list[str]


class ResponseBlockchains(TypedDict):
    items: list[ResponseBlockchain]


class RoutescanEtherscanApiModule(StrEnum):
    ACCOUNT = "account"
    BLOCK = "block"


class RoutescanEtherscanApiAction(StrEnum):
    GET_BLOCK_NO_BY_TIME = "getblocknobytime"
    BALANCE_HISTORY = "balancehistory"


class RoutescanEtherscanApiClosest(StrEnum):
    BEFORE = "before"
    AFTER = "after"


class ResponseRoutescanEtherscanApiMessage(StrEnum):
    OK = "OK"
    ERROR = "NOTOK"


class ResponseRoutescanEtherscanApiError(StrEnum):
    TEMP_UNAVAILABLE = "Error! Service is temporarily unavailable"
    NO_CLOSEST_BLOCK = "Error! No closest block found"


class ResponseRoutescanEtherscanApi(TypedDict):
    status: str
    message: ResponseRoutescanEtherscanApiMessage
    result: str | ResponseRoutescanEtherscanApiError


class BlockByNumber(TypedDict):
    number: str
    timestamp: str


class ResponseRPCGetBlockByNumber(TypedDict):
    id: int
    result: BlockByNumber


class ParamsRoutescanEtherscanApi(TypedDict):
    module: RoutescanEtherscanApiModule
    action: RoutescanEtherscanApiAction
    blockno: NotRequired[int]
    address: NotRequired[Address]
    closest: NotRequired[RoutescanEtherscanApiClosest]
    timestamp: NotRequired[int]
    apikey: NotRequired[str]


# https://api.routescan.io/v2/network/mainnet/evm/43114/etherscan/api?module=account&action=tokentx&contractaddress=0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7&address=0x77134cbC06cB00b66F4c7e623D5fdBF6777635EC&page=1&offset=100&startblock=34372864&endblock=34472864&sort=asc&apikey=YourApiKeyToken
# https://api.routescan.io/v2/network/mainnet/evm/1/etherscan/api?module=account&action=tokenbalancehistory&contractaddress=0x57d90b64a1a57749b0f932f1a3395792e12e7055&address=0xe04f27eb70e025b78871a2ad7eabe85e61212761&blockno=8000000&apikey=YourApiKeyToken


class RoutescanAPI(BalanceOracleApiInterface):
    def __init__(self, config: ApiConfig, log: Logger) -> None:
        super().__init__(config=config, log=log)
        self.__base_url_api: str = (
            f"{ROUTESCAN_API_BASE_URL}/network/{RoutescanNetworkType.MAINNET}/evm"
        )
        self.__base_url_cdn: str = f"{ROUTESCAN_CDN_BASE_URL}/api/evm"

        self.__auth_headers: HttpHeaders = {}
        self.__auth_headers.update(HEADERS_JSON)

        self.__supported_address_types = set()
        self.__supported_address_types.update([AddressType.EVM])

        self.__supported_chains: dict[EVMChainID, EVMChain] = self.__get_supported_chains()

    def supported_address_types(self) -> set[AddressType]:
        return self.__supported_address_types

    def __get_supported_chains(self) -> dict[EVMChainID, EVMChain]:
        supported_chains = {}

        try:
            url = f"{self.__base_url_api}/all/blockchains"
            res_blockchains = get_json_request(url=url, headers=self.__auth_headers)
            res_blockchains = cast(ResponseBlockchains, res_blockchains)

            for blockchain in res_blockchains["items"]:
                chain_id = int(blockchain["chainId"])
                chain_name = blockchain["name"]
                asset_id = blockchain["symbol"]

                base_asset: Asset = {
                    "id": asset_id,
                    "name": chain_name,
                    "decimals": EVM_BASE_ASSET_DECIMALS,
                }

                chain: EVMChain = {
                    "id": chain_id,
                    "name": chain_name,
                    "base_asset": base_asset,
                    "rpc_url": blockchain["rpcs"][0],
                }

                supported_chains[chain_id] = chain

        except RequestException as e:
            raise BalanceOracleException(e)

        return dict(sorted(supported_chains.items()))

    @staticmethod
    def __handle_etherscan_response(response: ResponseRoutescanEtherscanApi) -> None:
        if response["message"] == ResponseRoutescanEtherscanApiMessage.OK:
            return

        match response["result"]:
            case ResponseRoutescanEtherscanApiError.TEMP_UNAVAILABLE:
                raise ApiUnavailableException(reason=response["result"])
            case ResponseRoutescanEtherscanApiError.NO_CLOSEST_BLOCK:
                raise NoClosestBlockException()
            case _:
                raise ApiException(f"unexpected error response: {response["message"]}")

    def __get_blocknumber_at(
        self, chain_id: EVMChainID, timestamp_unix_seconds: int
    ) -> BlockNumber:
        try:
            url = f"{self.__base_url_api}/{chain_id}/etherscan/api"
            params: ParamsRoutescanEtherscanApi = {
                "module": RoutescanEtherscanApiModule.BLOCK,
                "action": RoutescanEtherscanApiAction.GET_BLOCK_NO_BY_TIME,
                "closest": RoutescanEtherscanApiClosest.BEFORE,
                "timestamp": timestamp_unix_seconds,
            }

            res_block_no = get_json_request(
                url=url, params=dict(params), headers=self.__auth_headers
            )
            res_block_no = cast(ResponseRoutescanEtherscanApi, res_block_no)
            self.__handle_etherscan_response(res_block_no)

            block_number = res_block_no["result"]
            if not block_number.isdigit():
                raise BalanceOracleException(
                    f"Expected block number as integer, but got '{block_number}'"
                )

            return int(block_number)

        except RequestException as e:
            raise BalanceOracleException(e)

    def __get_block_timestamp(
        self, block_number: BlockNumber, chain_id: EVMChainID, rpc_url: str
    ) -> int:
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": chain_id,
                "method": "eth_getBlockByNumber",
                "params": [hex(block_number), True],
            }

            res_block_timestamp = post_json_request(
                url=rpc_url, json=payload, headers=self.__auth_headers
            )
            res_block_timestamp = cast(ResponseRPCGetBlockByNumber, res_block_timestamp)

            block_timestamp_hex = res_block_timestamp["result"]["timestamp"]
            return int(block_timestamp_hex, 0)

        except RequestException as e:
            raise EthRPCException(e)

    def __get_balance_at_block(
        self,
        address: Address,
        chain_id: EVMChainID,
        block_number: BlockNumber,
    ) -> int:
        try:
            url = f"{self.__base_url_api}/{chain_id}/etherscan/api"
            params: ParamsRoutescanEtherscanApi = {
                "module": RoutescanEtherscanApiModule.ACCOUNT,
                "action": RoutescanEtherscanApiAction.BALANCE_HISTORY,
                "address": address,
                "blockno": block_number,
            }

            res_balance = get_json_request(
                url=url, params=dict(params), headers=self.__auth_headers
            )
            res_balance = cast(ResponseRoutescanEtherscanApi, res_balance)
            self.__handle_etherscan_response(res_balance)

            balance = res_balance["result"]
            if not balance.isdigit():
                raise BalanceOracleException(f"Expected balance as int, but got '{balance}'")

            return int(balance)

        except RequestException as e:
            raise BalanceOracleException(e)

    def __get_base_asset_balance_at_block(
        self,
        address: Address,
        chain: EVMChain,
        block_number: BlockNumber,
        timestamp_unix_seconds: int,
    ) -> AssetBalanceAtTime:
        chain_id = chain["id"]
        chain_name = chain["name"]
        chain_base_asset = chain["base_asset"]

        if "decimals" not in chain_base_asset:
            raise BalanceOracleException(
                f"expected asset '{chain_base_asset['id']} to have value for 'decimals' field."
            )

        balance_gas = self.__get_balance_at_block(
            address=address, chain_id=chain_id, block_number=block_number
        )

        if balance_gas == 0:
            raise ZeroBalanceException(
                f"zero balance for base asset on chain {chain_name} with ID {chain_id}"
            )

        chain_base_asset_decimals = chain_base_asset["decimals"]
        quantity = balance_gas / (10**chain_base_asset_decimals)

        block_timestamp = timestamp_unix_seconds
        chain = self.__supported_chains[chain_id]
        if "rpc_url" in chain:
            rpc_url = chain["rpc_url"]
            try:
                block_timestamp = self.__get_block_timestamp(
                    block_number=block_number,
                    chain_id=chain_id,
                    rpc_url=rpc_url,
                )
            except EthRPCException as e:
                self.__log__.error(
                    f"Failed to get block timestamp from RPC '{rpc_url} for block number {block_number}: {e}"
                )
        else:
            self.__log__.warn(
                f"no rpc url found for chain '{chain_name}' with ID {chain_id}. skipping block timestamp lookup."
            )

        balance_at_time: AssetBalanceAtTime = {
            "asset": chain_base_asset,
            "last_block_number": block_number,
            "quantity": quantity,
            "timestamp": block_timestamp,
        }

        return balance_at_time

    # def __get_token_asset_balances_at_block(
    #     self,
    #     address: Address,
    #     chain: EVMChain,
    #     block_number: BlockNumber,
    # ) -> AssetBalancesAtTime:
    #     balances_at_time: AssetBalancesAtTime = {}

    #     return balances_at_time

    def all_balances_at(
        self, account: AccountAddress, timestamp_unix_seconds: int
    ) -> AssetBalancesAtTime:
        address = account["address"]
        address_type = account["type"]
        if address_type not in self.__supported_address_types:
            raise UnsupportedAddressTypeException(address_type)

        balances_at_time: AssetBalancesAtTime = {}

        for chain in self.__supported_chains.values():
            chain_id = chain["id"]
            chain_name = chain["name"]

            try:
                try:
                    block_number = self.__get_blocknumber_at(
                        chain_id=chain_id, timestamp_unix_seconds=timestamp_unix_seconds
                    )
                except NoClosestBlockException:
                    self.__log__.warn(
                        f"no block found close to {timestamp_unix_seconds} on chain '{chain_name}' with ID {chain_id}. Did chain exist then?"
                    )
                    continue

                try:
                    base_asset_balance = self.__get_base_asset_balance_at_block(
                        address=address,
                        chain=chain,
                        block_number=block_number,
                        timestamp_unix_seconds=timestamp_unix_seconds,
                    )

                    base_asset_id = base_asset_balance["asset"]["id"]
                    if base_asset_id not in balances_at_time:
                        balances_at_time[base_asset_id] = {}

                    balances_at_time[base_asset_id][address] = base_asset_balance
                except ZeroBalanceException:
                    self.__log__.debug(
                        f"Skipping zero balance base asset for chain '{chain_name}' with ID {chain_id}. "
                    )
                    continue

                # try:
                #     token_asset_balances = self.__get_token_asset_balances_at_block(
                #         address=address, chain=chain, block_number=block_number
                #     )
                #     balances_at_time.update(token_asset_balances)
                # except ZeroBalanceException:
                #     self.__log__.debug(
                #         f"Skipping zero balance token assets for chain '{chain_name}' with ID {chain_id}. "
                #     )
                #     continue
            except ApiUnavailableException:
                self.__log__.warn(
                    f"Historical Balance API temporarily unavailable for chain '{chain_name}' with ID {chain_id}. skipping."
                )
                continue

            except ApiException as e:
                self.__log__.error(
                    f"could not get balance for address '{address}' on chain '{chain_name}' with ID {chain_id}: {e}",
                )
                continue

        if len(balances_at_time) == 0:
            raise NoBalancesFoundException()

        return balances_at_time
