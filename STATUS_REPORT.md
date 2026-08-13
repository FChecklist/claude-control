# Status report — 326b's real scope is already covered (verified); the real bug is a wrong-repo commit-verification defect that spuriously re-dispatched this task

UMR chain: addendum to UMR-20260813-092654-326b (chain: 084321-2962 ->
091633-8b6a -> 092654-326b -> this addendum, UMR-20260813-104321-99ff ->
P1 UMR-20260806-171945-5767)

## Verdict

**326b's real scope (PM hierarchy / single-gateway / zero-duplication /
dynamic-scope / standardized boolean-table report) is already implemented as
real, tested code — independently re-verified here, not just trusted from
the prior finding — and this task's own SPEC premise ("the prior worker made
ZERO commits") is false for the most recent prior attempt.** The genuinely
new finding of this task is a real, precisely-located bug in the platform's
own reconciliation pipeline that caused that prior attempt's real work to be
wrongly treated as "no commit evidence," triggering the spurious re-dispatch
that created this task in the first place.

## Part 1 — the SPEC's premise, checked against live state

The SPEC's "zero commits" claim is true only of the *original* 326b dispatch
(`task-20260813-095623-amendment-2--pm-hierarchy--single-gatewa`, UMR
`092654-326b` itself, real `status=killed`, confirmed via
`resource_governor.py --query-umr --umr-id UMR-20260813-092654-326b`:
`reason`: *"real systemd state 'inactive', no PR was ever opened ... no live
process and no real deliverable"*).

It is **not** true of the task this task was actually re-queued to replace:
`task-20260813-123927-fix-326b-real-no-op-blocker-with-real-im` (same title,
prior timestamp). That task:

- Made a real commit (`4eadc5a`, `docs: real dedup finding for
  UMR-20260813-092654-326b (PR #141 already covers it, not re-implemented)`,
  `STATUS_REPORT.md` rewritten with full citations).
- Pushed branch `worker/task-20260813-123927-fix-326b-real-no-op-blocker-with-real-im`.
- Opened a real, currently **OPEN** PR: **#142**,
  <https://github.com/FChecklist/claude-control/pull/142>
  ("docs: real dedup finding for UMR-20260813-092654-326b (already covered by
  PR 141)"), `task.yaml` last checkpoint `status: pending_review`.

That is real, non-empty, auditable work — not a no-op.

## Part 2 — independently re-verifying PR #142's own finding

PR #142's claim: 326b's scope is already implemented in
`scripts/pm-sentinel-tick.sh` on **PR #141** (still OPEN,
`worker/task-20260813-115823-integrate-server-native-pm-into-one-dete`,
commit `bb3fee7`). Re-checked directly rather than trusted:

```
$ git show bb3fee7 --stat
 scripts/pm-sentinel-tick.sh                       | 696 ++++++++++++++
 scripts/systemd/veridian-pm-sentinel-tick.service |  34 ++
 scripts/systemd/veridian-pm-sentinel-tick.timer   |  19 +
 scripts/test_pm_sentinel_tick.py                  | 363 +++++++++
 4 files changed, 1112 insertions(+)

$ git show bb3fee7:scripts/pm-sentinel-tick.sh | sed -n '1,24p'
#!/usr/bin/env bash
# pm-sentinel-tick.sh -- ONE integrated deterministic server-native PM tick.
# ...
#   3. UMR-20260813-092654-326b -- hierarchy / single-gateway / zero-dup /
#      dynamic-scope / standardized boolean-table report format. Real
#      finding: the dispatched task for this UMR (task-20260813-095623)
#      never started real work (task.yaml status=blocked, zero files
#      modified, zero PR) before being reconciled to status=killed -- none of
#      this scope existed anywhere before this integration.
# ...
# below goes through the EXISTING single front door, dispatch-owner-task.sh
```

Confirmed: a real, 696-line, tested (`test_pm_sentinel_tick.py`, 363 lines)
implementation of 326b's scope exists on PR #141. `gh pr view 141` confirms
`state: OPEN`, `mergeStateStatus: DIRTY` (a `STATUS_REPORT.md`-only doc
conflict, the same recurring pattern already seen on PR #133/#135/#139 — not
a code conflict).

**Disposition: not re-implemented here.** PR #141 is real and open; PR #142
already recorded this exact finding. Writing a third copy of the same
citation would itself be the duplication 326b point 3 exists to forbid.

## Part 3 — the real, new finding: why this task got spuriously re-dispatched

`resource_governor.py --query-umr --umr-id UMR-20260813-104321-99ff` (this
task's own governing UMR) records the real re-dispatch reason:

> `reconcile_stale_running_workers.py (STEP 3, task-20260807-052027): unit
> veridian-worker@task-20260813-123927-fix-326b-real-no-op-blocker-with-real-im.service
> confirmed ActiveState=failed; ... task.yaml's own last checkpoint
> status='pending_review', no real commit evidence accepted -- genuinely
> ambiguous (worker likely killed/crashed mid-work), real re-queue`

But real commit evidence *did* exist (`4eadc5a`, PR #142, both live). Traced
why the evidence gate rejected it — a real, precisely-located bug, not a
guess:

1. `task.yaml` (`task-20260813-123927-fix-326b-real-no-op-blocker-with-real-im/task.yaml`)
   records `repo: claude-control`, last checkpoint
   `status: pending_review`, `files_modified: []`, `recent_commits[0]:
   '4eadc5a docs: ...'`. This makes `reconcile_stale_running_workers.py`'s
   own `_first_recent_commit_sha()` (scripts/reconcile_stale_running_workers.py:246-285)
   produce a real candidate: `{"kind": "commit_sha", "value": "4eadc5a", ...}`.
2. That candidate is then submitted via `mark-umr-terminal --commit-sha
   4eadc5a --repo <repo>`. `reconcile_stale_running_workers.py`'s own
   `REPO_LOCAL_PATHS` dict (scripts/reconcile_stale_running_workers.py:100-105)
   and `MARK_TERMINAL_REPO_CHOICES` tuple (line 110) **do not contain
   `"claude-control"`** — even though `/opt/veridian/repos/claude-control`
   is a real, existing local checkout, and `claude-control` is this
   platform's own primary/default repo (`DEFAULT_REPO = "claude-control"`
   in `scripts/auto_phase_continuation.py:71` and
   `scripts/phase-continuation-tick.py:100`).
3. Because `repo` isn't in `MARK_TERMINAL_REPO_CHOICES`,
   `_mark_terminal()`'s own fallback (`reconcile_stale_running_workers.py:327`,
   `repo if repo in MARK_TERMINAL_REPO_CHOICES else "veridian-scripts"`)
   silently substitutes **`veridian-scripts`** as the `--repo` value, and
   because `REPO_LOCAL_PATHS.get("claude-control")` is also `None`,
   `--repo-root` is never passed at all (line 328-329, `if repo_root: cmd
   += [...]`).
4. `superboss-register.py`'s `cmd_mark_umr_terminal()` (line 7074-7076) then
   resolves the verification path as: `args.repo_root or
   DEFAULT_OCID_RESOLVER_REPO_LOCAL_PATHS.get(args.repo, ...["veridian-scripts"])`
   — i.e. it verifies commit `4eadc5a` against the **`veridian-scripts`**
   checkout, not `claude-control`, where that commit does not exist.
   `validate_umr_terminal_completion_evidence()` correctly refuses (the sha
   is real, just not in the repo being checked), and
   `reconcile_stale_running_workers.py` falls through to its last branch
   (line 456-467): "genuinely ambiguous ... real re-queue" — spawning this
   task.

`superboss-register.py`'s own `DEFAULT_OCID_RESOLVER_REPO_LOCAL_PATHS`
(line 3800-3804), the single source `p_markterm --repo`'s argparse
`choices` are drawn from (line 9388-9389: `choices=list(...)`), has the
identical gap: `{"compliance-tracker", "veridian-scripts", "projexa"}`,
no `"claude-control"` entry — so this is not a copy/paste slip local to the
reconcile script, it is a real, shared, upstream gap in the one canonical
repo-path table both callers key off.

**This is a real zero-duplication-policy defect in its own right**: 326b's
point 3 exists precisely so the platform doesn't do the exact thing this bug
caused — dispatch a second, redundant worker for already-completed work.
The fix (add `"claude-control": "/opt/veridian/repos/claude-control"` to
`DEFAULT_OCID_RESOLVER_REPO_LOCAL_PATHS` in `scripts/superboss-register.py`,
and mirror it into `REPO_LOCAL_PATHS`/`MARK_TERMINAL_REPO_CHOICES` in
`scripts/reconcile_stale_running_workers.py`) lives in the `veridian-scripts`
repo, not `claude-control` (this task's own assigned repo per its
`inputs_json.repo`). Editing `/opt/veridian/scripts` directly on this host
would itself violate 326b point 2 (SINGLE GATEWAY, NO BYPASS — "never raw
tmux, never direct file/git edits") and that live directory currently
carries unrelated uncommitted local changes from other in-flight work
(`git -C /opt/veridian/scripts status`: `dispatch_core.py`,
`pm-sentinel-tick.sh`, `quality-gate.sh`, `resource_governor.py`,
`test_pm_sentinel_tick.py` all locally modified) — not a safe target for an
out-of-scope drive-by edit.

**Real action taken instead**: logged as a real, durable registry issue
(`superboss-register.py add-issue`, see below) with the exact file/line
citations above, so a properly repo-scoped task can apply the one-line fix
through the normal single-gateway dispatch flow, instead of being lost or
silently re-discovered by a future duplicate investigation.

## Completed

- [x] Independently re-verified the SPEC's "zero commits" premise against
      live `resource_governor.py --query-umr` / `gh` state — false for the
      most recent prior attempt (`task-20260813-123927`, real commit
      `4eadc5a`, real OPEN PR #142).
- [x] Independently re-verified PR #142's own citation (PR #141,
      `scripts/pm-sentinel-tick.sh`, commit `bb3fee7`) directly against the
      real commit content, not trusted secondhand.
- [x] Traced the real root cause of why this task was spuriously
      re-dispatched despite real prior work existing: a shared repo-path
      table gap (`claude-control` missing from
      `DEFAULT_OCID_RESOLVER_REPO_LOCAL_PATHS` / `REPO_LOCAL_PATHS` /
      `MARK_TERMINAL_REPO_CHOICES`) causing `mark-umr-terminal` to verify
      real commit evidence against the wrong local repo checkout.
- [x] Logged that finding as a real, durable registry issue with exact
      file/line citations (not a raw edit to the live, out-of-scope
      `veridian-scripts` deployment).

## Remaining

- [ ] The one-line fix itself (`REPO_LOCAL_PATHS` / `DEFAULT_OCID_RESOLVER_REPO_LOCAL_PATHS`
      / `MARK_TERMINAL_REPO_CHOICES` additions) needs a task dispatched
      against the `veridian-scripts` repo through the normal single gateway
      — out of this task's own repo scope (`claude-control`).
- [ ] PR #141 and PR #142 both still need their routine `STATUS_REPORT.md`
      rebase (`mergeable=DIRTY`/`CONFLICTING`, doc-only) before merge — that
      is those PRs' own follow-up, not duplicated here.
