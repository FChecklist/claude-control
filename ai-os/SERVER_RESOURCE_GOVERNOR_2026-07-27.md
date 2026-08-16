# SERVER RESOURCE GOVERNOR (2026-07-27)

Owner directive, 2026-07-27. Built as a direct, evidenced response to a real
incident found and fixed the same day: `veridian-task-watchdog.timer` ran
unstopped for 9h18m, firing every 60s with no "is a worker already active for
this issue" check, spawning duplicate recovery/escalation actions for the same
stalled task and driving load average to 32 on this 8-core box. The timer is
now stopped and disabled and stays that way -- this document and the code it
describes is what makes that failure mode structurally impossible the next
time any trigger (cron, systemd timer, systemd worker spawn) is re-enabled.

## The real root cause, precisely

`scripts/dispatch_core.py` (PR #101) already closed the *count*-based half of
this problem: every consolidated tick script shares one flock
(`acquire_dispatch_lock()`) and one concurrency cap
(`CONCURRENCY_CAP=5`, `has_free_slot()`/`running_worker_count()`) across both
`veridian-worker@*` and `veridian-supervisor@*` units. That is real and it
works, but it has two gaps this task closes:

1. **No identity check.** A trigger that fires every 60s and completes in
   under 60s can spawn an unbounded number of *sequential* duplicates without
   the concurrent-unit count ever exceeding the cap. The watchdog incident was
   exactly this: same `task_id`, same stall signature, re-evaluated and
   re-actioned every single tick because nothing recorded "this task_id
   already has an outstanding recovery/escalation in flight."
2. **No RAM/disk-I/O/network visibility.** The existing gate is an implicit
   CPU-adjacent proxy (unit count) plus systemd slice `CPUQuota`/`MemoryMax`
   ceilings set as a stopgap during the OOM incident earlier the same
   session. Nothing reads real `/proc` data and freezes dispatch on any one
   of the four resources actually being exhausted.

The Server Resource Governor (`scripts/resource_governor.py`) is a queue that
sits *in front of* `dispatch_core.py`, not a replacement for it. Every real
spawn still ultimately goes through `dispatch_core.acquire_dispatch_lock()` +
`has_free_slot()` + `systemctl --user start` -- unmodified. The governor adds:
a persistent submission queue with per-identity de-duplication, a real 4-metric
hard cap, priority tiers with anti-starvation aging, a stuck-task
SIGTERM/SIGKILL protocol, and an emergency fail-safe cascade.

## Architecture

```
trigger (tick script / systemd unit / supervisor-sweep discovery)
    |
    v
resource_governor.submit(task_spec, tier, source_trigger)
    |  dedup check: umr_tasks WHERE task_identity=? AND status IN
    |  (queued, dispatched, running)  -->  reject-and-log if found
    v
umr_tasks queue table (superboss-register.sqlite, part of the UMR schema)
    |
    v   (resource_governor --tick, invoked by a governor timer or any tick script)
scan_stuck_tasks()  -- SIGTERM/SIGKILL any governor-tracked running unit past
    |                  its timeout, using systemd's real ActiveEnterTimestamp
    v
sample_metrics()  -- real /proc reads: CPU (/proc/stat), RAM (/proc/meminfo),
    |                disk I/O (/proc/diskstats, delta rate), network
    |                (/proc/net/dev, delta rate)
    v
any metric >= 99%?  --yes--> freeze this tick (no dispatch), record an
    |                        emergency-cascade tick (see Section 7 below)
    no
    v
next_queued_task()  -- highest EFFECTIVE priority (tier + anti-starvation
    |                  aging), ties broken by submission time
    v
dispatch_core.acquire_dispatch_lock() + has_free_slot()
    |
    v
real systemctl --user start/restart <unit>  (or veridian-task.py create for a
                                              brand-new escalation task)
    |
    v
umr_tasks row updated (status, unit_name, ts_dispatched, metric_snapshot_json)
dispatch_core.record_dispatch_event(...)  -- unchanged, existing wiring_registry hook
```

## Priority tiers (0 = highest, 4 = lowest)

| Tier | Name | Rationale | Mapped trigger sources |
|---|---|---|---|
| 0 | EMERGENCY / OWNER-DIRECTED | Reserved headroom for a human- or incident-response-initiated `submit(..., tier=0)`. No automated trigger uses this tier today; it exists so a future direct Owner action is never queued behind routine cron noise. Still subject to the 4-metric freeze and the emergency hard-stop -- tier alone never bypasses a real resource limit. | (reserved, none yet) |
| 1 | ACTIVE WORK CONTINUATION | Keeps *already in-progress*, multi-phase tasks moving. Starving this tier stalls work that is already most of the way done, which is worse than delaying a brand-new dispatch. | `phase-continuation-tick.py` |
| 2 | STANDARD DISPATCH / RECOVERY | Fresh task dispatch from the gap/module queues, plus the watchdog's own known-fix auto-recovery actions (`restart_unit`, `reset_failed_and_start`) -- getting an already-stalled worker moving again is more urgent than routine maintenance, but not as urgent as continuing work already mid-flight. | `dispatch-tick.py`; `veridian-task-watchdog.service` FIX_ACTIONS |
| 3 | MAINTENANCE / REMEDIATION | Periodic housekeeping/reconciliation sweeps. A short delay never loses live progress. | `status-remediation-tick.py`; `supervisor-sweep.sh`'s discovery-triggered `veridian-supervisor@` starts |
| 4 | BACKGROUND / DIAGNOSTIC ESCALATION | Investigative work spawned *in response to* a stall already detected. By definition the stalled task itself isn't blocked further by queuing this behind everything else -- it's already stuck. This is also the literal call path that caused the 2026-07-27 incident, so it gets the most conservative tier and the strictest de-dup identity (`rca-<task_id>`, matching `escalate()`'s own title prefix). | `veridian-task-watchdog.service`'s `escalate()` (new `rca-` task creation) |

Every trigger above is mapped to a `source_trigger` string recorded on its
`umr_tasks` row, so `--query-umr` can answer "what has this trigger submitted"
without re-deriving it from logs.

## De-duplication (the specific fix for the watchdog incident)

`submit()` takes an explicit `task_identity` in `task_spec` (the real
target task/issue identity -- e.g. the stalled `task_id`, or `rca-<task_id>`
for an escalation). Before queuing anything, it checks `umr_tasks` for an
existing row with the same `task_identity` and `status IN (queued, dispatched,
running)`. If found, the new submission is **rejected and logged** -- a new
`umr_tasks` row is still written with `status='rejected_duplicate'` and a
`reason` explaining what it collided with, so nothing is silently dropped and
`--query-umr` can show the full rejected history. This is checked *inside*
`superboss-register.py`'s existing `_write_lock()` flock (the same
serialization primitive `dispatch_core.acquire_dispatch_lock()` mirrors), so
two racing submissions for the same identity cannot both pass the check --
closing the exact TOCTOU shape `dispatch_core.py`'s own docstring already
names as the root cause of its own concurrency race.

## Dynamic realignment (anti-starvation aging)

A queued item's *effective* priority is `max(0, tier - age_seconds //
AGING_PROMOTION_INTERVAL_SECONDS)` (default interval: 15 minutes). A tier-3
maintenance item queued for 45+ minutes behind a steady stream of tier-1/2
work is promoted to tier-2, then tier-1, etc., rather than starving forever.
Ties (same effective priority) break on submission timestamp (FIFO). This is
a pure function of `(tier, ts_submitted, now)` -- `next_queued_task()` takes
an injectable `now`, so it is testable without real clocks.

## Stuck-task protocol

`scan_stuck_tasks()` runs at the top of every governor tick:

1. For every `umr_tasks` row with `status='running'`, read the unit's real
   `ActiveEnterTimestamp` via `systemctl --user show <unit> -p
   ActiveEnterTimestamp --value` (never a self-tracked approximation -- the
   same source of truth `veridian-task-watchdog.py` already trusts for
   checkpoint staleness). If elapsed >= `STUCK_TASK_TIMEOUT_SECONDS` (default
   1 hour), send `SIGTERM` via `systemctl --user kill -s SIGTERM <unit>` and
   mark the row `sigterm_sent` with `ts_sigterm`.
2. For every row in `sigterm_sent`, if `now - ts_sigterm >=
   SIGTERM_TO_SIGKILL_GRACE_SECONDS` (default 60s), send `SIGKILL` and mark
   `killed`.

Both timeouts are env-overridable (`VERIDIAN_GOVERNOR_STUCK_TIMEOUT_S`,
`VERIDIAN_GOVERNOR_SIGKILL_GRACE_S`), and both steps take an injectable `now`
so the 60-second escalation window is directly testable without a real sleep.

## Emergency fail-safe cascade

`_record_emergency_tick()` keeps a per-metric consecutive-over-threshold
counter (`resource-governor-emergency-state.json`, reset to 0 the instant a
metric drops back under threshold):

- **Stage 1 -- freeze (every tick any metric is >= 99%):** that tick's
  dispatch is skipped entirely; already-running units are left alone.
- **Stage 2 -- shed load (a metric stays >= 99% for
  `EMERGENCY_CONSECUTIVE_TICKS_SHED`, default 3, consecutive ticks):** the
  governor `SIGTERM`s its own lowest-tier-priority currently-running tracked
  unit (freeing real resources instead of just refusing new work) and appends
  a CRITICAL entry to `ai-os/logs/ATTENTION.md`.
- **Stage 3 -- hard stop (still >= 99% for
  `EMERGENCY_CONSECUTIVE_TICKS_HARDSTOP`, default 6, consecutive ticks):** a
  sentinel file (`resource-governor-EMERGENCY_STOP`) is written; the governor
  refuses to dispatch *anything*, including tier 0, until an operator runs
  `python3 scripts/resource_governor.py --clear-emergency-stop`.

## Metric measurement

CPU and RAM have a natural 0-100% ceiling read directly from `/proc/stat`
(idle-time delta over a total-time delta between two ticks) and
`/proc/meminfo` (`1 - MemAvailable/MemTotal`). Disk I/O and network have no
such ceiling in `/proc/diskstats` / `/proc/net/dev` alone -- both are raw
cumulative counters -- so each is normalized against a configured per-box
capacity baseline (`VERIDIAN_GOVERNOR_DISK_CAPACITY_BPS`,
`VERIDIAN_GOVERNOR_NET_CAPACITY_BPS`; conservative placeholder defaults
documented in `resource_governor.py`, meant to be replaced with this box's own
measured baseline). All four are delta-based across governor ticks; the
previous raw sample is persisted to
`resource-governor-metric-state.json` so a single-shot tick invocation (cron,
not just a long-lived loop) can still compute a real rate. The very first tick
after cold start has no prior sample, so it seeds state and reports 0% for the
three delta-based metrics rather than freezing the queue on start-up noise.

## Universal Task Metadata Record (UMR)

`superboss-register.py` gains one new tree, `umr_tasks` (idempotent
`CREATE TABLE IF NOT EXISTS` + FTS5 index + triggers, migrated in via
`_ensure_umr_table()` called from `_migrate_schema()` -- same pattern PR #101
already established, and tested against a fixture DB seeded with the real
pre-existing schema, not a fresh one, per that PR's own postmortem): one row
per governor-submitted task, covering `task_identity`, `tier`, `status`,
`source_trigger`, `task_kind`, `unit_name`, `inputs_json`/`outputs_json`,
`logs_ref`, `metric_snapshot_json` (the real 4-metric reading captured at
dispatch time), and full lifecycle timestamps
(`ts_submitted`/`ts_dispatched`/`ts_sigterm`/`ts_completed`).
`resource_governor.py --query-umr [--limit N] [--status S] [--search TEXT]`
is the query CLI.

## Closing the incident concretely

`veridian-task-watchdog.py`'s three real spawn call sites --
`_fix_restart_unit`, `_fix_reset_failed_and_start`, and `escalate()`'s
`veridian-task.py create` + `systemctl start` -- now call
`resource_governor.submit()` instead of invoking `systemctl`/`veridian-task.py`
directly. `escalate()` submits with `task_identity=f"rca-{task_id}"` (tier 4);
the two FIX_ACTIONS submit with `task_identity=task_id` (tier 2). If the
`.timer` were re-enabled today and fired every 60s against the same
still-stalled task, the *second* and every subsequent tick's submission for
that identity would be rejected as a duplicate (logged, not silently dropped)
the instant the first submission's row is still `queued`/`dispatched`/
`running` -- the load-average-32 spiral cannot recur through this path.
`veridian-task-watchdog.service`'s `ExecStart` is otherwise unchanged (it
still runs the watchdog script directly); the `.timer` unit itself is left
exactly as found: stopped and disabled. Re-enabling it is a separate Owner
decision, out of scope here.
