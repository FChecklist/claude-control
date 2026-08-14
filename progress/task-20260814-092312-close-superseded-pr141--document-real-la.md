# Task: Close superseded claude-control PR#141, document real landing

## Completed
- [x] Verify claude-control PR#141 state/branch -- OPEN, head `worker/task-20260813-115823-integrate-server-native-pm-into-one-dete`, title already self-disclosed as docs-only correction pointing at veridian-scripts#298
- [x] Verify veridian-scripts PR#299 merged -- confirmed MERGED, mergedAt 2026-08-13T18:49:15Z, title "feat(pm-sentinel-tick): integrate UMR-102459-10c3 + query-once/decide-and-fix (UMR-20260813-105106-e9a7)". Body confirms it supersedes #298 (#298 was CLOSED unmerged -- PR#141 pointed at the wrong/superseded PR number)
- [x] Verify follow-up PRs #313 (merged 2026-08-13T17:37:01Z), #323 (merged 2026-08-13T21:05:28Z), #341 (merged 2026-08-14T01:49:11Z), #306 (merged 2026-08-13T16:51:00Z) -- all MERGED in veridian-scripts
- [x] Live-verify /opt/veridian/scripts/pm-sentinel-tick.sh deployed -- confirmed present, mtime Aug 14 02:03
- [~] Live-verify veridian-pm-sentinel-tick.timer active/firing hourly -- COULD NOT independently re-verify from this task's sandbox: no /etc/systemd/system unit file visible, `systemctl`/`journalctl` return no data (no adm/systemd-journal group membership, no passwordless sudo). This is a sandbox access limitation, not a refutation. Citing the SPEC's own prior live-verification claim in the PR comment, caveated as sandbox-unverifiable here.
- [x] Confirm REPO_LOCAL_PATHS fix present in reconcile_stale_running_workers.py and superboss-register.py -- confirmed live: `REPO_LOCAL_PATHS["claude-control"]` (line 186) + `MARK_TERMINAL_REPO_CHOICES` including "claude-control" (line 192) in reconcile_stale_running_workers.py; `DEFAULT_OCID_RESOLVER_REPO_LOCAL_PATHS["claude-control"]` (line 4507) in superboss-register.py
- [x] git blame/log REPO_LOCAL_PATHS fix to find delivering PR -- commit 108652d "fix(reconcile): add claude-control repo mapping + supervisor-liveness race guard" (2026-08-13 14:14:58Z, Rajat Agarwal) landed via veridian-scripts PR#304 "fix(reconcile): claude-control repo mapping + supervisor-liveness race guard (UMR-20260813-115911-df5c)", merged 2026-08-13T22:59:21Z
- [x] Post closing comment on PR#141 citing evidence
- [x] Close PR#141
- [x] Call agent_work_briefing.py record-completion

## Remaining
(none)
