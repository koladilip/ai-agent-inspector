# configuration Specification

## Purpose

Provide a centralized configuration system for the Agent Inspector that allows developers to customize behavior through environment variables and a Python configuration object. The system must support secure defaults, easy customization, and runtime-reloadable settings.

## Requirements

### Requirement: TraceConfig class

The system SHALL provide a TraceConfig class that encapsulates all configurable settings.

#### Scenario: Initialize default configuration

- GIVEN a developer imports TraceConfig
- WHEN they create a TraceConfig instance without arguments
- THEN sensible defaults SHALL be applied
- AND the configuration SHALL be immediately usable
- AND all optional settings SHALL have safe default values

#### Scenario: Configure redaction rules

- GIVEN a TraceConfig is initialized
- WHEN `redact_keys=["password", "api_key", "ssn"]` is specified
- THEN events SHALL redact values for these keys
- AND the redaction SHALL replace values with "***REDACTED***"
- AND nested dictionary structures SHALL be searched recursively

- GIVEN a TraceConfig is initialized
- WHEN `redact_patterns=[r"\b\d{12}\b"]` is specified
- THEN events SHALL redact values matching these regex patterns
- AND pattern matching SHALL apply to string values at any depth

#### Scenario: Configure sampling

- GIVEN a TraceConfig is initialized
- WHEN `sample_rate=0.1` is specified
- THEN only 10% of runs SHALL be traced
- AND the sampling SHALL be deterministic based on run_id
- AND the default sample_rate SHALL be 1.0 (trace everything)

- GIVEN a TraceConfig is initialized
- WHEN `only_on_error=True` is specified
- THEN runs without errors SHALL NOT be traced
- AND runs with errors SHALL be traced completely
- AND this SHALL override sample_rate when enabled

#### Scenario: Configure queue settings

- GIVEN a TraceConfig is initialized
- WHEN `queue_size=2000` is specified
- THEN the in-memory queue SHALL hold up to 2000 events
- AND events beyond capacity SHALL be dropped
- AND the default queue_size SHALL be 1000

#### Scenario: Configure batch processing

- GIVEN a TraceConfig is initialized
- WHEN `batch_size=100` and `batch_timeout_ms=2000` are specified
- THEN events SHALL be batched when 100 events accumulate OR 2 seconds elapse
- AND the default batch_size SHALL be 50
- AND the default batch_timeout_ms SHALL be 1000

#### Scenario: Configure storage settings

- GIVEN a TraceConfig is initialized
- WHEN `storage_path="/custom/path/traces.db"` is specified
- THEN SQLite database SHALL be created at the custom path
- AND the directory SHALL be created if it does not exist
- AND the default storage_path SHALL be "./agent_inspector/traces.db"

#### Scenario: Configure encryption

- GIVEN a TraceConfig is initialized
- WHEN `encryption_enabled=True` is specified
- THEN stored data SHALL be encrypted at rest
- AND the encryption key SHALL be read from TRACE_ENCRYPTION_KEY environment variable
- AND a warning SHALL be logged if the key is not set
- AND encryption SHALL default to False for development

### Requirement: Environment variable support

The system SHALL read configuration from environment variables with higher precedence than defaults.

#### Scenario: Override with environment variables

- GIVEN the TRACE_SAMPLE_RATE environment variable is set to "0.5"
- WHEN a TraceConfig is created without specifying sample_rate
- THEN the sample_rate SHALL be 0.5
- AND the value SHALL be parsed from string to the appropriate type

#### Scenario: Environment variable for encryption key

- GIVEN encryption is enabled
- WHEN TRACE_ENCRYPTION_KEY environment variable is set
- THEN the key SHALL be used for encryption
- AND the key SHALL be at least 32 bytes when encoded
- AND a weak key SHALL trigger a warning

- GIVEN encryption is enabled
- WHEN TRACE_ENCRYPTION_KEY is not set
- THEN a deterministic key SHALL be generated from the system hostname
- AND a warning SHALL be logged that production should use a proper key

#### Scenario: Supported environment variables

- GIVEN the following environment variables are supported:
- THEN TRACE_SAMPLE_RATE SHALL configure sampling rate (float, 0.0-1.0)
- AND TRACE_ONLY_ON_ERROR SHALL configure error-only tracing (boolean)
- AND TRACE_QUEUE_SIZE SHALL configure queue capacity (integer)
- AND TRACE_STORAGE_PATH SHALL configure database path (string)
- AND TRACE_ENCRYPTION_ENABLED SHALL enable encryption (boolean)
- AND TRACE_ENCRYPTION_KEY SHALL provide encryption key (string)
- AND TRACE_REDACT_KEYS SHALL configure redacted keys (comma-separated string)
- AND TRACE_REDACT_PATTERNS SHALL configure redaction patterns (comma-separated string)

### Requirement: Configuration validation

The system SHALL validate configuration values and provide clear error messages.

#### Scenario: Validate sample rate range

- GIVEN a TraceConfig is initialized with `sample_rate=1.5`
- WHEN the configuration is created
- THEN a ValueError SHALL be raised
- AND the error message SHALL indicate sample_rate must be between 0.0 and 1.0

#### Scenario: Validate queue size

- GIVEN a TraceConfig is initialized with `queue_size=-100`
- WHEN the configuration is created
- THEN a ValueError SHALL be raised
- AND the error message SHALL indicate queue_size must be a positive integer

#### Scenario: Validate batch size

- GIVEN a TraceConfig is initialized with `batch_size=0`
- WHEN the configuration is created
- THEN a ValueError SHALL be raised
- AND the error message SHALL indicate batch_size must be at least 1

#### Scenario: Validate storage path

- GIVEN a TraceConfig is initialized with `storage_path="/root/file.db"`
- AND the process lacks write permission to /root
- WHEN the configuration is created
- THEN a warning SHALL be logged
- AND the warning SHALL indicate potential write permission issues
- AND the error SHALL occur at runtime, not at configuration time

### Requirement: Configuration immutability after initialization

The system SHALL prevent configuration changes after the tracer is initialized.

#### Scenario: Freeze configuration

- GIVEN a TraceConfig instance is created
- WHEN the config is passed to the tracer
- THEN the config SHALL be marked as frozen
- AND attempts to modify config attributes SHALL raise an AttributeError
- AND the freeze SHALL apply only to the instance, not the class

### Requirement: Configuration merging

The system SHALL support merging multiple configuration sources with proper precedence.

#### Scenario: Merge precedence order

- GIVEN default values, environment variables, and explicit TraceConfig arguments exist
- WHEN the configuration is created
- THEN explicit arguments SHALL have highest precedence
- AND environment variables SHALL have medium precedence
- AND default values SHALL have lowest precedence

#### Scenario: Partial configuration

- GIVEN only some configuration values are provided
- WHEN the configuration is created
- THEN provided values SHALL override defaults
- AND unspecified values SHALL use defaults or environment variables
- AND all required fields SHALL have valid values

### Requirement: Configuration inspection

The system SHALL provide methods to inspect the current configuration.

#### Scenario: Get configuration as dictionary

- GIVEN a TraceConfig instance exists
- WHEN `config.to_dict()` is called
- THEN a dictionary SHALL be returned with all configuration values
- AND the dictionary SHALL be JSON-serializable
- AND sensitive values SHALL be redacted in the output

#### Scenario: Configuration summary

- GIVEN a TraceConfig instance exists
- WHEN `str(config)` or `repr(config)` is called
- THEN a human-readable summary SHALL be returned
- AND the summary SHALL show key settings
- AND sensitive values SHALL be masked

### Requirement: Development mode configuration

The system SHALL provide a development mode for easier local development.

#### Scenario: Enable development mode

- GIVEN the TRACE_DEV environment variable is set to "true"
- WHEN the configuration is created
- THEN encryption SHALL be disabled
- AND sampling SHALL be set to 1.0
- AND redaction SHALL be disabled
- AND storage path SHALL be set to "./dev_traces.db"
- AND a clear warning SHALL be logged that this is not production-ready

### Requirement: Profile presets

The system SHALL provide predefined configuration profiles for common use cases.

#### Scenario: Production preset

- GIVEN a developer uses `TraceConfig.preset("production")`
- THEN encryption SHALL be enabled
- AND sample_rate SHALL be 0.1
- AND redaction SHALL be enabled with common sensitive keys
- AND queue_size SHALL be 2000

#### Scenario: Development preset

- GIVEN a developer uses `TraceConfig.preset("development")`
- THEN encryption SHALL be disabled
- AND sample_rate SHALL be 1.0
- AND redaction SHALL be disabled
- AND queue_size SHALL be 100

#### Scenario: Debug preset

- GIVEN a developer uses `TraceConfig.preset("debug")`
- THEN only_on_error SHALL be False
- AND sample_rate SHALL be 1.0
- AND batch_size SHALL be 1 (immediate writes)
- AND redaction SHALL be disabled for inspection