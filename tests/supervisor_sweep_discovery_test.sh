#!/bin/bash
# Regression test confirming supervisor-sweep.sh's real discovery loop picks
# up a `veridian-task.py adopt`ed task (real incident: claude-control PR #84
# had zero task_dir entry and was therefore permanently invisible to this
# loop, which only globs $TASKS_DIR/*/task.yaml).
#
# Runs the REAL supervisor-sweep.sh script (not a re-implementation) against
# a throwaway TASKS_DIR/LOG_DIR (via the VERIDIAN_TASKS_DIR/
# VERIDIAN_SWEEP_LOG_DIR overrides added alongside this test), with a mocked
# `systemctl` on PATH (python3/pyyaml run for real -- no real systemd unit is
# ever touched), and asserts it invokes `systemctl --user start
# veridian-supervisor@<task_id>.service` for a fixture task left
# status=pending_review with no review.json -- exactly the shape both a
# missed-trigger worker task AND an adopted task produce.
set -uo pipefail

SWEEP_SCRIPT="${1:-/opt/veridian/scripts/supervisor-sweep.sh}"
FAILURES=0

run_scenario() {
  # $1=label $2=status $3=has_review_json(0/1) $4=expect_start_called(0/1)
  local label="$1" status="$2" has_review="$3" expect_start="$4"
  local tmp start_log
  tmp="$(mktemp -d)"
  start_log="$(mktemp)"

  mkdir -p "$tmp/tasks/task-fixture" "$tmp/logs"
  cat > "$tmp/tasks/task-fixture/task.yaml" <<EOF
id: task-fixture
status: $status
EOF
  if [ "$has_review" = "1" ]; then
    echo '{"verdict": "approve"}' > "$tmp/tasks/task-fixture/review.json"
  fi

  local bindir
  bindir="$(mktemp -d)"
  cat > "$bindir/systemctl" <<'EOF'
#!/bin/bash
echo "$*" >> "$START_LOG"
exit 0
EOF
  chmod +x "$bindir/systemctl"

  (
    export VERIDIAN_TASKS_DIR="$tmp/tasks"
    export VERIDIAN_SWEEP_LOG_DIR="$tmp/logs"
    export START_LOG="$start_log"
    export PATH="$bindir:$PATH"
    bash "$SWEEP_SCRIPT"
  )

  local start_called="0"
  grep -q "start veridian-supervisor@task-fixture.service" "$start_log" && start_called="1"

  if [ "$start_called" = "$expect_start" ]; then
    echo "PASS: $label (start_called=$start_called)"
  else
    echo "FAIL: $label (expected start_called=$expect_start, got $start_called)"
    FAILURES=$((FAILURES + 1))
  fi
  rm -rf "$tmp" "$bindir" "$start_log"
}

# Scenario 1 -- the exact shape `adopt` produces (and a missed-trigger worker
# task): status=pending_review, no review.json. Must start the supervisor.
run_scenario "pending_review, no review.json (adopt / missed-trigger repro)" \
  "pending_review" "0" "1"

# Scenario 2 -- already reviewed. Must NOT re-trigger.
run_scenario "pending_review, review.json already exists -- not re-triggered" \
  "pending_review" "1" "0"

# Scenario 3 -- any other status (e.g. completed). Must NOT trigger.
run_scenario "status=completed -- not touched" \
  "completed" "0" "0"

if [ "$FAILURES" -eq 0 ]; then
  echo "All scenarios passed."
  exit 0
else
  echo "$FAILURES scenario(s) failed."
  exit 1
fi
