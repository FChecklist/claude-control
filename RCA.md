# RCA -- UMR-20260813-111352-6973 (SPEC claim: status=running vs. live systemd success; verified already correctly terminal, no gap)

## Governing chain
- This RCA task: `task-20260813-160301-rca--umr-20260813-111352-6973-status-run`,
  governing UMR `UMR-20260813-131701-2b6a` (PM-sentinel tick).
- Subject UMR: `UMR-20260813-111352-6973`, `task_identity=owner-task-20260813-111351-1537211`,
  dispatched `veridian-worker@task-20260813-131109-execute-the-real-merge-for-audit-approve.service`
  (title: "Execute the real merge for audit-approved PR 136").

## The SPEC's claim (checked live, not trusted)
The SPEC asserted `resource_governor.py --query-umr --umr-id UMR-20260813-111352-6973` showed
`status=running` while the real systemd unit was already terminal (success) -- the known
exit-write-back-bug class where a `running`/`dispatched` row never gets corrected after its
worker actually finishes.

## Real recorded fact (verified live, not trusted from the SPEC summary)

**Real systemd state** (`systemctl --user show ...`):
- `ActiveState=inactive`, `SubState=dead`, `Result=success` -- the unit ran once and exited clean.

**Real journal** (`journalctl --user -u ...`):
```
Aug 13 13:11:13 ... Started veridian-worker@task-...-execute-the-real-merge-for-audit-approve.service ...
Aug 13 13:19:22 ... Consumed 28.234s CPU time, 433.7M memory peak, 0B memory swap peak.
```

**Real DB row** (`resource_governor.py --query-umr --umr-id UMR-20260813-111352-6973`, queried live at
the start of this task):
- `status=completed` (**not** `running`)
- `ts_dispatched=2026-08-13T13:11:13.189245+00:00` -- matches the journal's `Started` line exactly.
- `ts_completed=2026-08-13T13:19:02.153385+00:00` -- ~20s before the journal's stop-accounting line,
  consistent with normal `ExecStopPost` write-back-then-cleanup ordering, not a stall.
- `outputs_json.file_path` points at a real, on-disk `STATUS_REPORT.md` in the task's own workspace.

**Canonical cross-check tool** (`superboss-register.py reconcile-umr-status --umr-id UMR-20260813-111352-6973`,
the mechanism purpose-built for exactly this class of check):
```json
{"umr_id": "UMR-20260813-111352-6973", "is_stale": false, "current_status": "completed",
 "proposed_status": null, "evidence": {"pr_evidence": [], "note": "no real merged-PR evidence found -- no reconciliation needed"}}
```

So: as of this task actually running, the row is **already** correctly, honestly terminal. No live
instance of the exit-write-back-bug exists on this row right now.

## Was the SPEC's claim ever true?
Almost certainly yes, at some earlier moment -- `ts_completed` (13:19:02) sits well before this RCA
task was dispatched, so the SPEC's PM-sentinel-tick snapshot most plausibly observed the row mid-flight
(`running`/`dispatched`) during the ~8-minute window between `ts_dispatched` (13:11:13) and
`ts_completed` (13:19:02), before the worker's own `ExecStopPost` hook
(`worker-exit-status-bridge.py`) wrote the real terminal status back. That is an ordinary async
completion race, not a stuck/buggy write-back -- the row genuinely was still running when observed,
and genuinely finished and self-corrected shortly after, well before anyone acted on the stale
snapshot. This is the same "self-resolved between snapshot and RCA" shape already seen twice
elsewhere in this repo's history (`UMR-20260813-124141-7641`'s RCA of `UMR-20260813-060311-6eea`;
`UMR-20260813-100904-...`'s RCA of `UMR-20260813-085615-c1dc`).

## What the subject task's real work actually was (for completeness, not re-derived from scratch)
`STATUS_REPORT.md` in the task's own workspace records real, substantive work: it re-checked PR #136
(`FChecklist/claude-control`)'s live mergeability, found it genuinely `DIRTY`/`mergeable=false` (three
newer merges, PR #137/#139/#140, landed on `master` after PR #136's base and touch the same
full-file-rewrite `STATUS_REPORT.md`), correctly declined to force a stale-content merge per its own
SPEC's explicit instruction, and instead filed a `insert-pm-decision-pending` entry recommending
rebase + fresh audit, or simply closing PR #136 (since its one actionable finding, a PR #131 audit
FAIL, had already taken effect independently).

**Independently re-verified live** (`gh api repos/FChecklist/claude-control/pulls/136`): PR #136 is now
real `state=closed`, `merged=false`, `closed_at=2026-08-13T14:09:40Z` by `FChecklist` -- consistent
with (and following) the task's own recommended low-risk action.

**Independent prior corroboration, found in this repo's own already-merged history**: the root
`STATUS_REPORT.md` from a later, already-merged task (`UMR-20260813-120205-1f32`,
`task-20260813-143157`) had *already* independently re-verified this exact row and recorded:
`UMR-20260813-111352-6973` -> `completed` -> "`claude-control` PR #136 confirmed real CLOSED (not
merged) -- superseded." This RCA is therefore at minimum the 2nd/3rd independent confirmation that
this row has no gap.

## Disposition
No fix, no redispatch, no `mark-umr-terminal` write needed. The subject row was already honestly
`completed` with real evidence before this task started, cross-confirmed by the canonical
`reconcile-umr-status` tool and by an independent, already-merged prior task's own verification.
The SPEC's `status=running` observation reflects a real but transient mid-flight snapshot, not a
current gap -- the row self-corrected via its own normal `ExecStopPost` write-back path well before
this RCA task ran.

This task's real deliverable is this documentation commit (closing out
`UMR-20260813-131701-2b6a` honestly) plus the `agent_work_briefing.py record-completion` write-back.
