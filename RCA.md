# RCA -- UMR-20260813-100854-e8a1 (status=killed)

## Governing chain
- This UMR: `UMR-20260813-100854-e8a1`, dispatched
  `task-20260813-103211-make-the-merged-write-back-reconciler-ac`
  (title: "Make the merged write-back reconciler actually run (PR #290 code is
  deployed but inert)"), which is itself an addendum to
  `UMR-20260813-065157-ba95` -> `UMR-20260806-171945-5767`.
- This RCA task: `task-20260813-141511-rca--umr-20260813-100854-e8a1-killed`,
  governing UMR `UMR-20260813-124024-e68a` (PM-sentinel tick).

## Real recorded fact (verified live, not trusted from the SPEC summary)
`resource_governor.py --query-umr --umr-id UMR-20260813-100854-e8a1`:
- `status=killed`
- `reason='stuck-task SIGKILL: no exit 60s after SIGTERM'`
- `unit_name=veridian-worker@task-20260813-103211-make-the-merged-write-back-reconciler-ac.service`
- `ts_dispatched=2026-08-13T10:32:15.373154+00:00`
- `ts_sigterm=2026-08-13T12:06:23.324046+00:00`
- `ts_completed=2026-08-13T12:07:24.591700+00:00`
- `logs_ref=null` (no logs attached to the row itself -- had to read the real
  task directory for evidence)

## What actually happened (from the real task directory)
`task.yaml` and `PROGRESS.md` for
`task-20260813-103211-make-the-merged-write-back-reconciler-ac` show **the
substantive work was genuinely completed**, across 6 real self-resuming
worker invocations between `10:32:15` and `11:06:59`:

1. Re-verified the SPEC's own evidence independently (didn't trust it).
2. Wired the already-real/tested/audited `run_owner_dispatch_reconciliation()`
   (from PR #290) into `dispatch-tick.py` -- the already-enabled, active,
   ~10-minute tick -- instead of re-enabling the disabled
   `veridian-cron-status-remediation-tick.timer`, explicitly justified
   against real Owner directive `INS-20260807-042700-a247`
   (per the SPEC's own instruction to justify, not assume).
3. Added a new hermetic test file (3 tests).
4. Ran a real one-off `--apply` pass directly against production: before
   `TOTAL=46/REAL_RUNNING=6/STALE_LABEL_TERMINAL=10/NEEDS_AI_JUDGMENT=30`
   -> applied 11 corrections -> after
   `TOTAL=35/REAL_RUNNING=5/STALE_LABEL_TERMINAL=0/NEEDS_AI_JUDGMENT=30`.
5. Posted an itemised per-row recommendation report for all 30
   `NEEDS_AI_JUDGMENT` rows as a PR comment (no bulk-guessing).
6. Full suite: 537 passed, same 2 pre-existing unrelated failures.
7. Opened **PR #293** (`FChecklist/veridian-scripts`), requested and got an
   independent Tier-1 audit: **AUDIT: PASS**.
8. Rebased onto `origin/main` after a real conflict was found (PR #249
   independently wired a complementary, non-duplicative reconciler into the
   same `dispatch-tick.py` section) -- kept both, re-tested, confirmed
   `mergeStateStatus=CLEAN` / `mergeable=MERGEABLE`.
9. Re-ran the full suite post-rebase in the background: 537 passed, 0 new
   failures.

By `11:06:59` (checkpoint from invocation 6, `task.yaml`), the task's own
`PROGRESS.md` correctly recorded the only remaining item as **external**:
"Owner/PM merge decision on PR #293 (this session does not self-merge)" --
i.e. the in-scope application work was done, and the task itself said so.

**Independently re-verified live, now**: PR #293 is still real, `OPEN`,
`mergeStateStatus=CLEAN`, `mergeable=MERGEABLE`, `mergedAt=null`, head
`8c73c550f3dc0c5f1358e8effc82b02b0cfa0423` -- confirmed as a real commit in
the local `veridian-scripts` checkout and confirmed **not yet** an ancestor
of `origin/main` (i.e. genuinely unmerged, matching the task's own claim).

## Real root cause of the kill
`resource_governor.py::scan_stuck_tasks()` sends SIGTERM once
`now - unit_ActiveEnterTimestamp >= STUCK_TASK_TIMEOUT_SECONDS` (default
3600s / 1h, `resource_governor.py:81`), then SIGKILL
`SIGTERM_TO_SIGKILL_GRACE_SECONDS` (60s) later if the unit hasn't exited.

- `systemd.log` (in the real task dir) shows 6 `CHECKPOINT` lines, one per
  invocation, ending with `status=pending_review` -- and **nothing after
  that**. `worker.log`'s last real log entry and `task.yaml`'s last
  checkpoint (`11:06:59`, invocation 6 start `11:06:06`) also stop there.
- The unit's `ActiveEnterTimestamp` resets on each of the 5 systemd restarts
  seen in `task.yaml` (`restart_count: 5`); the last restart was
  `11:06:06`. `11:06:06 + 3600s = 12:06:06`, matching the real
  `ts_sigterm=12:06:23` to within governor poll-interval jitter.
- So: invocation 6 started `11:06:06`, finished real work (a no-op
  re-verification -- correctly found "zero commits ahead of master" in
  *this* `claude-control` workspace, since the real deliverable lives in the
  separate `veridian-scripts` repo) and wrote its final checkpoint at
  `11:06:59` -- **53 seconds** of real work. The systemd unit process itself
  then never exited: **zero log activity for the following ~59 minutes**,
  until the stuck-task scanner's 1h timer (measured from unit start, not
  from last checkpoint) elapsed and sent SIGTERM, which the hung process
  also never honored, leading to SIGKILL 60s later.
- `supervisor.log`/`supervisor-systemd.log` (a companion process, not the
  worker itself) show a real, correct refusal earlier in the same task's
  life: `gh pr create` failed with "No commits between master and
  worker/task-...-ac" (expected -- this workspace repo has no commits, the
  real diff is in `veridian-scripts`), and the supervisor correctly refused
  to fall back to an unrelated PR (citing the real prior PR #84 incident)
  rather than silently misattributing review. That refusal set
  `status=blocked` once at `11:05:48`, which a subsequent restart correctly
  routed past (invocation 6 itself resolved to `pending_review`, not
  `blocked`). This confirms the supervisor-side logic behaved correctly and
  is **not** the hang; the hang is in the worker-unit process itself failing
  to terminate after its own final checkpoint.

**Conclusion**: this is a worker-process lifecycle bug (the systemd unit for
a task that has reached a stable "nothing left to do, blocked on an external
merge decision" state does not exit, and is later killed by the stuck-task
safety net purely on elapsed wall-clock time since last restart) -- it is
**not** a defect in the delivered work. The delivered work (PR #293) is real,
tested, audited PASS, and mergeable. This matches a known recurring pattern
on this box (see `cb7a03c` "real RCA + redispatch for UMR-20260808-175055-cebd
(stuck-task SIGKILL)" and `d6e25da` "resume-p2-3-after-stuck-task-sigkill" in
this repo's history) -- worth a dedicated follow-up to make the worker
process exit cleanly once it reaches a genuine no-further-action state,
rather than idling until the stuck-task scanner kills it. That follow-up is
a change to the worker wrapper/supervisor's post-checkpoint exit path, a
materially different and larger-blast-radius piece of work than this RCA's
own scope, and is intentionally **not** attempted here.

## Disposition
No in-scope application work remains to fix-and-redispatch: the only
remaining step (Owner/PM merge decision on PR #293) is explicitly external
and not something this or any redispatched worker session should
self-perform (the task's own PROGRESS.md says so, correctly, across 4
separate re-verification invocations that all found zero state change).
Redispatching this task's *scope* again would only repeat the same
already-complete re-verification loop.

Recorded a real, honest terminal outcome:

```
python3 scripts/superboss-register.py mark-umr-terminal \
  --umr-id UMR-20260813-100854-e8a1 \
  --status completed_unmerged \
  --reason "Real work complete: PR 293 in FChecklist/veridian-scripts wires \
run_owner_dispatch_reconciliation into the active dispatch-tick.py, apply \
pass corrected 11 stale rows, itemised NEEDS_AI_JUDGMENT report posted, \
Tier-1 audit PASS, rebased clean and mergeable. UMR was marked status \
killed only because the worker systemd unit hung with zero log activity \
for approx 59 minutes after its final checkpoint at 11:06:59 and was \
SIGKILLed by the 1h stuck task timer measured from unit restart not last \
checkpoint, a worker lifecycle bug not a work failure. Remaining step, \
Owner or PM merge of 293, is external and not redispatchable." \
  --pr-number 293 \
  --commit-sha 8c73c550f3dc0c5f1358e8effc82b02b0cfa0423 \
  --repo veridian-scripts \
  --repo-root /opt/veridian/scripts
```

Note: `--repo veridian-scripts`'s hardcoded default `repo_root`
(`/opt/veridian/repos/veridian-scripts`, `superboss-register.py:3802`) does
not exist on this box -- the real live checkout for that repo is
`/opt/veridian/scripts` (confirmed via `git remote -v` ->
`FChecklist/veridian-scripts.git`). Required an explicit `--repo-root`
override to verify the commit. This is a real, separate latent bug in
`superboss-register.py`'s `REPO_ROOTS` mapping (stale path), left
unfixed here as out of this RCA's scope -- flagged for a future task.

Command succeeded: `status=completed_unmerged`,
`ts_completed=2026-08-13T14:19:21.652855+00:00`, evidence keys
`['commit_sha', 'pr_number', 'repo']` recorded on the row's
`outputs_json`.
