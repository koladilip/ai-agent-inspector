"""
Core module for Agent Inspector.

Provides configuration, event model, queue system, and trace SDK.
"""

from .config import Profile, TraceConfig, get_config, set_config
from .events import (
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
    create_error,
    create_final_answer,
    create_llm_call,
    create_memory_read,
    create_memory_write,
    create_run_end,
    create_run_start,
    create_tool_call,
)
from .queue import EventQueue, EventQueueManager
from .trace import Trace, get_trace, run

__all__ = [
    # Configuration
    "Profile",
    "TraceConfig",
    "get_config",
    "set_config",
    # Events
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
    "create_run_start",
    "create_run_end",
    "create_llm_call",
    "create_tool_call",
    "create_memory_read",
    "create_memory_write",
    "create_error",
    "create_final_answer",
    # Queue
    "EventQueue",
    "EventQueueManager",
    # Trace
    "Trace",
    "get_trace",
    "run",
]
