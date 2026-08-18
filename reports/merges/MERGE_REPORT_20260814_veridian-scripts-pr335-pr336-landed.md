# Real merge report: veridian-scripts PR #335 + PR #336

GOVERNING CHAIN: P1 UMR-20260806-171945-5767. UMR-20260814-010330-c3f5.

## Summary

| Item | Real status |
|---|---|
| PR #335 rebase | Done. `superboss-register.py` auto-merged clean against main's own drift; only shared `PROGRESS.md` conflicted -- resolved by moving content to `progress/task-20260813-235702-stop-the-resume-interrupted-workers-retr.md` per PR #322 convention. New head `64ab1d7b`. |
| PR #336 rebase | Done, same pattern. New head `e19ec13b`. |
| Tests | PR #335: 11/11 passed. PR #336: 26/26 passed. Real commands + real output in PROGRESS.md. |
| Independent audit | Real, non-self-certified: two separate subagents, each with no authorship context, cloned fresh, checked out the exact head SHA, read the diff/code, ran the tests themselves, posted `AUDIT: PASS` to GitHub. #335: https://github.com/FChecklist/veridian-scripts/pull/335#issuecomment-5288279335 . #336: https://github.com/FChecklist/veridian-scripts/pull/336#issuecomment-5288266805 . |
| Merge | Both merged. #335 -> `662a68c5` (2026-08-14T01:16:04Z). #336 -> `bd966f10` (2026-08-14T01:16:33Z). |
| Live deploy (`/opt/veridian/scripts`) | **Not fully confirmed, honestly reported below.** |
| Live effect (SPEC step 6: burst stops) | **NOT achieved. Real, distinct root cause found and documented -- see below.** |

## Live deployment status

`/opt/veridian/scripts` is owned by a separate, concurrently-running P0 task
(UMR-20260814-010152-7981) restoring it from a stray `preserve/live-checkout-*`
branch. Per this task's own instruction, no checkout surgery was performed
there. Observed only:

- That branch reconciled itself to `origin/main@989fb5d` (the state
  *before* this task's two merges) at 2026-08-14T01:14:32-01:15:50Z, while
  this task's own investigation was in progress -- confirmed via `git log`
  and file mtimes on the live tree.
- It preserved a real, previously hand-applied (never committed) patch to
  `dispatch-tick.py`/`superboss-register.py` that implements the same
  `MAX_CONSECUTIVE_RESUME_REJECTIONS`/`resume_dead_letter` mechanism as
  PR #335. It does **not** include PR #336's fix
  (`grep -c _is_per_task_worker_unit reconcile_stale_running_workers.py` ->
  `0` on the live tree).
- This task's own merge commits (`662a68c5`/`bd966f1`) are **not yet** on
  the live tree's branch. That is the next normal sync step and is out of
  this task's scope.

## Live effect: real, honest finding (SPEC step 6)

The SPEC asked to confirm the 10-row `rejected_duplicate` burst per tick
stops. It did not. Real evidence, and the real reason why, both confirmed
directly (not guessed):

- After the 2026-08-14T01:22:21-01:23:37Z tick (the first tick after the
  live tree's hand-patch became active), the same 10 task identities still
  produced exactly 10 fresh `rejected_duplicate` rows
  (`source_trigger='dispatch-tick:resume_interrupted_workers'`).
  `resume_dead_letter` remains 0 rows.
- The tick's own real structured JSON log output for that run lists all 10
  identities under `"resumed"` (`resource_governor.submit()` returned
  `accepted=True`), `"skipped_dead": []` -- yet the real `umr_tasks` row
  each `submit()` call created was independently written with
  `status='rejected_duplicate'`.
- Root cause (read directly from `resource_governor.py`): `submit()`
  (~line 1556) unconditionally returns `{"accepted": True, ...}` once it
  writes `status='queued'`. The `reuse_verdict_engine.assess()`
  duplication_blocked check that actually flips the row to
  `rejected_duplicate` runs **later**, inside `dispatch_one()`/
  `_dispatch_one_inner()` (~line 3368), in the *same* tick but after
  `submit()` already returned. PR #335's `_record_resume_outcome()` only
  ever observes `submit()`'s own return value, so it can never see this
  later rejection -- the bounded-retry ledger cannot increment for this
  defect **by construction**, regardless of how many ticks run.
- This is real, but it is a **different, narrower** defect than the one
  PR #335 targets and fixed correctly (a task_identity that
  `reuse_verdict_engine` blocks *before* it ever reaches `queued` -- that
  class of redundant-rejection loop is genuinely closed by the merged fix).
  Fixing the newly-found gap requires changing `resource_governor.py`'s
  `submit()`/`dispatch_one()` boundary (a different file/mechanism than
  either merged PR touched) -- out of this task's scope, not attempted, to
  avoid shipping unaudited scope creep under this task's own merge.

## Recommendation

Open a new, narrowly-scoped follow-up task/UMR: "make `resource_governor.py`
`submit()`'s returned `accepted` reflect the row's real final status (or
give `resume_interrupted_workers_tick()` a way to observe the later
dispatch-stage rejection), so the just-merged PR #335 bounded-retry ledger
can actually observe and bound this specific recurring burst." Real tests
+ independent audit required, same as this task.
