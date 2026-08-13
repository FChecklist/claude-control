# This directory is retired

`scripts/` in this repo used to be the deployment source for the live
`/opt/veridian/scripts` directory on VERIDIAN-DEV, via `sync-repos.sh` +
`deploy-live-scripts.sh` (see `SCRIPTS_LIVE_VS_REPO_DRIFT_AUDIT_2026-07-25.yaml`
in the ai-os repo for the original reasoning).

As of 2026-08-01 this is retired. Root cause found and fixed the same day:
`/opt/veridian/scripts` is itself a real git working copy of
[`FChecklist/veridian-scripts`](https://github.com/FChecklist/veridian-scripts),
but `deploy-live-scripts.sh` was unconditionally overwriting same-named
tracked files there with this directory's older content on every sync
cycle — silently discarding real fixes merged into `veridian-scripts`.
Confirmed concretely: the 2026-07-27 worker-boot-activation OOM fix and
`dispatch-tick.py`'s `resume_interrupted_workers_tick` never actually
reached production despite being merged, because of this.

`sync-repos.sh` now pulls `/opt/veridian/scripts` directly from
`veridian-scripts` instead. This directory is no longer read by anything.

**2026-08-13 (task-20260813-103224, UMR-20260813-101142-5d24):** `deploy-live-scripts.sh`
itself has now been deleted outright from this directory (was: present but unused/dead
since 2026-08-01, contradicting this file's own "retire explicitly" intent and risking
someone re-wiring it back in pointed at the wrong repo). It still exists, correctly
un-tracked-as-live, in `git log` history here if anyone needs the old copy-based
mechanism for reference. The real, current, still-in-place mechanism remains
`sync-repos.sh`'s direct `git pull --ff-only` inside `/opt/veridian/scripts` (see
`FChecklist/veridian-scripts`'s own `sync-repos.sh` and, new as of this task,
`check_live_scripts_drift.py` in that same repo for a real live-vs-origin drift check).

**Do not add or edit files here for anything meant to run on the server.**
Use [`FChecklist/veridian-scripts`](https://github.com/FChecklist/veridian-scripts)
instead. The two files that existed only here
(`claude-tmux-usage-limit-check.sh`, `claude-usage-limit-retry.sh`) have
already been migrated there.
