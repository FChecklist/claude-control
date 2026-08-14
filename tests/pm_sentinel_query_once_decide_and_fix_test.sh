#!/bin/bash
# Regression test for scripts/pm_sentinel_query_once_decide_and_fix.sh
# (UMR-20260814-074850-b740, addendum to UMR-20260813-105106-e9a7 /
# UMR-20260813-102459-10c3).
#
# Proves the two Owner-mandated rules the module enforces:
#   1. QUERY ONCE PER TICK -- a repeated query for the same key within one
#      tick is served from cache; the underlying query command is invoked
#      exactly once, not once per call site.
#   2. DECIDE-AND-FIX, NOT DECIDE-AND-ASK -- a finding recorded without a
#      matching same-tick dispatch call fails loud (non-zero exit,
#      "DECIDE-AND-FIX VIOLATION"); a finding with a matching dispatch call
#      reconciles cleanly (exit 0).
#
# This test sources the real module directly (not a reimplementation), so
# it fails the moment someone weakens or removes either guard.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE="${1:-$SCRIPT_DIR/../scripts/pm_sentinel_query_once_decide_and_fix.sh}"
FAILURES=0

if [ ! -f "$MODULE" ]; then
  echo "FAIL: module not found at $MODULE"
  exit 1
fi

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; FAILURES=$((FAILURES + 1)); }

# ---------------------------------------------------------------------------
# Scenario 1: query-once-per-tick -- repeated query for the same key is
# served from cache; the underlying command runs exactly once.
# ---------------------------------------------------------------------------
run_query_once_scenario() {
  local call_log
  call_log="$(mktemp)"

  (
    # shellcheck disable=SC1090
    source "$MODULE"
    qodaf_init_tick_cache

    real_query() {
      echo "call" >> "$CALL_LOG"
      echo "row-data-for-umr-123"
    }

    export CALL_LOG="$call_log"

    out1="$(qodaf_cached_query "umr-123" real_query)"
    out2="$(qodaf_cached_query "umr-123" real_query)"
    out3="$(qodaf_cached_query "umr-123" real_query)"

    [ "$out1" = "row-data-for-umr-123" ] || exit 1
    [ "$out2" = "row-data-for-umr-123" ] || exit 1
    [ "$out3" = "row-data-for-umr-123" ] || exit 1

    calls="$(wc -l < "$CALL_LOG" | tr -d ' ')"
    [ "$calls" = "1" ] || exit 2

    qodaf_already_queried "umr-123" || exit 3
    qodaf_already_queried "umr-999-never-queried" && exit 4

    exit 0
  )
  local rc=$?
  local calls
  calls="$(wc -l < "$call_log" | tr -d ' ')"
  rm -f "$call_log"

  if [ "$rc" -eq 0 ]; then
    pass "query-once-per-tick: 3 calls for the same key -> 1 real underlying query, cached result replayed (real calls=$calls)"
  else
    fail "query-once-per-tick: expected rc=0 got rc=$rc (real underlying calls=$calls)"
  fi
}

# ---------------------------------------------------------------------------
# Scenario 2: cache_put seeds the cache from a bulk-query result -- a later
# individual lookup for the same key must not re-query.
# ---------------------------------------------------------------------------
run_cache_put_scenario() {
  (
    # shellcheck disable=SC1090
    source "$MODULE"
    qodaf_init_tick_cache

    qodaf_cache_put "umr-456" "bulk-listing-row-for-456"
    qodaf_already_queried "umr-456" || exit 1

    never_called() { echo "SHOULD NOT RUN"; exit 99; }
    out="$(qodaf_cached_query "umr-456" never_called)"
    [ "$out" = "bulk-listing-row-for-456" ] || exit 2
    exit 0
  )
  local rc=$?
  if [ "$rc" -eq 0 ]; then
    pass "query-once-per-tick: cache_put seeds a key -- later lookup reuses it, never re-queries"
  else
    fail "query-once-per-tick: cache_put seeding failed (rc=$rc)"
  fi
}

# ---------------------------------------------------------------------------
# Scenario 3: decide-and-fix violation -- a finding recorded with no
# matching dispatch must fail loud and non-zero.
# ---------------------------------------------------------------------------
run_decide_and_fix_violation_scenario() {
  local stderr_out
  stderr_out="$(mktemp)"
  (
    # shellcheck disable=SC1090
    source "$MODULE"
    qodaf_record_finding   # a real gap was found...
    # ...but no qodaf_record_actioned call -- the real dispatch gateway
    # was never invoked for it (the exact "decide-and-ask" bug this
    # module exists to prevent).
    qodaf_reconcile_decide_and_fix
  ) 2>"$stderr_out"
  local rc=$?
  local msg
  msg="$(cat "$stderr_out")"
  rm -f "$stderr_out"

  if [ "$rc" -ne 0 ] && printf '%s' "$msg" | grep -q "DECIDE-AND-FIX VIOLATION"; then
    pass "decide-and-fix: finding logged with no dispatch -> loud violation, non-zero exit"
  else
    fail "decide-and-fix: expected non-zero exit + VIOLATION message, got rc=$rc msg='$msg'"
  fi
}

# ---------------------------------------------------------------------------
# Scenario 4: decide-and-fix success -- a finding matched by a same-tick
# dispatch call reconciles cleanly.
# ---------------------------------------------------------------------------
run_decide_and_fix_success_scenario() {
  (
    # shellcheck disable=SC1090
    source "$MODULE"

    real_dispatch_gateway() {
      # the ONE real place a finding turns into a real fix, mirroring
      # dispatch_gap() in the merged veridian-scripts pm-sentinel-tick.sh
      qodaf_record_actioned
    }

    qodaf_record_finding
    real_dispatch_gateway "some real gap"

    qodaf_reconcile_decide_and_fix
  )
  local rc=$?
  if [ "$rc" -eq 0 ]; then
    pass "decide-and-fix: finding matched by same-tick dispatch -> reconciles cleanly, exit 0"
  else
    fail "decide-and-fix: expected exit 0 for a matched finding+dispatch, got rc=$rc"
  fi
}

# ---------------------------------------------------------------------------
# Scenario 5: multiple findings, one unmatched -- still a violation (proves
# the reconciliation is a real count, not just "at least one dispatch").
# ---------------------------------------------------------------------------
run_decide_and_fix_partial_violation_scenario() {
  local stderr_out
  stderr_out="$(mktemp)"
  (
    # shellcheck disable=SC1090
    source "$MODULE"
    real_dispatch_gateway() { qodaf_record_actioned; }

    qodaf_record_finding
    real_dispatch_gateway "gap 1"

    qodaf_record_finding   # gap 2 found...
    # ...but never dispatched.

    qodaf_reconcile_decide_and_fix
  ) 2>"$stderr_out"
  local rc=$?
  local msg
  msg="$(cat "$stderr_out")"
  rm -f "$stderr_out"

  if [ "$rc" -ne 0 ] && printf '%s' "$msg" | grep -q "2 real finding(s) logged this tick but only 1 actioned"; then
    pass "decide-and-fix: 2 findings, 1 dispatch -> violation with real counts in the message"
  else
    fail "decide-and-fix: expected violation with counts '2 ... 1 actioned', got rc=$rc msg='$msg'"
  fi
}

run_query_once_scenario
run_cache_put_scenario
run_decide_and_fix_violation_scenario
run_decide_and_fix_success_scenario
run_decide_and_fix_partial_violation_scenario

if [ "$FAILURES" -eq 0 ]; then
  echo "All scenarios passed."
  exit 0
else
  echo "$FAILURES scenario(s) failed."
  exit 1
fi
