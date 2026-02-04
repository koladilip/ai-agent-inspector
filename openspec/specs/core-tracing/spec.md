# core-tracing Specification

## Purpose

Provide a framework-agnostic trace SDK for AI agents that captures reasoning, tool usage, and execution flow. The system must be non-blocking, efficient, and minimal in overhead to ensure agent performance is never impacted.

## Requirements

### Requirement: Trace context management

The system SHALL provide a context manager interface for wrapping agent execution runs.

#### Scenario: Start a trace run

- GIVEN a developer wants to trace an agent execution
- WHEN they invoke `trace.run("run_name")` as a context manager
- THEN a unique run_id SHALL be generated
- AND the run SHALL be tracked with a start timestamp
- AND a `run_start` event SHALL be emitted

#### Scenario: Nested trace context

- GIVEN an agent invokes another agent
- WHEN a new trace.run() is called within an existing trace
- THEN the run_id SHALL remain the same for the parent context
- AND a nested context SHALL track the sub-execution
- AND events SHALL be associated with the parent run_id

### Requirement: Event emission

The system SHALL provide methods for emitting different event types during agent execution.

#### Scenario: LLM call event

- GIVEN an agent calls an LLM
- WHEN `trace.llm(prompt="...", response="...")` is invoked
- THEN an `llm_call` event SHALL be created
- AND the event SHALL include prompt, response, model name, and duration
- AND the event SHALL be queued for processing

#### Scenario: Tool call event

- GIVEN an agent invokes a tool
- WHEN `trace.tool(name="search", args={...}, result="...")` is called
- THEN a `tool_call` event SHALL be created
- AND the event SHALL include tool name, arguments, result, and duration
- AND the event SHALL be queued for processing

#### Scenario: Memory operations

- GIVEN an agent reads from memory
- WHEN `trace.memory_read(key="...", value="...")` is invoked
- THEN a `memory_read` event SHALL be created
- AND the event SHALL include the memory key and retrieved value

- GIVEN an agent writes to memory
- WHEN `trace.memory_write(key="...", value="...")` is invoked
- THEN a `memory_write` event SHALL be created
- AND the event SHALL include the memory key and stored value

#### Scenario: Error event

- GIVEN an agent execution fails
- WHEN `trace.error(message="...", exception=...)` is called
- THEN an `error` event SHALL be created
- AND the event SHALL include the error message, exception type, and stack trace
- AND the event SHALL be marked as critical

#### Scenario: Final answer event

- GIVEN an agent completes execution with a result
- WHEN `trace.final(answer="...")` is called
- THEN a `final_answer` event SHALL be created
- AND the event SHALL include the final answer
- AND the run SHALL be marked as completed

### Requirement: Event model schema

The system SHALL use a consistent JSON schema for all events.

#### Scenario: Event structure validation

- GIVEN an event is created
- WHEN the event is serialized
- THEN the JSON SHALL contain: run_id, timestamp, type, name (if applicable), input, output, duration_ms, and metadata
- AND all fields SHALL be JSON-serializable
- AND timestamps SHALL be in ISO 8601 format or Unix epoch milliseconds

#### Scenario: Run ID generation

- GIVEN a new trace run is started
- WHEN the run_id is generated
- THEN the run_id SHALL be a UUID v4
- AND the run_id SHALL be unique across all runs

### Requirement: Non-blocking event queue

The system SHALL provide an in-memory queue that never blocks agent execution.

#### Scenario: Queue event submission

- GIVEN an event needs to be queued
- WHEN `queue.put_nowait(event)` is called
- THEN the event SHALL be added to the queue
- AND the method SHALL return immediately
- AND agent execution SHALL NOT be blocked

#### Scenario: Queue overflow handling

- GIVEN the queue is full (maxsize=1000)
- WHEN a new event is submitted
- THEN the event SHALL be dropped
- AND no exception SHALL be raised
- AND agent execution SHALL continue without interruption
- AND a warning SHALL be logged for monitoring

#### Scenario: Queue capacity configuration

- GIVEN a TraceConfig is initialized
- WHEN `queue_size=2000` is specified
- THEN the queue SHALL have a maximum capacity of 2000 events
- AND the default queue size SHALL be 1000

### Requirement: Background event processor

The system SHALL run a background thread that processes queued events in batches.

#### Scenario: Batch collection

- GIVEN events are in the queue
- WHEN the background processor runs
- THEN events SHALL be collected in batches
- AND the batch size SHALL be configurable (default: 50 events)
- OR the batch SHALL be flushed after a timeout (default: 1 second)

#### Scenario: Worker thread lifecycle

- GIVEN the tracer is initialized
- WHEN the first trace.run() is called
- THEN a background daemon thread SHALL be started
- AND the thread SHALL run until the process exits
- AND the thread SHALL be a daemon to not prevent process shutdown

#### Scenario: Exporter invocation

- GIVEN a batch of events is collected
- WHEN the batch is ready to be processed
- THEN the batch SHALL be passed to the configured exporter
- AND the exporter SHALL handle compression, encryption, and storage
- AND any exporter errors SHALL be logged without crashing the worker

### Requirement: Sampling support

The system SHALL support sampling to reduce volume in high-traffic scenarios.

#### Scenario: Configurable sampling rate

- GIVEN a TraceConfig specifies `sample_rate=0.1`
- WHEN 100 agent runs are executed
- THEN approximately 10 runs SHALL be traced
- AND the selection SHALL be deterministic based on run_id

#### Scenario: Error-only sampling

- GIVEN a TraceConfig specifies `only_on_error=True`
- WHEN an agent run completes successfully
- THEN the run SHALL NOT be traced
- WHEN an agent run encounters an error
- THEN the run SHALL be traced in full

### Requirement: Performance overhead

The system SHALL impose minimal overhead on agent execution.

#### Scenario: Queue operation latency

- GIVEN an event is emitted
- WHEN the event is queued
- THEN the `put_nowait` operation SHALL complete in less than 100 microseconds
- AND the operation SHALL NOT allocate memory after initial queue setup

#### Scenario: Event creation overhead

- GIVEN a trace.llm() call is made
- WHEN the event is created and queued
- THEN the total operation SHALL complete in less than 1 millisecond
- AND no I/O SHALL be performed on the agent's thread

### Requirement: Thread safety

The system SHALL be thread-safe for concurrent agent execution.

#### Scenario: Concurrent runs

- GIVEN multiple threads execute trace.run() simultaneously
- WHEN events are emitted from each thread
- THEN all events SHALL be correctly associated with their run_id
- AND no race conditions SHALL corrupt the queue
- AND the background thread SHALL process events from all runs

### Requirement: Graceful shutdown

The system SHALL ensure no events are lost during process shutdown.

#### Scenario: Flush on exit

- GIVEN the process is shutting down
- WHEN the tracer's shutdown hook is triggered
- THEN remaining events in the queue SHALL be processed
- AND the worker thread SHALL wait for the final batch to complete
- AND the shutdown SHALL timeout after 5 seconds to prevent hanging