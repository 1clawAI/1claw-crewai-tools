#!/usr/bin/env python3
"""Live integration test for OneclawVaultTool with a real CrewAI agent.

Run:
    # Set credentials first (or source a .env):
    export ONECLAW_AGENT_ID="..."
    export ONECLAW_AGENT_API_KEY="ocv_..."
    export ONECLAW_VAULT_ID="..."
    export OPENAI_API_KEY="..."   # or GOOGLE_API_KEY for Gemini

    python examples/test_live.py [secret-path]

If no secret-path is given, defaults to "test/crewai-live".

The script runs three phases:
  1. Raw client auth + secret fetch (no CrewAI) — validates credentials.
  2. Single-agent crew that calls the vault tool.
  3. Two-agent crew where agent 1 fetches a secret and agent 2 summarizes a fact.
"""

from __future__ import annotations

import os
import sys
import time


def _env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        print(f"MISSING: {name}", file=sys.stderr)
        sys.exit(1)
    return v


def _check_llm_key() -> str:
    """Return a label for which LLM provider is configured."""
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("GOOGLE_API_KEY"):
        return "google (gemini)"
    print(
        "No LLM key found. Set OPENAI_API_KEY or GOOGLE_API_KEY.",
        file=sys.stderr,
    )
    sys.exit(1)


def phase1_raw_client(agent_id: str, api_key: str, vault_id: str, path: str) -> None:
    """Phase 1: validate auth + secret fetch without CrewAI."""
    from oneclaw_crewai._client import OneclawClient

    print("\n--- Phase 1: Raw client (no CrewAI) ---")
    client = OneclawClient(agent_id=agent_id, api_key=api_key, vault_id=vault_id)
    try:
        t0 = time.time()
        val = client.get_secret(path)
        elapsed = time.time() - t0
        # SECRET: do not log val — only confirm it's non-empty
        assert isinstance(val, str) and len(val) > 0, "Expected non-empty secret value"
        print(f"  Auth + fetch OK ({elapsed:.2f}s). Secret length: {len(val)} chars.")
    finally:
        client.close()


def phase2_single_agent(agent_id: str, api_key: str, vault_id: str, path: str) -> None:
    """Phase 2: one agent with OneclawVaultTool fetches the secret."""
    from crewai import Agent, Crew, Process, Task

    from oneclaw_crewai import OneclawVaultTool

    print("\n--- Phase 2: Single-agent crew ---")
    tool = OneclawVaultTool(agent_id=agent_id, api_key=api_key, vault_id=vault_id)

    agent = Agent(
        role="Secret fetcher",
        goal="Fetch a secret from the vault and confirm success without exposing the value.",
        backstory="You use the oneclaw_vault tool. Never paste secret content into your response.",
        tools=[tool],
        verbose=True,
    )

    task = Task(
        description=(
            f"Use the 'oneclaw_vault' tool with path '{path}'. "
            "Report ONLY whether the fetch succeeded and the character length of the value. "
            "Do NOT include any part of the secret in your response."
        ),
        expected_output="One sentence: success/failure + character count.",
        agent=agent,
    )

    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
    result = crew.kickoff()
    print(f"\n  Crew result: {result}")


def phase3_two_agents(agent_id: str, api_key: str, vault_id: str, path: str) -> None:
    """Phase 3: two agents — fetcher + summarizer."""
    from crewai import Agent, Crew, Process, Task

    from oneclaw_crewai import OneclawVaultTool

    print("\n--- Phase 3: Two-agent crew ---")
    tool = OneclawVaultTool(agent_id=agent_id, api_key=api_key, vault_id=vault_id)

    fetcher = Agent(
        role="Credential coordinator",
        goal="Fetch the secret and confirm it worked, without leaking the value.",
        backstory="You call the vault tool and report generic success/failure only.",
        tools=[tool],
        verbose=True,
    )

    writer = Agent(
        role="Technical writer",
        goal="Explain a security concept in one sentence.",
        backstory="You summarize facts. You never handle credentials.",
        tools=[],
        verbose=True,
    )

    task_fetch = Task(
        description=(
            f"Fetch the secret at path '{path}' using the 'oneclaw_vault' tool. "
            "Report success/failure and character count only."
        ),
        expected_output="One line: success or failure.",
        agent=fetcher,
    )

    task_write = Task(
        description="Write one sentence explaining what envelope encryption means.",
        expected_output="One sentence.",
        agent=writer,
    )

    crew = Crew(
        agents=[fetcher, writer],
        tasks=[task_fetch, task_write],
        process=Process.sequential,
        verbose=True,
    )
    result = crew.kickoff()
    print(f"\n  Crew result: {result}")


def main() -> None:
    agent_id = _env("ONECLAW_AGENT_ID")
    api_key = _env("ONECLAW_AGENT_API_KEY")
    vault_id = _env("ONECLAW_VAULT_ID")
    llm = _check_llm_key()

    path = sys.argv[1] if len(sys.argv) > 1 else "test/crewai-live"

    print(f"Agent:  {agent_id}")
    print(f"Vault:  {vault_id}")
    print(f"Path:   {path}")
    print(f"LLM:    {llm}")

    phase1_raw_client(agent_id, api_key, vault_id, path)
    phase2_single_agent(agent_id, api_key, vault_id, path)
    phase3_two_agents(agent_id, api_key, vault_id, path)

    print("\n=== All phases complete ===")


if __name__ == "__main__":
    main()
