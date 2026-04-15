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
)


def _vault_id() -> str:
    return str(uuid.uuid4())


def _agent_id() -> str:
    return str(uuid.uuid4())


@respx.mock
def test_successful_auth_and_secret_fetch(api_base: str) -> None:
    vid = _vault_id()
    aid = _agent_id()
    respx.post(f"{api_base}/v1/auth/agent-token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "jwt-one", "expires_in": 3600},
        )
    )
    respx.get(f"{api_base}/v1/vaults/{vid}/secrets/api-keys%2Fstripe").mock(
        return_value=httpx.Response(
            200,
            json={"value": "sk_test_abc", "path": "api-keys/stripe", "version": 1},
        )
    )

    client = OneclawClient(
        agent_id=aid,
        api_key="ocv_testkey",
        vault_id=vid,
        base_url=api_base,
    )
    try:
        assert client.get_secret("api-keys/stripe") == "sk_test_abc"
    finally:
        client.close()


@respx.mock
def test_jwt_caching_single_auth_for_two_fetches(api_base: str) -> None:
    vid = _vault_id()
    aid = _agent_id()
    auth_route = respx.post(f"{api_base}/v1/auth/agent-token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "jwt-one", "expires_in": 3600},
        )
    )
    respx.get(f"{api_base}/v1/vaults/{vid}/secrets/a").mock(
        return_value=httpx.Response(200, json={"value": "v1"}),
    )
    respx.get(f"{api_base}/v1/vaults/{vid}/secrets/b").mock(
        return_value=httpx.Response(200, json={"value": "v2"}),
    )

    client = OneclawClient(
        agent_id=aid,
        api_key="ocv_testkey",
        vault_id=vid,
        base_url=api_base,
    )
    try:
        assert client.get_secret("a") == "v1"
        assert client.get_secret("b") == "v2"
        assert auth_route.call_count == 1
    finally:
        client.close()


@respx.mock
@pytest.mark.parametrize("status", [401, 403])
def test_auth_error_on_token_failure(api_base: str, status: int) -> None:
    vid = _vault_id()
    aid = _agent_id()
    respx.post(f"{api_base}/v1/auth/agent-token").mock(
        return_value=httpx.Response(status, json={"detail": "nope"}),
    )

    client = OneclawClient(
        agent_id=aid,
        api_key="ocv_testkey",
        vault_id=vid,
        base_url=api_base,
    )
    try:
        with pytest.raises(OneclawAuthError):
            client.get_secret("x")
    finally:
        client.close()


@respx.mock
def test_secret_not_found(api_base: str) -> None:
    vid = _vault_id()
    aid = _agent_id()
    respx.post(f"{api_base}/v1/auth/agent-token").mock(
        return_value=httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600}),
    )
    respx.get(f"{api_base}/v1/vaults/{vid}/secrets/missing").mock(
        return_value=httpx.Response(404, json={"detail": "not found"}),
    )

    client = OneclawClient(
        agent_id=aid,
        api_key="ocv_testkey",
        vault_id=vid,
        base_url=api_base,
    )
    try:
        with pytest.raises(OneclawSecretNotFoundError):
            client.get_secret("missing")
    finally:
        client.close()


@respx.mock
def test_other_http_error(api_base: str) -> None:
    vid = _vault_id()
    aid = _agent_id()
    respx.post(f"{api_base}/v1/auth/agent-token").mock(
        return_value=httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600}),
    )
    respx.get(f"{api_base}/v1/vaults/{vid}/secrets/boom").mock(
        return_value=httpx.Response(500, json={"detail": "server"}),
    )

    client = OneclawClient(
        agent_id=aid,
        api_key="ocv_testkey",
        vault_id=vid,
        base_url=api_base,
    )
    try:
        with pytest.raises(OneclawError):
            client.get_secret("boom")
    finally:
        client.close()


@respx.mock
def test_token_refresh_when_near_expiry(api_base: str) -> None:
    vid = _vault_id()
    aid = _agent_id()
    auth = respx.post(f"{api_base}/v1/auth/agent-token").mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "jwt-first", "expires_in": 100}),
            httpx.Response(200, json={"access_token": "jwt-second", "expires_in": 3600}),
        ]
    )
    get_route = respx.get(f"{api_base}/v1/vaults/{vid}/secrets/x").mock(
        return_value=httpx.Response(200, json={"value": "ok"}),
    )

    client = OneclawClient(
        agent_id=aid,
        api_key="ocv_testkey",
        vault_id=vid,
        base_url=api_base,
    )
    try:
        with freeze_time("2024-06-01T12:00:00Z") as frozen:
            assert client.get_secret("x") == "ok"
            frozen.tick(delta=timedelta(seconds=71))
            assert client.get_secret("x") == "ok"
        assert auth.call_count == 2
        assert get_route.call_count == 2
    finally:
        client.close()
