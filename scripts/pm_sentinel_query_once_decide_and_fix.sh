#!/bin/bash
# pm_sentinel_query_once_decide_and_fix.sh -- QUERY-ONCE-PER-TICK +
# DECIDE-AND-FIX policy module for the server-native PM sentinel.
#
# GOVERNING CHAIN: UMR-20260813-084321-2962 -> UMR-20260813-102459-10c3 ->
# UMR-20260813-105106-e9a7 (addendum: two Owner directives, 2026-08-13) ->
# this addendum, UMR-20260814-074850-b740.
#
# WHY THIS FILE EXISTS HERE (read before deleting or "deduplicating" it):
# The real production sentinel script (`pm-sentinel-tick.sh`) does NOT live
# in this repo (`claude-control`) -- it lives in the sibling `veridian-
# scripts` repo, where both rules below are ALREADY real, merged, working
# code (`veridian-scripts` PR #299, merged commit `ae48cf0`, further
# hardened by PR #323 and #341). Independently re-verified live via `gh`
# before writing this file -- not trusted from a prior doc claim.
#
# This UMR's own SPEC anticipated that the sentinel script might not (yet)
# be present in *this* repo when this task ran, and gave an explicit
# fallback: add the query-once/decide-and-fix rule logic here as its own
# standalone addition -- a policy module the sentinel script can `source`
# once it lands in this repo -- rather than block on, or duplicate-guess
# at, whichever separate in-flight effort is recovering that script.
# Checked at task start: no open (or closed) claude-control PR implements
# `pm-sentinel-tick.sh`, so that fallback applies. This module intentionally
# mirrors the already-proven `veridian-scripts` design (on-disk per-tick
# cache; FINDINGS_LOGGED/FINDINGS_ACTIONED reconciliation) but is written
# generically -- no pm-sentinel-specific naming or state paths -- so it is
# a real, reusable, sourceable dependency, not a parallel reimplementation
# competing with the merged one.
#
# ---------------------------------------------------------------------------
# RULE 1 -- QUERY ONCE PER RUN/TICK
#   Fetch each real row's (UMR/PR/unit/etc.) state at most once per tick and
#   reuse it within that tick. Do not re-query the same key multiple times
#   just to double-check -- that wastes real tokens/API calls for zero new
#   information.
#
#   qodaf_init_tick_cache            -- call once at the top of a tick.
#   qodaf_cached_query <key> <cmd...> -- run <cmd...> at most once per key
#                                        per tick; every later call for the
#                                        same key returns the cached result
#                                        without re-invoking <cmd...>.
#   qodaf_already_queried <key>      -- true if <key> is already cached
#                                        this tick (skip re-decide, not just
#                                        re-fetch).
#   qodaf_cache_put <key> <value>    -- seed the cache from a value a bulk
#                                        query already returned, so a later
#                                        individual lookup for the same key
#                                        reuses it instead of re-querying.
#
# RULE 2 -- DECIDE-AND-FIX, NOT DECIDE-AND-ASK
#   For any non-financial finding (technical/product/priority), the fix
#   must be dispatched in the SAME tick it is found, not merely logged for
#   a future decision. A finding without an accompanying real dispatch (or
#   an explicit real blocker, e.g. a stop-work gate refusing it) is
#   incomplete work.
#
#   qodaf_record_finding              -- call immediately before any real
#                                        dispatch attempt for a finding.
#   qodaf_record_actioned             -- call from inside the ONE real
#                                        dispatch gateway function, exactly
#                                        once per finding it is handed,
#                                        regardless of that dispatch's own
#                                        terminal outcome (dispatched,
#                                        already in-flight, cap-reached, or
#                                        an explicit blocker are all real,
#                                        disclosed dispositions -- silently
#                                        dropping a finding is not).
#   qodaf_reconcile_decide_and_fix    -- call once at tick end. Prints a
#                                        loud "DECIDE-AND-FIX VIOLATION" and
#                                        returns non-zero if any finding was
#                                        logged but never actioned; exits 0
#                                        (silently) otherwise.
# ---------------------------------------------------------------------------
set -uo pipefail

# --- RULE 1: query-once-per-tick -------------------------------------------

# QODAF_CACHE_DIR is deliberately a real on-disk directory, not a bash
# associative array: call sites that invoke qodaf_cached_query via command
# substitution ($(...)) run in a forked subshell, and an in-memory
# `declare -A` write inside that subshell is silently lost the instant the
# subshell exits -- a real file write is not. See veridian-scripts
# pm-sentinel-tick.sh's own CACHE_DIR comment for the same real incident
# this design already avoided there.
QODAF_CACHE_DIR=""

qodaf_init_tick_cache() {
  QODAF_CACHE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/qodaf-tick-cache.XXXXXX")"
  trap 'rm -rf "$QODAF_CACHE_DIR"' EXIT
}

_qodaf_cache_key() {
  printf '%s' "$1" | tr -c 'A-Za-z0-9_-' '_'
}

qodaf_already_queried() {
  [ -n "$QODAF_CACHE_DIR" ] && [ -f "$QODAF_CACHE_DIR/$(_qodaf_cache_key "$1")" ]
}

qodaf_cache_put() {
  # qodaf_cache_put <key> <value> -- no-op if already cached (first real
  # fetch this tick wins, never overwritten mid-tick).
  local key="$1" value="$2"
  [ -n "$QODAF_CACHE_DIR" ] || { echo "qodaf: FATAL: qodaf_init_tick_cache not called" >&2; return 1; }
  local f="$QODAF_CACHE_DIR/$(_qodaf_cache_key "$key")"
  [ -f "$f" ] && return 0
  printf '%s' "$value" > "$f"
}

qodaf_cached_query() {
  # qodaf_cached_query <key> <cmd...> -- run <cmd...> at most once per
  # <key> per tick. stdout of <cmd...> is cached and replayed verbatim on
  # every later call for the same key this tick.
  local key="$1"; shift
  [ -n "$QODAF_CACHE_DIR" ] || { echo "qodaf: FATAL: qodaf_init_tick_cache not called" >&2; return 1; }
  local f="$QODAF_CACHE_DIR/$(_qodaf_cache_key "$key")"
  if [ -f "$f" ]; then
    cat "$f"
    return 0
  fi
  local out
  out="$("$@")"
  printf '%s' "$out" > "$f"
  printf '%s' "$out"
}

# --- RULE 2: decide-and-fix --------------------------------------------

QODAF_FINDINGS_LOGGED=0
QODAF_FINDINGS_ACTIONED=0

qodaf_record_finding() {
  QODAF_FINDINGS_LOGGED=$((QODAF_FINDINGS_LOGGED + 1))
}

qodaf_record_actioned() {
  QODAF_FINDINGS_ACTIONED=$((QODAF_FINDINGS_ACTIONED + 1))
}

qodaf_reconcile_decide_and_fix() {
  # Returns non-zero (and prints a loud violation) iff a finding was
  # recorded this tick but never actioned through the real dispatch
  # gateway -- i.e. "decide-and-ask" (logged, no accompanying fix)
  # happened at least once.
  if [ "$QODAF_FINDINGS_LOGGED" -ne "$QODAF_FINDINGS_ACTIONED" ]; then
    echo "DECIDE-AND-FIX VIOLATION: ${QODAF_FINDINGS_LOGGED} real finding(s) logged this tick but only ${QODAF_FINDINGS_ACTIONED} actioned via the real dispatch gateway -- a finding was logged without an accompanying same-tick fix (or blocker)." >&2
    return 1
  fi
  return 0
}
