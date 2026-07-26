#!/bin/bash
# Regression test for supervisor-entrypoint.sh's PR_URL-resolution guard
# (real incident: claude-control PR #84, 2026-07-26). When `gh pr create
# --head "$BRANCH"` fails and the `gh pr list --head "$BRANCH"` fallback also
# finds nothing, PR_URL was left as an empty string, and every later `gh pr
# comment/view/merge "$PR_URL"` call silently fell back to resolving "the PR
# associated with whatever branch is currently checked out in $WORKSPACE" --
# gh does not error on an empty PR argument. In the real incident this caused
# the script to post an AUDIT comment onto, and then for-real merge, a
# completely unrelated PR (#84) that the workspace happened to have checked
# out, with no genuine review of PR #84's own diff ever having run.
#
# This test extracts the REAL PR-URL-RESOLUTION-GUARD block out of the live
# script (between the PR-URL-RESOLUTION-GUARD-BLOCK-START/END markers) and
# evals it under a mocked `python3`, so it fails the moment someone removes
# or weakens the guard -- it does not re-implement the logic and therefore
# cannot drift from what actually ships.
set -uo pipefail

SUPERVISOR_SCRIPT="${1:-/opt/veridian/scripts/supervisor-entrypoint.sh}"
FAILURES=0

extract_block() {
  sed -n '/# --- PR-URL-RESOLUTION-GUARD-BLOCK-START/,/# --- PR-URL-RESOLUTION-GUARD-BLOCK-END ---/p' "$SUPERVISOR_SCRIPT"
}

BLOCK="$(extract_block)"
if [ -z "$BLOCK" ]; then
  echo "FAIL: could not find PR-URL-RESOLUTION-GUARD-BLOCK markers in $SUPERVISOR_SCRIPT"
  exit 1
fi

run_scenario() {
  # $1=label $2=pr_url $3=expect_exit $4=expect_checkpoint_status(or "" if none expected)
  local label="$1" pr_url="$2" expect_exit="$3" expect_checkpoint="$4"
  local checkpoint_log
  checkpoint_log="$(mktemp)"

  (
    export CHECKPOINT_LOG="$checkpoint_log"
    python3() {
      if echo "$*" | grep -q "veridian-task.py checkpoint"; then
        echo "$*" >> "$CHECKPOINT_LOG"
      fi
      return 0
    }
    export -f python3

    TASK_DIR="$(mktemp -d)"
    TASK_ID="fake-task"
    BRANCH="worker/fake-branch"
    PR_URL="$pr_url"

    eval "$BLOCK"
  )
  local actual_exit=$?

  local status="NONE"
  if [ -s "$checkpoint_log" ]; then
    status="$(grep -o -- '--status [a-z_]*' "$checkpoint_log" | head -1 | awk '{print $2}')"
  fi

  local ok=1
  [ "$actual_exit" = "$expect_exit" ] || ok=0
  [ "$status" = "$expect_checkpoint" ] || ok=0

  if [ "$ok" = "1" ]; then
    echo "PASS: $label (exit=$actual_exit, checkpoint=$status)"
  else
    echo "FAIL: $label (expected exit=$expect_exit checkpoint=$expect_checkpoint, got exit=$actual_exit checkpoint=$status)"
    FAILURES=$((FAILURES + 1))
  fi
  rm -f "$checkpoint_log"
}

# Scenario 1 -- the exact real-world bug: PR_URL never resolved (empty).
# Must checkpoint blocked and exit non-zero -- never fall through silently.
run_scenario "empty PR_URL after create+list fallback both fail (PR #84 repro)" \
  "" "1" "blocked"

# Scenario 2 -- normal case: PR_URL resolved fine. Must NOT checkpoint at all
# (the guard is a no-op) and must not exit the script.
run_scenario "PR_URL resolved normally -- guard is a no-op" \
  "https://github.com/FChecklist/fake-repo/pull/999" "0" "NONE"

if [ "$FAILURES" -eq 0 ]; then
  echo "All scenarios passed."
  exit 0
else
  echo "$FAILURES scenario(s) failed."
  exit 1
fi
