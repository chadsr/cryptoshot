from enum import StrEnum
from typing import TypeAlias, TypedDict, NotRequired, Mapping

HttpHeaders: TypeAlias = Mapping[str, str | bytes | None]
JSON: TypeAlias = dict[str, "JSON"] | list["JSON"] | str | int | float | bool | None

AssetID: TypeAlias = str
ServiceName: TypeAlias = str
ServiceAssetID: TypeAlias = str
Address: TypeAlias = str
BlockNumber: TypeAlias = int


class AddressType(StrEnum):
    XPUB = "xpub"
    AVAX = "avax"
    EVM = "evm"
    POLKADOT = "dot"
    KUSAMA = "ksm"


class AccountAddress(TypedDict):
    address: Address
    type: AddressType


class ServiceType(StrEnum):
    COINAPI = "coinapi"
    COINGECKO = "coingecko"
    KRAKEN = "kraken"
    ROUTESCAN = "routescan"


class AssetType(StrEnum):
    ERC20 = "erc20"
    ERC721 = "erc721"
    ERC1155 = "erc1155"
    NATIVE = "native"


class ServiceConfig(TypedDict):
    name: ServiceName
    type: ServiceType


class ApiConfig(ServiceConfig):
    api_token: str


class Asset(TypedDict):
    id: AssetID
    name: str
    type: NotRequired[AssetType]
    decimals: NotRequired[int]
    service_asset_id: NotRequired[ServiceAssetID]


EVMChainID: TypeAlias = int
ChainName: TypeAlias = str


class EVMChain(TypedDict):
    base_asset: Asset
    id: EVMChainID
    name: ChainName
    rpc_url: NotRequired[str]


class AssetValue(TypedDict):
    asset: Asset
    value: float
    quote_asset: AssetID


class AssetValueAtTime(AssetValue):
    timestamp: int


class AssetBalance(TypedDict):
    asset: Asset
    quantity: float


class AssetBalanceAtTime(AssetBalance):
    timestamp: int
    last_block_number: NotRequired[BlockNumber]


Assets: TypeAlias = dict[AssetID, Asset]
AssetPairs: TypeAlias = dict[AssetID, set[AssetID | AssetID]]

AssetValuesAtTime = dict[AssetID, AssetValueAtTime]
AssetBalancesAtTime = dict[AssetID, dict[ServiceAssetID | Address, AssetBalanceAtTime]]
