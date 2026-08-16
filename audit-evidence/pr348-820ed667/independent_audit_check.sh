#!/bin/bash
# INDEPENDENT auditor-authored check for FChecklist/veridian-scripts PR #348
# (head 820ed667465f61f609495faba532e61fd9eb34ed). Written from scratch by the
# auditor, NOT copied from tests/preflight_guard_hardstop_test.sh, to cross-check
# that test's own claims by extracting+running the real worker-entrypoint.sh text
# via independently-derived sed ranges (anchored on the marker comments AND on the
# cap-check `if` block above them), covering the two scenarios the audit spec calls
# out by name:
#   (A) a genuinely OVER-LIMIT worker (PRIOR_COUNT >= MAX_LIFETIME_INVOCATIONS) is
#       still stopped -- even when preflight itself would have passed.
#   (B) a NORMAL, under-cap worker still passes preflight and gets its lifetime
#       invocation counter charged (proving the fix didn't break the happy path).
set -uo pipefail
REPO="/tmp/audit-pr348"
WORKER="$REPO/worker-entrypoint.sh"
REAL_PY="$(command -v python3)"

PASS=0; FAIL=0
ok()  { echo "PASS: $1"; PASS=$((PASS+1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

# Independently-derived extraction: cap-check block (own anchor, not reusing the
# PR test's sed pattern) + the full PREFLIGHT-GUARD .. LIFETIME-INVOCATION-CHARGE
# region via the marker comments (the markers themselves are part of what's being
# audited -- confirming they exist and bound the right text is part of the check).
CAP_BLOCK=$(sed -n '/^MAX_LIFETIME_INVOCATIONS=/,/^fi$/p' "$WORKER")
GUARD_AND_CHARGE_BLOCK=$(sed -n '/# --- PREFLIGHT-GUARD-BLOCK-START/,/# --- LIFETIME-INVOCATION-CHARGE-BLOCK-END/p' "$WORKER")
[ -n "$CAP_BLOCK" ] || { echo "FATAL: cap-check block not found"; exit 2; }
[ -n "$GUARD_AND_CHARGE_BLOCK" ] || { echo "FATAL: guard/charge block not found"; exit 2; }

MOCK_BIN=$(mktemp -d)
cat > "$MOCK_BIN/python3" <<PYEOF
#!/bin/bash
REAL_PY="$REAL_PY"
if [ "\$1" = "-c" ]; then exec "\$REAL_PY" "\$@"; fi
case "\$1" in
  */preflight-guard.py)
    echo "{\"reason\": \"\${MOCK_REASON:-ok}\", \"detail\": \"\${MOCK_DETAIL:-}\"}"
    exit "\${MOCK_GUARD_EXIT:-0}"
    ;;
  */veridian-task.py)
    echo "veridian-task.py \$*" >> "\$CALL_LOG"
    exit 0
    ;;
  *) exec "\$REAL_PY" "\$@" ;;
esac
PYEOF
chmod +x "$MOCK_BIN/python3"
cat > "$MOCK_BIN/systemctl" <<'EOF'
#!/bin/bash
echo "systemctl $*" >> "$CALL_LOG"
exit 0
EOF
chmod +x "$MOCK_BIN/systemctl"
cat > "$MOCK_BIN/sleep" <<'EOF'
#!/bin/bash
echo "sleep $*" >> "$CALL_LOG"
exit 0
EOF
chmod +x "$MOCK_BIN/sleep"

echo "=== Scenario A: genuinely OVER-LIMIT worker (20 prior invocations, cap 20) must still be stopped ==="
TA=$(mktemp -d)
echo 20 > "$TA/.invocation_count"
: > "$TA/.call_log"
RUN_A=$(mktemp)
{
  echo '#!/bin/bash'
  echo 'set -uo pipefail'
  echo 'TASK_ID="audit-over-limit-task"'
  echo "TASK_DIR=\"$TA\""
  echo "$CAP_BLOCK"
  echo 'echo "SHOULD_NOT_REACH_HERE"'
} > "$RUN_A"
OUT_A=$(PATH="$MOCK_BIN:$PATH" CALL_LOG="$TA/.call_log" bash "$RUN_A" 2>&1)
RC_A=$?
[ "$RC_A" = "0" ] && ok "over-limit worker: script exits 0 (stopped, systemd will NOT retry) (got $RC_A)" || bad "over-limit worker: expected exit 0, got $RC_A"
echo "$OUT_A" | grep -q "SHOULD_NOT_REACH_HERE" && bad "over-limit worker: execution continued past the cap check (should have stopped)" || ok "over-limit worker: execution stopped exactly at the cap check"
[ "$(cat "$TA/.invocation_count")" = "20" ] && ok "over-limit worker: lifetime counter untouched, still 20 (no extra charge)" || bad "over-limit worker: counter changed unexpectedly"
grep -q "PREVENTION CAP HIT" "$TA/.call_log" && ok "over-limit worker: blocked checkpoint recorded (PREVENTION CAP HIT)" || bad "over-limit worker: no blocked checkpoint found"
grep -q "systemctl --user disable veridian-worker@audit-over-limit-task.service" "$TA/.call_log" && ok "over-limit worker: systemd unit disabled" || bad "over-limit worker: unit not disabled"
rm -rf "$TA" "$RUN_A"

echo
echo "=== Scenario B: NORMAL, well-under-cap worker (5 prior invocations, cap 20) with a PASSING preflight must proceed and be charged ==="
TB=$(mktemp -d)
echo 5 > "$TB/.invocation_count"
: > "$TB/.call_log"
RUN_B=$(mktemp)
{
  echo '#!/bin/bash'
  echo 'set -uo pipefail'
  echo 'TASK_ID="audit-normal-task"'
  echo "TASK_DIR=\"$TB\""
  echo 'WORKSPACE="'"$TB"'/workspace"'
  echo 'IS_RESUME=0'
  echo "$CAP_BLOCK"
  echo "MAX_INFRA_REJECTIONS=5"
  echo 'INFRA_REJECTION_COUNT_FILE="$TASK_DIR/.infra_rejection_count"'
  echo "$GUARD_AND_CHARGE_BLOCK"
  echo 'echo "REACHED_MAIN_BODY new_count=$NEW_COUNT"'
} > "$RUN_B"
OUT_B=$(MOCK_GUARD_EXIT=0 PATH="$MOCK_BIN:$PATH" CALL_LOG="$TB/.call_log" bash "$RUN_B" 2>&1)
RC_B=$?
[ "$RC_B" = "0" ] && ok "normal worker: script exits 0 (falls through, continues to real work) (got $RC_B)" || bad "normal worker: expected exit 0, got $RC_B"
echo "$OUT_B" | grep -q "REACHED_MAIN_BODY new_count=6" && ok "normal worker: reached main body with NEW_COUNT=6 (charged exactly once)" || bad "normal worker: did not reach main body correctly ($OUT_B)"
[ "$(cat "$TB/.invocation_count" 2>/dev/null)" = "6" ] && ok "normal worker: lifetime counter file now reads 6 (5 prior + 1 charge)" || bad "normal worker: counter file wrong/missing"
[ ! -e "$TB/.infra_rejection_count" ] && ok "normal worker: infra-rejection counter untouched on clean pass" || bad "normal worker: infra counter unexpectedly written"
rm -rf "$TB" "$RUN_B"

rm -rf "$MOCK_BIN"
echo
echo "================================================================"
echo "INDEPENDENT AUDIT CHECK RESULTS: $PASS passed, $FAIL failed"
echo "================================================================"
[ "$FAIL" -gt 0 ] && exit 1
exit 0
