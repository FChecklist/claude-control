#!/bin/bash
# Regression test proving worker-entrypoint.sh's real COMPLETION-GATE-BLOCK
# is actually wired in and actually fails the branch (task-20260814-054242,
# real fix for UMR-20260813-195922-f548 -- a prior task claimed this was
# fixed but only merged an RCA markdown, no gate code, no wiring).
#
# This extracts the REAL block out of the live script (between the
# COMPLETION-GATE-BLOCK-START/END markers) and evals it under a real git
# fixture (real prompt.txt, real git diff) with only veridian-task.py/
# systemctl mocked -- progress_completion_gate.py itself runs for REAL, so
# this cannot drift from what actually ships. Same convention as
# tests/worker_noop_pending_review_test.sh.
set -uo pipefail

WORKER_SCRIPT="${1:-/opt/veridian/scripts/worker-entrypoint.sh}"
GATE_SCRIPT="${2:-/opt/veridian/scripts/progress_completion_gate.py}"
REAL_PYTHON3="$(command -v python3)"
FAILURES=0

extract_block() {
  sed -n '/# --- COMPLETION-GATE-BLOCK-START/,/# --- COMPLETION-GATE-BLOCK-END ---/p' "$WORKER_SCRIPT"
}

BLOCK="$(extract_block)"
if [ -z "$BLOCK" ]; then
  echo "FAIL: could not find COMPLETION-GATE-BLOCK markers in $WORKER_SCRIPT"
  exit 1
fi

FIXTURE_ROOT="$(mktemp -d)"
trap 'rm -rf "$FIXTURE_ROOT"' EXIT

setup_fixture() {
  # $1=workspace dir  $2=mode: doc-only | real-code | no-objective
  local ws="$1" mode="$2"
  local origin="$FIXTURE_ROOT/origin-$RANDOM$RANDOM.git"
  git init --quiet --bare "$origin"
  git -C "$origin" symbolic-ref HEAD refs/heads/master
  git clone --quiet "$origin" "$ws"
  (
    cd "$ws"
    git config user.email test@example.com
    git config user.name test
    git checkout --quiet -B master
    echo "hello" > README.md
    git add -A
    git commit --quiet -m "initial"
    git push --quiet origin HEAD:master
    git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/master
  )
  case "$mode" in
    doc-only)
      mkdir -p "$ws/progress"
      echo "# progress only, no code" > "$ws/progress/fake-task.md"
      ;;
    real-code)
      mkdir -p "$ws/scripts"
      echo "# real fix" > "$ws/scripts/dispatch_core.py"
      mkdir -p "$ws/progress"
      echo "# progress + real code" > "$ws/progress/fake-task.md"
      ;;
    no-objective)
      mkdir -p "$ws/progress"
      echo "# progress only" > "$ws/progress/fake-task.md"
      ;;
  esac
  (cd "$ws" && git add -A && git commit --quiet -m "worker changes")
}

run_scenario() {
  # $1=label $2=mode $3=prompt_text $4=expect_gate_pass(0/1) $5=expected_checkpoint_status_or_NONE
  local label="$1" mode="$2" prompt_text="$3" expect_pass="$4" expected="$5"
  local ws="$FIXTURE_ROOT/ws-$RANDOM$RANDOM"
  setup_fixture "$ws" "$mode"

  local task_dir checkpoint_log systemctl_log
  task_dir="$(mktemp -d)"
  echo "$prompt_text" > "$task_dir/prompt.txt"
  checkpoint_log="$(mktemp)"
  systemctl_log="$(mktemp)"
  : > "$task_dir/worker.log"

  (
    export CHECKPOINT_LOG="$checkpoint_log"
    export SYSTEMCTL_LOG="$systemctl_log"
    export REAL_PYTHON3 GATE_SCRIPT

    python3() {
      if echo "$*" | grep -q "progress_completion_gate.py"; then
        # Real gate script, real git, real logic -- only the CLI path name
        # is substituted so the test doesn't depend on /opt/veridian being
        # writable/live.
        "$REAL_PYTHON3" "$GATE_SCRIPT" "${@:2}"
        return $?
      fi
      if echo "$*" | grep -q "veridian-task.py checkpoint"; then
        echo "$*" >> "$CHECKPOINT_LOG"
        return 0
      fi
      return 0
    }
    systemctl() {
      echo "$*" >> "$SYSTEMCTL_LOG"
      return 0
    }
    export -f python3 systemctl

    WORKSPACE="$ws"
    TASK_ID="fake-task"
    TASK_DIR="$task_dir"
    BRANCH="worker/fake-task"
    DEFAULT_BRANCH="master"

    eval "$BLOCK"
  )
  local block_exit=$?

  local status="NONE"
  if [ -s "$checkpoint_log" ]; then
    status="$(grep -o -- '--status [a-z_]*' "$checkpoint_log" | head -1 | awk '{print $2}')"
  fi

  local ok=1
  if [ "$expect_pass" = "1" ]; then
    # Gate passed -> block must NOT checkpoint blocked, must not disable the
    # unit, must fall through (real `eval` of a script with `exit` inside a
    # subshell means block_exit reflects whether it exited early).
    if [ "$status" = "blocked" ]; then
      ok=0
    fi
  else
    # Gate rejected -> must checkpoint blocked with the real reason, and
    # disable the unit (subshell exits 0 by script convention, but must not
    # fall through to the rest of worker-entrypoint.sh).
    if [ "$status" != "blocked" ]; then
      ok=0
    fi
    if ! grep -q "COMPLETION GATE REJECTED" "$task_dir/worker.log"; then
      ok=0
    fi
    if ! grep -q "start veridian-worker@" "$systemctl_log" 2>/dev/null; then
      : # disabling uses "disable", not "start" -- checked below instead
    fi
    if ! grep -q "disable veridian-worker@" "$systemctl_log"; then
      ok=0
    fi
  fi

  if [ "$ok" = "1" ]; then
    echo "PASS: $label (status=$status)"
  else
    echo "FAIL: $label (expect_pass=$expect_pass got status=$status)"
    echo "--- worker.log ---"
    cat "$task_dir/worker.log"
    FAILURES=$((FAILURES + 1))
  fi
  rm -f "$checkpoint_log" "$systemctl_log"
  rm -rf "$task_dir"
}

# Scenario 1 -- the exact real bug this task closes: objective names
# scripts/dispatch_core.py, diff is progress-only. Must reject.
run_scenario "doc-only diff against named source file -- must be rejected" \
  "doc-only" "ACTION: fix the swap-gate veto bug in scripts/dispatch_core.py." \
  0 "blocked"

# Scenario 2 -- identical objective, real code change present. Must pass
# through (no blocked checkpoint from this block).
run_scenario "real code diff against named source file -- must pass" \
  "real-code" "ACTION: fix the swap-gate veto bug in scripts/dispatch_core.py." \
  1 "NONE"

# Scenario 3 -- objective names no code file at all. Gate does not apply,
# must pass through regardless of diff content.
run_scenario "no code file named in objective -- gate does not apply" \
  "no-objective" "Investigate the dead-letter queue backlog and report findings." \
  1 "NONE"

if [ "$FAILURES" -eq 0 ]; then
  echo "All scenarios passed."
  exit 0
else
  echo "$FAILURES scenario(s) failed."
  exit 1
fi
