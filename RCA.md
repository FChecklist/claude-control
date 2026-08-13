# RCA -- UMR-20260813-060311-6eea (status=killed) -- confirmed (at least) 4th duplicate RCA dispatch, no new gap

## Governing chain
This task's own dispatching UMR: `UMR-20260813-191700-ebe6` (PM-sentinel tick, per
this task's `agent_work_briefing.py assemble-briefing`). Target row under
investigation: `UMR-20260813-060311-6eea`.

## Live re-check (not trusted from the dispatching prompt's summary)

```
python3 scripts/resource_governor.py --query-umr --umr-id UMR-20260813-060311-6eea
```

still shows, right now:

- `status`: `killed`
- `ts_completed`: `2026-08-13T09:43:03.490472+00:00`
- `reason`: *"RCA (UMR-20260813-091810-5045): real primary deliverable WAS produced --
  Tier-1 audit comment posted on veridian-scripts PR #249 (id 5276657173,
  2026-08-13T06:15:24Z, verdict AUDIT:FAIL, cites this exact UMR). Only the secondary
  claude-control documentation-PR step failed (no commits between master and worker
  branch -- worker never committed PROGRESS.md). Row was mislabeled by
  reconcile_owner_dispatch_status.py PRE-FIX apply_correction() at 07:02:01Z (commit
  b13833a fixed ts_completed/reason backfill 9min later at 07:11:52Z but does not
  retroactively backfill already-killed rows). Remaining scope already carried forward
  independently under UMR-20260813-090037-9a34 (comment id 5278604501, new head
  24a6f1f, PR now OPEN/MERGEABLE awaiting a fresh audit) -- not redispatched here, out
  of this UMR's scope. Correcting stale reason=queued/ts_completed=null to reflect
  real evidence; status remains killed (no claude-control artifact was ever produced by
  this dispatch)."*

This is **byte-identical, zero drift**, to the state independently confirmed by the
prior RCA merged as commit `db9169d` ("real RCA for UMR-20260813-060311-6eea --
already correctly terminal, no gap", 15:03:41Z). `status=killed` here is the honest,
correct terminal state: the row's own required deliverable (this dispatch's own
`claude-control` artifact -- a `PROGRESS.md` commit) genuinely never happened (verified
again: the original worker branch has no commits ahead of master), even though a real,
valuable side-effect (the Tier-1 `AUDIT:FAIL` comment on `veridian-scripts` PR #249)
was produced and is independently verifiable on GitHub. `mark-umr-terminal`'s own
structured-evidence gate requires a citable commit/PR for `completed`/
`completed_unmerged`; none exists for *this* dispatch's own required artifact, so
`killed` is correct, not a mislabel.

Cross-checked the two rows this reason cites, again, live:
- `UMR-20260813-091810-5045` (1st RCA dispatch, 09:36:42Z): `status=completed_unmerged`,
  unchanged.
- `UMR-20260813-090037-9a34` (the row that carried the real remaining PR #249 scope
  forward): `status=completed`, unchanged.

Neither needs a `mark-umr-terminal` write. **No new gap exists on any of the three real
rows this reason touches.**

## Real root cause: this is (at least) the 4th wasted RCA dispatch against the same target

This exact target (`UMR-20260813-060311-6eea`) is the **canonical example already named
by name** in `RCA_20260813_stop_the_self_amplifying_rca_cascade.md` (this same repo,
merged earlier) as the row that will "resurface... permanently, until something else
moves it off `status=killed`". Confirmed dispatch history against this one target,
oldest to newest:

1. `UMR-20260813-091810-5045` -- 09:36:42Z (1st RCA; did the real diagnostic work,
   corrected the target row's `reason`/`ts_completed` in place).
2. `UMR-20260813-124141-7641` -- 12:41:41Z (2nd RCA, ~3h later; confirmed exact content
   duplicate by the cascade RCA; reached `completed_unmerged` on its own).
3. The RCA merged as commit `db9169d` -- ~15:03:41Z (3rd RCA; re-confirmed no gap,
   again).
4. **This task**, dispatched 19:24:52Z (4th RCA; re-confirms no gap, again) -- ~4h20m
   after the 3rd, ~10h after the 1st.

Root cause of *this* recurrence is unchanged from the cascade RCA's own finding:
`pm-sentinel-tick.sh`'s `dispatch_gap()` / `is_in_flight()` only guards a target still
`queued`/`dispatched`/`running` in its own per-tick state file. The moment each prior
RCA dispatch reaches a real terminal status, the target row is no longer "in flight" by
that narrow definition, and `UMR-20260813-060311-6eea` permanently keeps resurfacing in
Check 2a's `--status killed --limit 15` scan (it can never leave `status=killed` -- see
above -- so it always matches).

## Fix status, re-verified live (not assumed from the older RCA doc)

The systemic fix the cascade RCA designed (target-identifier dedup guard extended with
an `rca:<UMR-ID>` class + `RCA_DEPTH` recursion guard, `veridian-scripts` PR #297
stacked on PR #306) is **still not live**:

- PR #306 (the extension itself): `state=MERGED`, but merged into
  `worker/task-20260813-115828-add-target-identifier-dedup-check-to-ser` -- an
  intermediate worker branch, not `main`.
- PR #297 (base `main`, the one that actually ships the dedup guard to production):
  `state=OPEN`, `mergeStateStatus=DIRTY`, `mergeable=CONFLICTING`, live head
  `aa90652`.

So the guard that would stop this exact cascade has not reached `main`, confirming why
a 4th dispatch was still possible. This remains a real, unresolved, higher-blast-radius
fix (conflict resolution + merge of PR #297) that is **out of scope for this narrow
RCA task**, exactly as the three prior RCAs against this same target also correctly
deferred it. Flagging again, more urgently given the now-4-deep recurrence count, for
Owner/PM visibility.

## Resolution

- **No redispatch** of the real remaining PR #249 audit scope -- already carried
  forward and closed under `UMR-20260813-090037-9a34` (`status=completed`, confirmed
  live above), independently of this row.
- **No `mark-umr-terminal` write** against `UMR-20260813-060311-6eea`,
  `UMR-20260813-091810-5045`, or `UMR-20260813-090037-9a34` -- all three are already
  honest and terminal; a redundant write would carry zero new evidence.
- This task closes its own loop for real by **committing this artifact**, matching the
  fix the 3rd RCA (`db9169d`) applied for itself: the *only* way `status=killed` on
  this dispatch's own `claude-control` requirement stays honest is for this dispatch to
  actually produce its own required commit, which it now has.
- Escalation note (unchanged conclusion from RCA #3, now with one more data point):
  merging `veridian-scripts` PR #297 (resolving its live `DIRTY`/`CONFLICTING` state
  against current `main`) is the one real change that stops further wasted dispatches
  against this and any other resolved-but-still-`killed` row. Recommended as a
  standalone, focused follow-up task -- not attempted here (conflict resolution on a
  shared systemd-tick script is a materially larger blast radius than this RCA's own
  narrow scope).
