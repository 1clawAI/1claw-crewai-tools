"""Tests for :mod:`oneclaw_crewai._client`."""

from __future__ import annotations

import uuid
from datetime import timedelta

import httpx
import pytest
import respx
from freezegun import freeze_time

from oneclaw_crewai._client import (
    OneclawAuthError,
    OneclawClient,
    OneclawError,
    OneclawSecretNotFoundError,
    OneclawValidationError,
)


def _vault_id() -> str:
    return str(uuid.uuid4())


def _agent_id() -> str:
    return str(uuid.uuid4())


BASE = "https://api.1claw.example"


@respx.mock
def test_successful_auth_and_secret_fetch() -> None:
    vid = _vault_id()
    aid = _agent_id()
    respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "jwt-one", "expires_in": 3600,
                "agent_id": aid, "vault_ids": [vid],
            },
        )
    )
    respx.get(f"{BASE}/v1/vaults/{vid}/secrets/api-keys%2Fstripe").mock(
        return_value=httpx.Response(
            200,
            json={"value": "sk_test_abc", "path": "api-keys/stripe", "version": 1},
        )
    )

    with OneclawClient(api_key="ocv_testkey", base_url=BASE) as client:
        assert client.get_secret("api-keys/stripe") == "sk_test_abc"


@respx.mock
def test_key_only_auth_auto_resolves_agent_and_vault() -> None:
    aid = _agent_id()
    vid = _vault_id()
    respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "jwt", "expires_in": 3600, "agent_id": aid, "vault_ids": [vid]},
        )
    )

    with OneclawClient(api_key="ocv_testkey", base_url=BASE) as client:
        assert client.agent_id == aid
        assert client.vault_id == vid


@respx.mock
def test_jwt_caching_single_auth_for_two_fetches() -> None:
    vid = _vault_id()
    aid = _agent_id()
    auth_route = respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "jwt-one", "expires_in": 3600,
                "agent_id": aid, "vault_ids": [vid],
            },
        )
    )
    respx.get(f"{BASE}/v1/vaults/{vid}/secrets/a").mock(
        return_value=httpx.Response(200, json={"value": "v1"}),
    )
    respx.get(f"{BASE}/v1/vaults/{vid}/secrets/b").mock(
        return_value=httpx.Response(200, json={"value": "v2"}),
    )

    with OneclawClient(api_key="ocv_testkey", agent_id=aid, vault_id=vid, base_url=BASE) as client:
        assert client.get_secret("a") == "v1"
        assert client.get_secret("b") == "v2"
        assert auth_route.call_count == 1


@respx.mock
@pytest.mark.parametrize("status", [401, 403])
def test_auth_error_on_token_failure(status: int) -> None:
    respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(status, json={"detail": "nope"}),
    )

    with OneclawClient(api_key="ocv_testkey", agent_id="a", vault_id="v", base_url=BASE) as client:
        with pytest.raises(OneclawAuthError):
            client.get_secret("x")


@respx.mock
def test_secret_not_found() -> None:
    vid = _vault_id()
    respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600}),
    )
    respx.get(f"{BASE}/v1/vaults/{vid}/secrets/missing").mock(
        return_value=httpx.Response(404, json={"detail": "not found"}),
    )

    with OneclawClient(api_key="ocv_testkey", vault_id=vid, base_url=BASE) as client:
        with pytest.raises(OneclawSecretNotFoundError):
            client.get_secret("missing")


@respx.mock
def test_other_http_error() -> None:
    vid = _vault_id()
    respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600}),
    )
    respx.get(f"{BASE}/v1/vaults/{vid}/secrets/boom").mock(
        return_value=httpx.Response(500, json={"detail": "server"}),
    )

    with OneclawClient(api_key="ocv_testkey", vault_id=vid, base_url=BASE) as client:
        with pytest.raises(OneclawError):
            client.get_secret("boom")


@respx.mock
def test_token_refresh_when_near_expiry() -> None:
    vid = _vault_id()
    aid = _agent_id()
    auth = respx.post(f"{BASE}/v1/auth/agent-token").mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "jwt-first", "expires_in": 100}),
            httpx.Response(200, json={"access_token": "jwt-second", "expires_in": 3600}),
        ]
    )
    respx.get(f"{BASE}/v1/vaults/{vid}/secrets/x").mock(
        return_value=httpx.Response(200, json={"value": "ok"}),
    )

    with OneclawClient(api_key="ocv_testkey", agent_id=aid, vault_id=vid, base_url=BASE) as client:
        with freeze_time("2024-06-01T12:00:00Z") as frozen:
            assert client.get_secret("x") == "ok"
            frozen.tick(delta=timedelta(seconds=41))
            assert client.get_secret("x") == "ok"
        assert auth.call_count == 2


@respx.mock
def test_put_secret() -> None:
    vid = _vault_id()
    aid = _agent_id()
    respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600}),
    )
    respx.put(f"{BASE}/v1/vaults/{vid}/secrets/new%2Fkey").mock(
        return_value=httpx.Response(200, json={"version": 1}),
    )

    with OneclawClient(api_key="ocv_testkey", agent_id=aid, vault_id=vid, base_url=BASE) as client:
        result = client.put_secret("new/key", "value123")
        assert result["version"] == 1


@respx.mock
def test_list_secrets() -> None:
    vid = _vault_id()
    respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600}),
    )
    respx.get(f"{BASE}/v1/vaults/{vid}/secrets").mock(
        return_value=httpx.Response(200, json={"secrets": [{"path": "a"}, {"path": "b"}]}),
    )

    with OneclawClient(api_key="ocv_testkey", vault_id=vid, base_url=BASE) as client:
        secrets = client.list_secrets()
        assert len(secrets) == 2


@respx.mock
def test_rotate_secret() -> None:
    vid = _vault_id()
    respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600}),
    )
    respx.post(f"{BASE}/v1/vaults/{vid}/secret-rotate/my%2Fkey").mock(
        return_value=httpx.Response(200, json={"version": 2}),
    )

    with OneclawClient(api_key="ocv_testkey", vault_id=vid, base_url=BASE) as client:
        result = client.rotate_secret("my/key", length=64, charset="hex")
        assert result["version"] == 2


@respx.mock
def test_memory_put_and_get() -> None:
    aid = _agent_id()
    respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600}),
    )
    respx.put(f"{BASE}/v1/agents/{aid}/memory/default/testkey").mock(
        return_value=httpx.Response(200, json={"status": "ok"}),
    )
    respx.get(f"{BASE}/v1/agents/{aid}/memory/default/testkey").mock(
        return_value=httpx.Response(200, json={"value": "hello"}),
    )

    with OneclawClient(api_key="ocv_testkey", agent_id=aid, vault_id="v", base_url=BASE) as client:
        client.memory_put("default", "testkey", "hello")
        assert client.memory_get("default", "testkey") == "hello"


@respx.mock
def test_memory_get_not_found_returns_none() -> None:
    aid = _agent_id()
    respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600}),
    )
    respx.get(f"{BASE}/v1/agents/{aid}/memory/default/missing").mock(
        return_value=httpx.Response(404, json={"detail": "not found"}),
    )

    with OneclawClient(api_key="ocv_testkey", agent_id=aid, vault_id="v", base_url=BASE) as client:
        assert client.memory_get("default", "missing") is None


@respx.mock
def test_memory_search() -> None:
    aid = _agent_id()
    respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600}),
    )
    respx.post(f"{BASE}/v1/agents/{aid}/memory/search").mock(
        return_value=httpx.Response(
            200, json={"results": [{"key": "k1", "value": "v1", "score": 0.9}]}
        ),
    )

    with OneclawClient(api_key="ocv_testkey", agent_id=aid, vault_id="v", base_url=BASE) as client:
        results = client.memory_search("default", "test query")
        assert len(results) == 1
        assert results[0]["key"] == "k1"


@respx.mock
def test_sign_message() -> None:
    aid = _agent_id()
    respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600}),
    )
    respx.post(f"{BASE}/v1/agents/{aid}/sign").mock(
        return_value=httpx.Response(
            200, json={"signature": "0xabc", "message_hash": "0xdef", "from": "0x123"}
        ),
    )

    with OneclawClient(api_key="ocv_testkey", agent_id=aid, vault_id="v", base_url=BASE) as client:
        result = client.sign_message("hello", chain="ethereum")
        assert result["signature"] == "0xabc"


@respx.mock
def test_submit_transaction() -> None:
    aid = _agent_id()
    respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600}),
    )
    respx.post(f"{BASE}/v1/agents/{aid}/transactions").mock(
        return_value=httpx.Response(
            200,
            json={
                "tx_hash": "0xabc123",
                "status": "broadcast",
                "signed_tx": "0x...",
            },
        ),
    )

    with OneclawClient(api_key="ocv_testkey", agent_id=aid, vault_id="v", base_url=BASE) as client:
        result = client.submit_transaction(chain="ethereum", to="0xdead", value="0.1")
        assert result["status"] == "broadcast"


@respx.mock
def test_get_balance() -> None:
    aid = _agent_id()
    respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600}),
    )
    respx.get(f"{BASE}/v1/agents/{aid}/signing-keys/ethereum/balance").mock(
        return_value=httpx.Response(200, json={"native_balance": "1.5", "address": "0x123"}),
    )

    with OneclawClient(api_key="ocv_testkey", agent_id=aid, vault_id="v", base_url=BASE) as client:
        result = client.get_signing_key_balance("ethereum")
        assert result["native_balance"] == "1.5"


@respx.mock
def test_trigger_automation() -> None:
    aid = _agent_id()
    auto_id = str(uuid.uuid4())
    respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600}),
    )
    respx.post(f"{BASE}/v1/automations/{auto_id}/trigger").mock(
        return_value=httpx.Response(200, json={"run_id": "r1", "status": "running"}),
    )

    with OneclawClient(api_key="ocv_testkey", agent_id=aid, vault_id="v", base_url=BASE) as client:
        result = client.trigger_automation(auto_id)
        assert result["status"] == "running"


@respx.mock
def test_validation_error_on_400() -> None:
    vid = _vault_id()
    respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600}),
    )
    respx.put(f"{BASE}/v1/vaults/{vid}/secrets/bad").mock(
        return_value=httpx.Response(400, json={"detail": "invalid"}),
    )

    with OneclawClient(api_key="ocv_testkey", vault_id=vid, base_url=BASE) as client:
        with pytest.raises(OneclawValidationError):
            client.put_secret("bad", "")
