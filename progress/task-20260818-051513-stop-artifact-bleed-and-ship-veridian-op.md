# task-20260818-051513-stop-artifact-bleed-and-ship-veridian-op

Resubmission of INS-20260818-051253-fdfb (prior submit failed on CLI arg-parsing before any
worker ran). Executing the Owner-approved reorg + plugin-scaffold plan verbatim per KNOWN_CONTEXT.

## Completed

- [x] Fetched origin, confirmed branch `worker/task-20260818-051513-stop-artifact-bleed-and-ship-veridian-op`
      is checked out at current `origin/master` (9dbb11d).
- [x] Inventoried real root contents via `git ls-tree --name-only HEAD` (not `find`, which the
      sandbox's `find_root_walk_guard` hook rejects for unscoped multi-arg invocations, and which
      also showed a display-layer truncation artifact on long output in this session -- used
      `git ls-tree`/`git ls-files` for all authoritative listings instead). Real count: 26
      `RCA_*.md` files + `RCA.md` (27 incident reports, not the 25 estimated in KNOWN_CONTEXT --
      used the real repo contents as source of truth per task instructions), 6 merge/audit
      reports (matches), 1 `STATUS_REPORT.md`, 4 instruction files, plus one file NOT in
      KNOWN_CONTEXT's inventory: `report_body.md` (single-commit, written by `gen_report.py`,
      genuine Tier-3 triage report content, not a scratch leftover) -- treated as an audit report
      and moved to `reports/audits/report_body.md` unrenamed (git-mv'd as-is, same as the other
      merge/audit reports), flagged in PR description as a judgment call since KNOWN_CONTEXT
      didn't account for it.
- [x] `git mv`'d all 26 `RCA_*.md` files into `reports/incidents/` as-is.
- [x] `git mv RCA.md reports/incidents/RCA_20260813_UMR-20260813-060311-6eea.md` (explicit rename
      case, content unchanged).
- [x] `git mv`'d 3 AUDIT_*.md files + `AUDIT_AND_MERGE_REPORT.md` + `TOOL_INTEGRATION_AUDIT_...`
      into `reports/audits/`, 3 `MERGE_REPORT_*.md` into `reports/merges/`.
- [x] `git mv STATUS_REPORT.md reports/audits/STATUS_REPORT_20260814_part1-4-status.md` (explicit
      rename case, content unchanged).
- [x] `git mv`'d `report_body.md` into `reports/audits/` (unrenamed).
- [x] `git mv AI_AGENT_INSTRUCTION_MANUAL_DRAFT.md archive/drafts/AI_AGENT_INSTRUCTION_MANUAL_DRAFT_2026-07-19.md`.
- [x] `git mv VERIDIAN_Review_Framework_evaluated_2045rows.csv archive/data/...` (unchanged).
- [x] `git mv`'d all 8 batch45 `.py` files + 4 sibling `.json` files into `scripts/batch45/`;
      updated the small number of repo-root-relative path references (`ai-os/TASK_COMPLETION_...`
      in `build_list.py`; `dispatch_prompts/`, `dispatch_logs/` in `build_dispatch_prompts.py` and
      `run_dispatch.py`) to `../../` since those directories stay at repo root -- sibling-to-sibling
      references (`objectives_45.json`, `triage_45.json`, `redispatched_ids.json`,
      `bucket_result.json`) needed no change since they move together.
- [x] `git mv .tmp archive/triage-2026-08-13/.tmp` and `git mv .triage archive/triage-2026-08-13/.triage`
      (entire dirs moved, internal structure preserved, e.g. `.triage/out/` is now
      `archive/triage-2026-08-13/.triage/out/`). Content not deleted, per constraint.
- [x] `git rm`'d the 4 confirmed-zero-reference files: `commit-msg.txt`, `commit-msg2.txt`,
      `pr-body.md`, `redispatched_task_ids_list.json`.
- [x] Appended `.tmp/`, `.triage/`, `commit-msg*.txt`, `commitmsg.txt` to `.gitignore`.
- [x] Replaced `AGENTS.md` with the exact verbatim text from KNOWN_CONTEXT's PROPOSED_AGENTS_MD
      (109 lines, under the 200-line success criterion).
- [x] Root file count (tracked): `AGENTS.md`, `CONTROLLER.yaml`, `.gitignore`,
      `priority16_e2e_testing_plan.md`, `priority19_dubai_e2e_testing_plan.md`, `README.md`,
      `SUPERBOSS_DISPATCH_PROMPT.md` = 7 tracked root files (+ `PROGRESS.md`, untracked/gitignored,
      always present on disk = 8 total via `find -type f`). This is below the "roughly 10-14"
      estimate in SUCCESS_CRITERIA; flagged honestly in the PR description rather than padding
      root with anything artificial to hit the number -- the actual repo had fewer genuinely
      root-level instruction/report files than the planning session estimated.

## Remaining

- [ ] Scaffold `plugin/veridian-ops/` (plugin.json, settings.json, agents/log-triage.md,
      agents/spec-reviewer.md, skills/inventory/SKILL.md, skills/veridian-audit/SKILL.md,
      hooks/hooks.json, hooks/no_duplicate_report_guard.py, hooks/verify_gate.py).
- [ ] Scaffold `.claude-plugin/marketplace.json`.
- [ ] Build and run the two stdin fixtures against `no_duplicate_report_guard.py` (banned-name
      exit 2, valid-new-name exit 0); include both fixtures + the exact check in the PR body.
- [ ] Validate all new JSON files with `python3 -m json.tool`.
- [ ] Commit + push incrementally.
- [ ] Write PR description enumerating every git mv/rm/new file explicitly, flagging the 3
      explicit NOT-done items (verify-config.json, plugin install, b6fa second-pass split).
- [ ] `record-completion` write-back to UMR-20260818-051442-ab1c.
- [ ] Do NOT run `gh pr create` -- pipeline opens the PR automatically since this diff contains
      real source/config changes.
