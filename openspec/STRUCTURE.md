# Agent Inspector - OpenSpec Structure

Complete overview of the OpenSpec specification structure for the Agent Inspector project.

## 📊 Structure Overview

```
openspec/
├── principles/                           # Foundational philosophy
│   ├── README.md                         # Principles overview & usage
│   └── core.md                          # The 10 Core Principles
│
├── specs/                                # Technical specifications
│   ├── core-tracing/                     # Trace SDK & event system
│   ├── configuration/                      # Config management
│   ├── data-processing/                   # Redaction, compression, encryption
│   ├── storage/                           # SQLite database
│   ├── api/                               # FastAPI backend
│   ├── ui/                                # Web interface
│   └── adapters/                          # Framework integrations
│
├── changes/                              # Change proposals
│   └── example-add-streaming-support/   # Complete example proposal
│       ├── proposal.md                    # Feature overview
│       ├── design.md                      # Technical architecture
│       ├── tasks.md                       # Implementation roadmap
│       ├── specs/                         # Spec deltas
│       │   └── core-tracing/
│       │       └── spec.md              # Requirements that change
│       └── README.md                      # Workflow explanation
│
└── README.md                             # Main documentation
```

---

## 🎯 Recommended Reading Order

### For New Team Members

1. **Start with Philosophy**
   - `principles/core.md` - Understand the "why" behind everything
   - `principles/README.md` - How to apply principles

2. **Understand the System**
   - `specs/README.md` - Overview of all components
   - `README.md` - Complete OpenSpec documentation

3. **Study an Example**
   - `changes/example-add-streaming-support/README.md` - How OpenSpec works
   - `changes/example-add-streaming-support/proposal.md` - Sample proposal

4. **Deep Dive into Specs**
   - Read each spec based on your role/interest
   - Focus on scenarios for behavior understanding

### For Creating New Features

1. `principles/core.md` - Ensure alignment with principles
2. `/openspec:proposal <feature>` - Generate initial proposal
3. Fill in `proposal.md`, `design.md`, `tasks.md`
4. Update relevant specs in `specs/`
5. Create spec deltas in `changes/<feature-name>/specs/`

### For Reviewing Changes

1. Read `proposal.md` - Understand the "why"
2. Review `design.md` - Validate the "how"
3. Check `tasks.md` - Ensure completeness
4. Examine spec deltas - See what requirements change
5. Cross-check with `principles/core.md` - Verify alignment

---

## 📁 Detailed Structure

### Principles Directory

**Purpose:** Foundational guidance that defines philosophy and architectural guardrails.

```
principles/
├── README.md          # Overview of principles and how to use them
└── core.md           # The 10 Core Principles document
```

**When to use:**
- Before creating new features
- During code reviews
- When making trade-off decisions
- For team onboarding

**Key questions addressed:**
- Why do we build things this way?
- What principles guide our decisions?
- How should we evaluate alternatives?

---

### Specs Directory

**Purpose:** Technical specifications defining "how" the system works.

```
specs/
├── core-tracing/
│   └── spec.md        # Trace SDK, events, queue, sampling
├── configuration/
│   └── spec.md        # TraceConfig, env vars, presets
├── data-processing/
│   └── spec.md        # Redaction → Compress → Encrypt
├── storage/
│   └── spec.md        # SQLite schema, queries, operations
├── api/
│   └── spec.md        # FastAPI endpoints, models
├── ui/
│   └── spec.md        # Web UI, timeline, detail views
└── adapters/
    └── spec.md        # Framework integrations
```

**Spec Format:**
```markdown
# component-name Specification

## Purpose
One-sentence summary.

## Requirements
### Requirement: Description
What system shall do.

#### Scenario: Use case
- GIVEN [state]
- WHEN [action]
- THEN [outcome]
```

**When to use:**
- Implementation reference
- Behavior verification
- Understanding component purpose
- Code review guidance

---

### Changes Directory

**Purpose:** Change proposals for new features or modifications.

```
changes/
└── example-add-streaming-support/
    ├── proposal.md              # What we want to change and why
    ├── design.md                # How we'll implement it
    ├── tasks.md                 # Implementation tasks (25 tasks, 106 hours)
    ├── specs/                   # Spec deltas
    │   └── core-tracing/
    │       └── spec.md        # Requirements that will change
    └── README.md               # Workflow explanation
```

**Proposal Files:**

1. **proposal.md**
   - Motivation (current state, problems, impact)
   - Proposed solution (high-level approach)
   - Benefits (value provided)
   - Affected components (what changes)
   - Migration path (phased implementation)
   - Risks and mitigations
   - Success criteria

2. **design.md**
   - Architecture overview (system diagram)
   - Data model (schema, in-memory structures)
   - Core changes (new APIs, event models)
   - Storage layer (queries, indexing)
   - API design (endpoints, request/response)
   - UI implementation (component designs)
   - Adapter integration (framework-specific)
   - Performance optimization (strategies)
   - Security considerations (token handling)
   - Testing strategy (unit, integration, performance)
   - Rollout plan (phases, monitoring)

3. **tasks.md**
   - 25 specific tasks
   - Time estimates (106 hours total ≈ 3 weeks)
   - Priority levels (P0, P1, P2, P3)
   - Dependencies between tasks
   - Acceptance criteria for each task
   - Owner assignments
   - Risk mitigation

4. **specs/** (Spec Deltas)
   - Requirements that will be added/modified
   - Shows impact on existing specs
   - Easy to review without reading full specs

**When to use:**
- Planning new features
- Reviewing changes
- Understanding implementation approach
- Breaking down work into tasks
- Estimating effort and resources

---

## 🔗 Document Relationships

### Principles → Specs

Each specification embodies the Core Principles:

| Principle | How it's Implemented |
|-----------|---------------------|
| Agent-First Semantics | `core-tracing/spec.md` - event model focuses on reasoning, not function calls |
| Framework Agnostic | `adapters/spec.md` - thin adapter layer, no framework deps in core |
| Non-Blocking | `core-tracing/spec.md` - queue + worker, never block agent thread |
| Safe by Default | `configuration/spec.md`, `data-processing/spec.md` - redaction, encryption by default |
| Local-First | `storage/spec.md` - SQLite, no cloud dependencies |
| Minimal Instrumentation | `adapters/spec.md` - automatic adapters, one-line enablement |
| Visual Clarity | `ui/spec.md` - timeline, decision flow, not raw logs |
| Performance-Aware | `data-processing/spec.md` - compression pipeline before storage |
| Progressive Complexity | All specs - phased implementation, simple first |
| Explainability | `api/spec.md`, `ui/spec.md` - insights over metrics |

### Specs → Changes

When creating a change proposal:
1. Read relevant specs to understand current state
2. Reference principles to ensure alignment
3. Create proposal describing what to change
4. Write design showing how to implement
5. Break down tasks showing what to do
6. Update specs with new requirements
7. Create spec deltas showing what changed

### Changes → Implementation

When implementing:
1. Follow tasks.md roadmap
2. Reference design.md for architecture
3. Consult specs for requirements
4. Ensure alignment with principles
5. Update documentation as code changes

---

## 📚 Quick Reference

### For Designers/Architects
- **Start with:** `principles/core.md`
- **Then read:** All specs to understand system
- **Reference:** `changes/example-add-streaming-support/design.md` for example

### For Developers
- **Start with:** `specs/README.md` for overview
- **Deep dive:** Read specs for components you work on
- **Study:** `changes/example-add-streaming-support/tasks.md` for task breakdown

### For Product Managers
- **Read:** `principles/core.md` to understand product philosophy
- **Review:** Proposals in `changes/` to understand upcoming work
- **Consult:** Specs to understand what can be built

### For QA/Testing
- **Reference:** Spec scenarios to create test cases
- **Use:** `tasks.md` acceptance criteria for validation
- **Check:** Principles to ensure test coverage aligns with values

### For DevOps/SRE
- **Study:** `storage/spec.md` for deployment requirements
- **Review:** `api/spec.md` for service endpoints
- **Check:** `data-processing/spec.md` for security considerations

---

## 🎯 Finding What You Need

### "I want to understand the project..."
- **Philosophy:** `principles/core.md`
- **System overview:** `specs/README.md`
- **Complete documentation:** `README.md`
- **Quick start:** `../OPENSPEC_GUIDE.md`

### "I want to propose a new feature..."
1. `principles/core.md` - Check alignment
2. `/openspec:proposal <feature>` - Generate proposal
3. Fill `proposal.md`, `design.md`, `tasks.md`
4. Update relevant specs
5. Example: `changes/example-add-streaming-support/`

### "I want to implement a component..."
- **Trace SDK:** `specs/core-tracing/spec.md`
- **Config:** `specs/configuration/spec.md`
- **Storage:** `specs/storage/spec.md`
- **API:** `specs/api/spec.md`
- **UI:** `specs/ui/spec.md`
- **Adapter:** `specs/adapters/spec.md`

### "I want to review a change..."
1. Read `proposal.md` - Understand the "why"
2. Review `design.md` - Validate the "how"
3. Check `tasks.md` - Ensure completeness
4. Examine `specs/*` - See requirements impact
5. Cross-check `principles/core.md` - Verify alignment

### "I want to write tests..."
- **Find scenarios:** Each spec has testable scenarios
- **Acceptance criteria:** `tasks.md` has criteria per task
- **Coverage:** Ensure all scenarios are tested
- **Example:** Review example proposal for test strategy

### "I want to deploy..."
- **Storage:** `specs/storage/spec.md` - DB schema and migrations
- **API:** `specs/api/spec.md` - Endpoints and health checks
- **Config:** `specs/configuration/spec.md` - Environment variables
- **Security:** `data-processing/spec.md` - Encryption requirements

### "I want to integrate a framework..."
- **Adapter interface:** `specs/adapters/spec.md`
- **Event model:** `specs/core-tracing/spec.md`
- **Example:** `changes/example-add-streaming-support/design.md` (LangChain section)

---

## 🔍 Navigation Tips

### By Role

| Role | Start Here | Then Read | Reference |
|------|-----------|-----------|-----------|
| **New Engineer** | `principles/core.md` | `specs/README.md` | All specs |
| **Architect** | `principles/core.md` | All specs | Example proposals |
| **Developer** | `specs/README.md` | Relevant specs | Tasks in changes |
| **Product Manager** | `principles/core.md` | Proposals | Specs overview |
| **QA Engineer** | Relevant specs | Scenarios | Tasks acceptance |
| **DevOps** | `storage/spec.md` | `api/spec.md` | All specs |
| **Contributor** | `principles/core.md` | Example proposal | All specs |

### By Topic

| Topic | Location |
|-------|----------|
| **Philosophy** | `principles/` |
| **Architecture** | `specs/` + `changes/*/design.md` |
| **Requirements** | `specs/*/spec.md` |
| **APIs** | `specs/api/spec.md` |
| **Data Model** | `specs/storage/spec.md`, `specs/data-processing/spec.md` |
| **UI Design** | `specs/ui/spec.md` |
| **Framework Integration** | `specs/adapters/spec.md` |
| **Examples** | `changes/example-add-streaming-support/` |
| **Workflow** | `changes/example-add-streaming-support/README.md` |

---

## ✅ Structure Quality Checklist

This OpenSpec structure is complete when:

- [x] **Principles defined** - Core philosophy documented
- [x] **All components specified** - Every system part has a spec
- [x] **Example proposal included** - Demonstrates workflow
- [x] **Documentation indexed** - Easy to find what you need
- [x] **Cross-references clear** - Documents reference each other
- [x] **Reading order defined** - Multiple paths for different users
- [x] **Quick reference available** - Fast lookup for common needs
- [x] **Format consistent** - All specs follow same structure
- [x] **Version control ready** - Clear organization for Git
- [x] **Maintainable** - Easy to add new specs and proposals

---

## 📊 Statistics

- **Total directories:** 3 (principles, specs, changes)
- **Specification files:** 7 (one per component)
- **Example proposal files:** 6 (proposal, design, tasks, spec delta, README)
- **Principle documents:** 2 (core, README)
- **Total markdown files:** 15
- **Estimated specification content:** ~3,500 lines
- **Example proposal content:** ~1,800 lines
- **Total documentation:** ~5,300+ lines

---

## 🚀 Getting Started

1. **Read this document** - Understand the structure
2. **Check out principles** - `principles/core.md`
3. **Explore specs** - Start with `specs/README.md`
4. **Study example** - `changes/example-add-streaming-support/`
5. **Start using** - Create your own proposal or implement from specs

---

## 💡 Key Takeaways

### Structure is Intentional

Every directory and file has a purpose:
- **Principles** = Why we build (philosophy)
- **Specs** = What we build (requirements)
- **Changes** = How we build it (implementation plans)

### Flow is Clear

Read order matters:
1. Principles (why) → Specs (what) → Changes (how)
2. Or: Principles → Example → Own proposal

### Navigation is Easy

Multiple paths for different users:
- By role
- By topic
- By task
- By goal

### Everything is Connected

- Principles guide specs
- Specs guide changes
- Changes produce implementations
- All reference each other

---

**Remember:** This structure is designed to help you understand, plan, and build the Agent Inspector effectively. Use it as your navigation map through the complete OpenSpec specification.

*For questions or contributions, refer to the main README or PR to the repository.*