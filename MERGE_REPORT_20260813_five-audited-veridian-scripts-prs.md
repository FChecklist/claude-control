# Merge report -- five audited-clean veridian-scripts PRs (2026-08-13, ~19:59Z)

Governing chain: UMR-20260806-171945-5767 (P1 deterministic foundation), PM-desktop-sentinel
tick 2026-08-13T19:45Z. UMR for this task: UMR-20260813-195756-9f4c.

Task scope: merge the five FChecklist/veridian-scripts PRs that were verified live this tick
as simultaneously `mergeable=MERGEABLE`, `mergeStateStatus=CLEAN`, and carrying a posted
`AUDIT:PASS` comment whose quoted head SHA matched the PR's `headRefOid` at re-check time:
PR 318, 312, 311, 310, 302.

Note: `PROGRESS.md` in this workspace is intentionally untracked (see its own `.gitignore`
entry and comment -- tracking it caused repeated cross-branch merge conflicts, e.g. PR12/23/24/27).
This file is the durable, committed record of the real outcome instead, per this repo's
established convention (see e.g. `AUDIT_AND_MERGE_REPORT.md`, `RCA_*.md`).

## Per-PR verification + outcome

For each PR: re-ran `gh pr view <N> --repo FChecklist/veridian-scripts --json headRefOid,mergeable,mergeStateStatus,comments`
immediately before merging, confirmed head SHA still matched the SHA quoted in the AUDIT:PASS
comment, then ran `gh pr merge <N> --repo FChecklist/veridian-scripts --squash` (no `--admin`,
no bypassing checks), then confirmed `mergedAt` via `gh pr view <N> --json state,mergedAt`.

| PR | Head SHA re-verified | Audit match | Merge result | Merge commit | mergedAt |
|----|----|----|----|----|----|
| 318 | d42dd3ba8f0b52ee30403ce28d6b8b17f1019676 | yes | MERGED | 7bdb75b398acbda549872d849d15baf51665b54f | 2026-08-13T19:58:43Z |
| 311 | 5acf2d099f369ce6395d24a3814ddedbff226788 | yes | MERGED | ba76722e0ce618fc092b074cffe3c722db962e93 | 2026-08-13T19:58:58Z |
| 310 | 089e58904368061ec90dcbeecba1c70a042735a4 | yes | MERGED | 370e75f5506a69e72239085e89b1948c1f2dbbc9 | 2026-08-13T19:59:06Z |
| 302 | f965d5234f7622238172f67779d08aa42c93c744 | yes (latest re-audit at f965d523 correctly superseded a stale earlier AUDIT:PASS at 8de6c8bb) | MERGED | 52224d04a59f461ad4f57f23e6239c71b3969dc7 | 2026-08-13T19:59:23Z |
| 312 | 404fbd2c949ef78093683bb7aa2f02d6aec96c98 | yes (head unmoved, audit still valid) | **FAILED -- real merge conflict** | n/a | n/a |

## PR 312 failure detail

`gh pr merge 312 --repo FChecklist/veridian-scripts --squash` failed with exact stderr:

```
GraphQL: Pull Request has merge conflicts (mergePullRequest)
```

Root cause: PR 318 was merged first (per the "in order" instruction). PR 318 and PR 312 both
touch `resource_governor.py`. Landing PR 318 changed `main` such that PR 312's unchanged head
(404fbd2c -- did not move, audit remains valid against that SHA) now produces a real conflict
against the new base. Re-checked twice after the failure (~6s apart, after GitHub's mergeability
recompute settled from `UNKNOWN`): both times returned `mergeable: CONFLICTING`,
`mergeStateStatus: DIRTY`. This is a genuine, durable conflict, not a transient GitHub
computation state.

Per task protocol ("If a merge fails, capture the exact gh stderr verbatim ... and continue to
the next PR -- do not abort the whole task on one failure") and the circuit-breaker rule ("on a
2nd consecutive failure of the identical approach: STOP"), only one merge attempt was made for
PR 312 (a real conflict is not a transient failure worth retrying identically), and the task
continued on to PRs 311, 310, 302, all of which merged successfully.

PR 312 needs a rebase of its source branch onto the new `main` (post-318) and a fresh audit
before it can land. That rebase/re-audit is follow-up work, out of scope for this merge-only
task, and was not attempted here.

## Summary

4 of 5 target PRs merged this tick: **318, 311, 310, 302**. PR 312 is genuinely blocked by a
real merge conflict introduced by landing PR 318 first, not by any fault in PR 312's own
content or audit -- it requires a rebase + re-audit, not a re-merge attempt.
