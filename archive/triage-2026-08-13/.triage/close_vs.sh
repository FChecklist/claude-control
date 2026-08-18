#!/bin/bash
set -e
REPO="FChecklist/veridian-scripts"

close_pr() {
  local n="$1"
  local msg="$2"
  echo "=== closing #$n ==="
  gh pr close "$n" --repo "$REPO" --comment "$msg" 2>&1
}

close_pr 169 "Closing as **superseded**: \`hooks/find_root_walk_guard.py\` and \`tests/test_find_root_walk_guard.py\` (100% of the functions this PR defines, verified by name-for-name AST comparison) are already present on \`origin/main\`. Introduced by commit \`86a2a8175b78a007929fd449b38967d677da58af\` (2026-08-08, \"feat: harden stop-work-order gate + land master_issue_tracker CRUD + find_root_walk_guard hook\"), refined since by \`055b6ca7bf97ecf09b82b6a1dda4d6d6c12e0d35\` (2026-08-08, PR #277 round-9 tier1 fix). Triaged under task-20260814-060159."

close_pr 81 "Closing as **superseded**: \`gtm_check_regression_testing.py\` (the only remaining diff file) has 100% function-name overlap with the current \`origin/main\` version. Introduced by commit \`8349c1f66941a081ea9b80db31e3dab2138bdc2c\` (2026-08-06 12:54:50Z, \"feat(gtm-checks): build 8 missing re-runnable check scripts, make TEST_SCRIPT_BUILD real\"). Triaged under task-20260814-060159."

close_pr 84 "Closing as **superseded**: \`gtm_check_performance_testing.py\` and \`gtm_check_lighthouse_audit.py\` both have 100% function-name overlap with \`origin/main\`. Introduced by commit \`8349c1f66941a081ea9b80db31e3dab2138bdc2c\` (2026-08-06 12:54:50Z, \"feat(gtm-checks): build 8 missing re-runnable check scripts, make TEST_SCRIPT_BUILD real\"). Triaged under task-20260814-060159."

close_pr 83 "Closing as **superseded**: \`audit_ocid_canonical_registry.py\`'s production code (\`plan_for_ocid\`, \`_load_sbr\`, \`main\`) is 100% present on \`origin/main\`, introduced by commit \`768fd6e2d24d4ad57e4f8f416dd4473654127fff\` (2026-08-05, \"feat(OCID-068 Phase 2): registry schema, DB-enforced completion gate, linkage extension, anti-fabrication audit scripts, seven-rule compliance tracking\"). Only 2 new test-function names remain unmatched -- no production code left to merge. Triaged under task-20260814-060159."

close_pr 108 "Closing as **superseded**: every function this PR defines in \`superboss-register.py\` (\`_ensure_pm_decisions_pending_table\`, \`insert_pm_decision_pending\`, \`resolve_pm_decision_pending\`, etc.) already exists on \`origin/main\`, introduced by commit \`d69a40b484a75ba5f1bfac826e217465d31e297a\` (2026-08-06 03:29:30Z, \"feat: insert_pm_decision_pending()/resolve_pm_decision_pending() in superboss-register.py\") and extended by \`daf9d3ecf17cad73e9b2255c5c52e0b10f3f17b2\` (2026-08-06, PR #110, owner-proposal lifecycle). Triaged under task-20260814-060159."

close_pr 216 "Closing as an exact **duplicate** of open PR #213: this PR's head commit \`645a807018ee873375460db92fbf3d93c114a065\` is byte-identical (same tree \`7c95416b\`) to PR #213's head commit. Zero unique content beyond #213. Triaged under task-20260814-060159."

close_pr 207 "Closing as a strict **subset** of open PR #213: PR #213's branch explicitly contains a \"merge PR #207 branch (unified_orchestrator.py base) into this amendment task\" commit -- confirmed via \`git merge-base --is-ancestor refs/prs/207 refs/prs/213\` = true. Every function this PR adds (\`_ensure_task_audits_table\`, \`record_task_audit\`, \`unified_orchestrator.py\`'s step_* pipeline) is already carried by #213, plus #213 adds a prompt-template-versioning registry on top. Triaged under task-20260814-060159; see #213 in the ranked still-real list."

echo "=== superseded/duplicate closures done ==="
