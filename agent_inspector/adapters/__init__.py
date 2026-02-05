"""
Adapters for popular agent frameworks.

Provides automatic tracing integration for various agent frameworks
without requiring code changes.

Supported Frameworks:
- LangChain: Automatic tracing of LLM calls, tool calls, and agent actions
- AutoGen: Automatic tracing of multi-agent conversations and handoffs
- CrewAI: Automatic tracing of multi-agent task workflows and delegations

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

Example with AutoGen:
    >>> from agent_inspector.adapters import enable_autogen
    >>>
    >>> # Create AutoGen agents
    >>> assistant = ConversableAgent("assistant", llm_config=llm_config)
    >>> user_proxy = UserProxyAgent("user_proxy")
    >>>
    >>> # Use with automatic tracing
    >>> with enable_autogen() as tracer:
    ...     chat_result = user_proxy.initiate_chat(assistant, message="Hello")

Example with CrewAI:
    >>> from agent_inspector.adapters import enable_crewai
    >>>
    >>> # Create CrewAI crew
    >>> crew = Crew(agents=[researcher, writer], tasks=[task1, task2])
    >>>
    >>> # Use with automatic tracing
    >>> with enable_crewai() as tracer:
    ...     result = crew.kickoff()
"""

# Import adapters (may fail if dependencies not installed)
try:
    from .langchain_adapter import (
        LangChainInspectorCallback,
        LangChainTracer,
        enable,
        get_callback_handler,
    )
except ImportError:
    LangChainInspectorCallback = None
    LangChainTracer = None
    enable = None
    get_callback_handler = None

try:
    from .autogen_adapter import (
        AutoGenInspectorCallback,
        AutoGenTracer,
        enable as enable_autogen,
        get_callback_handler as get_autogen_callback_handler,
    )
except ImportError:
    AutoGenInspectorCallback = None
    AutoGenTracer = None
    enable_autogen = None
    get_autogen_callback_handler = None

try:
    from .crewai_adapter import (
        CrewAIInspectorCallback,
        CrewAITracer,
        enable as enable_crewai,
        get_callback_handler as get_crewai_callback_handler,
    )
except ImportError:
    CrewAIInspectorCallback = None
    CrewAITracer = None
    enable_crewai = None
    get_crewai_callback_handler = None

__all__ = [
    # LangChain
    "LangChainInspectorCallback",
    "LangChainTracer",
    "enable",
    "get_callback_handler",
    "enable_langchain",
    # AutoGen
    "AutoGenInspectorCallback",
    "AutoGenTracer",
    "enable_autogen",
    "get_autogen_callback_handler",
    # CrewAI
    "CrewAIInspectorCallback",
    "CrewAITracer",
    "enable_crewai",
    "get_crewai_callback_handler",
]

# Convenience aliases
enable_langchain = enable
"""Convenience alias for enable() function.""" ""
