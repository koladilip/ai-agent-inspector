"""
AutoGen adapter for Agent Inspector.

Provides automatic tracing of AutoGen multi-agent systems.
Captures agent communication, handoffs, group chat dynamics, and individual agent events.

Example Usage:
    >>> from agent_inspector.adapters.autogen_adapter import enable
    >>>
    >>> # Create your AutoGen agents
    >>> assistant = ConversableAgent("assistant", llm_config=llm_config)
    >>> user_proxy = UserProxyAgent("user_proxy")
    >>>
    >>> # Enable tracing
    >>> with enable() as tracer:
    ...     # Start a group chat
    ...     chat_result = user_proxy.initiate_chat(
    ...         assistant,
    ...         message="Hello!"
    ...     )

    >>> # Or use the AutoGenInspectorCallback directly
    >>> from autogen import GroupChat, GroupChatManager
    >>> from agent_inspector.adapters.autogen_adapter import get_callback_handler
    >>>
    >>> callbacks = get_callback_handler()
    >>> groupchat = GroupChat(
    ...     agents=[assistant, user_proxy, coder],
    ...     messages=[],
    ...     max_round=12
    ... )
    >>> manager = GroupChatManager(groupchat=groupchat, callbacks=[callbacks])
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Union

from ..core.trace import Trace, TraceContext, get_trace

logger = logging.getLogger(__name__)


class AutoGenInspectorCallback:
    """
    AutoGen callback handler for automatic multi-agent tracing.

    Captures agent communication, handoffs, task assignments, and individual
    agent LLM/tool calls in AutoGen multi-agent systems.
    """

    def __init__(
        self,
        trace: Optional[Trace] = None,
        run_name: Optional[str] = None,
        track_agent_communication: bool = True,
        track_handoffs: bool = True,
        track_task_assignments: bool = True,
    ):
        """
        Initialize the AutoGen callback handler.

        Args:
            trace: Trace instance to use (if None, uses global trace).
            run_name: Optional name for the run (defaults to auto-generated).
            track_agent_communication: Whether to track inter-agent messages.
            track_handoffs: Whether to track agent handoffs.
            track_task_assignments: Whether to track task assignments.
        """
        self.trace = trace or get_trace()
        self.run_name = run_name or f"autogen_chat_{int(time.time())}"
        self.track_agent_communication = track_agent_communication
        self.track_handoffs = track_handoffs
        self.track_task_assignments = track_task_assignments

        # State tracking
        self._run_context: Optional[TraceContext] = None
        self._run_cm = None
        self._agent_registry: Dict[str, Dict[str, Any]] = {}
        self._active_conversations: Dict[str, Dict[str, Any]] = {}
        self._last_speaker: Optional[str] = None

    def on_initiate_chat(
        self,
        sender: Any,
        recipient: Any,
        message: str,
        **kwargs,
    ) -> None:
        """
        Called when a chat is initiated between agents.

        Args:
            sender: The initiating agent.
            recipient: The receiving agent.
            message: The initial message.
        """
        context = self.trace.get_active_context()
        if not context:
            logger.warning("No active trace context for chat initiation")
            return

        sender_name = getattr(sender, "name", str(sender))
        recipient_name = getattr(recipient, "name", str(recipient))

        # Register agents if not already tracked
        self._register_agent(sender)
        self._register_agent(recipient)

        # Track conversation start
        conversation_id = str(uuid.uuid4())
        self._active_conversations[conversation_id] = {
            "sender": sender_name,
            "recipient": recipient_name,
            "started_at": int(time.time() * 1000),
        }

        # Emit agent communication event
        if self.track_agent_communication:
            context.agent_communication(
                from_agent_id=sender_name,
                from_agent_name=sender_name,
                to_agent_id=recipient_name,
                to_agent_name=recipient_name,
                message_content=message,
                message_type="initiate_chat",
                group_id=conversation_id,
            )

        logger.debug(f"Chat initiated: {sender_name} → {recipient_name}")

    def on_receive_message(
        self,
        message: Union[str, Dict[str, Any]],
        sender: Any,
        recipient: Any,
        **kwargs,
    ) -> None:
        """
        Called when an agent receives a message.

        Args:
            message: The received message (can be string or dict with content).
            sender: The sending agent.
            recipient: The receiving agent.
        """
        context = self.trace.get_active_context()
        if not context:
            return

        sender_name = getattr(sender, "name", str(sender))
        recipient_name = getattr(recipient, "name", str(recipient))

        # Extract message content
        if isinstance(message, dict):
            content = message.get("content", str(message))
            message_type = message.get("role", "message")
        else:
            content = str(message)
            message_type = "message"

        # Register agents
        self._register_agent(sender)
        self._register_agent(recipient)

        # Track potential handoff
        if (
            self.track_handoffs
            and self._last_speaker
            and self._last_speaker != sender_name
        ):
            if self._last_speaker != recipient_name:
                context.agent_handoff(
                    from_agent_id=self._last_speaker,
                    from_agent_name=self._last_speaker,
                    to_agent_id=sender_name,
                    to_agent_name=sender_name,
                    handoff_reason="conversation_flow",
                    context_summary=f"Message: {content[:100]}..."
                    if len(content) > 100
                    else f"Message: {content}",
                )

        self._last_speaker = sender_name

        # Emit communication event
        if self.track_agent_communication:
            context.agent_communication(
                from_agent_id=sender_name,
                from_agent_name=sender_name,
                to_agent_id=recipient_name,
                to_agent_name=recipient_name,
                message_content=content,
                message_type=message_type,
            )

        # Check for function/tool calls in message
        if isinstance(message, dict):
            tool_calls = message.get("tool_calls", [])
            for tool_call in tool_calls:
                self._handle_tool_call(tool_call, sender_name, context)

    def _handle_tool_call(
        self,
        tool_call: Dict[str, Any],
        agent_name: str,
        context: TraceContext,
    ) -> None:
        """Handle a tool call from an agent."""
        tool_name = tool_call.get("function", {}).get("name", "unknown")
        tool_args_str = tool_call.get("function", {}).get("arguments", "{}")

        import json

        try:
            tool_args = (
                json.loads(tool_args_str)
                if isinstance(tool_args_str, str)
                else tool_args_str
            )
        except json.JSONDecodeError:
            tool_args = {"raw": tool_args_str}

        # This will be updated when the tool result is received
        context.tool(
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result="pending",
            tool_type="autogen_function",
        )

    def on_send_message(
        self,
        message: Union[str, Dict[str, Any]],
        sender: Any,
        recipient: Any,
        request_reply: bool = True,
        silent: bool = False,
        **kwargs,
    ) -> None:
        """
        Called when an agent sends a message.

        Args:
            message: The message being sent.
            sender: The sending agent.
            recipient: The receiving agent.
            request_reply: Whether a reply is requested.
            silent: Whether the message is silent.
        """
        # This is captured via on_receive_message on the other side
        pass

    def on_group_chat_start(
        self,
        group_chat_manager: Any,
        group_chat: Any,
        **kwargs,
    ) -> None:
        """
        Called when a group chat starts.

        Args:
            group_chat_manager: The GroupChatManager instance.
            group_chat: The GroupChat instance.
        """
        context = self.trace.get_active_context()
        if not context:
            return

        # Get agents in the group
        agents = getattr(group_chat, "agents", [])
        group_id = str(uuid.uuid4())

        # Register all agents and emit join events
        for agent in agents:
            agent_name = getattr(agent, "name", str(agent))
            self._register_agent(agent)

            context.agent_join(
                agent_id=agent_name,
                agent_name=agent_name,
                group_id=group_id,
                group_name=getattr(group_chat, "group_name", "group_chat"),
            )

        logger.debug(f"Group chat started with {len(agents)} agents")

    def on_group_chat_end(
        self,
        group_chat_manager: Any,
        group_chat: Any,
        summary: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        Called when a group chat ends.

        Args:
            group_chat_manager: The GroupChatManager instance.
            group_chat: The GroupChat instance.
            summary: Optional summary of the chat.
        """
        context = self.trace.get_active_context()
        if not context:
            return

        # Get agents in the group
        agents = getattr(group_chat, "agents", [])

        # Emit leave events for all agents
        for agent in agents:
            agent_name = getattr(agent, "name", str(agent))
            context.agent_leave(
                agent_id=agent_name,
                agent_name=agent_name,
                reason="chat_complete",
            )

        # Emit final answer if summary is available
        if summary:
            context.final(answer=summary)

        logger.debug(f"Group chat ended. Summary: {summary}")

    def on_llm_request(
        self,
        agent: Any,
        messages: List[Dict[str, Any]],
        **kwargs,
    ) -> None:
        """
        Called when an agent makes an LLM request.

        Args:
            agent: The agent making the request.
            messages: The messages being sent to the LLM.
        """
        context = self.trace.get_active_context()
        if not context:
            return

        agent_name = getattr(agent, "name", str(agent))

        # Store request for later correlation with response
        request_id = f"llm_{agent_name}_{int(time.time() * 1000)}"
        if not hasattr(self, "_pending_llm_requests"):
            self._pending_llm_requests = {}

        self._pending_llm_requests[request_id] = {
            "agent_name": agent_name,
            "messages": messages,
            "started_at": int(time.time() * 1000),
        }

    def on_llm_response(
        self,
        agent: Any,
        response: Any,
        **kwargs,
    ) -> None:
        """
        Called when an agent receives an LLM response.

        Args:
            agent: The agent that made the request.
            response: The LLM response.
        """
        context = self.trace.get_active_context()
        if not context:
            return

        agent_name = getattr(agent, "name", str(agent))

        # Extract response content
        if isinstance(response, dict):
            content = response.get("content", str(response))
            model = response.get("model", "unknown")
            usage = response.get("usage", {})
        else:
            content = str(response)
            model = "unknown"
            usage = {}

        # Get the prompt from messages
        prompt = ""
        if hasattr(self, "_pending_llm_requests") and self._pending_llm_requests:
            # Find the most recent request from this agent
            for req_id, req_data in reversed(list(self._pending_llm_requests.items())):
                if req_data["agent_name"] == agent_name:
                    messages = req_data["messages"]
                    # Convert messages to string
                    import json

                    prompt = json.dumps(messages, indent=2)
                    del self._pending_llm_requests[req_id]
                    break

        # Emit LLM call event
        context.llm(
            model=model,
            prompt=prompt,
            response=content,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )

    def on_function_call(
        self,
        agent: Any,
        function_name: str,
        arguments: Dict[str, Any],
        result: Any,
        **kwargs,
    ) -> None:
        """
        Called when an agent executes a function/tool.

        Args:
            agent: The agent executing the function.
            function_name: Name of the function.
            arguments: Arguments passed to the function.
            result: Result returned by the function.
        """
        context = self.trace.get_active_context()
        if not context:
            return

        agent_name = getattr(agent, "name", str(agent))

        # Emit tool call event
        context.tool(
            tool_name=function_name,
            tool_args=arguments,
            tool_result=result,
            tool_type="autogen_function",
        )

    def _register_agent(self, agent: Any) -> None:
        """Register an agent if not already tracked."""
        agent_name = getattr(agent, "name", str(agent))

        if agent_name not in self._agent_registry:
            self._agent_registry[agent_name] = {
                "name": agent_name,
                "registered_at": int(time.time() * 1000),
            }

            # Emit spawn event if within active context
            context = self.trace.get_active_context()
            if context:
                context.agent_spawn(
                    agent_id=agent_name,
                    agent_name=agent_name,
                    agent_role=getattr(agent, "system_message", None),
                )


class AutoGenTracer:
    """
    Tracer for AutoGen multi-agent systems with automatic instrumentation.

    Provides a context manager that sets up AutoGen callbacks
    and manages the trace run lifecycle.
    """

    def __init__(
        self,
        trace: Optional[Trace] = None,
        run_name: str = "autogen_chat",
        track_agent_communication: bool = True,
        track_handoffs: bool = True,
        track_task_assignments: bool = True,
        **config_kwargs,
    ):
        """
        Initialize the AutoGen tracer.

        Args:
            trace: Trace instance to use (if None, uses global trace).
            run_name: Name for the trace run.
            track_agent_communication: Whether to track inter-agent messages.
            track_handoffs: Whether to track agent handoffs.
            track_task_assignments: Whether to track task assignments.
            **config_kwargs: Additional config to pass to trace.run().
        """
        self.trace = trace or get_trace()
        self.run_name = run_name
        self.track_agent_communication = track_agent_communication
        self.track_handoffs = track_handoffs
        self.track_task_assignments = track_task_assignments
        self.config_kwargs = config_kwargs
        self._callback_handler: Optional[AutoGenInspectorCallback] = None
        self._run_cm = None
        self._run_context: Optional[TraceContext] = None

    def __enter__(self):
        """Enter the tracing context."""
        # Start a trace run
        self._run_cm = self.trace.run(
            run_name=self.run_name,
            agent_type="autogen",
            **self.config_kwargs,
        )
        self._run_context = self._run_cm.__enter__()

        # Create and attach callback handler
        self._callback_handler = AutoGenInspectorCallback(
            trace=self.trace,
            run_name=self.run_name,
            track_agent_communication=self.track_agent_communication,
            track_handoffs=self.track_handoffs,
            track_task_assignments=self.track_task_assignments,
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
    run_name: str = "autogen_chat",
    track_agent_communication: bool = True,
    track_handoffs: bool = True,
    track_task_assignments: bool = True,
) -> AutoGenTracer:
    """
    Enable automatic AutoGen tracing.

    This function creates a tracer that can be used as a context manager
    to automatically trace AutoGen multi-agent execution.

    Args:
        trace: Trace instance to use (if None, uses global trace).
        run_name: Name for the trace run.
        track_agent_communication: Whether to track inter-agent messages.
        track_handoffs: Whether to track agent handoffs.
        track_task_assignments: Whether to track task assignments.

    Returns:
        AutoGenTracer context manager.

    Example:
        >>> from agent_inspector.adapters.autogen_adapter import enable
        >>>
        >>> with enable() as tracer:
        ...     # Your AutoGen code here
        ...     chat_result = user_proxy.initiate_chat(assistant, message="Hello")
    """
    return AutoGenTracer(
        trace=trace,
        run_name=run_name,
        track_agent_communication=track_agent_communication,
        track_handoffs=track_handoffs,
        track_task_assignments=track_task_assignments,
    )


def get_callback_handler(
    trace: Optional[Trace] = None,
    track_agent_communication: bool = True,
    track_handoffs: bool = True,
    track_task_assignments: bool = True,
) -> AutoGenInspectorCallback:
    """
    Get an AutoGen callback handler for manual integration.

    Use this if you want to manually add the callback handler
    to your AutoGen agents or group chats.

    Note: For proper multi-agent tracing with context management,
    use the `enable()` context manager instead.

    Args:
        trace: Trace instance to use (if None, uses global trace).
        track_agent_communication: Whether to track inter-agent messages.
        track_handoffs: Whether to track agent handoffs.
        track_task_assignments: Whether to track task assignments.

    Returns:
        AutoGenInspectorCallback instance.

    Example:
        >>> from agent_inspector.adapters.autogen_adapter import get_callback_handler
        >>>
        >>> callbacks = get_callback_handler()
        >>> # Use with your agents or group chats
        >>> groupchat = GroupChat(agents=agents, messages=[], max_round=12)
        >>> manager = GroupChatManager(groupchat=groupchat, callbacks=[callbacks])
    """
    return AutoGenInspectorCallback(
        trace=trace,
        track_agent_communication=track_agent_communication,
        track_handoffs=track_handoffs,
        track_task_assignments=track_task_assignments,
    )
