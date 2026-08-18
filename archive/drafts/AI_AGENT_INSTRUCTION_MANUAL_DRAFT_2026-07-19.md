# AI AGENT Instruction Manual (Part 1 and Part 2) — DRAFT SPEC, NOT YET BUILT

> Captured verbatim from Owner instruction, 2026-07-19. This is a specification
> only — nothing described here has been implemented. Do not treat any JSON
> shape or routing assignment below as live/wired until a CONTROLLER.yaml
> entry says otherwise. Part of the AIROUTER-01 program (see
> `CONTROLLER.yaml`'s `AIROUTER-01` entry and
> `memory/veridian_ai_router_hierarchy_project_2026-07-18.md` Update 4/5) —
> this is the concrete task-contract layer underneath the Software Team
> L0-L5 hierarchy Update 4 already captured.
>
> **Constraint (reinforced 2026-07-19, applies to eventual build):** must run
> on VERIDIAN-DEV (167.233.220.35) using server resources only, through the
> Claude Code CLI subscription — never the Anthropic API. Routers must stay
> model-agnostic — no hardcoded model names in routing logic; the "Model"
> column below is the current default assignment, not a literal string to
> bake into code.

---

## Part 1 — Task Contract Pair (Instruction Contract + Execution Report)

Every AI worker should receive two JSON contracts per task, kept as reusable
templates in a task register (variables change per task; structure stays
fixed):

- **Instruction Contract (Input)** — sent by the Mother Router or a
  Supervisor to the worker.
- **Execution Report (Output)** — returned by the worker.

This applies to **every** AI worker regardless of model (GPT-OSS-20B,
GPT-OSS-120B, DeepSeek V4 Pro, GLM 5.2, Claude Code CLI, or any future
model). **GLM 5.2 and/or Claude Code CLI are the main implementers inside
the Mother Router** — i.e. the ones responsible for authoring/issuing these
JSON contracts to other workers, not just consuming them.

There must be a **task register** holding both contract shapes so they can
be reused, with only the variables changing per task.

### Owner-supplied examples (Instruction Contract shape, by step count)

The 4 examples below are illustrative, not actual live task data. They show
the Instruction Contract (Input) shape at increasing complexity. **The
Execution Report (Output) counterpart for each has NOT yet been drafted —
that is explicit future work**, not done as part of this capture pass.

**Single Step Task:**
```json
{
  "task_id": "TASK-001",
  "task_type": "Single Step",
  "objective": "Generate User Login API",
  "status": "PASS",
  "overall_confidence": 99,
  "completion": { "completed": 1, "expected": 1, "percentage": 100 },
  "steps": [
    { "step_no": 1, "name": "Generate API", "status": "PASS", "confidence": 99, "retry_count": 0, "validation": "PASS" }
  ],
  "missing": [],
  "warnings": [],
  "errors": [],
  "escalation": { "required": false, "reason": "" },
  "execution_summary": { "duration_seconds": 8, "tokens_used": 812, "files_created": 1 }
}
```

**Two Step Task:**
```json
{
  "task_id": "TASK-002",
  "task_type": "Two Step",
  "objective": "Generate API and Unit Tests",
  "status": "PASS",
  "overall_confidence": 98,
  "completion": { "completed": 2, "expected": 2, "percentage": 100 },
  "steps": [
    { "step_no": 1, "name": "Generate API", "status": "PASS", "confidence": 99, "retry_count": 0, "validation": "PASS" },
    { "step_no": 2, "name": "Generate Unit Tests", "status": "PASS", "confidence": 98, "retry_count": 0, "validation": "PASS" }
  ],
  "missing": [],
  "warnings": [],
  "errors": [],
  "escalation": { "required": false, "reason": "" },
  "execution_summary": { "duration_seconds": 16, "tokens_used": 1680, "files_created": 2 }
}
```

**Three Step Task:**
```json
{
  "task_id": "TASK-003",
  "task_type": "Three Step",
  "objective": "Generate API, Tests and Documentation",
  "status": "PASS",
  "overall_confidence": 97,
  "completion": { "completed": 3, "expected": 3, "percentage": 100 },
  "steps": [
    { "step_no": 1, "name": "Generate API", "status": "PASS", "confidence": 99, "retry_count": 0, "validation": "PASS" },
    { "step_no": 2, "name": "Generate Tests", "status": "PASS", "confidence": 98, "retry_count": 0, "validation": "PASS" },
    { "step_no": 3, "name": "Generate Documentation", "status": "PASS", "confidence": 96, "retry_count": 1, "validation": "PASS" }
  ],
  "missing": [],
  "warnings": ["Documentation regenerated after validation."],
  "errors": [],
  "escalation": { "required": false, "reason": "" },
  "execution_summary": { "duration_seconds": 31, "tokens_used": 2850, "files_created": 3 }
}
```

**Multi Step Task:**
```json
{
  "task_id": "TASK-004",
  "task_type": "Multi Step",
  "objective": "Implement Complete User Management Module",
  "status": "PASS",
  "overall_confidence": 97,
  "completion": { "completed": 8, "expected": 8, "percentage": 100 },
  "steps": [
    { "step_no": 1, "name": "Generate Database Schema", "status": "PASS", "confidence": 99, "retry_count": 0, "validation": "PASS" },
    { "step_no": 2, "name": "Generate Models", "status": "PASS", "confidence": 99, "retry_count": 0, "validation": "PASS" },
    { "step_no": 3, "name": "Generate APIs", "status": "PASS", "confidence": 98, "retry_count": 0, "validation": "PASS" },
    { "step_no": 4, "name": "Generate Frontend", "status": "PASS", "confidence": 97, "retry_count": 1, "validation": "PASS" },
    { "step_no": 5, "name": "Generate Unit Tests", "status": "PASS", "confidence": 98, "retry_count": 0, "validation": "PASS" },
    { "step_no": 6, "name": "Run Validation", "status": "PASS", "confidence": 98, "retry_count": 0, "validation": "PASS" },
    { "step_no": 7, "name": "Generate Documentation", "status": "PASS", "confidence": 97, "retry_count": 0, "validation": "PASS" },
    { "step_no": 8, "name": "Final Quality Check", "status": "PASS", "confidence": 97, "retry_count": 0, "validation": "PASS" }
  ],
  "missing": [],
  "warnings": ["Frontend required one retry before validation passed."],
  "errors": [],
  "escalation": { "required": false, "reason": "" },
  "execution_summary": { "duration_seconds": 124, "tokens_used": 11480, "files_created": 18, "files_modified": 9, "tests_passed": 42, "tests_failed": 0 }
}
```

**Open item (not resolved by this capture):** the 4 examples above are
labeled "Instruction Contract (Input)" by the Owner's own text, but their
shape (status/confidence/steps-already-executed/execution_summary) reads
like a completed *result*, not a pre-execution instruction. When this is
actually built, resolve this ambiguity with the Owner rather than guessing:
either (a) these are meant as the Execution Report (Output) shape and a
separate, genuinely pre-execution Instruction Contract shape needs to be
designed from scratch (objective/preconditions/inputs/process/constraints,
no status/confidence/results fields), or (b) the Owner intends one shared
schema reused for both directions with different fields populated. Do not
silently pick one interpretation during a future build.

---

## Part 2 — Capability-Based Routing (not parameter-count based)

Universal rule, apply to every instruction regardless of model:

> **All instructions shall be narrow, tightly structured, deterministic,
> with clearly defined Input, Preconditions, Process, Output, Validation,
> Success Criteria, Failure Criteria, Retry Policy, Escalation Rules,
> Documentation Requirements, Evidence Required, and Handover Requirements.
> The AI agent shall not make assumptions, shall not skip steps, shall not
> invent information, shall not silently fail, and shall immediately
> escalate if any mandatory input is missing or confidence is below the
> required threshold.**

### Universal Tightened Instruction Template (apply to every task)

- One objective only (or a predefined sequence of objectives).
- No assumptions under any circumstances.
- Clear Inputs (all mandatory inputs listed).
- Preconditions must be validated before execution.
- Fixed execution process; do not invent or reorder steps.
- Defined Outputs with required format.
- Evidence for every completed step (files, tests, logs, etc.).
- Validation against explicit acceptance criteria.
- Success only when 100% of expected outputs are complete.
- Failure if any required step is missing, invalid, or unverifiable.
- Retry only within the configured limit; do not retry indefinitely.
- Escalate immediately if required information is missing, confidence is
  below threshold, or authority is exceeded.
- No hallucinations: never fabricate code, files, results, APIs, test
  outcomes, or completion status.
- No silent skipping of instructions.
- Mandatory documentation for the assigned scope.
- Mandatory structured execution report before task completion.
- Mandatory handover package to the next agent or supervisor.

### Software Development Task Routing Matrix

Default model per task category. **Not hardcoded in router logic** — this
is the initial policy data to seed into a registry (e.g. Mother Router's
`ai_routing_policies`/`ai_model_registry`, see
[[veridian_ai_router_hierarchy_project_2026-07-18]] Update 3), swappable
without a code change.

| Task Category | Model |
|---|---|
| Read one file | GPT-OSS-20B |
| Explain one function | GPT-OSS-20B |
| Modify one function | GPT-OSS-20B |
| Write one function | GPT-OSS-20B |
| Fix one syntax error | GPT-OSS-20B |
| Fix one compiler error | GPT-OSS-20B |
| Fix one lint issue | GPT-OSS-20B |
| Rename one variable | GPT-OSS-20B |
| Rename one function | GPT-OSS-20B |
| Add comments to one file | GPT-OSS-20B |
| Generate one SQL query | GPT-OSS-20B |
| Generate one API endpoint | GPT-OSS-20B |
| Generate one REST Controller | GPT-OSS-20B |
| Generate one Service Class | GPT-OSS-20B |
| Generate one Repository Class | GPT-OSS-20B |
| Generate one Model | GPT-OSS-20B |
| Generate one DTO | GPT-OSS-20B |
| Generate one Schema | GPT-OSS-20B |
| Generate one Validation Class | GPT-OSS-20B |
| Generate one Unit Test | GPT-OSS-20B |
| Generate one Integration Test | GPT-OSS-20B |
| Generate Mock Data | GPT-OSS-20B |
| Convert JSON ↔ XML | GPT-OSS-20B |
| Convert CSV ↔ JSON | GPT-OSS-20B |
| Generate Documentation for one file | GPT-OSS-20B |
| Update README section | GPT-OSS-20B |
| Analyze Build Logs | GPT-OSS-20B |
| Validate JSON | GPT-OSS-20B |
| Validate YAML | GPT-OSS-20B |
| Validate Configuration File | GPT-OSS-20B |
| Monitor CI/CD Output | GPT-OSS-20B |
| Compare two files | GPT-OSS-20B |
| Generate Regex | GPT-OSS-20B |
| Generate Simple Bash Script | GPT-OSS-20B |
| Generate Simple Python Utility | GPT-OSS-20B |
| Generate Simple TypeScript Utility | GPT-OSS-20B |
| Multi-file Bug Fix | GPT-OSS-120B |
| Multi-file Feature Implementation | GPT-OSS-120B |
| Implement Approved Design | GPT-OSS-120B |
| CRUD Module Implementation | GPT-OSS-120B |
| Authentication Module Implementation | GPT-OSS-120B |
| Authorization Module Implementation | GPT-OSS-120B |
| API Layer Implementation | GPT-OSS-120B |
| Repository Layer Implementation | GPT-OSS-120B |
| Service Layer Implementation | GPT-OSS-120B |
| Business Logic Implementation | GPT-OSS-120B |
| Background Worker Implementation | GPT-OSS-120B |
| Queue Processing Implementation | GPT-OSS-120B |
| API Integration | GPT-OSS-120B |
| Payment Gateway Integration | GPT-OSS-120B |
| Email Service Integration | GPT-OSS-120B |
| SMS Integration | GPT-OSS-120B |
| Notification Module | GPT-OSS-120B |
| Refactor Approved Module | GPT-OSS-120B |
| Repository-wide Search & Replace | GPT-OSS-120B |
| Medium Complexity Debugging | GPT-OSS-120B |
| Test Failure Investigation | GPT-OSS-120B |
| Merge Approved Code | GPT-OSS-120B |
| Code Review against Checklist | GPT-OSS-120B |
| Dependency Upgrade | GPT-OSS-120B |
| Performance Profiling (Known Scope) | GPT-OSS-120B |
| Architecture Design | DeepSeek V4 Pro |
| Software Architecture Review | DeepSeek V4 Pro |
| Database Architecture | DeepSeek V4 Pro |
| Database Normalization | DeepSeek V4 Pro |
| API Architecture | DeepSeek V4 Pro |
| System Design | DeepSeek V4 Pro |
| Module Decomposition | DeepSeek V4 Pro |
| Repository Analysis | DeepSeek V4 Pro |
| Cross-module Refactoring Strategy | DeepSeek V4 Pro |
| Security Architecture Review | DeepSeek V4 Pro |
| Threat Analysis | DeepSeek V4 Pro |
| Performance Optimization Strategy | DeepSeek V4 Pro |
| Scalability Design | DeepSeek V4 Pro |
| Caching Strategy | DeepSeek V4 Pro |
| Event-driven Architecture | DeepSeek V4 Pro |
| Microservice Design | DeepSeek V4 Pro |
| Design Pattern Selection | DeepSeek V4 Pro |
| Technology Evaluation | DeepSeek V4 Pro |
| Root Cause Analysis | DeepSeek V4 Pro |
| Technical Specification Writing | DeepSeek V4 Pro |
| Repository Health Audit | DeepSeek V4 Pro |
| Engineering Risk Assessment | DeepSeek V4 Pro |
| Project Planning | GLM 5.2 / Claude Code CLI |
| Sprint Planning | GLM 5.2 / Claude Code CLI |
| Task Breakdown | GLM 5.2 / Claude Code CLI |
| Task Assignment | GLM 5.2 / Claude Code CLI |
| Multi-Agent Coordination | GLM 5.2 / Claude Code CLI |
| Repository Management | GLM 5.2 / Claude Code CLI |
| Branch Strategy | GLM 5.2 / Claude Code CLI |
| Merge Approval | GLM 5.2 / Claude Code CLI |
| Pull Request Review | GLM 5.2 / Claude Code CLI |
| Release Planning | GLM 5.2 / Claude Code CLI |
| Release Management | GLM 5.2 / Claude Code CLI |
| Engineering Governance | GLM 5.2 / Claude Code CLI |
| AI Router Management | GLM 5.2 / Claude Code CLI |
| Agent Governance | GLM 5.2 / Claude Code CLI |
| Worker Supervision | GLM 5.2 / Claude Code CLI |
| Conflict Resolution | GLM 5.2 / Claude Code CLI |
| Cross-team Coordination | GLM 5.2 / Claude Code CLI |
| Final Technical Approval | GLM 5.2 / Claude Code CLI |
| Production Deployment Approval | GLM 5.2 / Claude Code CLI |
| Executive Engineering Decisions | GLM 5.2 / Claude Code CLI |
| Mother Router Control | GLM 5.2 / Claude Code CLI |
| Complete Project Oversight | GLM 5.2 / Claude Code CLI |

---

## Status

**NOT STARTED.** Captured verbatim per Owner's "add this in the list, dont
do anything" instruction, 2026-07-19, immediately after an explicit
stop-all-work instruction earlier in the same session. No server SSH, no
code, no registry seeding done. Sits behind (or alongside) the Software
Team L0-L5 build already logged as top priority in
`memory/veridian_ai_router_hierarchy_project_2026-07-18.md` Update 4 — Part
1's task-contract pair and Part 2's routing matrix are the concrete
data/schema layer that build would consume.
