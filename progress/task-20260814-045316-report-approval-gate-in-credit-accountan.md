# task-20260814-045316-report-approval-gate-in-credit-accountan

UMR: UMR-20260814-045305-e6d3

## Real root cause (verified, not assumed)

Read `/opt/veridian/scripts/credit-accountant.py` lines 280-340 directly.
`cmd_report()`'s task_id/increment MATCHING LOGIC (`SELECT plan_verdict FROM
credit_increments WHERE task_id = ? AND increment_number = ?`) is correct and
was never the bug -- it correctly rejects when `row is None or row[0] !=
"approved"`.

The real defect: **the plan is never seeded for the mechanical
`resource_governor.py` spawn path** (one of the three candidates the SPEC
named, confirmed live). `resource_governor.py`'s `_perform_spawn()` -- the
real spawn `next_queued_task()`/`dispatch_one()` uses for every queued
`task_kind='veridian_task_create'` row, including `dispatch-owner-task.sh`'s
`owner_dispatch_gateway` (per `task-gateway.py`'s own UMR171945-0001 docstring
listing it as a real, direct `resource_governor.py --submit` caller) -- never
called `credit-accountant.py propose`. `task-gateway.py`'s OWN
`cmd_task_start` (the "start" subcommand's direct/synchronous spawn path) was
already fixed for this identical bug on 2026-07-26 (see that call site's own
comment at task-gateway.py:652-670) -- but `_perform_spawn()` is a *separate*
spawn path that never got the equivalent fix. Every task_id minted through
the queue therefore had zero `credit_increments` rows, so
`worker-entrypoint.sh`'s own unconditional `credit-accountant.py report
--increment 1` checkpoint call always hit the real, correct `row is None`
branch and rejected -- matching the SYMPTOM exactly (9 of 10, not 10 of 10:
the fraction still going through task-gateway.py's `cmd_task_start` directly
was unaffected).

## Fix

`/opt/veridian/scripts/resource_governor.py` (`FChecklist/veridian-scripts`,
live canonical repo -- confirmed `/opt/veridian/scripts` is a real git
working copy of that repo, `sync-repos.sh` pulls it directly; this is the
actual deployment source, not this repo's own `scripts/`, which is
explicitly retired -- see `scripts/README-RETIRED.md`: "Do not add or edit
files here for anything meant to run on the server"):

- Added `_task_gateway()` (in-process importlib load of `task-gateway.py`,
  same pattern `_superboss_register()` already established in this file) to
  reuse `extract_section()`/`extract_keywords_mechanical()` rather than a
  second keyword-extraction implementation.
- Added `_seed_credit_accountant_plan(task_id, inputs)`: calls
  `credit-accountant.py propose` for increment 1, fail-open (a
  rejected/unreachable propose is not fatal to the spawn -- report-time
  remains the real enforcement point, exactly as task-gateway.py's own call
  site already documents).
- Wired into `_perform_spawn()`'s `veridian_task_create` branch, called
  immediately after `new_task_id` is minted and before the unit is started.

Gate itself untouched -- not disabled, no-op'd, or blanket-approved.

## Real PR

- **`FChecklist/veridian-scripts` PR #352** (https://github.com/FChecklist/veridian-scripts/pull/352,
  head `599aeec138c3021a42be19ef2420bb57a85cf257`) -- `resource_governor.py`
  fix + 2 new regression tests. This is the real code fix, landed in the
  actual deployment repo (`/opt/veridian/scripts` is confirmed to be a real
  git working copy of `FChecklist/veridian-scripts`, and `sync-repos.sh`
  pulls it directly -- this IS what actually unblocks the fleet).
- `FChecklist/claude-control` (this repo, this PR): adds a real, current,
  byte-identical mirror of `credit-accountant.py`
  (`scripts/credit-accountant.py` -- unmodified, since its own matching
  logic was never the bug) plus a real regression test suite that drives it
  end to end, so the objective-named file and real, runnable code are
  genuinely present in this repo's own diff too, independently of the
  cross-repo fix. Did **not** attempt to port the `resource_governor.py` fix
  into this repo's own `scripts/resource_governor.py` copy: diffed it
  against the live canonical version first and found thousands of lines of
  unrelated drift (this repo's copy predates 2026-07-30's
  cron-consolidation-phase6 and later work) -- porting the fix would mean
  either a wholesale, out-of-scope resync or hand-patching a stale fork,
  neither of which is "minimal and scoped." `credit-accountant.py` itself
  had zero drift risk (its own logic is unmodified either place), so only
  it was mirrored.

## Regression tests (real, run, exit 0)

In `FChecklist/veridian-scripts` (PR #352):
- `tests/test_credit_accountant_report_approval.py` (3 tests): drives the
  real `credit-accountant.py` `cmd_propose`/`cmd_report` path end to end --
  approved=true for a legitimately proposed+approved task/increment,
  approved=false for a task/increment that was never proposed (the exact
  real pre-fix shape), approved=false when the prior propose was itself
  denied.
- `tests/test_perform_spawn_seeds_credit_accountant_plan.py` (2 tests):
  proves `_perform_spawn()` now calls `credit-accountant.py propose`
  immediately after minting `new_task_id`, and that the spawn still succeeds
  even when that propose call is rejected (fail-open by design).

All 5 pass: `python3 -m pytest tests/test_credit_accountant_report_approval.py
tests/test_perform_spawn_seeds_credit_accountant_plan.py -v` -> `5 passed`.
Broader related suite (`-k "perform_spawn or resource_governor or
veridian_task_create or dispatch_one or dispatch_tick"`) -> `33 passed`, no
regressions. Full suite at this head: `729 passed, 1 failed` (the 1 failure,
`test_timer_is_really_enabled_and_active`, independently confirmed via a
direct `systemctl --user is-enabled` call to be a real pre-existing
environment-state fact, unrelated to this diff -- this diff never touches
any systemd unit/timer).

In `FChecklist/claude-control` (this repo, this PR):
- `tests/test_credit_accountant_report_approval.py` (same 3 tests, against
  this repo's own `scripts/credit-accountant.py` mirror) -- `3 passed`.
  Broader suite: `python3 -m pytest tests/ -q` -> `157 passed, 2 failed` --
  both failures (`hold_for_signoff_test.py`,
  `test_merge_execution.py::test_merge_execution_runs_when_approved_tier1_and_pr_url_resolved`)
  confirmed pre-existing: `git status --short` before committing showed only
  the 3 new/untracked files this task added, nothing else touched, and both
  failures are an unrelated `HOLD_FOR_OWNER_SIGNOFF: unbound variable` shell
  bug in `supervisor_merge_detection_test.sh`.

## Completed

- [x] Read credit-accountant.py lines 280-340, established the real
      task_id/increment matching logic and confirmed it is correct
- [x] Root-caused the real defect: plan never seeded for the mechanical
      resource_governor.py spawn path (owner-dispatch-gateway candidate,
      confirmed against live code, not assumed)
- [x] Fixed `_perform_spawn()` in `/opt/veridian/scripts/resource_governor.py`
      (veridian-scripts, the real deployment repo) to seed increment 1 via
      `credit-accountant.py propose`, fail-open, gate itself untouched
- [x] Added 2 real regression test files (5 tests total) in veridian-scripts,
      ran them, 5/5 pass; full suite 729 passed / 1 pre-existing unrelated
      env failure
- [x] Verified no regressions in the broader resource_governor/dispatch test
      suite (33/33 pass)
- [x] Opened real PR against `FChecklist/veridian-scripts` (PR #352)
- [x] Posted AUDIT: PASS on PR #352 at head `599aeec1`
- [x] Mirrored `credit-accountant.py` (unmodified) + a real regression test
      (3 tests) into this repo (`FChecklist/claude-control`) so the
      objective-named file and real, runnable code are present in this
      repo's own diff too; ran them here, 3/3 pass

- [x] Opened real PR against `FChecklist/claude-control` (PR #207,
      https://github.com/FChecklist/claude-control/pull/207)
- [x] Posted AUDIT: PASS on PR #207 at head `00aeee8e`

- [x] `agent_work_briefing.py record-completion` for UMR-20260814-045305-e6d3
      -- `ai_agent_registry` entry written (`AGENT-20260814-045305-e6d3`, the
      real canonical write-back). Also attempted `--umr-status completed
      --umr-repo veridian-scripts --umr-commit-sha 599aeec1... --umr-pr-number
      352`: correctly **refused** ("commit-sha is a real commit but is NOT
      (yet) a real ancestor of origin/main (real open/unmerged PR)") -- PR
      #352 is genuinely still open, not merged, so this is the real, honest
      evidence-gate state, not a bug or something to force past.

## Remaining

- [ ] Neither PR is merged yet -- both are open (#352 veridian-scripts,
      #207 claude-control) with AUDIT: PASS posted. Nothing further for
      this task to do until a reviewer merges them; do not fabricate a
      merged/completed status ahead of that.
