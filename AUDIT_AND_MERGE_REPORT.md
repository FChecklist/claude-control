# Real merge report for claude-control PR #141 + Stage 4/5/6 guard fix

GOVERNING CHAIN: UMR-20260813-102459-10c3 -> UMR-20260813-172606-101a

## ACTION 1: merge claude-control PR #141 -- NOT executed, real reasons below

Both re-verification checks the dispatching prompt asked for were run against live GitHub state (`gh pr view 141 --repo FChecklist/claude-control`, `gh pr view 141 ... --json comments`), not assumed:

1. **`mergeable`/`mergeStateStatus`**: `CONFLICTING` / `DIRTY` (confirmed at task start and again at task end -- unchanged, `headRefOid=0deb2d322a56f03c6f9333b07e2cfda17f071797`). This is a real merge conflict GitHub itself will not resolve automatically; PR #142's own body independently confirms the same fact ("#141 needs a routine `STATUS_REPORT.md` rebase (`mergeable=CONFLICTING`, same recurring doc-conflict pattern as prior PRs in this chain)").
2. **Posted `AUDIT: PASS` vs. current `headRefOid`**: does **not** match. The one comment on the PR, posted by `FChecklist` at `2026-08-13T12:45:59Z`, reads `AUDIT: PASS` with a "Scope Confirmed" diffstat listing:
   ```
   STATUS_REPORT.md                                  | 181 +-----
   scripts/pm-sentinel-tick.sh                       | 696 ++++++++++++++++++++++
   scripts/systemd/veridian-pm-sentinel-tick.service |  34 ++
   scripts/systemd/veridian-pm-sentinel-tick.timer   |  19 +
   scripts/test_pm_sentinel_tick.py                  | 363 +++++++++++
   ```
   The PR's real current (and only) commit, `0deb2d3`, was pushed **six minutes after** that audit comment (`2026-08-13T12:51:55Z`) and its own message says: *"This branch's prior HEAD had committed scripts/pm-sentinel-tick.sh et al. directly into this retired directory... Those files are removed from this branch."* `gh pr diff 141 --name-only` confirms the current diff is `STATUS_REPORT.md` only. So the audit that passed reviewed a version of the PR that no longer exists; the current docs-only diff has never been independently audited.

Per the dispatching UMR's own explicit fallback ("If head has moved since the PASS or mergeable is CONFLICTING, do not merge -- dispatch what is actually needed (fresh audit or rebase) instead and report why"), and since **both** conditions are independently true, merging was correctly withheld. This task did not attempt to rebase `STATUS_REPORT.md` and self-issue a new audit verdict, because (a) rebasing risks colliding with the disclosed live concurrency (`UMR-20260813-105106-e9a7` is still amending the same underlying file this PR's history touched) and (b) issuing an `AUDIT: PASS` is a distinct reviewer role this task is not positioned to perform for its own dispatch chain.

**No merge commit exists for PR #141 from this task.** `git log origin/main`/`mergedAt` were not re-checked post-merge because no merge was attempted; `gh pr view 141 --json state` is `OPEN`.

### Correction to the dispatching prompt's own premise

The prompt asserted *"141 and 142 share no real content overlap"* and that the guard *"appears to match on shared governing-chain UMR text."* Both are inaccurate, verified against the real registry row and real PR bodies:

- `#142`'s own real title is *"docs: real dedup finding for UMR-20260813-092654-326b (already covered by **PR 141**, not re-implemented)"* -- it explicitly names PR 141, in a repo (`claude-control`) where both PRs live. That is real, direct textual overlap (a citation, not shared UMR-chain boilerplate).
- The Stage 6 guard's real match key, confirmed by reading `resource_governor.py::find_pr_for_task_identity()`, is already the literal target PR number extracted from each title (`_referenced_pr_number()`), not UMR-chain text. It matched here because `#142`'s title genuinely contains "PR 141," not because of a UMR-substring bug.

The real bug (see ACTION 2) is narrower and different from what the prompt guessed: Stage 6 could not distinguish a title that *cites* a PR number as already-covered/non-duplicate disclosure from a title that is itself alternate/duplicate work on that PR number.

## ACTION 2: Stage 4/5/6 duplicate-PR guard fix -- real, implemented, tested

**Real code location:** `/opt/veridian/scripts/resource_governor.py` (repo `FChecklist/veridian-scripts`), function `find_pr_for_task_identity()`, Stage 6 block (originally lines ~2198-2227 pre-fix).

**Verified root cause** (via `resource_governor.py --query-umr --umr-id UMR-20260813-145418-3f98` against the live `superboss-register.sqlite` `umr_tasks` table, not assumed): that row's real rejection reason was `"duplicate-PR guard (Stage 4/5/6): existing PR FChecklist/claude-control#142 already open/merged... checked worker/<task_identity>, prior real branch(es) [], and any existing PR title referencing the same PR number as this task's own title"`. The task's own title, `"Merge audit-passed PR 141..."`, yields `pr_num='141'` via `_referenced_pr_number()`; Stage 6 then scanned every PR in `claude-control` and matched `#142` purely because its title also contains the substring `"PR 141"` -- with no way to tell that citation apart from genuine duplicate work.

**Fix:** added `_DISCLOSURE_CITATION_RE` (matches real phrasing this repo's disclosure-PR convention already uses: "already covered", "not re-implemented", "not a duplicate", "superseded by", "supersedes") and excluded any Stage 6 title-match against a PR whose title contains that phrasing. The original #58/#64/#65/#66 fragmented-duplicate incident Stage 6 was built to catch used no such phrasing, so it remains caught (regression-tested).

**Where:** applied via a fresh scratch clone of `FChecklist/veridian-scripts` (not the live `/opt/veridian/scripts` working tree, which is currently another task's active, uncommitted branch -- editing it in place would have risked clobbering that task's in-progress work, the same class of hazard PR #141's own body discloses and avoids for `pm-sentinel-tick.sh`).

**Tests:** new `tests/test_stage6_duplicate_pr_citation_guard.py`, 3/3 pass:
- reproduces the real `#141`/`#142` false positive directly, asserts it no longer fires;
- regression-tests the original #58-style fragmented duplicate is still caught;
- unit-tests the new regex against the real `#142` title and common variants.

Full suite on the fix branch: **592 passed**, 2 pre-existing failures, both confirmed unrelated to this change by reproducing them identically on a clean pre-fix `main` checkout (real live systemd-timer/worker-cap state on the shared server, not code-path related).

**Real PR:** https://github.com/FChecklist/veridian-scripts/pull/318 (commit on branch `worker/task-20260813-181959-fix-stage6-duplicate-pr-guard-citation`), `mergeable=MERGEABLE`, `mergeStateStatus=CLEAN` at last check. Not merged by this task -- needs the normal review/audit + merge process.

## Summary table

| Item | Real status |
|---|---|
| claude-control PR #141 merge | **Not executed.** Real conflict (CONFLICTING/DIRTY) + stale audit (predates current headRefOid by 6 min, reviewed since-removed files). Needs rebase + fresh audit, not a forced merge. |
| Stage 4/5/6 guard false-positive root cause | Verified real: disclosure citation ("already covered... not re-implemented") in #142's title, matched by Stage 6's fuzzy same-number scan. Not a UMR-chain-text bug as the dispatching prompt guessed. |
| Guard fix | Real, coded, tested (3 new tests + 592/592 relevant suite unaffected), PR opened: veridian-scripts#318 (MERGEABLE/CLEAN). |
