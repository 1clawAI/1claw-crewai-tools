# 1claw-crewai-tools

[![PyPI version](https://img.shields.io/pypi/v/1claw-crewai-tools.svg)](https://pypi.org/project/1claw-crewai-tools/)
[![Python versions](https://img.shields.io/pypi/pyversions/1claw-crewai-tools.svg)](https://pypi.org/project/1claw-crewai-tools/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/1ClawAI/1claw-crewai-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/1ClawAI/1claw-crewai-tools/actions/workflows/ci.yml)

**Secure secret fetching for CrewAI agents via [1Claw](https://1claw.xyz) HSM-backed vaults.**

Credentials are retrieved at **runtime** from your vault using a **scoped agent identity** — not copied into prompts, repos, or long-lived agent memory. Do not log tool return values.

## Install

PyPI distribution name: **`1claw-crewai-tools`**. Python import package: **`oneclaw_crewai`**.

```bash
pip install 1claw-crewai-tools
```

## Usage

```python
import os
from crewai import Agent, Crew, Process, Task
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
    verbose=True,
)

task = Task(
    description="Read path api-keys/example using the vault tool; do not echo raw values in logs.",
    expected_output="Confirmation that the path was read.",
    agent=agent,
)

crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
crew.kickoff()
```

## Testing

### Unit tests (offline, no credentials needed)

```bash
# From the package root:
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -v                    # 10 tests — client + tool
ruff check src tests examples
mypy
```

All network calls are mocked with `respx`; no 1Claw account is required.

### Live integration test (requires 1Claw + LLM key)

`examples/test_live.py` runs three progressive phases against the real API:

| Phase | What it validates |
|-------|-------------------|
| 1 | Raw `OneclawClient` — agent token exchange + `get_secret` (no CrewAI) |
| 2 | Single-agent crew — CrewAI invokes `oneclaw_vault` tool, LLM reports result |
| 3 | Two-agent crew — fetcher reads secret, writer produces unrelated output |

**Prerequisites:**

1. A [1Claw](https://1claw.xyz) account with a vault containing at least one secret.
2. An agent registered in that org, bound to the vault (`vault_ids`), with a read policy on the secret path (e.g. `demo/**` or `**`).
3. An LLM API key — **OpenAI** (`OPENAI_API_KEY`) or **Google Gemini** (`GOOGLE_API_KEY`).

For Gemini, install the provider extra: `pip install "crewai[google-genai]"`.

**Run:**

```bash
export ONECLAW_AGENT_ID="<agent-uuid>"
export ONECLAW_AGENT_API_KEY="ocv_..."
export ONECLAW_VAULT_ID="<vault-uuid>"
export GOOGLE_API_KEY="..."   # or OPENAI_API_KEY

python examples/test_live.py demo/api-key
```

The script accepts an optional secret path argument (defaults to `test/crewai-live`).

**Example output (Phase 2):**

```
╭─── 🔧 Tool Execution Started (#1) ───╮
│  Tool: oneclaw_vault                  │
│  Args: {'path': 'demo/api-key'}      │
╰───────────────────────────────────────╯

╭─── ✅ Agent Final Answer ────╮
│  Fetch succeeded,            │
│  character length: 32.       │
╰──────────────────────────────╯
```

### Known issues and gotchas

| Issue | Details |
|-------|---------|
| **Tool name must be a valid identifier** | OpenAI (and other providers) require function names to start with a letter or underscore. The tool is named `oneclaw_vault` — not `1claw Vault` — for this reason. If you subclass and change `name`, keep it alphanumeric + underscores, starting with a letter. |
| **CrewAI verbose logging prints secret values** | When `verbose=True`, CrewAI's internal executor logs the raw return value of every tool call. This is a CrewAI framework behaviour, not this package. In production, set `verbose=False` or redirect stdout. |
| **Google Gemini requires an extra** | `pip install "crewai[google-genai]"` — without it, `LLM(model="gemini/...")` raises `ImportError`. |
| **`cache_function` must be a callable** | CrewAI's `BaseTool.cache_function` field is typed as `Callable[..., bool]`, not `bool`. This package sets it to a function that always returns `False`. If you override it, pass a callable, not a bare `False`. |

## Documentation

- **[Quickstart](docs/quickstart.md)** — prerequisites, env vars, paths, security, troubleshooting
- **[1Claw docs](https://docs.1claw.xyz)** — vaults, agents, policies

## Security

- Tool output can contain **plaintext credentials**. Never `print()` or log the return value of `_run` / tool execution.
- `OneclawVaultTool` sets CrewAI's **`cache_function`** to a callable that **always returns `False`** so credential reads are **not** cached by the framework.
- CrewAI's `verbose=True` prints tool output including secrets to stdout — use `verbose=False` in production.

## Repository

Source: [github.com/1ClawAI/1claw-crewai-tools](https://github.com/1ClawAI/1claw-crewai-tools)

## License

MIT — see [LICENSE](LICENSE).
