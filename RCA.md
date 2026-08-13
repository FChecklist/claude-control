# RCA -- UMR-20260813-090037-9a34 (was status=killed, now corrected to completed)

## Governing chain
- This RCA task: `task-20260813-145003-rca--umr-20260813-090037-9a34-killed`,
  governing UMR `UMR-20260813-124121-892a` (PM-sentinel tick).
- Subject UMR: `UMR-20260813-090037-9a34`, dispatched
  `task-20260813-091919-correct-the-real-audit-fail-on-veridian`
  (title: "Correct the real AUDIT:FAIL on veridian-scripts PR #249, scoped
  strictly to what PR #290 does not cover").

## Real recorded fact BEFORE this task (verified live, not trusted from the
briefing summary)
`resource_governor.py --query-umr --umr-id UMR-20260813-090037-9a34`:
- `status=killed`
- `reason`: "real systemd state 'inactive', no PR was ever opened, real
  task.yaml status='blocked' -- no live process and no real deliverable;
  mechanically correctable to killed (orphaned dispatch, never produced a
  real artifact)."
- `unit_name=veridian-worker@task-20260813-091919-correct-the-real-audit-fail-on-veridian.service`
- `ts_dispatched=2026-08-13T09:19:22Z`, `ts_completed=2026-08-13T10:42:03Z`

## What actually happened (from the real task directory + GitHub, not the
governor row's own summary)

The task's own SPEC (`task.yaml`/`prompt.txt`) explicitly and repeatedly
directed the worker to push its fix **onto the pre-existing branch of
veridian-scripts PR #249** ("Push to PR #249, then request a real fresh
Tier-1 audit against the NEW head SHA"), not to open a brand-new PR from the
task's own auto-provisioned branch (`worker/task-20260813-091919-correct-the-
real-audit-fail-on-veridian`, in repo `claude-control` per `inputs_json`).

The worker did real work in a separately prepared worktree
(`/opt/veridian/repos/veridian-scripts-worker-exit0-wt`, on PR #249's own
branch), addressing all 6 scoped steps (supervisor-side ExecStopPost bridge,
27 new tests, factoring `reconcile_stale_running_workers.py` into a callable
`sweep()` wired into `dispatch-tick.py`, investigating the 1 pre-existing
failing test as unrelated), committed
(`24a6f1fe29e34be9e4c5d02ca072c782bbe1fcb8`), pushed to PR #249, and posted a
PR comment requesting a fresh Tier-1 audit. It never touched the task's own
`claude-control` workspace/branch, which correctly stayed a genuine no-op
(`files_modified: []`).

**Independently re-verified live, not trusted from the worker's own claim:**
- `gh pr view 249 --repo FChecklist/veridian-scripts`: `state=MERGED`,
  `headRefOid=24a6f1fe29e34be9e4c5d02ca072c782bbe1fcb8`,
  `mergeCommit.oid=dbcb636116189850a6ba798fe700d4c080be1e9e`,
  `mergedAt=2026-08-13T10:39:54Z`.
- `gh api .../commits/24a6f1f...`: real commit, real author
  (raajat.agarwal@gmail.com), commit message byte-identical to the one the
  worker's own `result.json` tool-call log shows it composing.
- PR #249's comment thread (real, live): AUDIT:FAIL (stale head) -> "real fix
  pushed" comment from this task -> a **second, independent Tier-1
  AUDIT:PASS** against head `24a6f1f` -> merge -> real post-merge deploy
  verification comment.
- Fresh scratch clone of `veridian-scripts` (the canonical
  `/opt/veridian/repos/veridian-scripts` checkout is missing on disk --
  separate finding below) + `git merge-base --is-ancestor`: both
  `24a6f1f` and merge commit `dbcb636` are confirmed real ancestors of
  `origin/main`.

**Conclusion: the prior "killed / no PR was ever opened / no real
deliverable" reason was factually false.** Real, tested, independently
Tier-1-audited (PASS), merged work exists and was already merged (10:39:54Z)
**two minutes before** the governor row was marked killed (10:42:03Z).

## Root cause

A structural detection gap in the supervisor/governor terminal-status
pipeline, not a worker failure:

1. This task's SPEC (correctly, and as explicitly instructed by its own
   ZERO-DUPLICATION requirement) directed the worker to land its fix on a
   **pre-existing PR's own branch** in a **different repo**
   (`veridian-scripts`) than the task's own auto-provisioned workspace/branch
   (`claude-control`).
2. The task's own auto-provisioned branch therefore had zero commits -- a
   genuine no-op there, correctly routed to `pending_review`.
3. The supervisor's post-review PR-resolution step only knows how to look
   for a PR matching **the task's own auto-created branch name**
   (`worker/task-20260813-091919-correct-the-real-audit-fail-on-veridian`).
   `gh pr create` failed ("No commits between master and
   worker/task-...") and `gh pr list --head` found nothing for that branch
   name, so the supervisor set `task.yaml status=blocked` with note "could
   not resolve a real PR" -- it never looked at PR #249, the actual PR
   named throughout its own SPEC/prompt.
4. `resource_governor.py`'s dead-dispatch reconciliation later swept this
   row: systemd unit inactive + `task.yaml status=blocked` + no PR found for
   that specific branch name -> mechanically concluded "no real deliverable"
   and wrote `status=killed`. It has no fallback path that checks whether the
   task's own SPEC names a specific pre-existing PR to verify against.

This is a **false negative in the platform's own dispatch-outcome
detection**, not a fabricated-completion incident: the worker's own
`result.json`/`worker.log` record real evidence (exact commit SHA, exact PR
number) that was available but never consulted by either the supervisor's
PR-resolution step or the governor's kill-sweep.

## Correction made (real, verified evidence, not fabricated)

```
python3 scripts/superboss-register.py mark-umr-terminal \
  --umr-id UMR-20260813-090037-9a34 --status completed \
  --commit-sha 24a6f1fe29e34be9e4c5d02ca072c782bbe1fcb8 \
  --pr-number 249 --repo veridian-scripts \
  --repo-root <fresh scratch clone, since the canonical
               /opt/veridian/repos/veridian-scripts is missing on disk> \
  --reason "<full evidence, see command output>"
```

`validate_umr_terminal_completion_evidence()`'s own live `git fetch` +
`merge-base --is-ancestor` gate passed against the real GitHub state.
Row re-queried after the write: `status=completed`,
`ts_completed=2026-08-13T14:54:00Z`. No remaining scope to redispatch --
the substantive work was already done, audited PASS, and merged.

## Structural gaps flagged for Owner/PM visibility (NOT fixed here -- out of
this RCA task's own narrow scope; flagging per governing-chain precedent of
recording, not silently absorbing, out-of-scope findings)

1. **Supervisor PR-resolution / governor kill-sweep blind spot**: neither
   step checks a task's own SPEC for a named pre-existing PR before
   concluding "no deliverable." Any future task whose SPEC (correctly)
   directs it to push onto an existing PR's branch, in the task's own repo
   or a different one, is at risk of being wrongly marked
   blocked -> killed even when it lands real, merged, audited work. A real
   fix would have the supervisor's PR-resolution step and/or the governor's
   dead-dispatch sweep also check for a PR number/commit SHA the task's own
   `outputs_json`/prompt/`PROGRESS.md` explicitly names, before falling back
   to "no artifact."
2. **Missing canonical repo checkout**: `/opt/veridian/repos/veridian-scripts`
   (the default `--repo-root` for `veridian-scripts` used by
   `mark-umr-terminal` and by every `veridian-scripts-*-wt` worktree) does
   not exist on disk -- confirmed via `ls` (absent) and via every existing
   `veridian-scripts-*-wt` worktree's `.git` file pointing at a
   `.git/worktrees/<name>` path under that missing parent, each failing with
   `fatal: not a git repository`. This silently breaks any future
   `mark-umr-terminal --repo veridian-scripts` call that doesn't override
   `--repo-root`, and breaks any worker that tries to reuse one of those
   worktrees. Verified around here using a fresh scratch clone instead of
   repairing the shared checkout (higher blast radius than this RCA's scope
   -- multiple existing worktrees under `/opt/veridian/repos/` reference it
   and a naive re-clone at that exact path could collide with them).
