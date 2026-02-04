"""
Basic Tracing Example for Agent Inspector.

No external APIs or LLM calls – these examples simulate the trace events
a real agent would emit. In production, replace with your actual LLM and tools.

Run: python examples/basic_tracing.py
Then view traces at http://localhost:8000/ui (start server with: agent-inspector server)
"""

import time

from agent_inspector import TraceConfig, trace


def example_order_status_agent():
    """
    Real-world pattern: Order status lookup agent.

    Simulates an agent that looks up an order, checks inventory, and
    returns a customer-facing status. Typical of support or e-commerce bots.
    """
    from agent_inspector.core.config import set_config

    set_config(TraceConfig(sample_rate=1.0))

    order_id = "ORD-7842"
    customer_id = "cust_9f2a"

    with trace.run("order_status_agent", user_id=customer_id) as _:
        # Step 1: LLM decides which tool to call
        trace.llm(
            model="gpt-4",
            prompt=f"Customer asks: 'Where is my order {order_id}?' Decide tool.",
            response="Use get_order_status with order_id.",
            prompt_tokens=28,
            completion_tokens=12,
            total_tokens=40,
        )
        time.sleep(0.05)

        # Step 2: Tool – fetch order from backend (simulated)
        trace.tool(
            tool_name="get_order_status",
            tool_args={"order_id": order_id},
            tool_result={
                "order_id": order_id,
                "status": "shipped",
                "carrier": "UPS",
                "tracking": "1Z999AA10123456784",
                "estimated_delivery": "2024-03-18",
            },
            tool_type="api",
        )
        time.sleep(0.05)

        # Step 3: LLM formats reply for customer
        trace.llm(
            model="gpt-4",
            prompt="Format a short, friendly reply for the customer using the order data.",
            response=f"Your order {order_id} has shipped via UPS. Track it: 1Z999...784. Estimated delivery March 18.",
            prompt_tokens=45,
            completion_tokens=32,
            total_tokens=77,
        )

        trace.final(
            answer=f"Your order {order_id} has shipped via UPS (tracking 1Z999...784). Estimated delivery March 18."
        )

    print("✅ Order status trace completed.")


def example_rag_style_qa():
    """
    Real-world pattern: RAG-style Q&A (retrieve chunk, then answer).

    Simulates: retrieve relevant doc chunks from a vector store, then
    one LLM call to synthesize the final answer.
    """
    from agent_inspector.core.config import set_config

    set_config(TraceConfig(sample_rate=1.0))

    query = "What is the return policy for electronics?"

    with trace.run("rag_qa_agent", agent_type="rag") as _:
        # Retrieve step (simulated vector search)
        trace.tool(
            tool_name="retrieve_chunks",
            tool_args={"query": query, "top_k": 3},
            tool_result={
                "chunks": [
                    "Electronics may be returned within 30 days with receipt.",
                    "Refunds are processed within 5–7 business days.",
                    "Opened software and certain items are non-returnable.",
                ],
            },
            tool_type="search",
        )
        time.sleep(0.05)

        trace.llm(
            model="gpt-4",
            prompt=f"Query: {query}\n\nContext:\n" + "\n".join([
                "Electronics: 30-day return with receipt.",
                "Refunds: 5–7 business days.",
                "Some items non-returnable.",
            ]) + "\n\nAnswer concisely.",
            response="Electronics can be returned within 30 days with a receipt. Refunds take 5–7 business days. Some items are non-returnable.",
        )

        trace.final(
            answer="Electronics can be returned within 30 days with a receipt. Refunds take 5–7 business days. Some items are non-returnable."
        )

    print("✅ RAG Q&A trace completed.")


def example_error_handling_and_fallback():
    """
    Real-world pattern: Tool failure → log error → fallback path.

    Simulates a primary tool failing (e.g. timeout, rate limit), error
    emission for observability, then fallback tool to complete the run.
    """
    from agent_inspector.core.config import set_config

    set_config(TraceConfig(sample_rate=1.0))

    with trace.run("support_agent_with_fallback") as _:
        trace.llm(
            model="gpt-4",
            prompt="User asked for account balance. Which tool?",
            response="Use get_balance.",
        )
        time.sleep(0.05)

        # Primary tool fails (e.g. core service timeout)
        trace.tool(
            tool_name="get_balance",
            tool_args={"account_id": "acc_123"},
            tool_result="Error: upstream timeout after 5s",
        )
        trace.error(
            error_type="ToolError",
            error_message="get_balance failed: upstream timeout after 5s",
            critical=False,
        )
        time.sleep(0.05)

        # Fallback: cached or degraded path
        trace.tool(
            tool_name="get_balance_cached",
            tool_args={"account_id": "acc_123"},
            tool_result={"balance": 1250.00, "as_of": "2024-03-15T10:00:00Z", "cached": True},
        )

        trace.llm(
            model="gpt-4",
            prompt="Use balance (possibly cached) to reply.",
            response="Your balance is $1,250.00 (as of this morning). Live service was briefly unavailable.",
        )
        trace.final(
            answer="Your balance is $1,250.00 as of this morning. We had a brief delay; the value may be cached.",
            success=True,
        )

    print("✅ Error handling trace completed.")


def example_custom_config():
    """
    Real-world pattern: Dev vs prod – trace everything in dev,
    redact PII/sensitive keys, use custom DB path.
    """
    config = TraceConfig(
        sample_rate=1.0,
        redact_keys=["password", "secret", "api_key", "token"],
        db_path="agent_inspector_dev.db",
        log_level="DEBUG",
    )

    with trace.run("config_demo", config=config):
        trace.llm(
            model="gpt-3.5-turbo",
            prompt="User (api_key=sk-xxx) asked: What's 2+2?",
            response="4",
        )
        trace.tool(
            tool_name="calculator",
            tool_args={"expression": "2 + 2"},
            tool_result=4,
        )
        trace.final(answer="2 + 2 = 4")

    print("✅ Custom config trace completed.")


def example_nested_agents():
    """
    Real-world pattern: Orchestrator delegates to specialist sub-agent.

    Main agent decides "book hotel"; booking sub-agent calls tools
    and returns; main agent summarizes for the user.
    """
    from agent_inspector.core.config import set_config

    set_config(TraceConfig(sample_rate=1.0))

    with trace.run("orchestrator", user_id="user_abc") as _:
        trace.llm(
            model="gpt-4",
            prompt="User wants to book a hotel in Seattle. Delegate?",
            response="Delegate to booking specialist.",
        )
        time.sleep(0.05)

        with trace.run("booking_specialist", session_id="sess_xyz"):
            trace.tool(
                tool_name="search_hotels",
                tool_args={"city": "Seattle", "check_in": "2024-04-01", "nights": 2},
                tool_result={
                    "hotels": [
                        {"name": "Hotel A", "price": 180},
                        {"name": "Hotel B", "price": 220},
                    ],
                },
            )
            trace.tool(
                tool_name="reserve_room",
                tool_args={"hotel_id": "Hotel A", "confirmation": "CONF-8899"},
                tool_result={"status": "confirmed", "confirmation": "CONF-8899"},
            )
            trace.final(answer="Booked Hotel A. Confirmation: CONF-8899.")

        trace.llm(
            model="gpt-4",
            prompt="Booking specialist confirmed. Summarize for user.",
            response="Your Seattle stay is confirmed. Confirmation: CONF-8899.",
        )
        trace.final(
            answer="Your Seattle hotel is booked. Confirmation number: CONF-8899."
        )

    print("✅ Nested agents trace completed.")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Agent Inspector – Basic tracing (real-world patterns)")
    print("=" * 60 + "\n")

    print("\n📌 1. Order status agent")
    print("-" * 60)
    example_order_status_agent()

    print("\n📌 2. RAG-style Q&A")
    print("-" * 60)
    example_rag_style_qa()

    print("\n📌 3. Error handling and fallback")
    print("-" * 60)
    example_error_handling_and_fallback()

    print("\n📌 4. Custom config (redaction, db path)")
    print("-" * 60)
    example_custom_config()

    print("\n📌 5. Nested agents (orchestrator + specialist)")
    print("-" * 60)
    example_nested_agents()

    print("\n" + "=" * 60)
    print("All examples completed.")
    print("=" * 60)
    print("\n💡 View traces: agent-inspector server → http://localhost:8000/ui\n")

    from agent_inspector import get_trace
    get_trace().shutdown()
    print("✅ Events flushed to database.")
