"""HTTP client for the 1Claw Vault REST API (agent authentication).

Covers secrets, memory, signing, and automation endpoints with
automatic JWT caching and refresh.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import httpx


class OneclawError(Exception):
    """Base error for 1Claw API failures."""


class OneclawAuthError(OneclawError):
    """Raised when authentication or authorization fails (401/403)."""


class OneclawSecretNotFoundError(OneclawError):
    """Raised when the requested secret path does not exist (404)."""


class OneclawValidationError(OneclawError):
    """Request validation failure (400/422)."""


class OneclawClient:
    """Synchronous httpx client with JWT caching for agent API access.

    Supports key-only auth (``agent_id`` and ``vault_id`` auto-resolved
    from token exchange) and explicit IDs for backward compatibility.
    """

    def __init__(
        self,
        *,
        api_key: str,
        agent_id: str | None = None,
        vault_id: str | None = None,
        base_url: str = "https://api.1claw.co",
    ) -> None:
        self._api_key = api_key
        self._agent_id = agent_id
        self._vault_id = vault_id
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(timeout=30.0)
        self._access_token: str | None = None
        self._token_expires_at: float | None = None

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()

    def __enter__(self) -> OneclawClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def agent_id(self) -> str:
        if self._agent_id is None:
            self._ensure_token()
        assert self._agent_id is not None
        return self._agent_id

    @property
    def vault_id(self) -> str:
        if self._vault_id is None:
            self._ensure_token()
        if self._vault_id is None:
            raise OneclawError(
                "No vault_id available. Pass vault_id explicitly or ensure the agent "
                "has vault_ids configured."
            )
        return self._vault_id

    def _ensure_token(self) -> None:
        """Obtain or refresh the bearer token if missing or near expiry."""
        now = time.time()
        if (
            self._access_token is not None
            and self._token_expires_at is not None
            and now < self._token_expires_at - 60
        ):
            return

        body: dict[str, str] = {"api_key": self._api_key}
        if self._agent_id:
            body["agent_id"] = self._agent_id

        resp = self._http.post(
            f"{self._base_url}/v1/auth/agent-token",
            json=body,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code in (401, 403):
            raise OneclawAuthError(f"Authentication failed: HTTP {resp.status_code}")
        if not resp.is_success:
            raise OneclawError(f"Token request failed: HTTP {resp.status_code}")

        data: dict[str, Any] = resp.json()
        token = data.get("access_token")
        if not isinstance(token, str) or not token:
            raise OneclawError("Token response missing access_token")
        expires_in = data.get("expires_in", 300)
        if not isinstance(expires_in, (int, float)):
            expires_in = 300

        self._access_token = token
        self._token_expires_at = now + float(expires_in)

        if self._agent_id is None:
            resolved = data.get("agent_id")
            if isinstance(resolved, str) and resolved:
                self._agent_id = resolved

        if self._vault_id is None:
            vault_ids = data.get("vault_ids")
            if isinstance(vault_ids, list) and vault_ids:
                self._vault_id = str(vault_ids[0])

    def _headers(self) -> dict[str, str]:
        self._ensure_token()
        assert self._access_token is not None
        return {"Authorization": f"Bearer {self._access_token}"}

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resp = self._http.request(
            method,
            f"{self._base_url}{path}",
            headers=self._headers(),
            json=json,
            params=params,
        )
        if resp.status_code in (401, 403):
            raise OneclawAuthError(f"HTTP {resp.status_code}: {resp.text}")
        if resp.status_code == 404:
            raise OneclawSecretNotFoundError(f"Not found: {path}")
        if resp.status_code in (400, 422):
            raise OneclawValidationError(f"Validation error: {resp.text}")
        if not resp.is_success:
            raise OneclawError(f"HTTP {resp.status_code}: {resp.text}")
        if resp.status_code == 204:
            return {}
        return resp.json()  # type: ignore[no-any-return]

    # --- secrets ---

    def get_secret(self, path: str, *, vault_id: str | None = None) -> str:
        """Fetch a decrypted secret value by path."""
        vid = vault_id or self.vault_id
        encoded = quote(path.lstrip("/"), safe="")
        data = self._request("GET", f"/v1/vaults/{vid}/secrets/{encoded}")
        value = data.get("value")
        if not isinstance(value, str):
            raise OneclawError("Secret response missing string value")
        return value

    def put_secret(
        self,
        path: str,
        value: str,
        *,
        vault_id: str | None = None,
        secret_type: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create or update a secret."""
        vid = vault_id or self.vault_id
        encoded = quote(path.lstrip("/"), safe="")
        body: dict[str, Any] = {"value": value}
        if secret_type:
            body["type"] = secret_type
        if description:
            body["description"] = description
        return self._request("PUT", f"/v1/vaults/{vid}/secrets/{encoded}", json=body)

    def list_secrets(
        self, *, vault_id: str | None = None, prefix: str | None = None
    ) -> list[dict[str, Any]]:
        """List secrets in a vault, optionally filtered by prefix."""
        vid = vault_id or self.vault_id
        params: dict[str, Any] = {}
        if prefix:
            params["prefix"] = prefix
        data = self._request("GET", f"/v1/vaults/{vid}/secrets", params=params or None)
        return data.get("secrets", [])  # type: ignore[no-any-return]

    def delete_secret(self, path: str, *, vault_id: str | None = None) -> dict[str, Any]:
        """Delete a secret by path."""
        vid = vault_id or self.vault_id
        encoded = quote(path.lstrip("/"), safe="")
        return self._request("DELETE", f"/v1/vaults/{vid}/secrets/{encoded}")

    def rotate_secret(
        self,
        path: str,
        *,
        vault_id: str | None = None,
        length: int = 32,
        charset: str = "base64",
    ) -> dict[str, Any]:
        """Server-side secret rotation with generated value."""
        vid = vault_id or self.vault_id
        encoded = quote(path.lstrip("/"), safe="")
        return self._request(
            "POST",
            f"/v1/vaults/{vid}/secret-rotate/{encoded}",
            json={"length": length, "charset": charset},
        )

    # --- memory ---

    def memory_put(
        self,
        namespace: str,
        key: str,
        value: str,
        *,
        tier: str = "durable",
        ttl_secs: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"value": value, "tier": tier}
        if ttl_secs is not None:
            body["ttl_secs"] = ttl_secs
        return self._request(
            "PUT", f"/v1/agents/{self.agent_id}/memory/{quote(namespace)}/{quote(key)}", json=body
        )

    def memory_get(self, namespace: str, key: str) -> str | None:
        try:
            data = self._request(
                "GET", f"/v1/agents/{self.agent_id}/memory/{quote(namespace)}/{quote(key)}"
            )
            return data.get("value")  # type: ignore[return-value]
        except OneclawSecretNotFoundError:
            return None

    def memory_search(self, namespace: str, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
        data = self._request(
            "POST",
            f"/v1/agents/{self.agent_id}/memory/search",
            json={"namespace": namespace, "query": query, "top_k": top_k},
        )
        return data.get("results", [])  # type: ignore[no-any-return]

    # --- signing ---

    def sign_message(self, message: str, *, chain: str = "ethereum") -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/agents/{self.agent_id}/sign",
            json={"intent_type": "personal_sign", "message": message, "chain": chain},
        )

    def submit_transaction(
        self,
        *,
        chain: str,
        to: str,
        value: str = "0",
        data_hex: str | None = None,
        token_mint: str | None = None,
        simulate_first: bool = False,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"chain": chain, "to": to, "value": value}
        if data_hex:
            body["data"] = data_hex
        if token_mint:
            body["token_mint"] = token_mint
        if simulate_first:
            body["simulate_first"] = True
        return self._request("POST", f"/v1/agents/{self.agent_id}/transactions", json=body)

    def get_signing_key_balance(
        self, chain: str, *, tokens: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if tokens:
            params["tokens"] = tokens
        return self._request(
            "GET",
            f"/v1/agents/{self.agent_id}/signing-keys/{chain}/balance",
            params=params or None,
        )

    # --- env vars ---

    def list_env_vars(
        self,
        *,
        vault_id: str | None = None,
        environment: str | None = None,
    ) -> list[dict[str, Any]]:
        """List environment variables for a vault."""
        vid = vault_id or self.vault_id
        params: dict[str, Any] = {}
        if environment:
            params["environment"] = environment
        data = self._request("GET", f"/v1/vaults/{vid}/env-vars", params=params or None)
        return data.get("env_vars", [])  # type: ignore[no-any-return]

    def resolve_env_vars(
        self,
        *,
        vault_id: str | None = None,
        environment: str | None = None,
        git_branch: str | None = None,
    ) -> dict[str, Any]:
        """Resolve environment variables with precedence for a vault."""
        vid = vault_id or self.vault_id
        params: dict[str, Any] = {}
        if environment:
            params["environment"] = environment
        if git_branch:
            params["git_branch"] = git_branch
        return self._request("GET", f"/v1/vaults/{vid}/env-vars/resolve", params=params or None)

    # --- automations ---

    def trigger_automation(
        self, automation_id: str, *, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if context:
            body["context"] = context
        return self._request(
            "POST", f"/v1/automations/{automation_id}/trigger", json=body or None
        )
