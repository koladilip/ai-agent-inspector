"""
LangChain adapter for Agent Inspector.

Provides automatic tracing of LangChain agents without any code changes.
Captures LLM calls, tool calls, and memory operations automatically.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Union

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import AgentAction, AgentFinish, LLMResult

from ..core.trace import Trace, get_trace

logger = logging.getLogger(__name__)


class LangChainInspectorCallback(BaseCallbackHandler):
    """
    LangChain callback handler for automatic tracing.

    Captures all LLM calls, tool calls, and agent actions
    and emits them as Agent Inspector events.
    """

    def __init__(self, trace: Optional[Trace] = None, run_name: Optional[str] = None):
        """
        Initialize the LangChain callback handler.

        Args:
            trace: Trace instance to use (if None, uses global trace).
            run_name: Optional name for the run (defaults to auto-generated).
        """
        self.trace = trace or get_trace()
        self.run_name = run_name
        self._run_context = None
        self._llm_calls: Dict[str, Dict[str, Any]] = {}  # Track active LLM calls
        self._tool_calls: Dict[str, Dict[str, Any]] = {}  # Track active tool calls
        self._token_buffers: Dict[str, List[str]] = {}  # For streaming LLMs

        # Enable all callbacks
        self.always_verbose = True
        logger.debug("LangChainInspectorCallback initialized")

    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs
    ) -> None:
        """Called when a chain starts running."""
        logger.debug(f"Chain started: {serialized.get('name', 'unknown')}")

    def on_chain_end(
        self, serialized: Dict[str, Any], outputs: Dict[str, Any], **kwargs
    ) -> None:
        """Called when a chain finishes running."""
        logger.debug(f"Chain ended: {serialized.get('name', 'unknown')}")

    def on_chain_error(
        self,
        serialized: Dict[str, Any],
        error: Union[Exception, KeyboardInterrupt],
        **kwargs,
    ) -> None:
        """Called when a chain raises an error."""
        logger.error(f"Chain error in {serialized.get('name', 'unknown')}: {error}")

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs
    ) -> None:
        """
        Called when LLM starts running.

        Args:
            serialized: Serialized LLM object.
            prompts: List of prompts sent to LLM.
        """
        llm_name = serialized.get("name", "unknown")
        model = kwargs.get("invocation_params", {}).get("model", llm_name)

        # Get the active trace context
        context = self.trace.get_active_context()
        if not context:
            logger.warning("No active trace context for LLM call")
            return

        prompt = prompts[0] if prompts else ""

        # Track this LLM call with a unique ID based on current timestamp
        llm_call_id = f"llm_{int(time.time() * 1000000)}_{len(self._llm_calls)}"
        self._llm_calls[llm_call_id] = {
            "prompt": prompt,
            "model": model,
            "started_at": int(time.time() * 1000),
        }

        logger.debug(f"LLM call started: {model} with prompt length {len(prompt)}")

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """
        Called when a new token is generated (streaming).

        Args:
            token: The new token.
        """
        # For streaming LLMs, we could capture tokens here
        # This would require the streaming LLM support feature
        pass

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """
        Called when LLM finishes running.

        Args:
            response: LLM result containing generations and token counts.
        """
        context = self.trace.get_active_context()
        if not context:
            return

        # Extract response details
        generations = response.generations
        if not generations:
            return

        # Get the first generation
        generation = generations[0]
        response_text = generation.text if hasattr(generation, "text") else ""

        # Get token usage info if available
        llm_output = response.llm_output or {}
        token_usage = llm_output.get("token_usage", {})

        prompt_tokens = token_usage.get("prompt_tokens")
        completion_tokens = token_usage.get("completion_tokens")
        total_tokens = token_usage.get("total_tokens")

        # Retrieve tracked LLM call info from the most recent call
        model_name = "unknown"
        prompt_text = ""
        if self._llm_calls:
            # Get the most recent LLM call
            most_recent_id = max(
                self._llm_calls.keys(),
                key=lambda k: self._llm_calls[k].get("started_at", 0),
            )
            tracked_call = self._llm_calls.get(most_recent_id, {})
            model_name = tracked_call.get("model", "unknown")
            prompt_text = tracked_call.get("prompt", "")
            # Clean up tracked call
            del self._llm_calls[most_recent_id]

        # Create LLM call event with complete information
        context.llm(
            model=model_name,
            prompt=prompt_text,
            response=response_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    def on_llm_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs
    ) -> None:
        """Called when LLM raises an error."""
        context = self.trace.get_active_context()
        if context:
            context.error(
                error_type=type(error).__name__,
                error_message=str(error),
            )

    def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs
    ) -> None:
        """
        Called when a tool starts running.

        Args:
            serialized: Serialized tool object.
            input_str: String input to the tool.
        """
        tool_name = serialized.get("name", "unknown")

        context = self.trace.get_active_context()
        if not context:
            logger.warning("No active trace context for tool call")
            return

        # Track this tool call
        tool_call_id = f"{tool_name}_{len(self._tool_calls)}"
        self._tool_calls[tool_call_id] = {
            "name": tool_name,
            "input": input_str,
        }

    def on_tool_end(self, output: str, **kwargs) -> None:
        """
        Called when a tool finishes running.

        Args:
            output: Output from the tool.
        """
        context = self.trace.get_active_context()
        if not context:
            return

        # We need to get the tool name from the last tracked call
        # This is a limitation of the LangChain callback system
        # In a real implementation, we'd need better tracking
        last_tool_id = None
        if self._tool_calls:
            last_tool_id = list(self._tool_calls.keys())[-1]

        if last_tool_id:
            tool_info = self._tool_calls[last_tool_id]
            tool_name = tool_info["name"]

            # Parse input (it's a string representation of kwargs)
            tool_args = {"input": tool_info["input"]}

            # Create tool call event
            context.tool(
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=output,
            )

            # Remove from tracking
            del self._tool_calls[last_tool_id]

    def on_tool_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs
    ) -> None:
        """Called when a tool raises an error."""
        context = self.trace.get_active_context()
        if context:
            context.error(
                error_type=type(error).__name__,
                error_message=str(error),
            )

    def on_agent_action(self, action: AgentAction, **kwargs) -> None:
        """
        Called when an agent takes an action.

        Args:
            action: The action taken by the agent.
        """
        context = self.trace.get_active_context()
        if context:
            # Log the agent's reasoning/action
            context.tool(
                tool_name="agent_action",
                tool_args={
                    "tool": action.tool,
                    "tool_input": action.tool_input,
                    "log": action.log,
                },
                tool_result="pending",
            )

    def on_agent_finish(self, finish: AgentFinish, **kwargs) -> None:
        """
        Called when an agent finishes.

        Args:
            finish: The finish state including return values and logs.
        """
        context = self.trace.get_active_context()
        if context:
            # Extract the final answer
            output = finish.return_values
            answer = str(output.get("output", output)) if output else ""

            # Create final answer event
            context.final(answer=answer)

    def on_text(self, text: str, **kwargs) -> None:
        """Called when arbitrary text is output."""
        pass  # We don't trace arbitrary text output


class LangChainTracer:
    """
    Tracer for LangChain agents with automatic instrumentation.

    Provides a context manager that sets up LangChain callbacks
    and manages the trace run lifecycle.
    """

    def __init__(
        self,
        trace: Optional[Trace] = None,
        agent_type: str = "langchain",
        **config_kwargs,
    ):
        """
        Initialize the LangChain tracer.

        Args:
            trace: Trace instance to use (if None, uses global trace).
            agent_type: Type identifier for the agent.
            **config_kwargs: Additional config to pass to trace.run().
        """
        self.trace = trace or get_trace()
        self.agent_type = agent_type
        self.config_kwargs = config_kwargs
        self._callback_handler: Optional[LangChainInspectorCallback] = None

    def __enter__(self):
        """Enter the tracing context."""
        # Start a trace run
        run_name = self.config_kwargs.pop("run_name", "langchain_agent")

        self._run_cm = self.trace.run(
            run_name=run_name,
            agent_type=self.agent_type,
            **self.config_kwargs,
        )
        self._run_context = self._run_cm.__enter__()

        # Create and attach callback handler
        self._callback_handler = LangChainInspectorCallback(
            trace=self.trace,
            run_name=run_name,
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
    trace: Optional[Trace] = None, run_name: str = "langchain_agent"
) -> LangChainTracer:
    """
    Enable automatic LangChain tracing.

    This function creates a tracer that can be used as a context manager
    to automatically trace LangChain agent execution.

    Args:
        trace: Trace instance to use (if None, uses global trace).
        run_name: Name for the trace run.

    Returns:
        LangChainTracer context manager.

    Example:
        >>> from langchain.agents import initialize_agent, Tool, AgentType
        >>> from agent_inspector.adapters.langchain_adapter import enable
        >>>
        >>> # Initialize your LangChain agent
        >>> agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION)
        >>>
        >>> # Use with automatic tracing
        >>> with enable() as callbacks:
        ...     result = agent.run("Search for flights to New York")
        >>>     print(result)
    """
    return LangChainTracer(trace=trace, run_name=run_name)


def get_callback_handler(trace: Optional[Trace] = None) -> LangChainInspectorCallback:
    """
    Get a LangChain callback handler for manual integration.

    Use this if you want to manually add the callback handler
    to your LangChain chains.

    Args:
        trace: Trace instance to use (if None, uses global trace).

    Returns:
        LangChainInspectorCallback instance.

    Example:
        >>> from langchain.chains import LLMChain
        >>> from agent_inspector.adapters.langchain_adapter import get_callback_handler
        >>>
        >>> # Get callback handler
        >>> callbacks = [get_callback_handler()]
        >>>
        >>> # Use with your chains
        >>> chain = LLMChain(llm=llm, prompt=prompt)
        >>> result = chain.run("Hello", callbacks=callbacks)
    """
    return LangChainInspectorCallback(trace=trace)
