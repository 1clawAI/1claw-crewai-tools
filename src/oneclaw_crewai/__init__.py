"""1Claw CrewAI tools — secure vault, signing, memory, and automation access for agents."""

from ._client import (
    OneclawAuthError,
    OneclawClient,
    OneclawError,
    OneclawSecretNotFoundError,
    OneclawValidationError,
)
from ._tool import (
    OneclawGetBalanceTool,
    OneclawListEnvVarsTool,
    OneclawListSecretsTool,
    OneclawMemoryGetTool,
    OneclawMemoryPutTool,
    OneclawMemorySearchTool,
    OneclawPutSecretTool,
    OneclawResolveEnvTool,
    OneclawRotateSecretTool,
    OneclawSignMessageTool,
    OneclawSubmitTransactionTool,
    OneclawTriggerAutomationTool,
    OneclawVaultTool,
    get_all_tools,
)

# Single source of truth: the version lives in pyproject.toml and is read
# from the installed distribution metadata. A hand-maintained literal here
# drifts the moment a release bumps one and not the other — 0.59.8 shipped
# reporting 0.59.6, so anyone checking __version__ got the wrong answer.
try:  # pragma: no cover - trivial
    from importlib.metadata import PackageNotFoundError, version as _dist_version

    __version__ = _dist_version("1claw-crewai-tools")
except PackageNotFoundError:  # running from a source tree, not installed
    __version__ = "0+unknown"
__all__ = [
    "OneclawClient",
    "OneclawError",
    "OneclawAuthError",
    "OneclawSecretNotFoundError",
    "OneclawValidationError",
    "OneclawVaultTool",
    "OneclawPutSecretTool",
    "OneclawListSecretsTool",
    "OneclawRotateSecretTool",
    "OneclawResolveEnvTool",
    "OneclawListEnvVarsTool",
    "OneclawMemoryPutTool",
    "OneclawMemoryGetTool",
    "OneclawMemorySearchTool",
    "OneclawSignMessageTool",
    "OneclawSubmitTransactionTool",
    "OneclawGetBalanceTool",
    "OneclawTriggerAutomationTool",
    "get_all_tools",
]
