# Land every cleanly-mergeable open PR (FChecklist/claude-control)

Dispatch: UMR-20260816-093009-1c80. Owns exactly the cleanly-mergeable half of open PRs
(MERGEABLE state). Sibling dispatch owns the conflicting half — not touched here.

## Live re-derivation (done 2026-08-16, via `gh api repos/.../pulls/<n>`)

Checked all 26 currently-open PRs' real `mergeable`/`mergeable_state`. Confirmed exactly
17 report `mergeable=true`/`clean` — matches the SPEC snapshot exactly:
243, 242, 241, 240, 215, 214, 206, 194, 186, 159, 125, 116, 102, 98, 91, 83, 75.

Excluded (dirty/conflicting, sibling dispatch's set, NOT touched):
234, 158, 153, 150, 147, 142, 114, 111, 72.

## Plan per PR (newest -> oldest of the 17)

For each: get head SHA, check issue comments + reviews for an audit verdict citing that
exact 40-hex SHA. Fresh PASS -> merge. Stale-SHA/no-SHA PASS -> UNAUDITED, do not merge
without obtaining a real fresh audit. Real FAIL -> do not merge, report. Docs-only diffs
merge but labeled docs-only, never recorded as a fix. After each merge, confirm commit in
`git log origin/main` before continuing; rebase-check remaining PRs for staleness.

## Completed

- [x] Re-derived live MERGEABLE list (matches SPEC's 17 exactly)

## Remaining

- [ ] 243
- [ ] 242
- [ ] 241
- [ ] 240
- [ ] 215
- [ ] 214
- [ ] 206
- [ ] 194
- [ ] 186
- [ ] 159
- [ ] 125
- [ ] 116
- [ ] 102
- [ ] 98
- [ ] 91
- [ ] 83
- [ ] 75
- [ ] Final report table
- [ ] record-completion call
