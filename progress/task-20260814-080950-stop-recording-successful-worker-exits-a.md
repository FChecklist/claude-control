# Stop recording successful worker exits as failed in the register (UMR-20260814-080423-bd93)

## Completed
- [x] Reproduced the real evidence: `resource_governor.py --query-umr --limit 120 --status
      failed` on the live server shows all 31 status='failed' rows in the cited window
      (2026-08-14T01:51-07:47Z) carry a `reason` from `worker-exit-status-bridge.py`, and
      55/120 total failed rows across the box share `task.yaml`'s own last checkpoint
      status='blocked'.
- [x] Read `worker-exit-status-bridge.py` in full and confirmed it is NOT the defect: it
      only ever bridges an ALREADY self-reported negative `task.yaml` checkpoint status
      (failed/blocked/cancelled/rejected_duplicate/superseded/not_needed) to
      `umr_tasks.status='failed'` -- it never invents a negative status from a bare exit
      code. Matches this UMR's own "important prior finding".
- [x] Traced the two real units PM sentinel cited
      (`veridian-worker@task-20260814-071919-rca--umr-20260807-003517-23bb-killed.service`,
      `...task-20260814-071834-rca--umr-20260807-101751-68ff-killed.service`) to their real
      branches in `compliance-tracker`
      (`worker/task-20260814-071919-rca--umr-20260807-003517-23bb-killed`,
      `worker/task-20260814-071834-rca--umr-20260807-101751-68ff-killed`) and confirmed via
      real `git diff` against `origin/main` that both diffs are genuinely doc-only
      (`PROGRESS.md`, `ai-os/boss/ACTIVE-CLAIMS.yaml`, their own
      `progress/<task_id>.md`) -- zero application code, and that the underlying RCA work
      (verifying the original kill/decline, calling `mark-umr-terminal` for the target row)
      was real and correct.
- [x] Root-caused to `progress_completion_gate.py`'s `check-completion` (called from
      `worker-entrypoint.sh`'s `COMPLETION-GATE-BLOCK`): `pm-sentinel-tick.sh`'s Check 2a
      RCA dispatch template quotes the TARGET row's own live `reason` field verbatim
      (`real recorded reason: "..."`) -- historical evidence about the ORIGINAL incident,
      not this RCA task's own objective -- and `extract_named_code_files()` wrongly treated
      a code filename cited inside that quote (`directive-engine-stop-audit-monitor.sh`) as
      a required objective file. Proved this directly against the real function with the
      real reconstructed prompt text and the real doc-only diff before writing any fix.
- [x] Checked for live-deployment drift per this UMR's own instruction: `/opt/veridian/scripts`
      (the real live checkout) was one merge behind `origin/main` (an unrelated dupguard fix,
      PR #356) at investigation time. The real `origin/main` tip at PR time was actually
      `363702c` (PR #348), newer still -- confirmed `progress_completion_gate.py` was
      byte-identical between the live checkout's base and the true `origin/main` tip, so no
      other change to this file was in flight; the fix branch was cut from the true tip, not
      the stale live checkout.
- [x] Real code fix in `FChecklist/veridian-scripts`: excluded filenames that appear only
      inside a quoted `reason:` citation from `extract_named_code_files()`, same
      "excluded-unless-also-named-elsewhere" rule already established for the existing
      evidence-list and boilerplate-tool-name exclusions in that file.
- [x] Real tests added and run (41 passed, exit 0) -- `tests/test_progress_completion_gate.py`
      (2 new unit tests + 1 new end-to-end `check_completion()` test reproducing the exact
      real RCA-prompt/doc-only-diff shape) and `tests/test_worker_exit_status_bridge.py`
      (`test_exit0_gate_accepted_rca_completion_never_recorded_as_failed` -- the full
      two-file chain: gate acceptance -> resulting checkpoint status -> bridge leaves the
      real `umr_tasks` row at status='running', never 'failed'). Confirmed the new tests
      FAIL on the pre-fix code with the exact real rejection message.
- [x] Real PR opened against `FChecklist/veridian-scripts`:
      https://github.com/FChecklist/veridian-scripts/pull/363 (branch
      `fix/stop-recording-successful-worker-exits-as-failed-umr20260814080423-bd93`), a real
      code diff (progress_completion_gate.py + 2 test files), not a PROGRESS.md-only PR. This
      repo (`claude-control`) is not where the code fix belongs -- the register/completion-gate
      code lives in `veridian-scripts`; this task's own `repo:` field is `claude-control`, a
      cross-repo dispatch, same pattern already established elsewhere in this codebase (see
      `check_live_scripts_drift.py`'s own boilerplate-exclusion precedent for the same
      "real fix belongs in veridian-scripts" shape).

## Remaining
- [ ] Await CI + review/merge on veridian-scripts PR #363 (out of this task's own direct
      control once opened -- normal supervisor-review path for that repo).
- [ ] Once merged, the live `/opt/veridian/scripts` checkout should pick it up on its next
      real sync (not performed here to avoid mutating a shared production checkout mid-review
      for an unmerged PR).

## One noted separate anomaly (not in this fix's scope, flagged for a future task)
While investigating, found that `UMR-20260807-101751-68ff`'s own umr_tasks row was
independently re-marked `status='failed'` by a manual "task-20260814-080739 sweep" with a
DIFFERENT reason (not worker-exit-status-bridge.py) purely because its branch is doc-only
("no mergeable code artifact exists") -- even though its real, correct disposition (target
PR #249 already merged independently) needed no code in this workspace at all. This is a
related but distinct false-positive (a human/agent-run sweep conflating "no code diff" with
"no real completion evidence", not this gate). Not touched here -- out of this UMR's own
scope (worker-exit-status-bridge path only) and not part of the 31-row pattern the SPEC
asked to fix.
