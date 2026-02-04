Below is a **clean, concise “Core Principles” document** you can directly place in your repository as
`docs/core-principles.md` or in the README.

It is written in **engineering language**, aligned with everything we discussed, and suitable for **open-source + client credibility**.

---

# Core Principles

This project is an **Agent Execution Inspector**—not a logging library, not a chatbot framework, and not a SaaS-first observability platform.
The following principles guide every design and implementation decision.

---

## 1. Agent-First Semantics

**We observe agent behavior, not framework internals.**

Traditional tracing tools model systems as function calls and spans.
Agents are different: they reason, decide, act, observe, retry, and remember.

Therefore, this system models **agent-native concepts**:

* goals and runs
* LLM decisions
* tool selection and execution
* memory reads and writes
* retries and failure loops
* final outcomes

**If an event does not explain *why* an agent behaved a certain way, it does not belong here.**

---

## 2. Framework Agnostic by Design

**No framework is a dependency.**

The core tracer:

* does not import LangChain, CrewAI, AutoGen, or any agent framework
* operates on universal primitives (LLM, tool, memory, decision)

Framework integrations are implemented as **thin adapters**, never as core dependencies.

This ensures:

* portability across stacks
* long-term maintainability
* applicability to custom and proprietary agents

---

## 3. Non-Blocking Above All Else

**Agent execution must never wait for telemetry.**

Telemetry is:

* asynchronous
* buffered
* batched
* best-effort

If the system is under load:

* telemetry may be dropped
* agents must continue running

**Correct agent behavior is always more important than perfect observability.**

---

## 4. Safe by Default

**Traces are assumed to contain sensitive data.**

The system applies defensive controls by default:

* field-level redaction
* configurable payload minimization
* optional encryption at rest
* retention limits
* sampling and error-only tracing

Full prompt and tool output logging is always **opt-in**, never implicit.

---

## 5. Local-First, No Forced SaaS

**Users own their data.**

By default:

* traces are stored locally (file or SQLite)
* no external network calls are required
* no vendor lock-in is imposed

Optional exporters may send data to:

* self-hosted backends
* OpenTelemetry pipelines
* custom endpoints

This tool must remain usable:

* offline
* inside restricted environments
* without cloud accounts

---

## 6. Minimal Instrumentation Burden

**One-line enablement is the goal.**

While full auto-instrumentation is not realistic for all agent architectures, the system provides:

* automatic adapters where possible
* context-based tracing for custom agents
* manual hooks only for advanced or edge cases

Instrumentation should feel like:

> enabling logging
> not
> rewriting your agent

---

## 7. Visual Clarity Over Raw Data

**Logs do not create insight—structure does.**

The UI prioritizes:

* execution timelines
* decision flow
* tool causality
* failure visibility

Raw JSON is a storage format, not a user experience.

If a developer cannot answer *“what went wrong?”* within seconds, the UI has failed.

---

## 8. Performance-Aware Storage

**Trace data is optimized before it is persisted.**

Processing pipeline:

1. redact
2. serialize
3. compress
4. encrypt (optional)
5. store

This ensures:

* low IO overhead
* small storage footprint
* fast UI loading
* production safety

---

## 9. Progressive Complexity

**The simplest solution that works today beats a perfect system tomorrow.**

The system evolves in layers:

* simple UI before heavy frontend frameworks
* symmetric encryption before KMS
* local storage before distributed backends
* adapters before full automation

Complexity is added **only when real usage demands it**.

---

## 10. Explainability Over Metrics

**We optimize for understanding, not dashboards.**

This tool is not primarily about:

* throughput
* QPS
* system health

It is about:

* agent reasoning
* decision correctness
* tool reliability
* memory influence

Metrics support insight—but insight is the product.

---

## Summary

This project exists to answer one question:

> **“Why did my agent behave this way?”**

Every feature, abstraction, and UI element is evaluated against that goal.

If it helps answer that question:
✔ it belongs

If it does not:
✘ it does not


