# Agent Inspector - OpenSpec Documentation

This directory contains the complete OpenSpec specification for the **Agent Execution Inspector**, a framework-agnostic observability tool for AI agents.

## 📋 Overview

The Agent Inspector provides comprehensive tracing and inspection capabilities for AI agent reasoning and tool orchestration. These specifications define the complete system architecture, requirements, and implementation details across all components.

### Project Goals

- ✅ Trace agent reasoning & tool usage
- ✅ Framework-agnostic design
- ✅ Non-blocking & efficient performance
- ✅ Secure handling of sensitive data
- ✅ Simple visual web UI
- ✅ Enterprise-ready with encryption & compression

## 📁 Directory Structure

```
openspec/
├── principles/            # Core principles guiding all design decisions
│   ├── README.md          # Principles overview and how to use them
│   └── core.md           # Detailed core principles document
├── specs/
│   ├── core-tracing/      # Trace SDK, event model, queue system
│   ├── configuration/     # Config management, environment variables
│   ├── data-processing/   # Redaction, compression, encryption
│   ├── storage/           # SQLite database schema & operations
│   ├── api/               # FastAPI backend endpoints
│   ├── ui/                # Web UI, timeline, detail views
│   └── adapters/          # Framework adapters (LangChain, custom)
├── changes/               # Change proposals with design docs and tasks
│   └── example-add-streaming-support/  # Complete example proposal
└── README.md              # This file
```

## 🎯 Core Principles

Before diving into technical specifications, read the **[Core Principles](./principles/)** which guide every design and implementation decision.

The Core Principles document defines:
- **Why** we make certain decisions (not just what we build)
- Architectural guardrails and trade-offs
- How to evaluate new features and changes

**Key Question** that drives everything:
> "Why did my agent behave this way?"

## 📖 Specifications

### 1. core-tracing
Defines the core trace SDK that agents use to emit events.

**Key Components:**
- Context manager for trace runs (`trace.run()`)
- Event emission methods (`trace.llm()`, `trace.tool()`, `trace.memory_read()`, etc.)
- Non-blocking in-memory queue (never blocks agent execution)
- Background worker thread for batched event processing
- Sampling support (rate-based and error-only)

**Event Types:**
- `run_start` - Marks the beginning of an agent run
- `llm_call` - Captures LLM invocations
- `tool_call` - Captures tool/function executions
- `memory_read` - Memory retrieval operations
- `memory_write` - Memory storage operations
- `error` - Exception and failure tracking
- `final_answer` - Agent completion and result

### 2. configuration
Centralized configuration system with environment variable support.

**Key Features:**
- `TraceConfig` class with sensible defaults
- Environment variable overrides (`TRACE_*`)
- Redaction rules configuration (`redact_keys`, `redact_patterns`)
- Sampling configuration (`sample_rate`, `only_on_error`)
- Queue and batch processing settings
- Encryption configuration
- Profile presets (`production`, `development`, `debug`)

### 3. data-processing
Secure and efficient data processing pipeline.

**Pipeline Order:**
1. **Redaction** - Remove sensitive data by key or pattern
2. **Serialization** - Convert to compact JSON
3. **Compression** - Gzip compression (5-10x size reduction)
4. **Encryption** - Fernet symmetric encryption (optional)

**Capabilities:**
- Key-based redaction (passwords, API keys, etc.)
- Pattern-based redaction (SSNs, credit cards, tokens)
- Custom redaction functions
- Lossless compression
- Encryption at rest with configurable keys

### 4. storage
SQLite-based persistent storage layer.

**Schema:**
- `runs` table - Run metadata (id, name, status, timestamps)
- `steps` table - Individual events with BLOB data

**Features:**
- WAL mode for concurrent access
- Efficient indexing on run_id and timestamp
- Batch insert operations
- Automatic schema migration
- Prune and vacuum utilities
- Backup and restore support

### 5. api
FastAPI REST API for serving trace data to the UI.

**Endpoints:**
- `GET /v1/runs` - List runs with filtering and pagination
- `GET /v1/runs/{run_id}` - Get run details
- `GET /v1/runs/{run_id}/steps` - Get all steps for a run
- `GET /v1/runs/{run_id}/timeline` - Optimized timeline data
- `GET /v1/stats` - Database statistics
- `GET /health` - Health check

**Features:**
- Automatic OpenAPI documentation at `/docs`
- CORS support
- Optional API key authentication
- Rate limiting
- Efficient query performance (<100ms for list, <50ms for details)

### 6. ui
Simple, responsive web interface using FastAPI templates and vanilla JS/HTMX.

**Layout:**
- **Left Panel (30%)** - Run list with filters and search
- **Center Panel (45%)** - Timeline visualization
- **Right Panel (25%)** - Detail view for selected events

**Features:**
- Visual timeline with event type icons
- Event filtering (LLM only, Tools only, Errors only)
- Detailed inspection panel with syntax highlighting
- Real-time updates for running runs
- Dark mode support
- Export capabilities (JSON, image)
- Responsive design for mobile/tablet/desktop
- Keyboard navigation and accessibility support

### 7. adapters
Integration layer for popular agent frameworks.

**Included Adapters:**
- **LangChain** - Automatic capture of LLM calls, tool calls, and memory operations

**Adapter Interface:**
- `BaseAdapter` class for creating new adapters
- Standard event translation framework-specific → Agent Inspector
- Performance-optimized non-invasive hooking
- Graceful error handling

**Planned Adapters:**
- AutoGen
- CrewAI
- Microsoft Semantic Kernel
- Amazon Bedrock Agents
- LlamaIndex agents

## 🚀 Using OpenSpec

### Step 0: Understand the Principles

Before creating proposals or implementing features, read the **[Core Principles](./principles/core.md)**. These principles:

1. Align the team on philosophy and goals
2. Guide feature development and trade-offs
3. Help evaluate external dependencies
4. Inform code review decisions

### Step 1: Creating Proposals




### Installation

### Creating Proposals

To create a new change proposal:

```bash
/openspec:proposal Add support for streaming LLM responses
```

This will:
1. Search existing specs for related requirements
2. Read relevant codebase files
3. Generate a proposal with:
   - `proposal.md` - Description of the change
   - `design.md` - Technical decisions
   - `tasks.md` - Implementation tasks
   - `specs/` - Spec deltas showing requirement changes

### Reviewing Changes

When a proposal is created, reviewers can:

1. Review the proposal document
2. Understand spec deltas without digging through code
3. Provide feedback on design decisions
4. Break down tasks before implementation begins

### Updating Specs

To update existing requirements:

1. Navigate to the relevant spec file
2. Modify requirements and scenarios
3. Commit changes
4. OpenSpec will track spec deltas

## 🎯 Development Phases

### Phase 1 - Core Infrastructure (Week 1)
- ✅ Trace SDK
- ✅ Queue + worker
- ✅ JSON storage
- ✅ Redaction
- ✅ Compression

### Phase 2 - Security & API (Week 2)
- ✅ Encryption
- ✅ FastAPI backend
- ✅ UI timeline
- ✅ Demo agent
- ✅ Documentation

### Phase 3 - Adapters & Polish (Future)
- ✅ LangChain adapter
- ⏳ Additional framework adapters
- ⏳ Advanced UI features
- ⏳ Performance optimizations

## 🔒 Security Considerations

The Agent Inspector is designed with security as a first-class concern:

- **Redaction** - Sensitive fields are removed before storage
- **Encryption** - Data can be encrypted at rest using Fernet
- **Non-blocking** - Agent performance is never impacted
- **Configurable** - Security settings can be tuned per environment

## 📊 Performance Guarantees

| Aspect | Strategy | Target |
|--------|----------|--------|
| Blocking | Queue + worker | <1ms per event |
| IO | Batched writes | <100ms API responses |
| Size | Compression | 5-10x reduction |
| Privacy | Redaction | Configurable patterns |
| Load | Sampling | Configurable rate |

## 🧪 Example Usage

### Basic Tracing

```python
from agent_inspector import trace

with trace.run("flight_search"):
    trace.llm(prompt="Decide tool", response="Use search")
    trace.tool(name="search", args={"q": "cheap flight"}, result="...")
    trace.final(answer="Cheapest is Indigo")
```

### With LangChain Adapter

```python
from agent_inspector.adapters.langchain import enable

enable()  # Automatic tracing, no code changes needed!

# Your LangChain agent runs here
# All LLM calls, tool calls, and memory ops are automatically traced
```

### Custom Configuration

```python
from agent_inspector import TraceConfig, trace

config = TraceConfig(
    sample_rate=0.1,
    redact_keys=["password", "api_key"],
    encryption_enabled=True
)

with trace.run("task", config=config):
    # Your agent code
    pass
```

## 🤝 Contributing

To contribute new specifications or update existing ones:

1. Identify the relevant spec file in `openspec/specs/`
2. Add or modify requirements following the `Requirement` / `Scenario` pattern
3. Ensure all changes include clear, testable scenarios
4. Update this README if adding new capabilities

## 📚 Additional Resources

- [OpenSpec Documentation](https://openspec.dev)
- [OpenSpec GitHub](https://github.com/Fission-AI/OpenSpec/)
- [OpenSpec Discord](https://discord.gg/YctCnvvshC)

## 🏷️ Positioning

**Agent Inspector** answers the question:
> "Why did my agent behave this way?"

Not just:
> "Which function ran?"

This positions Agent Inspector as an **agent systems engineering** tool, focused on:
- Agent reasoning traces
- Decision making
- Hallucination detection
- Tool orchestration
- Memory operations

---

**Made with OpenSpec** - The lightweight spec-driven framework for AI infrastructure development.