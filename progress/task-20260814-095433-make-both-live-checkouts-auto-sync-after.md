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

## Remaining
- [ ] Merge PR #367 into veridian-scripts main.
- [ ] Deploy live: pull `origin/main` into `/opt/veridian/scripts`
      (fast-forward), copy the two new unit files into
      `~/.config/systemd/user/`, `systemctl --user daemon-reload`,
      confirm the retimed `.timer` is `enabled`+`active`.
- [ ] Run the updated job for real (`systemctl --user start
      veridian-cron-sync-repos.service`, wait for it to finish) and
      capture real command output.
- [ ] Verify both live checkouts are now at their remote head:
      `git rev-list --count HEAD..origin/master` == 0 for claude-control;
      `git rev-list --count HEAD..origin/main` == 0 for
      `/opt/veridian/scripts`.
- [ ] Call `agent_work_briefing.py record-completion` for
      UMR-20260814-095405-2b53.

## Verification (real command output)
_(filled in as each step actually runs, not written in advance)_
