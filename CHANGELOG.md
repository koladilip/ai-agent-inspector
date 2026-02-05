# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.2](https://github.com/koladilip/ai-agent-inspector/compare/v1.1.1...v1.1.2) (2026-02-05)


### Miscellaneous Chores

* release 1.1.2 ([5f64b7b](https://github.com/koladilip/ai-agent-inspector/commit/5f64b7b94a3e373014bdc0610a13e2e7209acaff))

## 1.1.1 (2026-02-05)


### Features

* clarify docs ([1d25a08](https://github.com/koladilip/ai-agent-inspector/commit/1d25a083fec1fc29a9b218faaec57900672f6653))


### Miscellaneous Chores

* fix release please ([403b19e](https://github.com/koladilip/ai-agent-inspector/commit/403b19ef3bb23791085edbfa909bf13e93299844))

## [1.1.0](https://github.com/koladilip/ai-agent-inspector/compare/v1.0.0...v1.1.0) (2026-02-04)


### Features

* clarify docs ([1d25a08](https://github.com/koladilip/ai-agent-inspector/commit/1d25a083fec1fc29a9b218faaec57900672f6653))

## [1.0.0] - 2025-02-04

### Added

- Trace SDK: `trace.run()`, `trace.llm()`, `trace.tool()`, `trace.memory_read()` / `trace.memory_write()`, `trace.error()`, `trace.final()`, `trace.emit()`
- Configuration: `TraceConfig`, presets (production, development, debug), env vars, redaction, encryption, compression
- Events: run_start, run_end, llm_call, tool_call, memory_read/write, error, final_answer, CUSTOM
- Non-blocking queue with batch flush and drain on shutdown
- Storage: SQLite with WAL, processing pipeline (redact, serialize, compress, encrypt)
- Exporters: `Exporter` protocol, `StorageExporter`, `CompositeExporter`
- Samplers: `Sampler` protocol, default hash-based sampling, pluggable via `Trace(sampler=...)`
- API: FastAPI server with `/v1/runs`, `/v1/runs/{id}`, `/v1/runs/{id}/timeline`, `/v1/runs/{id}/export`, `/v1/stats`, health, optional API key auth
- UI: three-panel web interface (run list, timeline, detail view)
- CLI: `agent-inspector` (server, init, config, stats, prune, backup, export, vacuum). PyPI package name: `ai-agent-inspector`.
- LangChain adapter: `enable_langchain()` for automatic tracing
- Testing: `set_trace()` / `get_trace()` for injection; version from `pyproject.toml` via `importlib.metadata`
- **Date range filter**: `list_runs(started_after=..., started_before=...)` (DB, API, ReadStore); query params `started_after` / `started_before` (ms since epoch)
- **Export run(s) to JSON**: `GET /v1/runs/{run_id}/export`; CLI `agent-inspector export <run_id> [--output file.json]` and `agent-inspector export --all [--limit N] [--output file.json]`. Install: `pip install ai-agent-inspector`.
- **Critical-event backpressure**: `TraceConfig.block_on_run_end` and `run_end_block_timeout_ms`; when set, run_end is queued with a blocking put (up to timeout) so it is not dropped under backpressure
- **Async context**: Trace context stack uses `contextvars` so the active context is correct in both sync and async (asyncio) code
- **OpenTelemetry OTLP exporter**: optional `agent_inspector.exporters.otel.OTLPExporter`; install with `pip install ai-agent-inspector[otel]`

### Security

- Default redaction keys and patterns; configurable `redact_keys` / `redact_patterns`
- Optional Fernet encryption at rest
