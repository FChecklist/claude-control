# TIER1 REDISPATCH REPORT -- 2026-07-26

## Objective

Re-derive, from the real 7-day completion audit (`ai-os/TASK_COMPLETION_AUDIT_2026-07-26.json`,
219 tasks, generated 2026-07-26T16:43:43Z) and each task's own `task.yaml` checkpoint history, the
subset of tasks whose real, verified failure cause was one of three specific bugs now fixed on
`master`: branch-mismatch ("could not resolve a real PR"), approved-but-merge-failed ("merge
itself FAILED"), and crontab-drift pre-flight rejections (`crontab_unauthorized_change`). For each
matching task, do a real relevance check against the current default branch of its target repo
before redispatching -- skip anything already satisfied -- then redispatch the genuinely unmet
ones via `scripts/task-gateway.py submit`/`start` using their exact original `prompt.txt` content.

## Derivation

- Candidates: all 94 rows in the audit whose `real_verified_status` is `NO_PR_FOUND` or
  `OPEN_NOT_DONE`.
- For each candidate, read `/opt/veridian/ai-os/tasks/<task_id>/task.yaml`'s
  `checkpoints[-1].note` and matched against the 3 root-cause patterns:
  - branch-mismatch: `"could not resolve a real PR"` -- **6 matches**
  - merge-failed: `"merge itself FAILED"` -- **5 matches**
  - crontab-drift: `"crontab_unauthorized_change"` -- **3 matches**
- Total matched: **14** (confirms this session's live bucketing pass: 6+5+3=14).

## Relevance check + outcomes (all 14)

For each task, its original `prompt.txt`'s real, stated deliverable (specific PR content, specific
file, specific test, specific registered artifact) was checked directly against the current
default branch / open PRs of its target repo (`claude-control` or `compliance-tracker`), including
running the task's own success-criteria commands (pytest, grep, gh pr view) where applicable.

| # | task_id | root cause | outcome | evidence |
|---|---------|-----------|---------|----------|
| 1 | task-20260726-101954-fix-owner-engine-dispatch-safety-gaps--r | branch-mismatch | **SKIPPED_ALREADY_SATISFIED** | PR #82 is MERGED. `scripts/prompt_gateway/gateway.py` on master already wires `needs_owner_clarification` (route_and_dispatch), gates `start` on `duplicate_found`, implements a real `repo_override` checkpoint, and `credit-accountant.py`'s `propose` subcommand genuinely accepts `--repo`. All fixed by a distinct successful task (`task-20260726-101257`, cited throughout the code's own comments). `python3 -m pytest tests/test_gateway_task_integration.py -q` -> 12 passed. |
| 2 | task-20260726-105110-fix-write-gate-spoofable-cgroup-file---f | branch-mismatch | **SKIPPED_ALREADY_SATISFIED** | PR #80 (still OPEN) already contains commits `62fc664`/`ee36e97` ("Round 3: fix real cgroup-config-file bypass + two git-push refspec parsing gaps" / "Round 3 (corrected): remove the env-var cgroup-path override"). `tests/write_gate_test.py` and `tests/interactive_session_guard_test.sh` both pass on that branch. |
| 3 | task-20260726-114944-fix-write-gate-argv-position-bypass---in | branch-mismatch | **SKIPPED_ALREADY_SATISFIED** | Same PR #80 branch also already contains commit `353fa09` ("Round 4: fix real argv-position detection bypass + add task-registry cross-reference"). Same passing test evidence as row 2. |
| 4 | task-20260726-115417-resolve-pr85-merge-conflict--vercel-gith | branch-mismatch | **SKIPPED_ALREADY_SATISFIED** | PR #85 is already MERGED (`gh pr view 85` -> state MERGED; visible on master as merge commit `0c247a8`). The conflict this task was meant to resolve no longer exists. |
| 5 | task-20260726-115422-resolve-pr80-merge-conflict--write-gate | branch-mismatch | **REDISPATCHED** | PR #80 is still OPEN with real, unresolved conflicts against current `master` (`gh pr view 80` -> `mergeable: CONFLICTING`, `mergeStateStatus: DIRTY`; confirmed live by a real `git merge origin/master` dry run in a scratch clone, which produced 3 real conflicting files: `ai-os/OWNER_DIRECTIVES/PROTOCOL_OWNER_AI.yaml`, `ai-os/OWNER_DIRECTIVES/interactive-session-guard.bashrc-snippet`, `tests/interactive_session_guard_test.sh`). New task_id: **`task-20260726-171337-resolve-pr80-merge-conflict--write-gate`** (instruction_id `INS-20260726-171308-7447`). |
| 6 | task-20260726-160604-append-4-new-x-post-analyses-to-x-post-a | branch-mismatch | **REDISPATCHED** | `grep -c` for the 4 target post IDs in the current `ai-os/X_POST_AI_ANALYSIS_2026-07-23.md` on master returned `0` -- none of the 4 rows have been appended yet. New task_id: **`task-20260726-171405-append-4-new-x-post-analyses-to-x-post-a`** (instruction_id `INS-20260726-171357-c149`). |
| 7 | task-20260720-025001-superboss-v2-plan--decisions-of-record | merge-failed | **SKIPPED_ALREADY_SATISFIED** | `ai-os/REVIEW_FRAMEWORK_DECISIONS_2026-07-19.md` already exists on compliance-tracker's default branch with all 7 required entries (`## D7 / D11`, `## D9`, `## C13`, `## C16`, `## C17`, `## C18`, `## C19`). |
| 8 | task-20260724-143319-fix-auditor-phase4-rejected-issues | merge-failed | **SKIPPED_ALREADY_SATISFIED** | PR #44 is MERGED. `ai-os-scripts/audit_pipeline_architecture.py`'s `upsert_findings()` on master already computes a genuine new-vs-existing delta (checks `audit_findings` table for prior `finding_id` before counting as new), and `ai-os/AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml`'s phase-4 evidence block cites two real back-to-back pipeline runs (`AUD-20260724-143435-521cb`, `AUD-20260724-143513-528e5`) instead of an unverified narrative claim. |
| 9 | task-20260724-183102-fix-terminology-phase4-gitlink-issue | merge-failed | **SKIPPED_ALREADY_SATISFIED** | `git ls-tree -r origin/master \| awk '$1=="160000"'` returns nothing (no gitlink entries). PR #48 (MERGED) body confirms the gitlink was removed and references companion `compliance-tracker` PR #553 ("Phase 4: migrate hardcoded terminology examples to registered placeholders"), which is also MERGED. |
| 10 | task-20260726-080948-fix-pr78-multi-violation-line-shift-bug | merge-failed | **SKIPPED_ALREADY_SATISFIED** | PR #78 is MERGED. `scripts/backfill_phase_self_report.py`'s `audit_and_correct_plan_file()` docstring on master explicitly documents and implements option (c) from the task's own SCOPE (resolve all violations' blame lookups against the original unmutated file first, then apply all reverts in one bottom-to-top pass). The exact regression test (`test_audit_reverts_two_violations_in_one_file`) exists and `python3 -m pytest tests/backfill_phase_self_report_test.py -q` -> 11 passed. |
| 11 | task-20260726-091956-fix-ddl-gate--privilege-escalation-cover | merge-failed | **SKIPPED_ALREADY_SATISFIED** | PR #79 is MERGED. `scripts/ddl_authorization_check.py` on master detects `GRANT`/`REVOKE`/`ALTER ROLE`/`SECURITY DEFINER` etc., and `is_real_reference()` does a real existence check (KE-id / `OWNER_DECISIONS_NEEDED_*.yaml` file lookup) rather than a shape-only regex match. `python3 -m pytest tests/test_ddl_authorization_check.py -q` -> 28 passed. |
| 12 | task-20260725-131506-task2-dedup-integration-audit | crontab-drift | **SKIPPED_ALREADY_SATISFIED** | Identical objective to a distinct, later, successful sibling task `task-20260725-160908-task2-dedup-integration-audit`, whose result is on master: `ai-os/VERIDIAN_ARCHITECTURE_V2_GAP_ANALYSIS_2026-07-25.yaml`'s `meta.re_verification` block records `items_re_checked: 105`, `verdicts_changed: 12`; `ai-os/VERIDIAN_ARCHITECTURE_V2_PHASE_PLAN_2026-07-25.yaml` has `integration_point` on every surviving phase (16 occurrences). |
| 13 | task-20260726-055454-migration-drift-audit-and-reconciliation | crontab-drift | **SKIPPED_ALREADY_SATISFIED** | Identical objective to a distinct sibling task `task-20260726-071400-migration-drift-audit-and-reconciliation`, which already produced compliance-tracker PR #563 (OPEN, MERGEABLE) containing `ai-os/MIGRATION_DRIFT_AUDIT_2026-07-26.yaml` -- a real, thorough audit documenting the root cause (`drizzle/meta/_journal.json` frozen at migration 0000 since it was first committed), the fix (rebuilt journal with 261 real entries, `drizzle.__drizzle_migrations` backfilled from 0 to 261 rows), and verification evidence for every previously-missing table. |
| 14 | task-20260726-055619-phase5-browser-execution-lite-llm-npu-bu | crontab-drift | **REDISPATCHED** | `ai-os/VERIDIAN_ARCHITECTURE_V2_PHASE_PLAN_2026-07-25.yaml`'s `phase_5_browser_execution_tiers` entry still has `status: not_started` on master. No compliance-tracker PR implementing the tiered browser execution engine, mode-pill/chat input components, or browser-to-server handoff exists (`gh pr list` search for litert/mode-pill/option-chain/browser-native/phase_5 found only the already-merged, pre-existing PR #331 spike). claude-control PR #72 (an amendment attempt referenced by this task's own prompt as "rejected") is still open but is explicitly superseded/corrected by this task's own prompt text, not a completed implementation. New task_id: **`task-20260726-171420-phase5-browser-execution-lite-llm-npu-bu`** (instruction_id `INS-20260726-171414-3d01`), target repo `compliance-tracker`. |

## Totals

- **SKIPPED_ALREADY_SATISFIED**: 11
- **REDISPATCHED**: 3
- **COULD_NOT_REDISPATCH**: 0
- Total processed: 14 (matches the 14 real tasks derived above; zero silent omissions)

## Redispatched tasks -- new task_ids

| original task_id | new task_id | instruction_id | repo | status at report time |
|---|---|---|---|---|
| task-20260726-115422-resolve-pr80-merge-conflict--write-gate | task-20260726-171337-resolve-pr80-merge-conflict--write-gate | INS-20260726-171308-7447 | claude-control | in_progress (pre-flight passed) |
| task-20260726-160604-append-4-new-x-post-analyses-to-x-post-a | task-20260726-171405-append-4-new-x-post-analyses-to-x-post-a | INS-20260726-171357-c149 | claude-control | in_progress (pre-flight passed) |
| task-20260726-055619-phase5-browser-execution-lite-llm-npu-bu | task-20260726-171420-phase5-browser-execution-lite-llm-npu-bu | INS-20260726-171414-3d01 | compliance-tracker | in_progress / pending |

Each was redispatched with its exact original `prompt.txt` content, unaltered, via:

```
python3 scripts/task-gateway.py submit --text "<original prompt.txt content>" --source ai_agent --session-id tier1_redispatch_2026-07-26
python3 scripts/task-gateway.py start --instruction-id <INS-...> --title "<original task.yaml title>" --repo <original repo> --prompt-file <original prompt.txt path>
```

Note: all three `submit` calls reported `duplicate_found: true`, but their `duplicate_evidence`
consisted entirely of generic, keyword-matched entity-index rows (dispatch-entrypoint scripts,
validation modules, etc. from `MASTER_INDEX.yaml`'s `search`/`check-duplicate` index) with zero
relation to the specific task content, and `active_collision_task_ids` was empty for all three --
i.e. no currently-running task duplicates this work. This is a mechanical keyword-collision
artifact of `check-duplicate`'s search-index match, not a real duplicate task or PR; combined with
this report's own direct-evidence relevance check above (confirming each of these 3 objectives is
genuinely unmet), all three were dispatched.

## COULD_NOT_REDISPATCH

None. All 14 matched tasks had a real, readable `prompt.txt` and were fully processed (11 skipped
with recorded evidence, 3 redispatched with recorded new task_ids).

## Scope note

Per this task's own SCOPE item 5 / EXPECTED_OUTPUT: this task's job was to trigger the 3 genuinely
unmet tasks and report -- not to do their work itself. The 3 redispatched tasks (and the write-gate
PR #80's eventual merge, the X-post file update, and the phase_5 browser-execution implementation)
run as separate, independent worker tasks and are not part of this task's own diff.
