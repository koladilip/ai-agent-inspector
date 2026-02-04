"""
Tests for Agent Inspector trace SDK.

Tests core tracing functionality including:
- Trace context lifecycle
- Event emission
- Sampling behavior
- Non-blocking operations
- Error handling
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from agent_inspector.core.config import Profile, TraceConfig
from agent_inspector.core.events import (
    EventStatus,
    EventType,
    create_error,
    create_final_answer,
    create_llm_call,
    create_memory_read,
    create_memory_write,
    create_run_start,
    create_tool_call,
)
from agent_inspector.core.trace import Trace, TraceContext, get_trace


@pytest.fixture
def test_config():
    """Create a test configuration."""
    return TraceConfig(
        sample_rate=1.0,
        queue_size=100,
        batch_size=10,
        batch_timeout_ms=100,
        encryption_enabled=False,
        compression_enabled=False,
        log_level="DEBUG",
    )


@pytest.fixture
def mock_exporter():
    """Create a mock exporter."""
    exporter = MagicMock()
    exporter.initialize.return_value = None
    exporter.export_batch.return_value = None
    exporter.shutdown.return_value = None
    return exporter


class TestTraceInitialization:
    """Test trace SDK initialization."""

    def test_initialization_with_config(self, test_config, mock_exporter):
        """Test that Trace initializes correctly with config."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        assert trace.config == test_config
        assert trace._exporter is not None
        assert trace._queue_manager is not None

    def test_initialization_without_config(self, test_config, mock_exporter):
        """Test that Trace uses global config when none provided."""
        from agent_inspector.core.config import set_config

        set_config(test_config)

        trace = Trace(exporter=mock_exporter)

        assert trace.config is not None

    def test_lazy_initialization(self, test_config, mock_exporter):
        """Test that initialization happens on first use."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        assert not trace._initialized

        # First use should initialize
        with trace.run("test_run"):
            pass

        assert trace._initialized


class TestTraceContext:
    """Test trace context lifecycle."""

    def test_context_creation(self, test_config, mock_exporter):
        """Test creating a trace context."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run") as ctx:
            assert ctx is not None
            assert ctx.run_id is not None
            assert ctx.run_name == "test_run"
            assert ctx._active is True
            assert len(ctx._events) >= 1

    def test_context_lifecycle(self, test_config, mock_exporter):
        """Test complete context lifecycle."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run") as ctx:
            assert ctx._active is True
            start_duration = ctx.get_duration_ms()
            assert start_duration is not None

        # After context exit
        assert ctx._active is False
        assert ctx.end_time_ms is not None

    def test_nested_contexts(self, test_config, mock_exporter):
        """Test nested trace contexts."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("outer_run") as outer_ctx:
            assert trace.get_active_context() == outer_ctx

            with trace.run("inner_run") as inner_ctx:
                assert trace.get_active_context() == inner_ctx

            # Inner context should be done
            assert trace.get_active_context() == outer_ctx

        # Both should be done
        assert trace.get_active_context() is None

    def test_context_with_user_info(self, test_config, mock_exporter):
        """Test context with user and session info."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run(
            "test_run",
            agent_type="custom",
            user_id="user123",
            session_id="session456",
        ) as ctx:
            assert ctx.agent_type == "custom"
            assert ctx.user_id == "user123"
            assert ctx.session_id == "session456"


class TestEventEmission:
    """Test event emission functionality."""

    def test_llm_event(self, test_config, mock_exporter):
        """Test emitting an LLM call event."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run") as ctx:
            event = ctx.llm(
                model="gpt-4",
                prompt="Hello",
                response="Hi there!",
                prompt_tokens=2,
                completion_tokens=3,
                total_tokens=5,
            )

            assert event is not None
            assert event.type == EventType.LLM_CALL
            assert event.model == "gpt-4"
            assert event.prompt == "Hello"
            assert event.response == "Hi there!"
            assert event.prompt_tokens == 2
            assert event.completion_tokens == 3
            assert event.total_tokens == 5
            assert event.status == EventStatus.COMPLETED
            assert event.duration_ms is not None

    def test_tool_event(self, test_config, mock_exporter):
        """Test emitting a tool call event."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run") as ctx:
            event = ctx.tool(
                tool_name="search",
                tool_args={"query": "test"},
                tool_result={"results": 5},
                tool_type="search",
            )

            assert event is not None
            assert event.type == EventType.TOOL_CALL
            assert event.tool_name == "search"
            assert event.tool_args == {"query": "test"}
            assert event.tool_result == {"results": 5}
            assert event.tool_type == "search"
            assert event.status == EventStatus.COMPLETED

    def test_memory_read_event(self, test_config, mock_exporter):
        """Test emitting a memory read event."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run") as ctx:
            event = ctx.memory_read(
                memory_key="user_prefs",
                memory_value={"color": "blue"},
                memory_type="key_value",
            )

            assert event is not None
            assert event.type == EventType.MEMORY_READ
            assert event.memory_key == "user_prefs"
            assert event.memory_value == {"color": "blue"}
            assert event.memory_type == "key_value"

    def test_memory_write_event(self, test_config, mock_exporter):
        """Test emitting a memory write event."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run") as ctx:
            event = ctx.memory_write(
                memory_key="last_search",
                memory_value={"query": "test"},
                memory_type="key_value",
                overwrite=True,
            )

            assert event is not None
            assert event.type == EventType.MEMORY_WRITE
            assert event.memory_key == "last_search"
            assert event.memory_value == {"query": "test"}
            assert event.overwrite is True

    def test_error_event(self, test_config, mock_exporter):
        """Test emitting an error event."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run") as ctx:
            event = ctx.error(
                error_type="ValueError",
                error_message="Invalid value",
                critical=False,
            )

            assert event is not None
            assert event.type == EventType.ERROR
            assert event.error_type == "ValueError"
            assert event.error_message == "Invalid value"
            assert event.critical is False
            assert ctx._error_occurred is True

    def test_final_answer_event(self, test_config, mock_exporter):
        """Test emitting a final answer event."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run") as ctx:
            event = ctx.final(
                answer="The answer is 42",
                answer_type="text",
                success=True,
            )

            assert event is not None
            assert event.type == EventType.FINAL_ANSWER
            assert event.answer == "The answer is 42"
            assert event.answer_type == "text"
            assert event.success is True
            assert ctx._active is False


class TestSampling:
    """Test sampling behavior."""

    def test_always_sample(self, test_config, mock_exporter):
        """Test that sample_rate=1.0 always samples."""
        test_config.sample_rate = 1.0
        trace = Trace(config=test_config, exporter=mock_exporter)

        traced_runs = 0
        for i in range(10):
            with trace.run(f"run_{i}") as ctx:
                if ctx is not None:
                    traced_runs += 1

        assert traced_runs == 10

    def test_never_sample(self, test_config, mock_exporter):
        """Test that sample_rate=0.0 never samples."""
        test_config.sample_rate = 0.0
        trace = Trace(config=test_config, exporter=mock_exporter)

        traced_runs = 0
        for i in range(10):
            with trace.run(f"run_{i}") as ctx:
                if ctx is not None:
                    traced_runs += 1

        assert traced_runs == 0

    def test_partial_sampling(self, test_config, mock_exporter):
        """Test that sample_rate=0.5 samples approximately half."""
        test_config.sample_rate = 0.5
        trace = Trace(config=test_config, exporter=mock_exporter)

        traced_runs = 0
        for i in range(100):
            with trace.run(f"run_{i}") as ctx:
                if ctx is not None:
                    traced_runs += 1

        # Should be approximately 50 (give some margin for randomness)
        assert 40 <= traced_runs <= 60

    def test_sampling_boundary_values(self, test_config, mock_exporter):
        """Boundary sample rates should behave as expected."""
        test_config.sample_rate = 1.0
        trace = Trace(config=test_config, exporter=mock_exporter)
        with trace.run("run"):
            pass

        test_config.sample_rate = 0.0
        trace = Trace(config=test_config, exporter=mock_exporter)
        with trace.run("run") as ctx:
            assert ctx is None


def test_only_on_error_emits_delete_run(monkeypatch, test_config, mock_exporter):
    """When only_on_error is set and no error occurs, a run_end delete is emitted."""
    test_config.only_on_error = True
    events = []

    from agent_inspector.core.queue import EventQueue

    def capture_put_nowait(self, event):
        events.append(event)
        return True

    monkeypatch.setattr(EventQueue, "put_nowait", capture_put_nowait, raising=True)
    trace = Trace(config=test_config, exporter=mock_exporter)

    with trace.run("test_run"):
        pass

    run_end_events = [e for e in events if e.get("type") == "run_end"]
    assert run_end_events
    assert run_end_events[-1].get("delete_run") is True


def test_run_end_emitted_on_success(monkeypatch, test_config, mock_exporter):
    events = []

    from agent_inspector.core.queue import EventQueue

    def capture_put_nowait(self, event):
        events.append(event)
        return True

    monkeypatch.setattr(EventQueue, "put_nowait", capture_put_nowait, raising=True)
    trace = Trace(config=test_config, exporter=mock_exporter)

    with trace.run("test_run"):
        pass

    run_end_events = [e for e in events if e.get("type") == "run_end"]
    assert run_end_events
    assert run_end_events[-1].get("delete_run") is False


def test_run_end_status_failed_on_exception(monkeypatch, test_config, mock_exporter):
    events = []

    from agent_inspector.core.queue import EventQueue

    def capture_put_nowait(self, event):
        events.append(event)
        return True

    monkeypatch.setattr(EventQueue, "put_nowait", capture_put_nowait, raising=True)
    trace = Trace(config=test_config, exporter=mock_exporter)

    with pytest.raises(ValueError):
        with trace.run("test_run"):
            raise ValueError("boom")

    run_end_events = [e for e in events if e.get("type") == "run_end"]
    assert run_end_events
    assert run_end_events[-1].get("run_status") == "failed"


def test_shutdown_calls_exporter(test_config):
    exporter = MagicMock()
    exporter.initialize.return_value = None
    exporter.export_batch.return_value = None
    exporter.shutdown.return_value = None

    trace = Trace(config=test_config, exporter=exporter)
    with trace.run("test_run"):
        pass

    trace.shutdown()
    exporter.shutdown.assert_called_once()


def test_get_active_context_nested(test_config, mock_exporter):
    trace = Trace(config=test_config, exporter=mock_exporter)
    with trace.run("outer") as outer:
        assert trace.get_active_context() == outer
        with trace.run("inner") as inner:
            assert trace.get_active_context() == inner
        assert trace.get_active_context() == outer


def test_shutdown_without_init(test_config, mock_exporter):
    trace = Trace(config=test_config, exporter=mock_exporter)
    trace.shutdown()


def test_emit_on_inactive_context(test_config, mock_exporter):
    trace = Trace(config=test_config, exporter=mock_exporter)
    with trace.run("test_run") as ctx:
        ctx._active = False
        assert ctx.llm(model="m", prompt="p", response="r") is None
        assert ctx.tool(tool_name="t", tool_args={}, tool_result="x") is None
        assert ctx.memory_read(memory_key="k", memory_value="v") is None
        assert ctx.memory_write(memory_key="k", memory_value="v") is None
        assert ctx.error(error_type="E", error_message="err") is None
        assert ctx.final(answer="a") is None


def test_get_active_context_none(test_config, mock_exporter):
    trace = Trace(config=test_config, exporter=mock_exporter)
    assert trace.get_active_context() is None


def test_queue_event_failure_is_non_fatal(test_config, mock_exporter, monkeypatch):
    trace = Trace(config=test_config, exporter=mock_exporter)

    def boom(self, _event):
        raise RuntimeError("queue fail")

    from agent_inspector.core.queue import EventQueue

    monkeypatch.setattr(EventQueue, "put_nowait", boom, raising=True)
    with trace.run("test_run") as ctx:
        # Should not raise even if queue fails
        ctx.llm(model="m", prompt="p", response="r")
        assert ctx is not None


def test_trace_convenience_methods_without_context(test_config, mock_exporter):
    trace = Trace(config=test_config, exporter=mock_exporter)
    assert trace.llm(model="m", prompt="p", response="r") is None
    assert trace.tool(tool_name="t", tool_args={}, tool_result="x") is None
    assert trace.memory_read(memory_key="k", memory_value="v") is None
    assert trace.memory_write(memory_key="k", memory_value="v") is None
    assert trace.error(error_type="E", error_message="err") is None
    assert trace.final(answer="a") is None


def test_trace_convenience_methods_with_context(test_config, mock_exporter):
    trace = Trace(config=test_config, exporter=mock_exporter)
    with trace.run("test_run"):
        assert trace.memory_read(memory_key="k", memory_value="v") is not None
        assert trace.memory_write(memory_key="k", memory_value="v") is not None
        assert trace.error(error_type="E", error_message="err") is not None
        assert trace.final(answer="a") is not None


def test_context_parent_event_stack(test_config, mock_exporter):
    trace = Trace(config=test_config, exporter=mock_exporter)
    with trace.run("test_run") as ctx:
        event = ctx.llm(model="m", prompt="p", response="r")
        assert event is not None
        with ctx._push_parent_event(event.event_id):
            child = ctx.tool(tool_name="t", tool_args={}, tool_result="x")
            assert child is not None
            assert child.parent_event_id == event.event_id


def test_context_complete_updates_status(test_config, mock_exporter):
    trace = Trace(config=test_config, exporter=mock_exporter)
    with trace.run("test_run") as ctx:
        ctx.complete(success=False)
        assert ctx._status == "failed"
        assert ctx._active is False


def test_export_batch_failure_is_non_fatal(test_config):
    class BoomExporter:
        def initialize(self):
            return None

        def export_batch(self, _batch):
            raise RuntimeError("boom")

        def close(self):
            return None

    trace = Trace(config=test_config, exporter=BoomExporter())
    trace._export_batch([{"event_id": "e1"}])


class TestErrorHandling:
    """Test error handling in trace context."""

    def test_exception_in_context(self, test_config, mock_exporter):
        """Test that exceptions in context are caught and logged."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with pytest.raises(ValueError):
            with trace.run("test_run") as ctx:
                ctx.llm(model="gpt-4", prompt="Hello", response="Hi")
                raise ValueError("Test error")

        # Error should have been logged
        assert ctx._error_occurred is True

    def test_graceful_context_exit_on_error(self, test_config, mock_exporter):
        """Test that context exits gracefully even with error."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        try:
            with trace.run("test_run") as ctx:
                ctx.llm(model="gpt-4", prompt="Hello", response="Hi")
                raise ValueError("Test error")
        except ValueError:
            pass

        # Context should still be properly cleaned up
        assert ctx._active is False
        assert ctx.end_time_ms is not None


class TestNonBlocking:
    """Test that operations are non-blocking."""

    def test_event_queue_put_nowait(self, test_config, mock_exporter):
        """Test that put_nowait does not block."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run") as ctx:
            # Queue event
            queue = trace._queue_manager.get_queue()
            event_dict = {"test": "data"}

            start_time = time.time()
            result = queue.put_nowait(event_dict)
            elapsed = time.time() - start_time

            # Should complete very quickly (<1ms)
            assert result is True
            assert elapsed < 0.001

    def test_context_creation_is_fast(self, test_config, mock_exporter):
        """Test that context creation is fast."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        start_time = time.time()
        with trace.run("test_run"):
            pass
        elapsed = time.time() - start_time

        # Should complete quickly (<10ms)
        assert elapsed < 0.01


class TestEventFactory:
    """Test event factory functions."""

    def test_create_run_start(self):
        """Test creating a run start event."""
        event = create_run_start(
            run_id="test_run_id",
            run_name="test_run",
            agent_type="custom",
        )

        assert event.type == EventType.RUN_START
        assert event.run_id == "test_run_id"
        assert event.run_name == "test_run"
        assert event.agent_type == "custom"

    def test_create_llm_call(self):
        """Test creating an LLM call event."""
        event = create_llm_call(
            run_id="test_run_id",
            model="gpt-4",
            prompt="Hello",
            response="Hi",
        )

        assert event.type == EventType.LLM_CALL
        assert event.model == "gpt-4"
        assert event.prompt == "Hello"
        assert event.response == "Hi"

    def test_create_tool_call(self):
        """Test creating a tool call event."""
        event = create_tool_call(
            run_id="test_run_id",
            tool_name="search",
            tool_args={"query": "test"},
        )

        assert event.type == EventType.TOOL_CALL
        assert event.tool_name == "search"
        assert event.tool_args == {"query": "test"}

    def test_create_error(self):
        """Test creating an error event."""
        event = create_error(
            run_id="test_run_id",
            error_type="ValueError",
            error_message="Test error",
        )

        assert event.type == EventType.ERROR
        assert event.error_type == "ValueError"
        assert event.error_message == "Test error"

    def test_create_final_answer(self):
        """Test creating a final answer event."""
        event = create_final_answer(
            run_id="test_run_id",
            answer="The answer is 42",
        )

        assert event.type == EventType.FINAL_ANSWER
        assert event.answer == "The answer is 42"

    def test_event_to_dict(self):
        """Test that events can be serialized to dict."""
        event = create_llm_call(
            run_id="test_run_id",
            model="gpt-4",
            prompt="Hello",
            response="Hi",
        )

        event_dict = event.to_dict()

        assert isinstance(event_dict, dict)
        assert event_dict["type"] == EventType.LLM_CALL.value
        assert event_dict["model"] == "gpt-4"
        assert event_dict["run_id"] == "test_run_id"


class TestConfiguration:
    """Test TraceConfig."""

    def test_default_config(self):
        """Test creating default configuration."""
        config = TraceConfig()

        assert 0.0 <= config.sample_rate <= 1.0
        assert config.queue_size == 1000
        assert config.batch_size == 50
        assert config.compression_enabled is True
        assert config.encryption_enabled is False

    def test_production_profile(self):
        """Test production profile configuration."""
        import os

        os.environ["TRACE_ENCRYPTION_KEY"] = "test_key_32_bytes_long_1234567890"

        config = TraceConfig.production()

        assert config.sample_rate == 0.01
        assert config.compression_enabled is True
        assert config.encryption_enabled is True
        assert config.log_level == "WARNING"

    def test_development_profile(self):
        """Test development profile configuration."""
        config = TraceConfig.development()

        assert config.sample_rate == 0.5
        assert config.compression_enabled is True
        assert config.encryption_enabled is False
        assert config.log_level == "INFO"

    def test_debug_profile(self):
        """Test debug profile configuration."""
        config = TraceConfig.debug()

        assert config.sample_rate == 1.0
        assert config.compression_enabled is False
        assert config.encryption_enabled is False
        assert config.log_level == "DEBUG"

    def test_invalid_sample_rate(self):
        """Test that invalid sample rate raises error."""
        with pytest.raises(ValueError):
            TraceConfig(sample_rate=1.5)

        with pytest.raises(ValueError):
            TraceConfig(sample_rate=-0.1)

    def test_invalid_queue_size(self):
        """Test that invalid queue size raises error."""
        with pytest.raises(ValueError):
            TraceConfig(queue_size=0)

        with pytest.raises(ValueError):
            TraceConfig(queue_size=-100)

    def test_redaction_keys_set(self):
        """Test that redaction keys are normalized."""
        config = TraceConfig(
            redact_keys=["PASSWORD", "API_KEY", "token"],
        )

        keys_set = config.get_redaction_keys_set()
        assert "password" in keys_set
        assert "api_key" in keys_set
        assert "token" in keys_set
        assert keys_set == {"password", "api_key", "token"}


class TestGlobalTrace:
    """Test global trace instance."""

    def test_get_global_trace(self, test_config, mock_exporter):
        """Test getting global trace instance."""
        with patch("agent_inspector.core.trace.StorageExporter", return_value=mock_exporter):
            trace1 = get_trace()
            trace2 = get_trace()

        # Should be same instance
        assert trace1 is trace2

    def test_global_trace_convenience_methods(self, test_config, mock_exporter):
        """Test convenience methods on global trace."""
        with patch("agent_inspector.core.trace.StorageExporter", return_value=mock_exporter):
            with get_trace().run("test_run"):
                # Convenience methods should work
                get_trace().llm(
                    model="gpt-4",
                    prompt="Hello",
                    response="Hi",
                )
                get_trace().tool(
                    tool_name="test",
                    tool_args={},
                    tool_result="ok",
                )
                get_trace().final(answer="Done!")

    def test_module_level_convenience_functions(self, test_config, mock_exporter):
        """Test module-level convenience functions."""
        import agent_inspector.core.trace as trace_module

        trace_module._global_trace = None
        with patch("agent_inspector.core.trace.StorageExporter", return_value=mock_exporter):
            with trace_module.run("module_run"):
                assert trace_module.llm(model="m", prompt="p", response="r") is not None
                assert trace_module.tool(
                    tool_name="t", tool_args={}, tool_result="x"
                ) is not None
                assert trace_module.memory_read(
                    memory_key="k", memory_value="v"
                ) is not None
                assert trace_module.memory_write(
                    memory_key="k", memory_value="v"
                ) is not None
                assert trace_module.error(
                    error_type="E", error_message="err"
                ) is not None
                assert trace_module.final(answer="a") is not None
