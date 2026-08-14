# AGENTS.md — Authorized AI Agents (claude-control)

> Owner: Rajat Agarwal (raajat.agarwal@gmail.com)

This document is the claude-control-specific counterpart to `FChecklist/compliance-tracker`'s
`AGENTS.md`. Written from scratch for this repository — claude-control's own history and
infrastructure are different from `compliance-tracker`'s, and this file says so honestly
rather than asserting a governance setup that doesn't exist here yet.

## What this repo actually is

claude-control is the cross-project requirements & decision catalog and orchestration control
repo for VERIDIAN's AI OS — see `README.md` and `CONTROLLER.yaml`. It holds `ai-os/` (the
constitution, memory, capability/wiring registries, dispatch tooling under `ai-os-scripts/`),
`scripts/` (including `superboss-register.py`, a duplicate of the canonical copy in
`veridian-scripts` — see that repo's own note on this), progress logs, RCAs, and audit
reports for work dispatched across this and other VERIDIAN repos.

## Evidence of how this repo has been built so far

**[FACT, verified via `git log` and `gh api`]** — `master` is the default branch. It currently
has **no GitHub branch-protection rule configured** (`gh api
repos/FChecklist/claude-control/branches/master/protection` returns 404 "Branch not
protected" as of 2026-08-14). The one real CI job present is `.github/workflows/claude.yml`
(`@claude`-mention-triggered `claude-code-action`, not a `repository_dispatch`
`zai-task`/`claude-task` pair the way `compliance-tracker`/`veda-advisors` have). Work in
this repo follows the observed pattern in `git log`: a worker branch per task
(`worker/task-<id>`), a PR against `master`, and a "Merge pull request" commit — treat this
as the required review surface even though nothing technical currently blocks a direct push.

**[NOT APPLICABLE YET]** — a named, per-repo "Authorized Agents" roster (the kind
`compliance-tracker/AGENTS.md` has, with named triggers, API keys, and permissions) does not
exist for claude-control, because this repo has no `repository_dispatch`-triggered dispatch
mechanism to authorize agents *into*. This document establishes the governance discipline
below so that whenever such infrastructure is added here, it has rules to build under from
day one — not so it can claim the roster already exists.

## Operating Rules

1. **Owner sign-off required to weaken any rule below.** Any change that removes, disables,
   or routes around a rule in this file requires Rajat Agarwal's explicit written
   instruction, quoted in the PR description — the same anti-bypass principle as
   `compliance-tracker/AGENTS.md` Operating Rule 9. Extending or tightening a rule never
   requires this.

2. **PR-against-`master` is the required review surface.** Work on a branch, open a PR
   against `master`. No CI currently gates the merge (see "Evidence" above), so this is a
   human/agent discipline norm, not a technical lock — stated honestly rather than glossed
   over.

3. **No fabricated governance.** Do not add "Authorized Agents" entries, CI job names, or
   enforcement claims to this file that don't correspond to something real in this
   repository. If a rule is aspirational, mark it `[POLICY ONLY]` or `[NOT APPLICABLE YET]`.

4. **Do not commit secrets.** Real secrets (API keys, tokens) must never be committed.

5. **Search-Reuse Discipline — Added 2026-08-14 (Owner-approved, addendum to P1
   UMR-20260806-171945-5767; citation: `OWNER_DECISIONS_NEEDED_2026-07-23.yaml` entry
   `id=crontab-drift-approved-2026-08-14`, `status=approved`).** Real indexes already exist
   and are already used by the deterministic dedup reviewer for dispatch-level decisions —
   `system_index`, `capability_registry`, `wiring_registry` (all three:
   `ai-os/memory/superboss-register.sqlite`), `CLAUDE_MEMORY_INDEX.md`, `dead_ends.json`,
   `open_questions.json` (all three: `ai-os/memory/`). A cross-repo audit on 2026-08-14
   found zero instances of any "check the index first" instruction in any real `AGENTS.md`,
   so different worker tasks were repeatedly re-discovering the same real facts via fresh
   exploratory search, wasting real tokens. Every worker must: (a) before broad exploratory
   search, check whether the fact needed is already answered by one of the six indexes
   above (also see `ai-os/MASTER_INDEX.yaml`, this repo's own "canonical file routes +
   search guidance" file, which points into the same indexes), and cite what was checked in
   the PR description or progress log, even if the check came up empty; (b) only do fresh
   search for what those indexes don't already answer — this is not a reason to skip real
   verification of current state, only a reason not to duplicate a search someone already
   did; (c) if a fresh search turns up a genuinely new fact worth reuse, write it back to
   the appropriate index (`capability_registry`/`wiring_registry` via
   `scripts/superboss-register.py`, `CLAUDE_MEMORY_INDEX.md`, `dead_ends.json`,
   `open_questions.json`) so the next worker doesn't have to rediscover it; (d) this does
   not relax any rule above — a cited index lookup is never a substitute for the audit,
   test, or completion requirements this file or any per-task protocol otherwise imposes.
   Does not assume zoekt or any other code-search service is running — no zoekt systemd
   unit exists as of this writing; verify what's actually available before relying on it.

## Contact

Repository owner: raajat.agarwal@gmail.com
