# Status report — query-once-per-tick + decide-and-fix-not-decide-and-ask: real code already built, real gap found and fixed on its own PR

UMR chain: addendum to UMR-20260813-102459-10c3 (chain: 084321-2962 ->
102459-10c3 -> this addendum -> P1 UMR-20260806-171945-5767). Governing
UMR for this task: `UMR-20260813-105106-e9a7`.

## Verdict

**Both Owner directives were already built as real, runtime-enforced code
in `pm-sentinel-tick.sh` on `FChecklist/veridian-scripts#299` by a prior
invocation of this exact UMR** (that invocation's own worker unit went
`ActiveState=inactive` with an ambiguous `task.yaml` checkpoint, which is
why the platform re-queued this UMR as a fresh task — see
`resource_governor.py --query-umr --umr-id UMR-20260813-105106-e9a7`,
`reason` field). Independently re-verifying that PR from a **fresh clone**
(not this box's live checkout, not trusted from the prior self-report)
found one real, concrete gap — PR #299 was missing the two systemd unit
files its own script docstring assumes exist — which is fixed here, on
that same PR, with the fix pushed and PR #298 (the now-fully-superseded
predecessor) closed to keep exactly one live PR for this file.

## Part 1 — what was already real (independently re-verified, not trusted)

`FChecklist/veridian-scripts#299` (`pm-sentinel-tick.sh`, single squashed
commit `9e3469f`, base = current `main`, `mergeable=MERGEABLE`,
`mergeStateStatus=CLEAN`) contains both directives as real code, not
narration:

1. **QUERY ONCE PER TICK** — `get_umr_row()` / `cache_put_row()` /
   `already_queried_this_tick()`, a real **on-disk** per-tick cache
   (`CACHE_DIR="$(mktemp -d ...)"`, `trap 'rm -rf "$CACHE_DIR"' EXIT`) —
   deliberately not a bash associative array, because every call site
   invokes these functions via `$(...)` command substitution, which bash
   always forks a subshell for; an in-memory `declare -A` write there would
   be silently lost the instant the subshell exits. The script's own header
   comment documents this as a real bug the test itself caught during
   development. Every bulk listing query (killed-row scan, running-row
   cross-check, `completed_unmerged` PR audit) populates the same cache via
   `cache_put_row()`; every per-row loop calls
   `already_queried_this_tick()` first and skips a row a prior check this
   same tick already fetched+handled. `cached_gh_pr_view` does the same for
   `gh pr view` / `gh api .../comments` calls, keyed by `(repo, pr_number)`.
2. **DECIDE-AND-FIX, NOT DECIDE-AND-ASK** — every real gap-detection call
   site calls `record_finding()` immediately before `dispatch_gap()`
   (`FINDINGS_LOGGED`); `dispatch_gap()` — the one real gateway every
   finding must go through, itself calling `dispatch-owner-task.sh
   --no-relay`, the same single front door `resource_governor.py`'s
   tier/concurrency-cap/`EMERGENCY_STOP`/stop-work gate already sits behind
   — increments `FINDINGS_ACTIONED` on every one of its own real terminal
   outcomes (dispatched, dispatch attempted-but-failed, already in-flight,
   per-tick cap reached, genuine financial escalation). At tick end, if
   `FINDINGS_LOGGED != FINDINGS_ACTIONED` the tick fails loudly
   (`DECIDE-AND-FIX VIOLATION`, non-zero exit) instead of silently leaving a
   finding undecided.

Real test evidence, re-run independently in a throwaway clone
(`/tmp/vs-review`, not this box's live checkout) rather than trusted from
the prior invocation's own report:

```
$ python3 -m pytest test_pm_sentinel_tick.py -v
PmSentinelTickKilledRowTest::test_first_tick_dispatches_real_rca_for_seeded_killed_row PASSED
PmSentinelTickKilledRowTest::test_second_tick_does_not_duplicate_already_in_flight_dispatch PASSED
PmSentinelTickFinancialEscalationTest::test_financial_gap_escalates_to_owner_instead_of_dispatching PASSED
PmSentinelTickDispatchFailurePropagatesTest::test_real_dispatch_failure_makes_tick_exit_nonzero PASSED
PmSentinelTickQueryOncePerTickTest::test_same_row_queried_at_most_once_per_tick PASSED
PmSentinelTickDecideAndFixTest::test_every_finding_gets_a_same_tick_dispatch PASSED
6 passed in 291.89s
```

`PmSentinelTickQueryOncePerTickTest` seeds one real `umr_id` that is
*both* a tracked-chain head *and* `status='killed'` — the concrete overlap
case where, pre-addendum, Check 1 and Check 2a would each independently
issue their own real `resource_governor.py --query-umr --umr-id <same id>`
call for the identical row — and asserts, via a real logging shim that
execs the real `resource_governor.py` (so real tick behavior is completely
unchanged), that the id is queried exactly once. `PmSentinelTickDecideAndFixTest`
seeds two independent real gaps and asserts each gets its own real
`dispatch-owner-task.sh` call in the same tick, with
`FINDINGS_LOGGED`/`FINDINGS_ACTIONED` reconciling and no
`DECIDE-AND-FIX VIOLATION`.

## Part 2 — the real gap found on independent review, and the fix

`claude-control#143`'s own audit (posted 2026-08-13T13:08:44Z, before this
task's re-dispatch) correctly flagged that a documentation-only PR in this
repo cannot substitute for an independent review of the actual code in
`veridian-scripts#299`, and that #299 needed that review before merge. This
task supplies that review, in a fresh clone rather than the live checkout:

- `git diff main pr299 --stat` on a clean clone showed exactly two files:
  `pm-sentinel-tick.sh` (922 new lines) and `test_pm_sentinel_tick.py` (587
  new lines) — **no `systemd/` files**, even though the script's own header
  comment says it is "wired as a systemd --user timer (see
  `systemd/veridian-pm-sentinel-tick.service` + `.timer` in this same
  directory)". Those two files were real and already present on the prior,
  now-superseded `#298` (`git diff pr298 pr299 --stat` confirmed the delta),
  and already live+active on this box
  (`systemctl --user show veridian-pm-sentinel-tick.timer -p ActiveState`:
  `active`) — they were simply dropped when `#299`'s squash commit carried
  the script and tests forward from `#298` but not the systemd units.
- Fixed on `#299` itself (commit `5e3eeeb`, pushed to
  `worker/task-20260813-123933-add-query-once-decide-and-fix`): restored
  both files, verified **byte-identical** (`diff`, zero delta) to both
  `#298`'s versions and the live, active deployment — not new/invented
  content, real already-authored content this PR should have carried
  forward.
- Re-ran the full real test suite against the fixed branch: 6/6 pass
  (unchanged from Part 1 — the fix only added previously-missing files, it
  did not touch `pm-sentinel-tick.sh` or the tests).
- `#298` (`feat: collapse server-native PM sentinel + financial-escalation
  + hierarchy policy into ONE script (10c3)`) closed as superseded — `#299`
  is now a strict superset (script + tests + systemd units + the
  query-once/decide-and-fix addendum), so keeping both open would itself be
  the duplication this UMR chain's own zero-duplication rule forbids.
- `claude-control#143` (the doc-only status report this audit-failed)
  closed rather than rebased — its `STATUS_REPORT.md`-only branch had
  diverged through five more merges to `master` since it was cut
  (`#144`/`#145`/`#148`), and this report supersedes it directly rather
  than mechanically replaying a stale rebase.

Not done here, out of this task's own scope: actually merging `#299` into
`veridian-scripts:main` — this platform's own convention is that workers
open PRs and a separate audit/merge step lands them (see `dispatch-tick`'s
own `completed_unmerged` PR-audit path, which `pm-sentinel-tick.sh` itself
reuses rather than reimplements); `#299` is now real, tested, and
`mergeable=CLEAN` and ready for that step.

## Completed

- [x] Independently re-verified (fresh clone, not the live checkout or the
      prior invocation's self-report) that both Owner directives
      (query-once-per-tick, decide-and-fix-not-decide-and-ask) are real,
      runtime-enforced code in `pm-sentinel-tick.sh` on
      `veridian-scripts#299`.
- [x] Independently re-ran the full real test suite (6/6 pass), including
      the two tests specific to this addendum
      (`PmSentinelTickQueryOncePerTickTest`,
      `PmSentinelTickDecideAndFixTest`).
- [x] Found a real gap on independent review: `#299` was missing the
      systemd unit files its own script assumes exist.
- [x] Fixed the gap on `#299` itself (commit `5e3eeeb`), byte-identical to
      the already-live deployment; re-verified 6/6 tests still pass.
- [x] Closed `#298` as superseded (now redundant with the fixed `#299`).
- [x] Closed `#143` (stale, audit-failed, superseded by this report).

## Remaining

- [ ] `veridian-scripts#299` itself still needs the platform's own
      independent merge/audit step (out of a worker's own authority —
      workers do not merge/push-main on this platform) before it lands on
      `main`.
