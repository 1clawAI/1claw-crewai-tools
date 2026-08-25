# 1claw-crewai-tools

[![PyPI version](https://img.shields.io/pypi/v/1claw-crewai-tools.svg)](https://pypi.org/project/1claw-crewai-tools/)
[![Python versions](https://img.shields.io/pypi/pyversions/1claw-crewai-tools.svg)](https://pypi.org/project/1claw-crewai-tools/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/1ClawAI/1claw-crewai-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/1ClawAI/1claw-crewai-tools/actions/workflows/ci.yml)

CrewAI agents need credentials and signing keys, but crew configs are not a safe place to store them. Hard-coded API keys end up in git. Shared `.env` files break when you spin up parallel agents with different permissions.

`1claw-crewai-tools` wraps the [1Claw](https://1claw.xyz) API as CrewAI-compatible tools. Each tool fetches secrets at runtime, signs transactions server-side, and writes to encrypted agent memory. Access is policy-scoped: your agent only sees vault paths a human explicitly granted.

Drop in `get_all_tools(client)` and your crew gets 13 tools (vault, env vars, memory, signing, automations) with one `OneclawClient` initialized from `ONECLAW_AGENT_API_KEY`.

## Install

```bash
pip install 1claw-crewai-tools
```

> PyPI package: **`1claw-crewai-tools`** · Python import: **`oneclaw_crewai`**

## Quick Start

### All tools at once (recommended)

```python
import os
from crewai import Agent, Crew, Process, Task
from oneclaw_crewai import OneclawClient, get_all_tools

client = OneclawClient(
    api_key=os.environ["ONECLAW_AGENT_API_KEY"],
    # agent_id and vault_id are auto-resolved from the API key
)

tools = get_all_tools(client)  # 13 tools

researcher = Agent(
    role="Blockchain Researcher",
    goal="Check wallet balances and sign transactions",
    backstory="You use 1Claw tools for all credential and signing operations.",
    tools=tools,
)

task = Task(
    description="Check the Ethereum balance, then sign the message 'hello world'.",
    expected_output="Balance and signature details.",
    agent=researcher,
)

crew = Crew(agents=[researcher], tasks=[task], process=Process.sequential)
crew.kickoff()
```

### Single tool (backward-compatible)

```python
from oneclaw_crewai import OneclawVaultTool

vault_tool = OneclawVaultTool(
    agent_id=os.environ["ONECLAW_AGENT_ID"],
    api_key=os.environ["ONECLAW_AGENT_API_KEY"],
    vault_id=os.environ["ONECLAW_VAULT_ID"],
)

agent = Agent(
    role="Engineer",
    goal="Build features using vault-stored API keys",
    backstory="You use tools instead of pasted secrets.",
    tools=[vault_tool],
)
```

## Available Tools

| Tool | Name | Description |
|------|------|-------------|
| `OneclawVaultTool` | `oneclaw_vault` | Fetch a decrypted secret by path |
| `OneclawPutSecretTool` | `oneclaw_put_secret` | Store or update a secret |
| `OneclawListSecretsTool` | `oneclaw_list_secrets` | List secrets (paths, not values) |
| `OneclawRotateSecretTool` | `oneclaw_rotate_secret` | Server-side secret rotation |
| `OneclawResolveEnvTool` | `oneclaw_resolve_env` | Resolve vault env vars with precedence |
| `OneclawListEnvVarsTool` | `oneclaw_list_env_vars` | List env var keys for a vault/environment |
| `OneclawMemoryPutTool` | `oneclaw_memory_put` | Store a value in encrypted memory |
| `OneclawMemoryGetTool` | `oneclaw_memory_get` | Retrieve a value from memory |
| `OneclawMemorySearchTool` | `oneclaw_memory_search` | Semantic search over memory |
| `OneclawSignMessageTool` | `oneclaw_sign_message` | EIP-191 message signing |
| `OneclawSubmitTransactionTool` | `oneclaw_submit_transaction` | Sign and broadcast transactions |
| `OneclawGetBalanceTool` | `oneclaw_get_balance` | Check signing key balances |
| `OneclawTriggerAutomationTool` | `oneclaw_trigger_automation` | Trigger automation workflows |

## Multi-Agent Crew Example

```python
from crewai import Agent, Crew, Process, Task
from oneclaw_crewai import OneclawClient, get_all_tools

client = OneclawClient(api_key=os.environ["ONECLAW_AGENT_API_KEY"])
tools = get_all_tools(client)

# Agent 1: Manages secrets and credentials
secrets_agent = Agent(
    role="Secrets Manager",
    goal="Manage and rotate API credentials securely",
    backstory="You handle all credential lifecycle operations.",
    tools=tools,
)

# Agent 2: Handles blockchain operations
blockchain_agent = Agent(
    role="Blockchain Operator",
    goal="Execute blockchain transactions safely",
    backstory="You check balances and sign transactions using 1Claw.",
    tools=tools,
)

# Agent 3: Remembers context across sessions
memory_agent = Agent(
    role="Knowledge Manager",
    goal="Store and recall important information",
    backstory="You use encrypted memory for persistent knowledge.",
    tools=tools,
)

rotate_task = Task(
    description="Rotate the secret at 'api-keys/external-service'.",
    expected_output="Confirmation of rotation with new version number.",
    agent=secrets_agent,
)

balance_task = Task(
    description="Check the Ethereum signing key balance.",
    expected_output="Native balance in ETH.",
    agent=blockchain_agent,
)

remember_task = Task(
    description="Store today's rotation status in memory under key 'last-rotation'.",
    expected_output="Confirmation that the value was stored.",
    agent=memory_agent,
)

crew = Crew(
    agents=[secrets_agent, blockchain_agent, memory_agent],
    tasks=[rotate_task, balance_task, remember_task],
    process=Process.sequential,
)
crew.kickoff()
```

## Authentication

The `OneclawClient` supports two auth patterns:

**Key-only (recommended)** — agent ID and vault ID auto-resolved:
```python
client = OneclawClient(api_key="ocv_...")
```

**Explicit IDs** — for backward compatibility or multi-vault setups:
```python
client = OneclawClient(
    api_key="ocv_...",
    agent_id="<agent-uuid>",
    vault_id="<vault-uuid>",
)
```

## Platform v0.56+ (HITL, HFA, Safe, guardrail governance)

Tools call 1Claw API **v0.58+**. Server-side behavior (no Python package API changes):

- **Graduated HITL** — `OneclawSubmitTransactionTool` may receive `202 awaiting_approval` for human review.
- **Guardrail governance** — Agent execution and widening guardrail edits may require approval; configure via dashboard/CLI.
- **Safe foundation** — Counterfactual Safe accounts via Vault agent accounts API.
- **Multichain signing** — EVM, BTC, SOL, XRP, ADA, TRX unchanged; Vault uses `rust-bitcoin`, `solana-sdk` v4, `xrpl-rust` 1.1.0.

## Testing

### Unit tests (offline, no credentials needed)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
ruff check src tests
```

All network calls are mocked with `respx`; no 1Claw account required.

## Security

- Tool output can contain **plaintext credentials**. Never `print()` or log return values.
- All tools set `cache_function` to always return `False` — no framework-level caching.
- CrewAI's `verbose=True` prints tool output to stdout — use `verbose=False` in production.
- Private signing keys **never leave the HSM** — signing happens server-side.

## Links

- [1Claw Documentation](https://docs.1claw.xyz)
- [CrewAI Integration Guide](https://docs.1claw.xyz/docs/integrations/crewai)
- [Source Code](https://github.com/1ClawAI/1claw-crewai-tools)

## License

MIT — see [LICENSE](LICENSE).
