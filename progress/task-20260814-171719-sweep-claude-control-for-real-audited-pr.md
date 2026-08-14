# Sweep claude-control open PRs for real audited merges

Repo: FChecklist/claude-control (origin)

## Completed
- [x] Listed all open PRs via `gh pr list` (23 open PRs found, numbers: 237,234,215,214,206,194,186,159,158,153,150,147,142,125,116,114,111,102,98,91,83,75,72)
- [x] Captured headRefOid + mergeable/mergeStateStatus for each open PR

## Remaining
- [ ] Determine audit-comment convention (look at recently-merged PR #239/#237 review history for the "AUDIT PASS" pattern)
- [ ] For each of the 23 open PRs: fetch PR comments/reviews, find most recent audit verdict comment, compare the commit SHA it references against current headRefOid
- [ ] Classify each PR: genuine-passing-audit-matching-head + clean mergeable -> MERGE candidate; anything else -> report only (failing/missing/stale audit, or real conflict)
- [ ] Merge MERGE candidates (gh pr merge), capture evidence (merge commit SHA / gh output)
- [ ] Write final report: PR numbers, real state, which were actually merged, with evidence
- [ ] Commit + push progress file updates along the way
- [ ] Call record-completion for UMR-20260814-171700-2255
