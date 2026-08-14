# task-20260814-085900-fix-pr219-metric-state-corruption-audit

UMR-20260814-085830-b190. Fixes the state-corruption bug PR#219 (claude-control)
got AUDIT:FAIL on, 2026-08-14. Governor-bypass wiring itself (cmd_start ->
EMERGENCY_STOP-sentinel check) is already good/audit-confirmed and is NOT
touched here.

## Completed

- [x] Read PR#219's full AUDIT:FAIL comment (posted 2026-08-14T08:14:35Z) --
      confirmed the one in-scope bug: `resource_threshold_block_reason()` ->
      `sample_metrics()` unconditionally overwrites the single shared
      `METRIC_STATE_PATH` file, which `dispatch_one()`'s periodic `--tick`
      loop also reads/writes for its own delta (rate) calc. `cmd_start` is a
      high-frequency entrypoint, so every call was resetting that shared
      baseline and corrupting the periodic tick dispatcher's disk_io/network
      rate math. (Confirmed out of scope, per SPEC, and NOT touched: the
      other two lower-severity findings in the same audit -- permanent
      task_key claim before the gate check, and the unused `--title` CLI arg
      -- SPEC named only the sample_metrics/METRIC_STATE_PATH bug.)
- [x] `scripts/resource_governor.py`:
  - `sample_metrics(now=None, persist=True)` -- new `persist` kwarg. When
    `False`, still reads the current raw sample and computes deltas against
    whatever baseline is already on disk, but never calls `_save_json` on
    `METRIC_STATE_PATH` (true read-only mode, no second state file needed).
  - `resource_threshold_block_reason(now=None, persist=True)` -- new
    `persist` kwarg, passed straight through to `sample_metrics()`.
  - `dispatch_one()` -- **unchanged call** (`resource_threshold_block_reason(now=now)`,
    `persist` defaults `True`), so the real periodic `--tick` dispatcher's
    own baseline-owning behavior is bit-for-bit identical to before this fix.
  - `--check-task-start-gate` CLI branch (the one task-gateway.py's
    `run_task_start_gate()` subprocess-calls from `cmd_start`) now calls
    `resource_threshold_block_reason(persist=False)` -- the on-demand,
    high-frequency gate check no longer mutates the shared baseline.
  - task-gateway.py itself needed **no changes** -- the CLI subprocess
    boundary already fully isolates it from this fix.
- [x] `tests/test_resource_governor.py`:
  - Updated the 7 existing `monkeypatch.setattr(rg, "sample_metrics", lambda
    now=None: ...)` mocks to accept the new `persist=True` kwarg so they
    don't TypeError now that `resource_threshold_block_reason()` always
    passes `persist=` through.
  - Added 4 new regression tests reproducing the exact audit scenario:
    `sample_metrics(persist=False)` never writes `METRIC_STATE_PATH`;
    interleaving many `persist=False` calls between two real
    `persist=True` ticks leaves the baseline byte-identical;
    `resource_threshold_block_reason(persist=False)` never writes the file;
    and an end-to-end test that runs a real `dispatch_one()` tick then 10
    real `--check-task-start-gate` CLI subprocess calls (the actual
    task-gateway.py call shape) and asserts the on-disk baseline is
    untouched by all 10.
- [x] Full suite: `python3 -m pytest tests/ -q` -> 186 passed, 2 failed.
      Both failures (`hold_for_signoff_test.py`,
      `test_merge_execution.py::test_merge_execution_runs_when_approved_tier1_and_pr_url_resolved`)
      reproduce identically on the pre-fix branch head (verified via `git
      stash`) -- pre-existing, unrelated to this change (bash `set -u`
      unbound-variable bug in `supervisor_merge_detection_test.sh`).
      `test_resource_governor.py` + `test_task_gateway_stop_work_gate.py`:
      33/33 passed.
- [x] Committed + pushed to PR#219's own branch
      (`worker/task-20260814-075408-complete-e592--close-task-gateway-py-gov`),
      no new PR opened.

## Remaining

- [ ] Request/trigger a fresh audit against the new head and report the
      outcome back on this task.
- [ ] `record-completion` write-back to `UMR-20260814-085830-b190`'s
      ai_agent_registry row once the audit result is in hand.
