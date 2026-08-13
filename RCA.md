# RCA: UMR-20260813-170234-5828 (mechanically marked `killed`)

## Summary

`UMR-20260813-170234-5828` dispatched `task-20260813-170300-fix-real-audit-fail-on-veridian-scripts`,
whose job was to fix a real, posted `AUDIT:FAIL` on `FChecklist/veridian-scripts#307`
(governing chain: Priority-1 `UMR-20260806-171945-5767`, direct follow-up to the audit
`UMR-20260813-155242-46d8`). The row was mechanically relabeled `killed` with reason
"no PR was ever opened ... no live process and no real deliverable". **That reason is
false.** The real deliverable exists and was independently re-verified live against
GitHub. The row has been corrected to `completed_unmerged`.

## What actually happened

1. The task's own SPEC required the worker to push a fix commit to the **same, already
   existing** branch/PR (`FChecklist/veridian-scripts#307`) rather than open a new PR --
   explicit instruction (e): *"Push to the SAME branch so the existing PR updates ...
   Do NOT self-merge and do NOT post your own AUDIT:PASS."*
2. The worker did exactly that (per its own `task.yaml` `completed_steps`, independently
   re-verified, not just trusted):
   - Restored `task_kind='veridian_task_create'` scoping in `scan_stuck_tasks()`.
   - Removed the unconditional, unguarded `_dispatch_core().log_dispatch_decision(r)`
     call from `run_tick()` (confirmed live: `log_dispatch_decision` has no definition
     anywhere in this repo's history, branch or main -- deletion was the correct fix,
     not an import/alias wiring).
   - Split the unrelated regressions out so `resource_governor.py` vs `main` is a clean
     additive diff, scoped to the telemetry-retention feature.
   - Re-ran the full suite.
   - Pushed commit `37d210aab1ecc399e3352429d0229db063f47952` to the existing PR branch
     (`worker/task-20260813-145927-bound-register-growth`).
   - Posted a real PR comment (`2026-08-13T17:22:38Z`) summarizing the fix and
     re-requesting audit -- no self-merge, no self AUDIT:PASS.
3. **Independently re-verified live (not trusted from any self-report):**
   - `gh pr view 307 --repo FChecklist/veridian-scripts` -> `state=OPEN`,
     `mergeable=MERGEABLE`, `mergeStateStatus=CLEAN`,
     `headRefOid=37d210aab1ecc399e3352429d0229db063f47952`.
   - `git log --oneline -1 37d210a` in `/opt/veridian/repos/veridian-scripts` -> commit
     genuinely exists: `fix(resource_governor): remove 2 real regressions flagged by
     AUDIT:FAIL on #307 (UMR-20260813-170234-5828)`.
   - PR comment timeline confirms the real audit-fail (`16:45:09Z`) and the real fix
     comment (`17:22:38Z`).
4. Because the task's **own** `task.yaml` records `repo: claude-control`,
   `branch: worker/task-20260813-170300-fix-real-audit-fail-on-veridian-scripts` (the
   scaffolding workspace for this task, not the repo the actual fix lives in), and that
   workspace genuinely has zero commits ahead of master (confirmed correct by the
   task's own supervisor: *"no changes to commit and zero commits ahead of master --
   genuine no-op"*), the task ended in `status=blocked` after the supervisor correctly
   refused to fabricate a PR for the wrong repo/branch (a documented past incident, PR
   #84) rather than silently falling back to an unrelated PR.

## Root cause

`reconcile_owner_dispatch_status.py`'s `collect_evidence()`
(`scripts/reconcile_owner_dispatch_status.py:247-252`) only searches for a PR match on
the task's **own** `task.yaml` `repo` + `branch` fields:

```python
pr_match = None
if yml.get("repo") and yml.get("branch"):
    for pr in _fetch_prs(yml["repo"], pr_cache):
        if pr["headRefName"] == yml["branch"]:
            pr_match = pr
            break
```

For a task whose real deliverable is a direct push to a **different, external** repo
(here `FChecklist/veridian-scripts`, never named in this task's own `task.yaml`
`repo`/`branch`, which point at `claude-control`), `pr_match` stays `None`
unconditionally. Combined with `real_active='inactive'` (both the worker and supervisor
systemd units had finished), the script falls into its last branch
(`scripts/reconcile_owner_dispatch_status.py:373-380`):

```python
if not pr_match and real_active in ("inactive", "no_unit", "unknown", "failed"):
    evidence["bucket"] = "STALE_LABEL_TERMINAL"
    evidence["new_status"] = "killed"
    evidence["reason"] = (
        f"real systemd state '{real_active}', no PR was ever opened, real task.yaml status="
        f"'{yml.get('status')}' -- no live process and no real deliverable; mechanically "
        "correctable to killed (orphaned dispatch, never produced a real artifact)."
    )
```

This is a **false conclusion**: it conflates "no PR in this task's own dispatch repo"
with "no real deliverable anywhere" -- ignoring that the real, verifiable evidence lives
on a different repo entirely.

**This is a confirmed second, independent occurrence** of the exact same bug class
already root-caused and documented for `UMR-20260813-155242-46d8` (see
`docs: real RCA for UMR-20260813-155242-46d8`, commit `14bd73f`), whose own RCA
explicitly flagged fixing this reconciler blind spot as an out-of-scope future follow-up.
It has now recurred, confirming the fix is still needed.

## Resolution

- No redispatch is warranted: the real, in-scope work is genuinely done and
  independently verified live (PR #307 open, mergeable, awaiting a fresh audit under
  the governing chain `UMR-20260813-155242-46d8`).
- Recorded the honest terminal outcome:
  ```
  python3 scripts/superboss-register.py mark-umr-terminal \
    --umr-id UMR-20260813-170234-5828 \
    --status completed_unmerged \
    --commit-sha 37d210aab1ecc399e3352429d0229db063f47952 \
    --pr-number 307 --repo veridian-scripts \
    --reason "..."
  ```
  This passed `validate_umr_terminal_completion_evidence()`'s real
  commit-exists-but-not-ancestor-of-main gate (PR #307 is open, unmerged --
  `completed_unmerged`, not `completed`, is the honest status).

## Real remaining follow-up (out of scope here, noted for traceability)

1. A fresh audit of PR #307 head `37d210a` belongs to the governing audit chain
   `UMR-20260813-155242-46d8`, not to this UMR.
2. The systemic fix to `reconcile_owner_dispatch_status.py` -- teaching
   `collect_evidence()` to also check for real evidence of external-repo actions
   (e.g. PR/commit references in the task's own prompt/completed_steps, not just
   `yml["repo"]`/`yml["branch"]`) before concluding "no PR was ever opened" -- remains
   undone. This is now a confirmed *recurring* bug (2 independent occurrences), not a
   one-off; a dedicated task should fix it directly rather than deferring a third time.
