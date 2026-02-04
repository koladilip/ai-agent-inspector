# Specifications Overview

This directory contains the complete technical specifications for all components of the Agent Inspector system. Each specification defines the requirements, behaviors, and interfaces for a specific component.

## 📋 Purpose

These specifications serve as the **source of truth** for:

- **Implementation** - Engineers use specs to understand what to build
- **Testing** - QA uses spec scenarios to create test cases
- **Reviews** - Reviewers check code against spec requirements
- **Onboarding** - New team members learn system architecture through specs

## 🗂️ Specifications by Component

### 1. Core Tracing (`core-tracing/spec.md`)

**Purpose:** Provide a framework-agnostic trace SDK for AI agents.

**Key Responsibilities:**
- Context manager for trace runs (`trace.run()`)
- Event emission methods (`trace.llm()`, `trace.tool()`, `trace.memory_*()`)
- Non-blocking in-memory queue (never blocks agent execution)
- Background worker thread for batched event processing
- Sampling support (rate-based and error-only)

**Event Types:**
- `run_start` - Beginning of agent execution
- `llm_call` - LLM invocations
- `tool_call` - Tool/function executions
- `memory_read` - Memory retrieval
- `memory_write` - Memory storage
- `error` - Exception tracking
- `final_answer` - Agent completion

**Performance Targets:**
- Queue operation: <100 microseconds
- Event creation: <1 millisecond
- No I/O on agent thread

---

### 2. Configuration (`configuration/spec.md`)

**Purpose:** Centralized configuration system with environment variable support.

**Key Features:**
- `TraceConfig` class with sensible defaults
- Environment variable overrides (`TRACE_*`)
- Redaction rules (`redact_keys`, `redact_patterns`)
- Sampling configuration (`sample_rate`, `only_on_error`)
- Queue and batch settings
- Encryption configuration
- Profile presets (`production`, `development`, `debug`)

**Configuration Hierarchy:**
1. Code defaults
2. Environment variables
3. Runtime config object
4. Profile presets

---

### 3. Data Processing (`data-processing/spec.md`)

**Purpose:** Secure and efficient data processing pipeline.

**Processing Order:**
1. **Redaction** - Remove sensitive data by key or pattern
2. **Serialization** - Convert to compact JSON
3. **Compression** - Gzip compression (5-10x reduction)
4. **Encryption** - Fernet symmetric encryption (optional)

**Capabilities:**
- Key-based redaction (passwords, API keys)
- Pattern-based redaction (SSNs, credit cards, tokens)
- Custom redaction functions
- Lossless compression
- Encryption at rest with configurable keys

---

### 4. Storage (`storage/spec.md`)

**Purpose:** SQLite-based persistent storage layer.

**Schema:**
- `runs` table - Run metadata (id, name, status, timestamps)
- `steps` table - Individual events with BLOB data

**Features:**
- WAL mode for concurrent access
- Efficient indexing on `run_id` and `timestamp`
- Batch insert operations
- Automatic schema migration
- Prune and vacuum utilities
- Backup and restore support

**Performance:**
- List runs: <100ms
- Get run details: <50ms
- Timeline query: <100ms

---

### 5. API (`api/spec.md`)

**Purpose:** FastAPI REST API for serving trace data to the UI.

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
- Efficient query performance

---

### 6. UI (`ui/spec.md`)

**Purpose:** Simple, responsive web interface for viewing traces.

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
- Responsive design (mobile/tablet/desktop)
- Keyboard navigation and accessibility

---

### 7. Adapters (`adapters/spec.md`)

**Purpose:** Integration layer for popular agent frameworks.

**Included Adapters:**
- **LangChain** - Automatic capture of LLM calls, tool calls, and memory operations

**Adapter Interface:**
- `BaseAdapter` class for creating new adapters
- Standard event translation (framework-specific → Agent Inspector)
- Performance-optimized non-invasive hooking
- Graceful error handling

**Planned Adapters:**
- AutoGen
- CrewAI
- Microsoft Semantic Kernel
- Amazon Bedrock Agents
- LlamaIndex agents

---

## 🔗 Component Interactions

### Data Flow

```
Agent Execution
    ↓ (trace.run())
Core Tracing
    ↓ (queue.put_nowait())
Background Worker
    ↓ (batch process)
Data Processing (redact → serialize → compress → encrypt)
    ↓ (export)
Storage (SQLite)
    ↓ (query)
API (FastAPI)
    ↓ (HTTP)
UI (Web Interface)
```

### Dependencies

| Component | Depends On | Used By |
|-----------|------------|---------|
| Core Tracing | Configuration | Adapters |
| Data Processing | Configuration | Core Tracing |
| Storage | Configuration | API, Core Tracing |
| API | Storage, Configuration | UI |
| UI | API | - |
| Adapters | Core Tracing | External Frameworks |

### Configuration Impact

| Config Setting | Affects Components |
|----------------|-------------------|
| `sample_rate` | Core Tracing, Storage |
| `redact_keys` | Data Processing |
| `encryption_enabled` | Data Processing, Storage |
| `queue_size` | Core Tracing |
| `batch_size` | Core Tracing, Storage |

---

## 📖 How to Use Specifications

### For Implementation

1. **Read the relevant spec** - Understand all requirements
2. **Study scenarios** - Each scenario defines testable behavior
3. **Check dependencies** - What other components you interact with
4. **Follow event model** - Use consistent JSON schemas
5. **Meet performance targets** - Ensure compliance with guarantees

### For Code Review

1. **Check spec compliance** - Does code implement all requirements?
2. **Verify scenarios** - Are all spec scenarios covered?
3. **Validate interfaces** - Do public APIs match spec?
4. **Review error handling** - Are edge cases addressed?
5. **Check performance** - Are targets met?

### For Testing

1. **Map scenarios to tests** - Each scenario → test case
2. **Cover all event types** - Test each event in the model
3. **Validate error paths** - Test failures and edge cases
4. **Measure performance** - Verify targets are met
5. **Check integration** - Test component interactions

### For Onboarding

**Recommended Reading Order:**
1. `core-tracing/spec.md` - Understand the tracing model
2. `configuration/spec.md` - Learn configuration system
3. `data-processing/spec.md` - Understand data pipeline
4. `storage/spec.md` - See how data is stored
5. `api/spec.md` - Understand the API layer
6. `ui/spec.md` - Learn the user interface
7. `adapters/spec.md` - See framework integrations

---

## 🎯 Spec Format

Each specification follows this structure:

```markdown
# component-name Specification

## Purpose
One-sentence summary of what this component does.

## Requirements
### Requirement: Description
What system shall do.

#### Scenario: Use case
- GIVEN [state]
- WHEN [action]
- THEN [outcome]

#### Scenario: Another use case
...
```

**Key Elements:**

- **Purpose** - Clear statement of component responsibility
- **Requirements** - "SHALL" statements defining behavior
- **Scenarios** - Given/When/Then format for testable behavior

---

## 📊 Spec Statistics

| Spec | Requirements | Scenarios | Lines |
|------|--------------|-----------|-------|
| Core Tracing | 10 | 25 | ~350 |
| Configuration | 8 | 18 | ~200 |
| Data Processing | 6 | 14 | ~180 |
| Storage | 8 | 20 | ~220 |
| API | 7 | 15 | ~190 |
| UI | 9 | 22 | ~250 |
| Adapters | 5 | 12 | ~150 |
| **Total** | **53** | **126** | **~1540** |

---

## 🔄 Updating Specifications

### When to Update

1. **New Feature** - Add requirements and scenarios for new capability
2. **Behavior Change** - Modify existing requirements/scenarios
3. **Bug Fix** - If bug fixes change documented behavior
4. **API Change** - Update interface specifications
5. **Performance Impact** - Update performance targets

### Change Process

1. Create a change proposal in `changes/`
2. Update relevant spec files with new requirements
3. Review with team to ensure alignment
4. Implement the changes
5. Verify all scenarios are tested
6. Update documentation

### Spec Deltas

For changes, create spec deltas in the change proposal:
```
changes/your-feature/
└── specs/
    ├── core-tracing/spec.md  # New requirements only
    └── api/spec.md          # Modified requirements only
```

This makes it easy to review what's changing without reading entire specs.

---

## ✅ Spec Quality Checklist

A specification is complete when:

- [ ] Purpose is clear and concise
- [ ] All requirements use "SHALL" language
- [ ] Every requirement has at least one scenario
- [ ] Scenarios follow Given/When/Then format
- [ ] Event models include full JSON schema
- [ ] Performance targets are specified (if applicable)
- [ ] Error conditions are documented
- [ ] Dependencies on other specs are clear
- [ ] Security considerations are addressed
- [ ] Edge cases are covered

---

## 🔍 Finding What You Need

### "I want to trace an agent..."
→ Read `core-tracing/spec.md` - Understand trace API and event model

### "I want to configure redaction..."
→ Read `configuration/spec.md` - See config options
→ Read `data-processing/spec.md` - Understand redaction rules

### "I want to add a new adapter..."
→ Read `adapters/spec.md` - Learn adapter interface
→ Read `core-tracing/spec.md` - Understand event model

### "I want to add an API endpoint..."
→ Read `api/spec.md` - See endpoint format and conventions

### "I want to add a UI feature..."
→ Read `ui/spec.md` - Understand UI structure and components

### "I want to store new data..."
→ Read `storage/spec.md` - See schema and query patterns

---

## 🚀 Quick Start

### For Developers Starting a New Component

1. Read the relevant spec
2. Identify requirements and scenarios
3. Map scenarios to unit tests
4. Implement requirements
5. Verify all tests pass
6. Check performance targets
7. Document any deviations

### For Reviewers

1. Read the relevant spec
2. Check code against requirements
3. Verify all scenarios are implemented
4. Look for edge case handling
5. Validate error handling
6. Check performance characteristics
7. Ensure alignment with other specs

### For QA Engineers

1. Read the relevant spec
2. Create test cases for each scenario
3. Build integration tests for interactions
4. Create performance tests for targets
5. Test error conditions
6. Verify security requirements

---

## 📚 Additional Resources

- [Core Principles](../principles/core.md) - Philosophy behind all specs
- [Structure Overview](../STRUCTURE.md) - Complete project structure
- [Example Proposal](../changes/example-add-streaming-support/) - How to propose changes
- [Main README](../README.md) - Project overview

---

## 💡 Key Takeaways

### Specs Are Living Documents

Specifications evolve with the codebase:
- New features add requirements
- Bug fixes may require updates
- API changes must be reflected

### Scenarios Drive Testing

Every scenario should have a corresponding test:
- Unit tests for individual requirements
- Integration tests for component interactions
- End-to-end tests for complete flows

### Consistency Matters

All specs should follow the same format:
- Given/When/Then scenarios
- SHALL requirements
- JSON schemas for events
- Performance targets where applicable

---

**Remember:** These specifications are the foundation of the Agent Inspector system. Use them as your guide for implementation, testing, and review. When in doubt, refer to the spec!

*For questions about specific specs, refer to the individual specification files in the subdirectories.*