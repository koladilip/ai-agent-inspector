# storage Specification

## Purpose

Provide a persistent storage layer for trace data using SQLite with efficient schema design, fast queries, and support for compressed/encrypted data blobs. The storage system must handle high-volume event data while maintaining query performance for the UI.

## Requirements

### Requirement: Database schema

The system SHALL use a two-table schema: runs and steps.

#### Scenario: Runs table structure

- GIVEN the database is initialized
- WHEN the runs table is created
- THEN the table SHALL have columns: id (TEXT PRIMARY KEY), started_at (INTEGER), completed_at (INTEGER), status (TEXT), name (TEXT), metadata (TEXT)
- AND id SHALL store the run_id UUID
- AND started_at SHALL be a Unix timestamp in milliseconds
- AND completed_at SHALL be nullable (set on run completion)
- AND status SHALL be one of: 'running', 'completed', 'failed'
- AND name SHALL store the run name from trace.run()
- AND metadata SHALL be a JSON string for additional run-level data

#### Scenario: Steps table structure

- GIVEN the database is initialized
- WHEN the steps table is created
- THEN the table SHALL have columns: id (INTEGER PRIMARY KEY AUTOINCREMENT), run_id (TEXT), event_type (TEXT), timestamp (INTEGER), blob (BLOB), parent_step_id (INTEGER NULL)
- AND run_id SHALL be a foreign key referencing runs(id)
- AND event_type SHALL be one of: 'run_start', 'llm_call', 'tool_call', 'memory_read', 'memory_write', 'error', 'final_answer'
- AND timestamp SHALL be a Unix timestamp in milliseconds
- AND blob SHALL contain the processed (redacted, compressed, encrypted) event data
- AND parent_step_id SHALL support hierarchical event relationships
- AND an index SHALL exist on run_id for fast lookups
- AND an index SHALL exist on timestamp for timeline ordering

#### Scenario: Foreign key constraints

- GIVEN the schema is created
- WHEN foreign key constraints are enabled
- THEN steps SHALL reference valid run_ids
- AND cascade deletes SHALL be configured (deleting a run deletes its steps)

### Requirement: Database initialization

The system SHALL initialize the database on first use.

#### Scenario: Create database if not exists

- GIVEN the configured storage_path does not exist
- WHEN the storage is first accessed
- THEN the database file SHALL be created
- AND the runs and steps tables SHALL be created
- AND indexes SHALL be created
- AND the database SHALL be initialized with SQLite version 3.35+ features

#### Scenario: Initialize with existing database

- GIVEN the storage_path points to an existing database
- WHEN the storage is accessed
- THEN the database SHALL be opened
- AND schema version SHALL be checked
- AND if schema is outdated, migration SHALL be attempted

#### Scenario: Create directory structure

- GIVEN the storage_path includes non-existent directories
- WHEN the database is initialized
- THEN parent directories SHALL be created automatically
- AND appropriate permissions SHALL be set (user read/write)

### Requirement: Run operations

The system SHALL support CRUD operations for runs.

#### Scenario: Create a new run

- GIVEN a run starts with run_id and name
- WHEN create_run() is called
- THEN a new row SHALL be inserted into runs table
- AND id SHALL be set to the run_id
- AND started_at SHALL be set to current timestamp
- AND status SHALL be set to 'running'
- AND name SHALL be set to the provided name
- AND the function SHALL return success

#### Scenario: Update run status to completed

- GIVEN a run exists with status 'running'
- WHEN update_run_status(run_id, 'completed') is called
- THEN the status SHALL be updated to 'completed'
- AND completed_at SHALL be set to current timestamp
- AND the update SHALL be atomic

#### Scenario: Update run status to failed

- GIVEN a run exists with status 'running'
- WHEN an error occurs in the run
- AND update_run_status(run_id, 'failed') is called
- THEN the status SHALL be updated to 'failed'
- AND completed_at SHALL be set to current timestamp

#### Scenario: Retrieve a single run

- GIVEN a run exists with run_id
- WHEN get_run(run_id) is called
- THEN the run record SHALL be returned
- AND the metadata SHALL be parsed from JSON to a dictionary
- AND if the run does not exist, None SHALL be returned

#### Scenario: List all runs

- GIVEN multiple runs exist in the database
- WHEN list_runs() is called
- THEN all runs SHALL be returned
- AND the results SHALL be ordered by started_at DESC (newest first)
- AND pagination SHALL be supported via limit and offset parameters

#### Scenario: Filter runs by status

- GIVEN runs exist with various statuses
- WHEN list_runs(status='failed') is called
- THEN only runs with status 'failed' SHALL be returned
- AND other statuses SHALL be excluded

#### Scenario: Delete old runs

- GIVEN the database contains many old runs
- WHEN delete_runs_older_than(days=30) is called
- THEN runs older than 30 days SHALL be deleted
- AND all associated steps SHALL be cascade deleted
- AND the number of deleted runs SHALL be returned

### Requirement: Step operations

The system SHALL support storing and retrieving event steps.

#### Scenario: Insert a step

- GIVEN a processed event blob is ready
- WHEN insert_step(run_id, event_type, timestamp, blob) is called
- THEN a new row SHALL be inserted into steps table
- AND the run_id SHALL match the parent run
- AND event_type SHALL be set to the event type
- AND timestamp SHALL be set to the event timestamp
- AND blob SHALL contain the processed data
- AND the step SHALL be assigned a sequential ID

#### Scenario: Insert steps in batch

- GIVEN multiple events are ready for storage
- WHEN insert_steps_batch([(run_id, type, ts, blob), ...]) is called
- THEN all steps SHALL be inserted in a single transaction
- AND the transaction SHALL commit atomically (all or nothing)
- AND performance SHALL be optimized via prepared statements

#### Scenario: Retrieve steps for a run

- GIVEN a run has multiple steps
- WHEN get_steps(run_id) is called
- THEN all steps for that run SHALL be returned
- AND results SHALL be ordered by timestamp ASC
- AND each step SHALL include the raw blob
- AND parent_step_id SHALL be included for hierarchy

#### Scenario: Retrieve steps by event type

- GIVEN a run has mixed event types
- WHEN get_steps(run_id, event_type='tool_call') is called
- THEN only tool_call events SHALL be returned
- AND other event types SHALL be filtered out

### Requirement: Query performance

The system SHALL maintain fast query performance for UI operations.

#### Scenario: Run list query under threshold

- GIVEN the database contains 10,000 runs
- WHEN list_runs(limit=100) is called
- THEN the query SHALL complete in less than 50 milliseconds
- AND the index on started_at SHALL be used

#### Scenario: Step retrieval query under threshold

- GIVEN a run has 500 steps
- WHEN get_steps(run_id) is called
- THEN the query SHALL complete in less than 20 milliseconds
- AND the index on run_id SHALL be used

#### Scenario: Timeline range query

- GIVEN the database has runs spanning multiple months
- WHEN list_runs(start_time=X, end_time=Y) is called
- THEN only runs in the time range SHALL be returned
- AND the timestamp index SHALL be used for filtering

### Requirement: Database connection management

The system SHALL manage SQLite connections efficiently.

#### Scenario: Connection pooling

- GIVEN the storage is accessed concurrently
- WHEN multiple operations occur simultaneously
- THEN a connection pool SHALL be used
- AND connections SHALL be reused
- AND maximum pool size SHALL be configurable (default: 5)

#### Scenario: WAL mode for concurrent access

- GIVEN the database is initialized
- WHEN the database is configured
- THEN WAL (Write-Ahead Logging) mode SHALL be enabled
- AND readers SHALL not block writers
- AND writers SHALL not block readers

#### Scenario: Connection cleanup on shutdown

- GIVEN the process is shutting down
- WHEN cleanup() is called
- THEN all open connections SHALL be closed
- AND any pending transactions SHALL be rolled back
- AND the database file SHALL be properly closed

### Requirement: Data integrity

The system SHALL ensure data integrity and consistency.

#### Scenario: Transaction rollback on error

- GIVEN a batch insert is in progress
- WHEN an error occurs during insertion
- THEN the entire transaction SHALL be rolled back
- AND no partial data SHALL be committed
- AND the error SHALL be logged with context

#### Scenario: Schema validation

- GIVEN the database file exists
- WHEN storage is initialized
- THEN the schema version SHALL be checked
- AND if incompatible version is detected
- THEN a clear error message SHALL be raised
- AND migration options SHALL be provided

#### Scenario: Blob size validation

- GIVEN a step blob exceeds a size threshold (default: 10MB)
- WHEN insert_step() is called
- THEN the insert SHALL be rejected
- AND an error SHALL be logged
- AND the step SHALL be dropped to prevent database bloat

### Requirement: Database maintenance

The system SHALL support database maintenance operations.

#### Scenario: Vacuum database

- GIVEN the database has accumulated free space from deletions
- WHEN vacuum() is called
- THEN the database file SHALL be rebuilt
- AND free space SHALL be reclaimed
- AND the operation SHALL be performed during low-traffic periods

#### Scenario: Analyze query performance

- GIVEN the database is in use
- WHEN analyze() is called
- THEN SQLite shall update statistics
- AND the query optimizer shall have better information
- AND subsequent queries shall be optimized

#### Scenario: Prune old data

- GIVEN the database has grown large
- WHEN prune(days=90) is called
- THEN runs older than 90 days SHALL be deleted
- AND cascade delete SHALL remove associated steps
- AND space SHALL be reclaimed
- AND a summary of deleted runs SHALL be returned

### Requirement: Backup and restore

The system SHALL support database backup operations.

#### Scenario: Create backup

- GIVEN the database is in use
- WHEN backup(backup_path) is called
- THEN a consistent snapshot SHALL be created
- AND the backup SHALL be written to the specified path
- AND the operation SHALL use SQLite's online backup API
- AND the original database SHALL remain locked for minimal time

#### Scenario: Restore from backup

- GIVEN a backup file exists
- WHEN restore(backup_path) is called
- THEN the current database SHALL be replaced
- AND all data SHALL be restored
- AND the operation SHALL be atomic
- AND a backup of the current database SHALL be created first

### Requirement: Database statistics

The system SHALL provide statistics about stored data.

#### Scenario: Get run counts

- GIVEN the database has runs
- WHEN get_statistics() is called
- THEN the following SHALL be returned:
  - total_runs
  - runs_by_status (running, completed, failed counts)
  - total_steps
  - steps_by_type (counts per event type)
  - oldest_run_timestamp
  - newest_run_timestamp
  - database_size_bytes

#### Scenario: Get storage usage

- GIVEN the database is growing
- WHEN get_storage_usage() is called
- THEN the following SHALL be returned:
  - database_file_size
  - runs_table_size
  - steps_table_size
  - index_sizes
  - free_space_available

### Requirement: Encryption support

The system SHALL store encrypted blobs transparently.

#### Scenario: Store encrypted blob

- GIVEN encryption is enabled
- AND a step blob has been encrypted
- WHEN insert_step() is called
- THEN the encrypted blob SHALL be stored as-is
- AND the storage layer SHALL not need to decrypt
- AND the blob SHALL be treated as opaque BLOB data

#### Scenario: Retrieve encrypted blob

- GIVEN an encrypted blob is stored
- WHEN get_steps() is called
- THEN the encrypted blob SHALL be returned
- AND decryption SHALL be handled by the caller (data-processing layer)
- AND the storage layer SHALL not attempt decryption

### Requirement: Concurrent access

The system SHALL handle concurrent writes from multiple processes.

#### Scenario: File locking

- GIVEN multiple processes attempt to write simultaneously
- WHEN one process has a write lock
- THEN other processes SHALL wait or timeout
- AND SQLite SHALL handle locking automatically
- AND busy timeout SHALL be configurable (default: 5 seconds)

#### Scenario: Retry on SQLITE_BUSY

- GIVEN a write operation encounters SQLITE_BUSY
- WHEN the operation is attempted
- THEN it SHALL automatically retry up to 3 times
- AND retries SHALL use exponential backoff
- AND if all retries fail, an exception SHALL be raised