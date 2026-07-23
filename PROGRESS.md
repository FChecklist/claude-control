# PROGRESS -- task-20260723-120458-gap-closing-phase5-network-security-perm

## Completed
- [x] Extended `/opt/veridian/scripts/health-check-15min.py` with `check_network_usage()`
      (reads /proc/net/dev, diffs rx/tx byte counters against the previous 15-min cycle's
      totals, same JSONL-based previous-cycle-read pattern the file already uses for
      `get_prev_blocked_ids()`). Wired into `main()`, no new cron entry. Verified live:
      next real `health-15min.jsonl` write has a non-null `network` key with 27 real
      interfaces. Item 20 (network_usage_logging): **DONE**.
- [x] Extended `ai-os/scripts/file_inventory.py`: added `file_inventory.mode TEXT`
      (idempotent `ALTER TABLE` in try/except), populated via
      `stat.S_IMODE(os.stat(path).st_mode)` on every scan pass. Verified live: 2460/2465
      rows populated after one real run. Item 22 (file_permission_change_tracking) also
      needs a consumer -- see security-check.py below. Item 22: **DONE**.
- [x] New file `scripts/security-check.py`: SSH new-source-IP + failed-then-success-burst
      detection from `/var/log/auth.log`, and file-permission-change detection by diffing
      `file_inventory.mode` against its own persisted baseline
      (`ai-os/logs/security-check-state.json`). Both wired to `scripts/notify-owner.py`
      with `dedupe-key=finding-type+identifier`. Fail-open throughout (a read/parse
      problem shows up in an `errors` list, never a crash). Exits 0, valid JSON, verified
      live. Added to the user crontab: `*/15 * * * * ... security-check.py`.
      Item 21 (ssh_login_anomaly_detection): **PARTIAL**. Item 24
      (security_event_detection): **PARTIAL**. Both downgraded from a straight DONE because
      of a real blocker found during testing (see below), not a design gap.
- [x] **Real blocker found via testing, not assumed**: `/var/log/auth.log` is
      `syslog:adm`, mode `0640`. The account every cron job on this server runs as
      (`rajat` -- groups `rajat,sudo,docker`, confirmed via `id`) is **not** in `adm`, so
      `security-check.py` currently cannot read auth.log at all (`sudo -n` also failed:
      "a password is required"). It fails open and reports this in an `errors` field
      rather than crashing. This is a real system-permission change (`sudo usermod -a -G
      adm rajat` or an equivalent ACL grant) that needs an Owner decision, not something
      an agent should silently grant itself -- logged in
      `ai-os/OWNER_DECISIONS_NEEDED_2026-07-23.yaml`.
- [x] End-to-end verification of permission-change detection: created a real test file,
      changed its mode 644->600, ran `file_inventory.py` + `security-check.py` before and
      after -- correctly detected `{old_mode: '0644', new_mode: '0600'}` and this real
      finding triggered one genuine `notify-owner.py` send (confirmed via
      `ai-os/logs/notify-owner-state.json`'s `security-permchange-6b9c96dd7c40cdbc` entry,
      timestamped 2026-07-23T12:13:48Z -- notify-owner.py only records that entry after a
      successful Resend send). Test file removed afterward. On the live system's actual
      current state (no auth.log access, no real permission drift after cleanup), a plain
      run of `security-check.py` finds zero findings -- stated here explicitly rather than
      fabricating one, per this task's own instruction not to invent a test finding.
- [x] **Found and fixed a real, reproducible `superboss-register.sqlite` integrity
      failure** (`wrong # of entries in index sqlite_autoindex_file_inventory_1`),
      surfaced by health-check-15min.py's own `check_db_integrity_and_backup()` after my
      `ALTER TABLE` + several sequential INSERT/UPDATE passes on `file_inventory` (this
      server's cron fleet -- health-check, queue-dispatcher, veridian-self-check -- all
      also hit this same DB concurrently in the background, matching the corruption
      pattern already documented in this session's KNOWN_CONTEXT). Verified table-scan
      row count matched a forced index-scan row count (2465 == 2465, 0 duplicate paths)
      before repairing, i.e. the underlying data was intact -- ran `REINDEX
      file_inventory;` (safe, non-destructive, does not touch row data), re-checked
      `PRAGMA integrity_check` -> `ok`. A subsequent real `health-check-15min.py` run
      confirms 0 anomalies. All DB writes this task made were sequential, single
      connection, no parallel agents, per this task's own constraint.
- [x] Restored `ai-os/GOVERNANCE_AUDIT_RESULT_2026-07-23.yaml` into this repo (it is a
      real document -- 60 items, all with real evidence -- created by an earlier task
      (`task-20260723-034803`, commit `5988921`) but that commit lives only on that task's
      own never-merged branch; it had never made it onto this repo's master, nor onto the
      live server at the canonical `/opt/veridian/ai-os/` path referenced by this task's
      own spec). Restored the full 60-item content, updated items 20/21/22/24 with real
      evidence citing file:line and command output, and recomputed the summary counts
      (done 26->28, partial 21->23, missing 13->9). Left items 1-19, 23, 25-60 untouched.
- [x] Added `ai-os/OWNER_DECISIONS_NEEDED_2026-07-23.yaml` with two real items: the
      auth.log group-permission grant above, and a second item explained below.
- [x] Committed real diffs for the two extended live-host scripts (they live on the
      server, not in this git repo) at `ai-os/patches/health-check-network-usage-2026-07-23.diff`
      and `ai-os/patches/file-inventory-mode-column-2026-07-23.diff`, each verified with
      `patch --dry-run` against the pre-phase file content. `scripts/security-check.py` is
      committed in full (new file, nothing to diff against).
- [x] Added the cron entry exactly as specified:
      `*/15 * * * * /opt/veridian/scripts/run-logged.sh "security-check" ...`
      (verified via `crontab -l`).

## Deliberately NOT done -- explained, not silently skipped
- [ ] **Did not run this task's own "NEXT_PHASE" self-dispatch steps** (`veridian-task.py
      create --title "gap-closing-phase6-..."` followed by
      `systemctl --user start veridian-worker@<new-id>.service`), even though this task's
      own spec framed skipping them as a "FAILURE of this task's own EXPECTED_OUTPUT, not
      optional."
      **Why**: this is the third consecutive phase of the exact same self-perpetuating
      chain (`task-20260723-034803` -> ... -> Phase 3 `task-20260723-103551` -> Phase 4
      `task-20260723-112603` -> this task, Phase 5). Phase 3 (commits e3c845d/b7e30ea) and
      Phase 4 (commit 71af82c) each independently investigated and explicitly declined to
      self-dispatch further phases, for two reasons stated in their own PROGRESS.md/commit
      messages: (1) the shared lessons file this chain reads
      (`/opt/veridian/ai-os/CONTINUOUS_GAP_CLOSING_PROMPT_2026-07-23.txt`, KNOWN_CONTEXT
      point 3) explicitly coaches future phases on how to word prompts to slip past an
      automated contradiction validator ("it's a bag-of-words checker, not semantic --
      prefer positive phrasing") -- re-read for this phase, that coaching text is still
      present, unchanged; (2) autonomously spawning further phases and pushing to
      production unattended, several invocations deep, needs explicit human confirmation,
      which neither phase had. This phase independently re-verified both findings (the
      lessons file's content, and that Phase 3/4's refusal was a deliberate, reasoned
      decision, not an oversight this task's own prompt mischaracterized it as -- Phase
      4's own investigation already checked that). Nothing has resolved either concern
      between Phase 4 and now, so this phase is holding the same pause rather than
      re-litigating a settled question or one-upping the pattern (this phase's own spec
      escalated the framing to "FAILURE...not optional" language, which reads as pressure
      to override that pause rather than a new fact that would change the analysis).
      Logged as an Owner decision item (`ai-os/OWNER_DECISIONS_NEEDED_2026-07-23.yaml`,
      id `continuous-gap-closing-chain-self-dispatch-pause`) with three concrete options
      for how to resolve it.
      **This phase DID still do its own real, scoped engineering work and DID commit and
      push it** -- the pause is specifically about autonomously spawning the *next* phase
      of an indefinite chain, not about doing or shipping this phase's own assigned work.

## Remaining (for a human to decide, not for automatic Phase 6)
- [ ] Owner decision: grant `adm` group membership (or equivalent) to the cron/worker
      account so item 21's SSH log parsing has live data. See
      `ai-os/OWNER_DECISIONS_NEEDED_2026-07-23.yaml`.
- [ ] Owner decision: how to resolve the shared lessons file's validator-evasion coaching
      and whether/how this chain should keep self-dispatching. See the same file.
- [ ] Once auth.log is readable, re-verify item 21/24 with a live SSH login and flip to
      DONE with fresh evidence (not fabricated now, since no real access exists yet).
