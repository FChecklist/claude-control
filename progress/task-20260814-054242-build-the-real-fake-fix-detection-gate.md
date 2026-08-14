# task-20260814-054242-build-the-real-fake-fix-detection-gate

## Real correction to the dispatching SPEC's own premise (verified live, not assumed)

The SPEC claims "the actual gate code was never written." Verified against
the live, currently-running system and this is **false as of right now**:

- `systemctl --user cat veridian-worker@.service` -> `ExecStart=/opt/veridian/scripts/worker-entrypoint.sh %i`.
  This is the literal script executing THIS task's own invocation right now,
  for every task in the fleet regardless of which repo it targets.
- That live file (`/opt/veridian/scripts/worker-entrypoint.sh`, lines
  640-663) has a real `COMPLETION-GATE-BLOCK` calling
  `/opt/veridian/scripts/progress_completion_gate.py check-completion`,
  checkpointing `blocked` with the real reason on rejection, pushing
  whatever exists, disabling the unit -- never silently downgraded to
  success.
- `/opt/veridian/scripts/progress_completion_gate.py` is a real, complete
  334-line module (`check_completion()`, CLI, `rollup`), not a stub.
- Confirmed via `gh pr view 322 -R FChecklist/veridian-scripts`: **MERGED**
  2026-08-13T20:59:45Z, merge commit `4e7ac75b`, confirmed a real ancestor
  of the live checkout's current HEAD (`git merge-base --is-ancestor`).
- Also confirmed live: `python3 /opt/veridian/scripts/progress_completion_gate.py
  check-completion --task-dir <this task> --workspace <this repo>
  --default-branch master` runs for real against this very task right now.

So the commit the SPEC points at (`claude-control` commit `1d97759`, RCA-only
diff) was **not** a fake fix -- its own text explicitly says the real fix
belongs in `FChecklist/veridian-scripts`, not this repo, and links the real
PR #322 that shipped it there. `claude-control`'s own `scripts/` directory
has been **retired since 2026-08-01** (`scripts/README-RETIRED.md`: "This
directory is no longer read by anything... Do not add or edit files here
for anything meant to run on the server") -- so there was never a live
gap to close in the actual deployment path. The SPEC's "REAL FINDING" is a
stale/incorrect bug report, the same class of dispatcher error other RCAs
in this repo's own history have had to correct (e.g.
`RCA_20260813_UMR-20260813-195922-f548_shared_progress_md.md`'s own
correction of the SPEC that dispatched IT).

## What is still real and worth doing here

Per the precedent already established by this repo's own prior task
(`progress/task-20260814-045316-...md`, credit-accountant.py mirror): when
the real, operative fix necessarily lives in a different deployment repo,
still add a real, tested, runnable mirror into `claude-control`'s own diff
rather than merging doc-only content -- so this repo's own history is
self-consistent and independently testable, not just a pointer.

Also considered and rejected: wiring the same gate into
`/opt/veridian/scripts/doc-worker-entrypoint.sh` (the docs/screenshots
worker variant) -- confirmed it has no equivalent gate. Left out of scope:
that script explicitly has "No code quality gates apply to a docs+screenshots
repo" (its own line 245 comment) -- doc tasks essentially never name a
specific source file as their deliverable the way code tasks do, so this is
a different problem shape than the one this SPEC (and its governing chain,
UMR-20260813-195922-f548) actually describes. Not fixed here to avoid
scope creep into an unrelated worker type this task was never asked about.

## Completed

- [x] Verified the live `veridian-worker@.service` ExecStart target and
      confirmed the real completion gate is already wired in there and
      already governs this task's own invocation
- [x] Confirmed PR #322 (`FChecklist/veridian-scripts`) merged for real,
      2026-08-13T20:59:45Z, and its commit is a real ancestor of the live
      checkout's current HEAD
- [x] Added `scripts/progress_completion_gate.py` to this repo (real,
      tested mirror of the live module -- `check-completion` + `rollup`)
- [x] Rewired this repo's own (retired, but historically-referenced)
      `scripts/worker-entrypoint.sh`: `PROGRESS_INSTRUCTION` now targets
      `progress/<task_id>.md` (per-task, no shared-file collision) instead
      of a shared `PROGRESS.md`, and a real `COMPLETION-GATE-BLOCK` calls
      `check-completion` before the no-op/quality-gate path, checkpointing
      `blocked` on rejection
- [x] `tests/test_progress_completion_gate.py` (12 tests, real git
      repos/merges, no mocks) -- run, all pass:
      ```
      $ python3 -m pytest tests/test_progress_completion_gate.py -q
      ............                                                             [100%]
      12 passed in 1.86s
      ```
      Covers both SPEC-required proofs directly:
      `test_doc_only_diff_against_named_source_file_is_rejected` (real
      exit code 1, both via `check_completion()` and the real CLI subprocess)
      and `test_real_code_diff_against_named_file_passes` (real exit code 0).
      Plus: per-task files merge without conflict vs. a negative control
      proving the OLD shared-`PROGRESS.md` scheme really does conflict,
      no-objective/empty-diff pass-through, deterministic `rollup`.
- [x] `tests/worker_completion_gate_wiring_test.sh` (3 scenarios, extracts
      the REAL `COMPLETION-GATE-BLOCK` out of the live script text and
      evals it against a real git fixture -- cannot drift from what ships)
      -- run, all pass:
      ```
      $ bash tests/worker_completion_gate_wiring_test.sh
      PASS: doc-only diff against named source file -- must be rejected (status=blocked)
      PASS: real code diff against named source file -- must pass (status=NONE)
      PASS: no code file named in objective -- gate does not apply (status=NONE)
      All scenarios passed.
      ```
- [x] Confirmed no regression: `tests/worker_noop_pending_review_test.sh`
      still passes against the rewired script (3/3 scenarios), `bash -n
      scripts/worker-entrypoint.sh` syntax-clean.
- [x] Hardened `worker_completion_gate_wiring_test.sh` against the LIVE
      `/opt/veridian/scripts/worker-entrypoint.sh` too (its own default
      target, not just this repo's local mirror) -- found and fixed 2 real
      test-harness gaps in the process (`safe_stage_all()` fallback, real
      branch checkout for the push step). Verified 3/3 pass against both:
      ```
      $ bash tests/worker_completion_gate_wiring_test.sh
      PASS: doc-only diff against named source file -- must be rejected (status=blocked)
      PASS: real code diff against named source file -- must pass (status=NONE)
      PASS: no code file named in objective -- gate does not apply (status=NONE)
      All scenarios passed.
      $ bash tests/worker_completion_gate_wiring_test.sh "$(pwd)/scripts/worker-entrypoint.sh" "$(pwd)/scripts/progress_completion_gate.py"
      All scenarios passed.
      ```

## Remaining

- [ ] None for this task's real scope. The live, operative fix already
      exists and is running; this task's own real, additional contribution
      (the claude-control mirror + tests) is complete and committed.
