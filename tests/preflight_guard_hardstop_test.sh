#!/bin/bash
# Regression test for the RCA fix to task-20260726-083946-fix-task-lifecycle--real-branch-resoluti's
# watchdog-flagged stall (signature "PRE-FLIGHT REJECTED (crontab_unauthorized_change,
# transient)"): worker-entrypoint.sh and doc-worker-entrypoint.sh both routed a
# crontab_unauthorized_change preflight-guard.py rejection to the "transient" branch
# (systemd retries, checkpoint status=failed) instead of the hard-stop branch
# (checkpoint status=blocked, service disabled). Since check_crontab_unauthorized_change()
# is a pure function of the live crontab / CRONTAB_APPROVED_SNAPSHOT.txt / this task's
# own prompt.txt, a retry reproduces the IDENTICAL rejection every time -- the real
# task burned 9 identical restarts this way before being superseded, the same bug
# class already fixed once for tight_task_schema_violation (2026-07-23).
#
# This test extracts the REAL PREFLIGHT-GUARD-BLOCK out of each live entrypoint script
# and evals it with a fake preflight-guard.py forced to return each GUARD_REASON, so it
# fails the moment someone reintroduces the bug -- it does not re-implement the
# hard-stop/transient decision, so it cannot silently drift from what actually ships.
set -uo pipefail

FAILURES=0

extract_block() {
  sed -n '/# --- PREFLIGHT-GUARD-BLOCK-START/,/# --- PREFLIGHT-GUARD-BLOCK-END/p' "$1"
}

run_case() {
  # $1=script path, $2=service unit name used in the script's systemctl call,
  # $3=fake GUARD_REASON, $4=expected checkpoint status (blocked|failed)
  local script="$1" unit_prefix="$2" reason="$3" expected="$4"
  local checkpoint_log systemctl_log fake_bin_dir
  checkpoint_log="$(mktemp)"
  systemctl_log="$(mktemp)"
  fake_bin_dir="$(mktemp -d)"

  # Fake preflight-guard.py invocation: python3 is shadowed below so any call
  # naming preflight-guard.py returns the forced GUARD_REASON as JSON; calls
  # naming veridian-task.py checkpoint are logged instead of executed.
  (
    export CHECKPOINT_LOG="$checkpoint_log"
    export SYSTEMCTL_LOG="$systemctl_log"
    export FAKE_REASON="$reason"

    python3() {
      if echo "$*" | grep -q "preflight-guard.py"; then
        echo "{\"proceed\": false, \"reason\": \"$FAKE_REASON\", \"detail\": \"fake detail for $FAKE_REASON\"}"
        return 1
      fi
      if echo "$*" | grep -q "veridian-task.py checkpoint"; then
        echo "$*" >> "$CHECKPOINT_LOG"
        return 0
      fi
      # json.load(sys.stdin) one-liners used to parse GUARD_OUT -- run for real,
      # they only parse the fake JSON above, no live-system dependency.
      command python3 "$@"
    }
    export -f python3
    systemctl() {
      echo "$*" >> "$SYSTEMCTL_LOG"
      return 0
    }
    export -f systemctl

    TASK_ID="fake-preflight-task"
    WORKSPACE="/nonexistent"
    TASK_DIR="$(mktemp -d)"
    : > "$TASK_DIR/worker.log"

    BLOCK="$(extract_block "$script")"
    eval "$BLOCK"
  )

  local status="NONE"
  if [ -s "$checkpoint_log" ]; then
    status="$(grep -o -- '--status [a-z_]*' "$checkpoint_log" | head -1 | awk '{print $2}')"
  fi
  local disabled=0
  grep -q "disable veridian-${unit_prefix}@" "$systemctl_log" 2>/dev/null && disabled=1
  local expect_disabled=0
  [ "$expected" = "blocked" ] && expect_disabled=1

  if [ "$status" = "$expected" ] && [ "$disabled" = "$expect_disabled" ]; then
    echo "PASS: $(basename "$script") reason=$reason -> status=$status disabled=$disabled"
  else
    echo "FAIL: $(basename "$script") reason=$reason -> expected status=$expected disabled=$expect_disabled, got status=$status disabled=$disabled"
    FAILURES=$((FAILURES + 1))
  fi
  rm -f "$checkpoint_log" "$systemctl_log"
  rm -rf "$fake_bin_dir"
}

for script in scripts/worker-entrypoint.sh scripts/doc-worker-entrypoint.sh; do
  if [ ! -f "$script" ]; then
    echo "SKIP: $script not found"
    continue
  fi
  unit_prefix="worker"
  [ "$script" = "scripts/doc-worker-entrypoint.sh" ] && unit_prefix="docworker"

  # The exact real-incident case: must now be a hard stop, not transient.
  run_case "$script" "$unit_prefix" "crontab_unauthorized_change" "blocked"
  # A reason that was never a hard stop must still retry as before (no regression
  # on the genuinely-transient branch, e.g. disk/mem/worktree).
  run_case "$script" "$unit_prefix" "disk_low" "failed"
done

if [ "$FAILURES" -eq 0 ]; then
  echo "All scenarios passed."
  exit 0
else
  echo "$FAILURES scenario(s) failed."
  exit 1
fi
