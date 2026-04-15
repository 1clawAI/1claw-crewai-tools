"""HTTP client for the 1Claw Vault REST API (agent authentication)."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import httpx


class OneclawError(Exception):
    """Base error for 1Claw API failures."""

    pass


class OneclawAuthError(OneclawError):
    """Raised when authentication or authorization fails (401/403)."""

    pass


class OneclawSecretNotFoundError(OneclawError):
    """Raised when the requested secret path does not exist (404)."""

    pass


class OneclawClient:
    """Synchronous httpx client with JWT caching for agent API access."""

    def __init__(
        self,
        agent_id: str,
        api_key: str,
        vault_id: str,
        base_url: str = "https://api.1claw.xyz",
    ) -> None:
        """Create a client for the given agent credentials and vault.

        Args:
            agent_id: 1Claw agent UUID string.
            api_key: Agent API key (``ocv_`` prefix).
            vault_id: Target vault UUID string.
            base_url: Vault API base URL (no trailing slash).
        """
        self._agent_id = agent_id
        self._api_key = api_key
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

    def _ensure_token(self) -> None:
        """Obtain or refresh the bearer token if missing or near expiry."""
        now = time.time()
        if (
            self._access_token is not None
            and self._token_expires_at is not None
            and now < self._token_expires_at - 30
        ):
            return

        url = f"{self._base_url}/v1/auth/agent-token"
        resp = self._http.post(
            url,
            json={"agent_id": self._agent_id, "api_key": self._api_key},
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

    def get_secret(self, path: str) -> str:
        """GET a decrypted secret value by vault path.

        Args:
            path: Secret path (e.g. ``api-keys/stripe``).

        Returns:
            The decrypted secret value string.

        Raises:
            OneclawAuthError: On 401 or 403.
            OneclawSecretNotFoundError: On 404.
            OneclawError: On other non-success responses or malformed JSON.
        """
        self._ensure_token()
        assert self._access_token is not None

        encoded = quote(path.lstrip("/"), safe="")
        url = f"{self._base_url}/v1/vaults/{self._vault_id}/secrets/{encoded}"
        resp = self._http.get(
            url,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )

        if resp.status_code in (401, 403):
            raise OneclawAuthError(f"Secret request unauthorized: HTTP {resp.status_code}")
        if resp.status_code == 404:
            raise OneclawSecretNotFoundError(f"Secret not found at path: {path}")
        if not resp.is_success:
            raise OneclawError(f"Secret request failed: HTTP {resp.status_code}")

        body: dict[str, Any] = resp.json()
        value = body.get("value")
        if not isinstance(value, str):
            raise OneclawError("Secret response missing string value")
        # SECRET: do not log — value is sensitive; never print or log this string.
        return value
