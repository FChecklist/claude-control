# task-20260814-034453-duplicate-guard-false-refuses-legitimate

GOVERNING CHAIN: P1 UMR-20260806-171945-5767. UMR for this task:
UMR-20260814-034424-ded4.

Real code: `superboss-register.py` (repo `FChecklist/veridian-scripts`) --
`extract_target_identifiers()` / `find_target_identifier_duplicate()`, the
`check-target-identifier-duplicate` CLI called by `dispatch-owner-task.sh`.

## Completed

- [x] Located the exact code: `extract_target_identifiers()` and
      `find_target_identifier_duplicate()` in `superboss-register.py`
      (`FChecklist/veridian-scripts`), called from
      `dispatch-owner-task.sh` step 1b via
      `check-target-identifier-duplicate`. Confirmed a PRIOR, narrower,
      already-merged fix exists (PR #346, "stop treating cited meta-tool
      script names as real dedup target identifiers") -- a different,
      earlier real incident (bare `resource_governor.py`/
      `superboss-register.py` mentions), not the scope-vs-evidence defect
      this task targets.
- [x] Checked for an existing open PR attempting this same fix (item 5).
      Found PR #342 ("fix(resource_governor): duplicate guards over-block
      brand-new/resumed work") -- confirmed via diff this is a DIFFERENT
      bug family (`resource_governor.py`'s Stage 4/5/6 PR-title-overmatch
      guard + `_orchestrator_reuse_verdict_gate()`'s cross-type
      wiring_registry match), not the `extract_target_identifiers()`
      scope-vs-evidence defect. PR #342 is itself stale/superseded: its
      real content already landed via the equivalent, later PR #345
      (merged 2026-08-14T02:07:29Z, see
      `progress/task-20260814-015201-*.md`), so PR #342 is now
      `mergeable=false` (dirty) against `main` and safe to leave alone --
      not this task's file, not this task's fix, and already redundant.
      Searched explicitly for any open PR touching
      `extract_target_identifiers`/`find_target_identifier_duplicate` or
      scope/escape-hatch language: none found. No conflicting open PR for
      this fix -- proceeding with a new PR, not a competing one.
- [x] Implemented the scope-aware matcher in `superboss-register.py`:
      - New `_TARGET_ID_ESCAPE_HATCH_RE`: inline
        `[NOT-A-TARGET: ...]` / `[EVIDENCE-ONLY: ...]` /
        `[OUT-OF-SCOPE: ...]` / `[PRIOR-CONTEXT: ...]` markers, stripped
        unconditionally before extraction -- the explicit,
        machine-readable "this identifier is evidence, not my target"
        escape hatch (item 2).
      - New `_split_labeled_sections()` + `_TARGET_ID_SECTION_HEADER_RE`:
        splits prompt text at recognized `TARGET:`/`SCOPE:`/
        `OUT OF SCOPE:`/`PRIOR CONTEXT:`/`EVIDENCE(-ONLY):`/
        `NOT-(A-)TARGET:` headers.
      - `extract_target_identifiers()`: if the text declares an explicit
        `TARGET:`/`SCOPE:` section, extraction is restricted to that
        section's content ONLY (item 1's primary directive -- title and
        an explicit target/scope section, nothing else). If not, every
        `OUT OF SCOPE:`/`PRIOR CONTEXT:`/`EVIDENCE(-ONLY):`/
        `NOT-(A-)TARGET:`-labeled section is stripped before the
        full-text fallback scan (item 1's "at minimum" bar), preserving
        original behavior for prompts with no explicit structure (the
        real 2026-08-13 same-PR-branch collisions this guard exists for
        used none of this structure).
      - New `_target_identifiers_for_title_and_prompt()`: title and
        prompt are now extracted SEPARATELY and unioned, not
        concatenated first -- the title always counts in full (it is the
        field that declares the target), never at the mercy of whether
        the prompt happens to open a `TARGET:` section (which would
        otherwise silently drop all pre-header prose, including the
        title if it had been concatenated first). Both
        `find_target_identifier_duplicate()`'s `my_ids` (the incoming
        dispatch) and `row_ids` (each candidate queued/running row) now
        go through this helper.
- [x] Ran the pre-existing `tests/test_target_identifier_dedup.py` (14
      tests) unchanged against the fix -- all still pass, confirming no
      regression to the original behavior for unstructured prompts.
      Real output:
      ```
      14 passed in 12.53s
      ```
- [x] Added `tests/test_target_identifier_scope_aware_dedup.py`, 8 new
      real tests, all run to real exit 0:
      - `test_scenario1_umr_cited_as_prior_context_now_allowed` +
        baseline sanity check -- reconstructs real refusal #1 (disk-fix
        UMR id cited only under an explicit `PRIOR CONTEXT:` section, no
        `TARGET:` header at all -- the fallback-exclusion path) -- now
        ALLOWED.
      - `test_scenario2_shared_evidence_path_outside_target_section_now_allowed`
        -- reconstructs real refusal #2 (shared worker task-directory
        evidence-file path cited only in an `EVIDENCE:` section, real
        target declared via `TARGET:` -- the section-restriction path)
        -- now ALLOWED.
      - `test_scenario3_script_cited_only_for_a_line_number_now_allowed`
        + pure-function escape-hatch check -- reconstructs real refusal
        #3 (worker entrypoint script cited only via an inline
        `[EVIDENCE-ONLY: ...]` escape hatch on the stored row's side,
        while the new dispatch's own real `TARGET:` legitimately
        includes that same script) -- now ALLOWED.
      - `test_true_duplicate_still_refused_unstructured_prompt` -- the
        real 2026-08-13 same-PR-branch collision shape (no structure at
        all) -- still REFUSED.
      - `test_true_duplicate_still_refused_with_explicit_target_sections`
        -- both sides use the new `TARGET:`/`SCOPE:` structure and
        genuinely share the same target PR -- still REFUSED (proves the
        scoping mechanism doesn't accidentally hide a real duplicate).
      - `test_title_always_counts_even_when_prompt_has_a_target_section_elsewhere`
        -- title-only match still REFUSED even though the prompt has its
        own unrelated `TARGET:` section.
      Real output:
      ```
      8 passed in 1.94s
      ```
- [x] Also updated `dispatch-owner-task.sh`'s step-1b comment/refusal
      message to document the new scope-aware behavior and the
      `[EVIDENCE-ONLY: ...]`/`[NOT-A-TARGET: ...]` escape hatch for
      dispatchers hitting a refusal (doc-only, no behavior change beyond
      the message text).
- [x] Caught and corrected a real mistake: the shared repo checkout at
      `/opt/veridian/repos/veridian-scripts` had a DIFFERENT, unrelated,
      in-progress branch checked out (`fix/lifetime-invocation-counter-
      preflight-rejection`, one commit ahead of `origin/main` --
      explicitly another task's work, invocation accounting, one of this
      task's own SCOPE LIMITS). First full-suite run (729 passed, 4
      failed) was accidentally run against that foreign branch. Moved my
      changes (via `git stash`) onto a fresh branch created from
      `origin/main` (`badf5a4`, confirmed the real current main tip) --
      `fix/scope-aware-target-identifier-dedup` -- and re-ran the
      target-identifier test files clean there (22/22 passed). Full
      regression suite re-running now on the correct base.
- [x] Confirmed, on the pre-fix code (`git stash`), that the same 4
      failures occur identically -- proving they are pre-existing and
      unrelated to this change, not a regression it introduces:
      `test_timer_is_really_enabled_and_active` (env-dependent systemd
      timer check, already documented pre-existing in PR #345's own
      notes), `test_supervisor_refuses_gitlink_only_branch_exact_
      pr146_170_191_repro`, and both
      `test_supervisor_no_op_branch_guard.py` tests (real unrelated
      `KeyError: 'service'` in `veridian-task.py`'s
      `sync_controller_entry`, nothing to do with duplicate-guard code).

- [x] Full-suite regression result on the correct `origin/main`-based
      branch: `4 failed, 729 passed in 199.47s` -- the same 4
      pre-existing/unrelated failures as the (mistaken foreign-branch)
      first run, confirmed identical.
- [x] Committed, pushed `fix/scope-aware-target-identifier-dedup`
      (based on real `origin/main` tip `badf5a4`), opened
      https://github.com/FChecklist/veridian-scripts/pull/350 with real
      pasted test output in the body. Confirmed
      `mergeable=true`/`mergeable_state=clean`.

## Remaining

- [ ] Get a real independent Tier-1 audit at the PR's head SHA, merge
      only on a fresh `AUDIT: PASS`, per this repo's standing merge
      convention (not this task's own job to self-merge without one).
- [ ] Run `agent_work_briefing.py record-completion` for
      `UMR-20260814-034424-ded4` once merged.

## Terminal status: PR OPEN, awaiting independent audit + merge

Real code fix landed in `superboss-register.py` (`extract_target_
identifiers()`/`find_target_identifier_duplicate()`) +
`dispatch-owner-task.sh` (doc), real new test file (8/8 passing,
reconstructing all 3 real false-positive scenarios as now-ALLOWED and a
true-duplicate control as still-REFUSED), pre-existing 14/14 tests
unaffected, full suite 729 passed / 4 pre-existing-unrelated failures
(verified via `git stash` on the same branch). PR #350 open, clean,
mergeable. Checked for and correctly distinguished from PR #342 (a
different, already-superseded bug fix) -- no conflicting open PR existed
for this fix, so a new PR was the right call, not a competing one.
