## What

Small follow-up to #345 (`1f16c11`, "duplicate guards over-blocking brand-new work",
UMR-20260814-015201) -- adds a new helper `_title_pr_reference_is_citation_only()`
that Stage 6 of `find_pr_for_task_identity()` was still missing.

## Why

While auditing and closing superseded PR #342 (task-20260814-060148), I diffed
it against what actually merged as #345/`1f16c11`. Everything else in #342 was
functionally identical to what #345 already shipped (the cross-repo hint_repo
scoping, the reuse_verdict_engine `task_kind` scoping, and 6 of #342's 8 new
tests). One real piece of unique value was NOT covered by #345:

#345's hint_repo-scoping fix closes the specific reported incident
(UMR-20260814-010152-7981 vs claude-control#185) because that collision was
cross-repo -- hint_repo scoping alone kills any bare-number match against a
different repo. It does **not** close the narrower same-repo case: a task
whose own title cites a PR number only as a parenthetical aside (e.g.
`"...(incl PR 322)..."`), where that number happens to belong to a real PR in
the *same* repo as `hint_repo`, and that candidate PR's title carries no
`_DISCLOSURE_CITATION_RE` disclaimer language -- unlike the real #58/#64/#65/#66
shape Stage 6 exists to catch, where the number IS the sentence's stated
subject, never inside a parenthetical.

## What this adds

- `_title_pr_reference_is_citation_only(text, pr_num)` -- the mirror-image
  check to the existing `_DISCLOSURE_CITATION_RE` (which inspects the
  *candidate* PR's title): this one inspects THIS task's own title, and
  excludes a bare "PR NNN" reference from Stage 6 matching when it falls
  strictly inside a parenthetical span.
- Wired into Stage 6's pr_num resolution logic.
- Two new tests in `tests/test_dupguard_overbroad_scope_fix.py`:
  `test_citation_only_pr_reference_helper_distinguishes_parenthetical_from_target`
  and `test_same_repo_parenthetical_citation_does_not_block`.
- Adjusted `test_cross_repo_same_number_pr_does_not_block`'s title (dropped
  the parens) to keep it isolated to the cross-repo scoping it was written to
  test -- its original title happened to also be a parenthetical citation and
  is now (correctly) short-circuited earlier by this fix.

## Testing

Ran `tests/test_dupguard_overbroad_scope_fix.py` directly: 8/8 pass.

Also ran `tests/test_stage6_duplicate_pr_citation_guard.py`,
`tests/test_target_pr_dispatch_time_recheck.py`, and
`tests/test_run_tick_continues_past_row_resolved_skip.py` (adjacent Stage-6
and title-reference coverage) -- all pass, no regressions.

Governing task: task-20260814-060148-close-two-superseded-duplicate-guard-bra.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
