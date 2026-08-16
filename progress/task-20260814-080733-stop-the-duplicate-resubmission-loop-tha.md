# task-20260814-080733-stop-the-duplicate-resubmission-loop-tha

Real evidence (PM sentinel, `resource_governor.py --query-umr --limit 120`,
2026-08-14T01:51-07:47Z): 59/120 real umr_tasks rows (49%) were
`rejected_duplicate` against a small number of long-dead task identities
(their RCAs already concluded correctly-killed, no remaining scope). Root
cause: `submit()`'s de-dup (`find_active_umr_by_identity`) only ever checks
whether an ACTIVE (queued/dispatched/running) row exists for a task_identity
right now -- it has no memory of "this identity has already been rejected as
a duplicate over and over." Once the one lingering active row for that
identity itself reaches a terminal state, the next resume/requeue call for
the exact same identity (any caller funneling through `submit()`, e.g.
`veridian-task-watchdog.py`'s step_2/step_3 fix/escalate paths, which re-fire
every ~60s while a target still looks stalled/looping) sees no active row and
is free to create a brand new "queued" row -- resetting the loop forever.

## Completed
- [x] Root-caused the resubmission loop to `scripts/resource_governor.py`'s
      `submit()` -- the one choke point every real resume/requeue caller
      funnels through -- rather than a nonexistent `reconcile_stale_running_workers.py`
      in this repo (that script/reason string is live-system evidence from a
      different, more evolved deployment; this repo's own equivalent
      mechanism is `resource_governor.py`, confirmed via the briefing's
      `resource_governor_queue_management` capability match).
- [x] Added `MAX_DUPLICATE_ATTEMPTS_PER_IDENTITY` (env-overridable, default
      20) and a new terminal status `RETIRED_STATUS = "retired_max_attempts"`.
- [x] `submit()` now counts every `rejected_duplicate` row as a real consumed
      attempt against its `task_identity`. Once an identity's rejected-duplicate
      count reaches the hard cap, the triggering rejection itself is written
      as `retired_max_attempts` (terminal) instead of `rejected_duplicate`.
- [x] `submit()` now checks for a pre-existing `retired_max_attempts` row for
      the identity FIRST, before the active-row check -- a retired identity
      is refused immediately, with **no new umr_tasks row written at all**,
      so it can never again consume a real governor cycle, regardless of
      whether the original blocking row is still active or has since gone
      terminal (this is the literal "already-terminal identity keeps getting
      resubmitted" bug).
- [x] Added `tests/test_resource_governor.py::test_duplication_blocked_identity_is_retired_and_never_resubmitted_again`
      proving: (1) an identity's rejected_duplicate attempts accumulate to the
      cap and get retired, (2) after the identity's original row itself also
      goes terminal, a subsequent "next tick" submit() call for the exact same
      identity is refused with no new row created (umr_id and total row count
      unchanged), and (3) pre-existing rapid-fire dedup test still passes
      unmodified (cap default kept comfortably above that test's 10-submission
      burst).
- [x] Ran the full resource_governor + dispatch_tick test suites -- real exit 0.
- [x] Committed and pushed; opened PR: https://github.com/FChecklist/claude-control/pull/223
      (verified branch head diff contains scripts/resource_governor.py,
      scripts/superboss-register.py, tests/test_resource_governor.py --
      not progress/doc-only).

## Remaining
- [ ] (none)
