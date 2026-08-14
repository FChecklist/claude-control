# PROGRESS -- task-20260814-043409-add-search-reuse-discipline-to-real-agen

Governing chain: addendum to P1 UMR-20260806-171945-5767. Owner-approved citation:
OWNER_DECISIONS_NEEDED_2026-07-23.yaml entry id=crontab-drift-approved-2026-08-14, status=approved.
UMR for this task: UMR-20260814-043403-112d.

## Scope (confirmed by real inspection, not assumed)
Real indexes cited by the spec, verified to exist on disk:
- `/opt/veridian/ai-os/memory/superboss-register.sqlite#system_index`
- `/opt/veridian/ai-os/memory/superboss-register.sqlite#capability_registry`
- `/opt/veridian/ai-os/memory/superboss-register.sqlite#wiring_registry`
- `/opt/veridian/ai-os/memory/CLAUDE_MEMORY_INDEX.md`
- `/opt/veridian/ai-os/memory/dead_ends.json`
- `/opt/veridian/ai-os/memory/open_questions.json`

Real repos with their own AGENTS.md under source control on default branch (checked via
`git ls-tree <default-branch>`, worktree/node_modules copies excluded):
- compliance-tracker (has AGENTS.md on `main`)
- projexa (has AGENTS.md on `main`)
- veda-advisors (has AGENTS.md on `main`)
- claude-control (no AGENTS.md yet on `master` -- this is this task's own workspace repo)
- veridian-scripts (no AGENTS.md yet on `main`)

No other real (non-worktree, non-node_modules) repo under /opt/veridian/repos has an AGENTS.md
(checked: ai-os [not a git repo], global-revenue-engine, infisuite-reverse-engineering,
odoo-reverse-engineering, sumeet-spec, veridian-ai-os, veridian-brain, veridian-ui-kit,
zai-independent-audit-2026-07-30, zoho-reverse-engineering -- none have one).

superboss-register.py: exists as a duplicate in TWO repos. The canonical/live one (per its own
docstring, "CANONICAL SCRIPT... the one real canonical script for every real read and every
real write against superboss-register.sqlite", 10304 lines, actively maintained, last touched
2026-08-14) lives in **veridian-scripts**. claude-control's copy (3451 lines, last touched
2026-08-03, an older/stale duplicate) is NOT the canonical one. Fixing the canonical copy in
veridian-scripts.

## Completed
- [x] Confirmed real repo/AGENTS.md/index inventory above
- [x] Progress file created
- [x] veda-advisors: added Search-Reuse Discipline (Operating Rule 6) to AGENTS.md, PR
      opened against `main` (not a worktree): https://github.com/FChecklist/veda-advisors/pull/18
- [x] compliance-tracker: added Search-Reuse Discipline (Operating Rule 12) to AGENTS.md,
      PR opened against `main` (fresh scratch clone, not the dirty local worktree at
      /opt/veridian/repos/compliance-tracker which had unrelated in-flight changes):
      https://github.com/FChecklist/compliance-tracker/pull/1127
- [x] projexa: added Search-Reuse Discipline (Operating Rule 7) to AGENTS.md, PR opened
      against `main` (fresh scratch clone, not the dirty local worktree):
      https://github.com/FChecklist/projexa/pull/71
- [x] claude-control: created AGENTS.md (none existed) with Search-Reuse Discipline as
      Operating Rule 5, PR opened against `master` from this task's own worker branch:
      https://github.com/FChecklist/claude-control/pull/205
- [x] veridian-scripts: created AGENTS.md (none existed) with Search-Reuse Discipline as
      Operating Rule 5 + added `RetryConnection` (busy-timeout already existed at 30s;
      added real retry-with-backoff on top, 20-min total-wait ceiling, verified live
      against an actually-locked SQLite file + existing test suite) to the CANONICAL
      `superboss-register.py`, PR opened against `main`:
      https://github.com/FChecklist/veridian-scripts/pull/351

## Remaining
- [ ] Check CI on all 5 PRs; merge each once green (autonomous-merge precedent: compliance-tracker/veda-advisors AGENTS.md Rule 10/Owner 2026-07-31 "Full autonomy, no exceptions")
- [ ] Report real diffs for each repo to the user
- [ ] record-completion write-back to UMR-20260814-043403-112d
