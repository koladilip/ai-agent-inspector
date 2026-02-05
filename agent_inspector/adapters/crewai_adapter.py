"""
CrewAI adapter for Agent Inspector.

Provides automatic tracing of CrewAI multi-agent workflows.
Captures agent task assignments, delegations, tool usage, and inter-agent collaboration.

Example Usage:
    >>> from agent_inspector.adapters.crewai_adapter import enable
    >>>
    >>> # Create your CrewAI agents and crew
    >>> researcher = Agent(role="Researcher", goal="Find information", backstory="...")
    >>> writer = Agent(role="Writer", goal="Write content", backstory="...")
    >>> crew = Crew(agents=[researcher, writer], tasks=[task1, task2])
    >>>
    >>> # Enable tracing
    >>> with enable() as tracer:
    ...     result = crew.kickoff()

    >>> # Or use the callback handler directly
    >>> from agent_inspector.adapters.crewai_adapter import get_callback_handler
    >>>
    >>> callbacks = get_callback_handler()
    >>> crew = Crew(
    ...     agents=[researcher, writer],
    ...     tasks=[task1, task2],
    ...     callbacks=[callbacks]
    ... )
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Union

from ..core.trace import Trace, TraceContext, get_trace

logger = logging.getLogger(__name__)


class CrewAIInspectorCallback:
    """
    CrewAI callback handler for automatic multi-agent workflow tracing.

    Captures task assignments, agent delegations, tool usage, and inter-agent
    collaboration patterns in CrewAI crews.
    """

    def __init__(
        self,
        trace: Optional[Trace] = None,
        run_name: Optional[str] = None,
        track_task_assignments: bool = True,
        track_delegations: bool = True,
        track_tool_usage: bool = True,
    ):
        """
        Initialize the CrewAI callback handler.

        Args:
            trace: Trace instance to use (if None, uses global trace).
            run_name: Optional name for the run (defaults to auto-generated).
            track_task_assignments: Whether to track task assignments.
            track_delegations: Whether to track agent delegations.
            track_tool_usage: Whether to track tool usage.
        """
        self.trace = trace or get_trace()
        self.run_name = run_name or f"crewai_workflow_{int(time.time())}"
        self.track_task_assignments = track_task_assignments
        self.track_delegations = track_delegations
        self.track_tool_usage = track_tool_usage

        # State tracking
        self._run_context: Optional[TraceContext] = None
        self._agent_registry: Dict[str, Dict[str, Any]] = {}
        self._active_tasks: Dict[str, Dict[str, Any]] = {}
        self._task_assignments: Dict[str, str] = {}  # task_id -> agent_id

    def on_crew_creation(
        self,
        crew: Any,
        **kwargs,
    ) -> None:
        """
        Called when a Crew is created.

        Args:
            crew: The Crew instance being created.
        """
        context = self.trace.get_active_context()
        if not context:
            return

        # Register all agents in the crew
        agents = getattr(crew, "agents", [])
        for agent in agents:
            self._register_agent(agent, context)

        logger.debug(f"Crew created with {len(agents)} agents")

    def on_agent_creation(
        self,
        agent: Any,
        **kwargs,
    ) -> None:
        """
        Called when an Agent is created.

        Args:
            agent: The Agent instance being created.
        """
        context = self.trace.get_active_context()
        if not context:
            return

        self._register_agent(agent, context)

    def _register_agent(
        self,
        agent: Any,
        context: TraceContext,
    ) -> None:
        """Register an agent and emit spawn event."""
        agent_id = self._get_agent_id(agent)
        agent_name = self._get_agent_name(agent)
        agent_role = self._get_agent_role(agent)

        if agent_id not in self._agent_registry:
            self._agent_registry[agent_id] = {
                "id": agent_id,
                "name": agent_name,
                "role": agent_role,
                "config": {
                    "goal": getattr(agent, "goal", None),
                    "backstory": getattr(agent, "backstory", None),
                    "allow_delegation": getattr(agent, "allow_delegation", None),
                },
            }

            # Emit agent spawn event
            context.agent_spawn(
                agent_id=agent_id,
                agent_name=agent_name,
                agent_role=agent_role,
                agent_config=self._agent_registry[agent_id]["config"],
            )

    def on_task_start(
        self,
        task: Any,
        agent: Any,
        **kwargs,
    ) -> None:
        """
        Called when a task execution starts.

        Args:
            task: The Task being executed.
            agent: The Agent executing the task.
        """
        context = self.trace.get_active_context()
        if not context:
            return

        task_id = self._get_task_id(task)
        task_name = self._get_task_name(task)
        agent_id = self._get_agent_id(agent)
        agent_name = self._get_agent_name(agent)

        # Register the agent
        self._register_agent(agent, context)

        # Track task assignment
        self._task_assignments[task_id] = agent_id
        self._active_tasks[task_id] = {
            "task_id": task_id,
            "task_name": task_name,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "started_at": int(time.time() * 1000),
        }

        # Emit task assignment event
        if self.track_task_assignments:
            context.task_assign(
                task_id=task_id,
                task_name=task_name,
                assigned_to_agent_id=agent_id,
                assigned_to_agent_name=agent_name,
                task_data={
                    "description": getattr(task, "description", None),
                    "expected_output": getattr(task, "expected_output", None),
                },
            )

        logger.debug(f"Task started: {task_name} → {agent_name}")

    def on_task_end(
        self,
        task: Any,
        agent: Any,
        result: Any,
        **kwargs,
    ) -> None:
        """
        Called when a task execution ends.

        Args:
            task: The Task that was executed.
            agent: The Agent that executed the task.
            result: The task result.
        """
        context = self.trace.get_active_context()
        if not context:
            return

        task_id = self._get_task_id(task)
        task_name = self._get_task_name(task)
        agent_id = self._get_agent_id(agent)
        agent_name = self._get_agent_name(agent)

        # Calculate completion time
        completion_time_ms = None
        if task_id in self._active_tasks:
            started_at = self._active_tasks[task_id].get("started_at")
            if started_at:
                completion_time_ms = int(time.time() * 1000) - started_at
            del self._active_tasks[task_id]

        # Emit task completion event
        context.task_complete(
            task_id=task_id,
            task_name=task_name,
            completed_by_agent_id=agent_id,
            completed_by_agent_name=agent_name,
            success=True,
            result=result,
            completion_time_ms=completion_time_ms,
        )

        logger.debug(f"Task completed: {task_name} by {agent_name}")

    def on_task_delegation(
        self,
        task: Any,
        from_agent: Any,
        to_agent: Any,
        reason: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        Called when a task is delegated from one agent to another.

        Args:
            task: The Task being delegated.
            from_agent: The Agent delegating the task.
            to_agent: The Agent receiving the delegation.
            reason: Reason for delegation.
        """
        if not self.track_delegations:
            return

        context = self.trace.get_active_context()
        if not context:
            return

        from_agent_id = self._get_agent_id(from_agent)
        from_agent_name = self._get_agent_name(from_agent)
        to_agent_id = self._get_agent_id(to_agent)
        to_agent_name = self._get_agent_name(to_agent)
        task_name = self._get_task_name(task)

        # Register both agents
        self._register_agent(from_agent, context)
        self._register_agent(to_agent, context)

        # Emit handoff event
        context.agent_handoff(
            from_agent_id=from_agent_id,
            from_agent_name=from_agent_name,
            to_agent_id=to_agent_id,
            to_agent_name=to_agent_name,
            handoff_reason=reason or "delegation",
            context_summary=f"Task delegation: {task_name}",
        )

        logger.debug(f"Task delegated: {from_agent_name} → {to_agent_name}")

    def on_llm_call(
        self,
        agent: Any,
        prompt: str,
        model: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        Called when an agent makes an LLM call.

        Args:
            agent: The Agent making the LLM call.
            prompt: The prompt sent to the LLM.
            model: The LLM model name.
        """
        # Store for correlation with response
        request_id = f"llm_{self._get_agent_id(agent)}_{int(time.time() * 1000)}"
        if not hasattr(self, "_pending_llm_calls"):
            self._pending_llm_calls = {}

        self._pending_llm_calls[request_id] = {
            "agent": agent,
            "prompt": prompt,
            "model": model,
            "started_at": int(time.time() * 1000),
        }

    def on_llm_response(
        self,
        agent: Any,
        response: str,
        model: Optional[str] = None,
        usage: Optional[Dict[str, int]] = None,
        **kwargs,
    ) -> None:
        """
        Called when an agent receives an LLM response.

        Args:
            agent: The Agent that made the LLM call.
            response: The LLM response.
            model: The LLM model name.
            usage: Token usage information.
        """
        context = self.trace.get_active_context()
        if not context:
            return

        agent_id = self._get_agent_id(agent)

        # Find the matching request
        prompt = ""
        matched_model = model
        if hasattr(self, "_pending_llm_calls"):
            for req_id, req_data in list(self._pending_llm_calls.items()):
                if self._get_agent_id(req_data["agent"]) == agent_id:
                    prompt = req_data["prompt"]
                    matched_model = model or req_data["model"]
                    del self._pending_llm_calls[req_id]
                    break

        usage = usage or {}

        # Emit LLM call event
        context.llm(
            model=matched_model or "unknown",
            prompt=prompt,
            response=response,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )

    def on_tool_usage(
        self,
        agent: Any,
        tool_name: str,
        tool_input: str,
        tool_output: str,
        **kwargs,
    ) -> None:
        """
        Called when an agent uses a tool.

        Args:
            agent: The Agent using the tool.
            tool_name: Name of the tool.
            tool_input: Input to the tool.
            tool_output: Output from the tool.
        """
        if not self.track_tool_usage:
            return

        context = self.trace.get_active_context()
        if not context:
            return

        import json

        try:
            tool_args = (
                json.loads(tool_input) if isinstance(tool_input, str) else tool_input
            )
        except (json.JSONDecodeError, TypeError):
            tool_args = {"input": tool_input}

        try:
            tool_result = (
                json.loads(tool_output) if isinstance(tool_output, str) else tool_output
            )
        except (json.JSONDecodeError, TypeError):
            tool_result = tool_output

        # Emit tool call event
        context.tool(
            tool_name=tool_name,
            tool_args=tool_args
            if isinstance(tool_args, dict)
            else {"input": tool_args},
            tool_result=tool_result,
            tool_type="crewai_tool",
        )

    def on_agent_communication(
        self,
        from_agent: Any,
        to_agent: Any,
        message: str,
        message_type: str = "collaboration",
        **kwargs,
    ) -> None:
        """
        Called when agents communicate with each other.

        Args:
            from_agent: The Agent sending the message.
            to_agent: The Agent receiving the message.
            message: The message content.
            message_type: Type of communication.
        """
        context = self.trace.get_active_context()
        if not context:
            return

        from_agent_id = self._get_agent_id(from_agent)
        from_agent_name = self._get_agent_name(from_agent)
        to_agent_id = self._get_agent_id(to_agent)
        to_agent_name = self._get_agent_name(to_agent)

        # Register both agents
        self._register_agent(from_agent, context)
        self._register_agent(to_agent, context)

        # Emit agent communication event
        context.agent_communication(
            from_agent_id=from_agent_id,
            from_agent_name=from_agent_name,
            to_agent_id=to_agent_id,
            to_agent_name=to_agent_name,
            message_content=message,
            message_type=message_type,
        )

    def on_crew_kickoff_start(
        self,
        crew: Any,
        **kwargs,
    ) -> None:
        """
        Called when a Crew kickoff starts.

        Args:
            crew: The Crew being executed.
        """
        context = self.trace.get_active_context()
        if not context:
            return

        # Register all agents
        agents = getattr(crew, "agents", [])
        for agent in agents:
            self._register_agent(agent, context)

        logger.debug(f"Crew kickoff started with {len(agents)} agents")

    def on_crew_kickoff_end(
        self,
        crew: Any,
        result: Any,
        **kwargs,
    ) -> None:
        """
        Called when a Crew kickoff ends.

        Args:
            crew: The Crew that was executed.
            result: The final result.
        """
        context = self.trace.get_active_context()
        if not context:
            return

        # Emit final answer
        if result:
            context.final(answer=str(result))

        logger.debug("Crew kickoff completed")

    def _get_agent_id(self, agent: Any) -> str:
        """Get unique identifier for an agent."""
        if hasattr(agent, "id"):
            return str(agent.id)
        elif hasattr(agent, "name"):
            return str(agent.name)
        elif hasattr(agent, "role"):
            return str(agent.role)
        else:
            return str(id(agent))

    def _get_agent_name(self, agent: Any) -> str:
        """Get human-readable name for an agent."""
        if hasattr(agent, "name"):
            return str(agent.name)
        elif hasattr(agent, "role"):
            return str(agent.role)
        else:
            return f"Agent-{id(agent)}"

    def _get_agent_role(self, agent: Any) -> Optional[str]:
        """Get role for an agent."""
        if hasattr(agent, "role"):
            return str(agent.role)
        elif hasattr(agent, "name"):
            return str(agent.name)
        else:
            return None

    def _get_task_id(self, task: Any) -> str:
        """Get unique identifier for a task."""
        if hasattr(task, "id"):
            return str(task.id)
        elif hasattr(task, "name"):
            return str(task.name)
        elif hasattr(task, "description"):
            desc = str(task.description)
            return f"task_{hash(desc) & 0xFFFFFFFF}"
        else:
            return str(id(task))

    def _get_task_name(self, task: Any) -> str:
        """Get human-readable name for a task."""
        if hasattr(task, "name"):
            return str(task.name)
        elif hasattr(task, "description"):
            desc = str(task.description)
            return desc[:50] + "..." if len(desc) > 50 else desc
        else:
            return f"Task-{id(task)}"


class CrewAITracer:
    """
    Tracer for CrewAI multi-agent workflows with automatic instrumentation.

    Provides a context manager that sets up CrewAI callbacks
    and manages the trace run lifecycle.
    """

    def __init__(
        self,
        trace: Optional[Trace] = None,
        run_name: str = "crewai_workflow",
        track_task_assignments: bool = True,
        track_delegations: bool = True,
        track_tool_usage: bool = True,
        **config_kwargs,
    ):
        """
        Initialize the CrewAI tracer.

        Args:
            trace: Trace instance to use (if None, uses global trace).
            run_name: Name for the trace run.
            track_task_assignments: Whether to track task assignments.
            track_delegations: Whether to track agent delegations.
            track_tool_usage: Whether to track tool usage.
            **config_kwargs: Additional config to pass to trace.run().
        """
        self.trace = trace or get_trace()
        self.run_name = run_name
        self.track_task_assignments = track_task_assignments
        self.track_delegations = track_delegations
        self.track_tool_usage = track_tool_usage
        self.config_kwargs = config_kwargs
        self._callback_handler: Optional[CrewAIInspectorCallback] = None
        self._run_cm = None
        self._run_context: Optional[TraceContext] = None

    def __enter__(self):
        """Enter the tracing context."""
        # Start a trace run
        self._run_cm = self.trace.run(
            run_name=self.run_name,
            agent_type="crewai",
            **self.config_kwargs,
        )
        self._run_context = self._run_cm.__enter__()

        # Create callback handler
        self._callback_handler = CrewAIInspectorCallback(
            trace=self.trace,
            run_name=self.run_name,
            track_task_assignments=self.track_task_assignments,
            track_delegations=self.track_delegations,
            track_tool_usage=self.track_tool_usage,
        )

        return self._callback_handler

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the tracing context."""
        # Clean up
        if self._run_cm:
            self._run_cm.__exit__(exc_type, exc_val, exc_tb)

        self._callback_handler = None
        self._run_cm = None
        self._run_context = None


def enable(
    trace: Optional[Trace] = None,
    run_name: str = "crewai_workflow",
    track_task_assignments: bool = True,
    track_delegations: bool = True,
    track_tool_usage: bool = True,
) -> CrewAITracer:
    """
    Enable automatic CrewAI tracing.

    This function creates a tracer that can be used as a context manager
    to automatically trace CrewAI multi-agent workflow execution.

    Args:
        trace: Trace instance to use (if None, uses global trace).
        run_name: Name for the trace run.
        track_task_assignments: Whether to track task assignments.
        track_delegations: Whether to track agent delegations.
        track_tool_usage: Whether to track tool usage.

    Returns:
        CrewAITracer context manager.

    Example:
        >>> from agent_inspector.adapters.crewai_adapter import enable
        >>>
        >>> with enable() as tracer:
        ...     # Your CrewAI code here
        ...     result = crew.kickoff()
    """
    return CrewAITracer(
        trace=trace,
        run_name=run_name,
        track_task_assignments=track_task_assignments,
        track_delegations=track_delegations,
        track_tool_usage=track_tool_usage,
    )


def get_callback_handler(
    trace: Optional[Trace] = None,
    track_task_assignments: bool = True,
    track_delegations: bool = True,
    track_tool_usage: bool = True,
) -> CrewAIInspectorCallback:
    """
    Get a CrewAI callback handler for manual integration.

    Use this if you want to manually add the callback handler
    to your CrewAI agents or crews.

    Note: For proper multi-agent tracing with context management,
    use the `enable()` context manager instead.

    Args:
        trace: Trace instance to use (if None, uses global trace).
        track_task_assignments: Whether to track task assignments.
        track_delegations: Whether to track agent delegations.
        track_tool_usage: Whether to track tool usage.

    Returns:
        CrewAIInspectorCallback instance.

    Example:
        >>> from agent_inspector.adapters.crewai_adapter import get_callback_handler
        >>>
        >>> callbacks = get_callback_handler()
        >>> crew = Crew(agents=agents, tasks=tasks, callbacks=[callbacks])
    """
    return CrewAIInspectorCallback(
        trace=trace,
        track_task_assignments=track_task_assignments,
        track_delegations=track_delegations,
        track_tool_usage=track_tool_usage,
    )
