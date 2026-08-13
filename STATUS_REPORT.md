# Status report — real re-check of PR #136's merge state (audit was real, merge execution was not)

UMR chain: addendum to UMR-20260813-101225-a248 (chain: UMR-20260813-084321-2962
-> a248 -> this addendum, UMR-20260813-111352-6973 -> P1 UMR-20260806-171945-5767)

## Verdict

**PR #136 genuinely cannot be merged right now, and forcing it would be a real
regression, not a stale-check false alarm.** The prior tier-1 APPROVE was real
and correctly scoped at the time it was granted. What changed since then is
also real: three more sequential worker tasks (PR #137, #139, #140) landed on
`master` after PR #136's base commit, before PR #136's own merge step ran. A
new audit-then-merge cycle is needed, not a forced merge of the stale diff —
so that is what this task dispatches, per its own SPEC's explicit instruction
not to force a stale-approval merge when mergeability has changed.

## Step 1 — real current mergeable state (`gh pr view` / GitHub REST, both agree)

```
state:              open
merged:              false
mergedAt:             null
mergeable:            false
mergeable_state:      dirty       (gh pr view's mergeStateStatus: DIRTY)
head_sha:             317fabf6dab870c546fb7c2f411139d1f6ee60ca   (unchanged since approval)
base_ref:             master
```

`gh pr view 136 --json state,mergeable,mergeStateStatus,headRefOid,baseRefName`
and `GET /repos/FChecklist/claude-control/pulls/136` (raw REST, to sidestep a
local CLI output-truncation quirk) were cross-checked and agree exactly. This
is a real, current `DIRTY`/`mergeable=false`, not the `UNKNOWN`/"still
computing" state the governing SPEC's incident text described — GitHub has
finished computing it, and the real answer is "conflicted."

## Step 2 — why: the head did not move, but `master` moved past it

`git merge-base origin/master 317fabf6...` = `ec606ae` (PR #134's merge
commit) — three real merges behind current `origin/master` tip
(`674421d`, PR #140). All three of those (`8a1f4d6`/PR #137,
`ead8711`→`95c5ce0`/PR #139, `674421d`→`8d6816a`/PR #140) touch the exact same
file PR #136 touches, `STATUS_REPORT.md` — this repo's convention is a
**full-file rewrite** per task (each task's status report replaces the whole
file, it does not append), so any two of these tasks whose branches both
started before the other merged are guaranteed to conflict on that file. A
real dry-run merge (`git merge --no-commit --no-ff` of current `origin/master`
into PR #136's real head, in a disposable clone) reproduces exactly one real
conflict: `CONFLICT (content): Merge conflict in STATUS_REPORT.md`.

So: **head did not move** (still `317fabf`, exactly what was audited — the
"no new commits since approval" precondition is genuinely met on PR #136's
own branch), but **mergeability changed** because `master` moved. That is
squarely the SPEC's second branch ("if a NEW audit is needed because
mergeability changed ... dispatch that instead of forcing a stale-approval
merge"), not the first ("if mergeable/CLEAN ... execute the real merge").
`gh pr merge 136` was deliberately **not** run — GitHub would refuse it
anyway while `mergeable=false`, and even a manual rebase-and-force-push here
would itself count as a new, unaudited commit under the SPEC's own rule.

## Step 3 — this is not just a mechanical rebase; the stale content itself matters

PR #136's actual diff (151 insertions / 143 deletions, `STATUS_REPORT.md`
only) is a full-file rewrite whose content is "real Tier-1 audit of PR #131
(FAIL) + live-timer stop for UMR-20260813-101225-a248". Checked live:
`claude-control#131` (the server-native PM sentinel PR that audit failed) is
now **`closed`, `merged: false`** — i.e. the real, correct outcome of that
audit finding already happened independently of this PR merging. Meanwhile
three newer, unrelated status reports (PR #137 dead-script deletion, PR #139
PR #135 re-check + financial-escalation dedup, PR #140 target-identifier
dedup) have already landed as the current `STATUS_REPORT.md` on `master`.
Because this repo's `STATUS_REPORT.md` convention is "latest full snapshot,
not an append-only log", merging PR #136's stale snapshot verbatim now would
silently overwrite and discard all three of those newer reports on `master`'s
live file (each remains recoverable from git history regardless, but the
live file would regress). Reconciling that — deciding what, if anything, of
PR #136's now-superseded finding is still worth keeping in the current
snapshot — is a real editorial judgment call, exactly the kind of thing a
fresh audit should make, not something this merge-execution task should
silently resolve by picking a merge strategy.

## Action taken

- **Not merged.** `gh pr merge 136` was not executed — real precondition
  (`mergeable=CLEAN`) is not met.
- **Dispatched, not forced.** Filed a real PM-decision-pending entry
  (`insert-pm-decision-pending`, `--related-umr UMR-20260813-101225-a248`)
  recommending: rebase PR #136's branch onto current `origin/master`,
  reconcile `STATUS_REPORT.md` (fold forward whatever of the PR #131
  FAIL/live-timer finding is still non-duplicated by the three newer
  reports), get a fresh tier-1 audit on the *rebased* head (its SHA will
  differ from the already-audited `317fabf`), then merge. Given PR #131 is
  already closed, the lowest-risk alternative the same decision entry
  surfaces is simply closing PR #136 without merging (its actionable
  consequence already happened); that judgment call is left to the fresh
  audit rather than decided here.

## Independent verification

- `gh pr view 136 --json state,mergedAt` / REST `merged`+`merged_at`: still
  `false`/`null` at the end of this task — confirms nothing was merged.
- `git log origin/master` after this task's own doc-only commit below:
  `origin/master` advances by exactly this task's one new commit, not by
  PR #136's `317fabf`.
