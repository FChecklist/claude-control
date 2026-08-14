# Task: Tier-1 audit — the never-audited duplication-blocked-task-identity PR

Target: FChecklist/claude-control PR #223 "fix(resource-governor): retire
duplication-blocked task identities" — head SHA 70d7841c35be5365e546aacd9078d6f95c1036ba.
0 reviews, 0 comments at task start. Touches scripts/resource_governor.py
(narrow stop-work exemption file, requires unusual care).

## Completed
- [x] Confirmed PR #223 identity: OPEN, head 70d7841c35be..., MERGEABLE/CLEAN, 0 reviews/0 comments
- [x] Pulled full diff (files: progress/task-20260814-080733-...md, scripts/resource_governor.py, scripts/superboss-register.py, tests/test_resource_governor.py)
- [x] Read full diff in detail: adds `MAX_DUPLICATE_ATTEMPTS_PER_IDENTITY`
      (env-overridable, default 20) + terminal status `RETIRED_STATUS =
      "retired_max_attempts"`; `submit()` now counts every
      `rejected_duplicate` as a real consumed attempt against its exact
      `task_identity`, retires the identity permanently once the cap hits,
      and short-circuits (no new umr_tasks row) on any further submission
      for an already-retired identity. `superboss-register.py` widens the
      `umr_tasks.status` CHECK via a real in-place table rebuild
      (`_migrate_umr_status_check`), reading the table's own stored CREATE
      TABLE SQL so every prior column survives untouched.
- [x] Checked out PR head 70d7841c35be5365e546aacd9078d6f95c1036ba locally
      (fresh clone + `git fetch origin pull/223/head`), confirmed SHA match.
- [x] Ran tests/test_resource_governor.py: **18/18 passed, exit 0**. Ran
      full repo suite (`pytest tests/`, excluding 2 scripts unrelated to
      this PR): **159 passed**, 2 pre-existing failures
      (`hold_for_signoff_test.py`, `test_merge_execution.py` /
      `supervisor_merge_detection_test.sh`) confirmed present on `master`
      baseline too (unrelated subsystem: owner-signoff auto-merge gating,
      not resource_governor/umr_tasks) -- not a regression from this PR.
- [x] Real CLI execution (isolated sandbox, throwaway sqlite DB, real
      `python3 resource_governor.py --submit`/`--query-umr`, not just
      pytest): confirmed a brand-new task_identity is accepted (`queued`),
      a genuinely duplicate identity is rejected (`rejected_duplicate`,
      attempt-counted), retirement fires exactly at the configured cap
      (drove cap=5 to `retired_max_attempts`), a post-retirement
      resubmission is refused with **zero new umr_tasks rows written**
      (row count before==after), and `--query-umr` returns correct,
      complete rows throughout.
- [x] Verified no over-blocking: confirmed via source
      (`find_active_umr_by_identity`/`query_umr_tasks` both use exact SQL
      `WHERE task_identity=?`, no prose/PR-title parsing anywhere in this
      change's call path -- unlike the unrelated, already-fixed
      `find_pr_for_task_identity`/Stage 4-6 duplicate-PR-guard defect
      class in a different repo/function this PR does not touch) AND by
      real execution: a second, unrelated task_identity submitted
      interleaved with the retiring identity stayed `queued`, completely
      unaffected.
- [x] Real migration test against a genuine pre-existing (production-
      shaped) DB: built the OLD (pre-PR, merge-base) schema with 3 real
      pre-existing rows across different statuses, then ran the NEW
      `_ensure_umr_table` against that same DB file. All 3 rows survived
      intact, CHECK constraint correctly widened to allow
      `retired_max_attempts`, FTS5 index rebuilt and functional, a bogus
      status is still correctly rejected by the CHECK, and a second
      `_ensure_umr_table` call is a true no-op (idempotent). This exact
      pre-existing-DB migration path had no dedicated automated test in
      the PR's own suite -- closed that verification gap manually.
- [x] Re-checked PR #223 immediately before posting: head SHA unchanged
      (70d7841c35be5365e546aacd9078d6f95c1036ba), `mergeable=MERGEABLE`,
      `mergeStateStatus=CLEAN`.
- [x] Posted `AUDIT:PASS` comment on PR #223 quoting head SHA, listing
      files audited and checks executed:
      https://github.com/FChecklist/claude-control/pull/223#issuecomment-5293617307
- [x] Merged PR #223 (`--merge --delete-branch`). Merge commit
      `d4ab44b59d0d277aba66b6442db75648937ad22a`, merged
      2026-08-14T13:05:15Z, head SHA at merge time verified unchanged
      (70d7841c35be5365e546aacd9078d6f95c1036ba).
- [x] Recorded completion via `agent_work_briefing.py record-completion`
      for UMR-20260814-125542-c8ce.

## Remaining
- [ ] (none)

## Terminal status: DONE
