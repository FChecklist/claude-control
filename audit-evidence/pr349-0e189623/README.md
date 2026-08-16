# Independent audit evidence: FChecklist/veridian-scripts PR #349

Head SHA audited: `0e189623ebc420d793aa32cdf28f80ff0752dddf`

This directory is a real, committed archive of what was independently audited
and executed against a fresh local clone (`gh repo clone FChecklist/veridian-scripts`
+ `git fetch origin pull/349/head:pr349`; `git rev-parse HEAD` confirmed to
match the SHA above before anything below was run). Verdict posted to the PR:
**AUDIT FAIL** — https://github.com/FChecklist/veridian-scripts/pull/349#issuecomment-5290085429

## Contents

- `reap_stale_test_scratch.py`, `tests/test_reap_stale_test_scratch.py`,
  `test_pm_sentinel_tick.py`, `test_resource_governor_queue_management.py`,
  `systemd/veridian-cron-reap-stale-test-scratch.{service,timer}`,
  `config/host/journald.conf.d/veridian-disk-cap.conf`,
  `config/host/logrotate.d/rsyslog` — exact copies of the audited files at
  head SHA `0e189623`.
- `pr349-full.diff` — full `gh pr diff 349` output captured at audit time.
- `shipped-test-output.txt` — real `pytest -v` output (all 4 PR-touched/added
  test files, real exit code 0 each) run against the fresh clone.
- `proof-scripts/` + `independent-check-output.txt` — two real, reproducible
  repros built independently of the PR's own test suite:
  1. **Symlink-attack repro**: a prefix-matching symlink pointing at a real
     directory with content, aged past the cutoff. Reaper deletes only the
     symlink; target content survives — confirms live register data outside
     `/tmp` is provably safe.
  2. **In-use-scratch repro (the FAIL finding)**: a prefix-matching directory,
     aged past the 2h default cutoff, containing a file a live background
     process is actively writing to (process cwd is NOT the candidate dir).
     The reaper deletes it — `"0 open-handle skips"` — proving the script's
     own docstring claim ("skips ... anything lsof reports as still open")
     does not hold. Root cause: `_has_open_handle()`
     (`reap_stale_test_scratch.py:70-81`) is invoked with the directory-level
     path (call site `reap_stale_test_scratch.py:119`), and `lsof -t <dir>`
     only detects cwd-based holds, not files open inside the tree, without
     `+D`.

See `progress/task-20260814-060034-real-tier-1-independent-audit-of-the-sta.md`
in this same task workspace for the full step-by-step audit log, and the
posted PR comment (linked above) for the complete writeup.
