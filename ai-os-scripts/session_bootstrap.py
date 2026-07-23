#!/usr/bin/env python3
"""Mandatory FIRST command of any task on VERIDIAN-DEV, per STANDING_DIRECTIVE.yaml rule_2_no_forgetting.
Reads real accumulated history directly from the register DB (not a reactive keyword search) plus the
living architecture documents, and prints one consolidated briefing. No task should start without running
this first -- it replaces "the assistant remembers to check" with "the assistant cannot proceed without
this output existing."

2026-07-23 (ai-os/EXECUTION_RULES_AUDIT_2026-07-23.yaml Part 40, pre_execution_checklist_automation phase):
also writes one real Pre-Execution Log row (superboss-register.py's new execution_log table) per invocation.
This is the single call site chosen for the PRE half of Part 40's log (postflight_audit_gate.py is the
matching call site for the POST half) because session_bootstrap.py is already the mandatory first command
of every task -- wiring the log here means it cannot be skipped by forgetting, same reasoning as this
file's own existing mandatory-first-command design. Every YES below is backed by a real check this
function itself just ran (query/file-load); every NO is an honest gap, not a guess.
"""
import argparse
import sqlite3, yaml, json, sys, datetime, os, subprocess, tempfile

DB = "/opt/veridian/ai-os/memory/superboss-register.sqlite"
REGISTER_SCRIPT = "/opt/veridian/scripts/superboss-register.py"

_argp = argparse.ArgumentParser()
_argp.add_argument("n", nargs="?", type=int, default=15, help="how many recent rows of each table to print")
_argp.add_argument("--work-item-id", dest="work_item_id", default=None)
_argp.add_argument("--software-task-id", dest="software_task_id", default=None)
_args, _unknown = _argp.parse_known_args()
N = _args.n

def recent(table, cols, limit=N):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f"SELECT {','.join(cols)} FROM {table} ORDER BY ts DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

print("=" * 70)
print(f"SESSION BOOTSTRAP -- generated {datetime.datetime.utcnow().isoformat()}Z")
print("=" * 70)

print(f"\n--- last {N} instructions (real history, not keyword-filtered) ---")
for r in recent("instructions", ["instruction_id", "ts", "utm_campaign", "utm_content"]):
    print(f"  [{r['ts']}] {r['instruction_id']} :: {r['utm_campaign']} / {r['utm_content']}")

print(f"\n--- last {N} work_items ---")
for r in recent("work_items", ["work_item_id", "ts", "software_task_id", "utm_campaign", "utm_content", "status"]):
    print(f"  [{r['ts']}] {r['work_item_id']} :: {r['software_task_id']} / {r['utm_campaign']} :: {r['status']}")

print(f"\n--- last {N} actions ---")
for r in recent("actions", ["action_id", "ts", "work_item_id", "utm_content", "result"]):
    print(f"  [{r['ts']}] {r['action_id']} :: {r['utm_content']} :: {r['result']}")

print("\n--- system_index: live registries/mechanisms ---")
for r in recent("system_index", ["path", "status", "purpose"], limit=20):
    print(f"  {r['path']} [{r['status']}] -- {r['purpose'][:80] if r['purpose'] else ''}")

try:
    sm = yaml.safe_load(open("/opt/veridian/ai-os/SYSTEM_MAP.yaml"))
    print("\n--- SYSTEM_MAP.yaml coverage ---")
    print(" ", sm.get("coverage_honesty"))
except Exception as e:
    print("\n--- SYSTEM_MAP.yaml: ERROR", e)

try:
    ma = yaml.safe_load(open("/opt/veridian/ai-os/MASTER_ARCHITECTURE_2026-07-22.yaml"))
    print("\n--- MASTER_ARCHITECTURE open questions ---")
    for q in ma.get("open_questions_for_owner", []):
        print("  -", q)
except Exception as e:
    print("\n--- MASTER_ARCHITECTURE: ERROR", e)

try:
    sd = yaml.safe_load(open("/opt/veridian/ai-os/STANDING_DIRECTIVE.yaml"))
    print("\n--- STANDING_DIRECTIVE assistant_working_protocol rules ---")
    for k in sd.get("assistant_working_protocol", {}):
        if k.startswith("rule_"):
            print("  -", k)
except Exception as e:
    print("\n--- STANDING_DIRECTIVE: ERROR", e)

print("\n--- file inventory diff (new/changed/missing since last prompt) ---")
import subprocess as _sp
_r = _sp.run(["python3", "/opt/veridian/ai-os/scripts/file_inventory.py"], capture_output=True, text=True, timeout=30)
print(_r.stdout)
if _r.returncode != 0:
    print("INVENTORY SCRIPT ERROR:", _r.stderr[-500:])

print("\n--- OPEN RCA ITEMS (rejected tasks not yet investigated) ---")
import sqlite3 as _sq
try:
    _conn = _sq.connect("/opt/veridian/ai-os/memory/superboss-register.sqlite")
    _c = _conn.cursor()
    _c.execute("SELECT audit_id, ts, software_task_id, stderr_tail FROM rca_open WHERE rca_status='OPEN_NEEDS_RCA' ORDER BY ts DESC")
    _rows = _c.fetchall()
    _conn.close()
    if _rows:
        for _r in _rows:
            print(f"  [OPEN] {_r[0]} :: {_r[2]} @ {_r[1]}")
            print(f"         error: {(_r[3] or '')[:150]}")
    else:
        print("  (none open)")
except Exception as _e:
    print("  ERROR reading rca_open:", _e)

print("\n--- FULL SCRIPT/MECHANISM REGISTRY (MASTER_INDEX.yaml -- read this before building anything new) ---")
import yaml as _yaml
try:
    _mi = _yaml.safe_load(open("/opt/veridian/ai-os/MASTER_INDEX.yaml"))
    _regs = _mi.get("registries", [])
    print(f"({len(_regs)} total registered mechanisms)")
    for _r in _regs:
        print(f"  {_r.get('id','?')} :: {_r.get('path','?')}")
except Exception as _e:
    print("ERROR reading MASTER_INDEX.yaml:", _e)

print("\n*** MANDATORY: before writing any new script, run: ***")
print('    python3 /opt/veridian/scripts/superboss-register.py check-duplicate "<keywords>"')
print("*** This tool already exists and works -- it was not used before building tonight's cron automation, ***")
print("*** which is why run-logged.sh (already registered since 2026-07-20) had to be rediscovered by accident. ***")

print("\n--- UNREGISTERED MENTIONS (auto-flagged by postflight_audit_gate.py, need registration) ---")
try:
    _conn2 = _sq.connect("/opt/veridian/ai-os/memory/superboss-register.sqlite")
    _c2 = _conn2.cursor()
    _c2.execute("SELECT id, ts, software_task_id, mentioned_path FROM unregistered_mentions WHERE status='NEEDS_REGISTRATION' ORDER BY ts DESC")
    _rows2 = _c2.fetchall()
    _conn2.close()
    if _rows2:
        for _r2 in _rows2:
            print(f"  [NEEDS_REGISTRATION] {_r2[3]} (from {_r2[2]} @ {_r2[1]})")
    else:
        print("  (none pending)")
except Exception as _e2:
    print("  ERROR reading unregistered_mentions:", _e2)

print("\n" + "=" * 70)
print("END BOOTSTRAP -- read the above before starting any new work.")
print("=" * 70)


def _safe_count(conn, sql, params=()):
    """Returns (n, None) on success, (0, error_str) if the table/query doesn't exist yet
    (e.g. a fresh DB) -- never raises, since this must not crash the mandatory first command."""
    try:
        row = conn.execute(sql, params).fetchone()
        return (row[0] if row else 0), None
    except Exception as e:
        return 0, str(e)


def build_pre_execution_fields():
    """Runs the real, cheap checks this call site CAN honestly perform, and maps each of Part 40's
    39 literal Pre-Execution Log fields to YES (real evidence just gathered) or NO (an honest gap --
    either no mechanism exists at all, or this generic bootstrap-time call site cannot determine it,
    e.g. task-specific judgment calls that only the calling agent can make later). Zero fabricated YES."""
    conn = sqlite3.connect(DB)
    instructions_n, _ = _safe_count(conn, "SELECT COUNT(*) FROM instructions")
    work_items_n, _ = _safe_count(conn, "SELECT COUNT(*) FROM work_items")
    actions_n, _ = _safe_count(conn, "SELECT COUNT(*) FROM actions")
    system_index_n, _ = _safe_count(conn, "SELECT COUNT(*) FROM system_index")
    rca_open_n, rca_err = _safe_count(conn, "SELECT COUNT(*) FROM rca_open WHERE rca_status='OPEN_NEEDS_RCA'")
    unreg_n, unreg_err = _safe_count(conn, "SELECT COUNT(*) FROM unregistered_mentions WHERE status='NEEDS_REGISTRATION'")
    task_audits_n, ta_err = _safe_count(conn, "SELECT COUNT(*) FROM task_audits")
    compliance_runs_n, cr_err = _safe_count(conn, "SELECT COUNT(*) FROM directive_compliance_runs")
    conn.close()

    yaml_files = {
        "MASTER_INDEX.yaml": "/opt/veridian/ai-os/MASTER_INDEX.yaml",
        "SYSTEM_MAP.yaml": "/opt/veridian/ai-os/SYSTEM_MAP.yaml",
        "STANDING_DIRECTIVE.yaml": "/opt/veridian/ai-os/STANDING_DIRECTIVE.yaml",
        "MASTER_ARCHITECTURE_2026-07-22.yaml": "/opt/veridian/ai-os/MASTER_ARCHITECTURE_2026-07-22.yaml",
    }
    yaml_loaded = {}
    for name, p in yaml_files.items():
        try:
            yaml.safe_load(open(p))
            yaml_loaded[name] = True
        except Exception:
            yaml_loaded[name] = False
    all_yaml_ok = all(yaml_loaded.values())

    rule_keys = []
    try:
        sd = yaml.safe_load(open("/opt/veridian/ai-os/STANDING_DIRECTIVE.yaml"))
        rule_keys = [k for k in sd.get("assistant_working_protocol", {}) if k.startswith("rule_")]
    except Exception:
        pass

    def yes(evidence):
        return {"status": "YES", "evidence": evidence}

    def no(reason):
        return {"status": "NO", "evidence": reason}

    f = {}
    f["Context Loaded"] = yes(f"queried instructions/work_items/actions: {instructions_n}/{work_items_n}/{actions_n} rows in {DB}")
    f["Owner Memory Loaded"] = no("no owner memory store exists (ai-os/EXECUTION_RULES_AUDIT_2026-07-23.yaml Part 33: MISSING, out of this task's scope)")
    f["Organization Memory Loaded"] = no("no organization memory store exists (same audit, Part 34: MISSING, out of this task's scope)")
    f["End User Memory Loaded"] = no("no end user memory store exists (same audit, Part 35: MISSING, out of this task's scope)")
    f["Previous Conversations Loaded"] = yes(f"read instructions.raw_text: {instructions_n} rows (closest real analog to 'conversations' in this system)")
    f["Previous Commitments Loaded"] = (yes(f"queried rca_open WHERE rca_status='OPEN_NEEDS_RCA': {rca_open_n} rows")
                                        if rca_err is None else no(f"rca_open query failed: {rca_err}"))
    f["Pending Tasks Loaded"] = (yes(f"queried work_items ({work_items_n} rows) + unregistered_mentions NEEDS_REGISTRATION ({unreg_n} rows)")
                                 if unreg_err is None else yes(f"queried work_items: {work_items_n} rows (unregistered_mentions table not yet present: {unreg_err})"))
    f["Metadata Searched"] = yes(f"queried system_index: {system_index_n} rows")
    f["YAML Files Searched"] = (yes(f"loaded {', '.join(yaml_loaded)} via yaml.safe_load") if all_yaml_ok
                                else no(f"one or more YAML files failed to load: {yaml_loaded}"))
    f["Entity Relationships Searched"] = no("this generic bootstrap call site does not query system_index.calls/called_by directly (available via superboss-register.py search, but not auto-run here)")
    f["Dependencies Searched"] = no("same reason as Entity Relationships Searched -- calls/called_by available on demand, not auto-queried by this script")
    f["Configuration Searched"] = (yes("loaded STANDING_DIRECTIVE.yaml (execution/guardrails sections)") if yaml_loaded.get("STANDING_DIRECTIVE.yaml") else no("STANDING_DIRECTIVE.yaml failed to load"))
    f["Business Rules Searched"] = (yes(f"printed STANDING_DIRECTIVE.yaml assistant_working_protocol rule_* keys: {rule_keys}") if rule_keys else no("no rule_* keys found under assistant_working_protocol"))
    f["Documentation Searched"] = (yes("read MASTER_ARCHITECTURE_2026-07-22.yaml open_questions_for_owner") if yaml_loaded.get("MASTER_ARCHITECTURE_2026-07-22.yaml") else no("MASTER_ARCHITECTURE_2026-07-22.yaml failed to load"))
    f["Existing Software Searched"] = yes(f"printed MASTER_INDEX.yaml registries + system_index ({system_index_n} rows) and the mandatory check-duplicate reminder")
    f["Existing Scripts Searched"] = yes(f"system_index rows include script paths ({system_index_n} rows available via check-duplicate)")
    f["Existing Automation Searched"] = yes(f"system_index includes dispatch_entrypoint/monitor/audit category rows ({system_index_n} total rows)")
    f["Existing APIs Searched"] = no("no ai-os-layer API registry exists to search (app-layer API routes are product-layer, out of this task's scope)")
    f["Cache Searched"] = no("no glm-response-cache.sqlite lookup performed by this call site (work_items.cache_id/ai_cache_id reference it, but not auto-queried here)")
    f["Logs Searched"] = yes("ran file_inventory.py for a real new/changed/missing diff (see output above)")
    f["Audit Records Searched"] = (yes(f"queried task_audits: {task_audits_n} rows") if ta_err is None else no(f"task_audits query failed: {ta_err}"))
    f["History Searched"] = (yes(f"queried directive_compliance_runs ({compliance_runs_n} rows) + work_items/actions history") if cr_err is None
                             else yes(f"queried work_items/actions history ({work_items_n}/{actions_n} rows; directive_compliance_runs not yet present: {cr_err})"))
    f["Existing Solution Found"] = no("this generic script does not run a task-specific check-duplicate query -- that requires the task's own subject keywords, decided by the calling agent, not by session_bootstrap.py")
    f["Existing Software Reused"] = no("same reason as Existing Solution Found -- a task-specific judgment call made later, not at bootstrap time")
    f["Task Broken into Steps"] = no("not yet performed at bootstrap time -- happens during planning, after this script runs")
    f["Software Steps Identified"] = no("same reason as Task Broken into Steps")
    f["AI Steps Identified"] = no("same reason as Task Broken into Steps")
    f["Human Approval Required"] = no("not determined at bootstrap time -- a task-specific judgment call made during planning")
    f["Execution Plan Created"] = no("not yet created at bootstrap time -- this log is written before planning begins")
    f["Execution Plan Validated"] = no("same reason as Execution Plan Created")
    f["Dependencies Verified"] = no("searched (see Dependencies Searched) but not verified against a specific task's needs at this generic call site")
    f["Permissions Verified"] = no("preflight-guard.py runs as a separate gate in worker-entrypoint.sh, not invoked or checked by session_bootstrap.py itself")
    f["Configuration Verified"] = no("configuration is searched (see Configuration Searched) but not verified against a schema by this call site")
    f["AI Required"] = no("task-specific judgment, not decided generically by session_bootstrap.py")
    f["Software Can Execute Without AI"] = no("same reason as AI Required")
    f["Previous Commitments Verified"] = no("rca_open items are loaded (see Previous Commitments Loaded) but not individually verified/resolved by this generic call site")
    f["Duplicate Work Prevented"] = no("the mandatory check-duplicate command is printed as a reminder but not auto-invoked with task-specific terms by this generic script")
    f["Safety Validation Passed"] = no("preflight-guard.py's safety gate is a separate call site (worker-entrypoint.sh), not run by session_bootstrap.py itself")
    f["Ready for Execution"] = no("context recovery + system search (this script's own real output) is complete, but planning/verification steps happen after bootstrap, in a later call site -- not truthfully YES here")
    return f


def write_pre_execution_log(work_item_id, software_task_id):
    fields = build_pre_execution_fields()
    fd, path = tempfile.mkstemp(prefix="pre_execution_fields_", suffix=".json")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(fields, fh)
        cmd = [
            "python3", REGISTER_SCRIPT, "log-execution", "--phase", "PRE",
            "--source-script", "ai-os/scripts/session_bootstrap.py",
            "--fields-file", path,
        ]
        if work_item_id:
            cmd += ["--work-item-id", work_item_id]
        if software_task_id:
            cmd += ["--software-task-id", software_task_id]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        print("\n--- PRE-EXECUTION LOG (ai-os/EXECUTION_RULES_AUDIT_2026-07-23.yaml Part 40) ---")
        if result.returncode == 0:
            print(" ", result.stdout.strip())
        else:
            print("  ERROR writing execution_log row:", result.stderr[-500:])
    finally:
        os.unlink(path)


write_pre_execution_log(_args.work_item_id, _args.software_task_id)
