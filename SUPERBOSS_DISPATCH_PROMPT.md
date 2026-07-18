# VERIDIAN-DEV Superboss Dispatch — Standing Instructions

Authoritative version. Finalized 2026-07-18. Referenced from `CONTROLLER.yaml`
entry `SUPERBOSS-PROMPT-01`. This file is the actual source of truth — do not
restate its content elsewhere; update it in place and bump the date below.

## Reusable dispatch prompt

Paste this (with the TASK line filled in) to invoke the workflow:

```
STANDING PROMPT — VERIDIAN-DEV SUPERBOSS TASK DISPATCH
========================================================

EXECUTION LOCATION
- All actual work happens on the Hetzner server (VERIDIAN-DEV, 167.233.220.35). Never on this laptop.
- This laptop exists only for our conversation. It performs no build, no test, no heavy computation.
- Claude CLI running ON the server is the real execution engine, not Claude Desktop.

ROLE STRUCTURE — ONE SUPERBOSS, TWO SEATS
- "Superboss" is one role, split across two seats: Claude Desktop (this conversation — the intake/dispatch seat) and Claude CLI on the server (the execution/audit/merge seat). Same standing instructions, same authority, neither seat is senior to the other.
- Sub-agents/workers never report to Claude Desktop directly. They report only to the server-side Superboss seat.

INTAKE (Claude Desktop's job — happens here, in this chat)
1. Read and analyze the task below: scope, acceptance criteria, affected repo(s), risk, dependencies.
2. Record it as a new entry in the master CONTROLLER.yaml (C:\Users\Dell\Downloads\Claude Code\control\CONTROLLER.yaml), following its existing intake convention. Pull before read, push after write.
3. Create the corresponding task on the server via `veridian-task.py create`, referencing the master entry's id.
4. Hand off. Do not attempt to execute the task from the laptop side beyond this dispatch step.

EXECUTION (server-side Superboss's job)
5. Break the task into small, independently-completable subtasks.
6. Each subtask runs as its own isolated worker — own git worktree, own branch, per /opt/veridian/README-SERVER.md's AI-OS section.
7. Workers never merge, never push to main, never deploy. They complete their scope, run their own quality gates, and checkpoint status.

NO DUPLICATION / NO COLLISION
8. Before assigning any subtask, the server-side Superboss checks existing task state (server ai-os/CONTROLLER.yaml + master CONTROLLER.yaml) to confirm no other worker — this task or any other — already owns that scope.
9. Isolated worktrees make simultaneous file edits structurally impossible across subtasks; the Superboss's real job is preventing overlapping scope from being assigned in the first place.

AUDIT + MERGE (server-side Superboss's job — see Tiered Trust Model below)
10. Quality gates (lint/build/test) must already be passing before a worker reports done.
11. The server-side Superboss reviews the actual diff — architecture, correctness, security — not a self-report.
12. tier1 + approved: merge to the target repo's main branch autonomously, push to GitHub, let Vercel auto-deploy, apply any needed Supabase migration.
13. tier2 + approved: hold for human sign-off, do not merge. Rejected (either tier): leave the PR open with review comments, create a targeted follow-up subtask. Never a full restart.

SYNC
14. Server ai-os/CONTROLLER.yaml pushes a summary pointer to the master CONTROLLER.yaml whenever a task reaches a terminal state (completed/blocked/failed/awaiting_human_approval) — not on every intermediate checkpoint.
15. Any session touching this task pulls the master CONTROLLER.yaml first, before doing anything else, to report real status without re-deriving it.

RECORD-KEEPING
16. Every subtask's outcome, files touched, decisions made, and audit result must be traceable from the master CONTROLLER.yaml's `where` pointer down to the real task.yaml / PR. No undocumented work.

========================================================
TASK: <describe the work here>
========================================================
```

## Tiered trust model (governs steps 10-13 above)

Added 2026-07-18 after Owner explicitly chose a staged-trust approach over
immediate full autonomy. Classification is **deterministic**, computed by
`/opt/veridian/scripts/risk-tier.py` from the actual diff — the AI reviewer
records a verdict (approve/reject) but cannot override which tier applies.

- **tier1** — additive, low-blast-radius changes: new files, isolated
  features, docs, tests, non-breaking UI work. Superboss reviews and, if
  approved, **merges autonomously**.
- **tier2** — diff touches any of: `migrations?/`, `schema.(sql|prisma)`,
  `*.sql`, `auth/`, anything matching `permission`/`payment`/`billing`/`rls`/
  `security` in its path, `.env` files, or a heavy-deletion diff
  (>20 lines deleted and >2x the lines added). Superboss still reviews and
  records a verdict, but **holds for human sign-off** — approval only means
  "ready for a human to merge," never permission to merge it itself.

Mechanics: `supervisor-entrypoint.sh` triggers automatically the moment a
worker's task reaches `pending_review` (via
`systemctl --user start veridian-supervisor@<task-id>.service`), plus a
15-minute cron sweep (`supervisor-sweep.sh`) catches any missed triggers
(crash, systemd hiccup). It always opens a real GitHub PR for auditability
regardless of verdict; `gh pr merge` only fires on tier1+approve.

**Live-verified 2026-07-18**, not just implemented: a real tier1 task was
spawned, reviewed, approved, and merged autonomously end to end (PR #3 on
`claude-control`, real merge commit `1ddac25`, confirmed via `gh pr view`
showing `state: MERGED`) before the test artifact was cleanly reverted.
tier2-hold and reject paths were not separately live-fired yet.

## Known gaps (do not claim these are solved)

- No per-worker resource limits (CPU/memory caps, concurrent-worker caps).
- Failed tasks resume from checkpoint on restart, but a task that exhausts
  its `StartLimitBurst` (3 restarts / 30 min) does not auto-resume further —
  needs a human/Claude-Desktop-triggered new task referencing the old
  checkpoint history.
- The GLM-5.2-via-proxy execution engine (see below) is validated on 3
  synthetic capability tests (text reply, tool-use file read, tool-use file
  edit) plus a small number of real gap-queue tasks — not yet proven at full
  sustained multi-week load. Watch its early real-task outcomes for quality
  drift versus the previous Claude-Code-native baseline; this is a genuinely
  new execution substrate, not a like-for-like swap that can be assumed safe
  by default.
- The Master + 5 Supervisor role/file-ownership layer (below) is a policy
  and reporting overlay on the existing tier1/tier2 supervisor-entrypoint.sh
  pipeline, not a separate second execution engine. `module-queue-dispatcher.py`
  and the per-module `ai-os/queues/*.yaml` files from the initial pilot
  (`master-decompose.py`) exist but are NOT the primary path for the 1713-item
  gap-queue backlog — that stays on `queue-dispatcher.py`/`gap_queue.yaml`,
  now labeled by module for reporting. Do not fork the same backlog across
  both mechanisms; that would double-dispatch the same findings.

## Execution engine: GLM-5.2 via local Anthropic-protocol proxy (2026-07-18)

Owner directive 2026-07-18: Claude subscription usage limits were observed
actively blocking real work (38 of 296 gap-queue groups failed with
`"You've hit your session limit"` mid-session — confirmed via task result.json,
not assumed). Full swap: **Claude Code CLI is still the execution harness**
(same tool-use loop — file edit, bash, git — same worktree/quality-gate/PR
flow) but now runs against **GLM-5.2 via OpenRouter** instead of Anthropic's
own models, through a small local translation proxy since OpenRouter speaks
the OpenAI chat-completions protocol, not Anthropic's Messages protocol
(confirmed by direct testing — pointing `ANTHROPIC_BASE_URL` straight at
OpenRouter 404s).

- Proxy: `/opt/veridian/scripts/anthropic_openrouter_proxy.py`, stdlib-only
  Python (no third-party deps — deliberate, since this sits in the path of
  every code change the framework writes), running as systemd user service
  `veridian-glm-proxy.service` on `127.0.0.1:8787`, `Restart=on-failure`.
- Config: `ANTHROPIC_BASE_URL=http://127.0.0.1:8787`,
  `ANTHROPIC_AUTH_TOKEN=dummy-proxy-token` (placeholder — the proxy itself
  holds and uses the real `OPENROUTER_API_KEY`), `ANTHROPIC_MODEL=z-ai/glm-5.2`,
  all in `/opt/veridian/shared/.env`, auto-loaded by every worker and
  supervisor systemd unit via their existing `EnvironmentFile=`.
- **Live-verified before trusting it**, not just deployed: (1) plain text
  reply — correct. (2) tool-use file read — correct content reported,
  `num_turns:2` confirming a real tool_use/tool_result round trip. (3) tool-use
  file **edit** — read the actual file after the run, confirmed the exact
  intended line changed and nothing else did, `num_turns:3`. All three via
  real `claude -p ... --dangerously-skip-permissions` calls against the
  running proxy.
- Cost note: Claude Code's own displayed `total_cost_usd` in these tests is
  calibrated for Anthropic models and is **not** the real bill for a
  non-Anthropic model routed through this proxy — treat it as noise, not a
  budget signal, until real OpenRouter billing is checked directly.
- `ANTHROPIC_API_KEY_DISABLED_PER_OWNER_2026-07-18` stays disabled — this
  change does not reintroduce Anthropic-API metered billing, it replaces it
  with OpenRouter/GLM-5.2 metered billing, which the Owner explicitly chose
  in place of the Claude subscription's usage ceiling.

## Role structure: Superboss (Master) + 5 module Supervisors (2026-07-18)

Owner directive: standardize every agent on one flow, with GLM-5.2 as the
model for all of it (Master, Supervisors, workers). This is layered onto the
**existing, already-working** tier1/tier2 pipeline above, not a replacement:

- **Superboss = Master.** Same seat as described at the top of this file
  (server-side Claude CLI, now GLM-5.2-backed). Owns architecture-level
  judgment: which gap-queue group goes to which Supervisor, tier1/tier2
  classification via `risk-tier.py`, final review, merge authority.
- **5 Supervisors, by module, mapped from each gap-queue item's category:**
  - **Frontend** — UI/components/pages/forms (`src/app/**/page.tsx`,
    `src/components/**`).
  - **Backend** — APIs/services/business logic (`src/app/api/**`,
    `src/lib/**-service.ts`, orchestration).
  - **Database** — schema/SQL/migrations (`src/lib/db/schema.ts`,
    `drizzle/**`).
  - **QA/Testing** — tests, security, performance, docs (`*.test.ts`,
    `docs/**`, CI test config).
  - **DevOps/Integration** — CI/CD, deployment, monitoring
    (`.github/workflows/**` — **but see the hard rule below**).
  - A gap-queue item spanning multiple modules is fine to close as one PR
    (current `queue-dispatcher.py` behavior) — the module label is for
    routing/reporting clarity, not a hard split requirement on every finding.
- **Standard task shape** (apply to new task prompts going forward — not a
  retrofit of already-dispatched tasks): TASK ID, MODULE, OBJECTIVE, FILES
  ALLOWED, FILES FORBIDDEN, DEPENDENCIES, INPUT, OUTPUT, STEPS, CONSTRAINTS,
  VALIDATION, DONE CRITERIA. `queue-dispatcher.py`'s `build_prompt()` already
  carries most of this (objective, findings, constraints); it doesn't yet
  emit explicit FILES ALLOWED/FORBIDDEN per item — a real gap if file-ownership
  enforcement is wanted at the per-task level rather than only at PR-review
  time.
- **Hard rule: never modify `.github/workflows/**` directly in a worker
  task.** Confirmed real failure: the GitHub token lacks the `workflow`
  OAuth scope, so any push touching a workflow file is rejected by GitHub
  itself (`refusing to allow an OAuth App to create or update workflow ...
  without workflow scope`) — real work gets done, then silently lost at the
  push step. If a finding's only real fix requires a workflow-file change,
  the worker should implement everything else and flag the workflow-file
  part in PROGRESS.md as needing manual application (by the Owner or a
  future PAT-scope change) rather than attempting and losing the push.

## GitHub / Vercel / Supabase — how Superboss implements and audits

- **GitHub**: every subtask ships as its own worktree branch + real PR (`gh
  pr create`), regardless of tier — this is the audit trail. tier1+approve
  merges via `gh pr merge --merge --delete-branch`; tier2 or reject holds
  the PR open with a structured `AUDIT:` comment (8 required fields per
  `mandatory-audit-check.yml` — concise, specific values only, no "n/a").
  Workflow-file changes are out of scope per the hard rule above.
- **Vercel**: no new action needed — the repo's existing GitHub integration
  auto-deploys a preview on every PR and promotes on merge to main. Superboss
  doesn't need to touch Vercel directly; it should note in its review if a
  change plausibly affects build/deploy (new env var needed, new route,
  etc.) so that's visible before merge, not after a broken deploy.
- **Supabase**: schema changes go through this repo's existing Drizzle
  migration convention (`drizzle/*.sql` + `schema.ts`, additive migrations
  only, checked for numbering collisions before adding) — tier2 by
  definition (matches the `migrations?/|schema\.(sql|prisma)|\*\.sql` path
  pattern), always held for human sign-off, never auto-merged.

## Retry policy for stuck gap-queue items (2026-07-18)

`queue-dispatcher.py` now auto-retries `needs_retry` items (up to
`MAX_RETRIES = 3`) instead of leaving them permanently stuck — this closed a
real gap found live: 38 of 296 groups were stuck in `needs_retry` with no
path back to dispatch, because the dispatcher only ever pulled from
`status == "queued"`. After `MAX_RETRIES` failed attempts, an item moves to
`stuck_needs_human` (surfaced by `gap-status.py`) instead of retrying
forever. Also fixed: `worker-entrypoint.sh`'s first `claude -p` call used to
**overwrite** `worker.log`/`result.json` on every restart (`>` instead of
`>>`), destroying the evidence needed to diagnose why a task failed — now
appends, so a task's full retry history survives for real debugging.

## Reporting (reaffirm explicitly — do not assume this carries over)

Per Owner's standing instruction: **do not narrate progress.** Report only
`X of Y groups completed (Z%)` from `gap-status.py`, plus any item that
genuinely needs the Owner's own decision (a `stuck_needs_human` item, a
tier2 hold, a scope ambiguity). This applies to the GLM-5.2-backed Superboss
exactly as it applied to the Claude-native one — state it plainly to any
fresh Superboss/Supervisor session reading this file, since a different
underlying model has no memory of this having been said before.

## Short-form dispatch prompt (v2)

Same rules as the full version above, compressed for repeated pasting. Use
this when brevity matters more than a first-time reader understanding the
"why." v1 added 2026-07-18 at Owner's request for a technical, non-lengthy
variant; **v2 same day** folds in real lessons from that day's actual
operation: the API-billing-vs-plan-token distinction (Owner corrected a real
misunderstanding — see the memory file
`feedback_veridian_superboss_dispatch_prompt.md` for the full exchange), the
corrected execution-model framing (parallel worker sessions, not "one
session displayed here"), the `CONTROLLER.yaml`/`task.yaml` concurrent-write
corruption bug found and fixed (file locking added, safe for concurrent
workers now), the `mandatory-audit-check.yml`-style strict field-validation
gotcha (concise+specific fields only, "n/a" gets rejected), and the
duplicate/stub-work lesson from the Track1b branches that turned out to be
claim-only with zero real code.

```
VERIDIAN-DEV DISPATCH [server-authoritative, plan-billed]

Target: Hetzner 167.233.220.35. Claude CLI on server = execution engine,
authenticated via CLAUDE_CODE_OAUTH_TOKEN (Claude subscription plan) in
/opt/veridian/shared/.env -- NEVER the Anthropic API key (disabled on
purpose, cost-sensitive project, do not re-enable without fresh
confirmation). This machine is intake-only and may disconnect anytime --
never block execution on its availability. Not "one session displayed
here" -- multiple independent worker sessions run on the server in
parallel; this chat just dispatches and reads results.

1. INTAKE (here, laptop): analyze task -> log entry in master CONTROLLER.yaml
   (C:\Users\Dell\Downloads\Claude Code\control\) -> check for existing
   open PRs/branches on the same scope first (gh pr list, git
   for-each-ref) to avoid re-dispatching duplicate or already-attempted
   work -> `veridian-task.py create --repo <repo> --title <t> --prompt
   <task>` on server -> hand off. No local execution.

2. EXEC (server, systemd --user, linger on, file-locked task/controller
   state -- safe for concurrent workers): isolated git worktree+branch per
   subtask. Workers never merge/push-main/deploy. quality-gate.sh must
   pass before pending_review. Capacity: 2-3 concurrent workers verified
   safe on this server's real headroom; check `free -h`/`uptime` before
   going higher.

3. AUDIT+MERGE (server, supervisor-entrypoint.sh, auto-fires on
   pending_review): real diff review via `claude -p`. risk-tier.py
   classifies tier1/tier2 deterministically. tier1+approve -> `gh pr merge`
   autonomous. tier2+approve -> hold, awaiting_human_approval (human
   sign-off happens here, in this chat, on reconnect). reject -> blocked +
   follow-up task. If this repo requires a structured "AUDIT:" comment
   (mandatory-audit-check.yml-style), keep every field concise and
   specific -- no "n/a", no long sentences in Severity Classified -- or
   the check itself will reject the comment. Workflow files only
   re-trigger on push, not new comments -- an empty commit is needed
   after posting a corrected audit comment.

4. SYNC: server ai-os/CONTROLLER.yaml -> master CONTROLLER.yaml pointer on
   terminal states only (automated via sync-controller-back.py, 30-min
   cron). Pull master first, every session.

5. NO DUPLICATION: before trusting any "claim" or in-progress marker as
   done, verify real code exists (diff/file changes), not just a
   claim-registration commit. Check task state before assigning scope.
   Worktrees kill file-level collision; scope-level collision is the
   supervisor's job.

Full rules: /opt/veridian/repos/claude-control/SUPERBOSS_DISPATCH_PROMPT.md

TASK: <task>
```

## Sync rule #14 — now automated, not just described

Added 2026-07-18: `sync-controller-back.py` on the server runs every 30 min
via cron, implementing rule #14 for real. No manual transcription needed
going forward for routine task completions. See
`/opt/veridian/README-SERVER.md`'s "Controller sync-back routine" section for
mechanics. Manual entries (like this file's own SUPERBOSS-PROMPT-01) are
still appropriate for governance/architecture changes — the automated
routine only covers individual worker-task terminal states.

## CRITICAL FIX 2026-07-18 — execution backend was broken (OpenRouter 402), now fixed

Every server worker task dispatched today was silently routed through
`ANTHROPIC_BASE_URL=http://127.0.0.1:8787` (veridian-glm-proxy.service,
translating Anthropic-shaped calls to OpenRouter/GLM-5.2), NOT through
`CLAUDE_CODE_OAUTH_TOKEN` (the real Claude subscription plan) as this
document's own header always specified. That OpenRouter account ran out of
credits — every single worker task this session failed with a 402 error
(`result.json`: "This request requires more credits"), which is the real
root cause behind the large run of WORKER-\* `status: failed` entries synced
into CONTROLLER.yaml and the ~20 stuck-CI PRs (#412-433) on compliance-tracker.

**Fixed 2026-07-18**: commented out `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`/
`ANTHROPIC_MODEL` in `/opt/veridian/shared/.env` (backup:
`.env.backup-2026-07-18-glm-proxy-disable`), stopped+disabled
`veridian-glm-proxy.service`. `claude` CLI now falls through to
`CLAUDE_CODE_OAUTH_TOKEN` directly — verified live (a test call billed
against `claude-sonnet-5`, zero OpenRouter involvement, zero 402).

**Standing rule going forward**: do not re-enable `ANTHROPIC_BASE_URL`/the
GLM proxy without a fresh Owner confirmation. Claude Code CLI via the
subscription plan is the sole execution engine for every worker/supervisor/
superboss role on this server — no other AI model, per Owner directive
2026-07-18. If a future session finds `ANTHROPIC_BASE_URL` set again in
`/opt/veridian/shared/.env`, that is a regression of this exact fix, not an
intentional config — investigate before trusting it.
