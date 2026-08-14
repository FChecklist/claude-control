# task-20260814-075408-complete-e592--close-task-gateway-py-gov

UMR-20260813-042708-e592: task-gateway.py's cmd_start bypasses
resource_governor.py's stop-work gate. Repo: FChecklist/claude-control.

## Investigation findings

- PR#126 (FChecklist/claude-control) was closed 2026-08-13 without merging.
  Its branch (`worker/task-20260813-042729-close-task-gateway-py-stop-work-bypass-g`)
  still exists and contains real work: `scripts/task-gateway.py` (+55 lines,
  `run_task_start_gate()` wired into `cmd_start`) and
  `tests/test_task_gateway_stop_work_gate.py` (293 lines).
- The audit that closed PR#126 found: the exact same fix was already live at
  `/opt/veridian/scripts/task-gateway.py` -- but that path belongs to a
  DIFFERENT git repo (`FChecklist/veridian-scripts`, confirmed via
  `git -C /opt/veridian/scripts remote -v`), not `claude-control`. So closing
  PR#126 without landing an equivalent fix in `claude-control` left
  `claude-control`'s own `scripts/task-gateway.py` still bypassing the gate --
  the audit's "already shipped live" claim was true for veridian-scripts, not
  for this repo.
- `claude-control`'s own `scripts/resource_governor.py` (697 lines, git HEAD)
  is a much earlier version than the live `/opt/veridian/scripts/
  resource_governor.py` (5410 lines) -- it has NO `--check-task-start-gate`
  flag, no `STOP_WORK_ORDER_TASK_IDS`/`OWNER_DECISIONS_PATH` machinery. PR#126's
  `run_task_start_gate()` depended on that nonexistent-in-git flag, so it
  cannot be merged as-is against this repo's actual resource_governor.py.
  Backporting the FULL stop-work-order/OWNER_DECISIONS subsystem is a much
  larger, separate UMR (UMR-20260808-121334-e122) and out of scope here.
- What DOES already exist, real and tested, in `claude-control`'s own
  `resource_governor.py`: `dispatch_one()` unconditionally checks
  `EMERGENCY_STOP_PATH` (the sentinel literally named "stop work" --
  `_write_emergency_stop()`'s own message: "All new dispatch is halted until
  an operator runs --clear-emergency-stop") and the 4-metric 99% threshold
  gate, before ever selecting/spawning a queued task. `cmd_start`'s
  synchronous direct-spawn path checks neither.

## Plan (scoped to this repo's real, existing gate)

1. `scripts/resource_governor.py`: extract the inline EMERGENCY_STOP +
   metric-threshold check already at the top of `dispatch_one()` into a
   reusable `resource_threshold_block_reason(now=None)` (pure extraction,
   `dispatch_one()` calls it, behavior unchanged). Add `--check-task-start-gate`
   CLI flag that calls it and prints `{"blocked", "detail", "metrics"}`.
2. `scripts/task-gateway.py`: add `RESOURCE_GOVERNOR` constant + a
   `run_task_start_gate()` function (subprocess call, matching this file's
   existing wrapped-script convention) wired into `cmd_start` right after the
   duplicate-task-key claim and before `veridian-task.py create` -- same
   position PR#126 used.
3. Real tests for both (extend `tests/test_resource_governor.py` +
   `tests/_resource_governor_fixtures.py`; new `tests/
   test_task_gateway_stop_work_gate.py` adapted from PR#126's, but against
   this repo's real gate, not the unmerged stop-work-order machinery).
4. Open PR against `FChecklist/claude-control`, request/perform a real audit,
   report the PR number.

## Completed
- [x] Investigated PR#126 (closed, not merged) -- confirmed real but
      non-mergeable-as-is (depends on a CLI flag that doesn't exist in this
      repo's resource_governor.py)
- [x] Root-caused why: PR#126's audit compared against a DIFFERENT repo's
      (veridian-scripts) already-live copy, not this repo's own file
- [x] Identified the real, existing gate in this repo's resource_governor.py
      (EMERGENCY_STOP_PATH + metric threshold, currently only enforced inside
      dispatch_one())

- [x] Extracted `resource_threshold_block_reason()` in resource_governor.py
      (pure extraction from dispatch_one()'s inline EMERGENCY_STOP + metric
      checks) + added `--check-task-start-gate` CLI flag
- [x] Wired task-gateway.py's `cmd_start` through the gate via
      `run_task_start_gate()`, right after the duplicate-task-key claim and
      before `veridian-task.py create`
- [x] Added 6 new tests to tests/test_resource_governor.py + new
      tests/test_task_gateway_stop_work_gate.py (7 tests: load-bearing
      real-subprocess block test, symmetry clear-proceeds test, source
      regression guard, 4 run_task_start_gate() unit tests)
- [x] Ran full test suite locally: 182 passed; 2 pre-existing failures
      confirmed unrelated (reproduced identically on pre-change commit --
      same 2 PR#126 itself documented); 1 test
      (test_concurrent_dispatch_never_double_dispatches_the_same_queued_row)
      confirmed pre-existing flaky (reproduces on both pre- and post-change
      commit, real `_save_json` tmp-file race under concurrent subprocesses)
- [x] Committed (124cc5e) + pushed to
      worker/task-20260814-075408-complete-e592--close-task-gateway-py-gov

- [x] Opened PR #219 against FChecklist/claude-control (master <-
      worker/task-20260814-075408-complete-e592--close-task-gateway-py-gov):
      https://github.com/FChecklist/claude-control/pull/219 -- confirmed
      `scripts/task-gateway.py` is present in the PR's real diff (completion
      gate satisfied)
- [x] Recorded UMR completion via agent_work_briefing.py record-completion
      (UMR-20260814-074711-080e, --umr-pr-number 219)

## Remaining
- [ ] Real independent audit (standing async review process -- same
      mechanism that reviewed PR#126/PR#349 -- not self-triggerable from
      within this task; PR is open and awaiting it)
- [ ] Merge once audit passes
