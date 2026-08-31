"""Tests for :mod:`oneclaw_crewai._tool`."""

from __future__ import annotations

import json
import uuid
from unittest.mock import patch

import httpx
import respx

from oneclaw_crewai._client import OneclawAuthError, OneclawClient
from oneclaw_crewai._tool import (
    OneclawGetBalanceTool,
    OneclawListSecretsTool,
    OneclawMemoryGetTool,
    OneclawMemoryPutTool,
    OneclawMemorySearchTool,
    OneclawPutSecretTool,
    OneclawRotateSecretTool,
    OneclawSignMessageTool,
    OneclawSubmitTransactionTool,
    OneclawTriggerAutomationTool,
    OneclawVaultTool,
    get_all_tools,
)

BASE = "https://api.1claw.example"


def _ids() -> tuple[str, str, str]:
    return str(uuid.uuid4()), str(uuid.uuid4()), "ocv_testkey1234567890"


def _make_client(agent_id: str, vault_id: str) -> OneclawClient:
    return OneclawClient(
        api_key="ocv_testkey", agent_id=agent_id, vault_id=vault_id, base_url=BASE
    )


def _mock_auth() -> None:
    respx.post(f"{BASE}/v1/auth/agent-token").mock(
        return_value=httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600}),
    )


# --- OneclawVaultTool (backward-compat constructor) ---


@respx.mock
def test_vault_tool_backward_compat_constructor() -> None:
    agent_id, vault_id, api_key = _ids()
    _mock_auth()
    respx.get(f"{BASE}/v1/vaults/{vault_id}/secrets/api-keys%2Fopenai").mock(
        return_value=httpx.Response(200, json={"value": "the-key-material"}),
    )

    tool = OneclawVaultTool(
        agent_id=agent_id, api_key=api_key, vault_id=vault_id, base_url=BASE
    )
    try:
        assert tool._run("api-keys/openai") == "the-key-material"
    finally:
        if tool._client is not None:
            tool._client.close()


@respx.mock
def test_vault_tool_with_shared_client() -> None:
    agent_id, vault_id, _ = _ids()
    client = _make_client(agent_id, vault_id)
    _mock_auth()
    respx.get(f"{BASE}/v1/vaults/{vault_id}/secrets/key").mock(
        return_value=httpx.Response(200, json={"value": "secret123"}),
    )

    tool = OneclawVaultTool(client=client)
    try:
        assert tool._run("key") == "secret123"
    finally:
        client.close()


def test_vault_tool_returns_error_string_on_failure() -> None:
    agent_id, vault_id, _ = _ids()
    client = _make_client(agent_id, vault_id)
    tool = OneclawVaultTool(client=client)
    try:
        with patch.object(client, "get_secret", side_effect=OneclawAuthError("denied")):
            out = tool._run("any/path")
        assert out.startswith("[1claw error]")
        assert "denied" in out
    finally:
        client.close()


def test_cache_function_disabled() -> None:
    agent_id, vault_id, _ = _ids()
    client = _make_client(agent_id, vault_id)
    tool = OneclawVaultTool(client=client)
    try:
        assert callable(tool.cache_function)
        assert tool.cache_function({"path": "x"}, "out") is False
    finally:
        client.close()


# --- OneclawPutSecretTool ---


@respx.mock
def test_put_secret_tool() -> None:
    agent_id, vault_id, _ = _ids()
    client = _make_client(agent_id, vault_id)
    _mock_auth()
    respx.put(f"{BASE}/v1/vaults/{vault_id}/secrets/new%2Fsecret").mock(
        return_value=httpx.Response(200, json={"version": 1}),
    )

    tool = OneclawPutSecretTool(client=client)
    try:
        result = json.loads(tool._run("new/secret", "myvalue"))
        assert result["version"] == 1
    finally:
        client.close()


# --- OneclawListSecretsTool ---


@respx.mock
def test_list_secrets_tool() -> None:
    agent_id, vault_id, _ = _ids()
    client = _make_client(agent_id, vault_id)
    _mock_auth()
    respx.get(f"{BASE}/v1/vaults/{vault_id}/secrets").mock(
        return_value=httpx.Response(200, json={"secrets": [{"path": "a"}]}),
    )

    tool = OneclawListSecretsTool(client=client)
    try:
        result = json.loads(tool._run())
        assert len(result) == 1
    finally:
        client.close()


# --- OneclawRotateSecretTool ---


@respx.mock
def test_rotate_secret_tool() -> None:
    agent_id, vault_id, _ = _ids()
    client = _make_client(agent_id, vault_id)
    _mock_auth()
    respx.post(f"{BASE}/v1/vaults/{vault_id}/secret-rotate/k").mock(
        return_value=httpx.Response(200, json={"version": 3}),
    )

    tool = OneclawRotateSecretTool(client=client)
    try:
        result = json.loads(tool._run("k"))
        assert result["version"] == 3
    finally:
        client.close()


# --- OneclawMemoryPutTool ---


@respx.mock
def test_memory_put_tool() -> None:
    agent_id, vault_id, _ = _ids()
    client = _make_client(agent_id, vault_id)
    _mock_auth()
    respx.put(f"{BASE}/v1/agents/{agent_id}/memory/default/mykey").mock(
        return_value=httpx.Response(200, json={"status": "ok"}),
    )

    tool = OneclawMemoryPutTool(client=client)
    try:
        result = tool._run("mykey", "myval")
        assert "Stored" in result
    finally:
        client.close()


# --- OneclawMemoryGetTool ---


@respx.mock
def test_memory_get_tool() -> None:
    agent_id, vault_id, _ = _ids()
    client = _make_client(agent_id, vault_id)
    _mock_auth()
    respx.get(f"{BASE}/v1/agents/{agent_id}/memory/default/mykey").mock(
        return_value=httpx.Response(200, json={"value": "recalled"}),
    )

    tool = OneclawMemoryGetTool(client=client)
    try:
        assert tool._run("mykey") == "recalled"
    finally:
        client.close()


@respx.mock
def test_memory_get_tool_not_found() -> None:
    agent_id, vault_id, _ = _ids()
    client = _make_client(agent_id, vault_id)
    _mock_auth()
    respx.get(f"{BASE}/v1/agents/{agent_id}/memory/default/missing").mock(
        return_value=httpx.Response(404, json={"detail": "not found"}),
    )

    tool = OneclawMemoryGetTool(client=client)
    try:
        assert "not found" in tool._run("missing")
    finally:
        client.close()


# --- OneclawMemorySearchTool ---


@respx.mock
def test_memory_search_tool() -> None:
    agent_id, vault_id, _ = _ids()
    client = _make_client(agent_id, vault_id)
    _mock_auth()
    respx.post(f"{BASE}/v1/agents/{agent_id}/memory/search").mock(
        return_value=httpx.Response(
            200, json={"results": [{"key": "k1", "score": 0.9}]}
        ),
    )

    tool = OneclawMemorySearchTool(client=client)
    try:
        result = json.loads(tool._run("find info"))
        assert len(result) == 1
    finally:
        client.close()


# --- OneclawSignMessageTool ---


@respx.mock
def test_sign_message_tool() -> None:
    agent_id, vault_id, _ = _ids()
    client = _make_client(agent_id, vault_id)
    _mock_auth()
    respx.post(f"{BASE}/v1/agents/{agent_id}/sign").mock(
        return_value=httpx.Response(
            200, json={"signature": "0xabc", "from": "0x123"}
        ),
    )

    tool = OneclawSignMessageTool(client=client)
    try:
        result = json.loads(tool._run("hello"))
        assert result["signature"] == "0xabc"
    finally:
        client.close()


# --- OneclawSubmitTransactionTool ---


@respx.mock
def test_submit_transaction_tool() -> None:
    agent_id, vault_id, _ = _ids()
    client = _make_client(agent_id, vault_id)
    _mock_auth()
    respx.post(f"{BASE}/v1/agents/{agent_id}/transactions").mock(
        return_value=httpx.Response(
            200, json={"tx_hash": "0x789", "status": "broadcast"}
        ),
    )

    tool = OneclawSubmitTransactionTool(client=client)
    try:
        result = json.loads(tool._run("ethereum", "0xdead", "0.01"))
        assert result["status"] == "broadcast"
    finally:
        client.close()


# --- OneclawGetBalanceTool ---


@respx.mock
def test_get_balance_tool() -> None:
    agent_id, vault_id, _ = _ids()
    client = _make_client(agent_id, vault_id)
    _mock_auth()
    respx.get(f"{BASE}/v1/agents/{agent_id}/signing-keys/ethereum/balance").mock(
        return_value=httpx.Response(
            200, json={"native_balance": "2.0", "address": "0x123"}
        ),
    )

    tool = OneclawGetBalanceTool(client=client)
    try:
        result = json.loads(tool._run("ethereum"))
        assert result["native_balance"] == "2.0"
    finally:
        client.close()


# --- OneclawTriggerAutomationTool ---


@respx.mock
def test_trigger_automation_tool() -> None:
    agent_id, vault_id, _ = _ids()
    auto_id = str(uuid.uuid4())
    client = _make_client(agent_id, vault_id)
    _mock_auth()
    respx.post(f"{BASE}/v1/automations/{auto_id}/trigger").mock(
        return_value=httpx.Response(200, json={"run_id": "r1", "status": "running"}),
    )

    tool = OneclawTriggerAutomationTool(client=client)
    try:
        result = json.loads(tool._run(auto_id))
        assert result["status"] == "running"
    finally:
        client.close()


# --- get_all_tools ---


def test_get_all_tools_returns_every_registered_tool() -> None:
    # An exact set, not a count: when a tool is added or renamed the failure
    # names it. The previous version asserted len() == 11 alongside 11 names,
    # so the two env-var tools were added without the test noticing.
    expected = {
        "oneclaw_vault",
        "oneclaw_put_secret",
        "oneclaw_list_secrets",
        "oneclaw_rotate_secret",
        "oneclaw_resolve_env",
        "oneclaw_list_env_vars",
        "oneclaw_memory_put",
        "oneclaw_memory_get",
        "oneclaw_memory_search",
        "oneclaw_sign_message",
        "oneclaw_submit_transaction",
        "oneclaw_get_balance",
        "oneclaw_trigger_automation",
    }
    agent_id, vault_id, _ = _ids()
    client = _make_client(agent_id, vault_id)
    try:
        tools = get_all_tools(client)
        assert {t.name for t in tools} == expected
        assert len(tools) == len(expected), "get_all_tools returned a duplicate"
    finally:
        client.close()
