# Real Tier-1 independent audit of PR 349 (FChecklist/veridian-scripts)

Head SHA under audit: `0e189623ebc420d793aa32cdf28f80ff0752dddf` (short: 0e189623)

## Completed
- [x] Confirmed PR 349 state via `gh pr view`: MERGEABLE, mergeStateStatus CLEAN, additions 556 / deletions 4, headRefOid 0e189623ebc420d793aa32cdf28f80ff0752dddf
- [x] Pulled full diff (`gh pr diff 349`) and file list (11 files matches spec)

- [x] Cloned veridian-scripts repo, checked out PR head SHA (confirmed local HEAD == 0e189623ebc420d793aa32cdf28f80ff0752dddf)
- [x] Read reap_stale_test_scratch.py in full: policy = /tmp only, narrow literal prefix/exact-name allowlist, mtime > min-age-hours (default 2h), best-effort lsof -t check before delete, fails open (exit 0 always)
- [x] Read tests/test_reap_stale_test_scratch.py: covers prefix match + age gate + dry-run + --min-age-hours override, on an isolated --tmp-dir root. Does NOT test the lsof open-handle skip path at all.
- [x] Read diffs to test_pm_sentinel_tick.py and test_resource_governor_queue_management.py: real root-cause fix, `src.backup(dst)` (full binary copy of live 3-4GB DB) replaced with `_schema_only_copy` (schema-only, 3-pass FTS5-safe clone), plus `addCleanup(shutil.rmtree...)` registered before the copy so scratch is reclaimed even if setUp raises mid-copy
- [x] Validated both systemd unit files: `systemd-analyze verify --user` on isolated copies -> exit 0, no errors/warnings. No `User=` directive anywhere in systemd/ (correct/consistent for --user scope). Structure (Unit/Service/Timer/Install, ConditionPathExists EMERGENCY_STOP guard, run-logged.sh wrapper, log path convention) matches existing veridian-cron-prune-memory-backups.{service,timer} exactly.
- [x] Validated journald.conf.d/veridian-disk-cap.conf (SystemMaxUse=1G/SystemKeepFree=2G, real journald.conf directives) and logrotate.d/rsyslog (`logrotate --debug -f` on the file: exit 0, valid syntax; diffed against this sandbox's own live /etc/logrotate.d/rsyslog -- byte-identical except added `maxsize 500M` line, corroborating the PR's own claim)
- [x] **FINDING**: lsof open-handle check in `_has_open_handle()` (reap_stale_test_scratch.py L70-81) is called with the top-level candidate directory path, not per-file. Empirically confirmed (`lsof -t <dir>` returns nothing when a process holds a file open *inside* that dir but does not have the dir itself as cwd; `lsof -t <the file itself>` correctly detects it). This means the "cannot delete in-use scratch" claim is NOT fully proven -- a process holding a live register-copy file open more than 2h after its containing tmpdir was created would have its live data deleted, undetected by this check.
- [x] Ran the real test suite, recorded actual exit codes:
  - `tests/test_reap_stale_test_scratch.py` -> 3 passed, exit 0 (3.06s)
  - `test_pm_sentinel_tick.py` -> 11 passed, exit 0 (34.31s)
  - `test_resource_governor_queue_management.py` -> 13 passed, exit 0 (7.82s)
  - `tests/test_rule7_completion_evidence.py` -> 14 passed, exit 0 (0.77s)
  - Confirmed via `ls /tmp` that no scratch dirs were left behind after these real runs (addCleanup fix verified live, not just read)
- [x] Built two real repros to test the reaper's claimed safety invariants directly (not just code review):
  1. Symlink-attack repro (prefix-matching symlink to a dir with real "precious live data" content, aged 3h): reaper deleted only the symlink, target content survived intact -- confirms live-register-data-outside-/tmp claim holds.
  2. Live-open-file repro (dir matching `pm_sentinel_tick_` prefix, aged 3h past default 2h cutoff, containing a file a live background process was actively writing to, process cwd NOT the candidate dir): reaper DELETED it, reporting "0 open-handle skips" -- proves the docstring's claimed lsof open-handle protection does NOT hold for the normal Python pattern (open a file inside a tmpdir without chdir'ing into it). Root cause: `_has_open_handle()` (reap_stale_test_scratch.py:70-81) is called with the directory-level path, and `lsof -t <dir>` only detects cwd-based holds, not files open inside the tree, without `+D`.
- [x] Formed verdict: **AUDIT FAIL** -- primary root-cause fix (schema-only copies + addCleanup) is real/tested/solid; systemd units + journald/logrotate caps are all valid; but the reaper's own explicitly-claimed "cannot delete in-use scratch" safety property is falsified by a real, reproducible, non-contrived scenario, and untested by the PR's own test file.
- [x] Posted real audit comment on PR 349 naming head SHA 0e189623ebc420d793aa32cdf28f80ff0752dddf -- https://github.com/FChecklist/veridian-scripts/pull/349#issuecomment-5290085429 (confirmed via `gh api` as the only comment on the PR)
- [x] Did NOT merge
- [x] record-completion via agent_work_briefing.py with UMR-20260814-060020-a9dc

## Verdict summary
**AUDIT FAIL** on PR 349 head SHA `0e189623ebc420d793aa32cdf28f80ff0752dddf`. Root-cause fix and all infra config (systemd/journald/logrotate) verified solid; the second-layer reaper script's own claimed in-use-scratch safety guarantee is real-world falsified (concrete repro in the PR comment). Not merged. Recommended fix: make `_has_open_handle` recursive (`lsof +D`) and add a real test for the open-handle-inside-dir case.
