# task-20260815-134246-unstarve-dispatch-queue--07-18-retry-res

UMR-20260815-105911-a2c9. Owner dispatch gateway rows have been starved for
6.5+ hours because all 4 occupied concurrency slots are held by resurrected
2026-07-18 `retry-2` task identities instead of real current owner_dispatch_gateway
work.

## Completed
- [x] Confirmed workspace topology: this claude-control checkout
      (`origin/master`) is a DIFFERENT repo from `/opt/veridian/scripts`
      (`origin/main`, remote `FChecklist/veridian-scripts`). The live
      `/opt/veridian/scripts/dispatch_core.py:101` named in the SPEC is a
      veridian-scripts repo file. Precedent: task-20260814-095433 did its
      real fix directly against `FChecklist/veridian-scripts`. Followed the
      same pattern: cloned `FChecklist/veridian-scripts` into this
      workspace (`veridian-scripts-clone/`, since the pretooluse_worker_
      enforcement hook blocks Edit/Write against `/opt/veridian/scripts`
      directly), branched, fixed, tested, pushed, opened the real PR there.
- [x] Read live `dispatch_core.py`: confirmed it is ONLY the
      concurrency-gating primitive (CONCURRENCY_CAP=5 at line 101,
      has_free_slot()/has_resource_headroom()) -- never decides WHAT to
      dispatch, only HOW MANY may run.
- [x] Found the real selection/ordering query: resource_governor.py's
      `next_queued_task()` (ranks queued rows by
      `(effective_priority(tier, age), ts_submitted)`) and `effective_priority()`
      (ages tier down over time, `AGING_PROMOTION_INTERVAL_SECONDS=15min`).
- [x] Checked directive_engine.py / recover-failed-workers.py /
      status-remediation-tick.py: NOT involved. directive_engine.py only
      drives DIRECTIVE.yaml's own priority_queue (different task_identity
      shapes like `PR617-REVIEW`); recover-failed-workers.py is a
      standalone, manually-invoked, 402-balance-only script;
      status-remediation-tick.py only handles PR merge-retry mechanics.
      The real re-minting path is `dispatch-tick.py`'s
      `resume_interrupted_workers_tick()`.
- [x] Proved root cause with real queries against the live
      superboss-register.sqlite:
      - 87 distinct `task-20260718-*` identities were resubmitted via
        `source_trigger='dispatch-tick:resume_interrupted_workers'`, all
        within `2026-08-15T03:56:09Z`-`04:15:xxZ` (~20s span), all
        `tier=1` (hardcoded in dispatch-tick.py).
      - A second burst of 30 rows landed `08:42:46Z`-`08:43:01Z` the same
        morning (matches SPEC's "35 identical 07-18 retry rows").
      - Read the actual task.yaml for one resurrected identity
        (`task-20260718-120006-retry-2--ai-engineering-quality--overal`):
        this work is REAL, not a zombie -- it was genuinely `blocked`
        2026-07-20 through 2026-08-15 on a real OpenRouter negative-balance
        issue, and was deliberately, correctly unblocked this morning by a
        separate task (`task-20260815-034138-resume-credit-blocked-backlog-after-real`,
        governing UMR-20260806-071025-1d28) once the real balance was
        reverified at $19.85, well above the $0.10 floor. So the fix must
        NOT re-block this backlog -- it must stop it from being able to
        starve owner rows, which is a different, real, additive fix.
      - Root cause mechanism: `effective_priority()` ages every row at the
        same rate, so a same-tier BATCH arrival can never be overtaken by a
        later same-tier arrival -- the `ts_submitted` ascending tiebreak
        always favors the older row. ~90 same-tier rows landing within
        seconds of each other structurally outrank every
        `owner_dispatch_gateway` row submitted afterward for as long as it
        takes the whole batch to drain.
- [x] Real fix implemented in `FChecklist/veridian-scripts`
      (branch `worker/task-20260815-134246-unstarve-dispatch-queue--07-18-retry-res`):
      1. `resource_governor.py`: `next_queued_task()` now applies a narrow,
         additive starvation guard -- once any `owner_dispatch_gateway` row
         has been queued for `OWNER_STARVATION_GUARANTEE_SECONDS` (30min
         default, `VERIDIAN_GOVERNOR_OWNER_STARVATION_GUARANTEE_S`
         override), the oldest such row is picked next unconditionally,
         ahead of every other queued row's tier/age. No starved owner row
         -> ranking unchanged.
      2. `dispatch-tick.py`: `resume_interrupted_workers_tick()` now caps
         real `resource_governor.submit()` calls per tick
         (`RESUME_SUBMIT_BATCH_LIMIT`, default 10,
         `VERIDIAN_RESUME_SUBMIT_BATCH_LIMIT` override) -- a large backlog
         now trickles across ticks instead of flooding the queue with
         dozens of same-tier, same-timestamp rows at once. Candidates past
         the cap are left untouched (not marked dead/duplicate) for a
         later tick.
- [x] Real before/after proof against the LIVE production DB (read-only
      connection, never mutated): loaded the pre-fix `resource_governor.py`
      via `git show 8fda6b8:resource_governor.py` alongside the post-fix
      working-tree version and ran both `next_queued_task()`s against the
      SAME real, live, currently-queued rows.
      - BEFORE picked `UMR-20260815-040423-4658`
        (`task-20260718-130005-retry-2...`, `dispatch-tick:resume_interrupted_workers`).
      - AFTER picked `UMR-20260815-041549-27c9`
        (`owner-task-20260815-041548-3221254`, `owner_dispatch_gateway`,
        age 34720s / 9.6h past the guarantee).
      - 15 real live `owner_dispatch_gateway` rows were confirmed past the
        starvation guarantee at proof time (ages 9346s-34720s).
- [x] Real tests, real exit 0:
      - `tests/test_owner_dispatch_starvation_guard.py` -- 3/3 pass (proves
        the pre-existing defect, proves the guard fires and picks the
        oldest starved row, proves no-op when nothing is starved).
      - `tests/test_resume_interrupted_workers_batch_cap.py` -- 2/2 pass
        (proves the cap bounds real submit() calls, proves no-op under the
        limit).
      - Full existing regression suite for both touched files re-run
        clean: `test_resource_governor_queue_management.py` (13/13),
        `tests/test_resume_interrupted_workers_bounded_retry.py` (2/2),
        `tests/test_resume_interrupted_workers_no_duplicate_row.py` (2/2),
        plus a 16-file sweep of every other test importing
        `dispatch_one`/`resource_governor`/`dispatch-tick`. 2 unrelated
        failures (`test_run_tick_still_stops_on_row_independent_block`,
        `test_dispatch_one_defense_in_depth_blocks_preexisting_queued_row`)
        reproduce IDENTICALLY against the unmodified pre-fix baseline
        (real live `running_worker_count()==5/5` on this box right now) --
        confirmed environmental, not caused by this change.
- [x] Opened real PR: https://github.com/FChecklist/veridian-scripts/pull/417
      (branch `worker/task-20260815-134246-unstarve-dispatch-queue--07-18-retry-res`
      -> `main`), citing all of the above evidence in the PR body and
      commit message.
- [x] Called `agent_work_briefing.py record-completion` for
      UMR-20260815-105911-a2c9.

## Remaining
- [ ] PR #417 review/merge is outside this task's own authority (per
      standing protocol: PRs are opened, not self-merged, by the worker
      that authored them) -- nothing further for this task once the real
      PR is open with real evidence.
