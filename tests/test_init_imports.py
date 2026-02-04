"""
Tests for optional imports in agent_inspector.__init__.
"""

import builtins
import importlib
import sys
from types import ModuleType


def _reload_agent_inspector():
    sys.modules.pop("agent_inspector", None)
    return importlib.import_module("agent_inspector")


def test_init_without_fastapi(monkeypatch):
    orig_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("fastapi") or name.startswith("agent_inspector.api.main"):
            raise ImportError("no fastapi")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    sys.modules.pop("agent_inspector.api.main", None)
    mod = _reload_agent_inspector()
    assert mod.run_server is None
    assert mod.get_api_server is None


def test_init_without_langchain(monkeypatch):
    orig_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("langchain"):
            raise ImportError("no langchain")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    mod = _reload_agent_inspector()
    assert mod.enable_langchain is None


def test_init_with_fake_langchain(monkeypatch):
    # Provide minimal fake langchain modules so adapter import succeeds
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

    mod = _reload_agent_inspector()
    assert mod.enable_langchain is not None


def test_global_trace_proxy():
    mod = _reload_agent_inspector()
    # Accessing attributes should go through __getattr__
    run_attr = getattr(mod.trace, "run")
    assert callable(run_attr)
