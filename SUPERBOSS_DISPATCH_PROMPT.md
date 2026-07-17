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

- No task queue/scheduler daemon — tasks are created one at a time via the
  CLI, by a human or by Claude Desktop following this prompt.
- Model Router is deferred to a Claude-Code-CLI-via-proxy approach (route to
  other models through an OpenRouter-style proxy, keep Claude Code as the one
  agent harness) — not yet built. True multi-harness independence was
  explicitly not chosen.
- No per-worker resource limits (CPU/memory caps, concurrent-worker caps).
- Failed tasks resume from checkpoint on restart, but a task that exhausts
  its `StartLimitBurst` (3 restarts / 30 min) does not auto-resume further —
  needs a human/Claude-Desktop-triggered new task referencing the old
  checkpoint history.

## Short-form dispatch prompt

Same rules as above, compressed for repeated pasting. Use this when brevity
matters more than a first-time reader understanding the "why." Added
2026-07-18 at Owner's request for a technical, non-lengthy variant.

```
VERIDIAN-DEV DISPATCH [server-authoritative]

Target: Hetzner 167.233.220.35. Claude CLI on server = execution engine. This
machine is intake-only and may disconnect anytime -- never block execution on
its availability.

1. INTAKE (here, laptop): analyze task -> log entry in master CONTROLLER.yaml
   (C:\Users\Dell\Downloads\Claude Code\control\) -> `veridian-task.py create
   --repo <repo> --title <t> --prompt <task>` on server -> hand off. No local
   execution.
2. EXEC (server, systemd --user, linger on): isolated git worktree+branch per
   subtask. Workers never merge/push-main/deploy. quality-gate.sh must pass
   before pending_review.
3. AUDIT+MERGE (server, supervisor-entrypoint.sh, auto-fires on
   pending_review): real diff review via `claude -p`. risk-tier.py classifies
   tier1/tier2 deterministically. tier1+approve -> `gh pr merge` autonomous.
   tier2+approve -> hold, awaiting_human_approval. reject -> blocked +
   follow-up task.
4. SYNC: server ai-os/CONTROLLER.yaml -> master CONTROLLER.yaml pointer on
   terminal states only. Pull master first, every session.
5. NO DUPLICATION: check task state before assigning scope. Worktrees kill
   file-level collision; scope-level collision is the supervisor's job.

Full rules: /opt/veridian/repos/claude-control/SUPERBOSS_DISPATCH_PROMPT.md

TASK: <task>
```
