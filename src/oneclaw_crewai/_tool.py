"""CrewAI tools for 1Claw — secrets, signing, memory, and automations.

Each tool wraps a 1Claw API endpoint via :class:`OneclawClient`.
"""

from __future__ import annotations

import json
from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from ._client import OneclawClient, OneclawError


def _never_cache(_args: Any = None, _result: Any = None) -> bool:
    """Return False so CrewAI does not cache tool output (credentials may rotate)."""
    return False


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------


class OneclawVaultInput(BaseModel):
    path: str = Field(..., description="Secret path in the vault, e.g. 'api-keys/openai'")


class OneclawVaultTool(BaseTool):
    """Fetch a decrypted secret from an HSM-backed 1Claw vault.

    Backward-compatible constructor: accepts ``agent_id``, ``api_key``,
    ``vault_id`` directly. For new code, prefer passing a shared
    ``OneclawClient`` via ``get_all_tools()``.
    """

    name: str = "oneclaw_vault"
    description: str = (
        "Fetch a secret from the 1Claw HSM-backed vault by its path. "
        "Use this tool whenever you need an API key, token, connection string, "
        "or other credential. Never ask the user to paste credentials — "
        "fetch them from the vault instead. "
        "Input: the secret path (e.g. 'api-keys/openai')."
    )
    args_schema: type[BaseModel] = OneclawVaultInput
    cache_function: Any = _never_cache

    _client: OneclawClient | None = None

    def __init__(
        self,
        *,
        client: OneclawClient | None = None,
        agent_id: str | None = None,
        api_key: str | None = None,
        vault_id: str | None = None,
        base_url: str = "https://api.1claw.xyz",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if client is not None:
            object.__setattr__(self, "_client", client)
        elif api_key is not None:
            object.__setattr__(
                self,
                "_client",
                OneclawClient(
                    api_key=api_key, agent_id=agent_id,
                    vault_id=vault_id, base_url=base_url,
                ),
            )
        else:
            raise ValueError("Either 'client' or 'api_key' is required")

    def _run(self, path: str) -> str:
        assert self._client is not None
        try:
            return self._client.get_secret(path)
        except OneclawError as exc:
            return f"[1claw error] {exc}"


class _PutSecretInput(BaseModel):
    path: str = Field(..., description="Secret path, e.g. 'api-keys/new-key'")
    value: str = Field(..., description="The secret value to store")


class OneclawPutSecretTool(BaseTool):
    """Store or update a secret in the 1Claw vault."""

    name: str = "oneclaw_put_secret"
    description: str = (
        "Store or update a secret in the 1Claw vault. Creates a new version "
        "if the path exists. Use this to securely persist credentials."
    )
    args_schema: type[BaseModel] = _PutSecretInput
    cache_function: Any = _never_cache
    _client: OneclawClient | None = None

    def __init__(self, *, client: OneclawClient, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_client", client)

    def _run(self, path: str, value: str) -> str:
        assert self._client is not None
        try:
            result = self._client.put_secret(path, value)
            return json.dumps(result)
        except OneclawError as e:
            return f"[1claw error] {e}"


class _ListSecretsInput(BaseModel):
    prefix: str | None = Field(None, description="Filter secrets by path prefix")


class OneclawListSecretsTool(BaseTool):
    """List available secrets in the 1Claw vault."""

    name: str = "oneclaw_list_secrets"
    description: str = (
        "List secrets stored in the 1Claw vault. Returns paths and metadata "
        "(not values). Optionally filter by prefix."
    )
    args_schema: type[BaseModel] = _ListSecretsInput
    cache_function: Any = _never_cache
    _client: OneclawClient | None = None

    def __init__(self, *, client: OneclawClient, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_client", client)

    def _run(self, prefix: str | None = None) -> str:
        assert self._client is not None
        try:
            return json.dumps(self._client.list_secrets(prefix=prefix))
        except OneclawError as e:
            return f"[1claw error] {e}"


class _RotateSecretInput(BaseModel):
    path: str = Field(..., description="Secret path to rotate")
    length: int = Field(32, description="Generated value length (8-1024)")
    charset: str = Field("base64", description="Charset: hex, base64, alphanumeric, ascii")


class OneclawRotateSecretTool(BaseTool):
    """Rotate a secret with a server-generated cryptographic value."""

    name: str = "oneclaw_rotate_secret"
    description: str = (
        "Rotate a secret at the given path. The server generates a new "
        "cryptographically random value. Old versions are preserved."
    )
    args_schema: type[BaseModel] = _RotateSecretInput
    cache_function: Any = _never_cache
    _client: OneclawClient | None = None

    def __init__(self, *, client: OneclawClient, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_client", client)

    def _run(self, path: str, length: int = 32, charset: str = "base64") -> str:
        assert self._client is not None
        try:
            return json.dumps(self._client.rotate_secret(path, length=length, charset=charset))
        except OneclawError as e:
            return f"[1claw error] {e}"


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


class _MemoryPutInput(BaseModel):
    namespace: str = Field("default", description="Memory namespace")
    key: str = Field(..., description="Memory entry key")
    value: str = Field(..., description="Value to store")
    tier: str = Field("durable", description="Storage tier: 'durable' or 'scratch'")


class OneclawMemoryPutTool(BaseTool):
    """Store a value in the agent's encrypted memory."""

    name: str = "oneclaw_memory_put"
    description: str = (
        "Store a value in the agent's HSM-encrypted persistent memory. "
        "Use 'durable' tier for long-term, 'scratch' for ephemeral."
    )
    args_schema: type[BaseModel] = _MemoryPutInput
    cache_function: Any = _never_cache
    _client: OneclawClient | None = None

    def __init__(self, *, client: OneclawClient, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_client", client)

    def _run(self, key: str, value: str, namespace: str = "default", tier: str = "durable") -> str:
        assert self._client is not None
        try:
            self._client.memory_put(namespace, key, value, tier=tier)
            return f"Stored '{key}' in namespace '{namespace}'"
        except OneclawError as e:
            return f"[1claw error] {e}"


class _MemoryGetInput(BaseModel):
    namespace: str = Field("default", description="Memory namespace")
    key: str = Field(..., description="Memory entry key")


class OneclawMemoryGetTool(BaseTool):
    """Retrieve a value from the agent's encrypted memory."""

    name: str = "oneclaw_memory_get"
    description: str = (
        "Retrieve a previously stored value from the agent's memory by key."
    )
    args_schema: type[BaseModel] = _MemoryGetInput
    cache_function: Any = _never_cache
    _client: OneclawClient | None = None

    def __init__(self, *, client: OneclawClient, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_client", client)

    def _run(self, key: str, namespace: str = "default") -> str:
        assert self._client is not None
        try:
            val = self._client.memory_get(namespace, key)
            if val is None:
                return f"Memory entry '{key}' not found in namespace '{namespace}'"
            return val
        except OneclawError as e:
            return f"[1claw error] {e}"


class _MemorySearchInput(BaseModel):
    namespace: str = Field("default", description="Memory namespace to search")
    query: str = Field(..., description="Natural language search query")
    top_k: int = Field(5, description="Number of results (1-50)")


class OneclawMemorySearchTool(BaseTool):
    """Semantic search over the agent's memory entries."""

    name: str = "oneclaw_memory_search"
    description: str = (
        "Search the agent's memory using natural language. Returns the most "
        "relevant stored entries ranked by similarity."
    )
    args_schema: type[BaseModel] = _MemorySearchInput
    cache_function: Any = _never_cache
    _client: OneclawClient | None = None

    def __init__(self, *, client: OneclawClient, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_client", client)

    def _run(self, query: str, namespace: str = "default", top_k: int = 5) -> str:
        assert self._client is not None
        try:
            return json.dumps(self._client.memory_search(namespace, query, top_k=top_k))
        except OneclawError as e:
            return f"[1claw error] {e}"


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------


class _SignMessageInput(BaseModel):
    message: str = Field(..., description="Message to sign (hex or plain text)")
    chain: str = Field("ethereum", description="Chain for signing key resolution")


class OneclawSignMessageTool(BaseTool):
    """Sign a message with the agent's blockchain key (EIP-191)."""

    name: str = "oneclaw_sign_message"
    description: str = (
        "Sign a message using the agent's blockchain signing key (EIP-191). "
        "Returns signature, message hash, and signer address. "
        "The private key never leaves the HSM."
    )
    args_schema: type[BaseModel] = _SignMessageInput
    cache_function: Any = _never_cache
    _client: OneclawClient | None = None

    def __init__(self, *, client: OneclawClient, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_client", client)

    def _run(self, message: str, chain: str = "ethereum") -> str:
        assert self._client is not None
        try:
            return json.dumps(self._client.sign_message(message, chain=chain))
        except OneclawError as e:
            return f"[1claw error] {e}"


class _SubmitTransactionInput(BaseModel):
    chain: str = Field(..., description="Blockchain (ethereum, base, solana, bitcoin, etc.)")
    to: str = Field(..., description="Recipient address")
    value: str = Field("0", description="Amount in native units (ETH, SOL, BTC, etc.)")
    data: str | None = Field(None, description="Hex-encoded calldata (EVM only)")
    token_mint: str | None = Field(None, description="Token contract for token transfers")
    simulate_first: bool = Field(False, description="Tenderly simulation before signing")


class OneclawSubmitTransactionTool(BaseTool):
    """Sign and broadcast a blockchain transaction."""

    name: str = "oneclaw_submit_transaction"
    description: str = (
        "Sign and broadcast a blockchain transaction using the agent's signing key. "
        "Supports EVM chains, Bitcoin, Solana, XRP, Cardano, and Tron. "
        "Transaction guardrails are enforced server-side."
    )
    args_schema: type[BaseModel] = _SubmitTransactionInput
    cache_function: Any = _never_cache
    _client: OneclawClient | None = None

    def __init__(self, *, client: OneclawClient, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_client", client)

    def _run(
        self,
        chain: str,
        to: str,
        value: str = "0",
        data: str | None = None,
        token_mint: str | None = None,
        simulate_first: bool = False,
    ) -> str:
        assert self._client is not None
        try:
            return json.dumps(
                self._client.submit_transaction(
                    chain=chain, to=to, value=value, data_hex=data,
                    token_mint=token_mint, simulate_first=simulate_first,
                )
            )
        except OneclawError as e:
            return f"[1claw error] {e}"


class _GetBalanceInput(BaseModel):
    chain: str = Field(..., description="Blockchain (ethereum, solana, bitcoin, etc.)")
    tokens: str | None = Field(None, description="Comma-separated token contract addresses")


class OneclawGetBalanceTool(BaseTool):
    """Check the agent's signing key balance on a blockchain."""

    name: str = "oneclaw_get_balance"
    description: str = (
        "Get native + token balances for the agent's signing key on a chain. "
        "Use before submitting a transaction to check available funds."
    )
    args_schema: type[BaseModel] = _GetBalanceInput
    cache_function: Any = _never_cache
    _client: OneclawClient | None = None

    def __init__(self, *, client: OneclawClient, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_client", client)

    def _run(self, chain: str, tokens: str | None = None) -> str:
        assert self._client is not None
        try:
            return json.dumps(self._client.get_signing_key_balance(chain, tokens=tokens))
        except OneclawError as e:
            return f"[1claw error] {e}"


# ---------------------------------------------------------------------------
# Environment Variables
# ---------------------------------------------------------------------------


class _ResolveEnvInput(BaseModel):
    environment: str | None = Field(None, description="Environment name (production, preview, development)")
    git_branch: str | None = Field(None, description="Git branch for branch-specific overrides")


class OneclawResolveEnvTool(BaseTool):
    """Resolve environment variables for a vault with precedence rules."""

    name: str = "oneclaw_resolve_env"
    description: str = (
        "Resolve environment variables for the vault with Vercel-style precedence: "
        "org shared vars < vault vars < branch-specific overrides. Returns the final "
        "merged key-value map and sources. Use this to get the runtime config for a "
        "specific environment and branch."
    )
    args_schema: type[BaseModel] = _ResolveEnvInput
    cache_function: Any = _never_cache
    _client: OneclawClient | None = None

    def __init__(self, *, client: OneclawClient, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_client", client)

    def _run(self, environment: str | None = None, git_branch: str | None = None) -> str:
        assert self._client is not None
        try:
            return json.dumps(
                self._client.resolve_env_vars(environment=environment, git_branch=git_branch)
            )
        except OneclawError as e:
            return f"[1claw error] {e}"


class _ListEnvVarsInput(BaseModel):
    environment: str | None = Field(None, description="Filter by environment name")


class OneclawListEnvVarsTool(BaseTool):
    """List environment variables defined on a vault."""

    name: str = "oneclaw_list_env_vars"
    description: str = (
        "List environment variables defined on the vault. Returns keys, environments, "
        "and metadata (sensitive vars have values omitted). Optionally filter by "
        "environment name."
    )
    args_schema: type[BaseModel] = _ListEnvVarsInput
    cache_function: Any = _never_cache
    _client: OneclawClient | None = None

    def __init__(self, *, client: OneclawClient, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_client", client)

    def _run(self, environment: str | None = None) -> str:
        assert self._client is not None
        try:
            return json.dumps(self._client.list_env_vars(environment=environment))
        except OneclawError as e:
            return f"[1claw error] {e}"


# ---------------------------------------------------------------------------
# Automations
# ---------------------------------------------------------------------------


class _TriggerAutomationInput(BaseModel):
    automation_id: str = Field(..., description="UUID of the automation to trigger")
    context: str | None = Field(None, description="JSON context data")


class OneclawTriggerAutomationTool(BaseTool):
    """Trigger a 1Claw automation workflow."""

    name: str = "oneclaw_trigger_automation"
    description: str = (
        "Trigger a pre-configured 1Claw automation workflow. "
        "Automations can rotate secrets, send notifications, make API calls, "
        "or run AI-powered workflows."
    )
    args_schema: type[BaseModel] = _TriggerAutomationInput
    cache_function: Any = _never_cache
    _client: OneclawClient | None = None

    def __init__(self, *, client: OneclawClient, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_client", client)

    def _run(self, automation_id: str, context: str | None = None) -> str:
        assert self._client is not None
        try:
            ctx = json.loads(context) if context else None
            return json.dumps(self._client.trigger_automation(automation_id, context=ctx))
        except (json.JSONDecodeError, OneclawError) as e:
            return f"[1claw error] {e}"


# ---------------------------------------------------------------------------
# Toolkit factory
# ---------------------------------------------------------------------------


def get_all_tools(client: OneclawClient) -> list[BaseTool]:
    """Return all 1Claw tools initialized with the given client.

    Example::

        from oneclaw_crewai import OneclawClient, get_all_tools

        client = OneclawClient(api_key="ocv_...")
        tools = get_all_tools(client)
        agent = Agent(role="...", tools=tools)
    """
    return [
        OneclawVaultTool(client=client),
        OneclawPutSecretTool(client=client),
        OneclawListSecretsTool(client=client),
        OneclawRotateSecretTool(client=client),
        OneclawResolveEnvTool(client=client),
        OneclawListEnvVarsTool(client=client),
        OneclawMemoryPutTool(client=client),
        OneclawMemoryGetTool(client=client),
        OneclawMemorySearchTool(client=client),
        OneclawSignMessageTool(client=client),
        OneclawSubmitTransactionTool(client=client),
        OneclawGetBalanceTool(client=client),
        OneclawTriggerAutomationTool(client=client),
    ]
