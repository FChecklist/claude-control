# PROGRESS -- task-20260724-041754-self-sustaining-system-engine-phase2-cle

## Completed
- [x] SCOPE 1: verified `registries.self_sustaining_system_engine` already exists, real and
  identical, in BOTH `/opt/veridian/ai-os/MASTER_INDEX.yaml` and
  `/opt/veridian/repos/claude-control/ai-os/MASTER_INDEX.yaml` (added by the already-merged
  commit b137579, part of PR #10) -- it points at the sqlite table, SOFTWARE_CATALOG.yaml,
  STANDING_DIRECTIVE.yaml's v2_self_sustaining_system_engine key, both 2026-07-24 cron entries,
  and KNOWLEDGE_ENGINE_PHASE3_CANDIDATES_2026-07-24.yaml. No new write needed -- the SPEC's
  premise that both locations were "found missing it" traces to a buggy verification one-liner
  (`'self_sustaining_system_engine' in d['registries']`) that checks string membership against a
  YAML *list* of dicts (always False) instead of checking each entry's `id` field. No file changes.
- [x] SCOPE 2: ran `python3 /opt/veridian/scripts/task-gateway.py close` for real against
  task-20260724-033446-self-sustaining-system-engine-phase2-con. First real run exposed a genuine
  bug: `knowledge_engine_reverify` returned `NO_TOUCHED_ROWS` because the reverify's local
  `git diff origin/master...HEAD` goes silently empty once the branch is fully merged AND any
  worktree of this shared repo has fetched that merge (worktrees share `refs/remotes/origin/*`) --
  exactly the state `close` is normally called in. Fixed `scripts/task-gateway.py`
  (`_changed_files_for_task`): when the branch is confirmed MERGED, ask GitHub directly
  (`gh pr view --json files`) for the PR's real file list instead of trusting local ref state;
  local diff remains the fallback for NOT_MERGED tasks. Re-ran close for real after the fix:
  `knowledge_engine_reverify.status = REVERIFIED`, 3 real touched rows (MASTER_INDEX.yaml,
  SOFTWARE_CATALOG.yaml, STANDING_DIRECTIVE.yaml) recomputed + confirmed VERIFIED_MATCH.
- [x] SCOPE 3: root-caused the in_progress -> completed checkpoint skip against
  task-20260724-033446's own history (5x in_progress, then straight to completed at 03:56:47,
  note "worker finished, no changes to commit"). Traced to `worker-entrypoint.sh`'s clean-tree
  shortcut (lines ~332-336 pre-fix): the AI agent had already self-committed its real changes
  during the main invocation, so the working tree was clean by the time the script checked --
  the script wrongly read "clean tree" as "no work happened" and short-circuited straight to
  `--status completed`, skipping quality gates, `pending_review`, and the supervisor entirely.
  Two-layer fix: (1) `worker-entrypoint.sh` now only takes the no-op shortcut when the branch has
  zero commits ahead of the real default branch (`git rev-list --count origin/$DEFAULT_BRANCH..HEAD`)
  -- any real commits fall through to the normal quality-gate + pending_review + supervisor-start
  path; (2) `veridian-task.py`'s `cmd_checkpoint` now hard-rejects (exit 1, no state change) any
  direct transition to `completed` unless `pending_review` already appears in that task's own
  checkpoint history -- a real state-machine guard, not just a fix to one caller. Verified with an
  isolated manual reproduction (throwaway task.yaml fixture, cleaned up after): direct
  in_progress -> completed was rejected (exit 1, checkpoints stayed empty); pending_review then
  completed both succeeded. `scripts/veridian-task.py` and `scripts/worker-entrypoint.sh` newly
  tracked in this repo (previously live-only at /opt/veridian/scripts/, with no in-sync tracked
  source -- compliance-tracker's copy is present but hundreds of lines stale).

## Remaining
- [x] Commit + push + PR (#11: https://github.com/FChecklist/claude-control/pull/11, separate from #10)
- [ ] Final checkpoint summary to Owner
