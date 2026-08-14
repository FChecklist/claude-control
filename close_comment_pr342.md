Closing as superseded.

This PR's entire scope -- the duplicate guard over-blocking brand-new/resumed
work -- was already fixed and merged as #345, commit
`1f16c1159b6474869c90de712d09a640a8191874` ("fix(resource_governor): duplicate
guards over-blocking brand-new work (UMR-20260814-015201)"), which is present
on `main` in the live checkout.

I diffed this PR's `resource_governor.py` and
`tests/test_duplicate_guard_over_broad_false_positives.py` against
`git diff 8d8a03d 1f16c11 -- resource_governor.py` (the actual merged change)
before closing:

- **Bug 1** (Stage 6 cross-repo PR-number over-match): both this PR and
  `1f16c11` independently implement the same real fix -- prefer a
  repo-qualified reference, else resolve a bare "PR NNN" only against
  `hint_repo`, never scan all of `GH_PR_CHECK_REPOS`. Functionally identical
  for the reported incident.
- **Bug 2** (`_orchestrator_reuse_verdict_gate` cross-type match): both fix it
  by skipping the gate for any row that isn't `task_kind ==
  'veridian_task_create'`. This PR guards the sole call site in
  `_dispatch_one_inner`; `1f16c11` guards inside the gate function itself.
  Verified `_orchestrator_reuse_verdict_gate` has exactly one caller -- the
  two placements are behaviorally identical. No unique value here.
- **Unique value found:** this PR's `_title_pr_reference_is_citation_only()`
  helper (excluding a bare "PR NNN" reference from Stage 6 when it appears
  only inside a parenthetical in the task's own title, e.g. "...(incl PR
  322)...") is genuinely not covered by `1f16c11`. Carried forward, on its
  own, in follow-up PR #356 -- see that PR for the isolated diff and its
  dedicated regression test.

Everything else in this PR (the Stage 6 scoping, the reuse-verdict-gate
scoping, and 6 of this PR's 8 new tests) duplicates coverage already shipped
in #345's `tests/test_dupguard_overbroad_scope_fix.py`. Closing without
merging; the one real delta lives in #356 instead of being discarded.
