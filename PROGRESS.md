# PROGRESS -- task-20260723-045924-governance-build-owner-notifications-202

## Completed
- [x] Built `scripts/notify-owner.py`: sends real email via Resend API (key from
      `shared/.env`, `RESEND_API_KEY`) to raajat.agarwal@gmail.com. CLI takes
      `--subject`/`--body`, optional `--dedupe-key`. Rate-limited to 1 email per
      distinct issue signature per hour via a JSON state file
      (`ai-os/logs/notify-owner-state.json`, content-hash keyed, self-pruning >24h).
      Deployed live at `/opt/veridian/scripts/notify-owner.py`.
- [x] Real test sends confirmed against the live Resend API (not assumed):
      message id `d08a0b6e-35a4-4c70-a0fa-bef7e26be6a9` (first send) and a second
      send via the integration path both returned real Resend ids. (Had to add a
      `User-Agent` header -- Cloudflare/Resend returns HTTP 403 error 1010 on
      Python's default urllib UA with no header; curl with the same key worked
      immediately, confirming it was a client-header issue, not a key/auth issue.)
- [x] Wired into `scripts/health-check-15min.py`:
      - Existing `ATTENTION.md` write left completely unchanged.
      - New: for each anomaly already detected this cycle, calls notify-owner.py
        with a digit-stripped hash of the anomaly text as the dedupe key (so a
        changing count, e.g. "14 unit(s)" -> "15 unit(s)", doesn't count as a new
        issue and re-spam). notify-owner.py's own hourly rate limit makes this
        safe to call every cycle.
      - New: blocked-task escalation lives in the same file (matches scope: "two
        consecutive health-check cycles"). `check_tasks()` now also returns
        `blocked_task_ids`; `get_prev_blocked_ids()` reads the previous cycle's
        JSONL record (read *before* this cycle's record is appended) so a task
        blocked in both the current and previous cycle is "confirmed" (30 min).
        One email per confirmed task id, deduped via notify-owner.py.
- [x] Judgment call, verified against live data before shipping: the task pool
      currently has 229 status=blocked tasks, all of them already stale (0 have
      checkpointed in the last 2h -- confirmed by direct query). Without a
      recency filter, first activation of the blocked-task escalation would have
      sent ~229 emails for multi-day-old abandoned/archived tasks instead of live
      problems. Added `is_stale_blocked()` (checkpoint age > 2h => skip) so only
      genuinely live blocked tasks escalate. Verified: pre-filter confirmed-blocked
      count = 229, post-filter = 0 (correct -- none of the current backlog is live).
- [x] Live-tested the full modified `health-check-15min.py` end to end
      (`python3 scripts/health-check-15min.py`): runs clean, compiles, ATTENTION.md
      path untouched, anomaly/blocked-notify paths exercised directly and confirmed
      working without breaking the existing summary/log/rotate behavior.
- [x] Deliverable files committed into this task's branch, mirroring the live
      server paths (`/opt/veridian/scripts/...`), since `/opt/veridian/scripts`
      and `/opt/veridian/ai-os` themselves are not under git (server-local ops
      dirs per `/opt/veridian/README-SERVER.md`) -- the real, working edits are
      live on the server; these copies are the durable record/PR artifact.

## Remaining
- [ ] None. Ready for review. Checkpoint to be set to status=pending_review with
      the real Resend message id as evidence.

## Out of scope (per task prompt, intentionally not touched)
- credit-accountant.py itself was not edited -- the blocked-task check lives in
  health-check-15min.py per the Scope section's explicit wording ("Integration
  point for tasks that remain status=blocked across two consecutive
  health-check cycles"), which already reads every task.yaml each cycle.
- No general-purpose notification framework; no other script's output format
  changed; no security/network monitoring; no log retention policy; no mobile
  notifications.
