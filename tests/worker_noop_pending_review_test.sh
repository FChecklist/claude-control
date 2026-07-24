#!/bin/bash
# Regression test for worker-entrypoint.sh's genuine-no-op completion path
# (real incident: task-20260724-041754's review.json rejected PR #11 because
# this branch called `checkpoint --status completed` directly, which
# veridian-task.py's cmd_checkpoint guard now hard-rejects without a prior
# 'pending_review' checkpoint -- silently, since this script never checked
# that command's exit code, leaving a genuine no-op task stuck at
# in_progress with its systemd service disabled and no automatic recovery).
#
# This test extracts the REAL no-op block out of the live script (between
# the NOOP-COMPLETION-BLOCK-START/END markers) and evals it under a real git
# fixture with mocked `python3`/`systemctl`, so it fails the moment someone
# reintroduces a direct `completed` checkpoint here -- it does not
# re-implement the logic and therefore cannot drift from what actually ships.
set -uo pipefail

WORKER_SCRIPT="${1:-/opt/veridian/scripts/worker-entrypoint.sh}"
FAILURES=0

extract_block() {
  sed -n '/# --- NOOP-COMPLETION-BLOCK-START/,/# --- NOOP-COMPLETION-BLOCK-END ---/p' "$WORKER_SCRIPT"
}

BLOCK="$(extract_block)"
if [ -z "$BLOCK" ]; then
  echo "FAIL: could not find NOOP-COMPLETION-BLOCK markers in $WORKER_SCRIPT"
  exit 1
fi

# Real git fixture: an "origin" repo plus a workspace clone, so the block's
# own real `git diff` / `git status` / `git rev-list` calls exercise real
# git, not a mock -- only python3 (veridian-task.py) and systemctl are
# mocked, matching tests/supervisor_merge_detection_test.sh's convention.
FIXTURE_ROOT="$(mktemp -d)"
trap 'rm -rf "$FIXTURE_ROOT"' EXIT

setup_fixture() {
  # $1=scenario workspace dir, $2=mode: noop | self-committed | dirty
  local ws="$1" mode="$2"
  local origin="$FIXTURE_ROOT/origin-$RANDOM$RANDOM"
  git init --quiet --bare "$origin"
  git clone --quiet "$origin" "$ws"
  (
    cd "$ws"
    git config user.email test@example.com
    git config user.name test
    echo "hello" > file.txt
    git add file.txt
    git commit --quiet -m "initial"
    git push --quiet origin HEAD:master
    git branch --quiet -M master
    git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/master 2>/dev/null || true
  )
  case "$mode" in
    noop)
      : # workspace already matches origin/master exactly, clean tree
      ;;
    self-committed)
      (
        cd "$ws"
        echo "more" >> file.txt
        git add file.txt
        git commit --quiet -m "worker self-committed real changes"
      )
      ;;
    dirty)
      (
        cd "$ws"
        echo "uncommitted" >> file.txt
      )
      ;;
  esac
}

run_scenario() {
  # $1=label $2=mode $3=expected_checkpoint_status_or_NONE $4=expect_supervisor_start(0/1)
  local label="$1" mode="$2" expected="$3" expect_supervisor="$4"
  local ws="$FIXTURE_ROOT/ws-$RANDOM$RANDOM"
  setup_fixture "$ws" "$mode"

  local checkpoint_log systemctl_log
  checkpoint_log="$(mktemp)"
  systemctl_log="$(mktemp)"

  (
    export CHECKPOINT_LOG="$checkpoint_log"
    export SYSTEMCTL_LOG="$systemctl_log"

    python3() {
      if echo "$*" | grep -q "veridian-task.py checkpoint"; then
        echo "$*" >> "$CHECKPOINT_LOG"
      fi
      return 0
    }
    systemctl() {
      echo "$*" >> "$SYSTEMCTL_LOG"
      return 0
    }
    export -f python3 systemctl

    WORKSPACE="$ws"
    TASK_ID="fake-noop-task"
    DEFAULT_BRANCH="master"
    # the block appends to "$TASK_DIR/worker.log"
    TASK_DIR="$(mktemp -d)"
    : > "$TASK_DIR/worker.log"

    eval "$BLOCK"
  )

  local status="NONE"
  if [ -s "$checkpoint_log" ]; then
    status="$(grep -o -- '--status [a-z_]*' "$checkpoint_log" | head -1 | awk '{print $2}')"
  fi

  local ok=1
  if [ "$status" != "$expected" ]; then
    ok=0
  fi
  local supervisor_started=0
  grep -q "start veridian-supervisor@" "$systemctl_log" && supervisor_started=1
  if [ "$supervisor_started" != "$expect_supervisor" ]; then
    ok=0
  fi
  # The old (buggy) behavior must never reappear: a genuine no-op must never
  # checkpoint straight to 'completed'.
  if grep -q -- "--status completed" "$checkpoint_log"; then
    echo "FAIL: $label (regression -- checkpointed directly to 'completed', the exact bug this test guards against)"
    ok=0
  fi

  if [ "$ok" = "1" ]; then
    echo "PASS: $label (checkpoint status=$status, supervisor_started=$supervisor_started)"
  else
    echo "FAIL: $label (expected status=$expected supervisor_started=$expect_supervisor, got status=$status supervisor_started=$supervisor_started)"
    FAILURES=$((FAILURES + 1))
  fi
  rm -f "$checkpoint_log" "$systemctl_log"
}

# Scenario 1 -- the exact real gap this task closes: a genuine no-op (clean
# tree, zero commits ahead of origin/master). Must checkpoint pending_review
# (never completed directly) and must start the supervisor so the task is
# never silently stuck.
run_scenario "genuine no-op (clean tree, zero commits ahead)" \
  "noop" "pending_review" 1

# Scenario 2 -- clean tree but the worker self-committed real changes ahead
# of origin/master. This block must NOT fire its own checkpoint at all here
# (it falls through to the existing quality-gate + pending_review path
# further down the real script, out of scope for this fix).
run_scenario "clean tree, commits ahead (self-committed, not a no-op)" \
  "self-committed" "NONE" 0

# Scenario 3 -- dirty working tree (uncommitted changes). The outer git
# diff/status guard must not even enter, so no checkpoint from this block.
run_scenario "dirty working tree (not a no-op)" \
  "dirty" "NONE" 0

if [ "$FAILURES" -eq 0 ]; then
  echo "All scenarios passed."
  exit 0
else
  echo "$FAILURES scenario(s) failed."
  exit 1
fi
