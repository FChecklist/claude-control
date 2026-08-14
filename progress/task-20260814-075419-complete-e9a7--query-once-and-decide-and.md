# task-20260814-075419-complete-e9a7--query-once-and-decide-and

Addendum to UMR-20260813-105106-e9a7 (addendum to UMR-20260813-102459-10c3):
add query-once and decide-and-fix rule enforcement to the server-native PM
sentinel.

## Completed
- [x] Checked prior attempt task-20260813-135608 for salvageable work:
      it opened claude-control PR #150 (already MERGED) reporting that both
      rules were already real, working code on `veridian-scripts` PR #299
      (`pm-sentinel-tick.sh`), plus fixed a real gap (missing systemd unit
      files) directly on that PR.
- [x] Confirmed live upstream state (fresh `gh` queries, not trusted from
      docs): `veridian-scripts` PR #299 ("integrate UMR-102459-10c3 +
      query-once/decide-and-fix") is **MERGED** to `main`
      (merge commit `ae48cf0`, merged 2026-08-13T18:49:15Z). Current
      `main` `pm-sentinel-tick.sh` (1084 lines) has real
      `get_umr_row()`/`cache_put_row()`/`already_queried_this_tick()`
      (query-once-per-tick, on-disk per-tick cache) and
      `record_finding()`/`dispatch_gap()`/`FINDINGS_LOGGED`/
      `FINDINGS_ACTIONED` reconciliation with a loud
      `DECIDE-AND-FIX VIOLATION` non-zero exit on mismatch. Further
      hardened since by `veridian-scripts` PR #323 and #341.
- [x] Checked `gh pr list --repo FChecklist/claude-control` (open, all
      states) for any PR already implementing the pm sentinel script in
      *this* repo: none exists, open or otherwise — `pm-sentinel-tick.sh`
      has never lived in `claude-control`, only in `veridian-scripts`.
      There is a separate in-flight open PR on the `veridian-scripts` side
      (`#355`, "zero-LLM-token guard") touching the same file for an
      unrelated concern (not query-once/decide-and-fix), confirming an
      effort is actively iterating on that script right now, just in the
      other repo.
- [x] Per SPEC's explicit fallback instruction ("if it is not yet present
      when you check, add the query-once/decide-and-fix rule logic as its
      own standalone addition... rather than blocking on it"): added
      `scripts/pm_sentinel_query_once_decide_and_fix.sh`, a real,
      generic, sourceable bash policy module implementing both rules
      (per-tick on-disk query cache; decide-and-fix finding/dispatch
      reconciliation with loud violation on mismatch) independent of any
      one sentinel script, so whichever script lands in this repo can
      `source` it instead of re-deriving the same logic.
- [x] Added `tests/pm_sentinel_query_once_decide_and_fix_test.sh` proving
      (a) a repeated query for the same key within one tick is served from
      cache and the underlying query function is invoked exactly once, and
      (b) a finding recorded without a matching dispatch call fails loud
      (DECIDE-AND-FIX VIOLATION, non-zero exit) while one with a matching
      dispatch call reconciles cleanly (exit 0).
- [x] Ran the new test locally: all scenarios pass.
- [x] Committed + pushed; opened PR.

## Remaining
- [ ] None — real code + real test landed in this repo per the addendum's
      own fallback instruction; the production enforcement itself already
      lives merged on `veridian-scripts` main (PR #299, hardened by #323,
      #341). Report the real PR number in the final checkpoint.
