# Progress: infrastructure-fault-preflight-rejection

Real fix lives in the `veridian-scripts` repo (worker-entrypoint.sh is deployed
there, `/opt/veridian/scripts/worker-entrypoint.sh` is a live copy of it), not in
this claude-control workspace. Branch:
`FChecklist/veridian-scripts#fix/lifetime-invocation-counter-preflight-rejection`.

## Completed
- [x] Confirmed the real bug live: `worker-entrypoint.sh` (ExecStart of
      `veridian-worker@.service`) incremented `.invocation_count` (cap
      `MAX_LIFETIME_INVOCATIONS=20`) at the top of the script, BEFORE the
      preflight guard ran -- so a purely infrastructural rejection (transient
      branch, note text `-- no model call made, no cost incurred`) still
      permanently burned a lifetime invocation slot, retried up to
      `StartLimitBurst=3` times by systemd.
- [x] Fix #1: moved the lifetime-invocation-counter write to a new
      `LIFETIME-INVOCATION-CHARGE-BLOCK`, immediately after preflight passes and
      a real model call (`claude -p`) is imminent. Neither the hard-stop branch
      nor the transient branch of the preflight guard ever reaches it now.
- [x] Fix #2: added a SEPARATE `.infra_rejection_count` counter with its own cap
      (`MAX_INFRA_REJECTIONS`, default 5, env-overridable via
      `VERIDIAN_MAX_INFRA_REJECTIONS`) and its own growing backoff
      (`sleep $((count * 5))`), on the transient/infrastructural rejection path
      only. Once exceeded, the unit is disabled and stops retrying (same shape
      as the existing hard-stop branch) -- so a genuinely broken host still
      cannot spin the task forever, without ever again borrowing from the real
      model-invocation budget to do it.
- [x] Real test: `tests/preflight_guard_hardstop_test.sh` (bash), extracts the
      REAL `PREFLIGHT-GUARD-BLOCK` + `LIFETIME-INVOCATION-CHARGE-BLOCK` verbatim
      from the real `worker-entrypoint.sh` (matching the file's own inline
      comment promising this filename) and runs it as a real bash subprocess
      with only `python3`/`systemctl`/`sleep` shimmed via `PATH`. 34/34
      assertions pass, exit code 0. Covers: transient rejection leaves the
      lifetime counter untouched; infra counter increments + backs off +
      eventually stops retrying on its own cap; hard-stop reasons also never
      charge the lifetime counter; a real preflight PASS does charge it; the
      pre-existing `MAX_LIFETIME_INVOCATIONS` cap check is unaffected.
- [x] Committed + pushed to
      `FChecklist/veridian-scripts#fix/lifetime-invocation-counter-preflight-rejection`
      (commit 820ed66).

- [x] Task 3: repaired all 11 damaged `.invocation_count` values. Real
      script: `scripts/repair_invocation_counters.py` (dry-run by default,
      `--apply` to write). Corrected value derived purely from each task's own
      `task.yaml` checkpoint history (never from the disputed live counter
      value), discounting only checkpoints whose note contains the literal
      "no model call made, no cost incurred" text. Full before/after table +
      methodology + a flagged discrepancy (one task's live counter didn't
      match its own checkpoint-derived total, and the SPEC's cited "18/20"
      for that task wasn't reproducible against its actual on-disk state) in
      `INVOCATION_COUNTER_REPAIR_20260814.md`. Verified all 11 writes
      post-hoc by re-reading the files.

## Remaining
- [ ] Open the real PR on `FChecklist/veridian-scripts` with the pasted real
      test output in the body.
- [ ] Deploy the fixed `worker-entrypoint.sh` to the live
      `/opt/veridian/scripts/worker-entrypoint.sh` path (currently only fixed in
      the repo checkout + this branch -- the live file is still the old,
      buggy version until this PR merges and gets deployed, same as the
      existing deploy convention this repo's own history shows, e.g. PR #345).
- [ ] Call `agent_work_briefing.py record-completion` for
      UMR-20260814-034225-3392 once the PR is open (and merged/deployed if
      that happens within this task's own lifetime).

## Scope notes
- Did NOT touch `doc-worker-entrypoint.sh` (separate template,
  `veridian-docworker@.service`, MAX_LIFETIME_INVOCATIONS default 8) even
  though it has the identical bug shape (its own transient branch at the old
  line ~79 also checkpoints failed with `-- no model call made` and does
  `exit 1` before any counter fix). The task SPEC explicitly names the
  `veridian-worker@.service` entrypoint; doc-worker is out of the named scope.
  Flagging as a known follow-up, not fixing it here.
- Did NOT touch host disk usage, logging/journald config, or dedup/duplicate-
  guard logic -- all explicitly out of scope per this task's SPEC.
