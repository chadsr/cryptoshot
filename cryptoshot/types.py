from datetime import datetime
from typing import TypedDict, TypeAlias
from enum import Enum


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
    AVAX_P_CHAIN = "avax_p"
    AVAX_X_CHAIN = "avax_x"
    ETHEREUM = "eth"
    POLKADOT = "dot"


ServiceID: TypeAlias = str


class PriceOracleID(Enum):
    COINGECKO: ServiceID = "coingecko"
    KRAKEN: ServiceID = "kraken"


class BalanceOracleID(Enum):
    ALCHEMY: ServiceID = "alchemy"
    AVALANCHE: ServiceID = "avalanche_explorer"
    ETHERSCAN: ServiceID = "etherscan_mainnet"
    GNOSISSCAN: ServiceID = "gnosisscan"
    KRAKEN: ServiceID = "kraken"


class ServiceConfig(TypedDict):
    id: ServiceID
    api_token: str


class KrakenConfig(ServiceConfig):
    private_key: str


class AccountConfig(TypedDict):
    name: str
    address: str
    address_type: AddressType


class PriceOracleConfig(TypedDict):
    base_currency: str
    priority: list[ServiceID]


class FormattingConfig(TypedDict):
    timestamp: str


class Config(TypedDict):
    services: list[ServiceConfig]
    accounts: list[AccountConfig]
    price_oracle: PriceOracleConfig
    formatting: FormattingConfig


class Asset(TypedDict):
    id: str
    name: str
    type: AssetType
    decimals: int
    chain_id: ChainID


class Balance(TypedDict):
    asset: Asset
    value: int


class BalanceAtTime(Balance):
    time: datetime
