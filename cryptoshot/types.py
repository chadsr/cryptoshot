from typing import TypedDict, TypeAlias, NotRequired
from enum import Enum
from collections.abc import Mapping

HttpHeaders: TypeAlias = Mapping[str, str | bytes | None]
JSON: TypeAlias = dict[str, "JSON"] | list["JSON"] | str | int | float | bool | None
URL: TypeAlias = str


class ChainID(Enum):
    AVALANCHE = "avalanche"
    ETHEREUM = "ethereum"
    GNOSIS = "gnosis"
    KUSAMA = "kusama"
    POLKADOT = "polkadot"


class AssetType(Enum):
    ERC20 = "erc20"
    NATIVE = "native"


class AddressType(Enum):
    AVAX = "avax"
    ETHEREUM = "eth"
    POLKADOT = "dot"


ServiceID: TypeAlias = str
AssetID: TypeAlias = str


class PriceOracleID(Enum):
    COINAPI = "coinapi"
    COINGECKO = "coingecko"
    KRAKEN = "kraken"


class BalanceOracleID(Enum):
    ALCHEMY = "alchemy"
    AVALANCHE = "avalanche_explorer"
    ETHERSCAN = "etherscan_mainnet"
    GNOSISSCAN = "gnosisscan"
    KRAKEN = "kraken"


class ServiceConfig(TypedDict):
    type: ServiceID
    api_token: str


class KrakenConfig(ServiceConfig):
    private_key: str


class AccountConfig(TypedDict):
    name: str
    address: str
    address_type: AddressType


class PriceOracleConfig(TypedDict):
    quote_asset: AssetID
    priority: list[ServiceID]


class FormattingConfig(TypedDict):
    timestamp: str


AssetGrouping: TypeAlias = list[AssetID]


class AssetsConfig(TypedDict):
    include: list[AssetID]
    exclude: list[AssetID]
    group: dict[AssetID, AssetGrouping]


class Config(TypedDict):
    services: dict[str, ServiceConfig]
    accounts: list[AccountConfig]
    assets: AssetsConfig
    price_oracle: PriceOracleConfig
    formatting: FormattingConfig


class Asset(TypedDict):
    id: AssetID
    name: str
    type: NotRequired[AssetType]
    decimals: NotRequired[int]
    chain_id: NotRequired[ChainID]


class AssetValue(TypedDict):
    asset: Asset
    value: float
    quote_asset: AssetID


class AssetValueAtTime(AssetValue):
    timestamp: int


class AssetBalance(TypedDict):
    asset: Asset
    value: int


class AssetBalanceAtTime(AssetBalance):
    timestamp: int


Assets: TypeAlias = dict[AssetID, Asset]
AssetPairs: TypeAlias = dict[AssetID, set[AssetID | AssetID]]

Prices: TypeAlias = dict[AssetID, dict[ServiceID, AssetValueAtTime]]
