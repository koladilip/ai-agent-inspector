"""
Real agent example for Agent Inspector.

Uses an OpenAI-compatible API (OpenAI, Azure, GLM, etc.) to run a real
tool-using agent: the model chooses a tool, we execute it locally, then
the model produces a final answer. All runs are traced.

Real-world patterns demonstrated:
- Tool selection + execution + answer (single question)
- Tool failure → error event → fallback tool → answer
- Retries (e.g. invalid JSON from LLM)
- Redaction (sensitive fields in tool args)
- Memory read/write (user preferences)
- Multi-tool sequence and parallel runs

Required environment variables:
- OPENAI_BASE_URL (e.g. https://api.openai.com/v1 or your provider)
- OPENAI_API_KEY
- OPENAI_MODEL

Optional:
- OPENAI_TEMPERATURE (default: 0.2)
- OPENAI_TIMEOUT (default: 60)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple

from agent_inspector.core.config import TraceConfig
from agent_inspector.core.trace import Trace

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def openai_chat(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    timeout_s: int = 60,
) -> Tuple[str, Dict[str, Any]]:
    """
    Call an OpenAI-compatible /chat/completions endpoint.

    Returns:
        (assistant_text, raw_response_json)
    """
    url = f"{_normalize_base_url(base_url)}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
            decoded = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP error {e.code}: {body}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"Request failed: {e}") from e

    choices = decoded.get("choices", [])
    if not choices:
        raise RuntimeError(f"No choices returned: {decoded}")

    message = choices[0].get("message", {})
    content = message.get("content", "")
    if not isinstance(content, str):
        content = str(content)

    return content, decoded


def tool_search_docs(query: str) -> Dict[str, Any]:
    """Simulate a knowledge-base / docs search (e.g. internal wiki or RAG)."""
    time.sleep(0.2)
    return {
        "query": query,
        "results": [
            {"title": "Agent Inspector Overview", "score": 0.92, "snippet": "Framework-agnostic observability for AI agents."},
            {"title": "Tracing API Reference", "score": 0.88, "snippet": "trace.run(), trace.llm(), trace.tool(), trace.final()."},
            {"title": "Storage and Retention", "score": 0.73, "snippet": "SQLite with WAL; configurable retention_days."},
        ],
    }


def tool_calculate(expression: str) -> Dict[str, Any]:
    """Safe arithmetic evaluator (e.g. for spreadsheet-style or calculator tools)."""
    import ast

    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Constant,
    )

    def _eval(node):
        if not isinstance(node, allowed_nodes):
            raise ValueError("Unsupported expression")
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise ValueError("Invalid constant")
            return node.value
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Mod):
                return left % right
            if isinstance(node.op, ast.Pow):
                return left ** right
            raise ValueError("Unsupported operator")
        if isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +operand
            if isinstance(node.op, ast.USub):
                return -operand
            raise ValueError("Unsupported unary operator")
        raise ValueError("Unsupported expression")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ValueError("Invalid expression") from e

    value = _eval(tree)
    return {"expression": expression, "value": value}


def tool_weather(city: str) -> Dict[str, Any]:
    """Simulated weather lookup (in production, call Open-Meteo or similar)."""
    time.sleep(0.1)
    return {"city": city, "forecast": "sunny", "temp_c": 22, "humidity": 65}


TOOLS = {
    "search_docs": tool_search_docs,
    "calculate": tool_calculate,
    "weather": tool_weather,
}


def choose_tool(
    prompt: str,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float,
    timeout_s: int,
):
    system = (
        "You are a tool selector. Decide the best tool and arguments.\n"
        "Return JSON only, no extra text.\n"
        "Schema: {\"tool\": \"search_docs|calculate|weather\", \"args\": {...}}\n"
        "Use calculate for arithmetic. Use weather for city weather. Use search_docs for everything else."
    )
    user = f"User question: {prompt}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    content, raw = openai_chat(base_url, api_key, model, messages, temperature, timeout_s)
    cleaned = _strip_json_fences(content)
    try:
        decision = json.loads(cleaned)
        return decision, messages, content, raw
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Tool selector returned invalid JSON: {content}") from e


def choose_tool_with_retry(
    prompt: str,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float,
    timeout_s: int,
    max_attempts: int = 2,
):
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return choose_tool(prompt, base_url, api_key, model, temperature, timeout_s)
        except Exception as e:
            last_error = e
            # Add a tiny delay before retry to simulate network hiccups
            time.sleep(0.4 + attempt * 0.6)
    raise RuntimeError(f"Tool selection failed after {max_attempts} attempts: {last_error}")


def answer_with_tool(
    prompt: str,
    tool_name: str,
    tool_result: Dict[str, Any],
    base_url: str,
    api_key: str,
    model: str,
    temperature: float,
    timeout_s: int,
):
    system = "You are a helpful agent. Use the tool result to answer concisely."
    user = f"User question: {prompt}\n\nTool used: {tool_name}\nTool result: {json.dumps(tool_result)}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    content, raw = openai_chat(base_url, api_key, model, messages, temperature, timeout_s)
    return content, messages, raw


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        # Remove optional ```json fence
        lines = cleaned.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```"):
            cleaned = "\n".join(lines[1:-1]).strip()
    # Also handle leading/trailing markdown code fences with language
    if cleaned.startswith("json"):
        cleaned = cleaned[4:].lstrip()
    return cleaned


def _run_single_question(
    trace: Trace,
    question: str,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float,
    run_name: str = "real_agent_demo",
    timeout_s: int = 60,
):
    with trace.run(run_name, agent_type="custom") as ctx:
        if ctx is None:
            print("Trace sampling skipped; set sample_rate=1.0 to force tracing.")
            return

        # 1) Choose a tool
        decision, messages, selector_response, _raw_selector = choose_tool_with_retry(
            question, base_url, api_key, model, temperature, timeout_s
        )
        ctx.llm(
            model=model,
            prompt=json.dumps(messages, ensure_ascii=False),
            response=selector_response,
        )

        tool_name = decision.get("tool")
        tool_args = decision.get("args", {})
        if tool_name not in TOOLS:
            raise RuntimeError(f"Unknown tool selected: {tool_name}")

        # 2) Call the tool
        tool_fn = TOOLS[tool_name]
        tool_result = tool_fn(**tool_args)
        ctx.tool(tool_name=tool_name, tool_args=tool_args, tool_result=tool_result)

        # 3) Produce final answer
        answer, answer_messages, _raw_answer = answer_with_tool(
            question, tool_name, tool_result, base_url, api_key, model, temperature, timeout_s
        )
        ctx.llm(
            model=model,
            prompt=json.dumps(answer_messages, ensure_ascii=False),
            response=answer,
        )
        ctx.final(answer=answer)

        print(answer)


def _suite_scenarios(
    trace: Trace,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float,
    timeout_s: int,
):
    counter = 1

    # Scenario 1: Happy path
    try:
        _run_single_question(
            trace,
            "What is 13 * (7 + 5)?",
            base_url,
            api_key,
            model,
            temperature,
            run_name=f"real_agent_demo #{counter}",
            timeout_s=timeout_s,
        )
    except Exception as e:
        print(f"Scenario 1 failed: {e}")
    counter += 1

    # Scenario 2: Tool failure → error event → fallback tool → answer (real failure)
    with trace.run("scenario_tool_failure", agent_type="custom") as ctx:
        if ctx:
            question = "What is 2 + 2 with an invalid expression?"
            decision = {"tool": "calculate", "args": {"expression": "2 + 2 + BAD"}}
            try:
                result = tool_calculate(**decision["args"])
                ctx.tool(tool_name="calculate", tool_args=decision["args"], tool_result=result)
            except Exception as e:
                ctx.tool(
                    tool_name="calculate",
                    tool_args=decision["args"],
                    tool_result={"error": str(e)},
                )
                ctx.error(error_type=type(e).__name__, error_message=str(e), critical=False)
                # Fallback: use search and let model answer
                alt_result = tool_search_docs("2 + 2 arithmetic")
                ctx.tool(
                    tool_name="search_docs",
                    tool_args={"query": "2 + 2 arithmetic"},
                    tool_result=alt_result,
                )
                answer, answer_messages, _raw_answer = answer_with_tool(
                    question,
                    "search_docs",
                    alt_result,
                    base_url,
                    api_key,
                    model,
                    temperature,
                    timeout_s,
                )
                ctx.llm(
                    model=model,
                    prompt=json.dumps(answer_messages, ensure_ascii=False),
                    response=answer,
                )
                ctx.final(answer=answer)

    # Scenario 3: Normal weather flow (shows tool selection + execution + answer)
    with trace.run("scenario_weather_flow", agent_type="custom") as ctx:
        if ctx:
            question = "What's the weather in Boston?"
            decision, messages, selector_response, _raw_selector = choose_tool_with_retry(
                question, base_url, api_key, model, temperature, timeout_s
            )
            ctx.llm(
                model=model,
                prompt=json.dumps(messages, ensure_ascii=False),
                response=selector_response,
            )
            tool_name = decision.get("tool")
            tool_args = decision.get("args", {})
            tool_result = TOOLS[tool_name](**tool_args)
            ctx.tool(tool_name=tool_name, tool_args=tool_args, tool_result=tool_result)
            answer, answer_messages, _raw_answer = answer_with_tool(
                question,
                tool_name,
                tool_result,
                base_url,
                api_key,
                model,
                temperature,
                timeout_s,
            )
            ctx.llm(
                model=model,
                prompt=json.dumps(answer_messages, ensure_ascii=False),
                response=answer,
            )
            ctx.final(answer=answer)

    # Scenario 4: Long response / larger payload
    try:
        _run_single_question(
            trace,
            "Summarize Agent Inspector in 5 bullets, and include a short example.",
            base_url,
            api_key,
            model,
            temperature,
            run_name=f"real_agent_demo #{counter}",
            timeout_s=timeout_s,
        )
    except Exception as e:
        print(f"Scenario 4 failed: {e}")
    counter += 1

    # Scenario 5: Redaction – sensitive keys in tool args are redacted in storage
    with trace.run("scenario_redaction", agent_type="custom") as ctx:
        if ctx:
            tool_args = {"query": "api_key=sk-test-123 password=secret"}
            tool_result = tool_search_docs(tool_args["query"])
            ctx.tool(tool_name="search_docs", tool_args=tool_args, tool_result=tool_result)
            answer, answer_messages, _raw_answer = answer_with_tool(
                "Find docs about API keys.",
                "search_docs",
                tool_result,
                base_url,
                api_key,
                model,
                temperature,
                timeout_s,
            )
            ctx.llm(
                model=model,
                prompt=json.dumps(answer_messages, ensure_ascii=False),
                response=answer,
            )
            ctx.final(answer=answer)

    # Scenario 6: Memory – user preferences (e.g. default city) read/write
    with trace.run("scenario_memory_ops", agent_type="custom") as ctx:
        if ctx:
            ctx.memory_write(
                memory_key="user_pref_city",
                memory_value={"city": "Seattle"},
                memory_type="key_value",
                overwrite=True,
            )
            ctx.memory_read(
                memory_key="user_pref_city",
                memory_value={"city": "Seattle"},
                memory_type="key_value",
            )
            answer = "Stored and retrieved user preference."
            ctx.final(answer=answer)

    # Scenario 7: Multi-tool sequence – search then calculate in one run
    with trace.run("scenario_nested_tools", agent_type="custom") as ctx:
        if ctx:
            first = tool_search_docs("Agent Inspector retention policy")
            ctx.tool(
                tool_name="search_docs",
                tool_args={"query": "Agent Inspector retention policy"},
                tool_result=first,
            )
            second = tool_calculate("15 * 3")
            ctx.tool(
                tool_name="calculate",
                tool_args={"expression": "15 * 3"},
                tool_result=second,
            )
            answer = "Combined docs lookup with a quick calculation."
            ctx.final(answer=answer)

    # Scenario 8: Parallel runs – concurrent requests (e.g. multiple users)
    def _parallel_run(idx: int):
        try:
            _run_single_question(
                trace,
                f"Run {idx}: What's 9 * 9?",
                base_url,
                api_key,
                model,
                temperature,
                run_name=f"real_agent_demo #{counter + idx}",
                timeout_s=timeout_s,
            )
        except Exception as e:
            print(f"Parallel run {idx} failed: {e}")

    threads = [threading.Thread(target=_parallel_run, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def main() -> int:
    if load_dotenv:
        load_dotenv()

    try:
        base_url = _require_env("OPENAI_BASE_URL")
        api_key = _require_env("OPENAI_API_KEY")
        model = _require_env("OPENAI_MODEL")
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
    timeout_s = int(os.getenv("OPENAI_TIMEOUT", "60"))

    trace = Trace(
        config=TraceConfig(
            sample_rate=1.0,
            compression_enabled=False,
            encryption_enabled=False,
        )
    )

    parser = argparse.ArgumentParser(description="Agent Inspector real agent demo")
    parser.add_argument("--suite", action="store_true", help="Run full scenario suite")
    parser.add_argument("question", nargs="*", help="Single question to ask")
    args = parser.parse_args()

    if args.suite:
        _suite_scenarios(trace, base_url, api_key, model, temperature, timeout_s)
    else:
        question = " ".join(args.question).strip() or "What is 13 * (7 + 5)?"
        _run_single_question(trace, question, base_url, api_key, model, temperature, timeout_s=timeout_s)

    trace.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
