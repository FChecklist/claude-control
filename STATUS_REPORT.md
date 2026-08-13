# Status report — query-once-per-tick + decide-and-fix rules for the server-native PM

UMR chain: addendum to UMR-20260813-102459-10c3 (chain: 084321-2962 ->
102459-10c3 -> this addendum -> P1 UMR-20260806-171945-5767).

## Verdict

**Both branches of the SPEC's conditional were real.** UMR-20260813-102459-10c3's
own integrated tick logic had **not** been committed anywhere (confirmed:
zero commits/PRs across `veridian-scripts` or `claude-control` reference
`102459-10c3`, via `git log --all --oneline` grep of both repos and
`gh search prs`/`gh api search/commits`) — the same finding the prior
status report in this chain (target-identifier dedup) already made. But
real, substantial WIP for that exact integration already existed
**uncommitted** in the live `/opt/veridian/scripts` checkout on the box
(`pm-sentinel-tick.sh`, `test_pm_sentinel_tick.py`, on branch
`worker/task-20260813-091931-...`, itself PR #292's own branch) — a real
finding, not something I authored from scratch. Per the SPEC's own
instruction ("if 10c3's integrated tick logic has not been built yet, fold
both rules in as hard requirements of that build"), both Owner directives
were folded directly into that same build before landing it, rather than
committing 10c3 first and bolting the rules on as a separate follow-up.

**The real fix lands in `FChecklist/veridian-scripts`, not this repo** —
same repo-boundary discipline as the prior addendum in this chain:
`claude-control/scripts/` has been retired since 2026-08-01
(`scripts/README-RETIRED.md`) and `pm-sentinel-tick.sh` has never existed
there; it only ever lived in `veridian-scripts` / the live server checkout.

## Step 1 — real code added (`veridian-scripts` PR #299)

<https://github.com/FChecklist/veridian-scripts/pull/299> — branch
`worker/task-20260813-123933-add-query-once-decide-and-fix` off current
`origin/main` (41c3d02), landing `pm-sentinel-tick.sh` +
`test_pm_sentinel_tick.py` for the first time in git.

**(1) QUERY ONCE PER TICK.** A real, on-disk, per-tick cache
(`CACHE_DIR`, `mktemp -d` + `trap ... EXIT`):
- `get_umr_row()` / `cache_put_row()` / `already_queried_this_tick()` wrap
  every individual `resource_governor.py --query-umr --umr-id` lookup.
  Checks 2a/2b/3 each call `already_queried_this_tick()` first and skip
  re-fetching/re-deciding any `umr_id` Check 1 (tracked-chain head) already
  handled this same tick — the real, concrete case closed: a chain head
  that is *also* `status=killed` used to be independently re-fetched and
  re-decided by Check 2a's system-wide killed-row scan.
- Check 2b's exit-write-back-bug cross-check used to make **two** separate
  real `systemctl --user show` calls against the identical unit (one
  `-p ActiveState`, one `-p Result`) — collapsed into one real call with
  both `-p` flags.
- Check 3's PR audit now goes through `cached_gh_pr_view()` so two
  `completed_unmerged` rows citing the same real PR never trigger two real
  GitHub API calls for it in one tick.

**Real regression caught and fixed during this same work:** the first cut
of this cache used a bash `declare -A` associative array. It silently
never worked — bash forks a real subshell for every `$(function_call)`
command substitution, and an in-memory array write inside that subshell is
lost the instant the subshell exits. This was caught by the new query-once
test itself failing (the `QUERY-ONCE:` skip message never appeared), not
assumed correct — root-caused and fixed by switching to a real on-disk
cache directory, which survives subshells because a file write is a real
filesystem side effect. Re-ran the test after the fix: passes.

**(2) DECIDE-AND-FIX, NOT DECIDE-AND-ASK.** Real runtime bookkeeping, not
convention: every real gap-detection call site calls `record_finding()`
immediately before `dispatch_gap()` (`FINDINGS_LOGGED`); `dispatch_gap()`
itself — the one real gateway every finding must go through — increments
`FINDINGS_ACTIONED` on every one of its own real terminal outcomes
(dispatched, dispatch attempted-but-failed, already in-flight, per-tick cap
reached, or genuine financial escalation). At tick end, if
`FINDINGS_LOGGED != FINDINGS_ACTIONED` the tick fails loudly
(`DECIDE-AND-FIX VIOLATION`, non-zero exit) instead of silently leaving an
undecided finding — a real regression guard against a future
gap-detection branch being added without a matching `dispatch_gap()` call.

Both rules' own real counters are exposed as new Prometheus
textfile-collector gauges (`pm_sentinel_tick_findings_logged/actioned`,
`pm_sentinel_tick_query_cache_hits/misses`) alongside the pre-existing
dispatch/failure counters.

## Step 2 — real tests proving both rules (`test_pm_sentinel_tick.py`)

Real subprocess + real isolated sqlite3 backup-API copy of the live
Superboss Register DB, same convention as every other real test in this
repo:

- **`PmSentinelTickQueryOncePerTickTest`** — seeds one real `umr_id` that
  is *both* a tracked-chain head (`owner_priority_sequence`, `status=active`)
  *and* `status=killed` in `umr_tasks` — the real overlap case where, before
  this addendum, Check 1 and Check 2a would each independently query the
  identical row. Via a real logging shim (`os.execv` into the real
  `resource_governor.py`, so real tick behavior is unchanged) that records
  every real invocation's argv, proves `--umr-id <that id>` is issued
  **exactly once** this tick, exactly **one** real dispatch happens (not
  two), and Check 2a's own real stdout shows the `QUERY-ONCE:` skip
  message.
- **`PmSentinelTickDecideAndFixTest`** — seeds two real, independent,
  non-overlapping technical gaps (two distinct killed rows, neither a chain
  head) in one tick. Proves each real finding gets its own real dispatch
  through the same gateway (`dispatch-owner-task.sh`) **in that same tick
  run**, and the real `FINDINGS_LOGGED`/`FINDINGS_ACTIONED` counters
  reconcile (2 found, 2 actioned, no `DECIDE-AND-FIX VIOLATION`).
- All 4 pre-existing tests (first-tick dispatch, zero-duplication,
  financial escalation, dispatch-failure-propagates) still pass unchanged.

```
$ python3 -m pytest test_pm_sentinel_tick.py -v
PmSentinelTickKilledRowTest::test_first_tick_dispatches_real_rca_for_seeded_killed_row PASSED
PmSentinelTickKilledRowTest::test_second_tick_does_not_duplicate_already_in_flight_dispatch PASSED
PmSentinelTickFinancialEscalationTest::test_financial_gap_escalates_to_owner_instead_of_dispatching PASSED
PmSentinelTickDispatchFailurePropagatesTest::test_real_dispatch_failure_makes_tick_exit_nonzero PASSED
PmSentinelTickQueryOncePerTickTest::test_same_row_queried_at_most_once_per_tick PASSED
PmSentinelTickDecideAndFixTest::test_every_finding_gets_a_same_tick_dispatch PASSED
======================== 6 passed in 290.42s ========================
```

## Step 3 — live-box housekeeping

Restored `/opt/veridian/scripts` (the live git checkout PR #299's own work
was staged through, to reuse the pre-existing real WIP) to exactly the
branch and uncommitted state it was found in
(`worker/task-20260813-091931-...`, PR #292's own branch, unrelated
pre-existing untracked files left untouched) — this task's own commit only
exists on its own new branch/PR, not mixed into PR #292's unrelated scope.

## What was NOT done (explicitly out of scope / not this task's authority)

- Did not merge `veridian-scripts#299` — workers never merge/push-main,
  same standing rule this chain's prior status reports already document.
- Did not create the systemd `veridian-pm-sentinel-tick.service`/`.timer`
  unit files the script's own header comment (pre-existing, unchanged by
  this work) still describes as its wiring mechanism — PR #136's Tier-1
  audit already found and disabled a live, unmerged-branch-served instance
  of this timer; re-enabling it against a merged, audited copy is a real
  separate operational step, not this addendum's own scope.
- Did not touch PR #292 (financial-only escalation amendment, still open,
  unmerged) or its branch beyond restoring it to its pre-existing state.
