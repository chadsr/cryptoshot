from typing import TypedDict, TypeAlias

from .services.types import (
    AccountAddress,
    Address,
    AssetBalanceAtTime,
    AssetID,
    AssetValueAtTime,
    EVMChainID,
    ServiceAssetID,
    ServiceConfig,
    ServiceName,
)


class AccountConfig(AccountAddress):
    name: str


class PriceOracleConfig(TypedDict):
    quote_asset: AssetID
    priority: list[ServiceName]


class FormattingConfig(TypedDict):
    timestamp: str


AssetConfigGrouping: TypeAlias = list[AssetID]


class AssetsConfig(TypedDict):
    include: list[AssetID]
    exclude: list[AssetID]
    group: dict[AssetID, AssetConfigGrouping]


class EvmChainIds(TypedDict):
    include: list[EVMChainID]
    exclude: list[EVMChainID]


class ChainsConfig(TypedDict):
    evmChainIds: EvmChainIds


ServicesConfig: TypeAlias = list[ServiceConfig]
AccountsConfig: TypeAlias = list[AccountConfig]


class Config(TypedDict):
    services: ServicesConfig
    accounts: AccountsConfig
    assets: AssetsConfig
    chains: ChainsConfig
    price_oracle: PriceOracleConfig
    formatting: FormattingConfig


Prices: TypeAlias = dict[AssetID, dict[ServiceName, AssetValueAtTime]]
Balances: TypeAlias = dict[
    AssetID, dict[Address | ServiceName, dict[ServiceAssetID, AssetBalanceAtTime]]
]
