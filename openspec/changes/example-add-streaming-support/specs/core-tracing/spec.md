
## Requirement: Streaming LLM support

The system SHALL support capturing streaming LLM responses with individual token-level granularity.

### Scenario: Start a streaming LLM context

- GIVEN a developer wants to trace a streaming LLM call
- WHEN `trace.start_llm_stream(model="gpt-4", prompt="Hello")` is called as a context manager
- THEN a streaming LLM context SHALL be created
- AND an `llm_call` event SHALL be emitted with `streaming: true`
- AND the context SHALL support `add_token()` method
- AND the context SHALL finalize the stream when exiting

### Scenario: Add individual streaming tokens

- GIVEN a streaming LLM context is active
- WHEN `stream.add_token(token)` is called for each generated token
- THEN each token SHALL be captured with:
  - token text
  - token index
  - timestamp
  - delta from previous token
- AND tokens SHALL be buffered in memory
- AND no blocking I/O SHALL occur

### Scenario: Finalize streaming LLM call

- GIVEN a streaming LLM context is active
- WHEN the context exits (stream completes)
- THEN all buffered tokens SHALL be written to storage
- AND the parent `llm_call` event SHALL be updated with:
  - `streaming: true`
  - `total_tokens: count`
  - `first_token_latency_ms: value`
  - `last_token_latency_ms: value`
  - `tokens_per_second: value`
- AND the complete response SHALL be stored

### Scenario: Streaming LLM event model

- GIVEN a streaming LLM call is completed
- WHEN the event is serialized
- THEN the `llm_call` event SHALL include streaming metadata
- AND a new event type `llm_token` SHALL be created for individual tokens
- AND token events SHALL reference the parent `llm_call_id`

## Requirement: Token buffer management

The system SHALL provide an efficient in-memory buffer for streaming tokens before database writes.

### Scenario: Buffer tokens in memory

- GIVEN tokens are being streamed
- WHEN tokens are added via `add_token()`
- THEN tokens SHALL be stored in an in-memory buffer
- AND the buffer SHALL not block the streaming thread
- AND buffer size SHALL be monitored

### Scenario: Automatic buffer flush

- GIVEN the token buffer reaches a threshold (default: 1000 tokens)
- WHEN `add_token()` is called
- THEN the buffer SHALL automatically flush to storage
- AND a new empty buffer SHALL be created
- AND the operation SHALL not interrupt the stream

### Scenario: Buffer finalization

- GIVEN a streaming context is exiting
- WHEN `finalize()` is called
- THEN remaining tokens in the buffer SHALL be written
- AND streaming statistics SHALL be calculated
- AND the parent `llm_call` event SHALL be updated
- AND the buffer SHALL be cleared

### Scenario: Configurable buffer size

- GIVEN a TraceConfig specifies `token_buffer_size=500`
- WHEN streaming is enabled
- THEN the buffer SHALL flush after 500 tokens
- AND the default buffer size SHALL be 1000

## Requirement: Streaming statistics calculation

The system SHALL calculate and store streaming performance metrics.

### Scenario: Calculate first token latency

- GIVEN a streaming LLM call begins
- WHEN the first token arrives
- THEN `first_token_latency_ms` SHALL be calculated as `token_timestamp - call_start_timestamp`
- AND this SHALL measure LLM time-to-first-token

### Scenario: Calculate token generation rate

- GIVEN a streaming LLM call completes
- WHEN statistics are calculated
- THEN `tokens_per_second` SHALL be calculated as `total_tokens / total_duration_ms * 1000`
- AND this SHALL measure overall generation speed

### Scenario: Calculate per-token latency

- GIVEN tokens are arriving during streaming
- WHEN each token is added
- THEN `delta_ms` SHALL be calculated as `current_token_timestamp - previous_token_timestamp`
- AND this SHALL help identify slow token generation

### Scenario: Aggregated streaming statistics

- GIVEN a streaming LLM call completes
- WHEN statistics are finalized
- THEN the following SHALL be calculated:
  - `total_tokens`: integer count
  - `avg_token_latency_ms`: average of all deltas
  - `min_token_latency_ms`: smallest delta
  - `max_token_latency_ms`: largest delta
  - `total_duration_ms`: last_token - call_start
  - `tokens_per_second`: rate calculation

## Requirement: Streaming error handling

The system SHALL handle errors during streaming gracefully.

### Scenario: Handle stream interruption

- GIVEN a streaming LLM call is in progress
- WHEN the stream is interrupted or raises an exception
- THEN the context SHALL catch the exception
- AND a `trace.error()` event SHALL be emitted
- AND captured tokens SHALL be preserved
- AND the `llm_call` status SHALL be set to 'failed'

### Scenario: Buffer flush failure

- GIVEN a token buffer needs to flush
- WHEN the database write fails
- THEN the error SHALL be logged
- AND tokens SHALL remain in the buffer
- AND retry logic SHALL attempt to write again
- AND the stream SHALL not be interrupted

### Scenario: Context manager cleanup

- GIVEN a streaming context encounters an error
- WHEN the context manager exits
- THEN cleanup SHALL occur in `__exit__`
- AND resources SHALL be released
- AND the state SHALL be consistent
- AND no uncommitted tokens SHALL be lost (best effort)

## Requirement: Non-blocking streaming capture

The system SHALL ensure streaming token capture adds minimal overhead to LLM execution.

### Scenario: Token capture overhead

- GIVEN a token is being captured
- WHEN `add_token()` is called
- THEN the operation SHALL complete in less than 100 microseconds
- AND no I/O SHALL be performed on the streaming thread
- AND the token SHALL be added to the in-memory buffer

### Scenario: Concurrent streaming

- GIVEN multiple streaming LLM calls are happening simultaneously
- WHEN tokens are captured from each stream
- THEN each stream SHALL have its own buffer
- AND token capture SHALL be thread-safe
- AND no race conditions SHALL corrupt data

### Scenario: Memory bounded streaming

- GIVEN a streaming LLM call generates many tokens (e.g., 50,000)
- WHEN tokens are buffered and flushed
- THEN memory usage SHALL remain bounded
- AND old tokens SHALL be written and cleared from memory
- AND the process SHALL not run out of memory