"""
Tests for multi-agent system support in Agent Inspector.

Tests multi-agent event types and emission:
- Agent spawn, join, leave events
- Agent communication and handoff events
- Task assignment and completion events
"""

import pytest
from unittest.mock import MagicMock

from agent_inspector.core.config import TraceConfig
from agent_inspector.core.events import (
    AgentCommunicationEvent,
    AgentHandoffEvent,
    AgentJoinEvent,
    AgentLeaveEvent,
    AgentSpawnEvent,
    BaseEvent,
    EventStatus,
    EventType,
    TaskAssignmentEvent,
    TaskCompletionEvent,
    create_agent_communication,
    create_agent_handoff,
    create_agent_join,
    create_agent_leave,
    create_agent_spawn,
    create_llm_call,
    create_task_assignment,
    create_task_completion,
)
from agent_inspector.core.trace import Trace, TraceContext, set_trace, run


@pytest.fixture
def test_config():
    """Create a test configuration with 100% sampling."""
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


class TestAgentSpawnEvent:
    """Test agent spawn events."""

    def test_agent_spawn_event_creation(self):
        """Test creating an agent spawn event."""
        event = create_agent_spawn(
            run_id="run_123",
            agent_id="agent_456",
            agent_name="Test Agent",
            agent_role="assistant",
            parent_run_id="parent_789",
            agent_config={"model": "gpt-4", "temperature": 0.7},
        )

        assert event is not None
        assert event.type == EventType.AGENT_SPAWN
        assert event.agent_id == "agent_456"
        assert event.agent_name == "Test Agent"
        assert event.agent_role == "assistant"
        assert event.parent_run_id == "parent_789"
        assert event.agent_config == {"model": "gpt-4", "temperature": 0.7}
        assert event.name == "Spawn: Test Agent"

    def test_agent_spawn_event_to_dict(self):
        """Test agent spawn event serialization."""
        event = create_agent_spawn(
            run_id="run_123",
            agent_id="agent_456",
            agent_name="Test Agent",
            agent_role="assistant",
        )

        data = event.to_dict()
        assert data["type"] == "agent_spawn"
        assert data["agent_id"] == "agent_456"
        assert data["agent_name"] == "Test Agent"
        assert data["agent_role"] == "assistant"
        assert "event_id" in data
        assert "timestamp_ms" in data


class TestAgentJoinEvent:
    """Test agent join events."""

    def test_agent_join_event_creation(self):
        """Test creating an agent join event."""
        event = create_agent_join(
            run_id="run_123",
            agent_id="agent_456",
            agent_name="Test Agent",
            group_id="group_789",
            group_name="Support Team",
        )

        assert event is not None
        assert event.type == EventType.AGENT_JOIN
        assert event.agent_id == "agent_456"
        assert event.agent_name == "Test Agent"
        assert event.group_id == "group_789"
        assert event.group_name == "Support Team"
        assert event.name == "Join: Test Agent"


class TestAgentLeaveEvent:
    """Test agent leave events."""

    def test_agent_leave_event_creation(self):
        """Test creating an agent leave event."""
        event = create_agent_leave(
            run_id="run_123",
            agent_id="agent_456",
            agent_name="Test Agent",
            group_id="group_789",
            reason="task_complete",
        )

        assert event is not None
        assert event.type == EventType.AGENT_LEAVE
        assert event.agent_id == "agent_456"
        assert event.agent_name == "Test Agent"
        assert event.group_id == "group_789"
        assert event.reason == "task_complete"
        assert event.name == "Leave: Test Agent"


class TestAgentCommunicationEvent:
    """Test agent communication events."""

    def test_agent_communication_direct(self):
        """Test creating a direct agent communication event."""
        event = create_agent_communication(
            run_id="run_123",
            from_agent_id="agent_a",
            from_agent_name="Agent A",
            to_agent_id="agent_b",
            to_agent_name="Agent B",
            message_content="Hello, can you help?",
            message_type="request",
            group_id="group_1",
        )

        assert event is not None
        assert event.type == EventType.AGENT_COMMUNICATION
        assert event.from_agent_id == "agent_a"
        assert event.from_agent_name == "Agent A"
        assert event.to_agent_id == "agent_b"
        assert event.to_agent_name == "Agent B"
        assert event.message_content == "Hello, can you help?"
        assert event.message_type == "request"
        assert event.group_id == "group_1"
        assert event.name == "Agent A → Agent B"

    def test_agent_communication_broadcast(self):
        """Test creating a broadcast agent communication event."""
        event = create_agent_communication(
            run_id="run_123",
            from_agent_id="agent_a",
            from_agent_name="Agent A",
            message_content="Attention all agents!",
            message_type="announcement",
        )

        assert event is not None
        assert event.to_agent_id is None
        assert event.to_agent_name is None
        assert event.name == "Agent A → All"


class TestAgentHandoffEvent:
    """Test agent handoff events."""

    def test_agent_handoff_event_creation(self):
        """Test creating an agent handoff event."""
        event = create_agent_handoff(
            run_id="run_123",
            from_agent_id="agent_a",
            from_agent_name="Agent A",
            to_agent_id="agent_b",
            to_agent_name="Agent B",
            handoff_reason="escalation",
            context_summary="Complex billing issue",
        )

        assert event is not None
        assert event.type == EventType.AGENT_HANDOFF
        assert event.from_agent_id == "agent_a"
        assert event.from_agent_name == "Agent A"
        assert event.to_agent_id == "agent_b"
        assert event.to_agent_name == "Agent B"
        assert event.handoff_reason == "escalation"
        assert event.context_summary == "Complex billing issue"
        assert event.name == "Handoff: Agent A → Agent B"


class TestTaskAssignmentEvent:
    """Test task assignment events."""

    def test_task_assignment_event_creation(self):
        """Test creating a task assignment event."""
        event = create_task_assignment(
            run_id="run_123",
            task_id="task_456",
            task_name="Process refund",
            assigned_to_agent_id="agent_789",
            assigned_to_agent_name="Billing Agent",
            assigned_by_agent_id="agent_abc",
            priority="high",
            deadline=1234567890000,
            task_data={"customer_id": "cust_123", "amount": 100.00},
        )

        assert event is not None
        assert event.type == EventType.TASK_ASSIGNMENT
        assert event.task_id == "task_456"
        assert event.task_name == "Process refund"
        assert event.assigned_to_agent_id == "agent_789"
        assert event.assigned_to_agent_name == "Billing Agent"
        assert event.assigned_by_agent_id == "agent_abc"
        assert event.priority == "high"
        assert event.deadline == 1234567890000
        assert event.task_data == {"customer_id": "cust_123", "amount": 100.00}
        assert event.name == "Task: Process refund → Billing Agent"


class TestTaskCompletionEvent:
    """Test task completion events."""

    def test_task_completion_success(self):
        """Test creating a successful task completion event."""
        event = create_task_completion(
            run_id="run_123",
            task_id="task_456",
            task_name="Process refund",
            completed_by_agent_id="agent_789",
            completed_by_agent_name="Billing Agent",
            success=True,
            result={"refund_id": "ref_123", "amount": 100.00},
            completion_time_ms=5000,
        )

        assert event is not None
        assert event.type == EventType.TASK_COMPLETION
        assert event.task_id == "task_456"
        assert event.task_name == "Process refund"
        assert event.completed_by_agent_id == "agent_789"
        assert event.completed_by_agent_name == "Billing Agent"
        assert event.success is True
        assert event.result == {"refund_id": "ref_123", "amount": 100.00}
        assert event.completion_time_ms == 5000
        assert event.name == "✓ Task: Process refund"

    def test_task_completion_failure(self):
        """Test creating a failed task completion event."""
        event = create_task_completion(
            run_id="run_123",
            task_id="task_456",
            task_name="Process refund",
            completed_by_agent_id="agent_789",
            completed_by_agent_name="Billing Agent",
            success=False,
            result={"error": "Insufficient funds"},
        )

        assert event is not None
        assert event.success is False
        assert event.name == "✗ Task: Process refund"


class TestTraceContextMultiAgent:
    """Test TraceContext multi-agent methods."""

    def test_agent_spawn_method(self, test_config, mock_exporter):
        """Test TraceContext.agent_spawn method."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run") as ctx:
            event = ctx.agent_spawn(
                agent_id="agent_1",
                agent_name="Test Agent",
                agent_role="assistant",
                agent_config={"model": "gpt-4"},
            )

            assert event is not None
            assert event.type == EventType.AGENT_SPAWN
            assert event.agent_id == "agent_1"
            assert event.agent_name == "Test Agent"
            assert event.run_id == ctx.run_id

    def test_agent_join_method(self, test_config, mock_exporter):
        """Test TraceContext.agent_join method."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run") as ctx:
            event = ctx.agent_join(
                agent_id="agent_1",
                agent_name="Test Agent",
                group_id="group_1",
                group_name="Support Team",
            )

            assert event is not None
            assert event.type == EventType.AGENT_JOIN
            assert event.agent_id == "agent_1"
            assert event.group_id == "group_1"

    def test_agent_leave_method(self, test_config, mock_exporter):
        """Test TraceContext.agent_leave method."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run") as ctx:
            event = ctx.agent_leave(
                agent_id="agent_1",
                agent_name="Test Agent",
                reason="shift_complete",
            )

            assert event is not None
            assert event.type == EventType.AGENT_LEAVE
            assert event.reason == "shift_complete"

    def test_agent_communication_method(self, test_config, mock_exporter):
        """Test TraceContext.agent_communication method."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run") as ctx:
            event = ctx.agent_communication(
                from_agent_id="agent_a",
                from_agent_name="Agent A",
                to_agent_id="agent_b",
                to_agent_name="Agent B",
                message_content="Hello!",
                message_type="greeting",
            )

            assert event is not None
            assert event.type == EventType.AGENT_COMMUNICATION
            assert event.from_agent_id == "agent_a"
            assert event.to_agent_id == "agent_b"
            assert event.message_content == "Hello!"

    def test_agent_handoff_method(self, test_config, mock_exporter):
        """Test TraceContext.agent_handoff method."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run") as ctx:
            event = ctx.agent_handoff(
                from_agent_id="agent_a",
                from_agent_name="Agent A",
                to_agent_id="agent_b",
                to_agent_name="Agent B",
                handoff_reason="escalation",
            )

            assert event is not None
            assert event.type == EventType.AGENT_HANDOFF
            assert event.from_agent_id == "agent_a"
            assert event.to_agent_id == "agent_b"
            assert event.handoff_reason == "escalation"

    def test_task_assign_method(self, test_config, mock_exporter):
        """Test TraceContext.task_assign method."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run") as ctx:
            event = ctx.task_assign(
                task_id="task_1",
                task_name="Process request",
                assigned_to_agent_id="agent_1",
                assigned_to_agent_name="Agent 1",
                priority="high",
            )

            assert event is not None
            assert event.type == EventType.TASK_ASSIGNMENT
            assert event.task_id == "task_1"
            assert event.assigned_to_agent_id == "agent_1"
            assert event.priority == "high"

    def test_task_complete_method(self, test_config, mock_exporter):
        """Test TraceContext.task_complete method."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run") as ctx:
            event = ctx.task_complete(
                task_id="task_1",
                task_name="Process request",
                completed_by_agent_id="agent_1",
                completed_by_agent_name="Agent 1",
                success=True,
                result="Done!",
            )

            assert event is not None
            assert event.type == EventType.TASK_COMPLETION
            assert event.task_id == "task_1"
            assert event.completed_by_agent_id == "agent_1"
            assert event.success is True


class TestTraceMultiAgent:
    """Test Trace class multi-agent convenience methods."""

    def test_trace_agent_spawn(self, test_config, mock_exporter):
        """Test Trace.agent_spawn convenience method."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run"):
            event = trace.agent_spawn(
                agent_id="agent_1",
                agent_name="Test Agent",
            )

            assert event is not None
            assert event.type == EventType.AGENT_SPAWN

    def test_trace_agent_join(self, test_config, mock_exporter):
        """Test Trace.agent_join convenience method."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run"):
            event = trace.agent_join(
                agent_id="agent_1",
                agent_name="Test Agent",
                group_id="group_1",
            )

            assert event is not None
            assert event.type == EventType.AGENT_JOIN

    def test_trace_agent_leave(self, test_config, mock_exporter):
        """Test Trace.agent_leave convenience method."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run"):
            event = trace.agent_leave(
                agent_id="agent_1",
                agent_name="Test Agent",
                reason="task_complete",
            )

            assert event is not None
            assert event.type == EventType.AGENT_LEAVE

    def test_trace_agent_communication(self, test_config, mock_exporter):
        """Test Trace.agent_communication convenience method."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run"):
            event = trace.agent_communication(
                from_agent_id="agent_a",
                from_agent_name="Agent A",
                message_content="Hello",
            )

            assert event is not None
            assert event.type == EventType.AGENT_COMMUNICATION

    def test_trace_agent_handoff(self, test_config, mock_exporter):
        """Test Trace.agent_handoff convenience method."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run"):
            event = trace.agent_handoff(
                from_agent_id="agent_a",
                from_agent_name="Agent A",
                to_agent_id="agent_b",
                to_agent_name="Agent B",
                handoff_reason="escalation",
            )

            assert event is not None
            assert event.type == EventType.AGENT_HANDOFF

    def test_trace_task_assign(self, test_config, mock_exporter):
        """Test Trace.task_assign convenience method."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run"):
            event = trace.task_assign(
                task_id="task_1",
                task_name="Test Task",
                assigned_to_agent_id="agent_1",
                assigned_to_agent_name="Test Agent",
                priority="high",
            )

            assert event is not None
            assert event.type == EventType.TASK_ASSIGNMENT

    def test_trace_task_complete(self, test_config, mock_exporter):
        """Test Trace.task_complete convenience method."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test_run"):
            event = trace.task_complete(
                task_id="task_1",
                task_name="Test Task",
                completed_by_agent_id="agent_1",
                completed_by_agent_name="Test Agent",
                success=True,
            )

            assert event is not None
            assert event.type == EventType.TASK_COMPLETION

    def test_trace_no_active_context(self, test_config, mock_exporter):
        """Test that methods return None when no active context."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        # No active context - test all multi-agent methods
        event = trace.agent_spawn(agent_id="agent_1", agent_name="Test")
        assert event is None

        event = trace.agent_join(agent_id="agent_1", agent_name="Test")
        assert event is None

        event = trace.agent_leave(agent_id="agent_1", agent_name="Test")
        assert event is None

        event = trace.agent_communication(
            from_agent_id="a", from_agent_name="A", message_content="test"
        )
        assert event is None

        event = trace.agent_handoff(
            from_agent_id="a",
            from_agent_name="A",
            to_agent_id="b",
            to_agent_name="B",
        )
        assert event is None

        event = trace.task_assign(
            task_id="task_1",
            task_name="Test",
            assigned_to_agent_id="agent_1",
            assigned_to_agent_name="Test",
        )
        assert event is None

        event = trace.task_complete(
            task_id="task_1",
            task_name="Test",
            completed_by_agent_id="agent_1",
            completed_by_agent_name="Test",
        )
        assert event is None


class TestTraceContextInactiveMultiAgent:
    """Test TraceContext multi-agent methods when context is inactive."""

    def test_context_agent_spawn_inactive(self, test_config, mock_exporter):
        """Test agent_spawn returns None when context is inactive."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test") as ctx:
            ctx._active = False  # Manually deactivate
            event = ctx.agent_spawn(agent_id="a", agent_name="A")
            assert event is None

    def test_context_agent_join_inactive(self, test_config, mock_exporter):
        """Test agent_join returns None when context is inactive."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test") as ctx:
            ctx._active = False
            event = ctx.agent_join(agent_id="a", agent_name="A")
            assert event is None

    def test_context_agent_leave_inactive(self, test_config, mock_exporter):
        """Test agent_leave returns None when context is inactive."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test") as ctx:
            ctx._active = False
            event = ctx.agent_leave(agent_id="a", agent_name="A")
            assert event is None

    def test_context_agent_communication_inactive(self, test_config, mock_exporter):
        """Test agent_communication returns None when context is inactive."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test") as ctx:
            ctx._active = False
            event = ctx.agent_communication(
                from_agent_id="a", from_agent_name="A", message_content="test"
            )
            assert event is None

    def test_context_agent_handoff_inactive(self, test_config, mock_exporter):
        """Test agent_handoff returns None when context is inactive."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test") as ctx:
            ctx._active = False
            event = ctx.agent_handoff(
                from_agent_id="a",
                from_agent_name="A",
                to_agent_id="b",
                to_agent_name="B",
            )
            assert event is None

    def test_context_task_assign_inactive(self, test_config, mock_exporter):
        """Test task_assign returns None when context is inactive."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test") as ctx:
            ctx._active = False
            event = ctx.task_assign(
                task_id="t1",
                task_name="Test",
                assigned_to_agent_id="a",
                assigned_to_agent_name="A",
            )
            assert event is None

    def test_context_task_complete_inactive(self, test_config, mock_exporter):
        """Test task_complete returns None when context is inactive."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("test") as ctx:
            ctx._active = False
            event = ctx.task_complete(
                task_id="t1",
                task_name="Test",
                completed_by_agent_id="a",
                completed_by_agent_name="A",
            )
            assert event is None


class TestEventValidation:
    """Test event validation edge cases."""

    def test_base_event_validation_no_run_id(self):
        """Test that BaseEvent raises ValueError when run_id is empty."""
        from agent_inspector.core.events import BaseEvent

        with pytest.raises(ValueError, match="run_id is required"):
            BaseEvent(run_id="", type=EventType.CUSTOM)

    def test_base_event_set_failed_with_exception(self):
        """Test set_failed with Exception object."""
        from agent_inspector.core.events import create_llm_call

        event = create_llm_call(
            run_id="run_123",
            model="gpt-4",
            prompt="test",
            response="test",
        )

        try:
            raise ValueError("Test error")
        except Exception as e:
            event.set_failed(e)

        assert event.status == EventStatus.FAILED
        assert event.output["error_type"] == "ValueError"
        assert event.output["error_message"] == "Test error"

    def test_base_event_set_failed_with_string(self):
        """Test set_failed with string error."""
        from agent_inspector.core.events import create_llm_call

        event = create_llm_call(
            run_id="run_123",
            model="gpt-4",
            prompt="test",
            response="test",
        )

        event.set_failed("Something went wrong")

        assert event.status == EventStatus.FAILED
        assert event.output["error_type"] == "Error"
        assert event.output["error_message"] == "Something went wrong"


class TestGlobalMultiAgentFunctions:
    """Test global module-level multi-agent convenience functions."""

    def test_global_agent_spawn(self, test_config, mock_exporter):
        """Test global agent_spawn function."""
        from agent_inspector.core.trace import agent_spawn

        set_trace(Trace(config=test_config, exporter=mock_exporter))

        with run("test_run"):
            event = agent_spawn(agent_id="agent_1", agent_name="Test Agent")
            assert event is not None
            assert event.type == EventType.AGENT_SPAWN

    def test_global_agent_join(self, test_config, mock_exporter):
        """Test global agent_join function."""
        from agent_inspector.core.trace import agent_join

        set_trace(Trace(config=test_config, exporter=mock_exporter))

        with run("test_run"):
            event = agent_join(
                agent_id="agent_1", agent_name="Test Agent", group_id="group_1"
            )
            assert event is not None
            assert event.type == EventType.AGENT_JOIN

    def test_global_agent_leave(self, test_config, mock_exporter):
        """Test global agent_leave function."""
        from agent_inspector.core.trace import agent_leave

        set_trace(Trace(config=test_config, exporter=mock_exporter))

        with run("test_run"):
            event = agent_leave(agent_id="agent_1", agent_name="Test Agent")
            assert event is not None
            assert event.type == EventType.AGENT_LEAVE

    def test_global_agent_communication(self, test_config, mock_exporter):
        """Test global agent_communication function."""
        from agent_inspector.core.trace import agent_communication

        set_trace(Trace(config=test_config, exporter=mock_exporter))

        with run("test_run"):
            event = agent_communication(
                from_agent_id="agent_a",
                from_agent_name="Agent A",
                message_content="Hello",
            )
            assert event is not None
            assert event.type == EventType.AGENT_COMMUNICATION

    def test_global_agent_handoff(self, test_config, mock_exporter):
        """Test global agent_handoff function."""
        from agent_inspector.core.trace import agent_handoff

        set_trace(Trace(config=test_config, exporter=mock_exporter))

        with run("test_run"):
            event = agent_handoff(
                from_agent_id="agent_a",
                from_agent_name="Agent A",
                to_agent_id="agent_b",
                to_agent_name="Agent B",
            )
            assert event is not None
            assert event.type == EventType.AGENT_HANDOFF

    def test_global_task_assign(self, test_config, mock_exporter):
        """Test global task_assign function."""
        from agent_inspector.core.trace import task_assign

        set_trace(Trace(config=test_config, exporter=mock_exporter))

        with run("test_run"):
            event = task_assign(
                task_id="task_1",
                task_name="Test Task",
                assigned_to_agent_id="agent_1",
                assigned_to_agent_name="Test Agent",
            )
            assert event is not None
            assert event.type == EventType.TASK_ASSIGNMENT

    def test_global_task_complete(self, test_config, mock_exporter):
        """Test global task_complete function."""
        from agent_inspector.core.trace import task_complete

        set_trace(Trace(config=test_config, exporter=mock_exporter))

        with run("test_run"):
            event = task_complete(
                task_id="task_1",
                task_name="Test Task",
                completed_by_agent_id="agent_1",
                completed_by_agent_name="Test Agent",
            )
            assert event is not None
            assert event.type == EventType.TASK_COMPLETION


class TestMultiAgentCompleteWorkflow:
    """Test complete multi-agent workflow scenarios."""

    def test_support_team_workflow(self, test_config, mock_exporter):
        """Test a complete customer support multi-agent workflow."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("support_session") as ctx:
            # Spawn support team agents
            ctx.agent_spawn(
                agent_id="triage_1",
                agent_name="Triage Agent",
                agent_role="triage",
            )
            ctx.agent_spawn(
                agent_id="billing_1",
                agent_name="Billing Agent",
                agent_role="billing",
            )

            # Agents join the team
            ctx.agent_join(
                agent_id="triage_1",
                agent_name="Triage Agent",
                group_id="support_team",
                group_name="Customer Support",
            )
            ctx.agent_join(
                agent_id="billing_1",
                agent_name="Billing Agent",
                group_id="support_team",
                group_name="Customer Support",
            )

            # Manager communicates with team
            ctx.agent_communication(
                from_agent_id="manager_1",
                from_agent_name="Manager",
                to_agent_id="triage_1",
                to_agent_name="Triage Agent",
                message_content="Please prioritize billing issues",
            )

            # Assign task to billing agent
            ctx.task_assign(
                task_id="task_1",
                task_name="Process refund request",
                assigned_to_agent_id="billing_1",
                assigned_to_agent_name="Billing Agent",
                priority="high",
            )

            # Handoff from triage to billing
            ctx.agent_handoff(
                from_agent_id="triage_1",
                from_agent_name="Triage Agent",
                to_agent_id="billing_1",
                to_agent_name="Billing Agent",
                handoff_reason="specialization",
            )

            # Complete the task
            ctx.task_complete(
                task_id="task_1",
                task_name="Process refund request",
                completed_by_agent_id="billing_1",
                completed_by_agent_name="Billing Agent",
                success=True,
            )

            # Agents leave at end of shift
            ctx.agent_leave(
                agent_id="billing_1",
                agent_name="Billing Agent",
                reason="shift_complete",
            )

            # Final answer
            ctx.final(answer="All tasks completed successfully")

        # Verify events were captured
        events = ctx._events
        event_types = [e["type"] for e in events]

        assert "agent_spawn" in event_types
        assert "agent_join" in event_types
        assert "agent_communication" in event_types
        assert "agent_handoff" in event_types
        assert "task_assignment" in event_types
        assert "task_completion" in event_types
        assert "agent_leave" in event_types
        assert "final_answer" in event_types

    def test_multi_agent_chat_workflow(self, test_config, mock_exporter):
        """Test a multi-agent group chat workflow."""
        trace = Trace(config=test_config, exporter=mock_exporter)

        with trace.run("group_chat") as ctx:
            # Multiple agents join a group chat
            agents = [
                ("researcher_1", "Researcher"),
                ("writer_1", "Writer"),
                ("editor_1", "Editor"),
            ]

            for agent_id, agent_name in agents:
                ctx.agent_spawn(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    agent_role="content_team",
                )
                ctx.agent_join(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    group_id="content_chat",
                    group_name="Content Creation Team",
                )

            # Simulate conversation
            ctx.agent_communication(
                from_agent_id="researcher_1",
                from_agent_name="Researcher",
                to_agent_id="writer_1",
                to_agent_name="Writer",
                message_content="Here is the research data...",
            )

            ctx.agent_communication(
                from_agent_id="writer_1",
                from_agent_name="Writer",
                to_agent_id="editor_1",
                to_agent_name="Editor",
                message_content="Draft is ready for review",
            )

            ctx.agent_handoff(
                from_agent_id="writer_1",
                from_agent_name="Writer",
                to_agent_id="editor_1",
                to_agent_name="Editor",
                handoff_reason="review",
            )

            # All agents leave
            for agent_id, agent_name in agents:
                ctx.agent_leave(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    reason="task_complete",
                )

        events = ctx._events
        communication_events = [e for e in events if e["type"] == "agent_communication"]
        assert len(communication_events) == 2
