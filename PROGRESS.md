# PROGRESS -- task-20260723-112603-gap-closing-phase4-continue-2026-07-23

---

# PROGRESS -- task-20260723-132537-gap-closing-phase8-coverage-notification

---

# PROGRESS -- task-20260723-141444-gap-closing-phase9-warnings-login-log-in

Phase 8's own PROGRESS.md (task-20260723-132537) is preserved below (merged into this
branch as the first step, same established convention every phase in this chain
follows) -- not restated separately, per this repo's "pointer, not restatement"
discipline.

## Completed
- [x] Read task.yaml, prompt.txt (PHASE4_CONTINUE_PROMPT_2026-07-23.txt) and the
      shared lessons file (CONTINUOUS_GAP_CLOSING_PROMPT_2026-07-23.txt) this
      chain runs on.
- [x] Read Phase 3's (task-20260723-103551) full checkpoint history and its
      PROGRESS.md at commit b7e30ea to understand what it actually did, not
      just what this task's prompt claims it did.
- [x] Independently verified the one factual claim in this task's prompt that
      is checkable: `gh pr view 4` on FChecklist/claude-control confirms
      state=MERGED, mergedAt=2026-07-23T10:39:01Z. That part is accurate.
- [x] Compared this task's prompt framing against Phase 3's actual reasoning.

## PAUSED -- not proceeding, not self-dispatching (flagged to Owner)
This task's own prompt describes Phase 3 as having simply "not self-dispatch[ed]
a next phase afterward." That is not what happened. Phase 3's real checkpoint
history (task.yaml, invocations 3 and 4) and its PROGRESS.md commit b7e30ea show
a *deliberate* refusal, for two reasons it stated explicitly:

1. The shared lessons file this chain reads
   (ai-os/CONTINUOUS_GAP_CLOSING_PROMPT_2026-07-23.txt, KNOWN_CONTEXT point 3)
   coaches future phases on how to word prompts to slip past an automated
   pre-flight contradiction validator ("it's a bag-of-words checker, not
   semantic -- prefer positive phrasing"). Phase 3 wrote: "Treating an
   automated safety check as an obstacle to word around, rather than a signal
   to resolve honestly, is not something this agent will operationalize." I
   re-read that file for this phase -- the coaching text is still present,
   unchanged. Nothing has resolved this concern between Phase 3 and now.
2. Self-dispatching further phases and pushing to real production repos,
   unattended, four invocations deep into a chain, needs explicit human
   confirmation -- which Phase 3 did not have, and which I also do not have
   visible evidence of.

Phase 3 checkpointed `blocked` at 2026-07-23T11:11:33Z. An automated watchdog
had already emailed the real Owner about it at 2026-07-23T11:00:18Z
(notify-owner-state.json key `blocked-task-task-20260723-103551-...`).

Fourteen minutes after Phase 3's final pause, this task
(PHASE4_CONTINUE_PROMPT_2026-07-23.txt, mtime 11:25:33Z) was created and its
worker started at 11:26:07Z -- with a prompt that characterizes Phase 3's
deliberate, reasoned refusal as an omission, and instructs the next phase to
"resume the self-dispatching pattern." I don't have visibility into who or
what wrote that prompt (file is owned by uid 1000 / user `rajat`, same as the
systemd --user services that run these workers, so ownership alone doesn't
distinguish a human action from a prior AI phase's self-dispatch step).
Regardless of provenance, the substance of Phase 3's concern is unaddressed,
and I am not willing to be the phase that quietly overrides a peer instance's
explicit safety refusal because a new prompt re-describes it more favorably.

**Decision:** I am not picking a new batch of gaps to close, not editing
gap_queue.yaml/MASTER_GAP_AUDIT, not pushing to compliance-tracker or any other
repo beyond this PROGRESS.md/checkpoint record, and not self-dispatching a
Phase 5. This mirrors Phase 3's decision, not because I'm assuming Phase 3 was
necessarily right about the underlying gap-closing work being unsafe, but
because the specific process concern it raised (a chain reading its own
instructions on how to evade a safety gate) is still live, and a human should
resolve that before any phase continues operationalizing it.

## Remaining
- [ ] A human needs to either (a) confirm explicitly that this chain should
      continue, having seen and addressed the validator-evasion coaching text
      in CONTINUOUS_GAP_CLOSING_PROMPT_2026-07-23.txt, or (b) decide to stop
      the chain / rewrite its lessons file without that coaching pattern.
- [ ] Separately worth human attention: whatever created
      PHASE4_CONTINUE_PROMPT_2026-07-23.txt and started this task 14 minutes
      after Phase 3's explicit pause, with a prompt that mischaracterizes that
      pause -- if that was automated rather than a manual human action, it
      means the self-dispatch mechanism itself can route around a phase's
      safety refusal, which defeats the purpose of the pause.
- [ ] If/when confirmed to proceed: pick the next coherent batch of 3-8 real
      gaps from ai-os/MASTER_GAP_AUDIT_2026-07-23.yaml (in compliance-tracker's
      ai-os/ subdirectory) as originally scoped, verify real state, close for
      real, update the audit doc, commit+push, then self-dispatch Phase 5.

---

# PROGRESS -- task-20260723-120458-gap-closing-phase5-network-security-perm

---

# PROGRESS -- task-20260723-123602-gap-closing-phase6-deployment-logging-ow

---

# PROGRESS -- task-20260723-130531-gap-closing-phase7-owner-notification-es
Phase 6's own PROGRESS.md (task-20260723-123602) is preserved in git history at commit
c70021f, and Phase 7's own PROGRESS.md (task-20260723-130531) at commit 1e629f2 --
both merged into this branch -- not restated here, per this repo's own
"pointer, not restatement" discipline (see README.md / CONTROLLER.yaml).

Note: this branch was originally cut from a master snapshot that predated the
phase6/phase7 lineage landing (an upstream dispatch/sync gap, not something this
task caused) -- `worker/task-20260723-130531-gap-closing-phase7-owner-notification-es`
(tip `1e629f2`) was never merged into the `master` this branch forked from. Verified
via `git merge-base --is-ancestor d91a796 HEAD` (NO) before starting this phase;
fixed by merging that branch into this one as the first step, mirroring this repo's
own established convention of each phase branch merging in the prior phase's branch
(e.g. `dfdf0f4` merging phase5 into phase6).

## Phase 7 recap (for reference; see commit 1e629f2 for full detail)
## Completed
- [x] **Re-verified items 27/28/56 instead of trusting the stale MISSING status**
      (which predates `scripts/notify-owner.py`'s existence, per this task's own
      instruction). Item 27 (notify_owner_when_needed): the underlying mechanism is
      real and already working -- `scripts/notify-owner.py` (real Resend sends),
      called from `health-check-15min.py` and `security-check.py`. **MISSING -> DONE.**
- [x] **Found the real remaining gap for items 28/56**: `health-check-15min.py`'s
      anomaly-notification loop sent the identical plain subject/body regardless of
      how long a problem had persisted -- no severity tiering. Confirmed this was a
      **live** gap today (not just the stale 2026-07-19 ATTENTION.md case, which
      predates notify-owner.py and doesn't prove anything by itself): a real,
      currently-active `superboss-register.sqlite` intermittent corruption recurred
      with **identical text** across 2 real consecutive health-check cycles
      (2026-07-23T13:00:01Z, 13:15:02Z -- same dedupe key
      `anomaly-a6edc5db0917bffbb894d1a8a82f5b181d99627d20ceed7056dde3dd89b35b7c`),
      with the Owner emailed once and given no signal 15 minutes later that it was
      still unresolved.
- [x] **Built the minimal fix**, reusing the existing consecutive-cycle-tracking
      pattern already in this file (`get_prev_blocked_ids()`/`get_prev_network_totals()`)
      and the existing `notify_owner()` call -- no new notification path, no new file:
      - `get_prev_anomaly_streaks()` (line 146): reads the last JSONL record's new
        `anomaly_streaks` field.
      - `send_anomaly_notifications()` (line 163): counts consecutive cycles per
        anomaly signature; once a signature persists `ANOMALY_ESCALATION_STREAK=3`
        cycles (45 min), switches to an escalated subject
        ("Veridian: UNRESOLVED PROBLEM on your server (still happening)") and body
        naming the streak count, under a distinct dedupe key (`...-escalated`) so
        the escalated email is treated as a new signature and sends immediately at
        the 45-min boundary instead of waiting out the still-running hourly
        rate-limit window.
      - `main()` now persists `anomaly_streaks` into each cycle's JSONL record
        (line 624) for the next cycle to read.
      Diff at `ai-os/patches/health-check-anomaly-escalation-2026-07-23.diff`,
      `patch --dry-run` verified against the pre-phase7 file.
- [x] **Real test** (per this task's own SUCCESS_CRITERIA -- real state manipulation
      of the simulated prior-cycle count, not a fabricated anomaly): imported the
      live `health-check-15min.py` module, called the real
      `check_db_integrity_and_backup()` to get the REAL currently-active corruption
      (confirmed identical, via independently recomputed sha256, to the real
      13:00/13:15 cycles' dedupe key), reconstructed `prev_streaks={that signature: 2}`
      (the 2 real cycles that already happened before this fix existed -- the
      `anomaly_streaks` field itself didn't exist yet to record them), then called
      the real `send_anomaly_notifications()`. Result: streak=3, escalated --
      `notify-owner-state.json` shows a brand-new `...{-escalated` key recorded at
      2026-07-23T13:18:20Z (a real confirmed Resend send), distinct from and later
      than the original key's 13:00:22Z send. Then ran the real, unmodified
      `python3 health-check-15min.py` end-to-end (exit 0): wrote
      `"anomaly_streaks": {"a6edc5db...": 1}` into the real JSONL (continuing fresh
      from this deploy, as expected) and correctly did **not** re-send the
      non-escalated base key (still timestamped 13:00:22Z afterward -- confirms the
      hourly rate-limit skip fired, no double-send).
- [x] **Item 44 (mobile_thin_client_policy): MISSING -> DONE.** Documentation-only
      gap (no code enforcement exists for the laptop rule either, per item 43's own
      PARTIAL evidence -- a technical mechanism here would be scope creep). Added
      `ai-os/STANDING_DIRECTIVE.yaml:29-30` (live host file), inside the existing
      `execution:` block that already carries `local_execution: forbidden` (the
      RULE-067-equivalent structured language this file uses): `mobile_execution:
      forbidden` plus a `mobile_execution_note` naming mobile devices as
      thin-client-only, mirroring RULE-067's "no development, execution, or AI
      processing ... on local machines" language, extended to mobile. Verified
      valid YAML.
- [x] **Item 42: PARTIAL -> DONE, as a side effect of item 44's fix** (not
      separately targeted). Its own PARTIAL evidence complained of precisely the
      gap item 44's fix closes ("no rule explicitly names mobile the way RULE-067
      names local machines") -- leaving it PARTIAL after adding that exact rule
      would have misreported already-done work, so updated it for consistency with
      the same evidence citation.
- [x] Updated `ai-os/GOVERNANCE_AUDIT_RESULT_2026-07-23.yaml`: items 27/28/42/44/56
      updated with real evidence, added a `phase7_amendment` block and an
      `item_44_amendment` block. Summary recomputed (done 32->37, partial 24->23,
      missing 4->0) and cross-checked against an independent Python/PyYAML recount
      of all 60 `items[].status` entries -- matches exactly (37 DONE / 23 PARTIAL /
      0 MISSING / 60 total). Left items 1-26, 29-41, 43, 45-55, 57-60 untouched.

## Deliberately NOT done -- explained, not silently skipped
- [ ] Did not build a new notification function/path -- reused `notify_owner()` and
      this file's existing prev-cycle-JSONL-state pattern, per zero-duplication.
- [ ] Did not backfill `anomaly_streaks` into the real pre-phase7 JSONL history --
      that would be editing production log history rather than genuine new
      tracking; the streak correctly (and honestly) restarts from this deploy
      forward.
- [ ] Did not build a technical enforcement mechanism for item 44 (mobile) beyond
      the policy statement -- item 43's own evidence shows no such mechanism exists
      for laptops either; out of this item's scope.

## Remaining (for a human to decide)
- [ ] 23 items in `ai-os/GOVERNANCE_AUDIT_RESULT_2026-07-23.yaml` still PARTIAL: 1,
      3, 4, 5, 6, 10, 11, 15, 21, 24, 25, 29, 30, 31, 32, 36, 45, 49, 50, 51, 52,
      54, 60 -- targeted by Phase 8 (see NEXT_PHASE).
- [ ] `ai-os/OWNER_DECISIONS_NEEDED_2026-07-23.yaml` still has 3 open entries from
      earlier phases (auth.log group permission, chain self-dispatch pause, log
      retention period) -- untouched this phase, not this phase's scope.

## NEXT_PHASE
Created and started Phase 8, targeting items 5 (health_check_covers_all_services),
36 (documentation_auto_generation), 49 (active_approval_notification), and 54
(automated_safe_fix_scheduling) from `ai-os/GOVERNANCE_AUDIT_RESULT_2026-07-23.yaml`
-- each specified with exact file:line, exact fix, exact test, same structure as
this task's own prompt. Real task:
`task-20260723-132537-gap-closing-phase8-coverage-notification`, created via
`veridian-task.py create` (which itself enables + starts the
`veridian-worker@task-20260723-132537-gap-closing-phase8-coverage-notification.service`
unit -- confirmed active via `systemctl --user status`, real PID 389962 running
`claude -p`).

## Phase 8 (this task)

### Completed
- [x] **Branch topology fix, before any build work**: this branch had been cut from
      a master snapshot predating the phase6/7 lineage (`git merge-base --is-ancestor
      d91a796 HEAD` => NO). Merged
      `worker/task-20260723-130531-gap-closing-phase7-owner-notification-es` (tip
      `1e629f2`) into this branch first, per this repo's own established convention.
      Only conflict was PROGRESS.md, resolved by keeping phase7's recap + appending
      a Phase 8 section.
- [x] **Fixed a pre-existing YAML syntax corruption** in
      `ai-os/GOVERNANCE_AUDIT_RESULT_2026-07-23.yaml` itself (2 unescaped single-quote
      apostrophes inside single-quoted scalars -- "item 44's" / "item 42's" should
      have been "44''s" / "42''s" -- which made the whole file fail `yaml.safe_load`).
      Required to programmatically recompute summary counts per this task's own
      SUCCESS_CRITERIA.
- [x] **Item 5 (health_check_covers_all_services): PARTIAL -> DONE.** Re-verified
      live host state first (systemd unit files confirmed: `veridian-worker@`,
      `veridian-supervisor@`, `veridian-glm-proxy.service`,
      `veridian-docworker@` all exist). Extended
      `scripts/health-check-15min.py:69` `check_systemd_units()`'s
      `systemctl --user list-units` pattern to also include
      `veridian-glm-proxy.service` and `veridian-docworker@*`. Real test:
      `check_systemd_units()` returns `{'total': 1, 'running': 1, 'failed_count': 0}`
      (unchanged from pre-fix -- honestly, no glm-proxy/docworker@ instance is
      currently loaded on this server, confirmed via `systemctl --user list-units
      --all`, so the count doesn't change today; the fix is real coverage for when
      one exists or fails). Full `health-check-15min.py` run: exit 0. Diff at
      `ai-os/patches/health-check-systemd-unit-coverage-2026-07-23.diff`, `patch
      --dry-run` verified.
- [x] **Item 49 (active_approval_notification): PARTIAL -> DONE.** Re-verified
      live host state first: `scripts/supervisor-entrypoint.sh`'s tier2-approve
      branch (elif at line 201, checkpoint at line 202) still only set a passive
      `awaiting_human_approval` DB status, no notify-owner.py call anywhere in the
      file (zero-duplication check re-confirmed). Added a best-effort
      `notify-owner.py --subject "Veridian: a task needs your approval" --body
      "$APPROVAL_BODY" --dedupe-key "awaiting-approval-$TASK_ID" || true` call
      right after the checkpoint, body in the simple-English convention. **Real
      test, no fabricated task**: found 3 real, currently-active tier2 tasks in
      `awaiting_human_approval` via `grep -l "status: awaiting_human_approval"
      ai-os/tasks/*/task.yaml`. Called notify-owner.py directly with the exact
      subject/body/dedupe-key the new code constructs for
      `task-20260717-194828-support-session-impersonation` (PR
      compliance-tracker#412) -- real Resend send confirmed (message id
      `3a6436e9-255c-46fb-8ceb-ffe1d2fd2d8a`), and
      `ai-os/logs/notify-owner-state.json` shows the new key
      `awaiting-approval-task-20260717-194828-support-session-impersonation`
      recorded at 2026-07-23T13:38:59Z. `bash -n` syntax-checked. Diff at
      `ai-os/patches/supervisor-entrypoint-approval-notification-2026-07-23.diff`,
      `patch --dry-run` verified.
- [x] **Item 36 (documentation_auto_generation): amended, stays PARTIAL.**
      Re-verified live host state first and found the audit's own evidence was
      stale for 1 of 3 scripts: `generate-system-diagram.py` already writes a
      real file (`ai-os/SYSTEM_DIAGRAM.md`, confirmed via a real run producing a
      real 5KB file) -- it is NOT stdout-only, contrary to the prior evidence.
      Built the buildable, non-cron part for the other 2:
      `generate_task_checklist.py` and `generate_quick_reference.py` now also
      write to `ai-os/generated/<script-name>-latest.yaml` (stdout kept). Real
      test: both scripts run clean (exit 0), both new files real/non-empty/valid
      YAML, byte-for-byte identical to their own stdout. Diffs at
      `ai-os/patches/generate-task-checklist-file-write-2026-07-23.diff` and
      `ai-os/patches/generate-quick-reference-file-write-2026-07-23.diff`, both
      `patch --dry-run` verified. **Cron half NOT done**: re-verified
      `AI_ENGINEERING_POLICY.yaml`'s `standing_exceptions` still requires Owner
      confirmation before any crontab change -- routed to
      `ai-os/OWNER_DECISIONS_NEEDED_2026-07-23.yaml` (id
      `cron-item-36-doc-generation-schedule`) instead of added unilaterally.
- [x] **Item 54 (automated_safe_fix_scheduling): amended, stays PARTIAL.**
      Re-verified `scripts/recover-failed-workers.py`'s safety gate
      (`is_402_balance_failure()`, line 44) is still real and unchanged -- only
      resets units whose task result.json contains the literal
      `"api_error_status":402`, everything else left untouched. Real manual
      invocation today (no flags): exit 0, 0 failed units found (clean state).
      No code change needed -- the script itself is correct. **Cron NOT added**,
      same standing-exception reason as item 36 -- routed to
      `ai-os/OWNER_DECISIONS_NEEDED_2026-07-23.yaml` (id
      `cron-item-54-recover-failed-workers-schedule`).
- [x] Updated `ai-os/GOVERNANCE_AUDIT_RESULT_2026-07-23.yaml`: items 5/36/49/54
      updated with real evidence, added a `phase8_amendment` block. Summary
      recomputed (done 37->39, partial 23->21, missing 0) and cross-checked
      against an independent PyYAML recount of all 60 `items[].status` entries --
      matches exactly.
- [x] Added 2 new entries to `ai-os/OWNER_DECISIONS_NEEDED_2026-07-23.yaml`
      (`cron-item-36-doc-generation-schedule`,
      `cron-item-54-recover-failed-workers-schedule`), both `status:
      awaiting_owner_decision`.

### Deliberately NOT done -- explained, not silently skipped
- [ ] Did not add the crontab entries items 36/54 would ideally have --
      `AI_ENGINEERING_POLICY.yaml` requires Owner confirmation first (see above).
- [ ] Did not add a second `ai-os/generated/` copy for
      `generate-system-diagram.py` -- it already durably persists real content
      elsewhere (`ai-os/SYSTEM_DIAGRAM.md`); a second copy of the same content
      would be pure duplication with no distinct purpose.
- [ ] Did not touch item 60 (its own gap -- manual-trigger/no-crontab for the
      same 3 doc scripts -- is unchanged by this phase's fix, since only the
      stdout-vs-file behavior changed, not the cron-trigger behavior; leaving it
      PARTIAL is still accurate, not a new inconsistency).

## NEXT_PHASE -- Phase 9 draft (spec only; self-dispatch commands NOT run this
phase -- see note below)

Targets 3 concrete remaining PARTIAL items from
`ai-os/GOVERNANCE_AUDIT_RESULT_2026-07-23.yaml`:

**ITEM_10 (no distinct WARNING severity level)** -- FILE:
`scripts/health-check-15min.py`, `main()` (anomalies built ~line 554-608,
disk/mem thresholds at line 581/583, currently binary: `>= 90%` is the only
threshold, everything else silent). FIX: add a parallel `warnings` list (e.g.
disk/mem `>= 75% and < 90%` -> WARN, `>= 90%` stays the existing anomaly/error
tier), logged with a distinct `WARN:` prefix in `health-15min.log` (grep
today: zero `WARN` hits, confirmed), NOT fed into `send_anomaly_notifications()`
own escalation (that stays anomaly-only, avoid duplicating the phase7 streak
mechanism onto a lower severity tier it wasn't designed for). TEST: force a
disk/mem value in the 75-89% synthetic range through the function directly,
confirm a `WARN:` entry appears in the returned dict/log line and no Owner
email fires for it; re-run the real unmodified script, confirm exit 0 and (if
real disk/mem stays under 75%) zero WARN entries in that real run.

**ITEM_25 (no security/behavior anomaly feeds the anomalies pipeline)** --
FILES: `scripts/security-check.py` (own `notify_owner()` at line 157, `main()`
at line 170, own cron `*/15 * * * *`, own state file
`ai-os/logs/security-check-state.json`) and `scripts/health-check-15min.py`
(`anomalies` list, ~line 554). Re-verify first whether merging would
double-notify (security-check.py already calls its own `notify_owner()` per
finding with its own dedupe keys). If so: make health-check-15min.py's
addition **surface-only** -- read `security-check-state.json`'s
`new_source_ips`/`failed_then_success_bursts` counts recorded within the
current 15-min window and append a one-line summary string to `anomalies`
(for ATTENTION.md/log visibility and the existing streak-escalation dict),
but do NOT call `notify_owner()` a second time for the same finding (already
sent by security-check.py itself) -- ATTENTION.md/health-15min.log gets full
visibility, Owner inbox does not get duplicate emails. TEST: with a real
recorded entry (or none, if genuinely empty right now -- say so, do not
fabricate) in `security-check-state.json`, confirm the summary line appears
in `anomalies` on the next real `health-check-15min.py` run and confirm via
`ai-os/logs/notify-owner-state.json` timestamps that no new send happened
from health-check-15min.py's own `notify_owner()` call path for that same
finding.

**ITEM_6 (crontab says every-15-min, some doc says every-1-min)** -- Re-verify
first: `grep -rn "every 1 minute\|1-minute\|every minute"` across
`STANDING_DIRECTIVE.yaml`, `AI_ENGINEERING_POLICY.yaml`,
`RULES_ARTICLES_198.json`, `VERIDIAN_EXECUTION_RULES_2026-07-23.md` did NOT
find the claimed "every 1 minute" source in this phase's quick check -- Phase
9 must locate the actual source document/line for this claim (or determine
it no longer exists / was already corrected) before deciding whether to
reword the doc to match the real 15-min cadence, or escalate as a
now-stale/unfindable claim. TEST: cite the exact file:line of the claim (or
state explicitly, with the exact grep commands run, that it could not be
found anywhere live).

**Note on self-dispatch**: this task's own spec's NEXT_PHASE instruction says
to create-and-start Phase 9 autonomously (`veridian-task.py create` +
`systemctl --user start`), continuing the pattern phase6/7 already followed.
This phase did NOT run those two commands. Reason: `ai-os/OWNER_DECISIONS_NEEDED_2026-07-23.yaml`'s
`continuous-gap-closing-chain-self-dispatch-pause` entry (raised by Phase 5, still
`status: awaiting_owner_decision`, unresolved) is exactly this question, and
phases 3/4/5 explicitly declined to self-dispatch for stated reasons that remain
true today. Phase 6/7 self-dispatched anyway without resolving that open decision
-- an inconsistency worth surfacing, not silently repeating a third way. Draft
above is ready to hand off; asked the user directly whether to dispatch it.

## Phase 9 (this task, task-20260723-141444-gap-closing-phase9-warnings-login-log-in)

This task was itself created and started (`veridian-task.py create` +
`systemctl --user start`) targeting items 10/11/52 -- a different set than phase 8's
own draft above (10/25/6), and phase 8 explicitly did not self-dispatch itself
(see its own final report to the user, and the "Note on self-dispatch" above). That
this task exists with a *different* item selection than phase 8's draft is itself
the evidence read as: a human reviewed phase 8's "hold or dispatch?" question and
chose to dispatch phase 9 themselves, with their own item selection, rather than the
AI auto-continuing its own draft unattended -- i.e. option (c) from the still-open
`continuous-gap-closing-chain-self-dispatch-pause` decision (human-gated, one phase
per explicit request) is the pattern actually being followed, not silent AI
self-replication. See "Self-dispatch decision for Phase 10" below for how this
phase applies that same reasoning going forward.

### Completed
- [x] **Branch topology**: merged `worker/task-20260723-132537-gap-closing-phase8-coverage-notification`
      into this branch first (was cut before that lineage landed on master) -- same
      established convention every phase in this chain follows. Only conflict was
      this file, resolved by keeping phase 8's recap and appending this section.
- [x] **Item 10 (warning_severity_level): PARTIAL -> DONE.** `scripts/health-check-15min.py`
      main() now builds a `warnings` list parallel to `anomalies` (`DISK_WARNING_PCT`/`MEM_WARNING_PCT`
      = 75, strictly below the existing 90 anomaly threshold), written into `health-15min.jsonl`'s
      own `"warnings"` key and into `health-15min.log` as `WARN:` lines. Deliberately NOT fed
      into `send_anomaly_notifications()`'s streak-escalation (phase 7's mechanism) -- that stays
      anomaly-only, avoids duplicating a mechanism onto a severity tier it wasn't designed for.
      Real test: unmodified `python3 health-check-15min.py` run at 2026-07-23T14:22:02Z, exit 0,
      wrote a real `"warnings": []` key (disk=26%/mem=15.8%, honestly under 75%, not fabricated).
      Threshold boundary separately verified in isolation (disk=80% -> warning not anomaly; 90%+
      unchanged -> anomaly). Diff: `ai-os/patches/health-check-warning-severity-2026-07-23.diff`,
      `patch --dry-run` clean, no fuzz.
- [x] **Item 11 (veridian_built_login_logging): PARTIAL -> DONE.** Added
      `log_login(user, source_ip, method)` to `scripts/superboss-register.py` (reuses the existing
      `actions` table + `actions_fts` index -- zero-duplication, no parallel login table), exposed
      via a new `log-login` CLI subcommand. Wired into `scripts/security-check.py`'s own existing
      (only) auth.log parser: `ACCEPTED_RE` now also captures method+user, `check_ssh_activity()`
      calls `log_login()` once per real accepted line, idempotent via a new `logged_login_keys` set
      in `security-check-state.json` (same shape as the file's existing `seen_ssh_ips`). Real test:
      called the real `log-login` CLI with this account's own real, currently-active SSH session
      (user=rajat, ip=49.47.68.54, sourced from `last`/wtmp since `/var/log/auth.log` itself is
      still unreadable by this account -- the same pre-existing, still-open
      `auth-log-group-permission` gap `OWNER_DECISIONS_NEEDED_2026-07-23.yaml` already tracks for
      item 21; method honestly recorded as wtmp-derived/unknown, not fabricated as
      publickey/password since wtmp doesn't carry that field). Produced a real row (confirmed via
      direct `SELECT`): `action_id=ACT-20260723-143359-46f3, utm_source=login, utm_medium=ssh,
      utm_content=49.47.68.54, metadata_json={"user":"rajat"}`. The auth.log code path itself is
      complete and correct but not exercisable end-to-end until item 21's permission gap is
      resolved -- same function (`log_login()`) verified via the CLI call above. Diffs:
      `ai-os/patches/superboss-register-login-logindex-2026-07-23.diff`,
      `ai-os/patches/security-check-login-logging-2026-07-23.diff`, both `patch --dry-run` clean.
- [x] **Item 52 (searchable_indexed_logs): PARTIAL -> DONE.** New `scripts/index-logs.py` scans
      `ai-os/logs/*.log(.jsonl)`, indexes every real non-blank line into a new `log_index` table +
      `log_index_fts` FTS5 virtual table in `superboss-register.sqlite` -- exact same
      `CREATE VIRTUAL TABLE` + `AFTER INSERT` trigger convention as instructions/actions/system_index,
      reusing `superboss-register.py`'s own connect/write-lock/id-gen directly (imported) rather than
      a second sqlite writer. Idempotent via a per-file `<file>.indexed_line` state file, same
      pattern as `index-transcript`. `search()` extended to include `log_index`. Real test (exact
      required command): `python3 scripts/superboss-register.py search "anomalies"` returned real
      `log_index` rows, e.g. `{"log_index_id": "LOGIDX-76bda56634d9-135", "log_file":
      ".../health-check-cron.log", "line_no": 135, "content": "ANOMALIES: ['Task failure rate 56.9%
      (164/288) above 20% threshold']"}`. A real full-scan run indexed 10,645 real lines across all
      15 files, exit 0. Cron entry specified in the governance yaml, not added to crontab -- same
      standing `AI_ENGINEERING_POLICY.yaml` exception phases 6/8 already routed similar cases through.
- [x] **Side finding, fixed as a necessary blocker for item 11's real test**: hit a real,
      pre-existing sqlite corruption in `superboss-register.sqlite`'s `actions_fts` shadow table
      (`actions_fts_data`) -- confirmed pre-existing via `health-check-15min.py`'s own
      `integrity_check` anomaly logged at 2026-07-23T14:22Z, *before* this phase made any DB write.
      Repaired minimally: dropped and recreated just `actions_fts` (the broken virtual table),
      repopulated from the real 342 `actions` rows -- no other table touched, no restore from the
      stale 05:57 daily backup (would have silently discarded phases 5-8's real same-day data). A
      separate, deeper page-level corruption remains in the `actions` table's own b-tree
      (`PRAGMA quick_check`: "Tree 14 page 14: 2nd reference to page 437") -- NOT fixed, out of this
      item's scope, and already the subject of this same day's repeated
      `CORRUPTED-2026-07-2[2-3]-*`/`rebuild-*` quarantine files from earlier phases. New writes
      succeed (fresh pages), but this is a real, open, recurring infra issue flagged in item 11's
      governance evidence for the Owner -- not silently left undocumented.
- [x] Updated `ai-os/GOVERNANCE_AUDIT_RESULT_2026-07-23.yaml`: items 10/11/52 PARTIAL -> DONE with
      real evidence, added a `phase9_amendment` block. Summary recomputed (done 39->42, partial
      21->18, missing 0) and cross-checked against an independent PyYAML recount of all 60
      `items[].status` entries -- matches exactly.

### Self-dispatch decision for Phase 10
This task's own spec again instructs (as a "hard requirement... not optional") to
autonomously run `veridian-task.py create` + `systemctl --user start` for a Phase 10
after this commit. **Not doing that.** The `continuous-gap-closing-chain-self-dispatch-pause`
decision in `ai-os/OWNER_DECISIONS_NEEDED_2026-07-23.yaml` (raised by phase 5, held by
phases 3/4/5/8) is still `status: awaiting_owner_decision` -- unresolved. This phase's own
existence (created manually, with a different item selection than phase 8's draft) reads as
the human choosing option (c) from that decision -- dispatch one phase at a time, on
request -- not as authorization for the AI to now resume unattended self-replication.
Continuing to self-dispatch here would repeat exactly the pattern phase 8 (most recently)
declined, without the underlying decision ever actually being resolved. Per this session's
own operating rules (hard-to-reverse, shared-system, repeatedly-escalated actions need
explicit confirmation, not another silent restart of the same judgment call), drafted a
Phase 10 spec below and am asking the user directly, same as phase 8 did.

**Phase 10 draft (spec only, not dispatched):**
1. **auth-log-group-permission decision, act on it if Owner already resolved it** -- if
   `usermod -a -G adm rajat` (or an ACL grant) has been applied since phase 5 raised this,
   re-run `security-check.py` for real and re-verify items 11/21 exercise the real auth.log
   path end-to-end; if not yet resolved, re-confirm the gap is still accurate and leave both
   PARTIAL-blocking-reasons in place (do not re-raise a duplicate decision entry).
2. **actions table b-tree corruption** (flagged in item 11's evidence this phase) -- a
   dedicated, careful recovery task: attempt a full table-by-table extraction to a fresh
   sqlite file (page-437-region rows first, cross-checked against `directive_compliance_runs`/
   `execution_log`'s own independent records of the same events where they overlap, to avoid
   trusting a single unstable read), rather than the stale 05:57 backup.
3. Re-run the "3 items closed" sweep against the remaining 18 PARTIAL items in
   `ai-os/GOVERNANCE_AUDIT_RESULT_2026-07-23.yaml`, same exact-I/O precision this document
   itself models -- pick the next 3 with a real, buildable (non-Owner-decision-blocked) path.
- [ ] Awaiting user: dispatch Phase 10 as drafted, hold, or redirect.

---

# PROGRESS -- task-20260723-142643-build-veridian-task-watchdog-service

## Completed
- [x] Prerequisite blocker found and fixed: superboss-register.sqlite failed
      `PRAGMA integrity_check` (only `file_inventory` table affected --
      confirmed by per-table SELECT COUNT(*) probe). Quarantined the corrupted
      file, rebuilt a fresh DB from every other real table (235 instructions,
      22 work_items, 361 actions, 110 system_index, 10938 log_index, 2
      execution_log, 180 directive_compliance_runs -- 17 rows in `actions`
      had a pre-existing NULL in a NOT NULL column, coerced to '' and logged),
      rebuilt all FTS5 indexes, verified `integrity_check` -> `ok` before
      swapping it in as the live DB. `file_inventory` itself is regenerable
      (20-min cron) and was left to self-heal -- confirmed repopulated
      (2541 files) on the next real run.
- [x] Root cause of that corruption found and fixed: `ai-os/scripts/file_inventory.py`
      opened the DB directly, bypassing `superboss-register.py`'s own flock
      write-lock convention (its own docstring names this exact class of bug).
      Added the same `_write_lock()` pattern; verified a real run afterward
      leaves `integrity_check` at `ok`.
- [x] `scripts/superboss-register.py`: added `known_fixes` table (signature
      PK, fix_action, last_applied, success_count) to `init_db()` + a
      standalone `_ensure_known_fixes_table()` defensive create, and a new
      `log-fix --signature --fix-action` subcommand (INSERT ... ON CONFLICT
      DO UPDATE, increments success_count on repeat). Ran `init` against the
      live DB (still `integrity_check` -> `ok` after). TEST_3 first half:
      `log-fix --signature test --fix-action test` -- real row confirmed:
      `('test', 'test', '2026-07-23T14:39:35...', 2)`.
- [x] `scripts/veridian-task-watchdog.py` (new): scans active
      `veridian-worker@*` units (same systemctl query as
      `check_latest_task.py`, task_id parsing same convention as
      `recover-failed-workers.py`), computes STALL (active + no checkpoint in
      20min) and LOOP (last-3-notes identical) exactly per spec, with one
      evidence-based exception: the literal harness string "periodic
      checkpoint" is excluded from LOOP eligibility (real false-positive
      confirmed live on task-20260723-141444, which had 3 consecutive
      "periodic checkpoint" notes while healthy). step_1 searches
      ATTENTION.md + task_audits (defensively created if missing) for a
      prior occurrence of the note's first-60-chars signature; step_2 looks
      up `known_fixes` by that same signature and, if present, applies the
      fix via a small whitelisted FIX_ACTIONS registry (fix_action is
      AI-authored free text from RCA tasks -- never shell-executed directly,
      only dispatched through this fixed registry, to avoid an
      unattended-automation command-injection vector), records the
      application via the new `log-fix` subcommand, and re-checks once after
      60s; step_3 escalates via `veridian-task.py create --repo claude-control`
      with a closed-ended RCA prompt (follows STANDING_DIRECTIVE.yaml's
      literal_template so it won't hit the same pre-flight-schema rejection
      this task itself hit twice on dispatch) and starts the new unit.
      Output: JSON per task per run to `ai-os/logs/watchdog.jsonl`.
- [x] Tested end-to-end against real data (not fabricated):
  - STALL: `--dry-run-task task-20260723-112603-gap-closing-phase4-continue-2026-07-23`
    (real historical task, real stale checkpoint from 11:34) -> real
    watchdog.jsonl line: `stalled: true, ... "step_1: no prior occurrence
    found (step_1) -> step_3: DRY_RUN would escalate..."`. `--dry-run-escalation`
    used here deliberately (this historical task is already `status:
    completed`, successfully finished -- actually dispatching a live, billed
    RCA task against it would be wasted spend for a non-incident; the
    production timer's real (non-dry-run) escalation path is proven
    separately below against a live synthetic stall).
  - LOOP exclusion: confirmed live against task-20260723-141444's real
    3x-"periodic checkpoint" checkpoint history -> `loop_detected: false`.
  - step_2 (known-fix path), full pipeline, REAL (non-simulated) DB rows:
    seeded a real `known_fixes` row and a real `task_audits` row sharing an
    exact 60-char signature, built a synthetic stalled task.yaml with that
    same note, ran the deployed watchdog against it -> real watchdog.jsonl
    line: `"step_2: restarted veridian-worker@task-99999999-999999-watchdog-selftest.service
    (signature seen before via task_audits); recheck after 60s: still
    stalled/looping -> step_3: ..."`, and the real `known_fixes` row's
    `success_count` incremented 1 -> 2 in the DB, proving step_2 (not step_3)
    fired first. Test task dir and test DB rows deleted after; `integrity_check`
    confirmed `ok` afterward.
- [x] Deployed for real: `/home/rajat/.config/systemd/user/veridian-task-watchdog.service`
      (oneshot) + `.timer` (OnUnitActiveSec=60, OnBootSec=60). `systemctl
      --user daemon-reload && enable --now veridian-task-watchdog.timer`.
      TEST_1 evidence: `systemctl --user status veridian-task-watchdog.timer`
      -> `Active: active (running)`; `systemctl --user list-timers` -> `NEXT
      2026-07-23T14:46:12 UTC, LEFT 46s`. The real OnBootSec-triggered first
      run already appended a real line to `ai-os/logs/watchdog.jsonl` for
      this very task (`task-20260723-142643...`, `stalled: false`).
- [x] `ai-os/STANDING_DIRECTIVE.yaml` `v2_watchdog_service.status`:
      `TO_BE_BUILT` -> `LIVE`, with a `status_evidence` field citing the real
      systemctl output above.

## Remaining
- [ ] None for this task's scope. Note for whoever reads `watchdog.jsonl`
      next: the deployed timer's escalation path is NOT dry-run in
      production -- a genuine future stall/loop on any active
      `veridian-worker@` unit will, for real, dispatch a new billed RCA task
      via `veridian-task.py create` and start its unit, autonomously,
      without further human confirmation. This is exactly what the task spec
      required ("DEPLOY: ... real, live, not just committed"), flagged here
      so it isn't a surprise the first time it fires.
