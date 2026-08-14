# task-20260814-095433-make-both-live-checkouts-auto-sync-after

UMR-20260814-095405-2b53. Real permanent auto-sync for the two live
checkouts (claude-control -> origin/master, /opt/veridian/scripts ->
origin/main), implemented as a systemd --user timer.

**Cross-repo note**: the real code for this fix lives in **veridian-scripts**
(`FChecklist/veridian-scripts`), not in this claude-control workspace --
`sync-repos.sh` and the `veridian-cron-sync-repos.{service,timer}` units
that keep both live checkouts in sync are veridian-scripts files (confirmed
by direct inspection of the live, already-installed job before making any
change). This claude-control repo needed no code changes for this fix.

## Completed
- [x] Independently re-verified the SPEC's evidence live (not trusted blind):
      claude-control at `113bcf0`, 16 commits behind `origin/master`;
      `/opt/veridian/scripts` at `2eee24b`, 6 commits behind `origin/main`.
- [x] Found the existing mechanism (capability registry pointed at it):
      `veridian-cron-sync-repos.timer`/`.service` already exist, already
      `enabled`+`active`, cadence every 2h, and already pull both
      claude-control and `/opt/veridian/scripts` (plus 5 other mirrors +
      veridian-ai-os). This is unit #1 of the closed 20-unit set
      (`~/.config/systemd/user/README.md` STANDING RULE) -- per that rule,
      a new periodic need that fits an existing unit's purpose must be
      folded into that unit, not shipped as a new (21st) unit.
- [x] Root-caused the drift with real log/journal evidence:
      `/opt/veridian/logs/sync-repos-20260814-082635.log` (last real run,
      08:26:42Z) shows claude-control synced OK to `113bcf0` -- the 16
      commits behind now landed AFTER that run, within the 2h gap before
      the next scheduled tick (~10:06Z). `/opt/veridian/scripts` was
      `SKIPPED: uncommitted local changes present` in that same run (a
      real, correct refuse-to-clobber event -- re-checked live, the tree
      is clean now, so it was transient) with no automatic retry available
      for up to 2h. Root cause = cadence too slow for same-day merge
      volume, not a missing job.
- [x] Implemented the real fix in `FChecklist/veridian-scripts`
      (branch `worker/task-20260814-095433-make-both-live-checkouts-auto-sync-after`):
      - `sync-repos.sh`: new shared `sync_critical_checkout()` function for
        both claude-control (`master`) and `/opt/veridian/scripts` (`main`)
        -- refuses to clobber uncommitted tracked changes and reports the
        real diff (not silent), detects+reports wrong-current-branch
        without auto-switching, idempotent (`rev-list --count` gated
        no-op), sets exit code so a drifted critical checkout is a real
        FAILED run in the register via `run-logged.sh`.
      - `systemd/veridian-cron-sync-repos.{service,timer}`: tracked in
        version control for the first time; `.timer` cadence raised from
        every-2h to every-5min (`OnCalendar=*:0/5`), matching the
        precedent set by `veridian-cron-prune-memory-backups.timer`.
      - `systemd/README.md`: documents the new tracked entry.
- [x] Opened real PR: https://github.com/FChecklist/veridian-scripts/pull/367
- [x] Merged PR #367 into veridian-scripts main (mergeCommit `8d88919`,
      2026-08-14T10:04:37Z).
- [x] Deployed live: pulled `origin/main` into `/opt/veridian/scripts`
      (fast-forward, `2eee24b` -> `8d88919`, 0 behind), copied the two new
      unit files into `~/.config/systemd/user/`, `systemctl --user
      daemon-reload`, `systemctl --user restart
      veridian-cron-sync-repos.timer`. Confirmed `enabled`+`active` with the
      new 5-min cadence live (timer fired within seconds of the restart).
- [x] Ran the updated job for real and hit (then fixed) a genuine live
      finding: the first real run (10:04:52Z) correctly detected and
      LOUDLY REPORTED (did not silently skip, did not auto-clobber) that
      `/opt/veridian/repos/claude-control` was sitting on a stale,
      already-superseded local branch (`land-6a78798-pm-sentinel`, one
      abandoned commit `dda3deb` left over from a different, already-
      complete task) instead of `master` -- exactly the wrong-branch
      hazard the new `sync_critical_checkout()` logic exists to catch.
      Investigated before touching anything: confirmed via `gh pr view 227`
      that the same content was already merged to `origin/master` as
      `0cb827d` through a normal PR, and confirmed via `lsof`/`ps` that no
      process was using the directory -- i.e. genuinely abandoned, not
      in-flight work. Manually ran `git checkout master` (a deliberate,
      evidence-based human/Owner-level call, not an automatic script
      action -- consistent with the code's own documented policy of never
      auto-switching branches itself), then re-ran the job.
- [x] Verified both live checkouts are now at their remote head (real
      command output):
      ```
      === claude-control ===
      branch: master
      HEAD: 90874049419d8e354a95fc2a59272062768c8631
      behind origin/master: 0

      === veridian-scripts (/opt/veridian/scripts) ===
      branch: main
      HEAD: 8d88919cc8caf8a8b3c4558c0f4be53993dcef23
      behind origin/main: 0

      === timer state ===
      enabled
      active
      ```
- [x] Verified idempotency: ran the service twice more after the fix
      (`systemctl --user start veridian-cron-sync-repos.service`), both
      times `status=0/SUCCESS`, both times "already up to date ...
      idempotent no-op" for the two critical checkouts -- no errors, no
      side effects on a clean re-run.
- [x] Verified register logging is real and working (query against
      `superboss-register.sqlite` `actions` table via
      `superboss-register.py search`), showing the exact before/after
      exit-code signal this fix adds:
      ```
      2026-08-14T08:26:42Z job_end:sync-repos ... status=completed exit_code=0   (old script, pre-fix; masked the veridian-scripts dirty-skip as "completed")
      2026-08-14T10:04:59Z job_end:sync-repos ... status=failed    exit_code=1   (new script; correctly caught claude-control on wrong branch)
      2026-08-14T10:05:13Z job_end:sync-repos ... status=failed    exit_code=1   (same, next tick, branch not yet fixed)
      2026-08-14T10:05:54Z job_end:sync-repos ... status=completed exit_code=0   (after manual `git checkout master`, real fast-forward pull)
      2026-08-14T10:06:20Z job_end:sync-repos ... status=completed exit_code=0   (idempotent re-run, no-op)
      ```
- [x] Called `agent_work_briefing.py record-completion` for
      UMR-20260814-095405-2b53.

## Remaining
- [ ] None. All verification criteria from the SPEC are met with real
      command output above.
