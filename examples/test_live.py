#!/usr/bin/env python3
"""Live integration test for 1claw-crewai-tools with real CrewAI agents.

Run:
    export ONECLAW_AGENT_API_KEY="ocv_..."
    export OPENAI_API_KEY="..."   # or GOOGLE_API_KEY for Gemini

    python examples/test_live.py [secret-path]

If no secret-path is given, defaults to "test/crewai-live".

Phases:
  1. Raw client — auth + secret fetch + memory round-trip (no CrewAI).
  2. Single-agent crew — vault tool fetch.
  3. Multi-tool crew — vault + memory + balance check.
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
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("GOOGLE_API_KEY"):
        return "google (gemini)"
    print("No LLM key. Set OPENAI_API_KEY or GOOGLE_API_KEY.", file=sys.stderr)
    sys.exit(1)


def phase1_raw_client(api_key: str, path: str) -> None:
    """Validate auth, secret fetch, and memory without CrewAI."""
    from oneclaw_crewai._client import OneclawClient

    print("\n--- Phase 1: Raw client (no CrewAI) ---")
    with OneclawClient(api_key=api_key) as client:
        t0 = time.time()
        val = client.get_secret(path)
        elapsed = time.time() - t0
        assert isinstance(val, str) and len(val) > 0
        print(f"  Secret fetch OK ({elapsed:.2f}s). Length: {len(val)} chars.")
        print(f"  Agent ID: {client.agent_id}")
        print(f"  Vault ID: {client.vault_id}")

        client.memory_put("test", "live-check", "crewai-live-test")
        recalled = client.memory_get("test", "live-check")
        assert recalled == "crewai-live-test"
        print("  Memory put+get OK.")


def phase2_single_agent(api_key: str, path: str) -> None:
    """One agent with OneclawVaultTool fetches the secret."""
    from crewai import Agent, Crew, Process, Task

    from oneclaw_crewai import OneclawClient, OneclawVaultTool

    print("\n--- Phase 2: Single-agent crew (vault tool) ---")
    client = OneclawClient(api_key=api_key)
    tool = OneclawVaultTool(client=client)

    agent = Agent(
        role="Secret fetcher",
        goal="Fetch a secret from the vault and confirm success.",
        backstory="Use the oneclaw_vault tool. Never paste secret content.",
        tools=[tool],
        verbose=True,
    )

    task = Task(
        description=(
            f"Use 'oneclaw_vault' with path '{path}'. "
            "Report success/failure and character count only."
        ),
        expected_output="One sentence: success + character count.",
        agent=agent,
    )

    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
    result = crew.kickoff()
    print(f"\n  Result: {result}")
    client.close()


def phase3_multi_tool(api_key: str, path: str) -> None:
    """Multi-tool agent: vault + memory + balance."""
    from crewai import Agent, Crew, Process, Task

    from oneclaw_crewai import OneclawClient, get_all_tools

    print("\n--- Phase 3: Multi-tool crew ---")
    client = OneclawClient(api_key=api_key)
    tools = get_all_tools(client)

    agent = Agent(
        role="Full-stack agent",
        goal="Demonstrate vault, memory, and blockchain tools.",
        backstory="Use 1Claw tools for all operations.",
        tools=tools,
        verbose=True,
    )

    task = Task(
        description=(
            f"1. Fetch the secret at path '{path}' (report length only).\n"
            "2. Store 'phase3-complete' in memory at key 'live-test-status'.\n"
            "3. Retrieve 'live-test-status' from memory and confirm it matches.\n"
            "Report all three results."
        ),
        expected_output="Three lines: secret length, store confirmation, recall confirmation.",
        agent=agent,
    )

    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
    result = crew.kickoff()
    print(f"\n  Result: {result}")
    client.close()


def main() -> None:
    api_key = _env("ONECLAW_AGENT_API_KEY")
    llm = _check_llm_key()

    path = sys.argv[1] if len(sys.argv) > 1 else "test/crewai-live"

    print(f"API Key: {api_key[:12]}...")
    print(f"Path:    {path}")
    print(f"LLM:     {llm}")

    phase1_raw_client(api_key, path)
    phase2_single_agent(api_key, path)
    phase3_multi_tool(api_key, path)

    print("\n=== All phases complete ===")


if __name__ == "__main__":
    main()
