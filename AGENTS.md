# AGENTS.md — Authorized AI Agents (claude-control)

> Owner: Rajat Agarwal (raajat.agarwal@gmail.com)

This document is the claude-control-specific counterpart to `FChecklist/compliance-tracker`'s
`AGENTS.md`. Written from scratch for this repository — claude-control's own history and
infrastructure are different from `compliance-tracker`'s, and this file says so honestly
rather than asserting a governance setup that doesn't exist here yet.

## What this repo actually is

claude-control is the cross-project requirements & decision catalog and orchestration control
repo for VERIDIAN's AI OS — see `README.md` and `CONTROLLER.yaml` (the single always-consult
ledger; read it before starting work on any tracked project). It holds `ai-os/` (constitution,
memory, capability/wiring registries, dispatch tooling under `ai-os-scripts/`), `scripts/`
(including `superboss-register.py`, a duplicate of the canonical copy in `veridian-scripts` —
see that repo's own note on this), and dated report archives under `reports/`.

## Where the rest of the operating docs live (on-demand, not duplicated here)

This file is intentionally the ONLY always-loaded instruction file.
- **Dispatch mechanics, tier classification, retry policy** → `SUPERBOSS_DISPATCH_PROMPT.md`
  (also `CONTROLLER.yaml` entry `SUPERBOSS-PROMPT-01`). Read before running a dispatch cycle.
- **Draft, unbuilt model-routing spec (historical only)** → `archive/drafts/AI_AGENT_INSTRUCTION_MANUAL_DRAFT_2026-07-19.md`.
  Superseded in practice by the single-model policy actually shipped.
- **Repo map / what already exists** → run the `inventory` skill instead of re-exploring by hand.
- **CA/auditor compliance checklist** → the `veridian-audit` skill (`/veridian-audit`; does not
  auto-trigger).

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

## Report filing rules — Added 2026-08-18 (stops the RCA/STATUS_REPORT bleed)

Two RCAs diagnosed this problem correctly (see the 2026-08-18 cleanup audit) but their fixes
were never wired into this repo's own scripts. The `veridian-ops-plugin`'s `PreToolUse` hook
now enforces this mechanically, not just this paragraph:

1. New incident/merge/audit reports go under `reports/{incidents,merges,audits}/`, named
   `<TYPE>_<YYYYMMDD>_<UMR-id-or-slug>.md`.
2. Generic shared filenames (`RCA.md`, `STATUS_REPORT.md`, `report.md`, `summary.md`, ...) are
   blocked for new file creation — they caused repeated PR collisions and at least one
   discarded PR.
3. A second report for the same id requires an explicit suffix (`_second_pass`, `_addendum`) —
   the hook blocks a same-id file without one and names the existing file to update instead.

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
