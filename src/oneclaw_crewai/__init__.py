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
    OneclawListSecretsTool,
    OneclawMemoryGetTool,
    OneclawMemoryPutTool,
    OneclawMemorySearchTool,
    OneclawPutSecretTool,
    OneclawRotateSecretTool,
    OneclawSignMessageTool,
    OneclawSubmitTransactionTool,
    OneclawTriggerAutomationTool,
    OneclawVaultTool,
    get_all_tools,
)

__version__ = "0.2.0"
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
    "OneclawMemoryPutTool",
    "OneclawMemoryGetTool",
    "OneclawMemorySearchTool",
    "OneclawSignMessageTool",
    "OneclawSubmitTransactionTool",
    "OneclawGetBalanceTool",
    "OneclawTriggerAutomationTool",
    "get_all_tools",
]
