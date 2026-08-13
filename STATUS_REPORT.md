# Status report — UMR-20260813-042145-7cc0 (addendum to P1 UMR-20260806-171945-5767)

Real findings only. No fabricated certification language. Evidence for every claim
below was gathered live against the real DB/systemd/git/journalctl state on
2026-08-13 (~04:20-04:40 UTC), not assumed from the dispatch prompt.

## Finding 1 — `--query-umr --umr-id X` fix: DONE

Real root cause confirmed in `/opt/veridian/scripts/resource_governor.py` /
`superboss-register.py`: the CLI parsed `--umr-id` into `args.umr_id` but never
passed it into `query_umr_tasks()`, which had no `umr_id` parameter at all — any
`--umr-id` call silently fell through to the plain-listing branch (`ORDER BY
ts_submitted DESC`) and returned the newest row regardless of X.

Fix: `query_umr_tasks()` gained a real `umr_id` kwarg (exact match on the real
PRIMARY KEY, first-priority branch), and `resource_governor.py`'s `--query-umr`
handler now threads `umr_id=args.umr_id` through.

Regression test: `tests/test_query_umr_by_id.py` (3 tests) — seeds 3 rows sharing
status/tier where the requested row is deliberately NOT the newest, proves
`--umr-id X` returns exactly that row both via `query_umr_tasks()` directly and
via the real CLI subprocess, and proves an unknown id returns `[]`. Confirmed this
test **fails** (returns the newest row, count=3) against the pre-fix code and
**passes** against the fix (`3 passed in 1.12s`).

Shipped as **[veridian-scripts PR #289](https://github.com/FChecklist/veridian-scripts/pull/289)**
(branch `worker/task-20260813-042207-fix-umr-id-filter---audit-failed-supervi`,
commit `90df8f6`) — not yet merged as of this report. Fix is already live at
`/opt/veridian/scripts/` (used to dogfood the P2/3/P4/parallel-mandate queries
below).

## Finding 2 — both failed `veridian-supervisor@...` audits: diagnosed, NOT certified

Both `veridian-supervisor@task-20260813-034138-...` (UMR-45c0) and
`veridian-supervisor@task-20260813-035740-...` (UMR-1d97) really were
`failed`/`failed`. Real root cause (from `journalctl --user` +
`supervisor-systemd.log`, not assumed): **neither worker ever created or pushed
its designated `worker/task-*` branch** —

```
fatal: couldn't find remote ref worker/task-20260813-034138-token-efficiency-external-memory-system
fatal: couldn't find remote ref worker/task-20260813-035740-boss-worker-model-tier-orchestration--ad
```

confirmed independently: both workspaces' `git status` is clean, `HEAD` is still
at the shared master tip (`067eafe`), and `git ls-remote --heads origin` on
`claude-control` has no matching ref for either branch. The real file evidence
(`state.json`, `sources/`, `dead_ends.json`, `open_questions.json`,
`decision_contracts/`, `CLAUDE_MEMORY_INDEX.md`, `BOSS_WORKER_DISPATCH_TIER_NOTE.md`)
is genuinely real, but lives at `/opt/veridian/ai-os/memory/` — outside any
git-tracked repo — so there was nothing for the supervisor to `git fetch`/diff.
`supervisor-entrypoint.sh` correctly continues past the fetch failure (no `-e`),
computes an empty diff against master, and a **real Superboss review did run**
against that empty diff plus each worker's own checkpoint notes — both
`review.json` files already existed with genuine verdicts:

- **UMR-45c0 (token-efficiency memory system): verdict = `reject`.** Real reason
  (Superboss's own words): the deliverable was "written directly onto the
  filesystem in a completely different repo... that this task was never given an
  isolated worktree/branch for... sits as untracked ('??') files in the live
  ai-os checkout, which is currently mid-cherry-pick... Nothing was committed and
  no PR was opened." Content quality itself was called out as good/honest; the
  reject is entirely about the missing audit trail.
- **UMR-1d97 (boss/worker tiering note): verdict = `approve`.** Real reason: it
  was genuinely a zero-diff investigation task (grep-verified no haiku tiering
  exists anywhere in the live pipeline) and correctly avoided building
  unrequested scaffolding — but the systemd unit still failed afterward because
  the post-review step ("could not resolve a real PR for branch ... `gh pr
  create` failed, no existing open PR found") correctly refuses to guess an
  unrelated PR to merge into, since no branch/PR exists to attach the approval
  to.

**Rerun for real:** `systemctl --user reset-failed` + `start` on both units just
now. Both exited `inactive (dead)` (not `failed`) this time — because the
idempotency guard at the top of `supervisor-entrypoint.sh` (`if [ -f
"$TASK_DIR/review.json" ]` → skip) found the pre-existing `review.json` and
exited 0 without re-reviewing. **Real PASS/FAIL text as of this rerun: neither
task is PASS.** UMR-45c0 stays REJECT/blocked; UMR-1d97's real content is
APPROVE but is administratively stuck unmerged (no PR exists). Per the Owner's
zero-compromise-of-audit instruction, **neither UMR-45c0 nor UMR-1d97 is marked
complete/certified by this report.**

This is a genuine worker-phase gap (branch never pushed), not a bug in the
supervisor/audit script — the "refuse to guess a PR" behavior is itself a
previously-shipped real fix (documented in the script's own comments) working as
intended. The real remediation (recommended, **not executed** by this dispatch,
since it would mean committing on a different task's behalf and is a scope
decision, not a script bug): a small follow-up subtask that takes the
already-reviewed real content and lands it via a proper isolated worktree +
branch + real PR (for UMR-1d97, that PR would then auto-merge per its existing
`approve`/`tier1` verdict; for UMR-45c0, per its `reject` verdict, it would still
need the reviewer's issues addressed, not just a push).

## Finding 3 — 4 priority chains: root cause differs from the dispatch prompt's premise

The dispatch prompt's premise ("0 active worker units because dispatch-tick.py
has no active timer") is **stale**: `systemctl --user list-timers` shows
`veridian-cron-dispatch-tick.timer` **enabled and firing every ~10 minutes**
(last fired 2026-08-13T04:23:16Z, confirmed live). Some prior session already
fixed the missing-timer gap (matches real merged history, e.g.
`UMR-20260807-045110-6a56` "register real cron and systemd timer" — completed
2026-08-07).

The real reason all 4 chains show 0 active worker units right now:

| Chain | Real umr_id (verified via the now-fixed `--umr-id` / DB query) | Real current state |
|---|---|---|
| P1 | `UMR-20260806-171945-5767` | root row `status=completed`; its own closeout task (`task-20260809-004606-priority-1-final-point--close-umr171945`) is `status: blocked` |
| P2/3 | `UMR-20260808-175055-cebd` → really requeued as `UMR-20260808-185252-afba` (confirmed, not assumed) | `status: blocked`; unit `veridian-worker@task-20260808-175102-...` is `inactive (dead)`, not running |
| P4 | `UMR-20260808-183732-d3a3` | `status: blocked`; unit `veridian-worker@task-20260808-192224-...` is `inactive (dead)` |
| Parallel mandate | `UMR-20260808-183926-70b6` | `status: blocked`; unit `veridian-worker@task-20260808-192230-...` is `inactive (dead)` |

All 4 task.yaml files carry the **identical real blocking reason**, verbatim:

> credit accountant rejected auto-fix attempt 1, no further metered spend
> without human review: `{"approved": false, "increment_number": 1, "reason":
> "existing software/mechanism already covers this (system_index match) -- use
> it instead of spending AI credits", "reviewer": "deterministic"}`

This is a real, deliberate governance gate (`credit-accountant.py`), functionally
equivalent to the stop-work-order gate the dispatch explicitly told me to
respect. **No new dispatch was submitted for any of these 4 chains.** Doing so
would either hit the identical rejection again (wasted spend) or — worse —
would be fabricating an exemption to a human-review gate that is explicitly
still standing. This is a real, intentional decision not to duplicate/bypass
work, not an oversight.

(The umr_tasks DB rows for `70b6` and `d3a3` still say `status='running'` even
though their real systemd units are `inactive (dead)` — a separate, narrower
stale-status gap. `--reconcile-stale` found nothing (their `last_heartbeat` is
NULL, out of that sweep's reach); `--backfill-null-heartbeats` (dry run only)
would fix it but its blast radius is dozens of unrelated rows across the whole
system going back to 2026-08-01 — **explicitly out of scope for this dispatch**
and not run with `--execute`, since it is not narrowly scoped to just these 4
chains and touches many other in-flight efforts I have no context on.)

## Deliverable table

| Row | Status |
|---|---|
| P1 (UMR-20260806-171945-5767) | NOT-COMPLETE — root row completed, but real closeout task is blocked pending human credit-accountant review |
| P2/3 (UMR-20260808-175055-cebd → real id UMR-20260808-185252-afba) | NOT-COMPLETE — blocked pending human credit-accountant review; unit inactive, no duplicate dispatched |
| P4 (UMR-20260808-183732-d3a3) | NOT-COMPLETE — blocked pending human credit-accountant review; unit inactive, no duplicate dispatched |
| Parallel mandate (UMR-20260808-183926-70b6) | NOT-COMPLETE — blocked pending human credit-accountant review; unit inactive, no duplicate dispatched |
| UMR-20260813-034121-45c0 | NOT-COMPLETE — real Superboss verdict is REJECT (missing audit trail: no branch/PR); not certified |
| UMR-20260813-035737-1d97 | NOT-COMPLETE — real Superboss verdict is APPROVE but unmerged (no PR exists to merge); not certified |
| This dispatch (UMR-20260813-042145-7cc0) | `--umr-id` bug fixed + real regression test proving it, both directions verified; PR #289 open, not yet merged — **NOT-COMPLETE** until PR #289 merges |

No row above is marked COMPLETE-WITH-PASSING-AUDIT. This dispatch's own fix is
real and tested but is not itself "complete with passing audit" until PR #289
is reviewed/merged through the same real pipeline.
