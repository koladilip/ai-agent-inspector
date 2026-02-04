# adapters Specification

## Purpose

Provide adapter layers that integrate Agent Inspector with popular agent frameworks and enable custom agent wrappers. Adapters shall automatically capture framework-specific events (LLM calls, tool calls, memory operations) and translate them to Agent Inspector's unified event model without requiring manual instrumentation.

## Requirements

### Requirement: LangChain adapter

The system SHALL provide automatic integration with LangChain framework.

#### Scenario: Enable LangChain adapter

- GIVEN a LangChain agent is being used
- WHEN `from agent_inspector.adapters.langchain import enable` is imported
- AND `enable()` is called
- THEN all LangChain LLM calls SHALL be automatically traced
- AND all LangChain tool calls SHALL be automatically traced
- AND LangChain memory operations SHALL be automatically traced
- AND no manual trace calls SHALL be required

#### Scenario: LangChain LLM call capture

- GIVEN LangChain adapter is enabled
- AND a LangChain agent calls an LLM (e.g., ChatOpenAI)
- WHEN the LLM call is made
- THEN a `trace.llm()` event SHALL be automatically emitted
- AND the event SHALL include:
  - model name (e.g., "gpt-4")
  - prompt/messages sent to the model
  - response received from the model
  - token usage (if available)
  - temperature and parameters
- AND the event SHALL be captured transparently without modifying agent code

#### Scenario: LangChain tool call capture

- GIVEN LangChain adapter is enabled
- AND a LangChain agent invokes a tool via LangChain's tool interface
- WHEN the tool is executed
- THEN a `trace.tool()` event SHALL be automatically emitted
- AND the event SHALL include:
  - tool name
  - tool arguments
  - tool result
  - execution duration
- AND nested tool calls SHALL be captured with parent-child relationships

#### Scenario: LangChain memory operation capture

- GIVEN LangChain adapter is enabled
- AND a LangChain agent uses memory (e.g., ConversationBufferMemory)
- WHEN the agent reads from memory
- THEN a `trace.memory_read()` event SHALL be emitted
- AND the event SHALL include the memory key and value

- WHEN the agent writes to memory
- THEN a `trace.memory_write()` event SHALL be emitted
- AND the event SHALL include the memory key and value

#### Scenario: LangChain error capture

- GIVEN LangChain adapter is enabled
- AND a LangChain agent execution fails
- WHEN an exception is raised in LangChain
- THEN a `trace.error()` event SHALL be emitted
- AND the event SHALL include the exception type, message, and stack trace
- AND the error SHALL be associated with the appropriate step in the trace

#### Scenario: Configure LangChain adapter

- GIVEN a TraceConfig is created
- WHEN the LangChain adapter is initialized
- THEN the adapter SHALL respect TraceConfig settings (sampling, redaction, etc.)
- AND adapter-specific settings can be provided:
  - `trace_llm_only`: boolean to only trace LLM calls
  - `trace_tools`: boolean to enable tool call tracing
  - `trace_memory`: boolean to enable memory operation tracing
- AND default settings SHALL trace all event types

#### Scenario: Disable LangChain adapter

- GIVEN LangChain adapter is enabled
- WHEN `disable()` is called
- THEN automatic tracing SHALL stop
- AND LangChain agents SHALL function normally without overhead
- AND existing traces SHALL remain intact

### Requirement: Custom agent wrapper

The system SHALL provide a context manager wrapper for custom agent implementations.

#### Scenario: Wrap custom agent execution

- GIVEN a custom agent implementation (not LangChain, AutoGen, etc.)
- WHEN the agent is wrapped with `with trace.run("agent_name"):`
- THEN the agent execution SHALL be traced
- AND events SHALL be automatically captured if the agent uses supported interfaces
- AND the run SHALL be properly scoped with start/end events

#### Scenario: Manual event emission in wrapper

- GIVEN a custom agent is wrapped
- AND the agent performs operations that need tracing
- WHEN `trace.llm()`, `trace.tool()`, etc. are called within the wrapper
- THEN events SHALL be captured in the run's trace
- AND events SHALL be ordered by timestamp
- AND the run SHALL include all emitted events

#### Scenario: Wrapper with nested agents

- GIVEN an agent spawns child agents
- WHEN each agent is wrapped with `trace.run()`
- THEN parent and child runs SHALL be linked
- AND parent run_id SHALL be included in child runs metadata
- AND the UI SHALL support visualizing the hierarchy

#### Scenario: Wrapper error handling

- GIVEN an agent is wrapped
- WHEN the agent raises an exception
- AND the exception is not caught within the wrapper
- THEN a `trace.error()` event SHALL be automatically emitted
- AND the run status SHALL be set to 'failed'
- AND the exception details SHALL be captured

### Requirement: Generic adapter interface

The system SHALL define a standard interface for creating new framework adapters.

#### Scenario: Adapter base class

- GIVEN a new adapter is being implemented
- WHEN the adapter extends `BaseAdapter`
- THEN the adapter MUST implement:
  - `setup()`: initialize the adapter and hook into framework
  - `teardown()`: remove hooks and cleanup
  - `on_llm_call()`: handler for LLM invocations
  - `on_tool_call()`: handler for tool invocations
  - `on_memory_read()`: handler for memory reads
  - `on_memory_write()`: handler for memory writes
  - `on_error()`: handler for errors
- AND all methods SHALL receive framework-specific event data
- AND the adapter SHALL translate events to Agent Inspector format

#### Scenario: Adapter registration

- GIVEN an adapter is implemented
- WHEN the adapter is registered with `register_adapter("framework_name", adapter_class)`
- THEN the adapter SHALL be available for enablement
- AND it SHALL be accessible via a standardized name
- AND duplicate registrations SHALL raise an error

#### Scenario: Adapter configuration

- GIVEN an adapter is being enabled
- WHEN `enable_adapter("framework_name", config={...})` is called
- THEN the adapter SHALL be initialized with provided configuration
- AND adapter-specific settings SHALL be passed through
- AND TraceConfig settings SHALL also be available to the adapter

### Requirement: Event translation

The system SHALL translate framework-specific events to Agent Inspector events.

#### Scenario: Normalize LLM event data

- GIVEN a framework emits an LLM call event
- WHEN the adapter processes the event
- THEN the following SHALL be extracted and normalized:
  - model name (from various field names like "model", "model_name", etc.)
  - prompt (from "prompt", "messages", "input", etc.)
  - response (from "response", "output", "result", etc.)
  - token usage (from "usage", "token_counts", etc.)
  - duration (calculated from timestamps if available)
- AND the normalized data SHALL be passed to `trace.llm()`

#### Scenario: Normalize tool event data

- GIVEN a framework emits a tool call event
- WHEN the adapter processes the event
- THEN the following SHALL be extracted and normalized:
  - tool name (from "tool", "function", "name", etc.)
  - arguments (from "args", "parameters", "input", etc.)
  - result (from "result", "output", "response", etc.)
  - duration (calculated if available)
- AND the normalized data SHALL be passed to `trace.tool()`

#### Scenario: Preserve framework metadata

- GIVEN a framework event contains additional metadata
- WHEN the event is translated
- THEN framework-specific metadata SHALL be preserved in the event's `meta` field
- AND the metadata SHALL be included in the stored trace
- AND the UI SHALL display framework-specific details when available

### Requirement: Performance considerations

The system SHALL ensure adapters add minimal overhead to agent execution.

#### Scenario: Non-invasive hooking

- GIVEN an adapter hooks into framework internals
- WHEN the adapter is enabled
- THEN hooks SHALL be lightweight
- AND the overhead per event SHALL be less than 1 millisecond
- AND no blocking operations SHALL occur on the agent thread

#### Scenario: Lazy initialization

- GIVEN an adapter is imported but not enabled
- WHEN the module is loaded
- THEN the adapter SHALL NOT initialize hooks
- AND no overhead SHALL be added until `enable()` is called
- AND memory usage SHALL remain minimal

#### Scenario: Conditional event capture

- GIVEN TraceConfig specifies sampling or filtering
- WHEN an event occurs in the framework
- THEN the adapter SHALL check if the event should be captured
- AND events SHALL be skipped if the run is not being sampled
- AND overhead SHALL be minimized for skipped events

### Requirement: Adapter error handling

The system SHALL handle adapter errors gracefully without affecting agent execution.

#### Scenario: Adapter initialization failure

- GIVEN an adapter fails to initialize (e.g., framework not installed)
- WHEN `enable()` is called
- THEN a clear error message SHALL be logged
- AND the exception SHALL be re-raised with context
- AND the agent SHALL continue to function without tracing

#### Scenario: Event processing failure

- GIVEN an adapter is processing an event
- AND an error occurs during event translation
- WHEN the error occurs
- THEN the error SHALL be logged
- AND the event SHALL be skipped
- AND the agent SHALL continue executing
- AND subsequent events SHALL be processed normally

#### Scenario: Hook removal on error

- GIVEN an adapter encounters a critical error
- WHEN the error occurs
- THEN the adapter SHALL attempt to remove all hooks
- AND the adapter SHALL disable itself
- AND a warning SHALL be logged
- AND the agent SHALL continue execution

### Requirement: Adapter testing

The system SHALL provide utilities for testing adapters.

#### Scenario: Mock adapter for testing

- GIVEN a developer is writing tests for an agent
- WHEN `MockAdapter()` is used instead of the real adapter
- THEN events SHALL be captured in memory
- AND no database writes SHALL occur
- AND events SHALL be accessible for assertions
- AND performance SHALL be fast

#### Scenario: Test event capture

- GIVEN a mock adapter is configured
- AND agent code is executed
- WHEN the test completes
- THEN `mock_adapter.get_events()` SHALL return all captured events
- AND events SHALL include the expected fields
- AND test assertions SHALL verify event correctness

### Requirement: Documentation and examples

The system SHALL provide clear documentation and examples for using adapters.

#### Scenario: LangChain adapter example

- GIVEN a developer wants to use the LangChain adapter
- WHEN they read the documentation
- THEN a complete working example SHALL be provided showing:
  - How to import and enable the adapter
  - How to configure the adapter
  - Sample agent code
  - How to view traces in the UI

#### Scenario: Custom wrapper example

- GIVEN a developer wants to trace a custom agent
- WHEN they read the documentation
- THEN examples SHALL be provided for:
  - Basic wrapper usage
  - Manual event emission
  - Error handling patterns
  - Nested agent scenarios

#### Scenario: Adapter development guide

- GIVEN a developer wants to create a new adapter
- WHEN they read the development guide
- THEN step-by-step instructions SHALL be provided:
  - How to extend BaseAdapter
  - How to hook into framework internals
  - How to translate events
  - How to test the adapter
  - How to register and enable the adapter

### Requirement: Compatibility

The system SHALL maintain compatibility with framework versions.

#### Scenario: Framework version detection

- GIVEN an adapter is being initialized
- WHEN the framework version is checked
- THEN the adapter SHALL detect the installed version
- AND the adapter SHALL adapt to version differences
- AND incompatible versions SHALL raise a clear error with version requirements

#### Scenario: Graceful degradation

- GIVEN a new framework version changes an API
- WHEN the adapter detects the change
- THEN the adapter SHALL use compatible fallback logic
- OR a warning SHALL be logged indicating limited functionality
- AND tracing SHALL continue to work as much as possible

#### Scenario: Minimum version requirements

- GIVEN an adapter requires specific framework features
- WHEN the adapter documentation is read
- THEN minimum and tested framework versions SHALL be listed
- AND breaking changes between versions SHALL be documented

### Requirement: Adapter lifecycle

The system SHALL provide proper lifecycle management for adapters.

#### Scenario: Enable/disable multiple times

- GIVEN an adapter is enabled and then disabled
- WHEN the adapter is enabled again
- THEN hooks SHALL be re-established
- AND configuration SHALL be reapplied
- AND the adapter SHALL function correctly

#### Scenario: Adapter state isolation

- GIVEN multiple adapter instances are created
- WHEN each instance is enabled independently
- THEN each instance SHALL have isolated state
- AND events SHALL be captured correctly by each instance
- AND configuration SHALL not leak between instances

#### Scenario: Global adapter registry

- GIVEN the system maintains a registry of adapters
- WHEN adapters are registered and retrieved
- THEN the registry SHALL be process-global
- AND the registry SHALL survive module reloads
- AND adapters SHALL remain available throughout the application lifecycle

### Requirement: Auto-discovery

The system SHALL support automatic detection and enablement of adapters.

#### Scenario: Auto-detect installed frameworks

- GIVEN an application starts
- WHEN the system scans for supported frameworks
- THEN installed frameworks (LangChain, AutoGen, etc.) SHALL be detected
- AND a summary SHALL be logged: "Detected frameworks: langchain, autogen"
- AND adapters SHALL not be enabled automatically (user must opt-in)

#### Scenario: Enable all detected adapters

- GIVEN multiple frameworks are detected
- WHEN `enable_all()` is called
- THEN all detected adapters SHALL be enabled
- AND each adapter SHALL use default configuration
- AND a warning SHALL be logged about enabling multiple adapters

### Requirement: Future adapter support

The system SHALL make it easy to add new framework adapters.

#### Scenario: Planned adapters

- GIVEN the system roadmap
- WHEN future adapter support is considered
- THEN the following frameworks SHALL be planned:
  - AutoGen
  - CrewAI
  - Microsoft Semantic Kernel
  - Amazon Bedrock Agents
  - LlamaIndex agents
- AND each adapter SHALL follow the BaseAdapter interface

#### Scenario: Community adapters

- GIVEN external developers want to contribute adapters
- WHEN they implement new adapters
- THEN they SHALL follow the BaseAdapter interface
- AND they SHALL include tests
- AND they SHALL provide documentation
- AND contributed adapters SHALL be accepted via PRs

### Requirement: Adapter metrics

The system SHALL track adapter-specific metrics.

#### Scenario: Track captured events per framework

- GIVEN adapters are active
- WHEN events are captured
- THEN metrics SHALL track:
  - Number of events captured per adapter
  - Number of events skipped (sampling)
  - Adapter processing time
  - Adapter errors
- AND metrics SHALL be exposed via the `/stats` API endpoint

#### Scenario: Adapter health monitoring

- GIVEN an adapter is running
- WHEN health is checked
- THEN the adapter SHALL report:
  - Whether hooks are active
  - Number of events captured
  - Any recent errors
- AND the health endpoint `/health` SHALL include adapter status