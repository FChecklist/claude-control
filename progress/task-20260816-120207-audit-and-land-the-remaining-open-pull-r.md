# Progress: audit-and-land-the-remaining-open-pull-r

Spec: audit and land every open PR in FChecklist/claude-control via the server-native
adopt+sweep mechanism (veridian-task.py adopt + supervisor-sweep.sh), never the
`@claude please audit` GH Action (currently broken, is_error=true, posts no verdict).

## Live PR list re-derived (2026-08-16, via `gh pr list --repo FChecklist/claude-control --state open`)

Newest first (14 open PRs found; note SPEC said "zero conflicting at 11:58Z" but live check
shows PR #247 CONFLICTING now -- re-derived live list wins per instructions):

| # | createdAt | mergeable | branch |
|---|---|---|---|
| 248 | 2026-08-16T09:57:39Z | MERGEABLE | worker/task-20260816-093730-rebase-and-land-every-conflicting-open-p |
| 247 | 2026-08-16T09:43:40Z | CONFLICTING | worker/task-20260814-125846-tier-1-audit-the-never-audited-duplicati |
| 246 | 2026-08-16T09:39:44Z | MERGEABLE | worker/task-20260816-093009-propagate-the-real-preflight-denial-reas |
| 243 | 2026-08-15T22:58:29Z | MERGEABLE | worker/task-20260815-225232-reject-invalid-complexity-tier-constant |
| 242 | 2026-08-15T22:19:26Z | MERGEABLE | worker/task-20260815-215959-rca-and-resume--gtm-certification-worker |
| 241 | 2026-08-14T20:07:13Z | MERGEABLE | worker/task-20260814-200142-publish-real-part1-4-status-to-status-re |
| 240 | 2026-08-14T17:25:27Z | MERGEABLE | worker/task-20260814-171719-sweep-claude-control-for-real-audited-pr |
| 206 | 2026-08-14T04:58:36Z | MERGEABLE | worker/task-20260814-043409-add-search-reuse-discipline-to-real-agen |
| 186 | 2026-08-13T21:22:24Z | MERGEABLE | worker/task-20260813-211803-rca--umr-20260813-205208-feab-killed |
| 114 | 2026-07-27T14:46:46Z | MERGEABLE | worker/task-20260726-181517-rca-task-20260726-171926-remove-anthropi |
| 111 | 2026-07-27T07:17:00Z | MERGEABLE | worker/task-20260727-065831-phase5-litert-spike-registration |
| 98 | 2026-07-26T17:31:19Z | MERGEABLE | worker/task-20260726-083833-build-interactive-session-write-gate--re |
| 91 | 2026-07-26T16:27:46Z | MERGEABLE | worker/task-20260726-162246-resolve-pr89-merge-conflict--phase-2-pol |
| 75 | 2026-07-25T23:38:37Z | MERGEABLE | task-20260725-231836-phase2-status-update |

## Mechanism confirmed
- `python3 /opt/veridian/scripts/veridian-task.py adopt --title <t> --repo FChecklist/claude-control --branch <b> --pr-url <url>`
- `bash /opt/veridian/scripts/supervisor-sweep.sh` (finds pending_review task w/ no review.json, starts `veridian-supervisor@<task_id>.service`)
- Verdict lands in `<task_dir>/review.json` (`"verdict": "approve"|...`) and `<task_dir>/task.yaml` `checkpoints[-1].recent_commits` (top = HEAD reviewed).
- Must confirm `recent_commits[0]` short SHA == live PR head SHA before trusting the verdict (else stale -> re-adopt under new task id).
- NOTE: `gh` output containing full 40-char hex SHAs gets silently truncated in this env; use `.headRefOid[0:12]` (short SHA) instead.

## Completed
- [x] Re-derived live open PR list (14 PRs, newest-first order above)
- [x] Confirmed adopt/sweep mechanism and verdict schema via prior example task (task-20260816-093439-adopted-sweep-adopt-claude-control-116-fix-watch)
- [x] Adopted all 14 PRs as real tasks (see mapping below), 2 supervisor-sweep.sh runs kicked off (each run scans the full /opt/veridian/ai-os/tasks tree so takes >120s itself; actual per-task audits run async via `veridian-supervisor@<task_id>.service`)

## Adoption mapping (PR -> adopted task_id)
- 248 -> task-20260816-120532-adopted-pr248--rebase-and-land-every-conflicting
- 247 -> task-20260816-120802-adopted-pr247--sweep-adopt-claude-control-234-ti
- 246 -> task-20260816-120805-adopted-pr246--propagate-the-real-preflight-deni
- 243 -> task-20260816-120808-adopted-pr243--reject-invalid-complexity-tier-co
- 242 -> task-20260816-120810-adopted-pr242--rca-and-resume--gtm-certification
- 241 -> task-20260816-120813-adopted-pr241--docs-status---real-part-1-4-statu
- 240 -> task-20260816-120816-adopted-pr240--sweep-claude-control-for-real-aud
- 206 -> task-20260816-120818-adopted-pr206--docs-progress---final-status-for
- 186 -> task-20260816-120820-adopted-pr186--docs--rca-for-umr-20260813-205208
- 114 -> task-20260816-120823-adopted-pr114--rca-task-20260726-171926-remove-a
- 111 -> task-20260816-120825-adopted-pr111--phase-5-browser-execution-tiers
- 98 -> task-20260816-120828-adopted-pr98--round-5--close-native-git-gh-comma
- 91 -> task-20260816-120830-adopted-pr91--resolve-pr89-merge-conflict--phase
- 75 -> task-20260816-120833-adopted-pr75--phase-2--mark-compiler-pipeline-in

## Remaining
- [ ] Wait for supervisor sweep(s) to produce review.json for all 14, verify head SHA match per task
- [ ] PR 248 -- read verdict, merge/report
- [ ] PR 247 -- read verdict, merge/report (note: CONFLICTING per gh, likely blocks merge regardless of verdict)
- [ ] PR 246 -- read verdict, merge/report
- [ ] PR 243 -- read verdict, merge/report
- [ ] PR 242 -- read verdict, merge/report
- [ ] PR 241 -- read verdict, merge/report
- [ ] PR 240 -- read verdict, merge/report
- [ ] PR 206 -- read verdict, merge/report
- [ ] PR 186 -- read verdict, merge/report
- [ ] PR 114 -- read verdict, merge/report
- [ ] PR 111 -- read verdict, merge/report
- [ ] PR 98 -- read verdict, merge/report
- [ ] PR 91 -- read verdict, merge/report
- [ ] PR 75 -- read verdict, merge/report
- [ ] Final report table
