## Root cause (already diagnosed, evidence below confirms it)

`pm_lifecycle.py` hardcoded `complexity_tier = "moderate"` in four places:
- `build_tightened_prompt()`'s default parameter
- `dispatch_audit_fix()`'s call site
- `dispatch_independent_audit()`'s call site
- the `run` subcommand's `--complexity-tier` argparse default

`plan_generator.py:56` defines `VALID_TIERS = ["mechanical", "integrative", "judgment"]`. `"moderate"` is not a member, so `tight_task_validation.py`'s schema gate hard-rejects every task minted through `pm_lifecycle.py` with `reason_code=tight_task_schema_violation` -- the worker checkpoints `status=blocked` and exits after ~1.8 CPU-seconds having touched zero files. `pm_lifecycle.py` is the Owner-mandated exclusive route for GTM certification / go-to-market gate work, so all of that work was dying on arrival.

Reference: `status-remediation-tick.py` already uses `complexity_tier="judgment"` at its own three call sites (lines 624, 653, 792) and those tasks are never rejected.

## Fix

1. Replaced all four `"moderate"` literals with `"judgment"`, a real `plan_generator.VALID_TIERS` member.
2. `build_tightened_prompt()` now lazy-loads `plan_generator` via the same `_load_module()` / `spec_from_file_location` convention already used elsewhere in this file (`classify_merge_tier`'s `policy_decision` load, etc.) and raises `ValueError` when `complexity_tier` is not a `plan_generator.VALID_TIERS` member -- so this typo class can never again pass silently into schema validation.
3. Added a regression test in `tests/test_pm_lifecycle.py`:
   - `test_every_complexity_tier_literal_in_pm_lifecycle_is_a_valid_tier` -- scans the live `pm_lifecycle.py` source for every `complexity_tier="..."` / `--complexity-tier default="..."` literal and asserts each is a real `plan_generator.VALID_TIERS` member.
   - `test_build_tightened_prompt_raises_on_invalid_complexity_tier` -- asserts the new fail-fast guard raises `ValueError` for `complexity_tier="moderate"`.
   - `test_build_tightened_prompt_accepts_every_valid_tier` -- asserts every real `VALID_TIERS` member is accepted.

## Real diff

```diff
diff --git a/pm_lifecycle.py b/pm_lifecycle.py
index 2ceb8f9..45f2ff0 100644
--- a/pm_lifecycle.py
+++ b/pm_lifecycle.py
@@ -215,14 +215,31 @@ RELAY_RE = re.compile(r"umr_id=(\S+)")
 
 
 def build_tightened_prompt(objective, scope, success_criteria, expected_output,
-                            known_context=None, complexity_tier="moderate"):
+                            known_context=None, complexity_tier="judgment"):
     """Assembles the labeled-field prompt shape tight_task_validation.py's
     own validate_tight_task()/parse_labeled_fields() validate against
     (## OBJECTIVE / ## SCOPE / ## SUCCESS_CRITERIA / ## EXPECTED_OUTPUT /
     ## KNOWN_CONTEXT / ## COMPLEXITY_TIER) -- built here, not left to the
     caller to hand-format, so every real dispatch this orchestrator makes
     is a real "validated tightened prompt" per this task's own SPEC step 3,
-    not free text."""
+    not free text.
+
+    Fail-fast guard (task-20260815-225232-reject-invalid-complexity-tier-
+    constant): every complexity_tier value reaching this point must be a
+    real member of plan_generator.VALID_TIERS -- that's the same list
+    tight_task_validation.py's own schema gate hard-rejects against
+    (reason_code tight_task_schema_violation) at dispatch time, roughly
+    1.8 CPU-seconds and zero files later. Checking it here, at the one
+    real prompt-assembly choke point every dispatch_task() caller in this
+    module goes through, means a typo'd tier constant (e.g. "moderate",
+    which is not a member) can never again pass silently through to that
+    far-away, much more expensive rejection."""
+    plan_generator = _load_module("plan_generator.py", "pm_lifecycle_plan_generator")
+    if complexity_tier not in plan_generator.VALID_TIERS:
+        raise ValueError(
+            f"invalid complexity_tier {complexity_tier!r}: must be one of "
+            f"{plan_generator.VALID_TIERS} (plan_generator.VALID_TIERS)"
+        )
     lines = [
         "## OBJECTIVE", objective.strip(), "",
         "## SCOPE", scope.strip(), "",
@@ -532,7 +549,7 @@ def dispatch_audit_fix(evidence, tier, medium, repo, no_relay=False):
             f"Most recent audit verdict on this PR: {finding!r} (createdAt={verdict.get('createdAt')}). "
             "Do not fabricate completion."
         ),
-        complexity_tier="moderate",
+        complexity_tier="judgment",
     )
     return dispatch_task(title, prompt, tier, medium, repo, no_relay=no_relay)
 
@@ -568,7 +585,7 @@ def dispatch_independent_audit(evidence, tier, medium, repo, no_relay=False):
         ),
         expected_output="A real 'AUDIT: PASS' or 'AUDIT: FAIL' comment posted on the PR, citing real findings.",
         known_context="No prior audit comment exists on this PR yet -- this is the first real review.",
-        complexity_tier="moderate",
+        complexity_tier="judgment",
     )
     return dispatch_task(title, prompt, tier, medium, repo, no_relay=no_relay)
 
@@ -953,7 +970,7 @@ def build_parser():
     p_run.add_argument("--success-criteria", default=None)
     p_run.add_argument("--expected-output", default=None)
     p_run.add_argument("--known-context", default=None)
-    p_run.add_argument("--complexity-tier", default="moderate")
+    p_run.add_argument("--complexity-tier", default="judgment")
     p_run.set_defaults(func=run_full_cycle)
 
     return ap
```

(`tests/test_pm_lifecycle.py` diff: +73/-0, adds the three tests described above -- see the PR Files tab for the full diff.)

## Real test output

```
$ python3 -m pytest tests -k complexity_tier -q
..                                                                       [100%]
2 passed, 968 deselected in 0.25s
```

```
$ python3 -m pytest tests/test_pm_lifecycle.py -q
............................                                             [100%]
28 passed in 0.06s
```

## Repo verification

```
$ git -C /opt/veridian/scripts rev-parse --show-toplevel
/opt/veridian/scripts
```
`/opt/veridian/scripts` is a checkout of `FChecklist/veridian-scripts` (confirmed via `git remote -v`), which is why this PR targets that repo and not `claude-control` (this task's dispatch-origin repo, which does not contain `pm_lifecycle.py`).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
