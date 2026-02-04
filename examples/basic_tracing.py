"""
Basic Tracing Example for Agent Inspector.

This example demonstrates how to use the Agent Inspector to trace
agent execution using the simple API.

No external frameworks required - just pure Python!
"""

import time

from agent_inspector import TraceConfig, trace


def example_basic_tracing():
    """Demonstrate basic tracing of an agent execution."""
    # Configure global tracing to sample all runs for this demo
    from agent_inspector.core.config import set_config

    set_config(TraceConfig(sample_rate=1.0))

    # Start a trace run
    with trace.run("flight_search_agent") as _:
        # Simulate agent thinking/decision making
        time.sleep(0.1)

        # LLM call - Agent decides which tool to use
        trace.llm(
            model="gpt-4",
            prompt="User wants to find flights from SFO to JFK on March 15th. "
            "Which tool should I use?",
            response="I should use the search_flights tool to find available flights.",
            prompt_tokens=25,
            completion_tokens=18,
            total_tokens=43,
        )

        time.sleep(0.05)

        # Tool call - Search for flights
        trace.tool(
            tool_name="search_flights",
            tool_args={
                "origin": "SFO",
                "destination": "JFK",
                "date": "2024-03-15",
                "passengers": 1,
            },
            tool_result={
                "flights": [
                    {
                        "airline": "Delta",
                        "flight": "DL123",
                        "price": "$350",
                        "duration": "5h 30m",
                    },
                    {
                        "airline": "United",
                        "flight": "UA456",
                        "price": "$320",
                        "duration": "5h 15m",
                    },
                    {
                        "airline": "American",
                        "flight": "AA789",
                        "price": "$340",
                        "duration": "5h 20m",
                    },
                ],
                "total": 3,
            },
            tool_type="search",
        )

        time.sleep(0.05)

        # Memory read - Check for user preferences
        trace.memory_read(
            memory_key="user_preferences",
            memory_value={
                "preferred_airlines": ["Delta", "United"],
                "max_price": "$400",
                "seating_preference": "window",
            },
            memory_type="key_value",
        )

        time.sleep(0.1)

        # LLM call - Agent processes results
        trace.llm(
            model="gpt-4",
            prompt="Found 3 flights. User prefers Delta or United, max price $400. "
            "Results:\n- Delta DL123: $350\n- United UA456: $320\n- American AA789: $340\n"
            "Which flight should I recommend?",
            response="I recommend United UA456 for $320. "
            "It's the cheapest option and United is one of the user's preferred airlines.",
            prompt_tokens=65,
            completion_tokens=28,
            total_tokens=93,
        )

        time.sleep(0.05)

        # Memory write - Store user's choice for future reference
        trace.memory_write(
            memory_key="last_search",
            memory_value={
                "route": "SFO-JFK",
                "date": "2024-03-15",
                "chosen_flight": "UA456",
                "timestamp": time.time(),
            },
            memory_type="key_value",
            overwrite=True,
        )

        time.sleep(0.05)

        # Final answer - Agent provides result to user
        trace.final(
            answer="I found 3 flights from SFO to JFK on March 15th. "
            "Based on your preferences, I recommend United Flight UA456 for $320. "
            "It's the cheapest option and United is one of your preferred airlines. "
            "The flight duration is 5 hours 15 minutes.",
        )

    print("✅ Trace completed successfully!")
    print("📊 View the trace in the UI at http://localhost:8000/ui")


def example_with_custom_config():
    """Demonstrate tracing with custom configuration."""
    from agent_inspector import TraceConfig

    # Create custom configuration
    config = TraceConfig(
        sample_rate=1.0,  # Trace all runs
        redact_keys=["password", "secret"],  # Redact sensitive keys
        compression_enabled=True,  # Compress data before storage
        log_level="DEBUG",  # Verbose logging
    )

    # Use custom config
    with trace.run("config_demo", config=config):
        trace.llm(
            model="gpt-3.5-turbo",
            prompt="Hello!",
            response="Hi there!",
        )

        trace.tool(
            tool_name="calculator",
            tool_args={"operation": "add", "a": 2, "b": 3},
            tool_result=5,
        )

        trace.final(answer="The result is 5!")

    print("✅ Custom config trace completed!")


def example_with_error_handling():
    """Demonstrate error handling in traces."""
    # Set global config to sample all runs
    from agent_inspector.core.config import set_config

    set_config(TraceConfig(sample_rate=1.0))

    with trace.run("error_demo"):
        try:
            # Simulate a successful LLM call
            trace.llm(
                model="gpt-4",
                prompt="What is 2+2?",
                response="2+2 equals 4",
            )

            time.sleep(0.1)

            # Simulate a tool failure
            trace.tool(
                tool_name="broken_tool",
                tool_args={"input": "test"},
                tool_result="Error: Tool is not responding",
            )

            # Emit an error event
            trace.error(
                error_type="ToolError",
                error_message="The broken_tool failed to respond",
                critical=False,
            )

            # Continue with another tool that works
            trace.tool(
                tool_name="working_tool",
                tool_args={"input": "test"},
                tool_result={"result": "success"},
            )

            # Provide final answer despite error
            trace.final(
                answer="I encountered an error with one tool, but was able to complete "
                "the request using an alternative method.",
                success=True,
            )

        except Exception as e:
            # Catch and log unexpected errors
            trace.error(
                error_type=type(e).__name__,
                error_message=str(e),
                critical=True,
            )
            raise

    print("✅ Error handling trace completed!")


def example_nested_runs():
    """Demonstrate nested trace contexts (sub-tasks)."""
    # Set global config to sample all runs
    from agent_inspector.core.config import set_config

    set_config(TraceConfig(sample_rate=1.0))

    # Main agent run
    with trace.run("main_agent", user_id="user123") as _:
        print("📝 Main agent starting...")

        # Agent decides to call a sub-agent
        trace.llm(
            model="gpt-4",
            prompt="User wants to book a flight. Should I delegate to booking agent?",
            response="Yes, delegate to the booking sub-agent.",
        )

        time.sleep(0.1)

        # Sub-agent run (nested)
        with trace.run(
            "booking_subagent", user_id="user123", session_id="booking_session_456"
        ) as _:
            print("📝 Sub-agent starting...")

            # Sub-agent processes booking
            trace.llm(
                model="gpt-4",
                prompt="Book United flight UA456",
                response="Proceeding to book UA456...",
            )

            time.sleep(0.1)

            trace.tool(
                tool_name="book_flight",
                tool_args={
                    "flight_id": "UA456",
                    "passenger_name": "John Doe",
                },
                tool_result={
                    "confirmation": "CONF-12345",
                    "status": "confirmed",
                },
            )

            trace.final(
                answer="Flight UA456 booked successfully! Confirmation: CONF-12345"
            )

        print("📝 Sub-agent completed!")

        # Main agent continues
        time.sleep(0.1)

        trace.llm(
            model="gpt-4",
            prompt="Sub-agent booked flight UA456. What should I tell the user?",
            response="Inform the user that the flight was successfully booked "
            "and provide the confirmation number.",
        )

        trace.final(
            answer="I've successfully booked your flight! "
            "United Flight UA456 has been confirmed. "
            "Your confirmation number is CONF-12345."
        )

    print("✅ Nested runs completed!")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Agent Inspector - Basic Tracing Examples")
    print("=" * 60 + "\n")

    # Run examples
    print("\n📌 Example 1: Basic Tracing")
    print("-" * 60)
    example_basic_tracing()
    print()

    print("\n📌 Example 2: Custom Configuration")
    print("-" * 60)
    example_with_custom_config()
    print()

    print("\n📌 Example 3: Error Handling")
    print("-" * 60)
    example_with_error_handling()
    print()

    print("\n📌 Example 4: Nested Runs")
    print("-" * 60)
    example_nested_runs()
    print()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)
    print("\n💡 Tip: Run the API server to view traces in the UI:")
    print("   python -m agent_inspector.cli server")
    print("   Then visit: http://localhost:8000/ui\n")

    # Shutdown to flush events to database
    print("💾 Flushing events to database...")
    from agent_inspector import get_trace

    get_trace().shutdown()
    print("✅ Done! Traces are now stored in the database.")
