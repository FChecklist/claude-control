#!/bin/bash
# Regression test for the supervisor-entrypoint.sh false-blocked merge bug
# (real incidents: PR #10, #13, #14, 2026-07-24 -- `gh pr merge --delete-branch`
# merged the PR via the GitHub API but then exited non-zero because its local
# git branch-delete step failed with "'master' is already used by worktree at
# '/opt/veridian/repos/claude-control'", causing the script to checkpoint the
# task as blocked even though the merge genuinely succeeded).
#
# This test extracts the REAL tier1 merge-detection block out of the live
# script (between the MERGE-DETECTION-BLOCK-START/END markers) and evals it
# under mocked `gh`/`python3`/`timeout`, so it fails the moment someone
# reintroduces the combined-exit-code bug -- it does not re-implement the
# logic and therefore cannot drift from what actually ships.
set -uo pipefail

SUPERVISOR_SCRIPT="${1:-/opt/veridian/scripts/supervisor-entrypoint.sh}"
FAILURES=0

extract_block() {
  sed -n '/# --- MERGE-DETECTION-BLOCK-START/,/# --- MERGE-DETECTION-BLOCK-END ---/p' "$SUPERVISOR_SCRIPT"
}

BLOCK="$(extract_block)"
if [ -z "$BLOCK" ]; then
  echo "FAIL: could not find MERGE-DETECTION-BLOCK markers in $SUPERVISOR_SCRIPT"
  exit 1
fi

run_scenario() {
  # $1=label $2=merge_only_exit $3=pr_state $4=merged_at $5=delete_branch_exit
  # $6=expected_checkpoint_status $7=combined_merge_delete_exit (historical
  # `gh pr merge --merge --delete-branch` behavior: can differ from
  # merge_only_exit because the local delete-branch step can fail even after
  # the merge itself already succeeded server-side -- that gap IS the bug).
  local label="$1" merge_exit="$2" pr_state="$3" merged_at="$4" delete_exit="$5" expected="$6"
  local combined_exit="${7:-$merge_exit}"
  local checkpoint_log
  checkpoint_log="$(mktemp)"

  (
    export MOCK_MERGE_EXIT="$merge_exit"
    export MOCK_COMBINED_EXIT="$combined_exit"
    export MOCK_PR_STATE="$pr_state"
    export MOCK_MERGED_AT="$merged_at"
    export MOCK_DELETE_EXIT="$delete_exit"
    export CHECKPOINT_LOG="$checkpoint_log"

    gh() {
      if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then
        if [ "$*" != "${*/--delete-branch/}" ]; then
          return "$MOCK_COMBINED_EXIT"
        fi
        return "$MOCK_MERGE_EXIT"
      elif [ "$1" = "pr" ] && [ "$2" = "view" ]; then
        case "$*" in
          *mergeCommit*) echo "deadbeef" ;;
          *mergedAt*) echo "$MOCK_MERGED_AT" ;;
          *state*) echo "$MOCK_PR_STATE" ;;
          *) echo "" ;;
        esac
        return 0
      elif [ "$1" = "api" ]; then
        return "$MOCK_DELETE_EXIT"
      fi
      return 0
    }
    python3() {
      if [ "$2" = "checkpoint" ] || echo "$*" | grep -q "veridian-task.py checkpoint"; then
        echo "$*" >> "$CHECKPOINT_LOG"
      fi
      return 0
    }
    timeout() { shift; "$@"; return 0; }
    export -f gh python3 timeout

    PR_URL="https://github.com/FChecklist/fake-repo/pull/999"
    TASK_DIR="$(mktemp -d)"
    TASK_ID="fake-task"
    REPO="fake-repo"
    BRANCH="worker/fake-branch"
    VERDICT="approve"
    TIER="tier1"
    SCOPE_OK="1"

    eval "$BLOCK"
  )

  local status="FAIL_TO_CHECKPOINT"
  if grep -q -- "--status $expected" "$checkpoint_log"; then
    status="$expected"
  elif [ -s "$checkpoint_log" ]; then
    status="$(grep -o -- '--status [a-z_]*' "$checkpoint_log" | head -1 | awk '{print $2}')"
  fi

  if [ "$status" = "$expected" ]; then
    echo "PASS: $label (checkpoint status=$status)"
  else
    echo "FAIL: $label (expected status=$expected, got status=$status)"
    FAILURES=$((FAILURES + 1))
  fi
  rm -f "$checkpoint_log"
}

# Scenario 1 -- the exact real-world bug: `gh pr merge --merge` (no
# --delete-branch) succeeds, the merge is genuinely confirmed via
# `gh pr view` (state=MERGED, mergedAt set), the separate best-effort
# branch-delete API call fails, AND -- to prove this is the same historical
# failure mode -- the OLD combined `gh pr merge --merge --delete-branch`
# command would have exited non-zero (local worktree git conflict) even
# though the merge itself had already succeeded server-side. Must checkpoint
# completed, NOT blocked.
run_scenario "merge succeeds, branch-delete fails (PR #10/#13/#14 repro)" \
  0 "MERGED" "2026-07-24T00:00:00Z" 1 "completed" 1

# Scenario 2 -- merge genuinely fails (API confirms not merged). Must still
# checkpoint blocked -- the fix must not paper over real failures.
run_scenario "merge genuinely fails" \
  1 "OPEN" "null" 0 "blocked"

# Scenario 3 -- gh pr merge exits non-zero (e.g. transient error) but the PR
# somehow already shows MERGED (idempotent retry racing a prior success).
# Detection must trust the API state, not the exit code, in both directions.
run_scenario "merge command reports failure but API already shows merged" \
  1 "MERGED" "2026-07-24T00:00:00Z" 0 "completed"

if [ "$FAILURES" -eq 0 ]; then
  echo "All scenarios passed."
  exit 0
else
  echo "$FAILURES scenario(s) failed."
  exit 1
fi
