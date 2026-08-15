## Problem

When a task is hard-rejected by the pre-flight schema/validation gate (`worker-entrypoint.sh`'s `PREFLIGHT-GUARD-BLOCK`), `veridian-task.py checkpoint` writes the real, specific cause into task.yaml's own checkpoint `note`, e.g.:

```
PRE-FLIGHT HARD STOP (tight_task_schema_violation): Complexity tier moderate is not
recognized. Please use one of: mechanical, integrative, judgment.
```

`worker-exit-status-bridge.py` (this `ExecStopPost` hook) then bridges that self-reported `blocked` checkpoint to `umr_tasks.status='failed'`, but discarded the real note entirely, writing only its own generic boilerplate as the register `reason`:

```
worker-exit-status-bridge (ExecStopPost, STEP 2 fix task-20260807-052027-platform-integrity--worker-units-exit-0): unit veridian-worker@<id>.service stopped with task.yaml's own last checkpoint status='blocked' ...
```

That string names the **component that reported the exit**, not the cause. Every operator/PM tier reading a `failed` register row had to SSH in, find the task directory, and read `task.yaml` by hand to learn why. Confirmed live: 3 real rows hard-stopped this way on 2026-08-15 alone (`tight_task_schema_violation` twice, `no_runnable_verification_command_in_success_criteria` once).

## Fix

In `run()`, when the last checkpoint's status is `blocked` and it carries a real `note`, that note now becomes the register `reason` (suffixed with `[via worker-exit-status-bridge]` so the writer stays identifiable, without leading with it):

```
PRE-FLIGHT HARD STOP (tight_task_schema_violation): Complexity tier moderate is not
recognized. Please use one of: mechanical, integrative, judgment. [via worker-exit-status-bridge]
```

Every other self-reported-negative case (no note present, or a non-`blocked` status such as plain `failed`/`cancelled`/`rejected_duplicate`/`superseded`/`not_needed`) is completely unaffected — it still gets the pre-existing generic boilerplate reason, exactly as before. No exit codes changed, no change to which rows get marked terminal, and the `ExecStopPost` fail-open contract (never a non-zero exit from this hook, never contaminating the unit's own `Result`) is untouched.

## Diff

```diff
@@ -261,18 +261,42 @@ def run(task_id, unit_kind="worker"):
         # Leave alone.
         _log(task_id, unit_kind, f"last task.yaml status={last_status!r} for umr {row['umr_id']} -- "
                                   f"not a self-reported negative outcome, leaving at running")
         return

-    reason = (
-        f"worker-exit-status-bridge (ExecStopPost, STEP 2 fix task-20260807-052027-platform-"
-        f"integrity--worker-units-exit-0{'  + supervisor-side extension UMR-20260813-090037-9a34' if unit_kind == 'supervisor' else ''}): "
-        f"unit {unit_name} stopped with task.yaml's own last "
-        f"checkpoint status={last_status!r} (a self-reported, no-more-automatic-progress "
-        f"outcome) -- bridging to umr_tasks so the row does not stay at 'running' forever with "
-        f"no further exit ever coming."
-    )
+    # task-20260815-230158-propagate-the-real-preflight-denial-reas: for the one real,
+    # common case that matters most operationally -- a preflight hard stop
+    # (worker-entrypoint.sh's PREFLIGHT-GUARD-BLOCK, e.g. tight_task_schema_violation,
+    # credit_accountant_rejected, circuit_breaker_tripped, ...) -- task.yaml's own last
+    # checkpoint note already carries the real, specific, self-describing rejection
+    # reason. Previously this hook discarded that note entirely and wrote only its
+    # own generic boilerplate as the register reason -- which names the COMPONENT
+    # THAT REPORTED the exit, not the cause. When that real note exists, use IT as
+    # the register reason, with a short suffix identifying this bridge as the
+    # writer -- never leading with the bridge name. Every other self-reported-
+    # negative status (no note, or non-'blocked') is completely unaffected.
+    checkpoint_note = None
+    if last_status == "blocked":
+        checkpoint_note = checkpoints[-1].get("note") if checkpoints else task.get("note")
+
+    if checkpoint_note:
+        reason = f"{checkpoint_note} [via worker-exit-status-bridge]"
+    else:
+        reason = (
+            f"worker-exit-status-bridge (ExecStopPost, STEP 2 fix task-20260807-052027-platform-"
+            f"integrity--worker-units-exit-0{'  + supervisor-side extension UMR-20260813-090037-9a34' if unit_kind == 'supervisor' else ''}): "
+            f"unit {unit_name} stopped with task.yaml's own last "
+            f"checkpoint status={last_status!r} (a self-reported, no-more-automatic-progress "
+            f"outcome) -- bridging to umr_tasks so the row does not stay at 'running' forever with "
+            f"no further exit ever coming."
+        )
     try:
```

`tests/test_worker_exit_status_bridge.py` gains two new real regression tests (real scratch SQLite DB + real `mark-umr-terminal` subprocess call, same convention every other test in this file uses — never mocked):

- `test_blocked_preflight_note_propagates_real_reason_code`: builds a temp task.yaml whose last checkpoint is `status=blocked` with the real `tight_task_schema_violation` note text, runs the bridge, and asserts the register `reason` contains both the real `reason_code` token and the full note text, and does **not** merely lead with `worker-exit-status-bridge`.
- `test_normally_completed_task_reason_path_unchanged`: a plain `status=failed` checkpoint with no note still gets the original generic boilerplate reason, unchanged.

## Test output

```
$ python3 -m pytest tests -k exit_status_bridge -v
collecting ... collected 969 items / 947 deselected / 22 selected

tests/test_worker_exit_status_bridge.py::test_self_reported_negative_writes_failed_real_end_to_end[worker-veridian-worker@{task_id}.service-worker.log] PASSED
tests/test_worker_exit_status_bridge.py::test_self_reported_negative_writes_failed_real_end_to_end[supervisor-veridian-supervisor@{task_id}.service-supervisor.log] PASSED
tests/test_worker_exit_status_bridge.py::test_blocked_preflight_note_propagates_real_reason_code PASSED
tests/test_worker_exit_status_bridge.py::test_normally_completed_task_reason_path_unchanged PASSED
tests/test_worker_exit_status_bridge.py::test_non_negative_statuses_never_write[completed-worker] PASSED
tests/test_worker_exit_status_bridge.py::test_non_negative_statuses_never_write[completed-supervisor] PASSED
tests/test_worker_exit_status_bridge.py::test_non_negative_statuses_never_write[in_progress-worker] PASSED
tests/test_worker_exit_status_bridge.py::test_non_negative_statuses_never_write[in_progress-supervisor] PASSED
tests/test_worker_exit_status_bridge.py::test_non_negative_statuses_never_write[pending-worker] PASSED
tests/test_worker_exit_status_bridge.py::test_non_negative_statuses_never_write[pending-supervisor] PASSED
tests/test_worker_exit_status_bridge.py::test_non_negative_statuses_never_write[pending_review-worker] PASSED
tests/test_worker_exit_status_bridge.py::test_non_negative_statuses_never_write[pending_review-supervisor] PASSED
tests/test_worker_exit_status_bridge.py::test_completed_no_change_with_real_marker_bridges_to_completed_real_end_to_end PASSED
tests/test_worker_exit_status_bridge.py::test_completed_no_change_without_marker_leaves_running PASSED
tests/test_worker_exit_status_bridge.py::test_completed_no_change_marker_missing_branch_sha_leaves_running PASSED
tests/test_worker_exit_status_bridge.py::test_row_already_non_running_is_idempotent_noop PASSED
tests/test_worker_exit_status_bridge.py::test_no_umr_row_for_unit_is_a_safe_noop PASSED
tests/test_worker_exit_status_bridge.py::test_no_task_yaml_leaves_row_running_for_step3_reconciler PASSED
tests/test_worker_exit_status_bridge.py::test_exit0_gate_accepted_rca_completion_never_recorded_as_failed PASSED
tests/test_worker_exit_status_bridge.py::test_unknown_unit_kind_argv_is_a_safe_noop PASSED
tests/test_worker_exit_status_bridge.py::test_real_systemd_stop_fires_the_bridge_end_to_end[worker] PASSED
tests/test_worker_exit_status_bridge.py::test_real_systemd_stop_fires_the_bridge_end_to_end[supervisor] PASSED

===================== 22 passed, 947 deselected in 11.03s ======================
```

(20 pre-existing tests + 2 new ones, all passing — including the real `systemctl --user` end-to-end tests, not skipped in this environment.)

## Real-evidence examples this fixes (from live `task.yaml` on disk today)

- `PRE-FLIGHT HARD STOP (tight_task_schema_violation): Complexity tier moderate is not recognized. Please use one of: mechanical, integrative, judgment.`
- `PRE-FLIGHT HARD STOP (tight_task_schema_violation): no_runnable_verification_command_in_success_criteria`

Both will now propagate verbatim into the register `reason` field instead of the opaque `worker-exit-status-bridge (ExecStopPost, ...)` boilerplate.

task-20260815-230158-propagate-the-real-preflight-denial-reas
UMR-20260815-135449-28ed

🤖 Generated with [Claude Code](https://claude.com/claude-code)
