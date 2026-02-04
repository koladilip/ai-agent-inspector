# Example: Add Streaming LLM Response Support

This directory contains a complete example of an OpenSpec change proposal. It demonstrates how to use OpenSpec to plan and review feature changes before writing any code.

## 📋 What This Proposal Covers

This example proposes adding support for capturing and displaying streaming LLM responses in the Agent Inspector. It includes:

- **Individual token capture** - Track each token as it's generated
- **Streaming visualization** - Show token generation timeline in the UI
- **Token replay** - Animate token arrival to debug timing issues
- **Performance metrics** - Track first-token latency and token generation rate

## 📁 Files in This Proposal

### 1. `proposal.md` - The Change Overview
**Purpose:** Describe what we want to change and why.

**Contents:**
- **Motivation** - Current state, problems, and impact
- **Proposed Solution** - High-level approach and data models
- **Benefits** - Value the change provides
- **Affected Components** - Which specs will need updates
- **Migration Path** - Phased implementation plan
- **Risks and Mitigations** - Potential issues and how to address them
- **Success Criteria** - How we know the change is complete

**Why This Matters:** Before writing code, everyone understands what we're building and why.

---

### 2. `design.md` - Technical Architecture
**Purpose:** Define exactly how the feature will be implemented.

**Contents:**
- **Architecture Overview** - System diagram and key decisions
- **Data Model** - Database schema and in-memory structures
- **Core Tracing Changes** - New APIs and event models
- **Storage Layer** - Database queries and indexing
- **API Design** - New FastAPI endpoints with request/response examples
- **UI Implementation** - Component designs and visual mockups
- **Adapter Integration** - Framework-specific integration details
- **Performance Optimization** - Strategies for efficiency
- **Security Considerations** - How we handle sensitive tokens
- **Testing Strategy** - Unit, integration, and performance tests
- **Rollout Plan** - Phased deployment and monitoring

**Why This Matters:** Engineers can review the design and identify issues before coding begins.

---

### 3. `tasks.md` - Implementation Roadmap
**Purpose:** Break down the work into actionable tasks with estimates.

**Contents:**
- **25 specific tasks** organized by phase
- **Time estimates** for each task (106 hours total ≈ 3 weeks)
- **Priority levels** (P0, P1, P2, P3) for sequencing
- **Dependencies** showing task relationships
- **Acceptance criteria** for each task
- **Risk mitigation** for high-risk items
- **Owner assignments** for engineering team

**Example Task Breakdown:**
```
Phase 1 (Week 1): Backend Foundation
- TASK-001: Database Schema Changes (2 hours)
- TASK-002: Streaming Context API (4 hours)
- TASK-003: Token Buffer Implementation (3 hours)
- TASK-004: Database Token Operations (4 hours)
- ...

Phase 2 (Week 2): UI Implementation
- TASK-009: Timeline Streaming Visualization (6 hours)
- TASK-010: Detail Panel Timeline (5 hours)
- TASK-011: Token Replay Animation (8 hours)
- ...

Phase 3 (Week 3): Optimization & Polish
- TASK-016: Token Aggregation Job (4 hours)
- TASK-020: User Guide Documentation (4 hours)
- ...
```

**Why This Matters:** Clear roadmap lets the team estimate resources, track progress, and deliver on time.

---

### 4. `specs/core-tracing/spec.md` - Spec Delta
**Purpose:** Show how existing specifications will change.

**Contents:**
- New requirements added to core-tracing spec
- Scenarios defining expected behavior
- Integration points with existing specs

**Why This Matters:** Spec deltas make it easy to review what requirements are changing without reading the entire spec.

---

## 🚀 OpenSpec Workflow

This example demonstrates the complete OpenSpec development workflow:

### Step 1: Generate a Proposal
```
User: /openspec:proposal Add streaming LLM support

Agent: 
- Searches existing specs for related requirements
- Reads relevant codebase files
- Generates proposal.md with all sections filled
- Creates the change directory structure
```

### Step 2: Review and Refine
```
Team reviews proposal.md:
- Is the motivation clear?
- Are the benefits compelling?
- Is the solution feasible?
- Are risks addressed?

→ Iterate until approved
```

### Step 3: Detailed Design
```
Engineer creates design.md:
- Architecture diagrams
- Data models and schemas
- API contracts
- UI mockups
- Security and performance considerations
```

### Step 4: Break Down Tasks
```
Team creates tasks.md:
- Identify all work needed
- Estimate effort
- Set priorities
- Define dependencies
- Assign owners
```

### Step 5: Update Specs
```
Spec deltas are created in specs/:
- core-tracing/spec.md - New streaming requirements
- api/spec.md - New endpoint requirements
- ui/spec.md - New UI requirements
- storage/spec.md - New schema requirements
```

### Step 6: Implement
```
Engineers follow tasks.md:
- Pick P0 tasks first
- Implement with clear acceptance criteria
- Update tasks as they complete
- Track progress against estimates
```

### Step 7: Review
```
Review is easy because:
- Proposal shows the "why"
- Design shows the "how"
- Tasks show the "what"
- Spec deltas show the requirements change

→ No digging through code to understand the change
```

---

## 📊 Value of This Approach

### Before OpenSpec
```
1. Developer has an idea
2. Starts writing code immediately
3. PR is submitted
4. Reviewers ask: "Why did you do this?"
5. Developer explains the intent
6. Reviewers find issues with the approach
7. Developer rewrites code
8. Repeat until accepted

Result: 3 weeks, 2 rewrites, frustrated team
```

### With OpenSpec
```
1. Developer has an idea
2. /openspec:proposal generates the full proposal
3. Team reviews proposal (1 hour meeting)
4. Design document is written (collaborative)
5. Tasks are broken down (team estimates)
6. Everyone understands the change
7. Implementation starts (clear direction)
8. Code review is about quality, not understanding

Result: 3 weeks, 0 rewrites, aligned team
```

### Key Benefits

✅ **Better Understanding** - Everyone knows the "why" before code is written

✅ **Early Issue Detection** - Design flaws found before implementation

✅ **Accurate Estimates** - Tasks broken down with team input

✅ **Faster Reviews** - Reviewers understand the change from spec deltas

✅ **Documentation First** - Spec becomes living documentation

✅ **Alignment** - Team agrees on approach before coding

---

## 💡 How to Use This Example

### For New Features

1. **Start with /openspec:proposal**
   - Describe the feature you want to add
   - Let OpenSpec generate the initial proposal

2. **Fill in the Details**
   - Complete proposal.md sections
   - Create design.md with architecture
   - Break down tasks.md with estimates

3. **Get Review**
   - Share proposal for feedback
   - Refine design based on input
   - Get team buy-in on tasks

4. **Implement**
   - Follow tasks.md roadmap
   - Mark tasks as complete
   - Track progress against estimates

### For Bug Fixes

Use a lighter approach:
- proposal.md: Describe the bug and root cause
- design.md: Explain the fix approach
- tasks.md: Break down fix into steps
- specs/: Update if behavior changes

### For Refactoring

- proposal.md: Why refactoring is needed
- design.md: New architecture approach
- tasks.md: Step-by-step migration plan
- specs/: Update if requirements change

---

## 🔍 Reviewing This Example

### What to Look For in `proposal.md`

- Is the problem clearly stated?
- Is the solution well-motivated?
- Are all affected components identified?
- Is the migration path realistic?
- Are risks acknowledged and mitigated?

### What to Look For in `design.md`

- Is the architecture sound?
- Are data models complete?
- Are API contracts clear?
- Are security concerns addressed?
- Is performance considered?

### What to Look For in `tasks.md`

- Are tasks granular enough?
- Are estimates realistic?
- Are dependencies clear?
- Are priorities appropriate?
- Are acceptance criteria specific?

### What to Look For in Spec Deltas

- Do new requirements align with proposal?
- Are scenarios testable?
- Is language consistent with existing specs?
- Are conflicts with other specs avoided?

---

## 🎯 Key Takeaways

1. **Specs are Living Documents** - They evolve with the codebase
2. **Changes Start with Proposals** - Review intent, not just code
3. **Design Before Code** - Architecture decisions get scrutiny
4. **Tasks Guide Implementation** - Clear roadmap, measurable progress
5. **Spec Deltas Show Impact** - Easy to see what's changing

---

## 📚 Additional Resources

- [OpenSpec Documentation](https://openspec.dev)
- [Main Project README](../../README.md)
- [All Specifications](../specs/)

---

## 🛠️ Creating Your Own Proposal

To create a new change proposal:

```bash
# In your chat with an AI agent that supports OpenSpec:
/openspec:proposal Your feature description here

# This will:
# 1. Search existing specs
# 2. Read relevant code
# 3. Generate proposal.md
# 4. Suggest design structure
# 5. Identify affected components
```

Then:
1. Fill in the proposal details
2. Create the design document
3. Break down tasks with the team
4. Update spec deltas
5. Get approval before coding

---

**Remember:** The time spent planning is repaid many times over in faster implementation, fewer rewrites, and better alignment.

---

*This example is part of the Agent Inspector project's OpenSpec documentation. It demonstrates how spec-driven development leads to better software with less friction.*