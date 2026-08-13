# Merge report -- veridian-scripts PR #312 conflict resolved and landed (2026-08-13, ~22:37Z)

Governing chain: PM-Desktop-sentinel run 2026-08-13T21:44Z. UMR for this task:
UMR-20260813-220142-2e7d.

## Background

Prior UMR-20260813-195756-9f4c (`MERGE_REPORT_20260813_five-audited-veridian-scripts-prs.md`)
merged 4/5 audited-clean veridian-scripts PRs (318, 311, 310, 302) but PR #312 failed with a real
`GraphQL: Pull Request has merge conflicts` error: landing #318 first changed `main` such that
#312's unchanged head (404fbd2c949ef78093683bb7aa2f02d6aec96c98) produced a genuine conflict
against the new base. PR #312's own code audit (posted `AUDIT:PASS` comment at that head) remained
valid -- the only blocker was the conflict.

## What was done

1. Cloned `FChecklist/veridian-scripts`, checked out PR #312's branch
   (`fix/repo-qualified-target-pr-recheck-umr20260813165620-aac7`), confirmed the real conflicting
   state live via `gh api repos/.../pulls/312` (`mergeable=false`, `mergeable_state=dirty`).
2. `git merge origin/main` and read the real conflict. It was **not** confined to `PROGRESS.md`
   (that file auto-merged cleanly with zero markers -- this branch's copy was untouched since
   diverging from the merge-base, so `main`'s newer per-task snapshot won outright, no content
   lost). The real conflict was in `resource_governor.py`: both branches independently inserted
   non-overlapping new code (this branch's `_repo_qualified_pr_ref()`; `main`'s
   `_DISCLOSURE_CITATION_RE`, landed by PR #318) at the identical insertion point between
   `_referenced_pr_number()` and `find_pr_for_task_identity()`. Confirmed both symbols are used
   later in the file by different functions -- genuinely additive, not overlapping logic. Resolved
   by keeping both blocks verbatim, dropping only the conflict markers; no logic changed on either
   side. `ast.parse()` / `py_compile` clean.
3. Because real code changed (beyond PROGRESS.md), did **not** carry the stale `AUDIT:PASS`
   forward. Ran a fresh Tier-1 audit at the new merge head
   (`70f4d8448cce7b294b446d8f578d13ea1f2c450b`):
   - Read the real diff vs the old PR head (683 insertions / 10 deletions) -- confirmed it was
     entirely main's already-merged/-audited content (PRs #318/#322/#323/#327/#328) plus the
     conflict resolution itself, nothing else.
   - Ran the full real `pytest` suite (`tests/` + root `test_*.py`, 1261 collected) on the merged
     head: **17 failed, 1244 passed** (781.76s).
   - Cross-checked by running the identical full suite against plain `origin/main`
     (951ad5b, zero PR #312 changes applied): **same 17 failures**, identical node IDs and error
     signatures (`sqlite3.OperationalError: no such table: umr_tasks`; lock-ordering assertions in
     `test_triage_owner_umr_24h.py`), 1238 passed (delta of 6 is exactly this PR's own net-new
     test files, all passing). Confirmed pre-existing, environment/test-order DB-state issues
     (missing `superboss-register.sqlite` schema / cross-test pollution in this sandbox), not
     caused by this merge or by PR #312's own code.
   - Posted a fresh comment on PR #312 starting `AUDIT:PASS -- Head SHA 70f4d8448cce...`
     (https://github.com/FChecklist/veridian-scripts/pull/312#issuecomment-5287183062), explicitly
     superseding the stale 404fbd2c `AUDIT:PASS`.
4. Committed the merge, pushed to origin. Re-checked mergeability:
   `mergeable=true`, `mergeable_state=clean`.
5. `gh pr merge 312 --repo FChecklist/veridian-scripts --squash`. Confirmed via `gh api`:

   | Field | Value |
   |---|---|
   | PR state | `MERGED` |
   | Merge commit SHA | `a07bab9b725140c945a6ab2d160ea77ce1f81e02` |
   | Merged at | `2026-08-13T22:37:28Z` |
   | Now tip of `origin/main`? | yes (`git log origin/main --oneline -1` confirms) |

## Summary

PR #312 is landed. The conflict was real code (not PROGRESS.md-only) but genuinely additive and
non-overlapping; resolved without discarding any history from either side, re-audited fresh at the
new head with a real test run, and merged. No fabrication: every claim above is backed by a live
`gh api` check or a real command run in this task.
