"""Tests for :mod:`oneclaw_crewai._tool`."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import httpx
import respx

from oneclaw_crewai._client import OneclawAuthError
from oneclaw_crewai._tool import OneclawVaultTool


def _ids() -> tuple[str, str, str]:
    return str(uuid.uuid4()), str(uuid.uuid4()), "ocv_testkey1234567890"


@respx.mock
def test_run_returns_secret_on_success() -> None:
    agent_id, vault_id, api_key = _ids()
    base = "https://api.1claw.example"
    respx.post(f"{base}/v1/auth/agent-token").mock(
        return_value=httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600}),
    )
    respx.get(f"{base}/v1/vaults/{vault_id}/secrets/api-keys%2Fopenai").mock(
        return_value=httpx.Response(200, json={"value": "the-key-material"}),
    )

    tool = OneclawVaultTool(
        agent_id=agent_id,
        api_key=api_key,
        vault_id=vault_id,
        base_url=base,
    )
    try:
        assert tool._run("api-keys/openai") == "the-key-material"
    finally:
        if tool._client is not None:
            tool._client.close()


def test_run_returns_error_string_on_oneclaw_error() -> None:
    agent_id, vault_id, api_key = _ids()
    tool = OneclawVaultTool(
        agent_id=agent_id,
        api_key=api_key,
        vault_id=vault_id,
        base_url="https://api.1claw.example",
    )
    try:
        assert tool._client is not None
        with patch.object(
            tool._client,
            "get_secret",
            side_effect=OneclawAuthError("denied"),
        ):
            out = tool._run("any/path")
        assert out.startswith("[1claw error]")
        assert "denied" in out
    finally:
        if tool._client is not None:
            tool._client.close()


def test_cache_function_disabled() -> None:
    agent_id, vault_id, api_key = _ids()
    tool = OneclawVaultTool(
        agent_id=agent_id,
        api_key=api_key,
        vault_id=vault_id,
        base_url="https://api.1claw.example",
    )
    try:
        assert callable(tool.cache_function)
        assert tool.cache_function({"path": "x"}, "out") is False
    finally:
        if tool._client is not None:
            tool._client.close()
