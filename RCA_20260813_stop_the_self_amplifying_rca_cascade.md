# RCA -- stop the self-amplifying RCA cascade

## Governing chain
Addendum to P1 `UMR-20260806-171945-5767`. ADJACENT BUT DISTINCT from
`UMR-20260813-115911-df5c` (owns routing killed-task RCA through the code
quality-gate auto-fix loop; real fix already merged, see
`RCA_20260813_stop_routing_killed_task_rca_through_quality_gate.md` in this
same repo -- `veridian-scripts` PR #305). This task owns RCA *generation*:
the automated killed-row RCA path itself emitting duplicate and recursive
RCA tasks.

## A. Real code path found
`veridian-scripts` repo, `pm-sentinel-tick.sh` (server-native PM sentinel,
systemd `--user` timer, hourly). Three checks all funnel through the same
single gateway, `dispatch_gap()`, with `TARGET_KEY="rca:${umr_id}"`:
- Check 1 (tracked-chain head killed)
- Check 2a (system-wide `--status killed --limit 15` scan)
- Check 2b (running row whose real unit is actually dead -- exit
  write-back-bug cross-check)

## Real evidence gathered (2026-08-13, real `--query-umr` pass)

### Confirmed exact duplicate
- `UMR-20260813-091810-5045` -- "RCA: UMR-20260813-060311-6eea killed",
  dispatched 09:36:42, **completed_unmerged**.
- `UMR-20260813-124141-7641` -- same exact title, submitted 12:41:41
  (~3h15m later).

Root cause, confirmed by reading `UMR-20260813-060311-6eea`'s own real
`reason` field live (not assumed): the RCA (5045) genuinely finished --
*"real primary deliverable WAS produced -- Tier-1 audit comment posted on
veridian-scripts PR #249 ... Row was mislabeled by
reconcile_owner_dispatch..."* -- but **6eea itself was never moved off
`status=killed`** (a separate, real bug in that reconciliation path, out of
this task's scope to fix). Because `is_in_flight()` in `pm-sentinel-tick.sh`
only ever checks its own per-tick `STATE_FILE` for a prior dispatch still
`queued`/`dispatched`/`running`, once 5045 itself reached a real terminal
status (`completed_unmerged`), 6eea was no longer "in flight" by that narrow
definition. Every subsequent tick that saw `UMR-20260813-060311-6eea`
resurface in Check 2a's `--status killed` listing (which it will,
permanently, until something else moves it off `status=killed`) had nothing
stopping it from dispatching a fresh, wasted duplicate RCA -- which is
exactly what happened at 12:41:41.

### Confirmed real recursion (RCA-of-RCA)
- `UMR-20260813-131646-007b` -- "RCA: UMR-20260813-101802-3ad2 killed".
  `UMR-20260813-101802-3ad2` was ITSELF titled "RCA:
  UMR-20260808-110448-b85c killed" -- a second-generation RCA, dispatched
  with no depth tracking or limit anywhere.
- `UMR-20260813-141610-273a` -- "RCA: UMR-20260813-101750-c377 killed".
  `UMR-20260813-101750-c377` was itself "RCA: UMR-20260808-183732-d3a3
  killed" -- same shape.
- Spec's own cited examples (`f8c3`->`0faf`, `e68a`->`e8a1`, `1f69`->`326b`)
  independently confirmed live: all three targets are themselves RCA or
  amendment-chain tasks, not original work.

Check 2a treats every `status=killed` row identically regardless of whether
it is itself an RCA task, and nothing recorded how many RCA generations deep
a given lineage already was.

## B. Target-identifier dedup guard
`veridian-scripts` PR #297 ("deterministic target-identifier dedup check
for dispatch-owner-task.sh") was open and unmerged at the time this task
ran, adding exactly this class of check --
`extract_target_identifiers()`/`find_target_identifier_duplicate()` in
`superboss-register.py`, wired into `dispatch-owner-task.sh` as a new step
1b -- for a related but different real incident (duplicate dispatches
citing the same PR number). **Reused, not reimplemented**: this task's own
PR branches directly from PR #297's exact head commit (not `main`) and
extends those SAME two functions:
- a 4th identifier class, `umr:<UMR-ID>` (`_TARGET_ID_UMR_RE`), since none
  of PR #297's three original classes (PR#+repo, file path, script name)
  ever match a bare `UMR-YYYYMMDD-HHMMSS-xxxx` token;
- two new, backward-compatible parameters on
  `find_target_identifier_duplicate()`: `statuses` (PR #297's own
  dispatch-owner-task.sh call site keeps its original
  queued/running-only default; `pm-sentinel-tick.sh`'s new RCA guard passes
  `queued,dispatched,running,completed,completed_unmerged`, since 5045's own
  case -- an already-`completed_unmerged` prior RCA -- is exactly the real
  duplicate that needed catching) and `window_hours<=0` meaning no cutoff
  (a killed row can resurface far outside PR #297's 4h default, as 6eea's
  own ~3h15m case already nearly did).

Wired into `pm-sentinel-tick.sh`'s `dispatch_gap()`, gated on `target_key`
starting with `rca:` (Checks 1/2a/2b only -- Check 3's `prfix:`/`audit:`
targets have their own, different, already-correct re-dispatch semantics
and are untouched).

## C. Recursion/depth guard
Every RCA prompt dispatched for a killed row now carries a real,
machine-checkable `RCA_DEPTH:<n>` marker (`rca_next_depth()` in
`pm-sentinel-tick.sh`): `1` if the killed row being RCA'd is not itself an
RCA task, or `(that row's own carried depth) + 1` if it is (parsed back out
of that row's own prompt). `dispatch_gap()` refuses to dispatch once depth
exceeds `MAX_RCA_DEPTH` (default 3, `PM_SENTINEL_MAX_RCA_DEPTH` override)
and instead calls a new `escalate_rca_recursion_limit()`, which reuses the
exact same `notify-owner.py` front door `escalate_financial_decision()`
already uses (no second, competing notification mechanism) -- a real,
human-visible report, per spec, instead of emitting another task.

## D. Reconciling the 12:40:20-12:41:41 batch
The spec's original evidence (PM desktop sentinel, 12:47-13:01 UTC) found
all ten of these rows sitting `queued`. By the time this task ran (real
`--query-umr` re-check, several hours later), real independent worker
execution had already moved **9 of the 10** to a real terminal status on
their own (`completed`, `completed_unmerged`, or `failed`) -- nothing left
stuck to reconcile for those nine. Cross-checked each of the ten's own
target UMR id against every other row in the most recent 130 for a
pre-existing RCA (i.e. a genuine duplicate submitted *before* 12:40): only
one match found.

The 10th, `UMR-20260813-124141-7641` (target `UMR-20260813-060311-6eea`),
**is** a genuine content duplicate of the already-completed
`UMR-20260813-091810-5045` (see "confirmed exact duplicate" above) -- but at
the time of this reconciliation it was found real, live `status=running`
(unit `veridian-worker@task-20260813-145737-...`, dispatched only minutes
before this task's own evidence pass). Per spec ("do not close anything
representing real unfinished work"), it was **not** force-closed via
`mark-umr-terminal` -- forcibly terminating a real, actively-running
worker's row is a different, riskier action than reconciling a stuck queued
row, and the constraint is explicit. It was left to reach its own real
terminal status through the normal task lifecycle (its own dispatched
worker's instructions already require it to record a real, honest
`mark-umr-terminal` outcome on completion).

No rows were mass-deleted. No row representing real unfinished work was
closed.

## E. Live proof
The fix has not yet been deployed live (pending review/merge of PR #297 and
this task's own PR, both required together for `check-target-identifier-
duplicate` to be present in the live `superboss-register.py`). Proof is
therefore a real, isolated-DB regression test rather than a live
production re-run, using the exact same mechanism (`dispatch_gap()`'s new
guard, real `pm-sentinel-tick.sh` subprocess, real
`check-target-identifier-duplicate` CLI call) that will run live once
merged:

`test_pm_sentinel_tick.py::PmSentinelTickRcaTargetDedupTest::test_killed_row_with_existing_completed_rca_produces_zero_new_rows`
seeds an isolated DB copy with a killed row + an already-`completed_unmerged`
prior RCA for the same target (the exact 5045/6eea/7641 shape), captures the
real row-id set **before** running `pm-sentinel-tick.sh`, runs it for real,
and asserts the row-id set **after** is byte-identical -- zero new rows --
while the tick's own stdout shows the real skip:
```
RCA TARGET DEDUP: rca:<TARGET_UMR> already has an existing row <EXISTING_RCA_UMR> (status=completed_unmerged) targeting the same real identifier -- skipping duplicate RCA dispatch (real incident this closes: UMR-20260813-091810-5045/UMR-20260813-124141-7641)
0/5 new dispatches this tick
```
`PASSED` (3 new tests: dedup zero-new-rows, depth-increments-under-limit,
depth-refused-and-escalated-at-limit). Full existing suite re-run
alongside for regressions -- see PROGRESS.md for the real pass/fail count.

## Out of scope, left for the owner
- `UMR-20260813-060311-6eea` itself is still stuck at `status=killed` even
  though its real RCA is done -- the real bug in
  `reconcile_owner_dispatch` that mislabeled it. Not this task's scope
  (RCA *generation*, not the reconciliation path that leaves a row
  permanently killed).
- `UMR-20260813-124141-7641`'s own real terminal outcome, once its
  currently-running worker finishes.
- PR #297 itself still needs human/owner review and merge -- this PR is
  stacked on it and depends on it merging first.
