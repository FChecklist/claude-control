# Sweep claude-control open PRs for real audited merges

Repo: FChecklist/claude-control (origin)

## Completed
- [x] Listed all open PRs via `gh pr list` (23 open PRs found, numbers: 237,234,215,214,206,194,186,159,158,153,150,147,142,125,116,114,111,102,98,91,83,75,72)
- [x] Captured headRefOid + mergeable/mergeStateStatus for each open PR

- [x] Determined audit-comment convention: issue comments (not PR reviews) starting `AUDIT: PASS` / `AUDIT: FAIL`, per AGENTS.md Rule 7(c) counterpart; PR #237's audit comment explicitly states the audited `headRefOid`
- [x] Fetched issue comments (`gh api repos/.../issues/<n>/comments`) and PR reviews (`gh api .../pulls/<n>/reviews`, all empty — no review-based audits) for all 23 open PRs
- [x] Classified each of the 23 PRs against real head SHA + real mergeable state (see report below)
- [x] Only PR #237 qualified: real `AUDIT: PASS` explicitly naming the exact current `headRefOid` (5cccc726...), mergeable=MERGEABLE/mergeStateStatus=CLEAN, re-confirmed live immediately before merging
- [x] Merged PR #237 via `gh pr merge 237 --merge` — merge commit `d9c22822af8d066ceb948c636394204433df8683`, mergedAt 2026-08-14T17:22:51Z, state MERGED (verified via `gh pr view`)
- [x] All other 22 PRs left open (failing audit, missing audit, stale audit not matching current head, and/or real CONFLICTING/DIRTY mergeable state) — see final report
- [x] Commit + push progress updates
- [ ] Call record-completion for UMR-20260814-171700-2255

## Final classification (all 23 open PRs)

| PR | head (short) | mergeable | audit verdict (current head) | action |
|----|---|---|---|---|
| 237 | 5cccc726 | MERGEABLE/CLEAN | **PASS**, explicitly names this exact headRefOid | **MERGED** (d9c22822) |
| 234 | 74faf0b8 | CONFLICTING/DIRTY | FAIL (unsynchronized destructive DB migration race) | skip: fail+conflict |
| 215 | b17c5ce8 | MERGEABLE/CLEAN | none (0 comments) | skip: missing audit |
| 214 | b8f0ebb5 | MERGEABLE/CLEAN | FAIL (commits disposable .triage/ scratch data) | skip: fail |
| 206 | 214021d5 | MERGEABLE/CLEAN | stale — PASS was against old head dc1080b2; branch since re-merged, new head requested re-audit, both `@claude` audit triggers errored (infra failure), no valid audit posted for current head | skip: no valid audit for current head |
| 194 | 1044746f | MERGEABLE/CLEAN | FAIL | skip: fail |
| 186 | 722a4f00 | MERGEABLE/CLEAN | FAIL | skip: fail |
| 159 | d9e309b7 | MERGEABLE/CLEAN | FAIL | skip: fail |
| 158 | f7688f89 | CONFLICTING/DIRTY | PASS | skip: real conflict overrides passing audit |
| 153 | ff551fe9 | CONFLICTING/DIRTY | PASS | skip: real conflict overrides passing audit |
| 150 | e11e5e52 | CONFLICTING/DIRTY | FAIL | skip: fail+conflict |
| 147 | 2d2b1252 | CONFLICTING/DIRTY | FAIL | skip: fail+conflict |
| 142 | 4eadc5a3 | CONFLICTING/DIRTY | FAIL | skip: fail+conflict |
| 125 | 6992c7ab | MERGEABLE/CLEAN | none (0 comments) | skip: missing audit |
| 116 | 2f0b755d | MERGEABLE/CLEAN | none (0 comments) | skip: missing audit |
| 114 | 58f49755 | CONFLICTING/DIRTY | FAIL | skip: fail+conflict |
| 111 | 549988ba | CONFLICTING/DIRTY | none (0 comments) | skip: missing audit + conflict |
| 102 | 3708c81c | MERGEABLE/CLEAN | FAIL, then later independent "AUDIT ... REJECT" (held for owner signoff per PR body) | skip: rejected |
| 98 | 3cbe6a7d | MERGEABLE/CLEAN | FAIL | skip: fail |
| 91 | fb772331 | MERGEABLE/CLEAN | FAIL | skip: fail |
| 83 | 6af88740 | MERGEABLE/CLEAN | none (0 comments) | skip: missing audit |
| 75 | fafc302b | MERGEABLE/CLEAN | none (0 comments) | skip: missing audit |
| 72 | 885c2a90 | CONFLICTING/DIRTY | FAIL | skip: fail+conflict |

Evidence artifacts (this workspace, `tmp/`): `open_prs.json` (PR list w/ head+mergeable), `comments_<n>.jsonl` (raw issue comments per PR fetched via `gh api repos/FChecklist/claude-control/issues/<n>/comments`), `reviews_<n>.jsonl` (all empty — no PR-review-based audits exist), `pr237_final.json` / `pr237_merged.json` (pre-merge live re-check and post-merge confirmation for #237).
