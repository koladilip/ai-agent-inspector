"""
Tests for CrewAI adapter.

Tests the CrewAIInspectorCallback without requiring actual CrewAI dependencies.
Uses mock objects to simulate CrewAI agents, crews, and tasks.
"""

import pytest
from unittest.mock import MagicMock, Mock, patch

from agent_inspector.core.config import TraceConfig
from agent_inspector.core.events import EventType
from agent_inspector.core.trace import Trace, set_trace

# Import the adapter
from agent_inspector.adapters.crewai_adapter import (
    CrewAIInspectorCallback,
    CrewAITracer,
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
    """Create a mock CrewAI agent."""
    agent = Mock()
    agent.id = "researcher"
    agent.role = "researcher"
    agent.name = "Research Agent"
    agent.goal = "Find information"
    agent.backstory = "Expert researcher"
    agent.allow_delegation = True
    return agent


@pytest.fixture
def mock_agent2():
    """Create another mock CrewAI agent."""
    agent = Mock()
    agent.id = "writer"
    agent.role = "writer"
    agent.name = "Writer Agent"
    agent.goal = "Write content"
    agent.backstory = "Expert writer"
    agent.allow_delegation = False
    return agent


@pytest.fixture
def mock_task():
    """Create a mock CrewAI task."""
    task = Mock()
    task.id = "task_123"
    task.name = "Research task"
    task.description = "Research the topic"
    task.expected_output = "Research report"
    return task


class TestCrewAIInspectorCallbackInit:
    """Test CrewAIInspectorCallback initialization."""

    def test_callback_init_default(self, test_config, mock_exporter):
        """Test callback initialization with defaults."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        assert callback.trace is not None
        assert callback.run_name.startswith("crewai_workflow_")
        assert callback.track_task_assignments is True
        assert callback.track_delegations is True
        assert callback.track_tool_usage is True
        assert callback._agent_registry == {}
        assert callback._active_tasks == {}

    def test_callback_init_custom(self, test_config, mock_exporter):
        """Test callback initialization with custom values."""
        trace = Trace(config=test_config, exporter=mock_exporter)
        callback = CrewAIInspectorCallback(
            trace=trace,
            run_name="custom_workflow",
            track_task_assignments=False,
            track_delegations=False,
            track_tool_usage=False,
        )

        assert callback.trace is trace
        assert callback.run_name == "custom_workflow"
        assert callback.track_task_assignments is False
        assert callback.track_delegations is False
        assert callback.track_tool_usage is False


class TestCrewAIInspectorCallbackAgentRegistration:
    """Test agent registration."""

    def test_register_agent(self, test_config, mock_exporter, mock_agent):
        """Test registering an agent."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        with callback.trace.run("test") as ctx:
            callback._register_agent(mock_agent, ctx)

            assert "researcher" in callback._agent_registry
            assert callback._agent_registry["researcher"]["name"] == "Research Agent"
            assert (
                callback._agent_registry["researcher"]["config"]["goal"]
                == "Find information"
            )

    def test_register_agent_already_registered(
        self, test_config, mock_exporter, mock_agent
    ):
        """Test registering an agent that's already registered."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        with callback.trace.run("test") as ctx:
            callback._register_agent(mock_agent, ctx)
            callback._register_agent(mock_agent, ctx)  # Second registration

            # Should only have one entry
            assert len(callback._agent_registry) == 1


class TestCrewAIInspectorCallbackCrewEvents:
    """Test crew-related callback events."""

    def test_on_crew_creation(
        self, test_config, mock_exporter, mock_agent, mock_agent2
    ):
        """Test on_crew_creation callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        crew = Mock()
        crew.agents = [mock_agent, mock_agent2]

        with callback.trace.run("test") as ctx:
            callback.on_crew_creation(crew)

            # Both agents should be registered
            assert "researcher" in callback._agent_registry
            assert "writer" in callback._agent_registry

    def test_on_agent_creation(self, test_config, mock_exporter, mock_agent):
        """Test on_agent_creation callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        with callback.trace.run("test") as ctx:
            callback.on_agent_creation(mock_agent)

            assert "researcher" in callback._agent_registry

    def test_on_crew_creation_no_context(self, test_config, mock_exporter, mock_agent):
        """Test on_crew_creation without active context."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        crew = Mock()
        crew.agents = [mock_agent]

        # Call without active context - should not raise
        callback.on_crew_creation(crew)


class TestCrewAIInspectorCallbackTaskEvents:
    """Test task-related callback events."""

    def test_on_task_start(self, test_config, mock_exporter, mock_agent, mock_task):
        """Test on_task_start callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        with callback.trace.run("test") as ctx:
            callback.on_task_start(task=mock_task, agent=mock_agent)

            assert "task_123" in callback._active_tasks
            assert callback._active_tasks["task_123"]["agent_id"] == "researcher"

    def test_on_task_end(self, test_config, mock_exporter, mock_agent, mock_task):
        """Test on_task_end callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        with callback.trace.run("test") as ctx:
            # First start the task
            callback.on_task_start(task=mock_task, agent=mock_agent)

            # Then end it
            callback.on_task_end(
                task=mock_task,
                agent=mock_agent,
                result="Task completed successfully",
            )

            # Task should be removed from active tasks
            assert "task_123" not in callback._active_tasks

    def test_on_task_end_no_active_task(
        self, test_config, mock_exporter, mock_agent, mock_task
    ):
        """Test on_task_end for task that wasn't started."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        with callback.trace.run("test") as ctx:
            # End a task that was never started
            callback.on_task_end(
                task=mock_task,
                agent=mock_agent,
                result="Task completed",
            )


class TestCrewAIInspectorCallbackDelegation:
    """Test task delegation callbacks."""

    def test_on_task_delegation(
        self, test_config, mock_exporter, mock_agent, mock_agent2, mock_task
    ):
        """Test on_task_delegation callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        with callback.trace.run("test") as ctx:
            callback.on_task_delegation(
                task=mock_task,
                from_agent=mock_agent,
                to_agent=mock_agent2,
                reason="specialization",
            )

    def test_on_task_delegation_disabled(
        self, test_config, mock_exporter, mock_agent, mock_agent2, mock_task
    ):
        """Test on_task_delegation when tracking is disabled."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback(track_delegations=False)

        with callback.trace.run("test") as ctx:
            # Should return early when disabled
            callback.on_task_delegation(
                task=mock_task,
                from_agent=mock_agent,
                to_agent=mock_agent2,
            )


class TestCrewAIInspectorCallbackLLM:
    """Test LLM-related callbacks."""

    def test_on_llm_call(self, test_config, mock_exporter, mock_agent):
        """Test on_llm_call callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        with callback.trace.run("test") as ctx:
            callback.on_llm_call(
                agent=mock_agent,
                prompt="Hello",
                model="gpt-4",
            )

            # Should store call for correlation
            assert len(callback._pending_llm_calls) == 1

    def test_on_llm_response(self, test_config, mock_exporter, mock_agent):
        """Test on_llm_response callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        with callback.trace.run("test") as ctx:
            # First make a call
            callback.on_llm_call(
                agent=mock_agent,
                prompt="Hello",
                model="gpt-4",
            )

            # Then get response
            callback.on_llm_response(
                agent=mock_agent,
                response="Hi there!",
                model="gpt-4",
                usage={"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
            )

    def test_on_llm_response_no_pending(self, test_config, mock_exporter, mock_agent):
        """Test on_llm_response without pending call."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        with callback.trace.run("test") as ctx:
            callback.on_llm_response(
                agent=mock_agent,
                response="Hi!",
                model="gpt-4",
            )


class TestCrewAIInspectorCallbackTool:
    """Test tool usage callbacks."""

    def test_on_tool_usage(self, test_config, mock_exporter, mock_agent):
        """Test on_tool_usage callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        with callback.trace.run("test") as ctx:
            callback.on_tool_usage(
                agent=mock_agent,
                tool_name="search",
                tool_input='{"query": "test"}',
                tool_output='{"results": ["item1"]}',
            )

    def test_on_tool_usage_disabled(self, test_config, mock_exporter, mock_agent):
        """Test on_tool_usage when tracking is disabled."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback(track_tool_usage=False)

        with callback.trace.run("test") as ctx:
            # Should return early when disabled
            callback.on_tool_usage(
                agent=mock_agent,
                tool_name="search",
                tool_input='{"query": "test"}',
                tool_output='{"results": []}',
            )

    def test_on_tool_usage_invalid_json(self, test_config, mock_exporter, mock_agent):
        """Test on_tool_usage with invalid JSON."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        with callback.trace.run("test") as ctx:
            callback.on_tool_usage(
                agent=mock_agent,
                tool_name="search",
                tool_input="not valid json",
                tool_output="also not valid",
            )


class TestCrewAIInspectorCallbackCommunication:
    """Test agent communication callbacks."""

    def test_on_agent_communication(
        self, test_config, mock_exporter, mock_agent, mock_agent2
    ):
        """Test on_agent_communication callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        with callback.trace.run("test") as ctx:
            callback.on_agent_communication(
                from_agent=mock_agent,
                to_agent=mock_agent2,
                message="Can you help with this?",
                message_type="request",
            )

    def test_on_agent_communication_no_context(
        self, test_config, mock_exporter, mock_agent, mock_agent2
    ):
        """Test on_agent_communication without context."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        # Call without active context - should not raise
        callback.on_agent_communication(
            from_agent=mock_agent,
            to_agent=mock_agent2,
            message="Hello",
        )


class TestCrewAIInspectorCallbackCrewLifecycle:
    """Test crew lifecycle callbacks."""

    def test_on_crew_kickoff_start(
        self, test_config, mock_exporter, mock_agent, mock_agent2
    ):
        """Test on_crew_kickoff_start callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        crew = Mock()
        crew.agents = [mock_agent, mock_agent2]

        with callback.trace.run("test") as ctx:
            callback.on_crew_kickoff_start(crew)

            # Both agents should be registered
            assert "researcher" in callback._agent_registry
            assert "writer" in callback._agent_registry

    def test_on_crew_kickoff_end(self, test_config, mock_exporter):
        """Test on_crew_kickoff_end callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        crew = Mock()

        with callback.trace.run("test") as ctx:
            callback.on_crew_kickoff_end(
                crew=crew,
                result="All tasks completed",
            )


class TestCrewAIInspectorCallbackAgentInfo:
    """Test agent info extraction methods."""

    def test_get_agent_id(self, test_config, mock_exporter, mock_agent):
        """Test _get_agent_id method."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        agent_id = callback._get_agent_id(mock_agent)
        assert agent_id == "researcher"

    def test_get_agent_name(self, test_config, mock_exporter, mock_agent):
        """Test _get_agent_name method."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        agent_name = callback._get_agent_name(mock_agent)
        assert agent_name == "Research Agent"

    def test_get_agent_role(self, test_config, mock_exporter, mock_agent):
        """Test _get_agent_role method."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        agent_role = callback._get_agent_role(mock_agent)
        assert agent_role == "researcher"

    def test_get_task_id(self, test_config, mock_exporter, mock_task):
        """Test _get_task_id method."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        task_id = callback._get_task_id(mock_task)
        assert task_id == "task_123"

    def test_get_task_name(self, test_config, mock_exporter, mock_task):
        """Test _get_task_name method."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))
        callback = CrewAIInspectorCallback()

        task_name = callback._get_task_name(mock_task)
        assert task_name == "Research task"


class TestCrewAITracer:
    """Test CrewAITracer context manager."""

    def test_tracer_context_manager(self, test_config, mock_exporter):
        """Test CrewAITracer as context manager."""
        tracer = CrewAITracer(
            trace=Trace(config=test_config, exporter=mock_exporter),
            run_name="test_workflow",
        )

        with tracer as callback:
            assert callback is not None
            assert isinstance(callback, CrewAIInspectorCallback)

    def test_tracer_cleanup(self, test_config, mock_exporter):
        """Test that tracer cleans up after exit."""
        tracer = CrewAITracer(
            trace=Trace(config=test_config, exporter=mock_exporter),
            run_name="test_workflow",
        )

        with tracer as callback:
            pass

        # After exit, callback should be None
        assert tracer._callback_handler is None


class TestEnableFunction:
    """Test enable() function."""

    def test_enable_returns_tracer(self, test_config, mock_exporter):
        """Test that enable() returns a CrewAITracer."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))

        tracer = enable(run_name="test_workflow")
        assert isinstance(tracer, CrewAITracer)

    def test_enable_context_manager(self, test_config, mock_exporter):
        """Test using enable() as context manager."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))

        with enable(run_name="test_workflow") as callback:
            assert isinstance(callback, CrewAIInspectorCallback)


class TestGetCallbackHandler:
    """Test get_callback_handler() function."""

    def test_get_callback_handler_returns_callback(self, test_config, mock_exporter):
        """Test that get_callback_handler() returns a callback."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))

        callback = get_callback_handler()
        assert isinstance(callback, CrewAIInspectorCallback)

    def test_get_callback_handler_custom_options(self, test_config, mock_exporter):
        """Test get_callback_handler() with custom options."""
        set_trace(Trace(config=test_config, exporter=mock_exporter))

        callback = get_callback_handler(
            track_task_assignments=False,
            track_delegations=False,
            track_tool_usage=False,
        )

        assert callback.track_task_assignments is False
        assert callback.track_delegations is False
        assert callback.track_tool_usage is False
