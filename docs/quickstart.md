# Quickstart: 1Claw + CrewAI

## 1. Prerequisites

1. A [1Claw](https://1claw.xyz) account and organization.
2. A **vault** that will hold your secrets (for example via the dashboard or CLI).
3. An **agent** registered in that org, with an **access policy** that grants **read** (and optionally write) on the paths your crew will use — for example `api-keys/*` if you store keys under `api-keys/...`.
4. The agent’s **`ocv_` API key** and **agent id**, and the **vault id** (UUIDs from the dashboard or CLI).

Without a matching policy, the Vault API returns **401/403** and the tool surfaces `[1claw error] ...`.

## 2. Installation

```bash
pip install 1claw-crewai-tools
```

For local development from a git checkout:

```bash
pip install -e ".[dev]"
```

## 3. Environment variables

| Variable | Description |
|----------|-------------|
| `ONECLAW_AGENT_ID` | Agent UUID (`agent_id` from 1Claw). |
| `ONECLAW_AGENT_API_KEY` | Agent API key starting with `ocv_`. |
| `ONECLAW_VAULT_ID` | Vault UUID the agent is allowed to use. |

Optional: point at a self-hosted or staging API (advanced):

- Pass `base_url=` when constructing `OneclawVaultTool` (default `https://api.1claw.xyz`).

CrewAI’s LLM (OpenAI, etc.) still needs its own keys — for example `OPENAI_API_KEY` if you use the default OpenAI-backed crew.

## 4. Minimal example

```python
import os
from crewai import Agent, Crew, Process, Task
from oneclaw_crewai import OneclawVaultTool

tool = OneclawVaultTool(
    agent_id=os.environ["ONECLAW_AGENT_ID"],
    api_key=os.environ["ONECLAW_AGENT_API_KEY"],
    vault_id=os.environ["ONECLAW_VAULT_ID"],
)

agent = Agent(
    role="Developer",
    goal="Use vault-backed credentials safely",
    backstory="You call the 1claw tool for secrets.",
    tools=[tool],
    verbose=True,
)

task = Task(
    description="Fetch the secret at path api-keys/openai using the vault tool.",
    expected_output="A short status line without pasting credential characters.",
    agent=agent,
)

crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
crew.kickoff()
```

## 5. How secret paths work

- Paths are **hierarchical strings** inside a vault, similar to file paths: e.g. `api-keys/stripe`, `db/postgres-url`, `prod/oauth/client-secret`.
- They must match what you configured in 1Claw and what your **policy** allows (glob patterns like `api-keys/**`).
- The tool sends the path to `GET /v1/vaults/{vault_id}/secrets/{path}` (with proper URL encoding); typos or missing secrets return **404**.

## 6. Security notes

- **Never log tool output** — it may contain full secret values.
- **Rotate and scope**: use narrow policies (least privilege), rotate `ocv_` keys and vault values from the dashboard or API when people or projects change.
- **CrewAI caching**: this package disables result caching for the vault tool so rotated values are not served from a stale cache; still avoid echoing secrets into task descriptions or final answers in untrusted logs.

## 7. Troubleshooting

| Symptom | What to check |
|---------|----------------|
| `[1claw error]` mentioning **401** / **403** | Agent policy does not allow this vault or path; JWT expired (client refreshes before calls — check clock skew); wrong `ONECLAW_AGENT_ID` / key. |
| **404** / not found | Path spelling; secret not created yet; wrong `ONECLAW_VAULT_ID`. |
| Connection errors | Network egress to `https://api.1claw.xyz` (or your `base_url`); TLS interception. |

For API details, see the [1Claw documentation](https://docs.1claw.xyz).
