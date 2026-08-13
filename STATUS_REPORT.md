# Status report — real Tier-1 audit of PR #131 (server-native PM sentinel) + live-actor risk finding

UMR: UMR-20260813-101225-a248 (this task's own governing UMR)
Governing chain: UMR-20260813-084321-2962 (build native server-side PM
sentinel) with amendment UMR-20260813-091633-8b6a. Target:
`FChecklist/claude-control` PR #131, "feat: server-native hourly PM sentinel
(pm-sentinel-tick.sh)".

## Mandate

1. Perform a real, independent Tier-1 audit of PR #131 at its real current
   head SHA (self-confirmed, not trusted from the dispatching evidence).
2. Audit it as a privileged autonomous actor (dispatch-only-via-front-door,
   real zero-duplication, real per-tick cap, financial-only Owner escalation,
   no fabricated completion).
3. Compare the live deployed `/opt/veridian/scripts/pm-sentinel-tick.sh`
   against the PR branch content; if they diverge, audit the running copy.
4. Post a real `AUDIT:PASS`/`AUDIT:FAIL` comment on PR #131 naming the exact
   head SHA.
5. Merge on a real PASS; on a real FAIL, do not merge and make (not
   escalate) the call on whether the live timer should be stopped.

## Correction to the dispatching evidence

The task was dispatched with the claim that PR #131 "carries NO posted AUDIT
comment at all" as of 2026-08-13T09:45-10:05Z. Re-verified via `gh api
repos/FChecklist/claude-control/issues/131/comments`: this is stale/wrong —
two comments already existed at that point, an `AUDIT: FAIL` at 09:09:27Z
and a traceability note at 09:37:16Z, both **before** the claimed evidence
window. This task performed its own fresh, independent audit rather than
trusting either that stale claim or the prior comment's conclusions
verbatim, and reached the same verdict from its own evidence plus
additional findings the prior comment did not cover.

## Head SHA confirmed live

`gh api repos/FChecklist/claude-control/pulls/131 --jq '.head.sha'` →
`6a78798ebd7280c28727879167201591e019fb14` (single commit, no pushes since;
`mergeable=true`, `mergeable_state=clean`, `state=open`).

## Finding 1 — PR #131 as literally proposed is a non-functional no-op

- `dispatch-owner-task.sh` (the script's only real-work path, called at
  `./dispatch-owner-task.sh` in `pm-sentinel-tick.sh`) does not exist
  anywhere in `claude-control` — confirmed via `gh api search/code` (0 hits)
  and direct `contents` 404s on both `scripts/dispatch-owner-task.sh` and
  `/dispatch-owner-task.sh`.
- `claude-control/scripts/` has been retired since 2026-08-01
  (`scripts/README-RETIRED.md`: "no longer read by anything... do not add
  or edit files here for anything meant to run on the server"). Merging
  this PR as-is has **zero real production effect** regardless of the
  missing dependency.
- The PR branch's `pm-sentinel-tick.sh` (355 lines) is missing the
  financial-only Owner-escalation amendment required by
  `UMR-20260813-091633-8b6a` entirely — no `is_financial_decision`/
  `escalate_financial_decision`/`notify-owner.py` logic anywhere in it.

## Finding 2 — real divergence: production is not running this PR's content

- `diff /opt/veridian/scripts/pm-sentinel-tick.sh <PR #131 branch content>`:
  real differences (live is 429 lines, PR branch is 355 — live has the
  financial-escalation amendment, PR branch does not).
- `diff /opt/veridian/scripts/pm-sentinel-tick.sh <veridian-scripts PR #292
  branch content>` (head `ff328e7d7c8d3f8f5f26653c8a5c95faf6e87971`): **empty
  diff** — the live file is byte-identical to PR #292, a *different* PR in a
  *different* repo, not PR #131.
- `/opt/veridian/scripts` is a live git working copy currently on branch
  `worker/task-20260813-091931-amendment--server-native-pm-escalation-p` at
  that exact commit; `git merge-base --is-ancestor ff328e7d... origin/main`
  fails — production is running an **unmerged, unreviewed feature branch
  directly**, not a reviewed/merged commit.
- `veridian-scripts` PR #292 itself: `gh api .../issues/292/comments` and
  `.../pulls/292/reviews` both return empty — **0 comments, 0 reviews**,
  never independently audited.
- The two systemd unit files (`.service`/`.timer`) *do* match byte-for-byte
  between PR #131 and the live installed units; only the script diverges.

## Finding 3 — privileged-actor checklist (audited against the live/running copy, since it's the real risk surface)

| Check | Result |
|---|---|
| Dispatch only via `dispatch-owner-task.sh` (no raw tmux/file-git edits/`task-gateway.py cmd_start`) | CONFIRMED — only call site producing real work in either version |
| Real per-tick dispatch cap | CONFIRMED — `MAX_DISPATCHES_PER_TICK=5`, enforced in `dispatch_gap()` |
| Real zero-duplication, incl. cross-PM-tier | CONFIRMED — own `is_in_flight()` bookkeeping (re-verified live) **plus** `dispatch-owner-task.sh`'s own unconditional `check-content-duplicate --window-hours 6` (content-keyed, not caller-keyed, genuinely cross-tier since it's the one shared front door) |
| Financial-only Owner escalation | CONFIRMED, live copy only — narrow `FINANCIAL_KEYWORDS` gate checked first in `dispatch_gap()`, escalates via existing `notify-owner.py` and returns without dispatching. **Absent entirely from PR #131's own branch content.** |
| No fabricated completion | CONFIRMED — neither version calls `mark-umr-terminal` itself; every dispatched prompt is explicitly told "Do not fabricate completion" |
| Real gap (both versions) | **UNRESOLVED**: the "merge fresh-PASS PR" path (`completed_unmerged` rows that are `MERGEABLE`+`CLEAN`+checks-pass+`APPROVED`) dispatches a worker whose own prompt tells it to itself run `gh pr merge` + `mark-umr-terminal` — conflicts with the standing no-worker-merge rule and never re-checks the *original* PR's own tier1/tier2 classification before authorizing that self-merge. Live, automatic, no additional gate. |

## Finding 4 — re-verified SPEC background evidence (d)

`python3 resource_governor.py --query-umr --umr-id UMR-20260813-084321-2962`
→ `status=running`, `unit_name=veridian-worker@task-20260813-084351-build-native-server-side-pm-sentinel--sy.service`.
`systemctl --user show` that unit → `ActiveState=inactive`, `SubState=dead`.
`journalctl --user -u` that unit → terminated 2026-08-13T09:03:02Z
("Consumed 6min 49.072s CPU time, 2.0G memory peak"). The exit-write-back-bug
gap is real and current for this exact chain (not this task's fix target).

## Verdict

**`AUDIT:FAIL`** posted on PR #131 at head `6a78798ebd7280c28727879167201591e019fb14`
(https://github.com/FChecklist/claude-control/pull/131#issuecomment-5279274298).
Not merged — confirmed still `state=open`, `merged=false` after posting.

## Live-timer call (evidence-based, non-financial, made directly per this task's own instructions — not escalated)

Stopped and disabled `veridian-pm-sentinel-tick.timer`
(`systemctl --user stop` + `disable`; confirmed `inactive`/`disabled`,
removed from `list-timers --all`). Rationale: the code actually running in
production (a) has never itself been independently audited (PR #292: 0
comments, 0 reviews), (b) is served from an unmerged feature branch checked
out directly on the box rather than a reviewed, merged commit, and (c)
carries the same live tier2-merge-bypass gap from Finding 3 with no
additional gate protecting it. Re-enable only after: (1) the "merge
fresh-PASS PR" path is fixed to re-verify the original PR's own risk tier
before authorizing a self-merge dispatch, and (2) the fixed code lands via a
normal reviewed, merged PR into `veridian-scripts` `main` and production is
redeployed from that merged commit, not a live feature-branch checkout.

## Duplication check

- PR #135 (`claude-control`): only touches `STATUS_REPORT.md` — not the same
  content as #131, not audited here.
- PR #292 (`veridian-scripts`): real code, but scope differs from #131 (adds
  the financial-escalation amendment) and is out of this task's target repo
  — not separately merged/closed here per this task's own "do not
  duplicate" instruction. Its being unaudited is reported above as evidence
  for the live-timer call, not fixed by this task.
- `wiring_registry` row `dispatch_event-owner-task-20260813-101222-1284891`
  (flagged by the pre-task briefing) is this task's own dispatch event, not
  separate prior work.

## Real evidence trail (commands run, not paraphrased)

- `gh api repos/FChecklist/claude-control/pulls/131 --jq '.head.sha,.mergeable,.mergeable_state,.state'`
- `gh api repos/FChecklist/claude-control/issues/131/comments`
- `gh api repos/FChecklist/claude-control/pulls/131/commits`
- `gh api repos/FChecklist/claude-control/contents/scripts/pm-sentinel-tick.sh?ref=6a78798e...`
- `gh api search/code -f q='dispatch-owner-task.sh repo:FChecklist/claude-control'` → `total_count: 0`
- `gh api repos/FChecklist/claude-control/contents/scripts/dispatch-owner-task.sh` and `/dispatch-owner-task.sh` → both 404
- `gh api repos/FChecklist/claude-control/contents/scripts/README-RETIRED.md`
- `diff /opt/veridian/scripts/pm-sentinel-tick.sh <PR #131 fetched content>`
- `gh api repos/FChecklist/veridian-scripts/contents/pm-sentinel-tick.sh?ref=ff328e7d...` then `diff` against the live file → empty
- `cd /opt/veridian/scripts && git status && git log --oneline -3 && git rev-parse --abbrev-ref HEAD && git rev-parse HEAD`
- `git merge-base --is-ancestor ff328e7d... origin/main` (in `/opt/veridian/scripts`) → not an ancestor
- `gh api repos/FChecklist/veridian-scripts/issues/292/comments` and `.../pulls/292/reviews` → both empty
- `ls -la /opt/veridian/scripts/dispatch-owner-task.sh /opt/veridian/scripts/notify-owner.py` → both present live
- `python3 /opt/veridian/scripts/resource_governor.py --query-umr --umr-id UMR-20260813-084321-2962`
- `systemctl --user show veridian-worker@task-20260813-084351-....service -p ActiveState -p SubState -p Result`
- `journalctl --user -u veridian-worker@task-20260813-084351-....service --no-pager`
- `gh pr comment 131 --repo FChecklist/claude-control --body-file ...` → posted
- `systemctl --user stop veridian-pm-sentinel-tick.timer && systemctl --user disable veridian-pm-sentinel-tick.timer`
- `systemctl --user is-active/is-enabled veridian-pm-sentinel-tick.timer` → `inactive`/`disabled`
- `gh api repos/FChecklist/claude-control/pulls/131 --jq '{state,merged}'` → `{"state":"open","merged":false}` (post-comment re-check)
