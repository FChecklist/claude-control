# STATUS REPORT -- UMR-20260813-102459-10c3 (addendum to UMR-20260813-084321-2962)

Integrates UMR-20260813-084321-2962 + UMR-20260813-091633-8b6a +
UMR-20260813-092654-326b into ONE file: `pm-sentinel-tick.sh` (real,
deterministic, boolean, logical -- zero LLM calls in the tick path).

## Repo-boundary correction (real finding, this invocation)

The code was originally built, tested, and committed inside THIS repo
(`claude-control`, commit `bb3fee7`). That is wrong: `claude-control`'s
`scripts/` directory has been retired since 2026-08-01 (its own
`scripts/README-RETIRED.md`) -- the exact same repo-boundary mistake
already on record as PR #131's root cause in this chain's history, and
independently rediscovered the same day by a sibling addendum task
(target-identifier dedup, landed in veridian-scripts#297). The retirement
note is explicit: "Do not add or edit files here for anything meant to run
on the server. Use FChecklist/veridian-scripts instead."

**Also found live during this correction:** a separate, currently-running
task (`UMR-20260813-105106-e9a7`, "query-once-per-tick + decide-and-fix",
its own addendum to this same 10c3 chain, dispatched to
`task-20260813-123933`) is live-editing the same
`/opt/veridian/scripts/pm-sentinel-tick.sh` working copy this integration
had deployed to. To avoid clobbering that task's in-progress,
uncommitted, unverified work, this fix did **not** touch the live working
tree at all -- it built the corrected commit from a fresh scratch clone of
`veridian-scripts` instead, using the exact byte-identical, already-tested
(`bb3fee7`) script/test content as the source of truth, rebased onto
current `veridian-scripts` `main`.

**Real fix landed:** [`FChecklist/veridian-scripts#298`](https://github.com/FChecklist/veridian-scripts/pull/298)
(open, not merged -- workers never merge/push-main). Builds on top of the
pre-existing open PR #292 (`2fcd274` base sentinel + `ff328e7` financial
escalation, both already real commits on that branch, never before
combined with the 326b/bd10 scope). #292 closed as superseded by #298
(comment + close posted, both real `gh` calls, see
`gh pr view 292/298 --repo FChecklist/veridian-scripts`).

`claude-control`'s own `bb3fee7`/`9deb568` commits (this repo's local
history only, never pushed to `origin`) are superseded by this correction
and are **not** part of the delivered fix -- `scripts/pm-sentinel-tick.sh`
et al. do not belong in this repo and are not being pushed here.

## Output contract (boolean table, one row -- this integration itself)

| FOUND | 100% COMPLETED W/ GAP ANALYSIS + REAL IMPLEMENTATION | TESTED | AUDITED WITH ARTIFACTS | INTEGRATED | WORKING | CERTIFIED |
|---|---|---|---|---|---|---|
| YES (all 3 source UMRs' real state independently re-queried, see PROGRESS.md; real repo-boundary mistake found and corrected this invocation) | YES (all 5 real bd10 audit-reject issues fixed + 1 newly-found 6th issue fixed; 8b6a financial-escalation code recovered from live-only and committed; 326b scope added with an honest "not applicable" for the blocked-status point; real fix now lands in the correct repo, veridian-scripts#298) | YES (4/4 real tests pass, 189.6s real run against an isolated sqlite COPY, evidence in PROGRESS.md; content re-verified byte-identical + `bash -n`/`py_compile` clean after rebase onto current veridian-scripts `main`) | PARTIAL -- self-audited with real artifacts (test run, live tick run, systemd Result=success, real PR #298) cited above; **no independent Tier-1 reviewer has re-audited PR #298 yet** (same discipline as every other UMR in this chain: never self-certify past what is independently verified) | YES (deployed to live `/opt/veridian/scripts/` prior to this correction; `veridian-pm-sentinel-tick.timer` enabled+active; real fix now also correctly version-controlled via veridian-scripts#298, not this retired repo) | YES (real `systemctl --user start` proof run: Result=success, 5 real RCA UMRs dispatched, capped correctly, metrics+report files written) | **NO** -- CERTIFIED requires all columns YES; AUDITED_WITH_ARTIFACTS is not yet independently confirmed, so this row is not self-certified as CERTIFIED |

See PROGRESS.md for the full real-findings table (per sibling UMR),
tool-verification table (per named reusable tool, FOUND/NOT FOUND with real
evidence), and the real before/after token-usage table.

## Real dispatches this integration's own live proof-run caused
`systemctl --user start veridian-pm-sentinel-tick.service` against the real
production DB (not a test copy) found real gaps and dispatched, through the
existing `dispatch-owner-task.sh --no-relay` front door only, exactly 5 new
real RCA UMRs (cap correctly enforced): UMR-20260813-124020-8a97,
UMR-20260813-124024-e68a, UMR-20260813-124028-1f69,
UMR-20260813-124033-1ac8, UMR-20260813-124037-f8c3 -- targeting real killed
rows including UMR-20260813-092654-326b itself. This is disclosed, not
hidden: it is the real, intended behavior of a now-working sentinel, bounded
by resource_governor.py's own pre-existing tier/concurrency-cap/stop-work
gate, same as every other real dispatch on this box.
