#!/bin/bash
# Regression test for the supervisor-entrypoint.sh audit-check CI-timing-race
# fix (real incident: compliance-tracker PR #560 -- mandatory-audit-check.yml
# runs on pull_request opened/synchronize, which fires the instant `gh pr
# create` does, well before this script's own AUDIT: PASS/FAIL comment can
# exist (that needs a real LLM review call to finish first). It failed at
# 23:39:15Z with "No structured audit verdict found"; a human had to manually
# `gh run rerun` the same job after the comment existed).
#
# This test extracts the REAL AUDIT-CHECK-RERUN block out of the live script
# (between the AUDIT-CHECK-RERUN-BLOCK-START/END markers) and evals it under
# mocked `gh`, so it fails the moment someone breaks the re-trigger logic --
# it does not re-implement the logic and therefore cannot drift from what
# actually ships.
set -uo pipefail

SUPERVISOR_SCRIPT="${1:-/opt/veridian/scripts/supervisor-entrypoint.sh}"
FAILURES=0

extract_block() {
  sed -n '/# --- AUDIT-CHECK-RERUN-BLOCK-START/,/# --- AUDIT-CHECK-RERUN-BLOCK-END ---/p' "$SUPERVISOR_SCRIPT"
}

BLOCK="$(extract_block)"
if [ -z "$BLOCK" ]; then
  echo "FAIL: could not find AUDIT-CHECK-RERUN-BLOCK markers in $SUPERVISOR_SCRIPT"
  exit 1
fi

run_scenario() {
  # $1=label $2=has_workflow(0/1) $3=run_status $4=run_conclusion
  # $5=head_sha_matches(0/1) $6=expect_rerun_called(0/1)
  local label="$1" has_workflow="$2" run_status="$3" run_conclusion="$4"
  local head_sha_matches="$5" expect_rerun="$6"
  local rerun_log
  rerun_log="$(mktemp)"

  (
    export MOCK_HAS_WORKFLOW="$has_workflow"
    export MOCK_RUN_STATUS="$run_status"
    export MOCK_RUN_CONCLUSION="$run_conclusion"
    export MOCK_HEAD_SHA_MATCHES="$head_sha_matches"
    export RERUN_LOG="$rerun_log"

    gh() {
      if [ "$1" = "workflow" ] && [ "$2" = "list" ]; then
        if [ "$MOCK_HAS_WORKFLOW" = "1" ]; then
          echo '[{"name":"CI"},{"name":"Mandatory Audit Check"}]'
        else
          echo '[{"name":"CI"}]'
        fi
        return 0
      elif [ "$1" = "pr" ] && [ "$2" = "view" ]; then
        echo "realsha123"
        return 0
      elif [ "$1" = "run" ] && [ "$2" = "list" ]; then
        local sha="realsha123"
        [ "$MOCK_HEAD_SHA_MATCHES" = "0" ] && sha="othersha999"
        echo "[{\"databaseId\":42,\"status\":\"$MOCK_RUN_STATUS\",\"conclusion\":\"$MOCK_RUN_CONCLUSION\",\"headSha\":\"$sha\"}]"
        return 0
      elif [ "$1" = "run" ] && [ "$2" = "rerun" ]; then
        echo "$*" >> "$RERUN_LOG"
        return 0
      fi
      return 0
    }
    sleep() { return 0; }
    export -f gh sleep

    PR_URL="https://github.com/FChecklist/fake-repo/pull/999"
    TASK_DIR="$(mktemp -d)"
    REPO="fake-repo"
    BRANCH="worker/fake-branch"

    eval "$BLOCK"
  )

  local rerun_called="0"
  [ -s "$rerun_log" ] && rerun_called="1"

  if [ "$rerun_called" = "$expect_rerun" ]; then
    echo "PASS: $label (rerun_called=$rerun_called)"
  else
    echo "FAIL: $label (expected rerun_called=$expect_rerun, got $rerun_called)"
    FAILURES=$((FAILURES + 1))
  fi
  rm -f "$rerun_log"
}

# Scenario 1 -- the exact real-world race: workflow exists, its run for this
# exact head SHA already concluded "failure" (ran before the AUDIT comment
# existed). Must trigger a rerun.
run_scenario "audit-check failed before AUDIT comment existed (PR #560 repro)" \
  1 "completed" "failure" 1 1

# Scenario 2 -- workflow exists, run for this head SHA concluded "success"
# (no race this time). Must NOT rerun a passing check.
run_scenario "audit-check already passed -- no rerun needed" \
  1 "completed" "success" 1 0

# Scenario 3 -- repo doesn't use mandatory-audit-check.yml at all (e.g.
# claude-control). Must not even attempt a run lookup/rerun.
run_scenario "repo has no Mandatory Audit Check workflow -- skipped entirely" \
  0 "completed" "failure" 1 0

# Scenario 4 -- a run exists but for a DIFFERENT (stale) head SHA, e.g. an
# earlier push's run. Must not rerun someone else's stale failed run.
run_scenario "run found but head SHA is stale -- not rerun" \
  1 "completed" "failure" 0 0

if [ "$FAILURES" -eq 0 ]; then
  echo "All scenarios passed."
  exit 0
else
  echo "$FAILURES scenario(s) failed."
  exit 1
fi
