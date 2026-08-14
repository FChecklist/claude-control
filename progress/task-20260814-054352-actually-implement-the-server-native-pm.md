# task-20260814-054352-actually-implement-the-server-native-pm

SPEC claim: the PR believed to be the real deterministic-boolean-system
integration of the server-native PM sentinel tick, financial-escalation
policy, and hierarchy single-gateway policy is merged-audit-passed on paper,
but its only changed file is a status report — zero real code landed.

Governing chain: P1 UMR-20260806-171945-5767 -> UMR-20260813-084321-2962
(base sentinel) + UMR-20260813-091633-8b6a (financial-escalation) +
UMR-20260813-092654-326b (hierarchy/single-gateway) -> addendum
UMR-20260813-102459-10c3 (collapse all 3 into ONE script).

Real code belongs in `FChecklist/veridian-scripts`, not this repo —
`scripts/README-RETIRED.md` in this repo confirms `claude-control/scripts/`
has been retired since 2026-08-01; this same repo-boundary mistake is
already on record as PR #131's root cause in this chain's own history.

## Completed

- [x] Independently re-verified the SPEC's premise from scratch (not trusted
      from any prior doc claim). Found: `veridian-scripts` PR #298
      ("collapse ... into ONE script (10c3)") is real code (696 lines:
      `pm-sentinel-tick.sh`, `test_pm_sentinel_tick.py`, systemd unit files)
      but **CLOSED, not merged** — its own PR comment says superseded by
      PR #299.
- [x] Confirmed `veridian-scripts` PR #299 ("integrate UMR-102459-10c3 +
      query-once/decide-and-fix") **is merged** to `main` (`ae48cf0`,
      confirmed via `git merge-base --is-ancestor ae48cf0 main`) and really
      did carry #298's content forward as a strict superset. Current `main`
      `pm-sentinel-tick.sh` (1084 lines pre-this-task) has real, working
      `is_financial_decision()`/`escalate_financial_decision()` (financial-
      escalation policy), dynamic addenda-chain discovery + `emit_report_row()`
      boolean-table JSONL + Prometheus metrics (hierarchy/single-gateway/
      zero-dup policy), and the base sentinel-tick killed-row RCA dispatch +
      all 5 AUDIT-REJECT FIXES. Further real fixes on top, both merged:
      PR #323 (`7dac937`, Check 0 live deploy drift) and PR #341 (`f9b4101`,
      stop re-dispatching RCA for already-closed killed rows).
- [x] So the 3-piece collapse itself was **already real, on `main`, with a
      real passing test suite** by the time this task ran — not something
      to redo from zero. The report-only-PR pattern the SPEC describes is
      real history (this file's own header comment documents an earlier
      instance: PRs #135/#139 for the financial-escalation UMR were
      doc-only `STATUS_REPORT.md` edits, verified via `gh pr view --json
      files`), but that instance had already been fixed by the time PR #299
      landed.
- [x] Ran the full real test suite before making any change (baseline):
      `python3 -m pytest test_pm_sentinel_tick.py -v` — 11/11 passed
      (507.38s), real isolated sqlite3 COPY of the live Superboss Register
      DB (backup API), real `dispatch-owner-task.sh --no-relay` calls.
- [x] Found one real, concrete, remaining gap: `pm-sentinel-tick.sh`'s own
      "TOKEN USAGE" header comment claimed zero LLM calls "verified by
      grep" and pointed to `PROGRESS.md` "for the real measured
      before/after token comparison" — a one-time manual claim, never
      automatically re-checked, and no `PROGRESS.md` snapshot anywhere in
      that repo's history actually contained that comparison.
- [x] Real fix landed in `FChecklist/veridian-scripts` PR #355
      (branch `fix/pm-sentinel-tick-real-token-delta-guard-10c3`, commit
      `9f0080a`):
      - `LLM_INVOCATION_PATTERN` + `assert_zero_llm_token_usage()`
        (`pm-sentinel-tick.sh`) — real, narrow call-site regex (same
        convention as the existing `FINANCIAL_KEYWORDS`), strips comment
        lines, greps real code for an actual LLM invocation call site,
        fails the tick loudly (non-zero exit, same `TICK_FAILURES`
        convention every other real tick failure already uses) if one is
        ever introduced. Runs first thing every real tick.
      - `pm_sentinel_tick_llm_invocation_count` Prometheus gauge — real,
        continuously re-measured token-delta baseline (0 by contract),
        exposed every hourly tick.
      - `PmSentinelTickTokenZeroGuardTest` (`test_pm_sentinel_tick.py`,
        2 new real tests): (1) the real shipped script passes its own
        guard; (2) a mutated copy with one real LLM call site appended
        (`curl https://api.anthropic.com/v1/messages`) is caught — proves
        the guard is a real detector, not a tautology. Both independently
        verified passing (90.14s) before being folded into the full suite.
      - `PROGRESS.md` (veridian-scripts) — real measured token-delta
        record + the #298/#299 supersession verification trail.
- [x] Real test run (full suite, post-change): `python3 -m pytest
      test_pm_sentinel_tick.py -v` — 13/13 passed (11 pre-existing + 2 new).
      `bash -n pm-sentinel-tick.sh`: syntax OK. `python3 -m py_compile
      test_pm_sentinel_tick.py`: OK.
- [x] Real smoke-tested `assert_zero_llm_token_usage()` standalone before
      wiring it in: PASS on the real shipped file (0 hits), FAIL (1 hit) on
      a copy with one injected real LLM call site.

## Real file paths changed

Repo `FChecklist/veridian-scripts`, PR #355
(https://github.com/FChecklist/veridian-scripts/pull/355), branch
`fix/pm-sentinel-tick-real-token-delta-guard-10c3`, commit `9f0080a`:
- `pm-sentinel-tick.sh`
- `test_pm_sentinel_tick.py`
- `PROGRESS.md`

This repo (`claude-control`): this progress file only (per this task's own
protocol — real code belongs in `veridian-scripts`, not here; workers never
merge/push `main` in either repo, left for real review same as every prior
status report in this chain).

## Remaining

- [ ] `veridian-scripts` PR #355 review/merge (workers don't merge to
      `main`).
- [ ] Node exporter textfile-collector directory wiring for
      `pm_sentinel_tick.prom` — pre-existing, documented caveat from
      PR #299, out of this task's scope.
