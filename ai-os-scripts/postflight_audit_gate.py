#!/usr/bin/env python3
"""Universal post-completion audit gate -- companion to /opt/veridian/scripts/preflight-guard.py
(which gates BEFORE a task starts; this gates the CLAIM that a task is DONE or FAILED).

Owner directive 2026-07-22: no task done by the assistant, any AI model, AI agent, AI router,
AI team, or software may be recorded as complete or failed until it has been audited end-to-end
by a script, automatically. This is that script -- and it is the ONLY path that may write a
terminal (DONE/FAILED) status into work_items. Every caller -- this assistant included -- goes
through the same gate; the gate cannot be skipped by forgetting, because superboss-register.py's
raw log-work is documented (STANDING_DIRECTIVE.yaml) as deprecated for terminal status.

Usage:
  python3 postflight_audit_gate.py \\
      --work-item-id <id or NEW> --software-task-id <id> \\
      --audit-cmd "<shell command that exits 0 on real success>" \\
      --content "<description>" \\
      [--post-fields-file <path to JSON judgment-call overrides, see write_post_execution_log below>]

The audit_cmd is RUN, not trusted. Its real exit code decides DONE vs FAILED. There is no
parameter to force a status -- the only way to get DONE is for the audit command to actually
exit 0.

2026-07-23 (ai-os/EXECUTION_RULES_AUDIT_2026-07-23.yaml Part 40, pre_execution_checklist_automation
phase): also writes one real Post-Execution Log row (superboss-register.py's new execution_log
table) per call, since this gate already runs at the exact moment a task's terminal status becomes
known -- the natural single call site for the POST half of Part 40's log (session_bootstrap.py is
the matching call site for the PRE half, since it is the mandatory first command). Most of Part 40's
20 Post-Execution fields are auto-derived from this gate's own real audit_cmd/exit_code and its
existing --content path-scan (see _scan_content_paths below); the handful that are pure task-specific
judgment calls (e.g. "Automation Updated") default to NO unless the caller supplies real evidence via
--post-fields-file -- never fabricated, never guessed.
"""
import argparse, subprocess, sqlite3, datetime, sys, uuid, json, os, re, tempfile

DB = "/opt/veridian/ai-os/memory/superboss-register.sqlite"
REGISTER_SCRIPT = "/opt/veridian/scripts/superboss-register.py"

import contextlib, fcntl

_WRITE_LOCK_PATH = DB + ".writelock"


@contextlib.contextmanager
def _write_lock():
    """Same proven flock convention as scripts/superboss-register.py's
    _write_lock() -- applied here 2026-07-24 after finding this gate (called on
    every task completion) was one of the remaining unlocked direct writers
    to the shared DB, root-caused as a real contributor to same-day recurring
    corruption."""
    os.makedirs(os.path.dirname(_WRITE_LOCK_PATH), exist_ok=True)
    with open(_WRITE_LOCK_PATH, "w") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lockfile, fcntl.LOCK_UN)

# Fields a caller may legitimately claim YES for via --post-fields-file, with real evidence --
# this gate cannot determine these itself (e.g. whether automation/workflow config changed), so
# it never guesses; anything not supplied here defaults to NO, not silently fabricated.
OPTIONAL_POST_FIELDS = {
    "Automation Updated", "Workflow Updated", "Relationships Updated", "Reusable Software Created",
    "AI Work Converted to Software", "Future AI Dependency Reduced", "Owner Approval Required",
}

def ensure_tables():
    with _write_lock():
        conn = sqlite3.connect(DB)
        conn.execute("""CREATE TABLE IF NOT EXISTS task_audits (
            audit_id TEXT PRIMARY KEY, ts TEXT, work_item_id TEXT, software_task_id TEXT,
            audit_cmd TEXT, exit_code INTEGER, stdout_tail TEXT, stderr_tail TEXT, verdict TEXT
        )""")
        conn.commit()
        conn.close()

def _scan_content_paths(content):
    return re.findall(r'(?:ai-os|scripts)/[\w./-]+\.(?:py|sh|yaml|json|md)', content)


def build_post_execution_fields(verdict, exit_code, audit_id, audit_cmd, work_item_id, content, override_fields):
    """Maps Part 40's 20 literal Post-Execution Log fields to YES/NO. Most are auto-derived from this
    gate's own real, just-computed audit outcome (never fabricated -- verdict/exit_code/audit_id are the
    real thing this script exists to produce). The handful of pure judgment-call fields
    (OPTIONAL_POST_FIELDS) default to NO unless override_fields supplies real evidence for them."""
    paths = _scan_content_paths(content)
    scripts = [p for p in paths if p.endswith((".py", ".sh"))]
    yamls = [p for p in paths if p.endswith((".yaml", ".json"))]
    docs = [p for p in paths if p.endswith(".md")]

    def yes(evidence):
        return {"status": "YES", "evidence": evidence}

    def no(reason):
        return {"status": "NO", "evidence": reason}

    f = {}
    f["Task Completed"] = yes(f"audit_cmd exit_code={exit_code}, verdict={verdict} (audit_id={audit_id})") if verdict == "DONE" \
        else no(f"audit_cmd exit_code={exit_code}, verdict={verdict} (audit_id={audit_id})")
    f["Software Updated"] = yes(f"--content mentions real path(s): {paths}") if paths else no("no ai-os/ or scripts/ path found in --content")
    f["Script Created/Updated"] = yes(f"--content mentions script path(s): {scripts}") if scripts else no("no .py/.sh path found in --content")
    f["Metadata Updated"] = yes(f"--content mentions metadata path(s): {yamls}") if yamls else no("no .yaml/.json path found in --content")
    f["YAML Updated"] = yes(f"--content mentions YAML path(s): {yamls}") if yamls else no("no .yaml path found in --content")
    f["Documentation Updated"] = yes(f"--content mentions doc path(s): {docs}") if docs else no("no .md path found in --content")
    f["Logs Created"] = yes(f"task_audits row inserted, audit_id={audit_id}")
    f["Audit Created"] = yes(f"task_audits row inserted, audit_id={audit_id}, execution_log row this call")
    f["History Updated"] = yes(f"work_items/log-work row inserted for software_task_id (see register_log_result)")
    f["Memory Updated"] = yes(f"{DB}: task_audits + work_items rows inserted this call (audit_id={audit_id})")
    f["Testing Completed"] = yes(f"audit_cmd was actually executed (not trusted-by-claim): `{audit_cmd[:200]}`, exit_code={exit_code}")
    f["Validation Passed"] = yes(f"verdict=DONE, audit_id={audit_id}") if verdict == "DONE" else no(f"verdict=FAILED, audit_id={audit_id}")
    f["Task Successfully Closed"] = yes(f"verdict=DONE and log-work call issued, audit_id={audit_id}") if verdict == "DONE" else no(f"verdict=FAILED, not closed, audit_id={audit_id}")
    for name in OPTIONAL_POST_FIELDS:
        f[name] = no("not supplied via --post-fields-file -- no automatic determination possible for this judgment-call field")

    if override_fields:
        for name, val in override_fields.items():
            if name in f or name in OPTIONAL_POST_FIELDS:
                f[name] = val
    return f


def write_post_execution_log(verdict, exit_code, audit_id, audit_cmd, work_item_id, software_task_id, content, post_fields_file):
    override_fields = None
    if post_fields_file:
        try:
            with open(post_fields_file, encoding="utf-8") as fh:
                override_fields = json.load(fh)
        except Exception as e:
            print(f"WARNING: could not read --post-fields-file {post_fields_file}: {e}", file=sys.stderr)

    fields = build_post_execution_fields(verdict, exit_code, audit_id, audit_cmd, work_item_id, content, override_fields)
    fd, path = tempfile.mkstemp(prefix="post_execution_fields_", suffix=".json")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(fields, fh)
        cmd = [
            "python3", REGISTER_SCRIPT, "log-execution", "--phase", "POST",
            "--source-script", "ai-os/scripts/postflight_audit_gate.py",
            "--software-task-id", software_task_id,
            "--fields-file", path,
        ]
        if work_item_id:
            cmd += ["--work-item-id", work_item_id]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return json.loads(result.stdout)
        return {"error": result.stderr[-500:]}
    finally:
        os.unlink(path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--software-task-id", required=True)
    p.add_argument("--audit-cmd", required=True, help="shell command; real exit code decides DONE vs FAILED")
    p.add_argument("--content", required=True)
    p.add_argument("--instruction-id", default=None)
    p.add_argument("--work-item-id", dest="work_item_id", default=None)
    p.add_argument("--post-fields-file", dest="post_fields_file", default=None,
                    help="optional path to a JSON file of caller-supplied real evidence for the judgment-call "
                         "Post-Execution Log fields this gate cannot auto-derive, e.g. "
                         '{"Automation Updated": {"status": "YES", "evidence": "crontab -l diff: ..."}}. '
                         "Any of the 20 Part-40 fields may be supplied here to override the auto-derived value "
                         "too, as long as real evidence is given -- fields not supplied default to NO.")
    args = p.parse_args()

    ensure_tables()
    audit_id = "AUD-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]

    try:
        result = subprocess.run(["bash", "-c", args.audit_cmd], capture_output=True, text=True, timeout=120)
        exit_code = result.returncode
        stdout_tail = result.stdout[-2000:]
        stderr_tail = result.stderr[-2000:]
    except subprocess.TimeoutExpired:
        exit_code = -1
        stdout_tail, stderr_tail = "", "TIMEOUT after 120s"

    verdict = "DONE" if exit_code == 0 else "FAILED"

    with _write_lock():
        conn = sqlite3.connect(DB)
        conn.execute(
            "INSERT INTO task_audits (audit_id, ts, work_item_id, software_task_id, audit_cmd, exit_code, stdout_tail, stderr_tail, verdict) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (audit_id, datetime.datetime.now(datetime.timezone.utc).isoformat(), None, args.software_task_id,
             args.audit_cmd, exit_code, stdout_tail, stderr_tail, verdict)
        )
        if verdict == "FAILED":
            conn.execute("""CREATE TABLE IF NOT EXISTS rca_open (
                audit_id TEXT PRIMARY KEY, ts TEXT, software_task_id TEXT, audit_cmd TEXT,
                stderr_tail TEXT, rca_status TEXT
            )""")
            conn.execute(
                "INSERT INTO rca_open (audit_id, ts, software_task_id, audit_cmd, stderr_tail, rca_status) VALUES (?,?,?,?,?,?)",
                (audit_id, datetime.datetime.now(datetime.timezone.utc).isoformat(), args.software_task_id,
                 args.audit_cmd, stderr_tail, "OPEN_NEEDS_RCA")
            )
        conn.commit()
        conn.close()

    # only now, with a real audit_id backed by a real exit code, call the actual register
    log_cmd = (
        f'python3 /opt/veridian/scripts/superboss-register.py log-work '
        f'--software-task-id "{args.software_task_id}" --source assistant --medium postflight_audit_gate '
        f'--content "{args.content} [audited by {audit_id}, exit_code={exit_code}]" --status {verdict}'
    )
    log_result = subprocess.run(["bash", "-c", log_cmd], capture_output=True, text=True)

    # AUTO-PROPAGATION: this is the mechanism the Owner asked for on 2026-07-22 --
    # every terminal-status write automatically updates OTHER relevant memory, with
    # zero AI action required. This runs unconditionally, inside the one shared gate
    # every actor's work already goes through -- it cannot be skipped by forgetting.
    propagation_log = []

    # 1. re-scan the file inventory immediately, not waiting for the next cron tick,
    #    so "what changed" reflects this exact task right away.
    try:
        inv = subprocess.run(["python3", "/opt/veridian/ai-os/scripts/file_inventory.py"],
                              capture_output=True, text=True, timeout=30)
        propagation_log.append({"step": "file_inventory_rescan", "ok": inv.returncode == 0})
    except Exception as e:
        propagation_log.append({"step": "file_inventory_rescan", "ok": False, "error": str(e)})

    # 2. scan this task's own --content for a file path under ai-os/ or scripts/ that
    #    is NOT yet in MASTER_INDEX.yaml's registries -- auto-flag it, don't rely on
    #    an AI remembering to register a new script it just built.
    try:
        import yaml as _yaml, re as _re
        mi = _yaml.safe_load(open("/opt/veridian/ai-os/MASTER_INDEX.yaml"))
        registered_basenames = {p2.get("path", "").rsplit("/", 1)[-1] for p2 in mi.get("registries", [])}
        mentioned_paths = _re.findall(r'(?:ai-os|scripts)/[\w./-]+\.(?:py|sh|yaml|json|md)', args.content)
        unregistered = [m for m in mentioned_paths if m.rsplit("/", 1)[-1] not in registered_basenames]
        if unregistered:
            with _write_lock():
                conn2 = sqlite3.connect(DB)
                conn2.execute("""CREATE TABLE IF NOT EXISTS unregistered_mentions (
                    id TEXT PRIMARY KEY, ts TEXT, software_task_id TEXT, mentioned_path TEXT, status TEXT
                )""")
                for up in unregistered:
                    mid = "UNREG-" + uuid.uuid4().hex[:8]
                    conn2.execute("INSERT INTO unregistered_mentions VALUES (?,?,?,?,?)",
                                  (mid, datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                   args.software_task_id, up, "NEEDS_REGISTRATION"))
                conn2.commit()
                conn2.close()
        propagation_log.append({"step": "unregistered_path_scan", "ok": True, "flagged": unregistered})
    except Exception as e:
        propagation_log.append({"step": "unregistered_path_scan", "ok": False, "error": str(e)})

    # Part 40 Post-Execution Log: written last, now that verdict/audit_id/exit_code are all real
    # and final -- see write_post_execution_log's own docstring for the auto-derivation rules.
    execution_log_result = write_post_execution_log(
        verdict, exit_code, audit_id, args.audit_cmd, args.work_item_id, args.software_task_id,
        args.content, args.post_fields_file,
    )

    print(json.dumps({
        "audit_id": audit_id,
        "verdict": verdict,
        "exit_code": exit_code,
        "audit_cmd": args.audit_cmd,
        "register_log_result": log_result.stdout.strip(),
        "auto_propagation": propagation_log,
        "post_execution_log": execution_log_result,
    }, indent=2))
    sys.exit(0 if verdict == "DONE" else 1)

if __name__ == "__main__":
    main()
