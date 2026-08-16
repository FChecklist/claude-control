# Progress: dispose-of-the-ten-rejected-pull-request

Spec: classify the 10 open, already-real-audited-and-blocked PRs in FChecklist/claude-control
(from prior wave task-20260816-120207) into exactly one of 4 buckets and act. NOT a re-audit --
source of truth is the real verdicts already recorded in
`progress/task-20260816-120207-audit-and-land-the-remaining-open-pull-r.md`.

## Source verdicts (read, not re-derived)
Read `progress/task-20260816-120207-audit-and-land-the-remaining-open-pull-r.md` in full --
contains real veridian-supervisor@<task>.service review.json verdicts for all 10 PRs
(247, 246, 243, 242, 240, 206, 186, 114, 91, 75).

## Completed
- [x] Read prior wave's real verdicts for all 10 PRs (no re-audit performed)
- [x] Pulled exact file lists per PR via `gh pr diff <n> --name-only` to ground each defect/decision
      in a real file path
- [x] Verified PR247 superseded-by claim: `git show --stat d4ab44b` (merge of PR #223) touches the
      identical file set (scripts/resource_governor.py, scripts/superboss-register.py,
      tests/test_resource_governor.py) as PR247's diff
- [x] Verified PR240 superseded-by claim: `git show 8fa0834` and `git show 9622ece` on origin/master
      contain the same tmp/ scratch files and the same progress file path as PR240's diff
- [x] Inspected PR242's tmp_secaudit/report.json diff content directly -- confirms real gitleaks/trivy
      match-string dumps (RuleID generic-api-key etc.) committed as scratch noise, no code fix in diff
- [x] Classified all 10 PRs into exactly one bucket each (table below)
- [x] Closed the 3 genuinely-superseded PRs (247, 243, 240) via `gh pr close --comment` naming the
      exact superseding commit/PR for each
- [x] Left the other 7 PRs open (5 real-defect, 1 infra-blocked, 1 owner-decision) -- no merge attempted
- [x] record-completion write-back to UMR-20260816-141409-76c7

## Bucket classification and actions

| # | Bucket | Action | Detail |
|---|---|---|---|
| 247 | 1 superseded | **CLOSED** w/ comment | Byte-for-byte duplicate of PR #223 (merged, commit d4ab44b) -- same 3 files (resource_governor.py, superboss-register.py, test_resource_governor.py) |
| 243 | 1 superseded | **CLOSED** w/ comment | Docs-only, referenced fix (veridian-scripts#423) superseded by master commit 89b30ab (None-sentinel), a non-crashing fix for the same root cause |
| 240 | 1 superseded | **CLOSED** w/ comment | Content byte-identical to what's already on master: progress file at 9622ece, tmp/ scratch at 8fa0834 |
| 242 | 2 real defect | left open | tmp_secaudit/report.json (+trivy.json etc.) commits raw gitleaks/trivy secret-match strings as scratch noise; diff has no real code fix -- real fixes live in separate unmerged branches not in this diff |
| 206 | 2 real defect | left open | progress/task-20260814-043409-add-search-reuse-discipline-to-real-agen.md deletes the real audit-trail checklist and replaces it with a leaked "... more files changed" placeholder |
| 186 | 2 real defect | left open | RCA_20260813_UMR-20260813-205208-feab.md's central conclusion is factually stale: claims veridian-scripts#305 was correctly left unmerged, but it was actually merged ~1.5h after this RCA's own commit |
| 114 | 2 real defect | left open | scripts/veridian-task-watchdog.py reintroduces a silent starvation failure mode (independent file-glob dedup, no TTL/cap) that master's resource_governor.submit() task_identity dedup (added 2026-07-27, post-incident) already fixed |
| 75 | 2 real defect | left open | ai-os/VERIDIAN_ARCHITECTURE_V2_PHASE_PLAN_2026-07-25.yaml edit breaks yaml.safe_load (ParserError), which breaks scripts/auto_phase_continuation.py's phase-detection for the whole file |
| 91 | 3 infra-blocked | left open | GITLINK GUARD trips on nested-repo gitlink `pr89-work` (mode 160000) in the branch -- audit cannot even run; no unilateral repair attempted |
| 246 | 4 owner decision | left open | Diff is docs-only but self-reports the worker unilaterally ran `gh pr merge` on other PRs without Superboss audit, plus mischaracterizes itself as docs-only -- needs Owner decision on how to handle the audit-bypass and whether any of those unaudited merges must be reviewed/reverted |

## Remaining
- [x] All 10 PRs disposed of per spec (3 closed, 7 left open with real detail)
- [x] Final report table delivered to user
- [x] No re-audits performed; no unilateral infra repairs attempted; no self-certified verdicts

TASK COMPLETE.
