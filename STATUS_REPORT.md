# RCA -- UMR-20260813-092654-326b (status=killed)

Governing chain: this task's own dispatching UMR (PM-sentinel tick), governing UMR-20260813-124028-1f69.

## Verdict

**No fix or redispatch needed.** UMR-20260813-092654-326b's `killed` status is honest and
accurate. This RCA was already independently performed by an earlier task
(`task-20260813-135602`, PR #148, merged) -- re-verified here from scratch, not trusted
secondhand, plus one new confirmation: the platform bug PR #148 found (which caused this exact
UMR to keep respawning duplicate RCA/redispatch attempts, including this task) **has since been
fixed and is live**.

## Step 1 -- real row read

`resource_governor.py --query-umr --umr-id UMR-20260813-092654-326b` (queried directly, not
trusted from the dispatch SPEC's summary):

- `task_kind=veridian_task_create`, dispatched worker
  `veridian-worker@task-20260813-095623-amendment-2--pm-hierarchy--single-gatewa.service`
  ("Amendment 2: PM hierarchy, single-gateway/zero-dup absolutes, generalized scope, GTM
  mission").
- `outputs_json` shows the dispatch itself succeeded (`returncode: 0`, worktree/branch prepared).
- `metadata_json.reconcile_owner_dispatch_status` (real evidence, `reconciled_at
  2026-08-13T10:42:03Z`): `task_yaml_status="blocked"`, `systemd_is_active="inactive"`,
  `pr_number=null`, `last_checkpoint_at=2026-08-13T10:08:32Z` (worker stalled ~34 min before
  reconciliation), bucket `STALE_LABEL_TERMINAL` -> `new_status=killed`.

**Root cause of `killed`:** the amendment-2 worker started, checkpointed once, then stalled
(`task.yaml` stuck `blocked`) and its systemd unit went `inactive` with no PR ever opened --
a genuine orphaned dispatch, never produced a real artifact. The mechanical reconciliation to
`killed` is correct, not a bug in itself.

## Step 2 -- zero-duplication check: has this exact UMR already been RCA'd?

Yes. `git log --oneline` on this same `claude-control` repo shows:

- `ba749c6` (PR #148, merged 2026-08-13T14:08:58Z) -- "real dedup + root-cause finding for
  UMR-20260813-092654-326b" -- found the amendment-2 scope (PM hierarchy / single-gateway /
  zero-duplication / dynamic-scope / standardized boolean-table report) was **already real,
  tested code**: `scripts/pm-sentinel-tick.sh` (commit `bb3fee7`, 696 lines + 363-line test
  file), shipped via **PR #141** (independently re-verified there, not trusted secondhand from
  a still-earlier finding in PR #142).
- That same task root-caused *why* the platform kept re-dispatching against this UMR instead of
  recognizing the real prior work: `DEFAULT_OCID_RESOLVER_REPO_LOCAL_PATHS`
  (`scripts/superboss-register.py`, then lines 3800-3804) and `REPO_LOCAL_PATHS` /
  `MARK_TERMINAL_REPO_CHOICES` (`scripts/reconcile_stale_running_workers.py`, then lines
  100-110) had **no `claude-control` entry** -- this platform's own default repo -- so
  `mark-umr-terminal` silently verified a real claude-control commit SHA against the wrong
  local checkout (`veridian-scripts`), refused it, and `reconcile_stale_running_workers.py`
  fell through to "genuinely ambiguous -> real re-queue", spawning redundant duplicate RCA
  tasks against this same UMR (this task included). Logged as
  `ISSUE-20260813-135602-repo-path` (#1099).

## Step 3 -- new confirmation this task adds: is the repo-path bug still live?

Re-checked the *live deployed* scripts directly (not assumed fixed from a citation):

```
$ grep -n 'claude-control' /opt/veridian/scripts/superboss-register.py
3821:    "claude-control": "/opt/veridian/repos/claude-control",
   (comment at 3806-3821 cites UMR-20260813-115911-df5c / task-20260813-140326 as the fix)

$ grep -n 'claude-control' /opt/veridian/scripts/reconcile_stale_running_workers.py
119:    "claude-control": "/opt/veridian/repos/claude-control",
125:MARK_TERMINAL_REPO_CHOICES = (..., "claude-control")
```

`/opt/veridian/repos/claude-control` exists as a real local checkout. The bug PR #148 found is
**already fixed and live** -- shipped by a separate, already-merged governance chain
(`UMR-20260813-115911-df5c`, task `task-20260813-140326`, PR #145 in this repo,
`veridian-scripts` PR #301/#303 for the code itself). This means the duplicate-RCA respawn loop
that produced this very task should now stop.

## Step 4 -- PR #141/#142 real current state

```
$ gh pr view 141 --json state,mergedAt   ->  state=OPEN, mergedAt=null
$ gh pr view 142 --json state,mergedAt   ->  state=OPEN, mergedAt=null
```

Both real, both still open. Landing either is separate, already-tracked work (not orphaned --
they are live, mergeable-pending PRs, not dead branches) and out of this RCA task's scope: this
task's job is root-cause diagnosis of the `killed` UMR, not merging unrelated feature PRs.

## Conclusion

- UMR-20260813-092654-326b: **`killed` status confirmed accurate, no change made.** The row was
  already terminal with an honest, evidenced reason before this task started; nothing to
  fix-and-redispatch, since the real scope behind the failed dispatch is already covered by
  open PR #141.
- No fabricated completion: no new code was written, because none was needed -- the real
  remaining gap (the repo-path bug that caused this and other duplicate RCA dispatches) was
  already closed by a separate, already-merged fix, independently re-verified here against the
  live deployed files rather than taken on citation alone.
- Recorded via `agent_work_briefing.py record-completion --umr-id UMR-20260813-124028-1f69`.
