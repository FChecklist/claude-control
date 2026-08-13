# RCA -- stop routing killed-task RCA through the code quality-gate auto-fix loop

## Governing chain
Addendum to P1 `UMR-20260806-171945-5767`. Cited stuck tasks:
`task-20260813-104656-rca--umr-20260808-183732-d3a3-killed`,
`task-20260813-105054-rca--umr-20260808-175055-cebd-killed`,
`task-20260813-105503-rca--umr-20260808-150937-43d0-killed`.

This is (at least) the 3rd dispatch of a task with this exact title. Prior
dispatches: `task-20260813-132414` (merged PR #145 into claude-control,
real code fix shipped as `veridian-scripts` PR #301, still open/unmerged at
the time this task ran) and `task-20260813-140326` (merged PR #151). Their
own commits are the reason `/opt/veridian/scripts/quality-gate.sh` already
had `task-20260813-132414`'s fix applied live (an untracked-task build-lock
requeue bug) when this task started, even though that fix's real PR (#301)
had not yet merged to `main`.

## SPEC's claim vs. what was actually verified live
SPEC claimed: the credit accountant is correctly refusing wasted spend
because "these are RCA tasks for killed processes, not code/feature tasks,
so applying a code quality-gate auto-fix loop to them is misapplied
automation" -- and asked for a blanket skip keyed on the task title pattern
`rca--umr-*-killed`.

Verified directly against each of the 3 tasks' own `quality-gate-0.json`,
`worker.log`, and `git diff --name-only origin/main...HEAD` (not trusted
from the SPEC's summary):

- All 3 had a genuinely **docs-only diff** at the time this task ran
  (PROGRESS.md / `ai-os/*.yaml` / `ai-os/*.md` bookkeeping only -- confirmed
  file-by-file, zero `.ts/.tsx/.js/...` files).
- All 3 failed the `build` gate (`next build`, timeout after 900s under
  documented host build-lock contention -- see `quality-gate.sh`'s own
  `BUILD_LOCK_*` comments), not because of any real defect in their diff.
- All 3 then had their auto-fix proposal correctly rejected by
  `credit-accountant.py`, but the *stated reasons* were not "quality gate
  misapplied to RCA tasks" -- they were task-specific: "this RCA was already
  completed and closed" / "same UMR row already RCA'd in memory" / "$0 real
  spend with zero artifacts" / "prior increment already rejected -- hard
  stop". i.e. the accountant was independently also catching that these 3
  tasks had **nothing left to do**, on top of the build-gate false failure.
- Confirmed via `git log` on each task's own workspace branch that the real
  underlying diagnosis work was already done and merged **elsewhere**:
  d3a3 via `veridian-scripts` PRs #870/#873/#878, closed out by #1081;
  43d0 via `veridian-scripts` PR #296. What was stuck on these 3 branches
  was trivial bookkeeping close-out, not open diagnosis work.

So the SPEC's core factual claim ("misapplied quality gate is blocking real
diagnosis") was **half right**: the quality-gate misapplication was real and
worth fixing. Its framing that resuming these tasks would let them "finish
their real diagnosis" was **not** right -- there was no diagnosis left to
finish. Both are reported here rather than only the flattering half.

## Why a title-pattern skip was rejected
`task-20260813-132414`'s own prior RCA of these same 3 tasks already found,
at the time it ran, that they had real `src/app/api/...` / `src/lib/...`
compliance-tracker source changes -- not pure documentation. A blanket
`rca--umr-*-killed` title bypass would have been actively wrong at that
point (it would have let real code changes skip lint/build), and titles are
caller-supplied free text with no verification -- trusting them for a
security/quality gate is the same class of shortcut the SPEC's own premise
should not be taken on faith for.

## Real fix
`/opt/veridian/scripts/quality-gate.sh`: compute
`git diff --name-only origin/$DEFAULT_BRANCH...HEAD`; if zero changed paths
have a code-relevant extension (ts/tsx/js/jsx/mjs/cjs/vue/svelte/css/scss/
less/py/go/rs/java/rb/php/sql/sh/json), skip the node/python
lint/build/test gates entirely and record a `docs_only_skip` pass. Gated on
the actual diff content, not the task's title or type label -- applies to
any genuinely docs-only worker task, not just this one naming convention.

Shipped as `veridian-scripts` PR #305 (stacked on the still-open #301,
since the live file already carried that unrelated fix uncommitted; rebase
onto `main` once #301 merges).

## Live verification
- Dry run: `quality-gate.sh` invoked directly against all 3 real blocked
  workspaces -- all 3 now exit 0 with a `docs_only_skip` result instead of
  a `build` timeout.
- Live run: `systemctl --user start veridian-worker@<task_id>.service` for
  all 3 -- all 3 progressed from `status: blocked` to `status:
  pending_review` (confirmed via each task's own `task.yaml`), no auto-fix
  spend triggered this time. Supervisor review now running on each; their
  own PRs are expected to be small bookkeeping-only diffs given the real
  diagnosis work is already merged.

## Out of scope, left for the owner
- `veridian-scripts` PR #301 and #305 both still need human/owner review
  and merge -- external, not redispatchable from here.
- The 3 resumed tasks' `pending_review` -> final outcome is now in the
  normal supervisor review pipeline.
