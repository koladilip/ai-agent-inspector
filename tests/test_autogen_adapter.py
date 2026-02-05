"""
Tests for AutoGen adapter.

Tests the AutoGenInspectorCallback without requiring actual AutoGen dependencies.
Uses mock objects to simulate AutoGen agents and conversations.
"""

import pytest
from unittest.mock import MagicMock, Mock, patch

from agent_inspector.core.config import TraceConfig
from agent_inspector.core.events import EventType
from agent_inspector.core.trace import Trace, set_trace

# Import the adapter
from agent_inspector.adapters.autogen_adapter import (
    AutoGenInspectorCallback,
    AutoGenTracer,
    enable,
    get_callback_handler,
)


@pytest.fixture
def test_config():
    """Create a test configuration."""
    return TraceConfig(
        sample_rate=1.0,
        queue_size=100,
        batch_size=10,
        batch_timeout_ms=100,
    )


@pytest.fixture
def mock_exporter():
    """Create a mock exporter."""
    exporter = MagicMock()
    exporter.initialize.return_value = None
    exporter.export_batch.return_value = None
    exporter.shutdown.return_value = None
    return exporter


@pytest.fixture
def mock_agent():
    """Create a mock AutoGen agent."""
    agent = Mock()
    agent.name = "test_agent"
    agent.id = "agent_123"
    return agent


@pytest.fixture
def mock_agent2():
    """Create another mock AutoGen agent."""
    agent = Mock()
    agent.name = "test_agent_2"
    agent.id = "agent_456"
    return agent


class TestAutoGenInspectorCallbackInit:
    """Test AutoGenInspectorCallback initialization."""

    def test_callback_init_default(self, test_config, mock_exporter):
        """Test callback initialization with defaults."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = AutoGenInspectorCallback()

        assert callback.trace is not None
        assert callback.run_name.startswith("autogen_chat_")
        assert callback.track_agent_communication is True
        assert callback.track_handoffs is True
        assert callback.track_task_assignments is True
        assert callback._agent_registry == {}

    def test_callback_init_custom(self, test_config, mock_exporter):
        """Test callback initialization with custom values."""
        trace = Trace(config=test_config, exporter=mock_exporter)
        callback = AutoGenInspectorCallback(
            trace=trace,
            run_name="custom_run",
            track_agent_communication=False,
            track_handoffs=False,
            track_task_assignments=False,
        )

        assert callback.trace is trace
        assert callback.run_name == "custom_run"
        assert callback.track_agent_communication is False
        assert callback.track_handoffs is False
        assert callback.track_task_assignments is False


class TestAutoGenInspectorCallbackRegisterAgent:
    """Test agent registration."""

    def test_register_agent(self, test_config, mock_exporter, mock_agent):
        """Test registering an agent."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = AutoGenInspectorCallback()

        with callback.trace.run("test") as ctx:
            callback._register_agent(mock_agent)

            assert "test_agent" in callback._agent_registry
            assert callback._agent_registry["test_agent"]["name"] == "test_agent"

    def test_register_agent_already_registered(
        self, test_config, mock_exporter, mock_agent
    ):
        """Test registering an agent that's already registered."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = AutoGenInspectorCallback()

        with callback.trace.run("test") as ctx:
            callback._register_agent(mock_agent)
            callback._register_agent(mock_agent)  # Second registration

            # Should only have one entry
            assert len(callback._agent_registry) == 1


class TestAutoGenInspectorCallbackChatEvents:
    """Test chat-related callback events."""

    def test_on_initiate_chat(
        self, test_config, mock_exporter, mock_agent, mock_agent2
    ):
        """Test on_initiate_chat callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = AutoGenInspectorCallback()

        with callback.trace.run("test") as ctx:
            callback.on_initiate_chat(
                sender=mock_agent,
                recipient=mock_agent2,
                message="Hello!",
            )

            # Both agents should be registered
            assert "test_agent" in callback._agent_registry
            assert "test_agent_2" in callback._agent_registry

    def test_on_initiate_chat_no_context(
        self, test_config, mock_exporter, mock_agent, mock_agent2
    ):
        """Test on_initiate_chat without active context."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = AutoGenInspectorCallback()

        # Call without active context - should not raise
        callback.on_initiate_chat(
            sender=mock_agent,
            recipient=mock_agent2,
            message="Hello!",
        )

    def test_on_receive_message(
        self, test_config, mock_exporter, mock_agent, mock_agent2
    ):
        """Test on_receive_message callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = AutoGenInspectorCallback()

        with callback.trace.run("test") as ctx:
            callback.on_receive_message(
                message="Hello there!",
                sender=mock_agent,
                recipient=mock_agent2,
            )

            assert callback._last_speaker == "test_agent"

    def test_on_receive_message_dict(
        self, test_config, mock_exporter, mock_agent, mock_agent2
    ):
        """Test on_receive_message with dict message."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = AutoGenInspectorCallback()

        with callback.trace.run("test") as ctx:
            callback.on_receive_message(
                message={"content": "Hello!", "role": "assistant"},
                sender=mock_agent,
                recipient=mock_agent2,
            )

            assert callback._last_speaker == "test_agent"

    def test_on_receive_message_no_context(
        self, test_config, mock_exporter, mock_agent, mock_agent2
    ):
        """Test on_receive_message without context - should not raise."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = AutoGenInspectorCallback()

        callback.on_receive_message(
            message="Hello!",
            sender=mock_agent,
            recipient=mock_agent2,
        )


class TestAutoGenInspectorCallbackGroupChat:
    """Test group chat callbacks."""

    def test_on_group_chat_start(
        self, test_config, mock_exporter, mock_agent, mock_agent2
    ):
        """Test on_group_chat_start callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = AutoGenInspectorCallback()

        # Mock group chat
        group_chat = Mock()
        group_chat.agents = [mock_agent, mock_agent2]

        with callback.trace.run("test") as ctx:
            callback.on_group_chat_start(
                group_chat_manager=Mock(),
                group_chat=group_chat,
            )

            # Both agents should be registered
            assert "test_agent" in callback._agent_registry
            assert "test_agent_2" in callback._agent_registry

    def test_on_group_chat_end(
        self, test_config, mock_exporter, mock_agent, mock_agent2
    ):
        """Test on_group_chat_end callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = AutoGenInspectorCallback()

        group_chat = Mock()
        group_chat.agents = [mock_agent, mock_agent2]

        with callback.trace.run("test") as ctx:
            callback.on_group_chat_end(
                group_chat_manager=Mock(),
                group_chat=group_chat,
                summary="Chat completed successfully",
            )


class TestAutoGenInspectorCallbackLLM:
    """Test LLM-related callbacks."""

    def test_on_llm_request(self, test_config, mock_exporter, mock_agent):
        """Test on_llm_request callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = AutoGenInspectorCallback()

        messages = [{"role": "user", "content": "Hello"}]

        with callback.trace.run("test") as ctx:
            callback.on_llm_request(
                agent=mock_agent,
                messages=messages,
            )

            # Should store request for correlation
            assert len(callback._pending_llm_requests) == 1

    def test_on_llm_response(self, test_config, mock_exporter, mock_agent):
        """Test on_llm_response callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = AutoGenInspectorCallback()

        messages = [{"role": "user", "content": "Hello"}]

        with callback.trace.run("test") as ctx:
            # First make a request
            callback.on_llm_request(
                agent=mock_agent,
                messages=messages,
            )

            # Then get response
            callback.on_llm_response(
                agent=mock_agent,
                response="Hi there!",
                model="gpt-4",
                usage={"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
            )

    def test_on_llm_response_no_pending(self, test_config, mock_exporter, mock_agent):
        """Test on_llm_response without pending request."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = AutoGenInspectorCallback()

        with callback.trace.run("test") as ctx:
            callback.on_llm_response(
                agent=mock_agent,
                response="Hi there!",
                model="gpt-4",
            )


class TestAutoGenInspectorCallbackFunction:
    """Test function/tool call callbacks."""

    def test_on_function_call(self, test_config, mock_exporter, mock_agent):
        """Test on_function_call callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = AutoGenInspectorCallback()

        with callback.trace.run("test") as ctx:
            callback.on_function_call(
                agent=mock_agent,
                function_name="search",
                arguments={"query": "test"},
                result={"results": ["item1", "item2"]},
            )

    def test_handle_tool_call(self, test_config, mock_exporter, mock_agent):
        """Test _handle_tool_call internal method."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = AutoGenInspectorCallback()

        tool_call = {
            "function": {
                "name": "search",
                "arguments": '{"query": "test"}',
            }
        }

        with callback.trace.run("test") as ctx:
            callback._handle_tool_call(tool_call, "test_agent", ctx)


class TestAutoGenTracer:
    """Test AutoGenTracer context manager."""

    def test_tracer_context_manager(self, test_config, mock_exporter):
        """Test AutoGenTracer as context manager."""
        tracer = AutoGenTracer(
            trace=Trace(config=test_config, exporter=mock_exporter),
            run_name="test_chat",
        )

        with tracer as callback:
            assert callback is not None
            assert isinstance(callback, AutoGenInspectorCallback)

    def test_tracer_cleanup(self, test_config, mock_exporter):
        """Test that tracer cleans up after exit."""
        tracer = AutoGenTracer(
            trace=Trace(config=test_config, exporter=mock_exporter),
            run_name="test_chat",
        )

        with tracer as callback:
            pass

        # After exit, callback should be None
        assert tracer._callback_handler is None


class TestEnableFunction:
    """Test enable() function."""

    def test_enable_returns_tracer(self, test_config, mock_exporter):
        """Test that enable() returns an AutoGenTracer."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))

        tracer = enable(run_name="test_run")
        assert isinstance(tracer, AutoGenTracer)

    def test_enable_context_manager(self, test_config, mock_exporter):
        """Test using enable() as context manager."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))

        with enable(run_name="test_run") as callback:
            assert isinstance(callback, AutoGenInspectorCallback)


class TestGetCallbackHandler:
    """Test get_callback_handler() function."""

    def test_get_callback_handler_returns_callback(self, test_config, mock_exporter):
        """Test that get_callback_handler() returns a callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))

        callback = get_callback_handler()
        assert isinstance(callback, AutoGenInspectorCallback)

    def test_get_callback_handler_custom_options(self, test_config, mock_exporter):
        """Test get_callback_handler() with custom options."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))

        callback = get_callback_handler(
            track_agent_communication=False,
            track_handoffs=False,
            track_task_assignments=False,
        )

        assert callback.track_agent_communication is False
        assert callback.track_handoffs is False
        assert callback.track_task_assignments is False
