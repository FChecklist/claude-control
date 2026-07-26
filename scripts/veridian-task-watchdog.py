#!/usr/bin/env python3
"""
VERIDIAN task watchdog -- ai-os/STANDING_DIRECTIVE.yaml v2_watchdog_service.
Built 2026-07-23, task-20260723-142643-build-veridian-task-watchdog-service.

Runs once per invocation (systemd timer, OnUnitActiveSec=60), scans every
active veridian-worker@ unit's task.yaml, flags STALL/LOOP, and on either
runs a bounded auto-recovery attempt before escalating to a fresh RCA task.

REUSED, NOT DUPLICATED (per this task's own KNOWN_CONTEXT constraint):
  - scripts/check_latest_task.py's exact `systemctl --user list-units
    veridian-worker@* --state=active --no-legend` invocation is the same
    query this script uses to find active units. check_latest_task.py only
    ever looks at the single newest task dir and blindly restarts it if no
    unit is active -- it does not read checkpoint history, cannot detect a
    stall (unit still active, just not progressing) or a loop, and has no
    RCA/escalation path. This script scans EVERY active unit's checkpoint
    history instead, which is why it supersedes rather than calls into it.
  - scripts/recover-failed-workers.py's task_id_from_unit() parsing
    convention (`unit.split("@", 1)[1].rsplit(".service", 1)[0]`) and its
    "read real evidence first, only touch units with a confirmed matching
    signature, print skipped ones for manual review" pattern is the model
    this script's step_1/step_2 signature-matched auto-recovery generalizes
    from one hardcoded failure type (402 balance errors) to any recurring
    checkpoint-note signature, via the new known_fixes table.
  - scripts/superboss-register.py's `log-fix` subcommand (added by this same
    task) is called via subprocess for every known_fixes write, rather than
    opening the sqlite file directly here -- keeps all writes going through
    that script's existing _write_lock() flock serialization instead of a
    second, parallel write path into the same canonical DB.
  - scripts/veridian-task.py's `create` subcommand (unmodified) is the
    step_3 escalation entrypoint; it already starts the new unit itself, so
    this script's own explicit `systemctl start` after create is a no-op
    safety net, not a real second start.

JUDGMENT CALLS (per this task's own OBJECTIVE -- these are not mechanical):

  1. STALL threshold: the spec's literal 20-minute checkpoint-staleness rule
     is applied as specified, but only against units systemctl currently
     reports active -- a unit that already exited (active_units==0) is
     either finished or crashed-to-terminal-state, neither of which this
     watchdog's stall/loop machinery is the right tool for (that is what
     recover-failed-workers.py's `failed`-state handling is for).

  2. LOOP false-positive filter: the spec's literal rule ("last 3
     checkpoints[].note are identical strings") is applied AS-IS, with one
     evidence-based exception. Every worker's harness appends a checkpoint
     roughly every 5 minutes regardless of whether anything happened, and
     when nothing new occurred that checkpoint's note is the fixed literal
     string "periodic checkpoint" -- confirmed live on
     task-20260723-141444-gap-closing-phase9-warnings-login-log-in, which
     had 3 consecutive "periodic checkpoint" notes while actively healthy
     (see watchdog.jsonl for this run's real evaluation of that task).
     Flagging that as a repeated-failure loop would fire on nearly every
     quiet-but-working task. LOOP_EXCLUDED_NOTES exists to name that one
     literal harness string as ineligible for loop detection; anything else
     -- including three identical *real* error/status sentences -- still
     triggers LOOP exactly per spec, because that IS the coincidental-vs-
     real distinction the spec's OBJECTIVE asks for, not a blanket exemption.

  3. fix_action is opaque, AI-authored free text (RCA tasks register it via
     `log-fix`). Blindly shell-executing it would be a real command-injection
     vector into an automated, unattended, 60-second-interval process. Step_2
     therefore only executes actions found in the small FIX_ACTIONS registry
     below; any other fix_action string is still recorded as "applied" (per
     spec) in known_fixes.last_applied/success_count via log-fix, but the
     watchdog performs no automated system action for it beyond that record
     -- action_taken in watchdog.jsonl says so explicitly, never fabricates
     a recovery that did not happen.

  4. RCA-escalation dedup (2026-07-26, root-caused against
     task-20260726-171939-delegation-expiry-enforcement-audit---te): escalate()
     used to shell out to `veridian-task.py create` unconditionally every time
     it was reached, with no memory of a prior escalation for the same
     task_id. This watchdog runs every ~60s and STALL is pure elapsed-time
     since the last checkpoint -- it has no floor for how long a genuinely
     healthy long invocation (a big quality-gate/test run, or an async wait
     on supervisor PR review) can legitimately take. Task-171939 was never
     actually stuck -- it reached 'blocked' on its own via a normal
     supervisor PR-review rejection shortly after -- but stayed past the
     20-minute staleness threshold for several ticks in a row, and each tick
     created a brand-new RCA task: task-20260726-175954-rca-... and
     task-20260726-180540-rca-... both exist for the identical task_id and
     signature, 5m46s apart (see ai-os/logs/watchdog.jsonl). find_in_flight_rca()
     now checks for an existing, non-terminal RCA task dir for this task_id
     before escalate() creates another one.

  5. known_fixes lookup was dead code for any signature not ALSO
     independently present in ATTENTION.md/task_audits (2026-07-26,
     root-caused against task-20260726-172004-search-performance-explain-
     analyze---gin, RCA task-20260726-183201): process_task() only called
     lookup_known_fix() when search_prior_occurrence() (step_1, which only
     greps ATTENTION.md and the task_audits table) had already returned
     found=True. superboss-register.py's log-fix command -- the ONLY writer
     of the known_fixes table -- never writes to ATTENTION.md or
     task_audits, so a signature registered purely via log-fix (exactly
     what every RCA task's own SUCCESS_CRITERIA instructs it to do) could
     never be found on a future occurrence: found stayed False forever,
     known_fix was never looked up, and step_3 escalated a brand-new
     billed RCA task on every single recurrence of an already-fixed
     signature -- the opposite of what known_fixes exists for. Fixed by
     looking up known_fixes independently of step_1's search; step_1's
     result is now purely informational (kept in the log line for
     provenance) and no longer gates step_2.

     Real root cause of task-20260726-172004 itself, registered under
     signature "periodic checkpoint": its worker was OOM-killed mid
     quality-gate (systemd journal: "A process of this unit has been
     killed by the OOM killer" / "Failed with result 'oom-kill'") under
     real memory contention from concurrent workers on this shared box --
     confirmed via `systemctl --user status`/`journalctl`, not a guess.
     The OOM kill took down the periodic-checkpoint heartbeat along with
     the rest of its cgroup, freezing task.yaml on a stale "periodic
     checkpoint" note. systemd's own Restart=on-failure had ALREADY
     restarted the unit (invocation 2 resuming cleanly from checkpoint,
     confirmed live) before this fix existed, making the escalation pure
     waste -- the same class of false escalation `find_in_flight_rca()`
     above was built for, just triggered by OOM-then-auto-restart instead
     of a merely-long-but-healthy invocation. Registered fix_action
     "wait_and_recheck" (see FIX_ACTIONS below) takes no destructive
     system action -- restarting an already-recovering unit would only
     interrupt it -- and instead relies on the existing apply -> sleep
     RECHECK_DELAY_SECONDS -> recheck flow to observe the self-heal (or,
     if it turns out the task is genuinely stuck and not just mid-recovery,
     still fall through to step_3 exactly as before).
"""
import argparse
import glob
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone

AI_OS = "/opt/veridian/ai-os"
TASKS_DIR = f"{AI_OS}/tasks"
LOGS_DIR = f"{AI_OS}/logs"
WATCHDOG_LOG = f"{LOGS_DIR}/watchdog.jsonl"
ATTENTION_PATH = f"{LOGS_DIR}/ATTENTION.md"
DB_PATH = "/opt/veridian/ai-os/memory/superboss-register.sqlite"
SUPERBOSS_REGISTER = "/opt/veridian/scripts/superboss-register.py"
VERIDIAN_TASK = "/opt/veridian/scripts/veridian-task.py"

STALL_MINUTES = 20
LOOP_COUNT = 3
RECHECK_DELAY_SECONDS = 60
SIGNATURE_LEN = 60

LOOP_EXCLUDED_NOTES = {
    "periodic checkpoint",
}

# Same convention as sync-controller-back.py's own TERMINAL set (each script
# keeps its own copy rather than importing a shared module -- these are
# independent cron/timer-invoked scripts, not a package).
TERMINAL = {"completed", "blocked", "failed", "awaiting_human_approval"}


def _now():
    return datetime.now(timezone.utc)


def _now_iso():
    return _now().isoformat()


def _parse_ts(ts):
    return datetime.fromisoformat(ts)


def list_active_task_ids():
    """Same query check_latest_task.py already uses, generalized from
    'count active units' to 'which task_ids are active' -- one real
    systemctl invocation, no duplicate polling mechanism."""
    r = subprocess.run(
        ["systemctl", "--user", "list-units", "veridian-worker@*", "--state=active", "--no-legend"],
        capture_output=True, text=True,
    )
    task_ids = []
    for line in r.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        unit = parts[0]
        if not unit.startswith("veridian-worker@"):
            continue
        # same convention as recover-failed-workers.py's task_id_from_unit()
        task_id = unit.split("@", 1)[1].rsplit(".service", 1)[0]
        task_ids.append(task_id)
    return task_ids


def load_task_yaml(task_id):
    path = f"{TASKS_DIR}/{task_id}/task.yaml"
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return None


def evaluate(task, task_id):
    """Pure function of (task.yaml dict) -> (stalled, loop_detected, note).
    No systemctl/subprocess/DB access here -- kept separable so it can be
    exercised directly against real historical task.yaml data for testing
    without side effects (see --dry-run-task)."""
    checkpoints = (task or {}).get("checkpoints") or []
    if not checkpoints:
        return False, False, ""

    last = checkpoints[-1]
    last_note = last.get("note") or ""
    last_at = last.get("at")

    stalled = False
    if last_at:
        try:
            age = (_now() - _parse_ts(last_at)).total_seconds() / 60.0
            stalled = age >= STALL_MINUTES
        except ValueError:
            stalled = False

    loop_detected = False
    if len(checkpoints) >= LOOP_COUNT:
        last_notes = [c.get("note") for c in checkpoints[-LOOP_COUNT:]]
        if len(set(last_notes)) == 1 and last_notes[0] and last_notes[0] not in LOOP_EXCLUDED_NOTES:
            loop_detected = True

    return stalled, loop_detected, last_note


def signature_of(note):
    return (note or "")[:SIGNATURE_LEN]


def search_prior_occurrence(signature):
    """step_1: does this exact error-signature substring appear in a PRIOR
    ATTENTION.md entry or task_audits row? Returns (found: bool, source: str)."""
    if not signature:
        return False, ""

    try:
        with open(ATTENTION_PATH) as f:
            content = f.read()
        if signature in content:
            return True, "ATTENTION.md"
    except FileNotFoundError:
        pass

    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS task_audits (audit_id TEXT PRIMARY KEY, ts TEXT, work_item_id TEXT, "
            "software_task_id TEXT, audit_cmd TEXT, exit_code INTEGER, stdout_tail TEXT, stderr_tail TEXT, verdict TEXT)"
        )
        like = f"%{signature}%"
        row = conn.execute(
            "SELECT audit_id FROM task_audits WHERE stdout_tail LIKE ? OR stderr_tail LIKE ? LIMIT 1",
            (like, like),
        ).fetchone()
        conn.close()
        if row:
            return True, "task_audits"
    except sqlite3.Error:
        pass

    return False, ""


def lookup_known_fix(signature):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS known_fixes (signature TEXT PRIMARY KEY, fix_action TEXT NOT NULL, "
        "last_applied TEXT, success_count INTEGER NOT NULL DEFAULT 0)"
    )
    row = conn.execute("SELECT * FROM known_fixes WHERE signature=?", (signature,)).fetchone()
    conn.close()
    return dict(row) if row else None


def record_fix_applied(signature, fix_action):
    r = subprocess.run(
        ["python3", SUPERBOSS_REGISTER, "log-fix", "--signature", signature, "--fix-action", fix_action],
        capture_output=True, text=True,
    )
    return r.returncode == 0


def _fix_restart_unit(task_id):
    unit = f"veridian-worker@{task_id}.service"
    subprocess.run(["systemctl", "--user", "restart", unit], capture_output=True, text=True)
    return f"restarted {unit}"


def _fix_reset_failed_and_start(task_id):
    # same two-call sequence as recover-failed-workers.py's recovered path
    unit = f"veridian-worker@{task_id}.service"
    subprocess.run(["systemctl", "--user", "reset-failed", unit], capture_output=True)
    subprocess.run(["systemctl", "--user", "start", unit], capture_output=True)
    return f"reset-failed + started {unit}"


def _fix_wait_and_recheck(task_id):
    """No destructive system action -- see JUDGMENT CALL 5 in this module's
    docstring. A stale "periodic checkpoint" note this watchdog only ever
    sees on an ACTIVE unit (list_active_task_ids() filters to --state=active)
    is frequently either a long-running-but-healthy quality-gate/build phase,
    or a very recent OOM-kill that systemd's own Restart=on-failure is
    already recovering -- forcing a restart here would just interrupt
    whichever of those is genuinely in flight. process_task()'s existing
    apply -> sleep(RECHECK_DELAY_SECONDS) -> recheck flow already exists to
    give real transient recovery a window before escalating; this action's
    only job is to take part in that flow without doing anything itself."""
    return "no destructive action taken -- deferring to systemd's own Restart=on-failure / in-flight work; recheck will confirm"


FIX_ACTIONS = {
    "restart_unit": _fix_restart_unit,
    "reset_failed_and_start": _fix_reset_failed_and_start,
    "wait_and_recheck": _fix_wait_and_recheck,
}


def apply_known_fix(task_id, fix_action):
    fn = FIX_ACTIONS.get(fix_action)
    if fn is None:
        return f"recorded known fix '{fix_action}' (unrecognized action name -- not in FIX_ACTIONS whitelist, no automated system action taken, logged only)"
    return fn(task_id)


RCA_PROMPT_TEMPLATE = """## OBJECTIVE
TASK REQUIRING AI JUDGMENT: {original_task_id} is stalled or looping (watchdog signature: "{signature}"). Read its task.yaml/worker.log/systemd.log, determine the real root cause (not a guess), and apply a real, reusable fix -- not a manual one-off patch.

## SCOPE
INPUT: /opt/veridian/ai-os/tasks/{original_task_id}/task.yaml, worker.log, systemd.log.
OUTPUT: a real fix applied to whatever file/service/config caused the stall or loop, PLUS one new row in the known_fixes table (superboss-register.sqlite) via `python3 scripts/superboss-register.py log-fix --signature "{signature}" --fix-action <name>` -- so this exact signature auto-resolves via step_2 next time, without a second RCA task.

## KNOWN_CONTEXT
zero_duplication_check_performed: true. This RCA task was auto-dispatched by scripts/veridian-task-watchdog.py's step_3 escalation (task-20260723-142643) after step_1 (search ai-os/logs/ATTENTION.md + task_audits for this signature) and step_2 (known_fixes lookup) found no existing recorded fix for this signature.

## SUCCESS_CRITERIA
`python3 scripts/superboss-register.py log-fix --signature "{signature}" --fix-action <name>` succeeds and returns success_count>=1 for this signature. Cite the real known_fixes row.

## EXPECTED_OUTPUT
COMMIT: whatever file(s) the real root cause requires. CHECKPOINT: status=pending_review, note=root cause + fix + known_fixes row as evidence.

## CONSTRAINTS
State the root cause honestly even if it is outside {original_task_id}'s own code (e.g. a shared script or DB). Register the fix in known_fixes even if the fix itself lives elsewhere.

## COMPLEXITY_TIER
judgment
"""


def find_in_flight_rca(task_id):
    """Real root cause of the 2026-07-26 task-20260726-171939 double-escalation
    incident: this watchdog runs every 60s (systemd OnUnitActiveSec=60) and
    escalate() had no memory of a prior escalation, so a task that stays
    "stalled" for several ticks in a row (STALL is pure elapsed-time-since-
    checkpoint, with no floor on how long a *genuinely healthy* long
    invocation -- a big quality-gate/test run, or a wait on supervisor PR
    review -- can legitimately take) got a fresh RCA task created on every
    single tick until its own checkpoint finally advanced. Confirmed live:
    task-20260726-175954-rca-... and task-20260726-180540-rca-... both exist
    for the exact same original task_id, 5m46s apart, while task-171939 was
    simply still busy (it finished on its own shortly after, reaching
    'blocked' via a normal supervisor PR-review rejection -- never actually
    stuck).

    Escalation titles are always exactly f"rca-{task_id}" (see escalate()
    below), and veridian-task.py's cmd_create slugifies+truncates that title
    to 40 chars for the new task_id (task-{ts}-{slug}) -- so for a long
    original task_id the literal substring "rca-{task_id}" will NOT appear
    intact in the new dir name. Matching therefore has to tolerate that
    truncation: split each candidate dir name on its first "-rca-" and treat
    the remainder as a (possibly truncated) prefix of task_id.
    """
    marker = "-rca-"
    for path in sorted(glob.glob(f"{TASKS_DIR}/*")):
        dir_name = os.path.basename(path)
        if dir_name == task_id or marker not in dir_name:
            continue
        candidate_task_id = dir_name.split(marker, 1)[1]
        if not candidate_task_id or not task_id.startswith(candidate_task_id):
            continue
        rca_task = load_task_yaml(dir_name)
        status = (rca_task or {}).get("status")
        if status not in TERMINAL:
            return True, dir_name
    return False, None


def escalate(task_id, signature, dry_run=False):
    in_flight, existing_task_id = find_in_flight_rca(task_id)
    if in_flight:
        return f"skipped: RCA already in flight for {task_id} ({existing_task_id}, not yet terminal) -- not creating a duplicate"

    title = f"rca-{task_id}"
    prompt = RCA_PROMPT_TEMPLATE.format(original_task_id=task_id, signature=signature)
    cmd = ["python3", VERIDIAN_TASK, "create", "--title", title, "--repo", "claude-control", "--prompt", prompt]
    if dry_run:
        return f"DRY_RUN would escalate: {' '.join(cmd[:6])} ... (title={title})"

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return f"escalation FAILED (create exit={r.returncode}): {r.stderr[:300]}"

    m = re.search(r"^CREATED: (\S+)", r.stdout, re.MULTILINE)
    new_task_id = m.group(1) if m else None
    if new_task_id:
        # cmd_create already starts the unit; explicit start here is a
        # documented no-op safety net, matching the spec's literal step_3.
        subprocess.run(["systemctl", "--user", "start", f"veridian-worker@{new_task_id}.service"], capture_output=True)
        return f"escalated: created and started {new_task_id}"
    return f"escalated: create ran (exit=0) but new task_id not parsed from stdout: {r.stdout[:200]}"


def process_task(task_id, task, dry_run_escalation=False):
    stalled, loop_detected, last_note = evaluate(task, task_id)
    status = (task or {}).get("status", "unknown")
    entry = {
        "ts": _now_iso(),
        "task_id": task_id,
        "status": status,
        "stalled": stalled,
        "loop_detected": loop_detected,
        "action_taken": "none",
    }

    if not (stalled or loop_detected):
        return entry

    signature = signature_of(last_note)
    # step_1 (informational only, kept for provenance in the log line below)
    # -- must NOT gate step_2: search_prior_occurrence() only greps
    # ATTENTION.md/task_audits, and log-fix (the only writer of known_fixes)
    # never writes to either, so gating the lookup behind `found` made every
    # log-fix-registered signature unreachable on its next real occurrence.
    # See JUDGMENT CALL 5 in this module's docstring for the full incident.
    found, source = search_prior_occurrence(signature)
    known_fix = lookup_known_fix(signature)

    if known_fix:
        applied_desc = apply_known_fix(task_id, known_fix["fix_action"])
        record_fix_applied(signature, known_fix["fix_action"])
        provenance = f"signature seen before via {source}" if found else "signature on record in known_fixes (no independent ATTENTION.md/task_audits match)"
        time.sleep(RECHECK_DELAY_SECONDS)
        recheck_task = load_task_yaml(task_id)
        still_bad, still_loop, _ = evaluate(recheck_task, task_id)
        if not (still_bad or still_loop):
            entry["action_taken"] = f"step_2: {applied_desc} ({provenance}); recheck after {RECHECK_DELAY_SECONDS}s: recovered"
            return entry
        entry["action_taken"] = f"step_2: {applied_desc} ({provenance}); recheck after {RECHECK_DELAY_SECONDS}s: still stalled/looping -> "
        esc = escalate(task_id, signature, dry_run=dry_run_escalation)
        entry["action_taken"] += f"step_3: {esc}"
        return entry

    reason = "no prior occurrence found (step_1)" if not found else "prior occurrence found but no known_fixes entry (step_2 not applicable)"
    esc = escalate(task_id, signature, dry_run=dry_run_escalation)
    entry["action_taken"] = f"step_1: {reason} -> step_3: {esc}"
    return entry


def append_jsonl(entry):
    os.makedirs(os.path.dirname(WATCHDOG_LOG), exist_ok=True)
    with open(WATCHDOG_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run-task", default=None,
                     help="TEST ONLY: evaluate exactly this task_id's real task.yaml as if its unit were active, "
                          "without querying systemctl. Not used by the production systemd timer invocation (no args).")
    ap.add_argument("--dry-run-escalation", action="store_true",
                     help="TEST ONLY: log what step_3 would run instead of actually dispatching a new billed task.")
    args = ap.parse_args()

    if args.dry_run_task:
        task_ids = [args.dry_run_task]
    else:
        task_ids = list_active_task_ids()

    results = []
    for task_id in task_ids:
        task = load_task_yaml(task_id)
        entry = process_task(task_id, task, dry_run_escalation=args.dry_run_escalation)
        append_jsonl(entry)
        results.append(entry)
        print(json.dumps(entry))

    return results


if __name__ == "__main__":
    main()
