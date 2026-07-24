# PROGRESS -- task-20260724-063403-fix-supervisor-merge-report-bug

## Completed
- [x] Root-caused: `/opt/veridian/scripts/supervisor-entrypoint.sh` tier1 merge block used
      `gh pr merge "$PR_URL" --merge --delete-branch`'s combined exit code as the sole
      success/failure signal. The API-side merge could succeed while the local
      `--delete-branch` git step failed ("'master' is already used by worktree at
      '/opt/veridian/repos/claude-control'"), and the script wrongly checkpointed the
      task blocked even though the merge was real (PRs #10, #13, #14, all 3 confirmed
      via `gh pr view --json state,mergedAt` this session before this task started).
- [x] Fixed the live script (option (a) from spec): split into a plain
      `gh pr merge "$PR_URL" --merge` call followed by a separate best-effort
      `gh api -X DELETE repos/FChecklist/$REPO/git/refs/heads/$BRANCH` branch deletion
      (pure GitHub API, cannot hit a local worktree conflict). Success/failure is now
      judged solely by a fresh `gh pr view --json state,mergedAt` call, never by any
      shell command's exit code. Marked the block with
      `MERGE-DETECTION-BLOCK-START/END` comments for testability.
- [x] Added `tests/supervisor_merge_detection_test.sh`: extracts the real merge block
      out of the live script via the START/END markers (no reimplementation, so it
      can't drift) and evals it under mocked `gh`/`python3`/`timeout`. 3 scenarios:
      (1) merge succeeds + branch-delete fails -- the exact PR #10/#13/#14 repro --
      expects `completed`; (2) merge genuinely fails -- expects `blocked`; (3) `gh pr
      merge` exits non-zero but `gh pr view` already shows MERGED (idempotent-retry
      race) -- expects `completed`. All 3 pass against the fixed script. Also verified
      by reconstructing the pre-fix block and confirming the test correctly FAILS
      2/3 scenarios against it (proving the test discriminates real bug vs. fix, not
      a tautology).
- [x] Retroactive check (step 4, read-only): pulled all 12 merged PRs + 2 open PRs on
      claude-control via `gh pr list`. Cross-checked every merged PR's task.yaml
      checkpoint history against its real PR state. Only the 3 already-known cases
      (#10, #13, #14 -- fixed in prior sessions) showed the false-blocked pattern.
      The other 9 merged-PR tasks (#1-#9, e2e-test, phase-15, watchdog, phase6,
      phase3) all show accurate `completed` end-states. The 2 currently open PRs
      (#11, #12) correctly show `in_progress`, not falsely blocked. No 4th
      unnoticed instance found.
- [x] Added `ai-os/patches/supervisor-entrypoint-merge-report-fix-2026-07-24.diff` to
      the repo's existing patch-archive convention (matches how prior
      supervisor-entrypoint.sh changes were recorded, e.g.
      `supervisor-entrypoint-deployment-logging-2026-07-23.diff`), documenting the
      real diff applied to the live server script.

## Remaining
- [ ] Push this branch and open the PR; let this task's own tier1 auto-merge (using
      the now-fixed live script) serve as the real-world regression test requested
      by the spec's EXPECTED_OUTPUT -- confirm via `gh pr view --json state,mergedAt`
      and the resulting task.yaml checkpoint that it lands as `completed`, not
      `blocked`.
- [ ] Final checkpoint summary.
