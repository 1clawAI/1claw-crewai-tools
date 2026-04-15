"""CrewAI BaseTool that reads secrets from a 1Claw vault."""

from __future__ import annotations

from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from ._client import OneclawClient, OneclawError


def _never_cache_vault_tool(_args: Any = None, _result: Any = None) -> bool:
    """Return False so CrewAI does not cache tool output (credentials may rotate)."""
    return False


class OneclawVaultInput(BaseModel):
    """Input schema for :class:`OneclawVaultTool`."""

    path: str = Field(
        ...,
        description=(
            "The secret path in the 1claw vault, e.g. 'api-keys/stripe' or "
            "'db/postgres-url'. Use the exact path the vault owner configured."
        ),
    )


class OneclawVaultTool(BaseTool):
    """Tool that fetches a secret value from a 1Claw vault by path."""

    name: str = "1claw Vault"
    description: str = (
        "Fetch a secret from a 1claw HSM-backed vault by its path. "
        "Use this tool whenever you need an API key, token, connection string, "
        "or other credential. Never ask the user to paste credentials — "
        "fetch them from the vault instead. "
        "Input: the secret path (e.g. 'api-keys/openai')."
    )
    args_schema: type[BaseModel] = OneclawVaultInput
    # CrewAI uses a callable here (not a bool); must always return False.
    cache_function: Any = _never_cache_vault_tool

    _client: OneclawClient | None = None

    def __init__(
        self,
        *,
        agent_id: str,
        api_key: str,
        vault_id: str,
        base_url: str = "https://api.1claw.xyz",
        **kwargs: Any,
    ) -> None:
        """Build a vault tool for the given agent and vault.

        Args:
            agent_id: 1Claw agent id (UUID).
            api_key: Agent API key (``ocv_`` prefix).
            vault_id: Vault id (UUID) the agent may access per policy.
            base_url: Vault API base URL.
            **kwargs: Forwarded to :class:`crewai.tools.BaseTool`.
        """
        super().__init__(**kwargs)
        object.__setattr__(
            self,
            "_client",
            OneclawClient(
                agent_id=agent_id,
                api_key=api_key,
                vault_id=vault_id,
                base_url=base_url,
            ),
        )

    def _run(self, path: str) -> str:
        """Fetch the secret at ``path``; returns error string on failure (does not raise)."""
        assert self._client is not None
        try:
            return self._client.get_secret(path)
        except OneclawError as exc:
            return f"[1claw error] {exc}"
