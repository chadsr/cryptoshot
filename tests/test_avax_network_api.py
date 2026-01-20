import logging
from typing import Any
import pytest

from cryptoshot.services.apis.avax_network import AvaxNetworkAPI
from cryptoshot.services.types import ApiConfig, ServiceType, AddressType, AccountAddress


@pytest.fixture
def api_config() -> ApiConfig:
    return {
        "name": "avax-network-test",
        "type": ServiceType.AVAX_NETWORK,
        "api_token": "TEST_TOKEN",
    }


def test_all_balances_at_returns_separate_p_and_x_chain_totals(
    monkeypatch: pytest.MonkeyPatch, api_config: ApiConfig
):
    logger = logging.getLogger("test")

    # Prepare mock data covering ALL P-Chain and X-Chain categories for a single asset
    asset_id = "FvwEAhmxKfeiG8SnEvq42hc6whRyY3EFYAvebMqDNDGCgxN5Z"  # AVAX Asset ID
    symbol = "AVAX"
    name = "Avalanche"
    denom = 9

    # Values in smallest units (strings)
    p_unlocked_unstaked = "100"
    p_unlocked_staked = "200"
    p_locked_platform = "10"
    p_locked_stakeable = "20"
    p_locked_staked = "30"
    p_pending_staked = "40"
    p_atomic_mem_unlocked = "5"
    p_atomic_mem_locked = "6"

    x_locked = "7"
    x_unlocked = "8"
    x_atomic_mem_unlocked = "9"
    x_atomic_mem_locked = "11"

    # Expected totals per chain in smallest units
    total_p_smallest = sum(
        int(v)
        for v in [
            p_unlocked_unstaked,
            p_unlocked_staked,
            p_locked_platform,
            p_locked_stakeable,
            p_locked_staked,
            p_pending_staked,
            p_atomic_mem_unlocked,
            p_atomic_mem_locked,
        ]
    )
    total_x_smallest = sum(
        int(v) for v in [x_locked, x_unlocked, x_atomic_mem_unlocked, x_atomic_mem_locked]
    )

    def make_entry(amount: str) -> dict[str, Any]:
        return {
            "assetId": asset_id,
            "name": name,
            "symbol": symbol,
            "denomination": denom,
            "type": "secp256k1",
            "amount": amount,
            "utxoCount": 1,
        }

    p_chain_response = {
        "balances": {
            "unlockedUnstaked": [make_entry(p_unlocked_unstaked)],
            "unlockedStaked": [make_entry(p_unlocked_staked)],
            "lockedPlatform": [make_entry(p_locked_platform)],
            "lockedStakeable": [make_entry(p_locked_stakeable)],
            "lockedStaked": [make_entry(p_locked_staked)],
            "pendingStaked": [make_entry(p_pending_staked)],
            "atomicMemoryUnlocked": [
                {
                    **make_entry(p_atomic_mem_unlocked),
                    "sharedWithChainId": "11111111111111111111111111111111LpoYY",
                    "status": "unlocked",
                }
            ],
            "atomicMemoryLocked": [
                {
                    **make_entry(p_atomic_mem_locked),
                    "sharedWithChainId": "11111111111111111111111111111111LpoYY",
                    "status": "locked",
                }
            ],
        },
        "chainInfo": {"chainName": "p-chain", "network": "mainnet"},
    }

    x_chain_response = {
        "balances": {
            "locked": [make_entry(x_locked)],
            "unlocked": [make_entry(x_unlocked)],
            "atomicMemoryUnlocked": [
                {
                    **make_entry(x_atomic_mem_unlocked),
                    "sharedWithChainId": "11111111111111111111111111111111LpoYY",
                }
            ],
            "atomicMemoryLocked": [
                {
                    **make_entry(x_atomic_mem_locked),
                    "sharedWithChainId": "11111111111111111111111111111111LpoYY",
                }
            ],
        },
        "chainInfo": {"chainName": "x-chain", "network": "mainnet"},
    }

    def fake_get_json_request(url: str, params=None, headers=None, timeout=10):  # noqa: ARG001
        if "/p-chain/" in url:
            return p_chain_response
        if "/x-chain/" in url:
            return x_chain_response
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(
        "cryptoshot.services.apis.avax_network.get_json_request", fake_get_json_request
    )

    api = AvaxNetworkAPI(config=api_config, log=logger)

    account: AccountAddress = {"address": "avax1testaddressxyz", "type": AddressType.AVAX}
    ts = 1_768_913_327

    balances_at_time = api.all_balances_at(account=account, timestamp_unix_seconds=ts)

    # Expect two separate entries for P-Chain and X-Chain using symbol+suffix as keys
    sym_p = f"{symbol} (P-Chain)"
    sym_x = f"{symbol} (X-Chain)"
    assert sym_p in balances_at_time
    assert sym_x in balances_at_time

    assert account["address"] in balances_at_time[sym_p]
    assert account["address"] in balances_at_time[sym_x]

    bal_p = balances_at_time[sym_p][account["address"]]
    bal_x = balances_at_time[sym_x][account["address"]]

    expected_quantity_p = total_p_smallest / (10**denom)
    expected_quantity_x = total_x_smallest / (10**denom)

    assert bal_p["asset"]["id"] == sym_p
    assert bal_p["asset"]["name"] == f"{name} (P-Chain)"
    assert bal_p["asset"]["decimals"] == denom
    assert bal_p["asset"]["service_asset_id"] == asset_id
    assert bal_p["timestamp"] == ts
    assert bal_p["quantity"] == expected_quantity_p

    assert bal_x["asset"]["id"] == sym_x
    assert bal_x["asset"]["name"] == f"{name} (X-Chain)"
    assert bal_x["asset"]["decimals"] == denom
    assert bal_x["asset"]["service_asset_id"] == asset_id
    assert bal_x["timestamp"] == ts
    assert bal_x["quantity"] == expected_quantity_x
