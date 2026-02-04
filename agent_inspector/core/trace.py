"""
Trace SDK for Agent Inspector.

Provides the main interface for tracing agent executions with context
managers and event emission methods. All operations are non-blocking
and thread-safe.

Extensibility:
- Pass a custom Exporter to Trace(exporter=...) or use CompositeExporter
  for multiple backends.
- Pass a custom Sampler to Trace(sampler=...) to control which runs are traced.
- Use TraceContext.emit(event) or Trace.emit(event) for custom event types.
- Use set_trace(trace) / set_trace(None) for testing or process-wide override.

Note: Under queue backpressure, events (including run_end) may be dropped;
the worker never blocks the calling thread.
"""

import hashlib
import logging
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, List, Optional

from ..storage.exporter import StorageExporter
from .config import TraceConfig, get_config
from .events import (
    BaseEvent,
    ErrorEvent,
    EventType,
    FinalAnswerEvent,
    LLMCallEvent,
    MemoryReadEvent,
    MemoryWriteEvent,
    ToolCallEvent,
    create_run_end,
    create_error,
    create_final_answer,
    create_llm_call,
    create_memory_read,
    create_memory_write,
    create_run_start,
    create_tool_call,
)
from .interfaces import Exporter, Sampler
from .queue import EventQueue, EventQueueManager

logger = logging.getLogger(__name__)


def _default_should_sample(run_id: str, config: TraceConfig) -> bool:
    """
    Default deterministic sampling based on run_id and config.sample_rate.

    Used when no custom Sampler is provided. Deterministic so the same run_id
    always gets the same decision.
    """
    if config.only_on_error:
        return True
    if config.sample_rate >= 1.0:
        return True
    if config.sample_rate <= 0.0:
        return False
    hash_val = int(hashlib.md5(run_id.encode()).hexdigest(), 16)
    threshold = int(config.sample_rate * (2**32))
    return (hash_val % (2**32)) < threshold


class TraceContext:
    """
    Context for a single agent run trace.

    Manages the lifecycle of a trace run, including event collection,
    run metadata, and completion tracking.
    """

    def __init__(
        self,
        run_id: str,
        run_name: str,
        config: TraceConfig,
        queue: EventQueue,
        agent_type: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """
        Initialize trace context.

        Args:
            run_id: Unique identifier for this run.
            run_name: Human-readable name for the run.
            config: TraceConfig instance.
            queue: Event queue for async processing.
            agent_type: Type of agent framework.
            user_id: User identifier.
            session_id: Session identifier.
        """
        self.run_id = run_id
        self.run_name = run_name
        self.config = config
        self.queue = queue
        self.agent_type = agent_type
        self.user_id = user_id
        self.session_id = session_id

        # Timing
        self.start_time_ms = int(time.time() * 1000)
        self.end_time_ms: Optional[int] = None

        # State
        self._active: bool = True
        self._events: List[Dict[str, Any]] = []
        self._parent_event_ids: List[str] = []  # For nested events

        # Run status
        self._status: str = "running"
        self._error_occurred: bool = False

        # Emit run start event
        self._emit_run_start()

    def _emit_run_start(self):
        """Emit the run start event."""
        event = create_run_start(
            run_id=self.run_id,
            run_name=self.run_name,
            agent_type=self.agent_type,
            user_id=self.user_id,
            session_id=self.session_id,
        )
        self._queue_event(event)
        logger.debug(f"Started trace run: {self.run_id} ({self.run_name})")

    def _queue_event(self, event: BaseEvent, critical: bool = False) -> None:
        """
        Queue an event for async processing.

        Events are queued raw and processed in the background worker
        to minimize impact on agent execution performance.

        Args:
            event: Event to queue.
            critical: If True and config.block_on_run_end is set, block (up to
                run_end_block_timeout_ms) so the event is not dropped under backpressure.
        """
        event_dict = event.to_dict()
        try:
            if critical and getattr(self.config, "block_on_run_end", False):
                timeout_s = getattr(
                    self.config, "run_end_block_timeout_ms", 5000
                ) / 1000.0
                queued = self.queue.put(event_dict, block=True, timeout=timeout_s)
            else:
                queued = self.queue.put_nowait(event_dict)
            if queued:
                self._events.append(event_dict)
        except Exception as e:
            logger.error(f"Failed to queue event {event.event_id}: {e}")
            # Don't block execution, just log the error

    @property
    def parent_event_id(self) -> Optional[str]:
        """Get the current parent event ID for nesting."""
        return self._parent_event_ids[-1] if self._parent_event_ids else None

    @contextmanager
    def _push_parent_event(self, event_id: str):
        """Context manager to push/pop parent event ID for nesting."""
        self._parent_event_ids.append(event_id)
        try:
            yield
        finally:
            self._parent_event_ids.pop()

    def llm(
        self,
        model: str,
        prompt: str,
        response: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Optional[LLMCallEvent]:
        """
        Emit an LLM call event.

        Args:
            model: Name of the LLM model.
            prompt: Prompt sent to the LLM.
            response: Response from the LLM.
            prompt_tokens: Number of tokens in the prompt (if available).
            completion_tokens: Number of tokens in the completion (if available).
            total_tokens: Total number of tokens (if available).
            temperature: Temperature parameter used.
            max_tokens: Max tokens parameter used.
            **kwargs: Additional LLM parameters.

        Returns:
            The created LLM call event.
        """
        if not self._active:
            logger.warning("Attempted to emit event on inactive trace context")
            return None

        event = create_llm_call(
            run_id=self.run_id,
            model=model,
            prompt=prompt,
            response=response,
            parent_event_id=self.parent_event_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        event.set_completed()
        self._queue_event(event)
        return event

    def tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        tool_result: Any,
        tool_type: Optional[str] = None,
        **kwargs,
    ) -> Optional[ToolCallEvent]:
        """
        Emit a tool call event.

        Args:
            tool_name: Name of the tool being called.
            tool_args: Arguments passed to the tool.
            tool_result: Result returned by the tool.
            tool_type: Type of tool (e.g., 'search', 'calculator').
            **kwargs: Additional tool parameters.

        Returns:
            The created tool call event, or None if trace context is inactive.
        """
        if not self._active:
            logger.warning("Attempted to emit event on inactive trace context")
            return None

        event = create_tool_call(
            run_id=self.run_id,
            tool_name=tool_name,
            tool_args=tool_args,
            parent_event_id=self.parent_event_id,
            tool_result=tool_result,
            tool_type=tool_type,
            **kwargs,
        )
        event.set_completed(output={"tool_result": tool_result})
        self._queue_event(event)
        return event

    def memory_read(
        self,
        memory_key: str,
        memory_value: Any,
        memory_type: Optional[str] = None,
        **kwargs,
    ) -> Optional[MemoryReadEvent]:
        """
        Emit a memory read event.

        Args:
            memory_key: Key being retrieved from memory.
            memory_value: Value retrieved from memory.
            memory_type: Type of memory (e.g., 'vector', 'key_value').
            **kwargs: Additional memory parameters.

        Returns:
            The created memory read event, or None if trace context is inactive.
        """
        if not self._active:
            logger.warning("Attempted to emit event on inactive trace context")
            return None

        event = create_memory_read(
            run_id=self.run_id,
            memory_key=memory_key,
            parent_event_id=self.parent_event_id,
            memory_value=memory_value,
            memory_type=memory_type,
            **kwargs,
        )
        event.set_completed(output={"memory_value": memory_value})
        self._queue_event(event)
        return event

    def memory_write(
        self,
        memory_key: str,
        memory_value: Any,
        memory_type: Optional[str] = None,
        overwrite: bool = False,
        **kwargs,
    ) -> Optional[MemoryWriteEvent]:
        """
        Emit a memory write event.

        Args:
            memory_key: Key being stored in memory.
            memory_value: Value being stored in memory.
            memory_type: Type of memory (e.g., 'vector', 'key_value').
            overwrite: Whether this overwrites an existing value.
            **kwargs: Additional memory parameters.

        Returns:
            The created memory write event.
        """
        if not self._active:
            logger.warning("Attempted to emit event on inactive trace context")
            return None

        event = create_memory_write(
            run_id=self.run_id,
            memory_key=memory_key,
            parent_event_id=self.parent_event_id,
            memory_value=memory_value,
            memory_type=memory_type,
            overwrite=overwrite,
            **kwargs,
        )
        event.set_completed(output={"memory_value": memory_value})
        self._queue_event(event)
        return event

    def error(
        self,
        error_type: str,
        error_message: str,
        stack_trace: Optional[str] = None,
        critical: bool = False,
        **kwargs,
    ) -> Optional[ErrorEvent]:
        """
        Emit an error event.

        Args:
            error_type: Type of error (e.g., 'ValueError').
            error_message: Error message.
            stack_trace: Full stack trace if available.
            critical: Whether this is a critical error.
            **kwargs: Additional error parameters.

        Returns:
            The created error event.
        """
        if not self._active:
            logger.warning("Attempted to emit event on inactive trace context")
            return None

        self._error_occurred = True
        event = create_error(
            run_id=self.run_id,
            error_type=error_type,
            error_message=error_message,
            parent_event_id=self.parent_event_id,
            critical=critical,
            stack_trace=stack_trace,
            **kwargs,
        )
        event.set_failed(error_message)
        self._queue_event(event)
        return event

    def final(
        self,
        answer: str,
        answer_type: Optional[str] = None,
        success: bool = True,
        **kwargs,
    ) -> Optional[FinalAnswerEvent]:
        """
        Emit a final answer event marking completion of the run.

        Args:
            answer: Final answer or result from the agent.
            answer_type: Type of answer (e.g., 'text', 'json').
            success: Whether the run completed successfully.
            **kwargs: Additional final answer parameters.

        Returns:
            The created final answer event.
        """
        if not self._active:
            logger.warning("Attempted to emit event on inactive trace context")
            return None

        event = create_final_answer(
            run_id=self.run_id,
            answer=answer,
            parent_event_id=self.parent_event_id,
            answer_type=answer_type,
            success=success,
            **kwargs,
        )
        event.set_completed(output={"answer": answer})
        self._queue_event(event)
        self._active = False
        return event

    def emit(self, event: BaseEvent) -> Optional[BaseEvent]:
        """
        Emit an arbitrary event on this context.

        Use this for custom event types (e.g., subclass BaseEvent with
        type=EventType.CUSTOM) or to push pre-built events.

        Args:
            event: Any BaseEvent (or subclass). run_id and parent_event_id
                are not overwritten; set them before calling if needed.

        Returns:
            The same event after queuing, or None if context is inactive.
        """
        if not self._active:
            logger.warning("Attempted to emit event on inactive trace context")
            return None
        # Ensure run_id and parent linkage for consistency
        if not event.run_id:
            event.run_id = self.run_id
        if event.parent_event_id is None and self.parent_event_id:
            event.parent_event_id = self.parent_event_id
        self._queue_event(event)
        return event

    def complete(self, success: bool = True):
        """
        Mark the trace run as complete without emitting a final answer event.

        Args:
            success: Whether the run completed successfully.
        """
        self._status = "completed" if success else "failed"
        self._active = False
        self.end_time_ms = int(time.time() * 1000)
        logger.debug(f"Completed trace run: {self.run_id} (status: {self._status})")

    def get_duration_ms(self) -> Optional[int]:
        """
        Get the duration of the trace run in milliseconds.

        Returns:
            Duration in milliseconds, or None if not yet completed.
        """
        if self.end_time_ms:
            return self.end_time_ms - self.start_time_ms
        return int(time.time() * 1000) - self.start_time_ms


class Trace:
    """
    Main interface for Agent Inspector tracing.

    Provides context managers and event emission methods for tracing
    agent executions. All operations are non-blocking and thread-safe.
    """

    def __init__(
        self,
        config: Optional[TraceConfig] = None,
        exporter: Optional[Exporter] = None,
        sampler: Optional[Sampler] = None,
    ):
        """
        Initialize the Trace SDK.

        Args:
            config: TraceConfig instance. If None, uses global config.
            exporter: Optional exporter override. Use CompositeExporter
                for multiple backends.
            sampler: Optional sampler to decide which runs to trace.
                If None, uses deterministic hash-based sampling from config.
        """
        self.config = config or get_config()
        self._exporter = exporter or StorageExporter(self.config)
        self._sampler = sampler
        self._queue_manager = EventQueueManager(self.config)
        self._initialized = False
        self._init_lock = threading.Lock()

        # Context stack for active trace contexts (works in both sync and async)
        self._context_stack: ContextVar[Optional[List["TraceContext"]]] = ContextVar(
            "agent_inspector_trace_context_stack", default=None
        )

    def _ensure_initialized(self):
        """Ensure the trace system is initialized (lazy initialization)."""
        if self._initialized:
            return

        with self._init_lock:
            if not self._initialized:
                # Initialize event queue with exporter
                def export_batch(batch: List[Dict[str, Any]]):
                    self._export_batch(batch)

                self._exporter.initialize()
                self._queue_manager.initialize(export_batch)

                self._initialized = True
                logger.info("Trace SDK initialized")

    def _export_batch(self, batch: List[Dict[str, Any]]):
        """
        Export a batch of events to storage.

        Args:
            batch: List of event dictionaries.
        """
        try:
            self._exporter.export_batch(batch)
        except Exception as e:
            logger.exception(f"Failed to export batch: {e}")

    def _check_sampling(self, run_id: str, run_name: str) -> bool:
        """
        Check if this run should be sampled based on sampler or config.

        Args:
            run_id: Unique identifier for the run.
            run_name: Human-readable run name.

        Returns:
            True if the run should be sampled/traced, False otherwise.
        """
        if self._sampler is not None:
            return self._sampler.should_sample(run_id, run_name, self.config)
        return _default_should_sample(run_id, self.config)

    @contextmanager
    def run(
        self,
        run_name: str,
        agent_type: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        config: Optional[TraceConfig] = None,
    ):
        """
        Context manager for tracing an agent execution.

        Args:
            run_name: Human-readable name for the run.
            agent_type: Type of agent framework.
            user_id: User identifier.
            session_id: Session identifier for grouping related runs.
            config: Optional config override for this run.

        Yields:
            TraceContext instance for emitting events.

        Example:
            >>> with trace.run("search_flights"):
            ...     trace.llm(model="gpt-4", prompt="Find flights", response="...")
            ...     trace.tool(name="search", args={"q": "flights"}, result="...")
            ...     trace.final(answer="Found 5 flights")
        """
        # Generate run ID
        run_id = str(uuid.uuid4())

        # Check sampling
        if not self._check_sampling(run_id, run_name):
            logger.debug(f"Run {run_id} not sampled, skipping trace")
            # Yield a no-op context
            yield None
            return

        # Use provided config or instance config
        run_config = config or self.config

        # Ensure initialization
        self._ensure_initialized()

        # Get queue
        queue = self._queue_manager.get_queue()
        if queue is None:
            raise RuntimeError("Event queue is not initialized")

        # Create trace context
        context = TraceContext(
            run_id=run_id,
            run_name=run_name,
            config=run_config,
            queue=queue,
            agent_type=agent_type,
            user_id=user_id,
            session_id=session_id,
        )

        # Push context onto stack (contextvars: correct for both sync and async)
        stack = self._context_stack.get() or []
        self._context_stack.set(stack + [context])

        try:
            # Yield context to user code
            yield context

        except Exception as e:
            # Capture error from user code
            context.error(
                error_type=type(e).__name__,
                error_message=str(e),
                critical=True,
            )
            raise
        finally:
            # Pop context from stack
            stack = self._context_stack.get() or []
            if len(stack) > 1:
                self._context_stack.set(stack[:-1])
            else:
                self._context_stack.set(None)

            # Mark context as inactive
            context._active = False

            # Set end time
            context.end_time_ms = int(time.time() * 1000)

            duration_ms = context.get_duration_ms()

            # Determine final status
            final_status = "failed" if context._error_occurred else "completed"

            # If only_on_error and no error occurred, delete the run
            delete_run = False
            if run_config.only_on_error and not context._error_occurred:
                logger.debug(f"Deleting run {run_id} (only_on_error and no error)")
                final_status = "deleted"
                delete_run = True

            # Emit run_end event for exporter to update storage
            run_end = create_run_end(
                run_id=run_id,
                status=final_status,
                completed_at=int(time.time() * 1000),
                duration_ms=duration_ms,
                delete_run=delete_run,
            )
            run_end.set_completed()
            context._queue_event(run_end, critical=True)

            logger.debug(
                f"Trace run {run_id} completed in {duration_ms}ms "
                f"(status: {final_status})"
            )

    def get_active_context(self) -> Optional[TraceContext]:
        """
        Get the currently active trace context for the current thread.

        Returns:
            The active TraceContext or None if no context is active.
        """
        stack = self._context_stack.get() or []
        return stack[-1] if stack else None

    # Convenience methods that use active context

    def llm(
        self,
        model: str,
        prompt: str,
        response: str,
        **kwargs,
    ) -> Optional[LLMCallEvent]:
        """
        Emit an LLM call event on the active trace context.

        Convenience method that automatically finds the active context.

        Args:
            model: Name of the LLM model.
            prompt: Prompt sent to the LLM.
            response: Response from the LLM.
            **kwargs: Additional LLM parameters.

        Returns:
            The created LLM call event, or None if no active context.
        """
        context = self.get_active_context()
        if context:
            return context.llm(model=model, prompt=prompt, response=response, **kwargs)
        logger.warning("No active trace context for LLM call")
        return None

    def tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        tool_result: Any,
        **kwargs,
    ) -> Optional[ToolCallEvent]:
        """
        Emit a tool call event on the active trace context.

        Convenience method that automatically finds the active context.

        Args:
            tool_name: Name of the tool being called.
            tool_args: Arguments passed to the tool.
            tool_result: Result returned by the tool.
            **kwargs: Additional tool parameters.

        Returns:
            The created tool call event, or None if no active context.
        """
        context = self.get_active_context()
        if context:
            return context.tool(
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=tool_result,
                **kwargs,
            )
        logger.warning("No active trace context for tool call")
        return None

    def memory_read(
        self, memory_key: str, memory_value: Any, **kwargs
    ) -> Optional[MemoryReadEvent]:
        """
        Emit a memory read event on the active trace context.

        Convenience method that automatically finds the active context.

        Args:
            memory_key: Key being retrieved from memory.
            memory_value: Value retrieved from memory.
            **kwargs: Additional memory parameters.

        Returns:
            The created memory read event, or None if no active context.
        """
        context = self.get_active_context()
        if context:
            return context.memory_read(
                memory_key=memory_key, memory_value=memory_value, **kwargs
            )
        logger.warning("No active trace context for memory read")
        return None

    def memory_write(
        self, memory_key: str, memory_value: Any, **kwargs
    ) -> Optional[MemoryWriteEvent]:
        """
        Emit a memory write event on the active trace context.

        Convenience method that automatically finds the active context.

        Args:
            memory_key: Key being stored in memory.
            memory_value: Value being stored in memory.
            **kwargs: Additional memory parameters.

        Returns:
            The created memory write event, or None if no active context.
        """
        context = self.get_active_context()
        if context:
            return context.memory_write(
                memory_key=memory_key, memory_value=memory_value, **kwargs
            )
        logger.warning("No active trace context for memory write")
        return None

    def error(
        self,
        error_type: str,
        error_message: str,
        **kwargs,
    ) -> Optional[ErrorEvent]:
        """
        Emit an error event on the active trace context.

        Convenience method that automatically finds the active context.

        Args:
            error_type: Type of error (e.g., 'ValueError').
            error_message: Error message.
            **kwargs: Additional error parameters.

        Returns:
            The created error event, or None if no active context.
        """
        context = self.get_active_context()
        if context:
            return context.error(
                error_type=error_type, error_message=error_message, **kwargs
            )
        logger.warning("No active trace context for error")
        return None

    def final(self, answer: str, **kwargs) -> Optional[FinalAnswerEvent]:
        """
        Emit a final answer event on the active trace context.

        Convenience method that automatically finds the active context.

        Args:
            answer: Final answer or result from the agent.
            **kwargs: Additional final answer parameters.

        Returns:
            The created final answer event, or None if no active context.
        """
        context = self.get_active_context()
        if context:
            return context.final(answer=answer, **kwargs)
        logger.warning("No active trace context for final answer")
        return None

    def emit(self, event: BaseEvent) -> Optional[BaseEvent]:
        """
        Emit an arbitrary event on the active trace context.

        Use for custom event types (e.g., EventType.CUSTOM or custom subclasses).

        Args:
            event: Any BaseEvent (or subclass). run_id/parent_event_id are
                set from active context if not already set.

        Returns:
            The event after queuing, or None if no active context.
        """
        context = self.get_active_context()
        if context:
            return context.emit(event)
        logger.warning("No active trace context for emit")
        return None

    def shutdown(self, timeout_ms: int = 5000):
        """
        Shutdown the trace system and flush remaining events.

        Args:
            timeout_ms: Maximum time to wait for shutdown (default: 5000ms).
        """
        logger.info("Shutting down Trace SDK...")
        self._queue_manager.shutdown()
        self._exporter.shutdown()
        logger.info("Trace SDK shut down")


# Global trace instance (set_trace allows injection for tests)
_global_trace: Optional[Trace] = None
_global_trace_lock = threading.Lock()


def get_trace() -> Trace:
    """
    Get the global trace instance.

    Creates a default trace instance if none exists. Use set_trace() to
    inject a custom instance (e.g., in tests) or set_trace(None) to reset.
    """
    global _global_trace
    if _global_trace is None:
        with _global_trace_lock:
            if _global_trace is None:
                _global_trace = Trace()
    return _global_trace


def set_trace(trace_instance: Optional[Trace]) -> None:
    """
    Set the global trace instance (for testing or process-wide override).

    Args:
        trace_instance: Trace instance to use globally, or None to clear
            so the next get_trace() will create a new default instance.
    """
    global _global_trace
    with _global_trace_lock:
        _global_trace = trace_instance


# Convenience functions that use the global trace instance
def run(
    run_name: str,
    agent_type: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
):
    """
    Context manager for tracing an agent execution using the global trace instance.

    Args:
        run_name: Human-readable name for the run.
        agent_type: Type of agent framework.
        user_id: User identifier.
        session_id: Session identifier.

    Yields:
        TraceContext instance.

    Example:
        >>> with trace.run("my_agent"):
        ...     trace.llm(model="gpt-4", prompt="...", response="...")
    """
    global_trace = get_trace()
    return global_trace.run(
        run_name=run_name,
        agent_type=agent_type,
        user_id=user_id,
        session_id=session_id,
    )


def llm(model: str, prompt: str, response: str, **kwargs):
    """Emit an LLM call event using the global trace instance."""
    return get_trace().llm(model=model, prompt=prompt, response=response, **kwargs)


def tool(tool_name: str, tool_args: Dict[str, Any], tool_result: Any, **kwargs):
    """Emit a tool call event using the global trace instance."""
    return get_trace().tool(
        tool_name=tool_name, tool_args=tool_args, tool_result=tool_result, **kwargs
    )


def memory_read(memory_key: str, memory_value: Any, **kwargs):
    """Emit a memory read event using the global trace instance."""
    return get_trace().memory_read(
        memory_key=memory_key, memory_value=memory_value, **kwargs
    )


def memory_write(memory_key: str, memory_value: Any, **kwargs):
    """Emit a memory write event using the global trace instance."""
    return get_trace().memory_write(
        memory_key=memory_key, memory_value=memory_value, **kwargs
    )


def error(error_type: str, error_message: str, **kwargs):
    """Emit an error event using the global trace instance."""
    return get_trace().error(
        error_type=error_type, error_message=error_message, **kwargs
    )


def final(answer: str, **kwargs):
    """Emit a final answer event using the global trace instance."""
    return get_trace().final(answer=answer, **kwargs)
