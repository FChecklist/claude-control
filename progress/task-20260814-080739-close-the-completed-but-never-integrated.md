# task-20260814-080739-close-the-completed-but-never-integrated

SPEC scope: the 10 `umr_tasks` rows in `status=completed_unmerged` submitted
2026-08-14T01:51-07:47Z (of 120 rows returned by `resource_governor.py
--query-umr --limit 120`, confirmed by re-filtering the same window from a
fresh `--status completed_unmerged` query). Real code: fix lands in
`FChecklist/veridian-scripts` (that is where `superboss-register.py`, the
real system of record for `umr_tasks`, actually lives -- confirmed via
`DEFAULT_OCID_RESOLVER_REPO_LOCAL_PATHS` and this task's own progress-gate
carve-out for genuinely cross-repo fixes, `progress_completion_gate.py`
lines ~92-100).

## Completed

- [x] Enumerated the 10 real `completed_unmerged` rows in scope (window
      01:51-07:47Z), pulled each row's full `outputs_json` (`--full`), and
      classified every one against a real, live git/gh check (never
      trusted the DB row's own claim):
      - `UMR-20260814-071820-220d` (compliance-tracker, commit `f84662c`):
        branch diff = `ai-os/boss/ACTIVE-CLAIMS.yaml` + its own RCA report
        `.md` only. **No real code.**
      - `UMR-20260814-070059-6484` (veridian-scripts, commit `05c33ed`,
        PR #360): branch diff = real code
        (`progress_completion_gate.py` +169, `tests/test_progress_completion_gate.py`
        +193, `worker-entrypoint.sh` +15). PR OPEN, `mergeStateStatus=CLEAN`,
        but latest posted audit comment is `AUDIT: FAIL`. **Real code,
        correctly still pending -- left alone.**
      - `UMR-20260814-061740-6655` (compliance-tracker, commit `bd85e54`):
        branch diff = `PROGRESS.md` (compaction) + its own RCA report `.md`
        only. **No real code.**
      - `UMR-20260814-061727-ece3` (compliance-tracker PR #1131, commit
        `a527b835b`): PR state=OPEN, `gh pr diff` = PROGRESS.md-only RCA
        conclusion text. **No real code** (the RCA finding itself --
        UMR-20260808-215121-1e87 correctly killed -- stands; it just never
        produced a mergeable artifact).
      - `UMR-20260814-060138-285e` (claude-control, commit `b8f0ebb`,
        PR #214): branch diff = real committed `.py`/`.sh` files, but
        almost entirely one-off `.triage/` scratch/analysis output (JSON
        dumps, throwaway scripts), not application code. PR OPEN,
        `mergeStateStatus=CLEAN`, latest posted audit is `AUDIT: FAIL`.
        **Real code exists, correctly still pending -- left alone** (not
        my call to force a merge without a fresh AUDIT:PASS, and not a
        "no real code" case either since real committed files do exist).
      - `UMR-20260814-054218-9475` (claude-control, commit `5e9f6dea`,
        PR #209): **status-machine bug, not a fake/real-code question** --
        PR #209 was already `state=MERGED` at 07:16:24Z (`headRefOid`
        exactly matches the row's own recorded commit), i.e. `git
        merge-base --is-ancestor 5e9f6dea origin/master` succeeds live.
        The row was simply never re-checked after its PR merged.
      - `UMR-20260814-051554-3126` (compliance-tracker PR #1128, commit
        `72d868f6a`): same shape as `-ece3` above -- PR OPEN,
        PROGRESS.md-only diff. **No real code.**
      - `UMR-20260814-034225-3392` (claude-control, commit `bde05d2a`):
        branch diff = real code, `scripts/repair_invocation_counters.py`
        (+141), but that commit's own message pointed at the real fix
        living in a separate PR: veridian-scripts **PR #348**
        (`worker-entrypoint.sh` +69/-8 + a new test file), head SHA
        `820ed667465f61f609495faba532e61fd9eb34ed`. **Real code, real open
        PR.**
      - `UMR-20260814-021624-579f` (compliance-tracker, commit `df6cfbd`):
        branch diff = its own RCA report `.md` only, zero PROGRESS.md
        change even. **No real code.**
      - `UMR-20260814-021610-0ccf` (compliance-tracker, commit `e6603c1`):
        branch diff = 1-line `PROGRESS.md` + its own RCA report `.md`
        only. **No real code.**
- [x] Drove the one real, mergeable, ready row to a real merge:
      **veridian-scripts PR #348** -- confirmed `mergeStateStatus=CLEAN`,
      confirmed a real, freshly-posted `AUDIT PASS` comment matching the
      PR's *current* `headRefOid` exactly (`820ed667...`), body describes
      real test execution (shipped test `34 passed, 0 failed`; independent
      auditor-authored harness `9 passed, 0 failed`, both `exit 0`) --
      **merged for real** (`gh api .../pulls/348/merge`, merge commit
      `363702c78d4234dfc3c17cb247d188e85a39f0b1`, merged
      2026-08-14T08:14:53Z). Not self-certified -- the AUDIT:PASS was
      already posted by an independent prior auditor pass before this
      sweep ever touched the PR.
- [x] Corrected the 2 rows whose real disposition the DB had wrong, via
      `superboss-register.py mark-umr-terminal`:
      - `UMR-20260814-034225-3392` -> `completed` (`--commit-sha
        820ed667...` / `--pr-number 348` / `--repo veridian-scripts`),
        reflecting the real merge just performed.
      - `UMR-20260814-054218-9475` -> `completed` (`--commit-sha
        5e9f6dea...` / `--pr-number 209` / `--repo claude-control`),
        correcting the stale-status bug found above.
- [x] Marked the 6 genuinely no-real-code rows terminal
      (`mark-umr-terminal --status failed --reason "..."`, each reason
      citing the exact branch/PR and `diff --stat` evidence gathered
      above) so they stop being counted as pending integration:
      `UMR-20260814-071820-220d`, `UMR-20260814-061740-6655`,
      `UMR-20260814-021624-579f`, `UMR-20260814-021610-0ccf`,
      `UMR-20260814-061727-ece3`, `UMR-20260814-051554-3126`.
- [x] **Fixed the underlying status machine** (SPEC step 4): root-caused
      *why* `UMR-20260814-054218-9475` went stale -- `superboss-register.py`'s
      `reconcile_umr_status_against_pr()` (the one function that cross-checks
      a row's status against live PR-merge evidence) had `stale_statuses =
      {"queued", "dispatched", "running"}`, structurally excluding
      `completed_unmerged`. A row could be written `completed_unmerged`
      correctly (real commit, genuinely unmerged at that moment) and then
      never get re-checked once its PR actually merged -- the exact "silent
      dead end" the SPEC names. Added `completed_unmerged` to
      `stale_statuses` so `reconcile-umr-status --umr-id X --apply` now
      performs the same real promotion queued/dispatched/running rows
      already got. Real diff + real test in **veridian-scripts PR #361**
      (`fix/completed-unmerged-reconcile-stale-statuses`,
      `test_reconcile_umr_status_completed_unmerged.py`, 5 cases, `PASS`,
      exit 0; also re-ran the pre-existing `test_umr_completion_percentage.py`
      to confirm no regression, `PASS (16 checks across 13 scenarios)`,
      exit 0). Not merged by this sweep -- needs its own independent
      AUDIT:PASS first, same rule this whole task exists to enforce.
- [x] `record-completion` written to `agent_work_briefing.py` for this
      task's own UMR (UMR-20260814-080349-639e).

## Remaining

- [ ] Not this task's scope, flagged only: `UMR-20260814-070059-6484`
      (veridian-scripts PR #360) and `UMR-20260814-060138-285e`
      (claude-control PR #214) both have real code and open, mergeable,
      conflict-free PRs, but their latest posted audit is `AUDIT: FAIL` --
      correctly left as `completed_unmerged` pending a real fix + a fresh
      independent audit pass; not mine to force through without one.
- [ ] veridian-scripts **PR #361** (this task's own status-machine fix)
      needs a real, independent `AUDIT:PASS` against its current head SHA
      before anyone merges it -- same rule applied to every other row
      above.
- [ ] Broader sweep beyond this 10-row window: 110 more `completed_unmerged`
      rows exist across the full `umr_tasks` history (older than
      2026-08-14T01:51Z) that this task's SPEC scope did not cover --
      flagged for a future task, not silently dropped.
