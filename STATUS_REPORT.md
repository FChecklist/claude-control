# Status report — reconcile stale queued rows whose target PR is already resolved (UMR-20260813-135626)

Governing chain: addendum to Priority-1 UMR-20260806-171945-5767, sibling of
UMR-20260813-120054-4e66 (dispatch-pipeline restoration, dispatched the same
run).

## Verdict

All 3 named rows were **already terminal by the time this task started**
(raced closed by sibling tasks during the same dispatch-pipeline restoration
this task is a sibling of) — 2 of the 3 closures were already accurate and
needed no change; 1 had a stale, non-evidentiary reason string that this
task fixed. The **real, still-open gap** was structural, not row-specific:
the dispatch gateway (`resource_governor.py`'s `_dispatch_one_inner()`) had
no guard that re-checks a task's own named target PR at dispatch time — only
at queue time. That gap is now closed (`veridian-scripts` PR #303).

## Step 1 — real re-check of the 3 named rows against live GitHub state

| Row | Title names | Real GitHub state (re-verified this task) | Row status found |
|---|---|---|---|
| `UMR-20260813-111356-3677` | `veridian-scripts` PR #249 | **MERGED** `dbcb6361...`, `mergedAt=2026-08-13T10:39:54Z` (34 min before the row queued at 11:13:56) | `failed`, but reason was a stale mechanical `"queued"` placeholder — **fixed this task** |
| `UMR-20260813-101609-9a69` | `claude-control` PR #135 | **MERGED** `78e4ee1c...`, `mergedAt=2026-08-13T10:40:46Z` | `rejected_duplicate`, real reason cites PR #139 (already accurate) — **no change needed** |
| `UMR-20260813-111352-6973` | `claude-control` PR #136 | **OPEN**, `mergeable=false`, `mergeable_state=dirty`, head `317fabf6` unchanged | `completed`, real evidence = `STATUS_REPORT.md` merged via PR #144 (already accurate) — **no change needed** |

## Step 2 — fixed `UMR-20260813-111356-3677`'s reason

`mark-umr-terminal --umr-id UMR-20260813-111356-3677 --status failed
--pr-number 249 --repo veridian-scripts` with a real reason naming PR #249's
merge commit SHA and `mergedAt` timestamp (previously the row's `reason`
column was a leftover `"queued"` placeholder that named no real evidence at
all). Status kept as `failed` (its real terminal state, an honest record of
the mechanical dispatch failure that occurred) — not fabricated as
`completed`, since no real work was performed.

## Step 3 — PR #136 disposition (target premise dead, but real need re-checked)

Per this task's own SPEC: determined whether PR #136's content is superseded.
Its real payload is a Tier-1 `AUDIT:FAIL` verdict on `claude-control` PR #131
plus a live-timer stop/disable action. Both real consequences already
happened **independently of PR #136 merging**:

- `AUDIT:FAIL` already posted as a permanent PR #131 comment:
  https://github.com/FChecklist/claude-control/pull/131#issuecomment-5279274298
- PR #131 itself is real-verified `CLOSED` (`merged:false`,
  `closedAt=2026-08-13T12:43:01Z`) — the audit's real recommended outcome
  already took effect.
- The live timer (`veridian-pm-sentinel-tick.timer`) was already really
  stopped+disabled via `systemctl --user`, a real action independent of any
  merge.
- PR #136's only file (`STATUS_REPORT.md`) has since been superseded 5+
  times over by newer merged snapshots (#133/#135/#137/#139/#140/#144, this
  file).

**Verdict: superseded.** Closed PR #136 without merging (real evidence
comment: https://github.com/FChecklist/claude-control/pull/136#issuecomment-5281545495),
and resolved the open `pm_decisions_pending` row `id=527` with
`status=close_without_merging` (contra that row's own
`recommended_option=rebase_and_reaudit` — a rebase would only re-add
already-obsolete documentation for zero real remaining operational effect).

## Step 4 — real root-cause fix: dispatch-time target-PR-state guard

Added `target_pr_already_resolved()` to `resource_governor.py`
(`_dispatch_one_inner()`, the single real dispatch gateway) — self-rejects a
`veridian_task_create` row whose own title names a real target PR that
GitHub already reports `MERGED`/`CLOSED` at dispatch time, distinct from
(and running before) the existing Stage 4/5/6 duplicate-PR / OCID-evidence /
reuse-verdict guards, none of which re-check a *named target* PR's live
state. Deliberately does **not** block an `OPEN`/`DIRTY` PR (PR #136's real
shape) — the right answer there is a fresh rebase+re-audit dispatch, not a
self-reject.

`veridian-scripts` PR #303:
https://github.com/FChecklist/veridian-scripts/pull/303

```
$ python3 tests/test_target_pr_dispatch_time_recheck.py
PASS: test_no_pr_number_in_title_never_blocks
PASS: test_merged_target_pr_blocks_with_real_evidence
PASS: test_closed_unmerged_target_pr_blocks
PASS: test_open_dirty_target_pr_never_blocks
PASS: test_gh_timeout_fails_open
PASS: test_gh_error_fails_open_not_found_in_hint_repo
PASS: test_dispatch_one_end_to_end_rejects_row_whose_target_pr_already_merged
PASS: test_dispatch_one_end_to_end_dirty_open_pr_is_not_rejected_by_this_guard

8/8 passed
$ echo $?
0
```

Pre-existing suites re-run unaffected: `test_rule2_dispatch_outcomes.py`
(8/8), `test_run_tick_continues_past_row_resolved_skip.py` (5/5),
`test_resource_governor_stuck_task_scope.py`,
`test_reconcile_dispatched_dead_zone.py`,
`test_resume_interrupted_workers_no_duplicate_row.py` — all pass.

## Step 5 — before/after proof

Real `gh` state re-verified this task (all cross-checked via both
`gh pr view --json` and raw `gh api` REST):

```
PR #249 (veridian-scripts): state=MERGED, mergedAt=2026-08-13T10:39:54Z, mergeCommit=dbcb636116189850a6ba798fe700d4c080be1e9e
PR #135 (claude-control):   state=MERGED, mergedAt=2026-08-13T10:40:46Z, mergeCommit=78e4ee1c3456146712c32cb2dff539d66bb76b0a
PR #133 (claude-control):   state=MERGED, mergedAt=2026-08-13T10:38:16Z, mergeCommit=b6eacf2b926a0165307522efc05f05b6b5fbe666
PR #139 (claude-control):   state=MERGED, mergedAt=2026-08-13T10:54:06Z
PR #131 (claude-control):   state=CLOSED, merged=false, closedAt=2026-08-13T12:43:01Z
PR #136 (claude-control):   state=OPEN -> CLOSED (this task), mergeable=false, mergeable_state=dirty, head=317fabf6dab870c546fb7c2f411139d1f6ee60ca
```

`umr_tasks` (`ai-os/memory/superboss-register.sqlite`), the 3 named rows,
**before this task's own writes**: all 3 already terminal (raced closed by
sibling tasks) -- `rejected_duplicate` / `completed` / `failed`-with-stale-
reason. **After this task's writes**: same 3 statuses, but
`UMR-20260813-111356-3677`'s `reason` now names real evidence
(commit SHA + `mergedAt`) instead of a stale `"queued"` placeholder.

Real, live, currently-executing queue backlog (`status='queued' AND
ts_dispatched IS NULL`, i.e. the actual dispatch-eligible set — this is the
number the new guard in `veridian-scripts` PR #303 will apply to on every
future dispatch tick): **23 rows** as of this report, none of which are the
3 rows this task investigated (all 3 already resolved off the live queue by
the time this task started). This count moves continuously — the
dispatch-pipeline restoration this task is a sibling of is actively draining
and adding real rows concurrently with this task's own run, so it is not a
frozen before/after pair for the whole queue; the row-level before/after
above is the load-bearing evidence.

## Independent verification

- `gh pr view <N> --repo FChecklist/<repo> --json state,mergedAt,mergeStateStatus,mergeable,headRefOid,closedAt,url`
  and `gh api repos/FChecklist/<repo>/pulls/<N>` (raw REST, cross-checked)
  for PRs #131, #133, #135, #136, #139, #249.
- `python3 /opt/veridian/scripts/superboss-register.py mark-umr-terminal ...`
  real output JSON captured above (Step 2).
- `gh pr comment 136` / `gh pr close 136` real output URLs captured above
  (Step 3).
- `python3 /opt/veridian/scripts/superboss-register.py resolve-pm-decision-pending --id 527 ...`
  -> `{"id": 527, "resolved": true}`.
- `gh pr create --repo FChecklist/veridian-scripts ...` -> PR #303 (Step 4).
- Real sqlite queries (read-only, direct `sqlite3.connect` against
  `ai-os/memory/superboss-register.sqlite`, the same DB the gateway
  capability fronts) for the before/after counts in Step 5.
