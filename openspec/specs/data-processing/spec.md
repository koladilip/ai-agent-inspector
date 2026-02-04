# data-processing Specification

## Purpose

Provide a secure and efficient data processing pipeline that transforms raw trace events through redaction, serialization, compression, and optional encryption before storage. The pipeline must handle sensitive data safely while minimizing storage footprint and maintaining data integrity.

## Requirements

### Requirement: Processing pipeline order

The system SHALL process events in a strictly ordered pipeline: redaction → serialization → compression → encryption → storage.

#### Scenario: Complete pipeline execution

- GIVEN a raw event dictionary is passed to the processor
- WHEN the pipeline executes
- THEN redaction SHALL be applied first
- AND the result SHALL be serialized to JSON
- AND the JSON SHALL be compressed
- AND the compressed data SHALL be encrypted (if enabled)
- AND the final blob SHALL be returned for storage

#### Scenario: Pipeline without encryption

- GIVEN encryption is disabled in configuration
- WHEN an event is processed
- THEN redaction, serialization, and compression SHALL still occur
- AND the compressed data SHALL be returned directly without encryption

### Requirement: Key-based redaction

The system SHALL redact sensitive data by field name.

#### Scenario: Redact top-level keys

- GIVEN an event contains `{"user": {"name": "Alice", "password": "secret123"}}`
- AND redact_keys includes "password"
- WHEN the event is processed
- THEN the output SHALL contain `{"user": {"name": "Alice", "password": "***REDACTED***"}}`
- AND the original value SHALL be completely replaced

#### Scenario: Redact nested keys

- GIVEN an event contains nested data at any depth
- AND redact_keys includes "token"
- WHEN the event is processed
- THEN all occurrences of "token" as a key SHALL be redacted regardless of nesting level
- AND nested structures SHALL be traversed recursively

#### Scenario: Redact common sensitive keys

- GIVEN a TraceConfig specifies redact_keys with common sensitive field names
- WHEN the configuration is initialized with default redaction keys
- THEN the following keys SHALL be redacted by default: password, api_key, secret, token, ssn, credit_card
- AND developers SHALL be able to override or extend this list

#### Scenario: Case-sensitive matching

- GIVEN redact_keys includes "Password"
- AND an event contains `{"password": "value"}`
- WHEN the event is processed
- THEN the "password" key SHALL NOT be redacted (case mismatch)
- AND only exact case matches SHALL be redacted

### Requirement: Pattern-based redaction

The system SHALL redact values matching regex patterns.

#### Scenario: Redact credit card numbers

- GIVEN redact_patterns includes `r"\b\d{4}-\d{4}-\d{4}-\d{4}\b"`
- AND an event contains `{"card": "1234-5678-9012-3456"}`
- WHEN the event is processed
- THEN the value SHALL be replaced with `{"card": "***REDACTED***"}`

#### Scenario: Redact SSN patterns

- GIVEN redact_patterns includes `r"\b\d{3}-\d{2}-\d{4}\b"`
- AND an event contains `{"id": "123-45-6789"}`
- WHEN the event is processed
- THEN the value SHALL be replaced with `{"id": "***REDACTED***"}`

#### Scenario: Redact API key patterns

- GIVEN redact_patterns includes `r"[A-Za-z0-9]{32,}"` (long alphanumeric strings)
- AND an event contains `{"key": "abc123def456..."}` (40 chars)
- WHEN the event is processed
- THEN the value SHALL be replaced with `{"key": "***REDACTED***"}`

#### Scenario: Multiple pattern matches

- GIVEN an event contains multiple values matching the same pattern
- WHEN the event is processed
- THEN ALL matching values SHALL be redacted
- AND non-matching values SHALL remain unchanged

#### Scenario: Pattern in nested strings

- GIVEN redact_patterns includes `r"\b\d{12}\b"`
- AND an event contains `{"data": {"nested": {"value": "123456789012"}}}`
- WHEN the event is processed
- THEN the nested value SHALL be redacted

### Requirement: Custom redaction behavior

The system SHALL support custom redaction functions.

#### Scenario: Custom redaction marker

- GIVEN a developer provides a custom redaction function
- AND the function returns `[FILTERED]` instead of `***REDACTED***`
- WHEN the custom redactor is configured
- THEN redacted values SHALL use the custom marker

#### Scenario: Partial redaction

- GIVEN a developer wants to show partial values
- AND a custom redactor is configured for "email"
- AND the email is "user@example.com"
- WHEN the event is processed
- THEN the value SHALL become "u***@example.com"

### Requirement: JSON serialization

The system SHALL serialize events to JSON with consistent formatting.

#### Scenario: Standard serialization

- GIVEN a redacted event dictionary is ready
- WHEN serialization is performed
- THEN the output SHALL be valid JSON
- AND datetime objects SHALL be converted to ISO 8601 strings
- AND binary data SHALL be base64-encoded
- AND complex objects SHALL be converted to their string representation

#### Scenario: Handle non-serializable objects

- GIVEN an event contains a Python object that is not JSON-serializable
- WHEN serialization is attempted
- THEN the object SHALL be converted to `{"__type__": "ClassName", "__repr__": "str(object)"}`
- AND the serialization SHALL not fail
- AND the original type information SHALL be preserved

#### Scenario: Compact JSON format

- GIVEN the JSON is serialized
- WHEN no pretty-printing is configured
- THEN the output SHALL be compact (no whitespace)
- AND this SHALL reduce storage size

### Requirement: Compression

The system SHALL compress JSON data using gzip.

#### Scenario: Gzip compression

- GIVEN a JSON string is ready for compression
- WHEN gzip compression is applied
- THEN the output SHALL be a bytes object
- AND the compression level SHALL be 6 (balanced speed/size)
- AND the size SHALL be reduced by approximately 5-10x

#### Scenario: Compression of small payloads

- GIVEN a JSON string is less than 100 bytes
- WHEN compression is applied
- THEN compression SHALL still be applied
- AND overhead SHALL be minimal
- AND the compressed size MAY be slightly larger than original

#### Scenario: Decompression for retrieval

- GIVEN compressed data is retrieved from storage
- WHEN decompression is applied
- THEN the original JSON SHALL be perfectly restored
- AND no data loss SHALL occur

### Requirement: Encryption

The system SHALL encrypt compressed data using Fernet symmetric encryption when enabled.

#### Scenario: Encrypt with provided key

- GIVEN encryption is enabled
- AND TRACE_ENCRYPTION_KEY is set to a valid 32-byte key
- WHEN compressed data is encrypted
- THEN Fernet SHALL be used for symmetric encryption
- AND the output SHALL be a URL-safe base64-encoded string
- AND the same key SHALL be required for decryption

#### Scenario: Key validation

- GIVEN encryption is enabled
- AND TRACE_ENCRYPTION_KEY is too short (<32 bytes)
- WHEN the configuration is validated
- THEN a ValueError SHALL be raised
- AND the error message SHALL indicate the required key length

#### Scenario: Key derivation from passphrase

- GIVEN TRACE_ENCRYPTION_KEY is a human-readable passphrase
- WHEN the key is used
- THEN SHA-256 SHALL be applied to derive a 32-byte key
- AND the derived key SHALL be used for encryption

#### Scenario: Decryption

- GIVEN encrypted data is retrieved
- WHEN decryption is applied with the correct key
- THEN the original compressed data SHALL be restored
- AND a wrong key SHALL raise a cryptography exception

#### Scenario: Encryption disabled

- GIVEN encryption_enabled is False
- WHEN an event is processed
- THEN encryption SHALL be skipped
- AND the compressed data SHALL be returned directly

### Requirement: Pipeline error handling

The system SHALL handle errors gracefully at each pipeline stage.

#### Scenario: Redaction error

- GIVEN redaction fails due to malformed data
- WHEN the error occurs
- THEN the error SHALL be logged
- AND the original data SHALL pass through to the next stage
- AND processing SHALL continue

#### Scenario: Serialization error

- GIVEN serialization fails for an event
- WHEN the error occurs
- THEN the event SHALL be skipped
- AND an error SHALL be logged with the run_id
- AND subsequent events SHALL continue processing

#### Scenario: Compression error

- GIVEN compression fails unexpectedly
- WHEN the error occurs
- THEN the uncompressed JSON SHALL be stored instead
- AND a warning SHALL be logged
- AND the system SHALL not crash

#### Scenario: Encryption error

- GIVEN encryption fails (e.g., invalid key)
- WHEN the error occurs
- THEN encryption SHALL be disabled for this batch
- AND compressed data SHALL be stored unencrypted
- AND a critical error SHALL be logged

### Requirement: Performance optimization

The system SHALL optimize pipeline performance.

#### Scenario: Batch processing

- GIVEN multiple events are ready for processing
- WHEN they are processed as a batch
- THEN each event SHALL be processed independently
- AND compression/encryption overhead SHALL be amortized
- AND the pipeline SHALL handle at least 1000 events per second

#### Scenario: Memory efficiency

- GIVEN large events are being processed
- WHEN the pipeline runs
- THEN intermediate representations SHALL be garbage-collected promptly
- AND memory usage SHALL not grow unbounded

#### Scenario: Caching compiled regex

- GIVEN redaction patterns are compiled to regex
- WHEN the processor is initialized
- THEN compiled patterns SHALL be cached
- AND the cache SHALL persist for the lifetime of the process

### Requirement: Pipeline statistics

The system SHALL track processing metrics.

#### Scenario: Track processing time

- GIVEN events are processed through the pipeline
- WHEN processing completes
- THEN the time for each stage SHALL be recorded
- AND average processing time SHALL be available via metrics API

#### Scenario: Track compression ratio

- GIVEN events are compressed
- WHEN compression completes
- THEN the compression ratio SHALL be calculated
- AND the average ratio SHALL be tracked over time

#### Scenario: Track redaction count

- GIVEN events are processed
- WHEN redaction occurs
- THEN the number of redacted fields SHALL be counted
- AND statistics SHALL show which keys are most commonly redacted