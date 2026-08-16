# PROGRESS -- task-20260814-060159-triage-and-dispose-the-pre-2026-08-08-st

SPEC: Triage and dispose of the stale open PR backlog on FChecklist/veridian-scripts
and FChecklist/claude-control, scoped strictly to PRs last updated before 2026-08-08.
Classify each as superseded (proven present on origin main via a named commit),
obsolete (proven false premise / missing target, via a real check), or still-real
(unique unmerged value). Close superseded/obsolete with a proving comment; rank
still-real ones with concrete reasons. No closures on age alone, no fake-fix gate.

## Methodology (real, deterministic, no guessing)
- Cloned both repos locally (`.triage/vs_repo` for veridian-scripts; the task
  workspace itself for claude-control), fetched every open PR's head ref, computed
  `git merge-base` + full-tree diff vs `origin/main`/`origin/master`.
- "Superseded" proof standard: every real (non-test-name) function/class defined by
  the PR's diff already exists, by name, in the current main-tip version of that
  same file (verified via AST-level `def `/`class ` extraction + content compare),
  AND a real commit that introduced that content into main is named via
  `git log --diff-filter=A` / `git log -S<token>`.
- "Duplicate/subset" proof standard: PR head commit is byte-identical to, or a real
  git ancestor of, another still-open PR's head commit (`git merge-base --is-ancestor`),
  proving zero unique value beyond the sibling PR.
- "Obsolete" proof standard (PROGRESS.md-only PRs): the repo structurally moved off
  the shared root `PROGRESS.md` model (commit `1c363b6`, veridian-scripts main,
  "fix(worker-entrypoint): per-task progress files + real completion gate, kill the
  shared-PROGRESS.md conflict/empty-fix hole"), confirmed live by `worker-entrypoint.sh`
  now targeting `progress/${TASK_ID}.md` and root `PROGRESS.md` being a rotating
  single-task scratch file (currently holding an unrelated, much later task). A PR
  whose *entire* diff is a `PROGRESS.md` edit for a long-superseded task checkpoint
  carries no code and cannot be merged without regressing the current file.
- Everything else: left open, listed in the ranked "still real" tables below with a
  concrete per-PR reason (what unique function/file/capability it carries that is
  provably absent from main).

## Completed
- [x] Scoped both repos to PRs last updated before 2026-08-08 (real query via
      `gh api --paginate`, not the stale evidence counts): veridian-scripts = 59
      qualifying open PRs (not 30 -- 2 spec-listed numbers, #273/#276, are excluded
      because they were actually updated on/after 2026-08-08, confirmed live);
      claude-control = 11 qualifying open PRs (matches spec's list exactly).
- [x] Cloned veridian-scripts, fetched all 59 PR head refs, ran deterministic
      merge-base/diff/function-match classification against `origin/main`.
- [x] Fetched all 11 claude-control PR head refs in this workspace, ran the same
      classification against `origin/master`.
- [x] Identified 26 veridian-scripts PRs whose entire diff is a `PROGRESS.md`-only
      edit -- OBSOLETE, proven by commit `1c363b6` (shared-PROGRESS.md model
      structurally replaced).
- [x] Identified 5 veridian-scripts PRs fully superseded by named main commits
      (100% of their real functions/files already present under the same names):
      #169, #81, #84, #83, #108.
- [x] Identified 2 veridian-scripts PRs that are exact-duplicate/strict-subset of a
      still-open sibling PR (zero unique value beyond the sibling): #216 (dup of
      #213), #207 (subset of #213).
- [x] Identified 1 claude-control PR that is a strict subset of a still-open sibling
      PR: #113 (subset of #116, confirmed via `git merge-base --is-ancestor`).
- [x] Closed all 33 disposed veridian-scripts PRs with proof-citing comments.
- [x] Closed the 1 disposed claude-control PR with a proof-citing comment.
- [x] Wrote ranked still-real lists (26 veridian-scripts, 10 claude-control) with
      concrete per-PR reasons below.

## Remaining
- [ ] None -- triage complete. PM/owner should review the ranked still-real lists
      below and decide merge order; this task does not merge anything (out of scope).

## Disposed: veridian-scripts (FChecklist/veridian-scripts)

### Superseded (change already present on origin/main)
| PR | Title | Proving commit |
|---|---|---|
| #169 | fix(hooks): real PreToolUse guard rejecting unbounded find/walks | `hooks/find_root_walk_guard.py` + `tests/test_find_root_walk_guard.py` introduced by `86a2a817` (2026-08-08, "feat: harden stop-work-order gate + land master_issue_tracker CRUD + find_root_walk_guard hook"), refined since by `055b6ca7` (2026-08-08, PR #277 round-9 tier1 fix). Every function PR #169 defines (`evaluate`, `_is_unbounded`, `_resolve_root`, etc.) exists under the same name on main today. |
| #81 | feat(OCID-020 GTM): category 7 (regression testing) | `gtm_check_regression_testing.py` (only remaining diff file) is byte-for-function-identical to main's version, introduced by `8349c1f6` (2026-08-06 12:54:50Z, "feat(gtm-checks): build 8 missing re-runnable check scripts, make TEST_SCRIPT_BUILD real"). |
| #84 | feat(OCID-020 GTM): category 9 (performance) + 24 (lighthouse) | `gtm_check_performance_testing.py` + `gtm_check_lighthouse_audit.py`, both fully present, same commit `8349c1f6`. |
| #83 | Verify no OCID canonical registry corruption occurred | `audit_ocid_canonical_registry.py`'s production code (`plan_for_ocid`, `_load_sbr`, `main`) is 100% present on main, introduced by `768fd6e2` (2026-08-05, "feat(OCID-068 Phase 2): registry schema, DB-enforced completion gate... anti-fabrication audit scripts"). Only 2 new test-function names remain, no production code left to merge. |
| #108 | Extend superboss-register.py with pm_decisions_pending insert/resolve | Every function this PR defines already exists on main, introduced by `d69a40b4` (2026-08-06 03:29:30Z, "feat: insert_pm_decision_pending()/resolve_pm_decision_pending() in superboss-register.py") and extended by `daf9d3ec` (2026-08-06, PR #110, owner-proposal lifecycle). |

### Duplicate / strict subset of a still-open sibling PR (zero unique value)
| PR | Title | Proof |
|---|---|---|
| #216 | Precise correction based on real direct study... | Head commit `645a8070` is **byte-identical** to open PR #213's head commit (same SHA, same tree `7c95416b`). Verbatim duplicate. |
| #207 | feat(orchestrator): close 3 real gaps -- submission contract... | PR #213's branch explicitly contains `git merge PR #207 branch (unified_orchestrator.py base) into this amendment task` -- confirmed via `git merge-base --is-ancestor refs/prs/207 refs/prs/213` = true. Every function #207 adds (`_ensure_task_audits_table`, `record_task_audit`, `unified_orchestrator.py`'s step_* functions) is a strict subset of what #213 already carries. |

### Obsolete (PROGRESS.md-only diff, premise structurally false)
Commit `1c363b6` (veridian-scripts main) moved every worker off the shared root
`PROGRESS.md` onto `progress/${TASK_ID}.md`, and added `progress_completion_gate.py`
which explicitly refuses to treat a `PROGRESS.md`-only diff as real completion
evidence. Root `PROGRESS.md` on main today (`# PROGRESS -- task-20260814-051552-...`)
has zero relationship to any of these PRs' content -- it has been overwritten dozens
of times since. Each PR below has **no file in its diff except `PROGRESS.md`**:

#24, #28, #74, #75, #80, #89, #94, #101, #113, #182, #183, #203, #209, #215, #219,
#220, #222, #223, #225, #226, #229, #236, #239, #240, #243, #267

(26 PRs total. Titles and individual close-comment text are in the closed PRs
themselves on GitHub -- each comment cites commit `1c363b6` by SHA.)

## Disposed: claude-control (FChecklist/claude-control)

| PR | Title | Disposition | Proof |
|---|---|---|---|
| #113 | phase_8 increment 1: DSPy decision + engine-ai-learning evidence | Strict subset of open PR #116 | #116's branch head (`2f0b755`) directly builds on #113's exact head commit (`006c5c4`) as its parent -- confirmed via `git merge-base --is-ancestor refs/prs/113 refs/prs/116` = true, and `ai-os/VERIDIAN_V2_PROMPT_LIFECYCLE_ENGINES_SCOPING_2026-07-27.md` content is byte-identical between the two. Merging #116 carries everything #113 offers plus a watchdog fix on top. |

## Still-real: veridian-scripts (26 PRs, ranked by concrete unique value)

1. **#213** (subsumes #207 and #216, both closed above) -- feat(orchestrator): mirrors 3 compliance-tracker
   patterns. Adds `unified_orchestrator.py` (whole new script, `step_*` pipeline: `step_validate_input`, `step_reuse_check`, `step_reverify`, `step_submission_contract`, `step_writeback`, etc. -- none exist on main in any form) plus `superboss-register.py` additions `_ensure_orchestrator_executions_table`, `_ensure_prompt_templates_table`, `_ensure_prompt_versions_table`, `_ensure_task_audits_table`, `register_prompt_template`/`resolve_prompt_template`, `record_orchestrator_execution`, `record_task_audit` -- a full prompt-template-versioning + execution-audit registry with zero prior art on main. Highest-value single PR in the backlog.
2. **#205** -- feat(superboss-register): capability graduation tracking. Adds
   `_ensure_capability_graduation_log_table`, `record_capability_graduation`,
   `list_capability_graduations`, `search_task_precedent`, `cmd_search_task_precedent`
   -- none present on main; directly extends the capability_registry the wiring
   briefing already leans on.
3. **#247** -- feat: real embedding/vector-similarity semantic search over
   capability_registry. `capability_semantic_search.py` is a whole new file
   (`embed_texts`, `cosine_similarity`, `cmd_search`, `cmd_reindex`) with zero
   overlap with anything on main -- the only semantic (non-keyword) capability
   search implementation that exists anywhere in this backlog.
4. **#200** -- feat(wiring-health-check): standing deterministic wiring health
   check. `wiring_health_check.py` is a whole new file (`run_all_checks`,
   `check_registries_reachable`, `check_gateway_pickup_path`,
   `check_external_agent_dispatch`, `check_pm_report_freshness`) plus
   `generate_pm_report_v3.py::get_wiring_health_check_section` -- not on main.
5. **#198** -- feat(pm-report): tracked-PR merge state + recent owner-UMR status
   section. `generate_pm_report_v3.py::get_pr_view`, `load_tracked_pr_list`,
   `get_tracked_pr_merge_state_section`, `get_recent_owner_umr_status_section` --
   none present on main; closes a real PM-report blind spot (this very backlog).
6. **#8** -- feat: entity/relation coordination graph in superboss-register.py.
   `_ensure_coordination_graph_tables`, `_get_or_create_entity`, `log_entity`,
   `log_relation`, `cmd_check_conflict` + new `backfill_active_claims.py` -- none
   on main.
7. **#61** -- feat(OCID Master Standard v6 Phase 2): lifecycle state machine +
   registry-integrity checksum baseline. 14 new functions
   (`transition_ocid_lifecycle_state`, `check_registry_integrity`,
   `_compute_ocid_registry_checksum`, `resume_ocid_lifecycle`, ...), none on main.
8. **#196** -- fix(resource-governor): `update_pm_decision_pending`/
   `cmd_update_pm_decision_pending` -- lets a pending PM decision row be amended,
   not just inserted/resolved. Not on main (the stale-queued aggregation part of
   this PR *is* already on main via `flag_stale_queued_tasks`, but this update
   path is not).
9. **#184** -- fix(dispatch): `_flag_stale_resume_for_pm`/`_resume_staleness_hours`
   in dispatch-tick.py, gates blind resume of hours-stale queued/interrupted tasks
   -- not on main (most of this PR's other functions are already there under the
   same names; this gate specifically is not).
10. **#65** -- feat: GTM check scripts for categories api/database/governance
    testing (`gtm_check_api_testing.py`, `gtm_check_database_testing.py`,
    `gtm_check_governance_testing.py`) -- unlike categories 7/9/24 (#81/#84,
    already superseded), these three categories have **no** matching script on
    main at all.
11. **#78** -- feat(OCID-020 cat19): `sqlite_daily_backup.py` + systemd timer/service
    + tests -- whole new file, not on main; only sqlite backup automation in the
    backlog.
12. **#204** -- test: first real batch of load-bearing script tests (47/148 ->
    57/150 baseline). 7 whole new test files targeting
    `worker-entrypoint.sh`/`resource_governor.py tick loop`/`recover_failed_workers.py`
    guard logic that currently has zero coverage on main.
13. **#79** -- feat(OCID-020 GTM): category 6 e2e testing helper `_flatten_titles`
    in `gtm_check_e2e_testing.py` is the only unmatched piece (category 5 UI
    testing is otherwise already on main) -- small but real, unmerged.
14. **#62** -- feat: gtm_certification_categories schema + 25-row seed migration.
    Main reads/writes this table everywhere (`generate_pm_report_v3.py`,
    `gtm_write_category_result.py`, `superboss-register.py`) but **no script in
    main's history ever creates the table** (only test fixtures do) -- this is
    the only candidate migration script for how that table came to exist in
    production. Needs a live-DB check before merge/close (may already have been
    run by hand against production without the code ever landing) -- flagged,
    not closed, per "never guess."
15. **#72** -- audit_ocid_canonical_registry.py gains `_bounded_for_storage` (caps
    pathologically large audit evidence before storage) -- the one function in
    this PR not already on main (rest is the same content #83, closed above,
    duplicates).
16. **#118** -- fix: repair_file_inventory_20260806.py, a one-time corruption-repair
    script for an incident dated 2026-08-06. Not on main. Likely stale (8 days of
    further commits since, no evidence the underlying corruption is still live)
    but no commit proves the incident was independently resolved -- flagged low
    priority, not closed.
17. **#190** -- chore: preserve session_metadata_sync.py + sweep_awaiting_approval.py
    "before scripts-dir reconciliation." No "scripts-dir reconciliation" commit
    was found on main, so the feared deletion this PR guards against may never
    have happened -- but that doesn't prove the premise false either way.
    Flagged, not closed.
18. **#232** -- test(quality-gate): tests/test_build_lock_spin_bound.py, new test
    file proving build-lock requeue is bounded. Not on main.
19. **#233** -- SPEC_VERIFICATION doc: merges must run inside a real worker unit,
    not the interactive session. Standalone finding doc, archival value.
20. **#244** -- FINDING doc: wiring_registry re-escalation loop SPEC is
    false-premise (5th time this exact false alarm was raised) -- archival/
    institutional-memory value, prevents a 6th re-litigation.
21. **#266** -- capability_registry record for the real 965-issue resolution
    matrix (`umr_5767_issue_resolution_matrix_capability_record.json`) -- new
    file, not on main.
22. **#60** -- OCID-069 independent re-verification report -- standalone doc,
    archival value only.
23. **#71** -- OCID-068 UTR/UMR taxonomy independent re-verification -- standalone
    doc, archival value only.
24. **#90** -- OCID-020 PR #954 adoption-cycle re-verification -- standalone doc,
    archival value only.
25. **#93** -- OCID-020 GTM-schema standalone-task re-verification -- standalone
    doc, archival value only.
26. **#99** -- owner-directive report on sqlite3 recovery (stopped) + pr_url.txt --
    standalone doc, archival value only.

## Still-real: claude-control (10 PRs, ranked by concrete unique value)

1. **#102** -- Add `plan_backlog_completion.py` + `execute_backlog_plan.py`: real
   backlog dedup + PR-state planner, with 2 fixture-backed dedup test suites. Whole
   new capability, zero overlap with main -- directly relevant to *this very task*
   (backlog triage/disposal tooling). Highest-value PR in this repo's backlog.
2. **#116** -- (supersedes/contains #113, closed above) Fix watchdog step_2
   known_fixes gating + wire skip_escalation_when_active + register DSPy decision
   scoping in MASTER_INDEX.yaml. Touches `scripts/veridian-task-watchdog.py`
   (exists on main, real behavioral fix not present there) plus the phase-8 scoping
   doc from #113.
3. **#98** -- Round 5: close native git/gh command-alias bypass of the
   interactive-session guard (`interactive-session-guard.bashrc-snippet` +
   `tests/interactive_session_guard_test.sh`, 376 added lines, only 10 lines
   already match main) -- a real, still-open security-boundary gap in the guard.
4. **#114** -- rca-task-20260726-171926: dedup fix for `veridian-task-watchdog.py`
   + new `tests/veridian_task_watchdog_dedup_test.py` (whole new test file, not
   on main).
5. **#83** -- Re-verify 20-engine inventory (2 days stale at PR time) + report
   Auditor Engine status; touches `ai-os-scripts/generate_engines_gateways_inventory.py`
   and the phase plan YAML with 130 added lines, only 2 already on main --
   substantive inventory correction, not yet landed.
6. **#125** -- MASTER_INDEX.yaml live 2026-08-06 GitHub/Vercel census refresh.
   Main's last real census commit touching this file is `937d7c1` (2026-08-02) --
   this PR's Aug 6 data is genuinely newer, not a re-run of what's already there.
7. **#111** -- phase_5_browser_execution_tiers: register litert-spike in
   MASTER_INDEX.yaml + new `PHASE5_BROWSER_EXECUTION_INCREMENT1_2026-07-27.md`
   (file doesn't exist on main).
8. **#91** -- Resolve PR89 merge conflict (Phase 2 policy unification); its own
   `pr89-work` path doesn't exist on main -- carries conflict-resolution content
   not reproduced anywhere else.
9. **#75** -- phase_2: mark compiler pipeline/intelligence engines done in the
   phase-plan YAML -- diverges from #72's edits to the same file (neither is an
   ancestor of the other, confirmed via `git merge-base --is-ancestor` both ways)
   -- real, independent status update, will need manual reconciliation with #72
   at merge time, not a duplicate.
10. **#72** -- Amend phase_2/phase_5 scope for the Owner-clarified two-stage
    SOFTWARE FIRST UX requirement -- same file as #75, independent diverging edit,
    same reconciliation note applies.
