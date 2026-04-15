# 1claw-crewai-tools

[![PyPI version](https://img.shields.io/pypi/v/1claw-crewai-tools.svg)](https://pypi.org/project/1claw-crewai-tools/)
[![Python versions](https://img.shields.io/pypi/pyversions/1claw-crewai-tools.svg)](https://pypi.org/project/1claw-crewai-tools/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/1ClawAI/1claw-crewai-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/1ClawAI/1claw-crewai-tools/actions/workflows/ci.yml)

**Secure secret fetching for CrewAI agents via [1Claw](https://1claw.xyz) HSM-backed vaults.**

Credentials are retrieved at **runtime** from your vault using a **scoped agent identity**—not copied into prompts, repos, or long-lived agent memory. Do not log tool return values.

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

## Documentation

- **[Quickstart](docs/quickstart.md)** — prerequisites, env vars, paths, security, troubleshooting
- **[1Claw docs](https://docs.1claw.xyz)** — vaults, agents, policies

## Security

- Tool output can contain **plaintext credentials**. Never `print()` or log the return value of `_run` / tool execution.
- `OneclawVaultTool` sets CrewAI’s **`cache_function`** to a callable that **always returns `False`** so credential reads are **not** cached by the framework (CrewAI’s field is a callable, not a bool).

## Repository

Source: [github.com/1ClawAI/1claw-crewai-tools](https://github.com/1ClawAI/1claw-crewai-tools)

## License

MIT — see [LICENSE](LICENSE).
