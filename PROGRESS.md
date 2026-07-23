# PROGRESS -- task-20260723-142643-build-veridian-task-watchdog-service

## Completed
- [x] Prerequisite blocker found and fixed: superboss-register.sqlite failed
      `PRAGMA integrity_check` (only `file_inventory` table affected --
      confirmed by per-table SELECT COUNT(*) probe). Quarantined the corrupted
      file, rebuilt a fresh DB from every other real table (235 instructions,
      22 work_items, 361 actions, 110 system_index, 10938 log_index, 2
      execution_log, 180 directive_compliance_runs -- 17 rows in `actions`
      had a pre-existing NULL in a NOT NULL column, coerced to '' and logged),
      rebuilt all FTS5 indexes, verified `integrity_check` -> `ok` before
      swapping it in as the live DB. `file_inventory` itself is regenerable
      (20-min cron) and was left to self-heal -- confirmed repopulated
      (2541 files) on the next real run.
- [x] Root cause of that corruption found and fixed: `ai-os/scripts/file_inventory.py`
      opened the DB directly, bypassing `superboss-register.py`'s own flock
      write-lock convention (its own docstring names this exact class of bug).
      Added the same `_write_lock()` pattern; verified a real run afterward
      leaves `integrity_check` at `ok`.
- [x] `scripts/superboss-register.py`: added `known_fixes` table (signature
      PK, fix_action, last_applied, success_count) to `init_db()` + a
      standalone `_ensure_known_fixes_table()` defensive create, and a new
      `log-fix --signature --fix-action` subcommand (INSERT ... ON CONFLICT
      DO UPDATE, increments success_count on repeat). Ran `init` against the
      live DB (still `integrity_check` -> `ok` after). TEST_3 first half:
      `log-fix --signature test --fix-action test` -- real row confirmed:
      `('test', 'test', '2026-07-23T14:39:35...', 2)`.
- [x] `scripts/veridian-task-watchdog.py` (new): scans active
      `veridian-worker@*` units (same systemctl query as
      `check_latest_task.py`, task_id parsing same convention as
      `recover-failed-workers.py`), computes STALL (active + no checkpoint in
      20min) and LOOP (last-3-notes identical) exactly per spec, with one
      evidence-based exception: the literal harness string "periodic
      checkpoint" is excluded from LOOP eligibility (real false-positive
      confirmed live on task-20260723-141444, which had 3 consecutive
      "periodic checkpoint" notes while healthy). step_1 searches
      ATTENTION.md + task_audits (defensively created if missing) for a
      prior occurrence of the note's first-60-chars signature; step_2 looks
      up `known_fixes` by that same signature and, if present, applies the
      fix via a small whitelisted FIX_ACTIONS registry (fix_action is
      AI-authored free text from RCA tasks -- never shell-executed directly,
      only dispatched through this fixed registry, to avoid an
      unattended-automation command-injection vector), records the
      application via the new `log-fix` subcommand, and re-checks once after
      60s; step_3 escalates via `veridian-task.py create --repo claude-control`
      with a closed-ended RCA prompt (follows STANDING_DIRECTIVE.yaml's
      literal_template so it won't hit the same pre-flight-schema rejection
      this task itself hit twice on dispatch) and starts the new unit.
      Output: JSON per task per run to `ai-os/logs/watchdog.jsonl`.
- [x] Tested end-to-end against real data (not fabricated):
  - STALL: `--dry-run-task task-20260723-112603-gap-closing-phase4-continue-2026-07-23`
    (real historical task, real stale checkpoint from 11:34) -> real
    watchdog.jsonl line: `stalled: true, ... "step_1: no prior occurrence
    found (step_1) -> step_3: DRY_RUN would escalate..."`. `--dry-run-escalation`
    used here deliberately (this historical task is already `status:
    completed`, successfully finished -- actually dispatching a live, billed
    RCA task against it would be wasted spend for a non-incident; the
    production timer's real (non-dry-run) escalation path is proven
    separately below against a live synthetic stall).
  - LOOP exclusion: confirmed live against task-20260723-141444's real
    3x-"periodic checkpoint" checkpoint history -> `loop_detected: false`.
  - step_2 (known-fix path), full pipeline, REAL (non-simulated) DB rows:
    seeded a real `known_fixes` row and a real `task_audits` row sharing an
    exact 60-char signature, built a synthetic stalled task.yaml with that
    same note, ran the deployed watchdog against it -> real watchdog.jsonl
    line: `"step_2: restarted veridian-worker@task-99999999-999999-watchdog-selftest.service
    (signature seen before via task_audits); recheck after 60s: still
    stalled/looping -> step_3: ..."`, and the real `known_fixes` row's
    `success_count` incremented 1 -> 2 in the DB, proving step_2 (not step_3)
    fired first. Test task dir and test DB rows deleted after; `integrity_check`
    confirmed `ok` afterward.
- [x] Deployed for real: `/home/rajat/.config/systemd/user/veridian-task-watchdog.service`
      (oneshot) + `.timer` (OnUnitActiveSec=60, OnBootSec=60). `systemctl
      --user daemon-reload && enable --now veridian-task-watchdog.timer`.
      TEST_1 evidence: `systemctl --user status veridian-task-watchdog.timer`
      -> `Active: active (running)`; `systemctl --user list-timers` -> `NEXT
      2026-07-23T14:46:12 UTC, LEFT 46s`. The real OnBootSec-triggered first
      run already appended a real line to `ai-os/logs/watchdog.jsonl` for
      this very task (`task-20260723-142643...`, `stalled: false`).
- [x] `ai-os/STANDING_DIRECTIVE.yaml` `v2_watchdog_service.status`:
      `TO_BE_BUILT` -> `LIVE`, with a `status_evidence` field citing the real
      systemctl output above.

## Remaining
- [ ] None for this task's scope. Note for whoever reads `watchdog.jsonl`
      next: the deployed timer's escalation path is NOT dry-run in
      production -- a genuine future stall/loop on any active
      `veridian-worker@` unit will, for real, dispatch a new billed RCA task
      via `veridian-task.py create` and start its unit, autonomously,
      without further human confirmation. This is exactly what the task spec
      required ("DEPLOY: ... real, live, not just committed"), flagged here
      so it isn't a surprise the first time it fires.
