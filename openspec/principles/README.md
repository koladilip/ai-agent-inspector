# Core Principles

This directory contains the foundational principles that guide every design and implementation decision in the Agent Inspector project.

## 📋 Overview

The Core Principles document (`core.md`) defines the philosophical and architectural guardrails for the entire system. Unlike technical specifications (which define *how* things work), principles define *why* we make certain decisions and what we value.

## 🎯 Why Principles Matter

### Alignment Across the Team
When engineers, designers, and product managers all understand the core principles:
- Decisions become consistent
- Trade-offs are easier to evaluate
- The product has a coherent vision

### Guiding Feature Development
When considering new features or changes:
1. **Does it align with principles?** → If no, reconsider the approach
2. **How does it support the goal?** → Answer: "Why did my agent behave this way?"
3. **What are the trade-offs?** → Principles help evaluate alternatives

### Evaluating External Dependencies
When choosing libraries or frameworks:
- Does it maintain framework agnosticism?
- Does it introduce blocking behavior?
- Does it require external services?
- Does it create vendor lock-in?

## 📚 The 10 Core Principles

### 1. Agent-First Semantics
**Observe agent behavior, not framework internals.**

Traditional tools model function calls and spans. We model agent reasoning, decisions, tool selection, retries, and outcomes. If an event doesn't explain *why* an agent behaved a certain way, it doesn't belong here.

### 2. Framework Agnostic by Design
**No framework is a dependency.**

The core tracer doesn't import LangChain, CrewAI, AutoGen, or any agent framework. We operate on universal primitives (LLM, tool, memory). Frameworks are handled by thin adapters, ensuring portability and long-term maintainability.

### 3. Non-Blocking Above All Else
**Agent execution must never wait for telemetry.**

Telemetry is asynchronous, buffered, batched, and best-effort. Under load, telemetry may be dropped but agents must continue running. Correct agent behavior is always more important than perfect observability.

### 4. Safe by Default
**Traces are assumed to contain sensitive data.**

Field-level redaction, payload minimization, encryption at rest, retention limits, and error-only tracing are applied by default. Full prompt and tool output logging is always opt-in, never implicit.

### 5. Local-First, No Forced SaaS
**Users own their data.**

Traces are stored locally (file or SQLite) by default. No external network calls are required, no vendor lock-in is imposed. The tool must work offline, in restricted environments, and without cloud accounts.

### 6. Minimal Instrumentation Burden
**One-line enablement is the goal.**

Automatic adapters where possible, context-based tracing for custom agents, manual hooks only for advanced cases. Instrumentation should feel like enabling logging, not rewriting your agent.

### 7. Visual Clarity Over Raw Data
**Logs do not create insight—structure does.**

The UI prioritizes execution timelines, decision flow, tool causality, and failure visibility. Raw JSON is a storage format, not a user experience. If a developer cannot answer "what went wrong?" within seconds, the UI has failed.

### 8. Performance-Aware Storage
**Trace data is optimized before it is persisted.**

Processing pipeline: redact → serialize → compress → encrypt (optional) → store. This ensures low IO overhead, small storage footprint, fast UI loading, and production safety.

### 9. Progressive Complexity
**The simplest solution that works today beats a perfect system tomorrow.**

Evolution in layers: simple UI before heavy frontend frameworks, symmetric encryption before KMS, local storage before distributed backends, adapters before full automation. Complexity is added only when real usage demands it.

### 10. Explainability Over Metrics
**We optimize for understanding, not dashboards.**

Focus on agent reasoning, decision correctness, tool reliability, and memory influence. Metrics support insight—but insight is the product. This is not primarily about throughput, QPS, or system health.

## 🔗 Principles to Specifications

The technical specifications in `../specs/` are concrete implementations of these principles:

| Principle | Related Specs |
|-----------|---------------|
| Agent-First Semantics | `core-tracing/spec.md` - event model |
| Framework Agnostic | `adapters/spec.md` - thin adapter layer |
| Non-Blocking | `core-tracing/spec.md` - queue and worker |
| Safe by Default | `configuration/spec.md`, `data-processing/spec.md` - redaction and encryption |
| Local-First | `storage/spec.md` - SQLite, no cloud deps |
| Minimal Instrumentation | `adapters/spec.md` - automatic capture |
| Visual Clarity | `ui/spec.md` - timeline and detail views |
| Performance-Aware | `data-processing/spec.md` - compression pipeline |
| Progressive Complexity | All specs - phased implementation |
| Explainability | `api/spec.md`, `ui/spec.md` - insights over metrics |

## 💡 How to Use These Principles

### When Designing Features
Ask yourself:
1. Does this help answer "Why did my agent behave this way?"
2. Is this framework-agnostic?
3. Will this block agent execution?
4. Is this safe by default?
5. Can this work offline/locally?

### When Reviewing Code
Check if the implementation:
- Violates any core principles?
- Adds unnecessary complexity?
- Creates framework dependencies?
- Blocks the agent thread?
- Compromises data safety?

### When Making Trade-offs
Use principles to prioritize:
- **Performance vs. Completeness** → Non-blocking wins
- **Features vs. Simplicity** → Progressive complexity
- **Usability vs. Security** → Safe by default
- **Integration vs. Portability** → Framework agnostic

### When Accepting PRs
Evaluate against:
- [ ] Aligns with core principles
- [ ] Doesn't create framework dependencies
- [ ] Non-blocking implementation
- [ ] Safe by default
- [ ] Local-first (no forced SaaS)
- [ ] Minimal instrumentation burden
- [ ] Supports explainability

## 🚀 Quick Reference

### The One Question
Every feature, abstraction, and UI element is evaluated against this goal:

> **"Why did my agent behave this way?"**

If it helps answer that question: ✔️ it belongs  
If it does not: ❌ it does not

### Decision Framework
When faced with a design choice:

1. **Check principles first** - Does this violate any principle?
2. **Consider trade-offs** - Which principles are in tension?
3. **Prefer simplicity** - Simple solution today > complex tomorrow
4. **Validate alignment** - Does this answer "the one question"?
5. **Document reasoning** - Capture why this decision was made

## 📖 Further Reading

- **Core Principles Document** - `./core.md` - Detailed explanation of each principle
- **Technical Specifications** - `../specs/` - Implementation details guided by principles
- **Example Proposal** - `../changes/example-add-streaming-support/` - See principles in action
- **Quick Start Guide** - `../OPENSPEC_GUIDE.md` - How to use OpenSpec

## 🤝 Contributing

When contributing to this project:

1. **Read the principles first** - Understand what guides our decisions
2. **Check existing specs** - See how principles are implemented
3. **Propose changes** - Use OpenSpec workflow for new features
4. **Align with principles** - Ensure your work respects the core philosophy

## ⚖️ Tensions Between Principles

Sometimes principles conflict. When they do:

| Conflict | Resolution | Example |
|----------|-------------|---------|
| Performance vs. Completeness | Performance wins (Principle 3) | Drop telemetry rather than block agent |
| Usability vs. Security | Security wins (Principle 4) | Redact by default, opt-in for full data |
| Features vs. Simplicity | Simplicity wins (Principle 9) | Progressive complexity, simple UI first |
| Integration vs. Portability | Portability wins (Principle 2) | Framework adapters, not dependencies |

## 🎯 Success Criteria

We know we're living up to our principles when:

✅ Engineers understand the "why" behind technical decisions  
✅ Code reviews reference principles by number  
✅ New features align with principles without explicit guidance  
✅ The product feels coherent and consistent  
✅ Users can answer "Why did my agent behave this way?" quickly  

---

**Remember:** Principles are not just words on a page—they're the foundation of every decision we make. When in doubt, return to the principles and let them guide you.

*These principles are part of the Agent Inspector project's OpenSpec documentation.*