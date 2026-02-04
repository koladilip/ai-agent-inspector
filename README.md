<div align="center">

# 🔍 Agent Inspector

**Framework-agnostic observability for AI agents**

A lightweight, non-blocking tracing system for monitoring and debugging AI agent reasoning, tool usage, and execution flow.

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)]()

</div>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [API Documentation](#api-documentation)
- [Framework Adapters](#framework-adapters)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

**Agent Inspector** answers the question: *"Why did my agent behave this way?"*

Unlike traditional logging or tracing tools, Agent Inspector is designed specifically for AI agents with:

- **Agent-first semantics** - Tracks reasoning, decisions, and tool orchestration
- **Framework agnostic** - Works with LangChain, AutoGen, custom agents, and more
- **Non-blocking** - Never impacts agent performance (<1ms overhead)
- **Secure by default** - Automatic redaction, compression, and encryption
- **Local-first** - No SaaS required, all data stays on your machine
- **Simple UI** - Visual timeline for understanding agent behavior

### What Makes It Different

Traditional tools model systems as function calls and spans. Agent Inspector models:
- 🤖 **LLM decisions** - Why did the agent choose this tool?
- 🔧 **Tool execution** - What arguments were passed? What was the result?
- 📖 **Memory operations** - What did the agent read/write?
- ❌ **Failure modes** - Where did the agent get stuck or fail?
- ✅ **Final outcomes** - What was the final answer?

---

## Features

### Core Tracing
- ✅ Context manager API for easy instrumentation
- ✅ Event types: LLM calls, tool calls, memory operations, errors
- ✅ Non-blocking queue and background worker
- ✅ Sampling support (rate-based and error-only)
- ✅ Thread-safe for concurrent execution

### Data Pipeline
- 🔒 **Redaction** - Remove sensitive data by key or pattern
- 📦 **Serialization** - Compact JSON for storage
- 🗜️ **Compression** - 5-10x size reduction with gzip
- 🔐 **Encryption** - Fernet symmetric encryption (optional)

### Storage
- 💾 SQLite database with WAL mode for concurrent access
- 📊 Efficient indexing on run_id and timestamp
- 🧹 Automatic pruning and vacuum utilities
- 💾 Backup and restore support

### API & UI
- 🌐 FastAPI REST API with OpenAPI docs
- 🎨 Simple three-panel web interface
- Left panel: Run list with filters and search
- Center panel: Timeline visualization
- Right panel: Detail view for events
- 🌙 Dark mode support
- ⚡ Real-time updates for running runs

### Adapters
- 🔌 **LangChain** - Automatic tracing, no code changes needed
- 🔌 **AutoGen** - Coming soon
- 🔌 **CrewAI** - Coming soon
- 🔌 Custom adapters - Easy to create for any framework

---

## Installation

### Requirements

- Python 3.9 or higher
- pip or another package manager

### Install from PyPI

```bash
pip install agent-inspector
```

### Install from Source

```bash
git clone https://github.com/Fission-AI/AgentInspector.git
cd AgentInspector
pip install -e .
```

### Optional Dependencies

```bash
# For LangChain adapter
pip install "agent-inspector[langchain]"

# For development
pip install "agent-inspector[dev]"
```

---

## Quick Start

### 1. Initialize Agent Inspector

```bash
agent-inspector init
```

This creates a default configuration and initializes the SQLite database.

### 2. Start Tracing in Your Code

```python
from agent_inspector import trace

# Wrap your agent execution in a trace context
with trace.run("my_agent"):
    # Your agent code here
    trace.llm(
        model="gpt-4",
        prompt="What is the capital of France?",
        response="The capital of France is Paris."
    )
    
    trace.tool(
        tool_name="search",
        tool_args={"query": "capital of France"},
        tool_result="Paris"
    )
    
    trace.final(answer="The capital of France is Paris.")
```

### 3. Start the API Server

```bash
agent-inspector server
```

### 4. View Traces in the UI

Open your browser to: **http://localhost:8000/**  
Root redirects to **/ui/**.

---

## Architecture

Agent Inspector is built around explicit interfaces so each layer can evolve independently.

### SDK Core
- `Trace` provides the context manager API (`trace.run(...)`) and event emission.
- Events are immutable dictionaries serialized by the processing pipeline.
- Events flow into an `Exporter` which handles delivery.

### Exporters
- The SDK depends on the `Exporter` interface.
- `StorageExporter` implements it using the database + pipeline.
- Alternative exporters can be plugged in without changing the SDK.

### Storage
- SQLite with WAL mode for concurrent access.
- Runs and steps are stored separately for efficient queries.

### API & UI
- API depends on a `ReadStore` interface to query runs and steps.
- UI is served as static assets under `/ui/static`.

---

## Configuration

### Configuration Presets

Agent Inspector comes with three configuration presets:

#### Production
```bash
agent-inspector config --profile production
```
- Sample rate: 1%
- Compression: Enabled
- Encryption: Enabled
- Log level: WARNING

#### Development
```bash
agent-inspector config --profile development
```
- Sample rate: 50%
- Compression: Enabled
- Encryption: Disabled
- Log level: INFO

#### Debug
```bash
agent-inspector config --profile debug
```
- Sample rate: 100%
- Compression: Disabled
- Encryption: Disabled
- Log level: DEBUG

### Environment Variables

Configure Agent Inspector using environment variables:

```bash
# Presets
export TRACE_PROFILE=development

# Sampling
export TRACE_SAMPLE_RATE=0.5
export TRACE_ONLY_ON_ERROR=false

# Queue & Batch
export TRACE_QUEUE_SIZE=1000
export TRACE_BATCH_SIZE=50
export TRACE_BATCH_TIMEOUT=1000

# Redaction
export TRACE_REDACT_KEYS="password,api_key,token"
export TRACE_REDACT_PATTERNS="\\b\\d{3}-\\d{2}-\\d{4}\\b"

# Encryption
export TRACE_ENCRYPTION_ENABLED=true
export TRACE_ENCRYPTION_KEY=your-secret-key-here

# Storage
export TRACE_DB_PATH=agent_inspector.db
export TRACE_RETENTION_DAYS=30

# API
export TRACE_API_HOST=127.0.0.1
export TRACE_API_PORT=8000
export TRACE_API_KEY_REQUIRED=false
export TRACE_API_KEY=your-api-key

# UI
export TRACE_UI_ENABLED=true
export TRACE_UI_PATH=/ui

# Processing
export TRACE_COMPRESSION_ENABLED=true
export TRACE_COMPRESSION_LEVEL=6

# Logging
export TRACE_LOG_LEVEL=INFO
export TRACE_LOG_PATH=agent_inspector.log
```

### Custom Configuration

Create a custom configuration in code:

```python
from agent_inspector import TraceConfig, set_config

config = TraceConfig(
    sample_rate=1.0,  # Trace all runs
    only_on_error=False,
    redact_keys=["password", "api_key", "secret"],
    redact_patterns=[
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
        r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",  # Credit card
    ],
    encryption_enabled=False,
    compression_enabled=True,
    compression_level=6,
    queue_size=1000,
    batch_size=50,
    db_path="custom_inspector.db",
    retention_days=30,
)

set_config(config)
```

---

## Usage Examples

### Basic Agent Tracing

```python
from agent_inspector import trace

def search_flights_agent(user_query):
    with trace.run("flight_search", user_id="user123"):
        # Agent decides which tool to use
        trace.llm(
            model="gpt-4",
            prompt=f"User: {user_query}. Which tool should I use?",
            response="Use the search_flights tool."
        )
        
        # Tool execution
        trace.tool(
            tool_name="search_flights",
            tool_args={"query": user_query},
            tool_result={
                "flights": [
                    {"airline": "Delta", "price": "$350"},
                    {"airline": "United", "price": "$320"},
                ]
            }
        )
        
        # Agent processes results
        trace.llm(
            model="gpt-4",
            prompt=f"Found 2 flights. Which should I recommend?",
            response="Recommend United for $320, it's cheaper."
        )
        
        # Final answer
        trace.final(
            answer="I recommend United Airlines for $320. It's the cheapest option."
        )

# Run the agent
search_flights_agent("Find flights from SFO to JFK")
```

### Real Agent Example (OpenAI-compatible)

This example makes real LLM calls and runs multiple scenarios.

```bash
cp .env.example .env
```

Set these in `.env`:
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

Run a single question:
```bash
python examples/real_agent.py "What is 13 * (7 + 5)?"
```

Run the full scenario suite:
```bash
python examples/real_agent.py --suite
```

### With LangChain (Automatic)

```python
from langchain.agents import initialize_agent, Tool, AgentType
from langchain.llms import OpenAI
from agent_inspector.adapters import enable_langchain

# Initialize your LangChain agent
llm = OpenAI(temperature=0)
tools = [
    Tool(name="search", func=search_flights, description="Search for flights")
]
agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION)

# Use with automatic tracing
with enable_langchain(run_name="langchain_flight_agent") as callbacks:
    result = agent.run("Find flights from SFO to JFK")
    print(result)
```

That's it! All LLM calls, tool calls, and agent actions are automatically traced.

### Error Handling

```python
from agent_inspector import trace

with trace.run("error_demo"):
    try:
        # Successful operation
        trace.llm(
            model="gpt-4",
            prompt="What is 2+2?",
            response="4"
        )
        
        # Tool that fails
        trace.tool(
            tool_name="broken_tool",
            tool_args={"input": "test"},
            tool_result="Error: Connection timeout"
        )
        
        # Log the error
        trace.error(
            error_type="ConnectionError",
            error_message="Tool failed to connect",
            critical=False
        )
        
        # Continue with fallback
        trace.tool(
            tool_name="fallback_tool",
            tool_args={"input": "test"},
            tool_result="success"
        )
        
    except Exception as e:
        # Log unexpected errors
        trace.error(
            error_type=type(e).__name__,
            error_message=str(e),
            critical=True
        )
        raise
```

### Nested Agents

```python
from agent_inspector import trace

# Main agent
with trace.run("planning_agent", user_id="user123") as main_ctx:
    trace.llm(
        model="gpt-4",
        prompt="User wants to book a flight. Should I delegate?",
        response="Yes, delegate to booking agent."
    )
    
    # Sub-agent (nested)
    with trace.run("booking_agent", session_id="booking_456"):
        trace.tool(
            tool_name="book_flight",
            tool_args={"flight_id": "UA123"},
            tool_result={"status": "confirmed", "confirmation": "CONF-12345"}
        )
        
        trace.final(answer="Flight booked successfully!")
    
    # Main agent continues
    trace.final(answer="I've booked your flight. Confirmation: CONF-12345")
```

### Memory Operations

```python
from agent_inspector import trace

with trace.run("memory_agent"):
    # Read from memory
    trace.memory_read(
        memory_key="user_preferences",
        memory_value={"preferred_airline": "Delta", "seat": "window"},
        memory_type="key_value"
    )
    
    # Write to memory
    trace.memory_write(
        memory_key="last_search",
        memory_value={"query": "SFO to JFK", "timestamp": 1234567890},
        memory_type="key_value",
        overwrite=True
    )
    
    trace.final(answer="I found your preferences and remembered your search.")
```

---

## API Documentation

Once you start the API server, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Main Endpoints

#### Health Check
```
GET /health
```

#### List Runs
```
GET /v1/runs
  ?limit=100
  &offset=0
  &status=completed
  &user_id=user123
  &search=flight
```

#### Get Run Details
```
GET /v1/runs/{run_id}
```

#### Get Run Timeline
```
GET /v1/runs/{run_id}/timeline
  ?include_data=true
```

#### Get Run Steps
```
GET /v1/runs/{run_id}/steps
  ?limit=50
  &offset=0
  &event_type=llm_call
```

#### Get Step Data
```
GET /v1/runs/{run_id}/steps/{step_id}/data
```

#### Statistics
```
GET /v1/stats
```

---

## Framework Adapters

### LangChain

Install the optional dependency:

```bash
pip install "agent-inspector[langchain]"
```

Automatic tracing:

```python
from agent_inspector.adapters import enable_langchain
from langchain.agents import initialize_agent

# Create agent
agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION)

# Trace automatically
with enable_langchain() as callbacks:
    result = agent.run("Your query here")
```

Manual callback handler:

```python
from agent_inspector.adapters import get_callback_handler

# Get callback handler
callbacks = [get_callback_handler()]

# Use with LangChain chains
chain = LLMChain(llm=llm, prompt=prompt)
result = chain.run("Your query", callbacks=callbacks)
```

### Creating Custom Adapters

Create a new adapter by extending `BaseCallbackHandler` (for LangChain-like frameworks) or by using the Trace SDK directly:

```python
from agent_inspector import Trace, get_trace

class CustomAdapter:
    def __init__(self, trace: Trace = None):
        self.trace = trace or get_trace()
    
    def on_llm_call(self, model, prompt, response):
        """Handle LLM calls in your framework."""
        context = self.trace.get_active_context()
        if context:
            context.llm(model=model, prompt=prompt, response=response)
    
    def on_tool_call(self, tool_name, args, result):
        """Handle tool calls in your framework."""
        context = self.trace.get_active_context()
        if context:
            context.tool(tool_name=tool_name, tool_args=args, tool_result=result)

# Use your adapter
with trace.run("custom_agent"):
    adapter = CustomAdapter()
    
    # Your framework code
    adapter.on_llm_call("gpt-4", "Hello", "Hi there!")
```

---

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/Fission-AI/AgentInspector.git
cd AgentInspector

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=agent_inspector --cov-report=html
```

### Project Structure

```
agent_inspector/
├── core/              # Core tracing SDK
│   ├── config.py     # Configuration management
│   ├── events.py     # Event model
│   ├── interfaces.py # Exporter and ReadStore protocols
│   ├── queue.py      # Non-blocking queue
│   └── trace.py      # Main Trace SDK
├── processing/         # Data processing pipeline
│   └── pipeline.py   # Redaction, compression, encryption
├── storage/           # SQLite database
│   ├── database.py   # Database operations
│   └── exporter.py   # Storage exporter implementation
├── api/               # FastAPI REST API
│   └── main.py       # API server
├── ui/                # Web interface
│   ├── app.py        # UI router + static mounting
│   ├── static/       # CSS/JS assets
│   └── templates/    # HTML templates
├── adapters/           # Framework integrations
│   └── langchain_adapter.py
└── cli.py             # Command-line interface
```

### Running Examples

```bash
# Basic tracing example
python examples/basic_tracing.py

# Real agent example (OpenAI-compatible)
python examples/real_agent.py "What is 13 * (7 + 5)?"

# Start API server
python -m agent_inspector.cli server

# View statistics
python -m agent_inspector.cli stats

# Prune old data
python -m agent_inspector.cli prune --retention-days 30 --vacuum
```

### Code Quality

```bash
# Format code
black agent_inspector/ examples/ tests/

# Lint code
flake8 agent_inspector/

# Type check
mypy agent_inspector/
```

---

## Contributing

We welcome contributions! Here's how to get started:

### Reporting Issues

1. Check existing issues on GitHub
2. Create a new issue with:
   - Clear description of the bug or feature
   - Steps to reproduce (for bugs)
   - Expected vs actual behavior
   - Environment details (Python version, OS, etc.)

### Submitting Pull Requests

1. Fork the repository
2. Create a feature branch:
   ```bash
   git checkout -b feature/my-feature
   ```
3. Make your changes
4. Run tests:
   ```bash
   pytest
   ```
5. Ensure code quality:
   ```bash
   black agent_inspector/
   flake8 agent_inspector/
   ```
6. Commit your changes
7. Push to your fork
8. Create a pull request

### Development Guidelines

- Follow PEP 8 style guide
- Add tests for new features
- Update documentation
- Keep changes minimal and focused
- Align with the [Core Principles](openspec/principles/core.md)

---

## CLI Commands

```bash
# Initialize Agent Inspector
agent-inspector init [--profile production|development|debug]

# Start API server
agent-inspector server [--host HOST] [--port PORT]

# View statistics
agent-inspector stats

# Prune old traces
agent-inspector prune [--retention-days N] [--vacuum]

# Vacuum database
agent-inspector vacuum

# Create backup
agent-inspector backup /path/to/backup.db

# View configuration
agent-inspector config [--show] [--profile PROFILE]

# Show version
agent-inspector --version
```

---

## Performance

Agent Inspector is designed for minimal overhead:

| Operation | Target | Typical |
|-----------|--------|---------|
| Queue event | <100μs | ~50μs |
| Create event | <1ms | ~200μs |
| Compress data | N/A | 5-10x reduction |
| API latency | <100ms | ~50ms |
| UI load | <500ms | ~200ms |

### Memory Usage

- Queue: ~10KB (1000 events × 10 bytes/event)
- Background thread: ~5MB (batch processing)
- Database: Varies with trace volume

---

## Security

### Default Protections

- 🔒 **Redaction** - Sensitive keys redacted by default
- 🗜️ **Compression** - Reduces storage footprint
- 🔐 **Encryption** - Fernet encryption (optional)
- 📊 **Sampling** - Reduces data collection volume
- 💾 **Local-First** - No data leaves your machine

### Best Practices

1. **Never log API keys** - Use redaction or environment variables
2. **Enable encryption** - For production deployments
3. **Use sampling** - Reduce overhead in high-traffic scenarios
4. **Review traces** - Regularly audit what's being captured
5. **Prune old data** - Set appropriate retention policies

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Support

- 📖 [Documentation](https://github.com/Fission-AI/AgentInspector#readme)
- 🐛 [Issue Tracker](https://github.com/Fission-AI/AgentInspector/issues)
- 💬 [Discord](https://discord.gg/YctCnvvshC)
- 📧 Email: team@agentinspector.dev

---

## Acknowledgments

Built with [OpenSpec](https://openspec.dev) - The lightweight spec-driven framework for AI infrastructure development.

---

<div align="center">

**Made with ❤️ by the Agent Inspector Team**

[⭐ Star us on GitHub](https://github.com/Fission-AI/AgentInspector)
</div>
