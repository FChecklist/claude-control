# task-20260815-225232-reject-invalid-complexity-tier-constant

## Completed
- [x] Confirmed real tracking repo via `git -C /opt/veridian/scripts rev-parse --show-toplevel` -> `/opt/veridian/scripts`, remote `FChecklist/veridian-scripts` (NOT this task's dispatch-origin repo `claude-control`, which has no `pm_lifecycle.py`).
- [x] Cloned `FChecklist/veridian-scripts` into `workspace/veridian-scripts-clone` (edits to the live `/opt/veridian/scripts` checkout are blocked by `pretooluse_worker_enforcement`, so all real code edits happen in this in-workspace clone).
- [x] Replaced all four `complexity_tier="moderate"` literals in `pm_lifecycle.py` with `"judgment"` (a real `plan_generator.VALID_TIERS` member): `build_tightened_prompt()` default, `dispatch_audit_fix()` call site, `dispatch_independent_audit()` call site, `--complexity-tier` argparse default.
- [x] `build_tightened_prompt()` now lazy-loads `plan_generator` via the existing `_load_module()` convention and raises `ValueError` when `complexity_tier` is not in `plan_generator.VALID_TIERS`.
- [x] Added regression tests to `tests/test_pm_lifecycle.py`: scan-every-literal test, raises-on-invalid-tier test, accepts-every-valid-tier test.
- [x] Ran `python3 -m pytest tests -k complexity_tier -q` -> `2 passed, 968 deselected` (real output pasted in commit/PR body).
- [x] Ran full `python3 -m pytest tests/test_pm_lifecycle.py -q` -> `28 passed` (no regressions).
- [x] Committed (`6648bbf`) and pushed branch `worker/task-20260815-225232-reject-invalid-complexity-tier-constant` to `FChecklist/veridian-scripts`.
- [x] Opened PR against `FChecklist/veridian-scripts` with real diff + real test output in the body.

## Remaining
- [ ] None -- awaiting review/merge of the PR against `veridian-scripts`.

## Notes
- SUCCESS_CRITERIA command 2 (`import plan_generator, pm_lifecycle; assert set(plan_generator.VALID_TIERS) >= {"judgment"}`) was already true before this fix (VALID_TIERS always contained "judgment") -- it verifies the tier name exists, not that pm_lifecycle uses it correctly. The real regression coverage for pm_lifecycle's own literals is the new `test_every_complexity_tier_literal_in_pm_lifecycle_is_a_valid_tier` test.
- Did not edit `/opt/veridian/scripts` directly (blocked by `pretooluse_worker_enforcement` hook, correctly, since that path is outside this worker's assigned workspace) -- all real changes are in the pushed branch on `veridian-scripts`, not just in this workspace clone.
