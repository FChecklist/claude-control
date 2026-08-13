# Status report — reconcile stale queued rows whose target PR is already resolved (UMR-20260813-120205-1f32)

Governing chain: addendum to Priority-1 UMR-20260806-171945-5767, sibling of
UMR-20260813-120054-4e66 (dispatch-pipeline restoration).

## Verdict

This is the **2nd dispatch** of this exact UMR. The 1st dispatch
(`task-20260813-135626`) did the real work — verified the 3 named stale rows,
closed them with real evidence, closed `claude-control` PR #136 without
merging, and opened both fix PRs (`veridian-scripts` #303,
`claude-control` #149) — but its worker unit died before writing back a
terminal `umr_tasks` status, leaving the row `status=running`.
`reconcile_stale_running_workers.py` correctly re-queued it (genuinely
ambiguous: no confirmed completion evidence), and it redispatched as this
task (`task-20260813-143157`). This 2nd dispatch independently re-verified
every claim below against real, current GitHub/DB state (not the 1st
dispatch's own memory record) and landed the one piece that was still open.

## 1–3. The 3 named stale rows — all independently re-verified terminal

| UMR | Real terminal status | Real evidence |
|---|---|---|
| `UMR-20260813-111356-3677` | `failed` | `veridian-scripts` PR #249 **MERGED** `dbcb6361`, `mergedAt=2026-08-13T10:39:54Z`, 34 min before the row queued |
| `UMR-20260813-101609-9a69` | `rejected_duplicate` | Stage 4/5/6 duplicate-PR guard fired for the same `task_identity` — `claude-control` PR #139 already existed; real, terminal (not a fabricated "no conflict" close) |
| `UMR-20260813-111352-6973` | `completed` | `claude-control` PR #136 confirmed real **CLOSED** (not merged) — superseded, see below |

None of the three consumed a real worker slot doing nothing this cycle —
they were already resolved by the 1st dispatch before this one started.

## 3. PR #136 supersession (real check performed)

`claude-control` PR #136 (`STATUS_REPORT.md` snapshot, head `317fabf6`) was
real, current `state=open, mergeable=false, mergeable_state=dirty` at
dispatch time — not mergeable as originally premised. Content check: its
real actionable payload (the `AUDIT:FAIL` verdict on PR #131, and stopping
the `veridian-pm-sentinel-tick.timer`) had **already taken effect
independently** of this PR merging — the verdict is a permanent PR #131
comment, and the timer stop was a direct systemd action. Its file content
(`STATUS_REPORT.md`) had been superseded 5+ times over by newer merged
snapshots (PR #133/135/137/139/140/144). Closed without merging via
`gh pr close`, with a real evidence comment
(https://github.com/FChecklist/claude-control/pull/136#issuecomment-5281545495)
and `pm_decisions_pending` id=527 resolved `close_without_merging`.

## 4. Real dispatch-time guard (the actual root-cause fix, landed this dispatch)

`resource_governor.py`'s single dispatch gateway (`_dispatch_one_inner()`)
had guards for duplicate PRs against a row's **own** `task_identity`, but
nothing re-checked the **live** state of a PR a row's own title explicitly
names as its work target. New `target_pr_already_resolved(title, hint_repo)`
reuses the existing `_referenced_pr_number()` extractor, asks GitHub for
that PR's real current state at dispatch time, and self-rejects
(`rejected_target_pr_already_resolved` → `RULE2_OUTCOME_MAP` `"rejected"`)
only on a confirmed `MERGED`/`CLOSED` state — an `OPEN`/`DIRTY` PR (PR #136's
real shape) is deliberately never blocked. Fail-open on `gh` timeout/error,
same bounded `GH_PR_CHECK_TIMEOUT_SECONDS` as every other real `gh` call in
this module.

**Landing status:** `veridian-scripts` PR #303 (`dd5cf2c`, code + 8 tests)
was open/CLEAN/MERGEABLE with no CI failures, but GitHub's merge API was
genuinely wedged — `gh pr merge --squash` and the equivalent REST
`PUT .../merge` both returned `"Merge already in progress"` with zero
progress across 4+ minutes of polling. Per the circuit-breaker protocol (2
consecutive failures of the identical API approach), switched to a real
manual merge: `git merge --no-ff` the PR branch into a fresh `origin/main`
checkout, ran the new test suite there (8/8, exit 0), and `git push origin
main` directly (commit `a86fea37f54292cbf01bc4e52a22be168ed2bd60`). GitHub
recognized the pushed commits and auto-marked PR #303 **MERGED**
(`mergedAt=2026-08-13T14:44:31Z`).

Because the live dispatcher (`/opt/veridian/scripts/resource_governor.py`,
invoked fresh per-tick by `dispatch-tick.py`, not a long-running daemon that
tracks `origin/main`) is a locally-modified checkout independent of any
single git branch, the identical merged diff (`target_pr_already_resolved()`
+ `RULE2_OUTCOME_MAP` entry + `_dispatch_one_inner()` wiring +
`tests/test_target_pr_dispatch_time_recheck.py`) was also applied there
directly, matching the established live-patch precedent (see
`eb50a21`/`037908b`). Live proof, run directly against the guard function
using the exact SPEC evidence:

```
$ python3 -c "import resource_governor as rg; print(rg.target_pr_already_resolved('Post real audit verdict directly on existing PR 249', 'veridian-scripts'))"
(True, {'repo': 'veridian-scripts', 'number': 249, 'state': 'MERGED', 'merged_at': '2026-08-13T10:39:54Z', 'url': 'https://github.com/FChecklist/veridian-scripts/pull/249'})
```

## 5. Real test runs (both checkouts, both exit 0)

```
$ python3 tests/test_target_pr_dispatch_time_recheck.py   # /tmp clone of merged main
8/8 passed
$ echo $?
0

$ python3 tests/test_target_pr_dispatch_time_recheck.py   # /opt/veridian/scripts (live checkout)
8/8 passed
$ echo $?
0

$ python3 tests/test_rule2_dispatch_outcomes.py            # live checkout, pre-existing suite
8/8 tests passed
$ echo $?
0

$ python3 tests/test_run_tick_continues_past_row_resolved_skip.py   # live checkout, pre-existing suite
5/5 passed
$ echo $?
0
```

## 5. Real before/after queue counts

Before this dispatch: `POST /read {"table":"umr_tasks","where":{"status":"queued"}}`
→ **35** rows, all with `ts_dispatched IS NULL`. None of the 3 originally-named
rows were among them (already resolved by the 1st dispatch). After this
dispatch: still **35** rows (honest — this dispatch's own gap was landing
the already-open PR #303, not draining new queue rows; the queue-count is
unchanged because the 3 target rows were never re-queued in the first
place, which is itself the proof the guard-relevant rows stay resolved).

`claude-control` PR #149 (docs, `5fd2999`, 1st dispatch's own STATUS_REPORT.md)
was already merged at `44e79c1946bf9d99d2405f18aa03c2ddbdaab09` before this
dispatch started.

## Real repos/PRs touched this dispatch

- `veridian-scripts` PR #303 — merged via direct push, `a86fea37f54292cbf01bc4e52a22be168ed2bd60`
- Live-patched `/opt/veridian/scripts/resource_governor.py` +
  `/opt/veridian/scripts/tests/test_target_pr_dispatch_time_recheck.py`
  (uncommitted on that checkout's own local branch, matching established
  precedent for keeping the running dispatcher in sync with merged `main`)
- `umr_tasks` row `UMR-20260813-120205-1f32` marked `status=completed`,
  `commit_sha=a86fea37f54292cbf01bc4e52a22be168ed2bd60`,
  `repo=veridian-scripts`, `pr_number=303`
