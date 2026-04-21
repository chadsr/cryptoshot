from collections.abc import Mapping
from logging import Logger
from time import sleep
from typing import TypedDict, override

from .interfaces import BalanceOracleApiInterface
from .requestutils import post_json_request
from .exceptions import RequestException
from ..exceptions import (
    BalanceOracleException,
    NoBalancesFoundException,
    UnsupportedAddressTypeException,
)
from ..types import (
    AccountAddress,
    AddressType,
    ApiConfig,
    Asset,
    AssetBalancesAtTime,
    HttpHeaders,
    JSONDict,
)

# Ethereum mainnet beacon chain constants
GENESIS_TIME = 1_606_824_023
SLOTS_PER_EPOCH = 32
SECONDS_PER_SLOT = 12
SECONDS_PER_EPOCH = SLOTS_PER_EPOCH * SECONDS_PER_SLOT

API_BASE = "https://beaconcha.in/api/v2"
API_BALANCES_ENDPOINT = f"{API_BASE}/ethereum/validators/balances"
ETH_DECIMALS = 18

MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 5


class BeaconchainBalanceEntry(TypedDict):
    """Parsed balance entry from the Beaconcha.in V2 API response."""

    index: int
    public_key: str
    balance_wei: int
    effective_wei: int
    timestamp_start: int
    timestamp_end: int


def _timestamp_to_epoch(ts: int) -> int:
    """Convert a Unix timestamp to a beacon chain epoch number."""
    if ts < GENESIS_TIME:
        raise BalanceOracleException(
            f"Timestamp {ts} is before beacon chain genesis ({GENESIS_TIME})"
        )
    return (ts - GENESIS_TIME) // SECONDS_PER_EPOCH


def _extract_balance(response: JSONDict, validator: str | int) -> BeaconchainBalanceEntry:
    """Extract and validate the balance result from a Beaconcha.in API response."""
    data = response.get("data")
    if not isinstance(data, list) or len(data) == 0:
        raise NoBalancesFoundException(f"No balance data returned for validator {validator}")

    entry = data[0]
    if not isinstance(entry, Mapping):
        raise BalanceOracleException("Unexpected response format: expected mapping entry")

    balance_json = entry.get("balance")
    if not isinstance(balance_json, Mapping):
        raise BalanceOracleException("Unexpected response format: expected balance mapping")

    validator_json = entry.get("validator")
    if not isinstance(validator_json, Mapping):
        raise BalanceOracleException("Unexpected response format: expected validator mapping")

    current = balance_json.get("current")
    effective = balance_json.get("effective")
    if not isinstance(current, str) or not isinstance(effective, str):
        raise BalanceOracleException("Unexpected response format: expected string balance values")

    index_val = validator_json.get("index")
    pubkey_val = validator_json.get("public_key")
    if not isinstance(index_val, int) or not isinstance(pubkey_val, str):
        raise BalanceOracleException(
            "Unexpected response format: expected int index and str public_key"
        )

    range = response.get("range")
    if not isinstance(range, Mapping):
        raise BalanceOracleException("Unexpected response format: expected range mapping entry")

    timestamp_json = range.get("timestamp")
    if not isinstance(timestamp_json, Mapping):
        raise BalanceOracleException("Unexpected response format: expected timestamp mapping")

    timestamp_start = timestamp_json.get("start")
    if not isinstance(timestamp_start, int):
        raise BalanceOracleException("Unexpected response format: expected int timestamp values")

    timestamp_end = timestamp_json.get("end")
    if not isinstance(timestamp_end, int):
        raise BalanceOracleException("Unexpected response format: expected int timestamp values")

    return BeaconchainBalanceEntry(
        index=index_val,
        public_key=pubkey_val,
        balance_wei=int(current),
        effective_wei=int(effective),
        timestamp_start=timestamp_start,
        timestamp_end=timestamp_end,
    )


class BeaconchainAPI(BalanceOracleApiInterface):
    """Beaconcha.in validator balance oracle.

    Queries the Beaconcha.in V2 API for an Ethereum beacon chain validator's
    balance at a given epoch (derived from the requested Unix timestamp).

    The account address should be a validator index (e.g. ``"12345"``) or a
    ``0x``-prefixed public key.  The address type must be ``"eth_validator"``.
    """

    def __init__(self, config: ApiConfig, log: Logger) -> None:
        super().__init__(config=config, log=log)

        self.__api_key: str = config["api_token"]

        self.__headers: HttpHeaders = {
            "Authorization": f"Bearer {self.__api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        self.__supported_address_types: set[AddressType] = {AddressType.ETH_VALIDATOR}

    @override
    def supported_address_types(self) -> set[AddressType]:
        return self.__supported_address_types

    def __fetch_validator_balance(
        self, validator: str | int, epoch: int
    ) -> BeaconchainBalanceEntry:
        """Fetch validator balance at a specific epoch via the Beaconcha.in API."""
        identifier = int(validator) if str(validator).isdigit() else validator

        body: JSONDict = {
            "validator": {"validator_identifiers": [identifier]},
            "chain": "mainnet",
            "epoch": epoch,
        }

        res_json = post_json_request(
            url=API_BALANCES_ENDPOINT,
            json=body,
            headers=self.__headers,
        )

        if not isinstance(res_json, Mapping):
            raise BalanceOracleException("Unexpected response format: expected mapping")

        return _extract_balance(res_json, validator)

    @override
    def all_balances_at(
        self, account: AccountAddress, timestamp_unix_seconds: int
    ) -> AssetBalancesAtTime:
        address = account["address"]
        address_type = account["type"]
        if address_type not in self.__supported_address_types:
            raise UnsupportedAddressTypeException(address_type)

        epoch = _timestamp_to_epoch(timestamp_unix_seconds)
        self.__log__.debug(
            f"Querying beaconchain validator {address} at epoch {epoch} "
            f"(timestamp {timestamp_unix_seconds})"
        )

        balance_result: BeaconchainBalanceEntry | None = None
        retries = 0
        while balance_result is None and retries < MAX_RETRIES:
            try:
                balance_result = self.__fetch_validator_balance(validator=address, epoch=epoch)
            except RequestException as e:
                retries += 1
                if retries == MAX_RETRIES:
                    raise e

                sleep(RETRY_WAIT_SECONDS)
                continue

        if not balance_result:
            raise NoBalancesFoundException("No balance found after %d retries", retries)

        balance_eth: float = balance_result["balance_wei"] / 10**ETH_DECIMALS

        if balance_eth == 0:
            raise NoBalancesFoundException(f"Validator {address} has zero balance at epoch {epoch}")

        asset: Asset = {
            "id": "ETH",
            "name": "Ethereum (Beacon Chain)",
            "decimals": ETH_DECIMALS,
        }

        balances_at_time: AssetBalancesAtTime = {
            "ETH": {
                address: {
                    "asset": asset,
                    "quantity": balance_eth,
                    "epoch_number": epoch,
                    "timestamp": balance_result["timestamp_start"],
                }
            }
        }

        return balances_at_time
