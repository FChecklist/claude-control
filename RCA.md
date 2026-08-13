# RCA -- UMR-20260813-060311-6eea (status=killed, verified already correctly terminal)

## Governing chain
- This RCA task: `task-20260813-145737-rca--umr-20260813-060311-6eea-killed`,
  governing UMR `UMR-20260813-124141-7641` (PM-sentinel tick).
- Subject UMR: `UMR-20260813-060311-6eea`, dispatched
  `task-20260813-060321-real-tier-1-audit-of-pr--249---worker-ex` (Tier-1
  audit of `veridian-scripts` PR #249).
- This is at least the **2nd** RCA dispatch for this exact subject UMR. The
  1st, `task-20260813-093638-rca--umr-20260813-060311-6eea-killed`
  (governed by `UMR-20260813-091810-5045`), already did the real diagnostic
  work and corrected the subject row's `reason` -- but never committed its
  own `claude-control` artifact (no PROGRESS.md/RCA.md commit on its own
  branch), so `reconcile_stale_running_workers.py` later closed *that* task's
  own governing UMR as `completed_unmerged`, and a fresh PM-sentinel tick
  re-dispatched this task against the same subject row.

## Real recorded fact BEFORE this task (verified live, not trusted from the
briefing summary)
`resource_governor.py --query-umr --umr-id UMR-20260813-060311-6eea`:
- `status=killed`
- `ts_dispatched=2026-08-13T06:03:28Z`, `ts_completed=2026-08-13T09:43:03Z`
- `reason`: "RCA (UMR-20260813-091810-5045): real primary deliverable WAS
  produced -- Tier-1 audit comment posted on veridian-scripts PR #249 (id
  5276657173, 2026-08-13T06:15:24Z, verdict AUDIT:FAIL, cites this exact
  UMR). Only the secondary claude-control documentation-PR step failed (no
  commits between master and worker branch -- worker never committed
  PROGRESS.md). Row was mislabeled by reconcile_owner_dispatch_status.py
  PRE-FIX apply_correction() at 07:02:01Z (commit b13833a fixed
  ts_completed/reason backfill 9min later at 07:11:52Z but does not
  retroactively backfill already-killed rows). Remaining scope already
  carried forward independently under UMR-20260813-090037-9a34 ... not
  redispatched here, out of this UMR's scope. Correcting stale
  reason=queued/ts_completed=null to reflect real evidence; status remains
  killed (no claude-control artifact was ever produced by this dispatch)."

This reason is not a stale/mechanical kill message -- it is itself the
output of a real, independent, prior RCA (the 1st dispatch, above),
carrying real evidence (a specific GitHub comment id/timestamp/verdict) and
a real cross-reference to the row that carried the remaining scope forward.

## Independent re-verification of the two cross-referenced rows (not trusted
from the subject row's own reason text alone)

- `UMR-20260813-091810-5045` (the RCA that produced the correction above):
  `status=completed_unmerged`, `ts_completed=2026-08-13T10:56:40Z`, reason
  confirms `reconcile_stale_running_workers.py` found the RCA task's worker
  unit inactive with real completion candidates (git branch existed) but no
  merged PR for *that task's own* branch -- consistent with "did the real
  diagnostic work, never committed its own claude-control artifact."
- `UMR-20260813-090037-9a34` (the row the remaining scope was carried
  forward to): `status=completed`, `ts_completed=2026-08-13T14:54:00Z`,
  corrected by a separate, already-merged RCA
  (`task-20260813-145003-rca--umr-20260813-090037-9a34-killed`, PR #156,
  merged into this repo's `main` as `a94410e`, present in this task's own
  starting history). Real evidence: `veridian-scripts` PR #249 merged
  (`dbcb636`, `mergedAt=2026-08-13T10:39:54Z`) after an independent Tier-1
  `AUDIT:PASS` against commit `24a6f1f`.

Both cross-referenced rows check out. There is no dangling or contradicted
claim anywhere in the chain.

## Root cause

**No further gap exists on the subject UMR row itself.** `status=killed` is
the honest, correct terminal state: real substantive work happened (the
Tier-1 audit comment on PR #249, and -- via the row it cites -- the actual
PR #249 fix, audit, and merge), but the specific deliverable this dispatch's
own task was scoped to produce (a `claude-control` documentation commit on
its own auto-provisioned branch) never happened, and that is exactly what
`killed` + this reason correctly records.

The real, structural root cause is a **redispatch loop**, the same pattern
already independently diagnosed and partially fixed elsewhere in this
governing chain (see `RCA_20260813_stop_routing_killed_task_rca_through_
quality_gate.md`'s "same UMR row already RCA'd in memory" finding, and
`eb50a21`/`037908b`'s fixes for `UMR-20260813-115911-df5c`'s own redispatch
loop): a PM-sentinel tick dispatches an RCA task against a `status=killed`
row; the dispatched worker does real, correct diagnostic work and even
corrects the row's `reason` in place via `mark-umr-terminal`/direct write,
but if *that worker's own* `claude-control` branch never gets a committed
PROGRESS.md/PR, its own governing UMR closes as `completed_unmerged`
(not `completed`) once reconciled -- and nothing in the dispatch-time gate
checks "does this killed row's own `reason` already cite a completed prior
RCA" before queuing another one. The 1st dispatch
(`task-20260813-093638`, UMR-091810-5045) hit exactly this: real work,
no committed artifact, so this 2nd dispatch was queued.

This task closes the loop for real: it commits a real `claude-control`
artifact (this file + PROGRESS.md) on its own branch, so its own governing
UMR (`UMR-20260813-124141-7641`) can close as `completed`, not
`completed_unmerged` -- breaking the specific mechanism that caused the
redispatch.

## Action taken

No fix to the subject row (`UMR-20260813-060311-6eea`) or its two
cross-referenced rows was needed -- all three are already correctly,
honestly terminal with real evidence. No remaining scope to redispatch:
the only open thread (`veridian-scripts` PR #249's successor work) is
already tracked independently under `UMR-20260813-090037-9a34`, itself
already closed `completed`.

This task's own real deliverable is this documentation commit, closing
the artifact gap that caused the prior redispatch.

## Structural gap flagged for Owner/PM visibility (NOT fixed here -- out of
this RCA task's own narrow scope)

The dispatch-time gate that queues RCA tasks against `status=killed` rows
has no check for "does this row's own `reason` already cite a completed
prior RCA UMR." Without that check, any `killed` row whose correcting RCA
task itself failed to commit a `claude-control` artifact (a real, recurring
failure mode -- see `UMR-20260813-091810-5045` here, and the 3 cases in
`RCA_20260813_stop_routing_killed_task_rca_through_quality_gate.md`) will
keep being redispatched indefinitely, each new dispatch re-deriving the
same already-correct conclusion at real token cost. A real fix would have
the PM-sentinel tick's own dispatch-time gate parse the target row's
`reason` for an `RCA (UMR-...)` citation and skip redispatch when that
cited UMR is itself already terminal with a real correction -- not
implemented here (would require identifying and safely editing the
PM-sentinel tick's own dispatch-candidate-selection code, a wider blast
radius than this RCA's own scope).
