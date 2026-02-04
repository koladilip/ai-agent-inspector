# api Specification

## Purpose

Provide a FastAPI-based REST API that serves trace data to the web UI, enabling developers to query runs, retrieve steps, and filter results. The API must be efficient, well-documented, and support the UI's timeline and detail views.

## Requirements

### Requirement: Server initialization

The system SHALL initialize a FastAPI application with CORS support.

#### Scenario: Start the API server

- GIVEN the FastAPI application is configured
- WHEN the server is started with `uvicorn server.api:app`
- THEN the server SHALL listen on port 8000 by default
- AND the port SHALL be configurable via PORT environment variable
- AND CORS SHALL be enabled for all origins in development mode
- AND CORS SHALL be restricted to specific origins in production mode

#### Scenario: Automatic API documentation

- GIVEN the FastAPI application is running
- WHEN `/docs` is accessed
- THEN interactive Swagger UI documentation SHALL be displayed
- AND all endpoints SHALL be documented with examples
- AND request/response schemas SHALL be visible

- WHEN `/openapi.json` is accessed
- THEN OpenAPI JSON specification SHALL be returned
- AND the spec SHALL be machine-readable for code generation

### Requirement: Run listing endpoint

The system SHALL provide an endpoint to list trace runs with filtering and pagination.

#### Scenario: List all runs with default parameters

- GIVEN the database contains multiple runs
- WHEN a GET request is made to `/runs`
- THEN a JSON response SHALL be returned with status 200
- AND the response SHALL include:
  - `runs`: array of run objects
  - `total`: total count of runs
  - `page`: current page number
  - `page_size`: items per page
- AND each run object SHALL contain: id, name, status, started_at, completed_at, step_count
- AND results SHALL be ordered by started_at DESC (newest first)
- AND default page_size SHALL be 20
- AND default page SHALL be 1

#### Scenario: Filter runs by status

- GIVEN the database contains runs with different statuses
- WHEN a GET request is made to `/runs?status=failed`
- THEN only runs with status 'failed' SHALL be returned
- AND total SHALL reflect the filtered count
- AND valid status values SHALL be: running, completed, failed

#### Scenario: Filter runs by name search

- GIVEN the database contains runs with various names
- WHEN a GET request is made to `/runs?search=flight`
- THEN only runs whose name contains "flight" SHALL be returned
- AND the search SHALL be case-insensitive

#### Scenario: Filter runs by date range

- GIVEN the database contains runs spanning multiple days
- WHEN a GET request is made to `/runs?start=1738320000000&end=1738406400000`
- THEN only runs within the timestamp range SHALL be included
- AND timestamps SHALL be Unix milliseconds
- AND both start and end SHALL be optional

#### Scenario: Paginate results

- GIVEN the database contains 100 runs
- WHEN a GET request is made to `/runs?page=2&page_size=10`
- THEN runs 11-20 SHALL be returned
- AND page SHALL be 2
- AND page_size SHALL be 10

#### Scenario: Validate pagination parameters

- GIVEN a request is made to `/runs?page=0`
- THEN a 400 Bad Request SHALL be returned
- AND the error message SHALL indicate page must be >= 1

- GIVEN a request is made to `/runs?page_size=1000`
- THEN a 400 Bad Request SHALL be returned
- AND the error message SHALL indicate page_size must be <= 100

### Requirement: Run detail endpoint

The system SHALL provide an endpoint to retrieve details for a specific run.

#### Scenario: Get run by ID

- GIVEN a run exists with run_id "abc-123"
- WHEN a GET request is made to `/runs/abc-123`
- THEN a JSON response SHALL be returned with status 200
- AND the response SHALL include:
  - `id`: the run_id
  - `name`: run name
  - `status`: current status
  - `started_at`: start timestamp (milliseconds)
  - `completed_at`: completion timestamp or null
  - `duration_ms`: total duration or null if running
  - `metadata`: additional run metadata
  - `step_count`: total number of steps
  - `error_count`: number of error steps

#### Scenario: Handle non-existent run

- GIVEN a request is made to `/runs/nonexistent-id`
- WHEN the run does not exist
- THEN a 404 Not Found SHALL be returned
- AND the response SHALL contain an error message

#### Scenario: Validate run_id format

- GIVEN a request is made to `/runs/invalid-format`
- WHEN the run_id is not a valid UUID
- THEN a 400 Bad Request SHALL be returned
- AND the error message SHALL indicate invalid UUID format

### Requirement: Steps endpoint

The system SHALL provide an endpoint to retrieve steps for a run with optional filtering.

#### Scenario: Get all steps for a run

- GIVEN a run exists with run_id "abc-123" and multiple steps
- WHEN a GET request is made to `/runs/abc-123/steps`
- THEN a JSON response SHALL be returned with status 200
- AND the response SHALL include:
  - `steps`: array of step objects
  - `total`: total step count
- AND each step SHALL contain:
  - `id`: step database ID
  - `run_id`: parent run ID
  - `event_type`: type of event (llm_call, tool_call, etc.)
  - `timestamp`: event timestamp (milliseconds)
  - `parent_step_id`: parent step ID or null
  - `data`: decoded event data (after decompression/decryption)
- AND results SHALL be ordered by timestamp ASC

#### Scenario: Filter steps by event type

- GIVEN a run has mixed event types
- WHEN a GET request is made to `/runs/abc-123/steps?event_type=tool_call`
- THEN only steps with event_type 'tool_call' SHALL be returned
- AND total SHALL reflect filtered count
- AND valid event_types SHALL be: run_start, llm_call, tool_call, memory_read, memory_write, error, final_answer

#### Scenario: Filter steps by error status

- GIVEN a request is made to `/runs/abc-123/steps?errors_only=true`
- THEN only error events SHALL be returned
- AND this SHALL include steps with event_type='error' OR steps that contain error information

#### Scenario: Paginate steps

- GIVEN a run has many steps
- WHEN a GET request is made to `/runs/abc-123/steps?page=1&page_size=50`
- THEN the first 50 steps SHALL be returned
- AND pagination SHALL work the same as run listing

### Requirement: Timeline aggregation endpoint

The system SHALL provide an optimized endpoint for the UI timeline view.

#### Scenario: Get timeline summary

- GIVEN a run exists with multiple steps
- WHEN a GET request is made to `/runs/abc-123/timeline`
- THEN a JSON response SHALL be returned with status 200
- AND the response SHALL include:
  - `events`: array of simplified event objects
  - `duration_ms`: total run duration
- AND each event SHALL contain:
  - `id`: step ID
  - `type`: event type
  - `name`: event name (e.g., tool name, model name)
  - `timestamp`: event timestamp
  - `duration_ms`: event duration (if applicable)
  - `status`: success or error
- AND the data SHALL be optimized for rendering a timeline

#### Scenario: Timeline with parent-child relationships

- GIVEN a run has nested operations (e.g., LLM calls a tool)
- WHEN the timeline is retrieved
- THEN events SHALL include `parent_id` for nested events
- AND the timeline SHALL support hierarchical visualization

### Requirement: Statistics endpoint

The system SHALL provide an endpoint for database statistics.

#### Scenario: Get global statistics

- GIVEN the database has been in use
- WHEN a GET request is made to `/stats`
- THEN a JSON response SHALL be returned with status 200
- AND the response SHALL include:
  - `total_runs`: total number of runs
  - `runs_by_status`: object with counts for each status
  - `total_steps`: total number of steps
  - `steps_by_type`: object with counts for each event type
  - `oldest_run`: timestamp of oldest run
  - `newest_run`: timestamp of newest run
  - `database_size_mb`: database size in megabytes

#### Scenario: Get time-series statistics

- GIVEN a request is made to `/stats?timeseries=true&days=7`
- THEN the response SHALL include:
  - `runs_over_time`: array of {timestamp, count} grouped by day/hour
  - `steps_over_time`: array of {timestamp, count} grouped by day/hour
  - `errors_over_time`: array of {timestamp, count} grouped by day/hour

### Requirement: Health check endpoint

The system SHALL provide a health check endpoint for monitoring.

#### Scenario: Check service health

- GIVEN the API server is running
- WHEN a GET request is made to `/health`
- THEN a JSON response SHALL be returned with status 200
- AND the response SHALL include:
  - `status`: "healthy"
  - `timestamp`: current timestamp
  - `database`: status of database connection
  - `version`: API version

#### Scenario: Database connection check

- GIVEN the database connection fails
- WHEN `/health` is accessed
- THEN the response SHALL include:
  - `status`: "unhealthy"
  - `database`: "disconnected"
  - AND the HTTP status SHALL be 503 Service Unavailable

### Requirement: Response models

The system SHALL use Pydantic models for request/response validation.

#### Scenario: Run model validation

- GIVEN a Run model is defined
- WHEN a run is serialized to JSON
- THEN all fields SHALL be properly typed
- AND timestamps SHALL be integers (milliseconds)
- AND optional fields SHALL be null when absent
- AND the model SHALL be documented in OpenAPI spec

#### Scenario: Step data decoding

- GIVEN a step blob is retrieved from storage
- WHEN the step is serialized in the API response
- THEN the blob SHALL be decompressed (if compressed)
- AND the data SHALL be decrypted (if encrypted)
- AND the result SHALL be parsed from JSON
- AND the decoded data SHALL be included in the response

#### Scenario: Error response format

- GIVEN an error occurs during request processing
- WHEN the error response is returned
- THEN the response SHALL include:
  - `error`: error message
  - `detail`: additional details (if available)
  - `status_code`: HTTP status code
- AND the content-type SHALL be application/json
- AND the format SHALL be consistent across all errors

### Requirement: Performance requirements

The system SHALL meet performance targets for API responses.

#### Scenario: Run list response time

- GIVEN the database contains 10,000 runs
- WHEN `/runs?page=1&page_size=20` is called
- THEN the response time SHALL be under 100ms
- AND the query SHALL use indexes efficiently

#### Scenario: Run detail response time

- GIVEN a run has 500 steps
- WHEN `/runs/{run_id}` is called
- THEN the response time SHALL be under 50ms
- AND only run metadata SHALL be fetched (not steps)

#### Scenario: Steps response time

- GIVEN a run has 500 steps
- WHEN `/runs/{run_id}/steps` is called
- THEN the response time SHALL be under 200ms
- AND all steps SHALL be fetched and decoded

#### Scenario: Timeline response time

- GIVEN a run has 500 steps
- WHEN `/runs/{run_id}/timeline` is called
- THEN the response time SHALL be under 150ms
- AND the response SHALL be pre-aggregated

### Requirement: Authentication and authorization

The system SHALL support optional API authentication.

#### Scenario: API key authentication (optional)

- GIVEN authentication is enabled via configuration
- WHEN a request is made without an API key
- THEN a 401 Unauthorized SHALL be returned
- AND the WWW-Authenticate header SHALL be set

- GIVEN authentication is enabled
- WHEN a request is made with valid X-API-Key header
- THEN the request SHALL proceed normally
- AND the API key SHALL be validated against configured keys

#### Scenario: Public access (default)

- GIVEN authentication is disabled (default)
- WHEN any request is made to the API
- THEN the request SHALL proceed without authentication
- AND the API SHALL be publicly accessible
- AND this SHALL be suitable for local development

### Requirement: Rate limiting

The system SHALL protect against excessive API requests.

#### Scenario: Apply rate limits

- GIVEN rate limiting is enabled
- WHEN a client makes more than 100 requests per minute
- THEN a 429 Too Many Requests SHALL be returned
- AND the response SHALL include Retry-After header
- AND the rate limit SHALL be per IP address

#### Scenario: Whitelist rate limits

- GIVEN certain IP addresses are whitelisted
- WHEN requests come from a whitelisted IP
- THEN rate limiting SHALL be bypassed
- AND the IP list SHALL be configurable

### Requirement: Error handling

The system SHALL handle errors gracefully with appropriate HTTP status codes.

#### Scenario: 400 Bad Request

- GIVEN invalid query parameters are provided
- THEN a 400 error SHALL be returned
- AND the error message SHALL describe which parameter was invalid
- AND the error SHALL include the expected format

#### Scenario: 404 Not Found

- GIVEN a requested resource (run, step) does not exist
- THEN a 404 error SHALL be returned
- AND the error message SHALL indicate which resource was not found

#### Scenario: 500 Internal Server Error

- GIVEN an unexpected error occurs
- THEN a 500 error SHALL be returned
- AND the error message SHALL be generic (for security)
- AND detailed error SHALL be logged server-side

#### Scenario: 503 Service Unavailable

- GIVEN the database is unavailable
- THEN a 503 error SHALL be returned
- AND the error message SHALL indicate service unavailability
- AND the health check SHALL reflect this status

### Requirement: CORS configuration

The system SHALL support CORS for frontend integration.

#### Scenario: Development CORS

- GIVEN the application is in development mode
- WHEN any origin makes a request
- THEN CORS SHALL be allowed for all origins
- AND credentials SHALL be allowed

#### Scenario: Production CORS

- GIVEN the application is in production mode
- WHEN a request is made from an allowed origin
- THEN CORS SHALL be permitted
- AND requests from other origins SHALL be blocked
- AND the allowed origins list SHALL be configurable

### Requirement: API versioning

The system SHALL support API versioning.

#### Scenario: Version prefix

- GIVEN the API is accessed
- WHEN requests are made to `/v1/runs`
- THEN the v1 API SHALL be used
- AND all endpoints SHALL be prefixed with `/v1`

#### Scenario: Version negotiation

- GIVEN a client specifies `Accept: application/vnd.api+json; version=1`
- WHEN the request is processed
- THEN the appropriate version SHALL be served
- AND unsupported versions SHALL return 400 Bad Request