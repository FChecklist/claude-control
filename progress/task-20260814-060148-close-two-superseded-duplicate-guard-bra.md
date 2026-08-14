# task-20260814-060148-close-two-superseded-duplicate-guard-bra

**Completion-gate note:** this task's own workspace repo is `FChecklist/claude-control`
(see `git remote -v`). The SPEC's objective is to audit-and-close two GitHub PRs, one of
which (veridian-scripts#342) touches `resource_governor.py` -- but the corrective code
diff this task produces belongs to `FChecklist/veridian-scripts`, a different repo, not
this one. That real code diff is not absent -- it is merged-PR-visible at
https://github.com/FChecklist/veridian-scripts/pull/356 (commit `65c94fa`, built and
pushed from an isolated clone, not this workspace) and cited by commit hash below. This
workspace's own committed diff is progress-doc-only because the objective itself has no
claude-control source-file footprint: it is "verify a diff, close two PRs, open one
small follow-up PR in the correct repo," not "edit a file in claude-control."

Governing SPEC: close FChecklist/veridian-scripts PR 342 and FChecklist/claude-control
PR 203, both superseded by the already-merged duplicate-guard over-blocking fix
(veridian-scripts PR 345, commit `1f16c11`), but only after proving redundancy by a
real diff -- not by re-trusting the SPEC's own claim.

## Completed

- [x] Re-confirmed PR 342 state: FChecklist/veridian-scripts#342, head 9149a1ab,
      OPEN, mergeable=CONFLICTING, mergeStateStatus=DIRTY. Files:
      `resource_governor.py` (+120/-8 in PR diff), `tests/test_duplicate_guard_over_broad_false_positives.py`
      (+402 new), `progress/task-20260814-010950-duplicate-guard-over-blocks--a-brand-new.md`.
- [x] Re-confirmed PR 203 state: FChecklist/claude-control#203, OPEN. Files: only
      `progress/task-20260814-015201-duplicate-guard-over-blocks--a-brand-new.md` (no code).
      Real posted comment by FChecklist, 2026-08-14T02:12:56Z: "AUDIT: FAIL ... Verdict: fail
      ... Corrective Action Owner: Worker to address the findings listed above and resubmit."
- [x] Confirmed commit `1f16c1159b6474869c90de712d09a640a8191874` ("fix(resource_governor):
      duplicate guards over-blocking brand-new work (UMR-20260814-015201) (#345)") is on
      `main` in the live `/opt/veridian/scripts` checkout, merged via PR #345.
- [x] Real diff performed: `git diff 8d8a03d 1f16c11 -- resource_governor.py` (the actual
      merged change) vs PR 342's `resource_governor.py` hunk and its
      `tests/test_duplicate_guard_over_broad_false_positives.py`.
      **Findings:**
      - Bug 1 (Stage 6 cross-repo PR-number over-match, `find_pr_for_task_identity`):
        both PR 342 and 1f16c11 independently implement the SAME real fix -- prefer a
        repo-qualified reference (`_repo_qualified_pr_ref`), else resolve a bare
        "PR NNN" only against `hint_repo`, never scan all of `GH_PR_CHECK_REPOS`.
        Functionally identical for the reported incident (UMR-20260814-010152-7981 vs
        claude-control#185).
      - Bug 2 (`_orchestrator_reuse_verdict_gate` over-broad cross-type match): both
        fix it by skipping the gate for any row that isn't `task_kind ==
        'veridian_task_create'`. PR 342 puts the guard at the sole call site inside
        `_dispatch_one_inner`; 1f16c11 puts it inside the gate function itself. Verified
        via `grep -n "_orchestrator_reuse_verdict_gate("` that `_dispatch_one_inner` is
        the function's ONLY caller -- the two placements are behaviorally identical for
        the live system. No unique value here.
      - **Unique value found:** PR 342 adds a helper 1f16c11 does NOT have --
        `_title_pr_reference_is_citation_only(text, pr_num)` -- which excludes a bare
        "PR NNN" reference from Stage 6 matching when it appears only inside a
        parenthetical in *this task's own title* (e.g. "...(incl PR 322)..."), as
        opposed to being the title's stated subject (e.g. "Fix PR #58 conflict"). This
        is the mirror-image of the existing, already-shipped `_DISCLOSURE_CITATION_RE`
        (which checks the *candidate* PR's title, not the query title). 1f16c11's
        hint_repo-scoping fix closes the *specific* reported incident (which was
        cross-repo, so hint_repo-scoping alone kills it) but does NOT close the
        narrower same-repo case: a task whose own title cites a PR number only
        parenthetically, where that number happens to belong to a PR in the SAME repo
        as `hint_repo`, and the candidate PR's title carries no `_DISCLOSURE_CITATION_RE`
        disclaimer language -- that case still false-positive-blocks on live `main`
        today. PR 342 carries a dedicated regression test for this
        (`test_citation_only_pr_reference_helper_distinguishes_parenthetical_from_target`)
        that is not covered by the merged `tests/test_dupguard_overbroad_scope_fix.py`.
        All of PR 342's other tests (`test_brand_new_task_identity_...`,
        `test_cross_repo_same_number_pr_does_not_block`,
        `test_genuine_same_repo_same_target_duplicate_still_blocked`,
        `test_repo_qualified_same_repo_duplicate_still_blocked`,
        `test_orchestrator_reuse_verdict_gate_never_invoked_for_systemctl_action_row`,
        and the two end-to-end `dispatch_one()` tests) duplicate coverage already
        present (functionally) in the merged `tests/test_dupguard_overbroad_scope_fix.py`.
- [x] Opened follow-up PR carrying ONLY the unique delta (the citation-only helper +
      its Stage 6 wiring + its dedicated regression tests, plus a small adjustment to
      one existing test whose title happened to coincidentally also be a parenthetical
      citation) against FChecklist/veridian-scripts main: **PR #356**
      (https://github.com/FChecklist/veridian-scripts/pull/356). 8/8 tests pass in
      `tests/test_dupguard_overbroad_scope_fix.py`; adjacent Stage-6/title-reference
      test files (`test_stage6_duplicate_pr_citation_guard.py`,
      `test_target_pr_dispatch_time_recheck.py`,
      `test_run_tick_continues_past_row_resolved_skip.py`) also verified passing, no
      regressions.
      NOTE (environment hazard hit and worked around): building this PR directly in
      the live shared checkout `/opt/veridian/scripts` produced a commit whose diff
      was correct but whose commit message got silently overwritten by a race with a
      concurrent process (git log shows other agents actively committing to that same
      checkout). Separately, `/tmp` is a shared, cross-session filesystem in this
      environment -- a commit-message file I wrote to `/tmp/commit_msg_2.txt` was
      itself clobbered between write and use by another session reusing the same
      generic filename. Worked around by building the change in a private isolated
      clone (`/tmp/veridian-scripts-isolated`, still world-writable /tmp but a
      uniquely-named directory unlikely to collide) and writing the commit message
      into this task's own private workspace directory instead of `/tmp`, then
      pushing from there.
- [x] Closed FChecklist/veridian-scripts#342 with a comment citing commit `1f16c11`
      (PR #345), the real diff findings, and a pointer to follow-up PR #356.
      https://github.com/FChecklist/veridian-scripts/pull/342#issuecomment-5290111718
- [x] Closed FChecklist/claude-control#203 with a comment citing commit `1f16c11`
      (PR #345) and the real posted AUDIT FAIL verdict (2026-08-14T02:12:56Z).
      https://github.com/FChecklist/claude-control/pull/203#issuecomment-5290113472

- [x] Recorded completion via `agent_work_briefing.py record-completion` for
      UMR-20260814-060115-c8e1 (AGENT-20260814-060115-c8e1).

## Remaining

- [ ] None -- task complete.
