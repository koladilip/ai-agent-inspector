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
    CUSTOM = "custom"
    """Use for custom events via TraceContext.emit() or Trace.emit()."""

    # Multi-agent events
    AGENT_SPAWN = "agent_spawn"
    """Event when a new agent is spawned/created in a multi-agent system."""
    AGENT_JOIN = "agent_join"
    """Event when an agent joins a conversation/group chat."""
    AGENT_LEAVE = "agent_leave"
    """Event when an agent leaves a conversation/group chat."""
    AGENT_COMMUNICATION = "agent_communication"
    """Event capturing communication between agents (messages)."""
    AGENT_HANDOFF = "agent_handoff"
    """Event capturing handoff from one agent to another."""
    TASK_ASSIGNMENT = "task_assignment"
    """Event when a task is assigned to an agent."""
    TASK_COMPLETION = "task_completion"
    """Event when an agent completes a task."""


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
    For custom event types, subclass BaseEvent, set type=EventType.CUSTOM,
    and use metadata/input/output for payload; then emit via TraceContext.emit().
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


# Multi-agent event types


@dataclass
class AgentSpawnEvent(BaseEvent):
    """Event capturing agent creation/spawning in multi-agent systems."""

    type: EventType = EventType.AGENT_SPAWN
    agent_id: str = ""
    """Unique identifier for the spawned agent."""
    agent_name: str = ""
    """Human-readable name of the agent."""
    agent_role: Optional[str] = None
    """Role of the agent (e.g., 'researcher', 'coder', 'reviewer')."""
    parent_run_id: Optional[str] = None
    """Run ID of the parent agent that spawned this agent."""
    agent_config: Dict[str, Any] = field(default_factory=dict)
    """Configuration of the spawned agent (model, tools, etc.)."""

    def __post_init__(self):
        """Validate agent spawn event after initialization."""
        super().__post_init__()
        self.name = f"Spawn: {self.agent_name or self.agent_id}"


@dataclass
class AgentJoinEvent(BaseEvent):
    """Event capturing agent joining a group chat or conversation."""

    type: EventType = EventType.AGENT_JOIN
    agent_id: str = ""
    """Unique identifier for the joining agent."""
    agent_name: str = ""
    """Human-readable name of the agent."""
    group_id: Optional[str] = None
    """Identifier for the group/conversation being joined."""
    group_name: Optional[str] = None
    """Name of the group/conversation."""

    def __post_init__(self):
        """Validate agent join event after initialization."""
        super().__post_init__()
        self.name = f"Join: {self.agent_name or self.agent_id}"


@dataclass
class AgentLeaveEvent(BaseEvent):
    """Event capturing agent leaving a group chat or conversation."""

    type: EventType = EventType.AGENT_LEAVE
    agent_id: str = ""
    """Unique identifier for the leaving agent."""
    agent_name: str = ""
    """Human-readable name of the agent."""
    group_id: Optional[str] = None
    """Identifier for the group/conversation being left."""
    reason: Optional[str] = None
    """Reason for leaving (e.g., 'task_complete', 'error', 'timeout')."""

    def __post_init__(self):
        """Validate agent leave event after initialization."""
        super().__post_init__()
        self.name = f"Leave: {self.agent_name or self.agent_id}"


@dataclass
class AgentCommunicationEvent(BaseEvent):
    """Event capturing communication between agents."""

    type: EventType = EventType.AGENT_COMMUNICATION
    from_agent_id: str = ""
    """Unique identifier of the sender agent."""
    from_agent_name: str = ""
    """Human-readable name of the sender agent."""
    to_agent_id: Optional[str] = None
    """Unique identifier of the recipient agent (None for broadcast)."""
    to_agent_name: Optional[str] = None
    """Human-readable name of the recipient agent."""
    message_type: str = "message"
    """Type of communication (e.g., 'message', 'request', 'response', 'handoff')."""
    message_content: str = ""
    """Content of the message."""
    group_id: Optional[str] = None
    """Group/conversation ID if part of a group chat."""
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata about the communication."""

    def __post_init__(self):
        """Validate agent communication event after initialization."""
        super().__post_init__()
        if self.to_agent_id:
            self.name = f"{self.from_agent_name or self.from_agent_id} → {self.to_agent_name or self.to_agent_id}"
        else:
            self.name = f"{self.from_agent_name or self.from_agent_id} → All"


@dataclass
class AgentHandoffEvent(BaseEvent):
    """Event capturing handoff from one agent to another."""

    type: EventType = EventType.AGENT_HANDOFF
    from_agent_id: str = ""
    """Unique identifier of the handing-off agent."""
    from_agent_name: str = ""
    """Human-readable name of the handing-off agent."""
    to_agent_id: str = ""
    """Unique identifier of the receiving agent."""
    to_agent_name: str = ""
    """Human-readable name of the receiving agent."""
    handoff_reason: Optional[str] = None
    """Reason for the handoff (e.g., 'specialization', 'escalation', 'load_balancing')."""
    context_summary: Optional[str] = None
    """Summary of context being transferred."""

    def __post_init__(self):
        """Validate agent handoff event after initialization."""
        super().__post_init__()
        self.name = f"Handoff: {self.from_agent_name or self.from_agent_id} → {self.to_agent_name or self.to_agent_id}"


@dataclass
class TaskAssignmentEvent(BaseEvent):
    """Event capturing task assignment to an agent."""

    type: EventType = EventType.TASK_ASSIGNMENT
    task_id: str = ""
    """Unique identifier for the task."""
    task_name: str = ""
    """Human-readable name/description of the task."""
    assigned_to_agent_id: str = ""
    """Agent ID that the task is assigned to."""
    assigned_to_agent_name: str = ""
    """Human-readable name of the assigned agent."""
    assigned_by_agent_id: Optional[str] = None
    """Agent ID that assigned the task (None for system assignment)."""
    priority: Optional[str] = None
    """Task priority (e.g., 'high', 'medium', 'low')."""
    deadline: Optional[int] = None
    """Deadline timestamp in milliseconds (if any)."""
    task_data: Dict[str, Any] = field(default_factory=dict)
    """Additional task-specific data."""

    def __post_init__(self):
        """Validate task assignment event after initialization."""
        super().__post_init__()
        self.name = f"Task: {self.task_name or self.task_id} → {self.assigned_to_agent_name or self.assigned_to_agent_id}"


@dataclass
class TaskCompletionEvent(BaseEvent):
    """Event capturing task completion by an agent."""

    type: EventType = EventType.TASK_COMPLETION
    task_id: str = ""
    """Unique identifier for the task."""
    task_name: str = ""
    """Human-readable name/description of the task."""
    completed_by_agent_id: str = ""
    """Agent ID that completed the task."""
    completed_by_agent_name: str = ""
    """Human-readable name of the completing agent."""
    success: bool = True
    """Whether the task was completed successfully."""
    result: Optional[Any] = None
    """Result/output of the task."""
    completion_time_ms: Optional[int] = None
    """Time taken to complete the task in milliseconds."""

    def __post_init__(self):
        """Validate task completion event after initialization."""
        super().__post_init__()
        status = "✓" if self.success else "✗"
        self.name = f"{status} Task: {self.task_name or self.task_id}"


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


# Multi-agent event factory functions


def create_agent_spawn(
    run_id: str,
    agent_id: str,
    agent_name: str,
    agent_role: Optional[str] = None,
    parent_run_id: Optional[str] = None,
    agent_config: Optional[Dict[str, Any]] = None,
    parent_event_id: Optional[str] = None,
    **kwargs,
) -> AgentSpawnEvent:
    """Create an agent spawn event."""
    return AgentSpawnEvent(
        run_id=run_id,
        agent_id=agent_id,
        agent_name=agent_name,
        agent_role=agent_role,
        parent_run_id=parent_run_id,
        agent_config=agent_config or {},
        parent_event_id=parent_event_id,
        **kwargs,
    )


def create_agent_join(
    run_id: str,
    agent_id: str,
    agent_name: str,
    group_id: Optional[str] = None,
    group_name: Optional[str] = None,
    parent_event_id: Optional[str] = None,
    **kwargs,
) -> AgentJoinEvent:
    """Create an agent join event."""
    return AgentJoinEvent(
        run_id=run_id,
        agent_id=agent_id,
        agent_name=agent_name,
        group_id=group_id,
        group_name=group_name,
        parent_event_id=parent_event_id,
        **kwargs,
    )


def create_agent_leave(
    run_id: str,
    agent_id: str,
    agent_name: str,
    group_id: Optional[str] = None,
    reason: Optional[str] = None,
    parent_event_id: Optional[str] = None,
    **kwargs,
) -> AgentLeaveEvent:
    """Create an agent leave event."""
    return AgentLeaveEvent(
        run_id=run_id,
        agent_id=agent_id,
        agent_name=agent_name,
        group_id=group_id,
        reason=reason,
        parent_event_id=parent_event_id,
        **kwargs,
    )


def create_agent_communication(
    run_id: str,
    from_agent_id: str,
    from_agent_name: str,
    message_content: str,
    to_agent_id: Optional[str] = None,
    to_agent_name: Optional[str] = None,
    message_type: str = "message",
    group_id: Optional[str] = None,
    parent_event_id: Optional[str] = None,
    **kwargs,
) -> AgentCommunicationEvent:
    """Create an agent communication event."""
    return AgentCommunicationEvent(
        run_id=run_id,
        from_agent_id=from_agent_id,
        from_agent_name=from_agent_name,
        to_agent_id=to_agent_id,
        to_agent_name=to_agent_name,
        message_type=message_type,
        message_content=message_content,
        group_id=group_id,
        parent_event_id=parent_event_id,
        **kwargs,
    )


def create_agent_handoff(
    run_id: str,
    from_agent_id: str,
    from_agent_name: str,
    to_agent_id: str,
    to_agent_name: str,
    handoff_reason: Optional[str] = None,
    context_summary: Optional[str] = None,
    parent_event_id: Optional[str] = None,
    **kwargs,
) -> AgentHandoffEvent:
    """Create an agent handoff event."""
    return AgentHandoffEvent(
        run_id=run_id,
        from_agent_id=from_agent_id,
        from_agent_name=from_agent_name,
        to_agent_id=to_agent_id,
        to_agent_name=to_agent_name,
        handoff_reason=handoff_reason,
        context_summary=context_summary,
        parent_event_id=parent_event_id,
        **kwargs,
    )


def create_task_assignment(
    run_id: str,
    task_id: str,
    task_name: str,
    assigned_to_agent_id: str,
    assigned_to_agent_name: str,
    assigned_by_agent_id: Optional[str] = None,
    priority: Optional[str] = None,
    deadline: Optional[int] = None,
    task_data: Optional[Dict[str, Any]] = None,
    parent_event_id: Optional[str] = None,
    **kwargs,
) -> TaskAssignmentEvent:
    """Create a task assignment event."""
    return TaskAssignmentEvent(
        run_id=run_id,
        task_id=task_id,
        task_name=task_name,
        assigned_to_agent_id=assigned_to_agent_id,
        assigned_to_agent_name=assigned_to_agent_name,
        assigned_by_agent_id=assigned_by_agent_id,
        priority=priority,
        deadline=deadline,
        task_data=task_data or {},
        parent_event_id=parent_event_id,
        **kwargs,
    )


def create_task_completion(
    run_id: str,
    task_id: str,
    task_name: str,
    completed_by_agent_id: str,
    completed_by_agent_name: str,
    success: bool = True,
    result: Optional[Any] = None,
    completion_time_ms: Optional[int] = None,
    parent_event_id: Optional[str] = None,
    **kwargs,
) -> TaskCompletionEvent:
    """Create a task completion event."""
    return TaskCompletionEvent(
        run_id=run_id,
        task_id=task_id,
        task_name=task_name,
        completed_by_agent_id=completed_by_agent_id,
        completed_by_agent_name=completed_by_agent_name,
        success=success,
        result=result,
        completion_time_ms=completion_time_ms,
        parent_event_id=parent_event_id,
        **kwargs,
    )
