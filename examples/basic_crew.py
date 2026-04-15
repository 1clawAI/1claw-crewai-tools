# Run: pip install -e . && python examples/basic_crew.py
# Requires: ONECLAW_* env vars and an LLM key (OPENAI_API_KEY or GOOGLE_API_KEY).

"""Example two-agent crew: first agent fetches a vault path; second summarizes static text."""

from __future__ import annotations

import os
import sys

from crewai import Agent, Crew, Process, Task

from oneclaw_crewai import OneclawVaultTool


def _require_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        print(f"Missing required environment variable: {name}", file=sys.stderr)
        sys.exit(1)
    return v


def _get_llm() -> object | None:
    """Return an LLM instance for Gemini if GOOGLE_API_KEY is set, else None (OpenAI default)."""
    google_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if google_key:
        from crewai import LLM

        return LLM(model="gemini/gemini-2.0-flash", api_key=google_key)
    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "Set OPENAI_API_KEY or GOOGLE_API_KEY for the LLM provider.",
            file=sys.stderr,
        )
        sys.exit(1)
    return None


def main() -> None:
    llm = _get_llm()

    agent_id = _require_env("ONECLAW_AGENT_ID")
    api_key = _require_env("ONECLAW_AGENT_API_KEY")
    vault_id = _require_env("ONECLAW_VAULT_ID")

    vault_tool = OneclawVaultTool(
        agent_id=agent_id,
        api_key=api_key,
        vault_id=vault_id,
    )

    llm_kwargs: dict[str, object] = {"llm": llm} if llm else {}

    fetcher = Agent(
        role="Credential coordinator",
        goal="Retrieve the configured key path from 1Claw without exposing it in chat logs.",
        backstory="You only use the vault tool and report success or failure in generic terms.",
        tools=[vault_tool],
        verbose=True,
        **llm_kwargs,
    )

    summarizer = Agent(
        role="Technical writer",
        goal="Produce a one-sentence explanation of HTTPS for developers.",
        backstory="You never handle raw API keys; you only summarize public facts.",
        tools=[],
        verbose=True,
        **llm_kwargs,
    )

    task_fetch = Task(
        description=(
            "Use the 'oneclaw_vault' tool with path 'api-keys/openai'. "
            "Respond with a single line stating only whether the lookup succeeded — "
            "do not include any characters from the credential itself."
        ),
        expected_output="One line: success or failure, no key material.",
        agent=fetcher,
    )

    task_summary = Task(
        description=(
            "Write one sentence explaining that HTTPS encrypts data between browser and server."
        ),
        expected_output="One sentence.",
        agent=summarizer,
    )

    crew = Crew(
        agents=[fetcher, summarizer],
        tasks=[task_fetch, task_summary],
        process=Process.sequential,
        verbose=True,
    )
    crew.kickoff()


if __name__ == "__main__":
    main()
