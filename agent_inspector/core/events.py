"""
Event model for Agent Inspector.

Defines the core event types and schemas for tracing agent execution.
"""

import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from .config import TraceConfig


class EventType(str, Enum):
    """Enumeration of all event types in the system."""

    RUN_START = "run_start"
    RUN_END = "run_end"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    ERROR = "error"
    FINAL_ANSWER = "final_answer"


class EventStatus(str, Enum):
    """Status of events (for async events like LLM calls)."""

    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BaseEvent:
    """
    Base class for all events.

    All events include common fields for identification and tracking.
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    """Unique identifier for this event."""

    run_id: str = ""
    """Identifier for the run this event belongs to."""

    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    """Event timestamp in milliseconds since epoch."""

    type: EventType = EventType.RUN_START
    """Event type (LLM call, tool call, etc.)."""

    name: str = ""
    """Human-readable name for this event."""

    status: EventStatus = EventStatus.STARTED
    """Status of the event."""

    duration_ms: Optional[int] = None
    """Duration of the event in milliseconds (for completed events)."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata for the event."""

    input: Optional[Dict[str, Any]] = None
    """Input data for the event."""

    output: Optional[Dict[str, Any]] = None
    """Output data for the event."""

    parent_event_id: Optional[str] = None
    """ID of parent event (for nested events)."""

    def __post_init__(self):
        """Validate event after initialization."""
        if not self.run_id:
            raise ValueError("run_id is required for events")

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""
        data = asdict(self)
        data["type"] = self.type.value
        data["status"] = self.status.value
        return data

    def set_completed(self, output: Optional[Dict[str, Any]] = None):
        """Mark event as completed and calculate duration."""
        now_ms = int(time.time() * 1000)
        self.status = EventStatus.COMPLETED
        self.duration_ms = now_ms - self.timestamp_ms
        if output is not None:
            self.output = output

    def set_failed(self, error: Union[str, Exception]):
        """Mark event as failed."""
        self.status = EventStatus.FAILED
        self.duration_ms = int(time.time() * 1000) - self.timestamp_ms
        if isinstance(error, Exception):
            self.output = {
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
        else:
            self.output = {"error_type": "Error", "error_message": str(error)}


@dataclass
class RunStartEvent(BaseEvent):
    """Event marking the beginning of an agent run."""

    type: EventType = EventType.RUN_START
    run_name: str = ""
    """Name of the run."""
    agent_type: Optional[str] = None
    """Type of agent framework (e.g., 'langchain', 'autogen')."""
    user_id: Optional[str] = None
    """User identifier for the run."""
    session_id: Optional[str] = None
    """Session identifier for grouping related runs."""


@dataclass
class RunEndEvent(BaseEvent):
    """Event marking the end of an agent run."""

    type: EventType = EventType.RUN_END
    run_status: str = "completed"
    """Final status of the run (completed, failed, deleted)."""
    completed_at: Optional[int] = None
    """Completion timestamp in milliseconds."""
    duration_ms: Optional[int] = None
    """Run duration in milliseconds."""
    delete_run: bool = False
    """Whether the run should be deleted from storage."""

    def __post_init__(self):
        """Validate run end event after initialization."""
        super().__post_init__()
        self.name = "Run End"

    def to_dict(self) -> Dict[str, Any]:
        """Convert run end event to dictionary for JSON serialization."""
        data = super().to_dict()
        data["run_status"] = self.run_status
        return data

@dataclass
class LLMCallEvent(BaseEvent):
    """Event capturing an LLM invocation."""

    type: EventType = EventType.LLM_CALL
    model: str = ""
    """Name of the LLM model used (e.g., 'gpt-4', 'claude-3')."""
    prompt: str = ""
    """Prompt sent to the LLM."""
    response: str = ""
    """Response from the LLM."""
    prompt_tokens: Optional[int] = None
    """Number of tokens in the prompt (if available)."""
    completion_tokens: Optional[int] = None
    """Number of tokens in the completion (if available)."""
    total_tokens: Optional[int] = None
    """Total number of tokens (if available)."""
    streaming: bool = False
    """Whether this was a streaming LLM call."""
    first_token_latency_ms: Optional[int] = None
    """Time to first token in streaming mode (milliseconds)."""
    last_token_latency_ms: Optional[int] = None
    """Time to last token in streaming mode (milliseconds)."""
    tokens_per_second: Optional[float] = None
    """Token generation rate (for streaming calls)."""
    temperature: Optional[float] = None
    """Temperature parameter used."""
    max_tokens: Optional[int] = None
    """Max tokens parameter used."""

    def __post_init__(self):
        """Validate LLM event after initialization."""
        super().__post_init__()
        self.name = self.model or "LLM Call"


@dataclass
class ToolCallEvent(BaseEvent):
    """Event capturing a tool or function invocation."""

    type: EventType = EventType.TOOL_CALL
    tool_name: str = ""
    """Name of the tool/function being called."""
    tool_args: Dict[str, Any] = field(default_factory=dict)
    """Arguments passed to the tool."""
    tool_result: Any = None
    """Result returned by the tool."""
    tool_type: Optional[str] = None
    """Type of tool (e.g., 'search', 'calculator', 'api')."""

    def __post_init__(self):
        """Validate tool event after initialization."""
        super().__post_init__()
        self.name = self.tool_name or "Tool Call"


@dataclass
class MemoryReadEvent(BaseEvent):
    """Event capturing a memory retrieval operation."""

    type: EventType = EventType.MEMORY_READ
    memory_key: str = ""
    """Key being retrieved from memory."""
    memory_value: Optional[Any] = None
    """Value retrieved from memory."""
    memory_type: Optional[str] = None
    """Type of memory (e.g., 'vector', 'key_value', 'cache')."""

    def __post_init__(self):
        """Validate memory read event after initialization."""
        super().__post_init__()
        self.name = f"Read: {self.memory_key or 'Unknown'}"


@dataclass
class MemoryWriteEvent(BaseEvent):
    """Event capturing a memory storage operation."""

    type: EventType = EventType.MEMORY_WRITE
    memory_key: str = ""
    """Key being stored in memory."""
    memory_value: Any = None
    """Value being stored in memory."""
    memory_type: Optional[str] = None
    """Type of memory (e.g., 'vector', 'key_value', 'cache')."""
    overwrite: bool = False
    """Whether this overwrites an existing value."""

    def __post_init__(self):
        """Validate memory write event after initialization."""
        super().__post_init__()
        self.name = f"Write: {self.memory_key or 'Unknown'}"


@dataclass
class ErrorEvent(BaseEvent):
    """Event capturing an error or exception."""

    type: EventType = EventType.ERROR
    error_type: str = ""
    """Type of error (e.g., 'ValueError', 'RuntimeError')."""
    error_message: str = ""
    """Error message."""
    stack_trace: Optional[str] = None
    """Full stack trace if available."""
    critical: bool = False
    """Whether this is a critical error that stopped execution."""

    def __post_init__(self):
        """Validate error event after initialization."""
        super().__post_init__()
        self.name = self.error_type or "Error"


@dataclass
class FinalAnswerEvent(BaseEvent):
    """Event marking the completion of an agent run with final answer."""

    type: EventType = EventType.FINAL_ANSWER
    answer: str = ""
    """Final answer or result from the agent."""
    answer_type: Optional[str] = None
    """Type of answer (e.g., 'text', 'json', 'action')."""
    success: bool = True
    """Whether the run completed successfully."""

    def __post_init__(self):
        """Validate final answer event after initialization."""
        super().__post_init__()
        self.name = "Final Answer"


# Event factory functions
def create_run_start(
    run_id: str,
    run_name: str,
    agent_type: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> RunStartEvent:
    """Create a run start event."""
    return RunStartEvent(
        run_id=run_id,
        run_name=run_name,
        agent_type=agent_type,
        user_id=user_id,
        session_id=session_id,
    )


def create_run_end(
    run_id: str,
    status: str,
    completed_at: int,
    duration_ms: int,
    delete_run: bool = False,
    parent_event_id: Optional[str] = None,
) -> RunEndEvent:
    """Create a run end event."""
    return RunEndEvent(
        run_id=run_id,
        run_status=status,
        completed_at=completed_at,
        duration_ms=duration_ms,
        delete_run=delete_run,
        parent_event_id=parent_event_id,
    )


def create_llm_call(
    run_id: str,
    model: str,
    prompt: str,
    parent_event_id: Optional[str] = None,
    **kwargs,
) -> LLMCallEvent:
    """Create an LLM call event."""
    return LLMCallEvent(
        run_id=run_id,
        model=model,
        prompt=prompt,
        parent_event_id=parent_event_id,
        **kwargs,
    )


def create_tool_call(
    run_id: str,
    tool_name: str,
    tool_args: Dict[str, Any],
    parent_event_id: Optional[str] = None,
    **kwargs,
) -> ToolCallEvent:
    """Create a tool call event."""
    return ToolCallEvent(
        run_id=run_id,
        tool_name=tool_name,
        tool_args=tool_args,
        parent_event_id=parent_event_id,
        **kwargs,
    )


def create_memory_read(
    run_id: str,
    memory_key: str,
    parent_event_id: Optional[str] = None,
    **kwargs,
) -> MemoryReadEvent:
    """Create a memory read event."""
    return MemoryReadEvent(
        run_id=run_id,
        memory_key=memory_key,
        parent_event_id=parent_event_id,
        **kwargs,
    )


def create_memory_write(
    run_id: str,
    memory_key: str,
    memory_value: Any,
    parent_event_id: Optional[str] = None,
    **kwargs,
) -> MemoryWriteEvent:
    """Create a memory write event."""
    return MemoryWriteEvent(
        run_id=run_id,
        memory_key=memory_key,
        memory_value=memory_value,
        parent_event_id=parent_event_id,
        **kwargs,
    )


def create_error(
    run_id: str,
    error_type: str,
    error_message: str,
    parent_event_id: Optional[str] = None,
    critical: bool = False,
    **kwargs,
) -> ErrorEvent:
    """Create an error event."""
    return ErrorEvent(
        run_id=run_id,
        error_type=error_type,
        error_message=error_message,
        parent_event_id=parent_event_id,
        critical=critical,
        **kwargs,
    )


def create_final_answer(
    run_id: str,
    answer: str,
    parent_event_id: Optional[str] = None,
    **kwargs,
) -> FinalAnswerEvent:
    """Create a final answer event."""
    return FinalAnswerEvent(
        run_id=run_id,
        answer=answer,
        parent_event_id=parent_event_id,
        **kwargs,
    )
