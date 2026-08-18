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

__version__ = "0.3.0"
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
