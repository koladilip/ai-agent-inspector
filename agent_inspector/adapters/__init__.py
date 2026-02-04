"""
Adapters for popular agent frameworks.

Provides automatic tracing integration for various agent frameworks
without requiring code changes.

Supported Frameworks:
- LangChain: Automatic tracing of LLM calls, tool calls, and agent actions

Example with LangChain:
    >>> from agent_inspector.adapters import enable_langchain
    >>> from langchain.agents import initialize_agent
    >>>
    >>> # Create a LangChain agent
    >>> agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION)
    >>>
    >>> # Use with automatic tracing
    >>> with enable_langchain() as callbacks:
    ...     result = agent.run("Search for flights to New York")
    ...     print(result)
"""

from .langchain_adapter import (
    LangChainInspectorCallback,
    LangChainTracer,
    enable,
    get_callback_handler,
)

__all__ = [
    "LangChainInspectorCallback",
    "LangChainTracer",
    "enable",
    "get_callback_handler",
]

# Convenience alias for LangChain enable function
enable_langchain = enable
"""Convenience alias for enable() function."""
