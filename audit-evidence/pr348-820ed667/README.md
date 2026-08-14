# Audit evidence: FChecklist/veridian-scripts PR #348

Head SHA audited: `820ed667465f61f609495faba532e61fd9eb34ed` (confirmed via
`gh pr view 348 --repo FChecklist/veridian-scripts --json headRefOid`).

This directory is archival evidence for a real, independent audit of PR #348.
It is **not** a change to worker-entrypoint.sh in this repo -- the file being
audited lives in FChecklist/veridian-scripts, a different repo, and the audit
spec explicitly says "do not merge". These are read-only copies of the exact
audited artifacts plus the auditor's own independently-executed test harness
and its captured real output, kept here so the audit is reproducible and not
just asserted.

Contents:
- `worker-entrypoint.sh` -- exact copy of the file as it stands at PR #348's
  head SHA (verbatim `git show pr-348:worker-entrypoint.sh` at the time of
  audit).
- `tests/preflight_guard_hardstop_test.sh` -- exact copy of the new test file
  shipped in the PR (verbatim, 239 lines, +239/-0 in the PR diff).
- `independent_audit_check.sh` -- a second, auditor-authored test harness,
  written from scratch (not copied from the PR's own test), that
  independently re-extracts the real cap-check + PREFLIGHT-GUARD-BLOCK +
  LIFETIME-INVOCATION-CHARGE-BLOCK from worker-entrypoint.sh via its own sed
  ranges and executes them as real bash subprocesses. Covers exactly the two
  scenarios the audit spec calls out: (A) a genuinely over-limit worker is
  still stopped, (B) a normal/under-cap worker still passes preflight.
- `shipped-test-output.txt` -- real captured stdout+exit code from running
  `bash tests/preflight_guard_hardstop_test.sh` against the PR's actual
  worker-entrypoint.sh. Real result: 34 passed, 0 failed, exit code 0.
- `independent-check-output.txt` -- real captured stdout+exit code from
  running `independent_audit_check.sh`. Real result: 9 passed, 0 failed,
  exit code 0.

The full AUDIT PASS finding, with this evidence summarized, was posted as a
real comment on PR #348 (not merged, no self-certification).
