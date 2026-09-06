# FRIDAY Intelligence Roadmap

This roadmap is derived from FRIDAY's own repository examination and its improvement/AGI-capability recommendations.

## North Star

Move FRIDAY from a reactive developer assistant toward a general-purpose operating layer that can:

- understand complex goals
- plan multi-step work
- select and compose specialist agents
- inspect and modify code safely
- verify its own work
- learn reusable lessons from completed tasks
- notice uncertainty and investigate it with bounded curiosity
- maintain long-running task checkpoints
- adapt its tool/agent capabilities without becoming an uncontrolled self-modifier

This is an AGI-inspired architecture, not a claim that the system is AGI.

## Phase 1 — Cognitive + Workspace Foundation

### Implemented in this iteration

- Durable `experiences` memory table in SQLite.
- `cognition.learn` for reusable lessons, decisions, failures, patterns, and preferences.
- `cognition.recall` for retrieving relevant prior experiences.
- `cognition.curiosity` for bounded uncertainty-reduction questions.
- `cognition.checkpoint` for long-running project work.
- `Cognition Agent` specialist definition.
- Persisted conversation endpoint for the frontend history sidebar.
- Shadcn-inspired collapsible left conversation/GitHub sidebar.
- Collapsible right tool workspace reserved for future tools.
- Execution trace remains separate from private reasoning.

## Phase 2 — Developer Agent

Build a first-class coding loop around the existing filesystem, Git, and terminal tools:

1. inspect repository/workspace
2. understand the goal
3. create a task plan
4. implement one bounded change
5. run focused verification
6. inspect the diff
7. fix failures
8. repeat until the acceptance criteria are satisfied
9. store the useful lesson
10. checkpoint unfinished work

Mutating operations remain approval-gated.

## Phase 3 — Verification + QA

- dedicated QA agent execution
- test selection based on changed files
- lint/typecheck/build verification
- regression detection
- evidence-backed completion criteria
- no "done" response without verification evidence

## Phase 4 — Knowledge + Curiosity

- trusted external research tools
- documentation retrieval
- project knowledge graph
- concept abstraction
- cross-domain analogies
- uncertainty tracking
- bounded curiosity loops that stop when additional investigation has low value

## Phase 5 — Dynamic Agent System

- discover missing capabilities
- create specialist definitions from registered tools
- persist useful specialist definitions
- evaluate whether a dynamic agent should become a permanent built-in agent
- prevent dynamic agents from bypassing runtime permissions

## Phase 6 — Long-Running Autonomy

Introduce durable task state so FRIDAY can resume a partially completed project after interruption. A task should have a goal, acceptance criteria, plan, completed steps, remaining steps, evidence, failures, and checkpoint.

## Phase 7 — Production Hardening

FRIDAY's own analysis identified rate limiting, security headers, WebSocket origin protection, reconnection, CI/CD, environment validation, observability, Python lint/type checking, stronger tests, prompt-injection defenses, and scalable persistence as important gaps.

## Core Principle

FRIDAY should become more capable by composing **planning + specialist agents + tools + verification + memory + bounded curiosity**, not by giving one model unrestricted access to everything.
