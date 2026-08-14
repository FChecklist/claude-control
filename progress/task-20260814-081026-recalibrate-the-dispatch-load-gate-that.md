# task-20260814-081026-recalibrate-the-dispatch-load-gate-that

## Context
Real target file (`dispatch_core.py`'s `load1_backoff` check, `has_resource_headroom_detail()`)
lives in the **veridian-scripts** repo (`FChecklist/veridian-scripts`), NOT in this task's own
`claude-control` workspace checkout. Confirmed via `grep -n "load1" /opt/veridian/scripts/dispatch_core.py`
(production mirror) and cross-checked against `/opt/veridian/repos/veridian-scripts` (git remote
`FChecklist/veridian-scripts`). Prior UMR-20260813-155201-da76 ("unwedge dispatch -- stale swap
ratchet") established the binding architectural precedent for this exact shape: dispatch_core.py is
**not** exempt from the 2026-08-08 stop-work order, so every real fix must live in
`resource_governor.py` (exempt) and wrap `dispatch_core.has_free_slot_detail()`'s own result --
`dispatch_core.py` itself stays untouched. Followed that same pattern here.

Work done in a fresh worktree: `/opt/veridian/repos/veridian-scripts-load1-fix-wt`
(branch `fix/dispatch-load1-cpu-idle-calibration-recal8102`, off `origin/main`).

## Completed
- [x] Located the real `load1_backoff` gate: `dispatch_core.has_resource_headroom_detail()`
      (`os.getloadavg()[0] >= cpu_count * BACKOFF_UTILIZATION_PCT(0.80)`).
- [x] Confirmed dispatch_core.py must stay untouched (prior UMR-20260813-155201-da76 precedent);
      fix lives in `resource_governor.py`.
- [x] Added `read_loadavg_runnable()` -- real, live `/proc/loadavg` nr_running/nr_threads parser.
- [x] Added `_override_load1_backoff_when_cpu_idle(slot_ok, slot_detail, metrics, now=None)` --
      narrowly overrides `slot_detail["check"] == "load1_backoff"` only, requiring BOTH:
      1. this tick's own real, delta-based `/proc/stat` CPU utilization (`metrics["cpu"]`, already
         computed by `sample_metrics()`) confirmed under `LOAD1_OVERRIDE_MAX_CPU_UTILIZATION_PCT` (50%, env-overridable), AND
      2. a real, live `/proc/loadavg` runnable-queue snapshot (`nr_running <= cpu_count`) as an
         independent safety backstop, so genuine CPU saturation still throttles.
      Never touches `load1_unreadable`/`cap_exhausted`/mem/swap checks. Fails open (no override) on
      any unreadable `/proc/loadavg`.
- [x] Wired the override into `_dispatch_one_inner()` right after the existing swap-ratchet override,
      with the same `_append_attention()` INFO logging convention.
- [x] Wrote `tests/test_load1_backoff_cpu_idle_override.py` (12 tests): unit tests for the parser and
      override function (real SPEC evidence shape overrides; does NOT override on high real cpu%,
      missing metrics, contended runnable queue, `load1_unreadable`, other gates, unreadable
      `/proc/loadavg`) + 3 end-to-end `dispatch_one()` tests (proceeds when CPU idle but load1
      inflated == DELIVER requirement; still defers on genuine CPU saturation; still defers on
      contended runnable queue).
- [x] Ran new suite: `12/12 passed` (both the module's own `__main__` runner and `pytest`, exit 0 --
      pasted below).
- [x] Ran `tests/test_stale_swap_ratchet_override.py` (existing, adjacent gate): `15 passed`, no
      regression.
- [x] Ran the wider `resource_governor`/`dispatch_core`/`dispatch_decision`/`load1`/`swap_ratchet`/
      `has_free_slot`-scoped subset: `53 passed, 716 deselected`, no regression.
- [x] Committed on `fix/dispatch-load1-cpu-idle-calibration-recal8102`.

## Remaining
- [ ] Full `pytest tests/` run (background, whole repo, ~769 tests) -- confirm exit 0 before final push.
- [ ] Push branch + open PR against `FChecklist/veridian-scripts`.
- [ ] Record `pr_url.txt` and `agent_work_briefing.py record-completion`.

## Real test output (new suite, exit 0)
```
$ python3 tests/test_load1_backoff_cpu_idle_override.py
PASS: test_read_loadavg_runnable_parses_real_shape
PASS: test_overrides_real_spec_evidence_shape
PASS: test_does_not_override_when_real_cpu_utilization_is_high
PASS: test_does_not_override_when_metrics_cpu_missing
PASS: test_does_not_override_when_runnable_queue_exceeds_cpu_count
PASS: test_never_overrides_load1_unreadable
PASS: test_never_overrides_other_real_gates
PASS: test_passthrough_when_slot_already_ok
PASS: test_never_overrides_when_proc_loadavg_unreadable
PASS: test_dispatch_one_end_to_end_proceeds_when_cpu_idle_but_load1_inflated
PASS: test_dispatch_one_end_to_end_still_defers_when_cpu_actually_saturated
PASS: test_dispatch_one_end_to_end_still_defers_when_runnable_queue_contended

12/12 passed
$ echo $?
0

$ python3 -m pytest tests/test_load1_backoff_cpu_idle_override.py -v
...
============================== 12 passed in 0.55s ==============================

$ python3 -m pytest tests/test_stale_swap_ratchet_override.py -q
...............
15 passed in 0.41s
```
