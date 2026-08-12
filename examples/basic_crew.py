# Run: pip install -e . && python examples/basic_crew.py
# Requires: ONECLAW_AGENT_API_KEY env var and an LLM key (OPENAI_API_KEY or GOOGLE_API_KEY).

"""Example multi-agent crew using all 1Claw tools: secrets, memory, signing, automations."""

from __future__ import annotations

import os
import sys

from crewai import Agent, Crew, Process, Task

from oneclaw_crewai import OneclawClient, get_all_tools


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
    api_key = _require_env("ONECLAW_AGENT_API_KEY")

    client = OneclawClient(api_key=api_key)
    tools = get_all_tools(client)

    llm_kwargs: dict[str, object] = {"llm": llm} if llm else {}

    secrets_agent = Agent(
        role="Secrets Manager",
        goal="Fetch and manage vault secrets securely.",
        backstory="You retrieve and rotate credentials. Never expose raw values.",
        tools=tools,
        verbose=True,
        **llm_kwargs,
    )

    memory_agent = Agent(
        role="Knowledge Manager",
        goal="Store and recall important information across sessions.",
        backstory="You use encrypted memory for persistent knowledge.",
        tools=tools,
        verbose=True,
        **llm_kwargs,
    )

    task_fetch = Task(
        description=(
            "Use 'oneclaw_vault' to read 'api-keys/openai'. "
            "Report only whether the lookup succeeded and the character length."
        ),
        expected_output="One line: success or failure, no key material.",
        agent=secrets_agent,
    )

    task_remember = Task(
        description=(
            "Use 'oneclaw_memory_put' to store the key 'last-check' with value "
            "'secrets verified' in the 'default' namespace."
        ),
        expected_output="Confirmation that the value was stored.",
        agent=memory_agent,
    )

    task_recall = Task(
        description=(
            "Use 'oneclaw_memory_get' to retrieve 'last-check' "
            "from the 'default' namespace."
        ),
        expected_output="The retrieved value.",
        agent=memory_agent,
    )

    crew = Crew(
        agents=[secrets_agent, memory_agent],
        tasks=[task_fetch, task_remember, task_recall],
        process=Process.sequential,
        verbose=True,
    )
    crew.kickoff()


if __name__ == "__main__":
    main()
