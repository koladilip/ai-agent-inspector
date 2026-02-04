"""
LangChain adapter tests using minimal fake modules.
"""

import sys
from types import ModuleType

import pytest


def _install_fake_langchain():
    lc = ModuleType("langchain")
    callbacks = ModuleType("langchain.callbacks")
    callbacks_base = ModuleType("langchain.callbacks.base")
    schema = ModuleType("langchain.schema")

    class BaseCallbackHandler:
        pass

    class AgentAction:
        def __init__(self, tool, tool_input, log):
            self.tool = tool
            self.tool_input = tool_input
            self.log = log

    class AgentFinish:
        def __init__(self, return_values):
            self.return_values = return_values

    class LLMResult:
        def __init__(self, generations, llm_output=None):
            self.generations = generations
            self.llm_output = llm_output or {}

    callbacks_base.BaseCallbackHandler = BaseCallbackHandler
    schema.AgentAction = AgentAction
    schema.AgentFinish = AgentFinish
    schema.LLMResult = LLMResult

    sys.modules["langchain"] = lc
    sys.modules["langchain.callbacks"] = callbacks
    sys.modules["langchain.callbacks.base"] = callbacks_base
    sys.modules["langchain.schema"] = schema


def test_langchain_adapter_basic_flow(monkeypatch):
    _install_fake_langchain()

    from agent_inspector.adapters.langchain_adapter import LangChainInspectorCallback
    from agent_inspector.core.trace import Trace

    trace = Trace()
    callback = LangChainInspectorCallback(trace=trace, run_name="test")

    # Start a trace context
    with trace.run("test_run") as ctx:
        # Simulate LLM start/end
        callback.on_llm_start({"name": "fake"}, ["hello"])

        class Gen:
            text = "hi"

        response = sys.modules["langchain.schema"].LLMResult(
            generations=[Gen()], llm_output={"token_usage": {"total_tokens": 5}}
        )
        callback.on_llm_end(response)

        # Simulate tool calls
        callback.on_tool_start({"name": "tool"}, "input")
        callback.on_tool_end("ok")

        # Simulate agent finish
        finish = sys.modules["langchain.schema"].AgentFinish({"output": "done"})
        callback.on_agent_finish(finish)

    assert ctx is not None


def test_langchain_adapter_error_paths(monkeypatch):
    _install_fake_langchain()

    from agent_inspector.adapters.langchain_adapter import LangChainInspectorCallback
    from agent_inspector.core.trace import Trace

    trace = Trace()
    callback = LangChainInspectorCallback(trace=trace, run_name="test")

    # No active context paths should not raise
    callback.on_llm_error(RuntimeError("llm failed"))
    callback.on_tool_error(RuntimeError("tool failed"))
    callback.on_chain_error({"name": "chain"}, RuntimeError("chain failed"))

    # Active context error emission
    with trace.run("test_run") as ctx:
        callback.on_llm_error(RuntimeError("llm failed"))
        callback.on_tool_error(RuntimeError("tool failed"))

    assert ctx is not None


def test_langchain_chain_start_end_no_context(monkeypatch):
    _install_fake_langchain()

    from agent_inspector.adapters.langchain_adapter import LangChainInspectorCallback
    from agent_inspector.core.trace import Trace

    trace = Trace()
    callback = LangChainInspectorCallback(trace=trace, run_name="test")

    callback.on_chain_start({"name": "chain"}, {"input": "x"})
    callback.on_chain_end({"name": "chain"}, {"output": "y"})


def test_langchain_streaming_token_path(monkeypatch):
    _install_fake_langchain()

    from agent_inspector.adapters.langchain_adapter import LangChainInspectorCallback
    from agent_inspector.core.trace import Trace

    trace = Trace()
    callback = LangChainInspectorCallback(trace=trace, run_name="test")
    callback.on_llm_new_token("a")


def test_langchain_tool_tracking_order(monkeypatch):
    _install_fake_langchain()

    from agent_inspector.adapters.langchain_adapter import LangChainInspectorCallback
    from agent_inspector.core.trace import Trace

    trace = Trace()
    callback = LangChainInspectorCallback(trace=trace, run_name="test")

    with trace.run("test_run") as ctx:
        callback.on_tool_start({"name": "tool1"}, "input1")
        callback.on_tool_start({"name": "tool2"}, "input2")
        callback.on_tool_end("out2")
        # Ensure still active and no crash when tool stack has multiple
        assert ctx is not None


def test_langchain_agent_action(monkeypatch):
    _install_fake_langchain()

    from agent_inspector.adapters.langchain_adapter import LangChainInspectorCallback
    from agent_inspector.core.trace import Trace

    trace = Trace()
    callback = LangChainInspectorCallback(trace=trace, run_name="test")

    with trace.run("test_run") as ctx:
        action = sys.modules["langchain.schema"].AgentAction("tool", "input", "log")
        callback.on_agent_action(action)
        assert ctx is not None


def test_langchain_tool_end_without_start(monkeypatch):
    _install_fake_langchain()

    from agent_inspector.adapters.langchain_adapter import LangChainInspectorCallback
    from agent_inspector.core.trace import Trace

    trace = Trace()
    callback = LangChainInspectorCallback(trace=trace, run_name="test")

    with trace.run("test_run"):
        # No tool_start before tool_end should not crash
        callback.on_tool_end("output")


def test_langchain_on_chain_error_with_context(monkeypatch):
    _install_fake_langchain()

    from agent_inspector.adapters.langchain_adapter import LangChainInspectorCallback
    from agent_inspector.core.trace import Trace

    trace = Trace()
    callback = LangChainInspectorCallback(trace=trace, run_name="test")

    with trace.run("test_run") as ctx:
        callback.on_chain_error({"name": "chain"}, RuntimeError("fail"))
        assert ctx is not None


def test_langchain_llm_start_without_context(monkeypatch):
    _install_fake_langchain()

    from agent_inspector.adapters.langchain_adapter import LangChainInspectorCallback
    from agent_inspector.core.trace import Trace

    trace = Trace()
    callback = LangChainInspectorCallback(trace=trace, run_name="test")
    callback.on_llm_start({"name": "fake"}, ["hello"])


def test_langchain_llm_end_without_generations(monkeypatch):
    _install_fake_langchain()

    from agent_inspector.adapters.langchain_adapter import LangChainInspectorCallback
    from agent_inspector.core.trace import Trace

    trace = Trace()
    callback = LangChainInspectorCallback(trace=trace, run_name="test")

    class Resp:
        generations = []
        llm_output = {}

    with trace.run("test_run"):
        callback.on_llm_end(Resp())


def test_langchain_tool_start_without_context(monkeypatch):
    _install_fake_langchain()

    from agent_inspector.adapters.langchain_adapter import LangChainInspectorCallback
    from agent_inspector.core.trace import Trace

    trace = Trace()
    callback = LangChainInspectorCallback(trace=trace, run_name="test")
    callback.on_tool_start({"name": "tool"}, "input")


def test_langchain_tracer_context_manager(monkeypatch):
    _install_fake_langchain()

    from agent_inspector.adapters.langchain_adapter import LangChainTracer
    from agent_inspector.core.trace import Trace

    trace = Trace()
    tracer = LangChainTracer(trace=trace, run_name="demo")
    callbacks = tracer.__enter__()
    assert callbacks is not None
    tracer.__exit__(None, None, None)


def test_langchain_enable_and_get_callback(monkeypatch):
    _install_fake_langchain()

    from agent_inspector.adapters.langchain_adapter import enable, get_callback_handler
    from agent_inspector.core.trace import Trace

    trace = Trace()
    tracer = enable(trace=trace, run_name="demo")
    assert tracer is not None
    callback = get_callback_handler(trace=trace)
    assert callback is not None
