# Status report — stop routing killed-task RCA through code quality-gate auto-fix loop (UMR-20260813-115911-df5c)

Governing chain: addendum to Priority-1 UMR-20260806-171945-5767, affects
UMR-20260808-183732-d3a3 / UMR-20260808-175055-cebd / UMR-20260813-091314-ba01
RCA chains.

## Verdict

This is the **4th dispatch** of this exact UMR (task-20260813-132414 →
-135613 → -140326 (this task)). The SPEC's own premise — skip the code
quality-gate auto-fix loop entirely for `rca--umr-*-killed`-titled tasks —
was already investigated and correctly **rejected** by the 1st dispatch
(commit `037908b`, merged `claude-control` PR #145): all 3 named RCA tasks
have merged PRs touching real `compliance-tracker` source
(`src/app/api/...`, `src/lib/...`), not pure diagnosis docs, so a blanket
title-pattern exemption would have let real code changes skip lint/build
checks going forward. The real, narrower bug that dispatch actually fixed
(a fabricated "build" gate failure for directly-created tasks with no
`umr_tasks` row) is confirmed still live in `/opt/veridian/scripts/quality-gate.sh`.

The 2nd and 3rd dispatches (`-135613`, this task) both re-verified that fix
is intact and found **no new quality-gate-routing work to do** — but neither
one asked *why the same already-resolved UMR kept getting redispatched at
all*. That's the real, previously-undiagnosed bug this task closes.

## Why this UMR kept getting redispatched (the real, new finding)

`reconcile_stale_running_workers.py` (STEP 3, the sweep that reclaims a
`veridian-worker@<task_id>.service` unit gone inactive without writing a
terminal `umr_tasks` status) requeued this UMR's row **twice** for reasons
that had nothing to do with quality gates:

1. **Missing `claude-control` repo mapping.** `REPO_LOCAL_PATHS`
   (`reconcile_stale_running_workers.py`) and
   `DEFAULT_OCID_RESOLVER_REPO_LOCAL_PATHS` (`superboss-register.py`) had no
   entry for `claude-control` — the repo every one of this UMR's own tasks
   is dispatched against. Without a resolvable `repo_root`,
   `_real_branch_tip_sha()` / `_first_recent_commit_sha()` could never
   produce a completion candidate, so the sweep always fell through to
   "genuinely ambiguous — real re-queue", regardless of how much real,
   pushed, reviewed work the task had done. Confirmed live: before the fix,
   `_completion_candidates()` against task-20260813-135613's real task.yaml
   returned `[]`; the branch's real tip (`2d2b125...`) was fully resolvable
   via `git ls-remote` once the repo mapping existed.
2. **A real race** between `worker-entrypoint.sh` disabling
   `veridian-worker@<task_id>.service` (the expected, correct handoff the
   moment a task reaches `pending_review`) and
   `veridian-supervisor@<task_id>.service` finishing its real review.
   `ActiveState=inactive` on the WORKER unit alone is not evidence of a
   crash when the SUPERVISOR unit is still live. Confirmed live:
   task-20260813-135613's worker unit went inactive at
   `status=pending_review` while its supervisor was still reviewing PR #147
   (which the supervisor then correctly rejected seconds later as a stale
   duplicate of already-merged `037908b`) — the sweep ran in that exact
   window, found no repo mapping (bug 1), and requeued a task whose real
   review was already in flight, producing task-20260813-140326 (this task).

## Fix

`veridian-scripts` PR #304 (also applied directly to the live
`/opt/veridian/scripts/{reconcile_stale_running_workers.py,superboss-register.py}`,
same precedent as `037908b`):
- Added `"claude-control": "/opt/veridian/repos/claude-control"` to both
  repo-path dicts and to `MARK_TERMINAL_REPO_CHOICES`.
- Added a supervisor-liveness check: when `task.yaml` status is
  `pending_review`, the sweep now checks the paired
  `veridian-supervisor@<task_id>.service` unit's `ActiveState` first and
  skips (`not_settled`) if it's still live/transitional, before ever
  reaching the completion-candidate/requeue logic.

Both changes are additive only — no existing repo mapping, argparse choice,
or decision path changed for any other repo/status combination. Verified:
`python3 -m py_compile` on both files; a fresh `reconcile_stale_running_workers.py`
dry run against the live DB exits 0 with no new errors.

## Status of the 3 named RCA tasks (re-checked this task, unchanged)

None of the 3 is currently blocked by a quality-gate-routing issue — all
three moved past that class of failure once `037908b` landed. Their current
blockers are unrelated and, per this task's own SPEC scope (fix
routing/config, not force through individual task outcomes), correctly left
for human review / already resolved on their own:

| Task | Current state |
|---|---|
| `task-20260813-104656-rca--umr-20260808-183732-d3a3-killed` | `blocked`, but git log shows it is **already fully closed** (PR #1081 merged, commit `1a9dd759e`) — credit-accountant's latest rejection (increment 9) correctly says no new work is needed; this is a stuck-completed-task bookkeeping gap (worker keeps getting re-invoked against a done task), a separate issue from quality-gate routing, out of this task's scope. |
| `task-20260813-105054-rca--umr-20260808-175055-cebd-killed` | `blocked` — legitimate circuit-breaker hard stop (2 consecutive credit-accountant rejections) pending human review; real work (PR #1080 rebase/CI) is otherwise progressing normally per its own checkpoint history. |
| `task-20260813-105503-rca--umr-20260808-150937-43d0-killed` | `blocked` — same legitimate circuit-breaker hard stop pending human review. |

Forcing any of these 3 past their current blockers would mean overriding a
deliberate circuit breaker (the same one governing this very task's own
protocol) without new evidence that it's wrong to do so — not attempted.

## Real config/code changed

- `/opt/veridian/scripts/reconcile_stale_running_workers.py` — repo mapping
  + supervisor-liveness guard (applied live + `veridian-scripts` PR #304).
- `/opt/veridian/scripts/superboss-register.py` — repo mapping (applied live
  + `veridian-scripts` PR #304).
- Quality-gate routing itself (`/opt/veridian/scripts/quality-gate.sh`):
  unchanged this task — already correctly fixed by `037908b`, reconfirmed
  live, no blanket RCA-type exemption implemented (would have been wrong).
