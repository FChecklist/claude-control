#!/bin/bash
# Regression test for supervisor-entrypoint.sh's MERGE-GATE-BLOCK
# (task-20260814-095552-block-merges-that-have-no-fresh-passing): the block
# must call scripts/merge_gate.py's read-only `check` before ever reaching
# the MERGE-DETECTION-BLOCK's `gh pr merge` call, and must checkpoint the
# task blocked -- WITHOUT ever calling `gh pr merge` -- whenever the gate
# refuses.
#
# This test extracts the REAL MERGE-GATE-BLOCK out of the live script
# (between the MERGE-GATE-BLOCK-START/END markers) and evals it under a
# mocked `python3` (standing in for merge_gate.py's own exit code/JSON
# output) and a `gh` that fails the test outright if `pr merge` is ever
# called from inside this block -- so it fails the moment someone lets a
# merge attempt slip past a REFUSE.
set -uo pipefail

SUPERVISOR_SCRIPT="${1:-/opt/veridian/scripts/supervisor-entrypoint.sh}"
FAILURES=0

extract_block() {
  sed -n '/# --- MERGE-GATE-BLOCK-START/,/# --- MERGE-GATE-BLOCK-END ---/p' "$SUPERVISOR_SCRIPT"
}

BLOCK="$(extract_block)"
if [ -z "$BLOCK" ]; then
  echo "FAIL: could not find MERGE-GATE-BLOCK markers in $SUPERVISOR_SCRIPT"
  exit 1
fi

run_scenario() {
  # $1=label $2=gate_exit(0/1) $3=gate_json $4=expected_checkpoint_status_or_NONE
  local label="$1" gate_exit="$2" gate_json="$3" expected="$4"
  local checkpoint_log merge_called_log
  checkpoint_log="$(mktemp)"
  merge_called_log="$(mktemp)"

  (
    export MOCK_GATE_EXIT="$gate_exit"
    export MOCK_GATE_JSON="$gate_json"
    export CHECKPOINT_LOG="$checkpoint_log"
    export MERGE_CALLED_LOG="$merge_called_log"

    gh() {
      if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then
        # The whole point of this test: this must NEVER be reached when the
        # gate refused.
        echo "GH_PR_MERGE_CALLED $*" >> "$MERGE_CALLED_LOG"
        return 0
      fi
      return 0
    }
    python3() {
      # merge_gate.py check --pr-url ... -> stand in for its real stdout/exit.
      if echo "$*" | grep -q "merge_gate.py"; then
        echo "$MOCK_GATE_JSON"
        return "$MOCK_GATE_EXIT"
      fi
      # The reason-extraction `python3 -c "import json..."` pipe and the
      # veridian-task.py checkpoint call -- real python3 handles the former
      # fine (pure stdlib json on real stdin), so only intercept checkpoint.
      if echo "$*" | grep -q "veridian-task.py checkpoint"; then
        echo "$*" >> "$CHECKPOINT_LOG"
        return 0
      fi
      command python3 "$@"
    }
    export -f gh python3

    PR_URL="https://github.com/FChecklist/fake-repo/pull/999"
    TASK_DIR="$(mktemp -d)"
    TASK_ID="fake-task"

    eval "$BLOCK"
  )

  local status="NONE"
  if [ -s "$checkpoint_log" ]; then
    status="$(grep -o -- '--status [a-z_]*' "$checkpoint_log" | head -1 | awk '{print $2}')"
  fi
  local merge_called="0"
  [ -s "$merge_called_log" ] && merge_called="1"

  local ok=1
  if [ "$status" != "$expected" ]; then ok=0; fi
  # A REFUSE (expected != NONE, i.e. checkpoint blocked) must never call gh pr merge.
  if [ "$expected" != "NONE" ] && [ "$merge_called" = "1" ]; then ok=0; fi

  if [ "$ok" = "1" ]; then
    echo "PASS: $label (checkpoint status=$status, gh pr merge called=$merge_called)"
  else
    echo "FAIL: $label (expected status=$expected, got status=$status, gh pr merge called=$merge_called)"
    FAILURES=$((FAILURES + 1))
  fi
  rm -f "$checkpoint_log" "$merge_called_log"
}

# Scenario 1 -- no audit verdict at all (real incidents: claude-control
# #216/#217/#220/#221/#226, veridian-scripts #356/#366). Must block, never merge.
run_scenario "gate refuses: no audit verdict found" \
  1 '{"allowed": false, "reason": "no audit verdict found: no PR comment or review body opens with a structured '"'"'AUDIT: PASS'"'"'/'"'"'AUDIT: FAIL'"'"' line"}' \
  "blocked"

# Scenario 2 -- newest verdict is FAIL (real incident: claude-control #219).
# Must block, never merge.
run_scenario "gate refuses: newest verdict is FAIL" \
  1 '{"allowed": false, "reason": "newest posted audit verdict is FAIL"}' \
  "blocked"

# Scenario 3 -- stale pass (cited SHA != current head). Must block, never merge.
run_scenario "gate refuses: stale pass" \
  1 '{"allowed": false, "reason": "stale pass: newest PASS verdict cites SHA aaa1111 but the PR'"'"'s current head is bbb2222"}' \
  "blocked"

# Scenario 4 -- fresh PASS citing the current head. Must NOT block (this
# block only gates entry into the pre-existing MERGE-DETECTION-BLOCK; it
# does not itself call gh pr merge, so "not blocked" is success here).
run_scenario "gate allows: fresh pass citing current head" \
  0 '{"allowed": true, "reason": "fresh PASS verdict cites head SHA matching current head"}' \
  "NONE"

if [ "$FAILURES" -eq 0 ]; then
  echo "All scenarios passed."
  exit 0
else
  echo "$FAILURES scenario(s) failed."
  exit 1
fi
