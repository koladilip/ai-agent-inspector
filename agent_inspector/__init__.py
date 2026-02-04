"""
Agent Inspector - Framework-agnostic observability for AI agents.

A lightweight, non-blocking tracing system for monitoring and debugging
AI agent reasoning, tool usage, and execution flow.

Example Usage:
    >>> from agent_inspector import trace
    >>>
    >>> with trace.run("my_agent"):
    ...     trace.llm(model="gpt-4", prompt="Hello", response="Hi there!")
    ...     trace.tool(name="search", args={"q": "flights"}, result="5 flights found")
    ...     trace.final(answer="I found 5 flights for you")

Example with LangChain:
    >>> from agent_inspector.adapters.langchain_adapter import enable
    >>>
    >>> with enable() as callbacks:
    ...     result = agent.run("Search for flights to New York")
    >>>     print(result)
"""

__version__ = "1.0.0"
__author__ = "Agent Inspector Team"
__license__ = "MIT"

# Core tracing API
# Configuration
from .core.config import (
    Profile,
    TraceConfig,
    get_config,
    set_config,
)
from .core.trace import (
    Trace,
    error,
    final,
    get_trace,
    llm,
    memory_read,
    memory_write,
    run,
    tool,
)

# LangChain adapter
try:
    from .adapters.langchain_adapter import enable as enable_langchain
except ImportError:
    # LangChain is optional
    enable_langchain = None

# API server
try:
    from .api.main import get_api_server, run_server
except ImportError:
    # FastAPI is optional
    run_server = None
    get_api_server = None

# Event types
from .core.events import (
    BaseEvent,
    ErrorEvent,
    EventStatus,
    EventType,
    FinalAnswerEvent,
    LLMCallEvent,
    MemoryReadEvent,
    MemoryWriteEvent,
    RunEndEvent,
    RunStartEvent,
    ToolCallEvent,
)

__all__ = [
    # Version
    "__version__",
    # Core tracing
    "Trace",
    "trace",  # Convenience alias for get_trace()
    "run",
    "llm",
    "tool",
    "memory_read",
    "memory_write",
    "error",
    "final",
    "get_trace",
    # Configuration
    "TraceConfig",
    "Profile",
    "get_config",
    "set_config",
    # Event types
    "EventType",
    "EventStatus",
    "BaseEvent",
    "RunStartEvent",
    "RunEndEvent",
    "LLMCallEvent",
    "ToolCallEvent",
    "MemoryReadEvent",
    "MemoryWriteEvent",
    "ErrorEvent",
    "FinalAnswerEvent",
    # Adapters (optional)
    "enable_langchain",
    # API server (optional)
    "run_server",
    "get_api_server",
]


# Convenience property for global trace instance
class _GlobalTrace:
    """Convenience wrapper for global trace instance."""

    def __getattr__(self, name):
        """Proxy all attribute access to global trace instance."""
        global_trace = get_trace()
        return getattr(global_trace, name)


trace = _GlobalTrace()
"""Global trace instance for convenience usage.

Example:
    >>> trace.run("my_agent")
    >>> trace.llm(model="gpt-4", prompt="...", response="...")
"""
