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

## Verdicts so far (real, from review.json written by veridian-supervisor@<task>.service)

- **PR 248**: verdict=approve tier1, head 421c2fc matches live head. Docs-only (1 progress/*.md file,
  itself a report about a prior PR-closure wave). Supervisor auto-merged autonomously (tier1 full-approval
  directive). Confirmed merged: `e34e821` in `git log origin/master`. **MERGED.**
- **PR 241**: verdict=approve tier1 (STATUS_REPORT.md + progress/*.md, no code). Docs-only=yes.
  Auto-merged 2026-08-16T12:11:55Z, confirmed via `gh pr view 241 --json state,mergedAt` = MERGED. **MERGED.**
- **PR 111**: verdict=approve tier1 (MASTER_INDEX.yaml registry entry + doc, no code). Docs-only=yes.
  Auto-merged 2026-08-16T12:12:15Z, confirmed MERGED via gh. **MERGED.**
- **PR 247**: verdict=**reject** tier1 -- byte-for-byte duplicate of work already merged to master
  (PR #223/d4ab44b). Real FAIL. **NOT MERGED**, blocked.
- **PR 246**: verdict=**reject** tier1 -- diff itself trivial/docs but self-reports the worker
  unilaterally ran `gh pr merge` on other PRs without Superboss audit (rule violation) plus a
  mischaracterized docs-only claim. Real FAIL. **NOT MERGED**, blocked.
- **PR 242**: verdict=**reject** tier1 -- diff has no real code fix, dumps debug scratch files
  incl. one embedding raw gitleaks secret-match strings; real fixes described live in separate
  unmerged branches not part of this diff. Real FAIL. **NOT MERGED**, blocked.
- **PR 240**: verdict=**reject** tier1 -- stale duplicate resubmission of work already on master
  (byte-identical progress file already at 8fa0834/9622ece) plus ~120 throwaway scratch files.
  Real FAIL. **NOT MERGED**, blocked.
- **PR 206**: verdict=**reject** tier2 -- diff deletes the real audit trail (Completed/Remaining
  checklist w/ 5 real cross-repo PR links) and replaces with a leaked "... more files changed"
  placeholder; title promises "final status" but none is recorded. Real FAIL. **NOT MERGED**, blocked.
- **PR 91**: supervisor service **failed** (not a verdict) -- GITLINK GUARD tripped: branch contains
  a bare git submodule gitlink at `pr89-work` (mode 160000), a nested checkout of a different repo
  swept in by `git add -A` (same known pattern as claude-control PRs #146/#170/#191). Audit could not
  even run. Real blocking infra defect in the branch itself, needs human fix. **NOT MERGED**, blocked.

- **PR 243**: verdict=**reject** tier1 -- diff itself docs-only, but tracing to the real underlying
  PR (FChecklist/veridian-scripts#423, task title misidentifies it as #243) it is mergeable:CONFLICTING
  against main; main already fixed the same root cause differently (commit 89b30ab, None sentinel),
  and #423's guard would crash real call paths relying on that sentinel. Real FAIL. **NOT MERGED**, blocked.
- **PR 75**: verdict=**reject** tier1 -- underlying claim (compliance-tracker PR #560 merged) is real,
  but this diff's phase-plan YAML edit is mechanically broken: new keys inserted mid-sequence break
  `yaml.safe_load` (ParserError), which would break `scripts/auto_phase_continuation.py`'s phase-detection
  for the whole file -- opposite of the change's stated purpose. Real FAIL. **NOT MERGED**, blocked.

- **PR 98**: verdict=approve tier1 -- real code fix (closes git/gh alias-based bypass of the
  interactive-session write gate, ships regression test suite). Docs-only=NO (real code+tests).
  Auto-merged 2026-08-16T12:13:59Z, confirmed MERGED via gh. **MERGED.**

- **PR 186**: verdict=**reject** tier1 -- docs-only RCA file, but its central conclusion is stale/false:
  it claims veridian-scripts#305 is "correctly not merged" (completed_unmerged), but live verification
  (gh api + git merge-base) shows #305 was fixed at a new head and actually merged ~1.5h after this
  RCA's own commit timestamp. Real FAIL (factually incorrect docs). **NOT MERGED**, blocked.

- **PR 114**: verdict=**reject** tier1 -- diff mechanically clean but stale/superseded: origin/master
  already has a more robust fix for the same duplicate-RCA-escalation problem
  (resource_governor.submit()'s task_identity dedup w/ hard-cap+retirement, added 2026-07-27 after a
  real 9h18m runaway-firing incident); this diff's independent file-glob check has no TTL/cap and
  reintroduces a silent starvation failure mode. Real FAIL. **NOT MERGED**, blocked.

## All 14 PRs audited. Final live state confirmed via `gh pr view --json state,mergedAt`
## and merge commits confirmed present in `git log origin/master`:
## 248, 241, 111, 98 = MERGED (real commits: e34e821, 3e6cf47, 2225b40, 0b2fec5)
## 247, 246, 243, 242, 240, 206, 186, 114, 91, 75 = NOT MERGED (real reject verdict or, for 91,
## a real infra guard blocking the audit itself -- see verdicts above)

## Remaining
- [x] All 14 PRs adopted, swept, and given real verdicts
- [x] 4 merges confirmed present in git log origin/master
- [x] Re-checked live open-PR list at end: 75,91,114,186,206,240,242,243,246,247 still open (matches
      the 10 real rejects/blocks above exactly) -- no new PRs appeared mid-sweep
- [x] record-completion write-back to UMR-20260816-120141-7468 done
- [x] Final report table delivered to user

TASK COMPLETE. 4/14 merged (all confirmed via gh + git log origin/master), 10/14 real-audited and
correctly left unmerged with real blocking reasons documented above. Zero self-certified verdicts --
every verdict came from a real veridian-supervisor@<task>.service run's review.json.
