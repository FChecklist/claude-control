#!/usr/bin/env python3
"""
task-gateway.py -- single unified CLI implementing
ai-os/STANDING_DIRECTIVE.yaml's v2_task_lifecycle_pipeline (phases
0/1/4/5/7/8/9/11) as real, callable software commands, so no AI agent or
router needs to remember/sequence superboss-register.py, veridian-task.py,
and postflight_audit_gate.py in the right order manually.

Every subcommand's real work is delegated to the already-built script it
wraps -- this file only sequences those calls and merges their outputs into
one JSON response per subcommand. It does not reimplement any of their
internal logic (no direct sqlite writes; the one direct sqlite read, in
lookup_work_item(), is a read-only lookup used to correctly sequence later
calls, not a substitute for any wrapped script).

Subcommands: submit, start, log, close, register-automation, status
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys

import yaml

VERIDIAN_ROOT = "/opt/veridian"
SCRIPTS = f"{VERIDIAN_ROOT}/scripts"
AI_OS = f"{VERIDIAN_ROOT}/ai-os"
SUPERBOSS = f"{SCRIPTS}/superboss-register.py"
VERIDIAN_TASK = f"{SCRIPTS}/veridian-task.py"
POSTFLIGHT = f"{AI_OS}/scripts/postflight_audit_gate.py"
DB_PATH = f"{AI_OS}/memory/superboss-register.sqlite"

REQUIRED_SECTIONS = [
    "OBJECTIVE", "SCOPE", "KNOWN_CONTEXT", "SUCCESS_CRITERIA",
    "EXPECTED_OUTPUT", "CONSTRAINTS", "COMPLEXITY_TIER",
]

STOPWORDS = {
    "the", "a", "an", "of", "to", "for", "and", "or", "in", "on", "vs",
    "is", "are", "be", "do", "does", "this", "that", "with", "from",
    "by", "at", "as", "it", "its", "into", "not", "no",
}


def fail(message, **extra):
    payload = {"error": message}
    payload.update(extra)
    print(json.dumps(payload, indent=2, default=str))
    sys.exit(1)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def run_json(cmd, step):
    """Run a wrapped script expected to exit 0 and print exactly one JSON blob.
    A nonzero exit or unparseable stdout here is a real wrapper-level failure
    (distinct from postflight_audit_gate.py's own FAIL verdict, which exits 1
    by design and is handled separately in cmd_close)."""
    proc = run(cmd)
    if proc.returncode != 0:
        fail(f"{step} failed (exit {proc.returncode})", command=cmd,
             stdout=proc.stdout[-2000:], stderr=proc.stderr[-2000:])
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        fail(f"{step} did not return parseable JSON", command=cmd,
             stdout=proc.stdout[-2000:], stderr=proc.stderr[-2000:])


def lookup_work_item(task_id):
    """Read-only lookup of the work_items row linked to this task_id, checked
    against both ai_task_id (veridian-task.py worker tasks) and
    software_task_id (the field name postflight_audit_gate.py and phase_7's
    exact_command use generically for whatever id is under audit). Returns
    None if no row is found -- callers must handle that, not assume it."""
    if not os.path.isfile(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT work_item_id, instruction_id FROM work_items "
        "WHERE ai_task_id = ? OR software_task_id = ? ORDER BY ts DESC LIMIT 1",
        (task_id, task_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def extract_keywords_mechanical(text):
    """STANDING_DIRECTIVE.yaml v2_task_lifecycle_pipeline.phase_1_software_first_search
    .keyword_extraction_baseline_mechanical_first.step_1_mechanical: regex-extract
    quoted strings, file paths (contains '/' or '.py'/'.yaml'/'.md'),
    snake_case/kebab-case identifiers, numbers referencing item/rule IDs --
    zero AI judgment, pure regex."""
    quoted = re.findall(r'"([^"]+)"', text) + re.findall(r"'([^']+)'", text)

    tokens = re.findall(r"\S+", text)
    file_paths = [
        t.strip(".,;:()[]{}\"'")
        for t in tokens
        if "/" in t or re.search(r"\.(py|yaml|yml|md)$", t.strip(".,;:()[]{}\"'"))
    ]

    identifiers = re.findall(r"\b[a-z0-9]+(?:[_-][a-z0-9]+)+\b", text)
    rule_ids = re.findall(r"\b(?:item|rule)\s*#?\d+\b", text, re.IGNORECASE)

    keywords = []
    for group in (quoted, file_paths, identifiers, rule_ids):
        for term in group:
            term = term.strip()
            if term and term.lower() not in STOPWORDS and term not in keywords:
                keywords.append(term)
    return keywords


def cmd_submit(args):
    keywords = extract_keywords_mechanical(args.text)
    fallback_used = False
    if not keywords:
        # step_1_mechanical yielded zero terms. This script cannot itself
        # exercise step_2_ai_supplement (that step is explicitly AI
        # judgment, not mechanical); instead it applies a purely mechanical
        # fallback (first significant words) so the mandatory phase_1
        # search still runs with a non-empty query, and flags that this
        # happened so a calling AI agent can supply real step_2 terms if it
        # judges that necessary.
        fallback_used = True
        words = re.findall(r"[A-Za-z]{4,}", args.text)
        keywords = [w for w in words if w.lower() not in STOPWORDS][:5]
    keyword_str = " ".join(keywords) if keywords else args.text

    log_result = run_json(
        ["python3", SUPERBOSS, "log-instruction",
         "--text", args.text, "--source", args.source,
         "--medium", "task_gateway", "--session-id", args.session_id],
        "log-instruction",
    )
    instruction_id = log_result.get("instruction_id")

    dup_result = run_json(
        ["python3", SUPERBOSS, "check-duplicate", keyword_str],
        "check-duplicate",
    )
    search_result = run_json(
        ["python3", SUPERBOSS, "search", keyword_str, "--limit", "10"],
        "search",
    )

    systemctl_proc = run([
        "systemctl", "--user", "list-units", "veridian-worker@*",
        "--state=active", "--no-legend",
    ])
    active_task_ids = []
    for line in systemctl_proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        unit = line.split()[0]
        m = re.match(r"veridian-worker@(.+)\.service", unit)
        if m:
            active_task_ids.append(m.group(1))

    kw_lower = [k.lower() for k in keywords]
    active_collision_task_ids = [
        tid for tid in active_task_ids
        if any(k in tid.lower() for k in kw_lower)
    ]

    print(json.dumps({
        "instruction_id": instruction_id,
        "duplicate_found": bool(dup_result.get("found", 0) > 0),
        "duplicate_evidence": dup_result.get("matches", []),
        "prior_search_results": search_result,
        "active_collision_task_ids": active_collision_task_ids,
        "keywords_extracted": keywords,
        "keyword_extraction_fallback_used": fallback_used,
    }, indent=2, default=str))


def cmd_start(args):
    if not os.path.isfile(args.prompt_file):
        fail(f"prompt-file not found: {args.prompt_file}")
    text = open(args.prompt_file).read()
    missing = [s for s in REQUIRED_SECTIONS if f"## {s}" not in text]
    if missing:
        fail(
            "prompt-file does not follow the literal_template -- missing required section(s)",
            missing_sections=missing,
            prompt_file=args.prompt_file,
        )

    create_proc = run([
        "python3", VERIDIAN_TASK, "create",
        "--title", args.title, "--repo", args.repo, "--prompt", text,
    ])
    if create_proc.returncode != 0:
        fail("veridian-task.py create failed", stdout=create_proc.stdout, stderr=create_proc.stderr)
    m = re.search(r"CREATED:\s*(\S+)", create_proc.stdout)
    if not m:
        fail("could not parse task_id from veridian-task.py create output", stdout=create_proc.stdout)
    task_id = m.group(1)
    service = f"veridian-worker@{task_id}.service"

    # veridian-task.py create already enables+starts the unit; this explicit
    # start is the spec-mandated verification step and is idempotent against
    # an already-active unit.
    run(["systemctl", "--user", "start", service])
    is_active_proc = run(["systemctl", "--user", "is-active", service])
    systemd_active = is_active_proc.stdout.strip() == "active"

    work_result = run_json(
        ["python3", SUPERBOSS, "log-work",
         "--instruction-id", args.instruction_id,
         "--ai-task-id", task_id,
         "--source", "ai_agent", "--medium", "task_gateway",
         "--content", f"task_start:{args.title[:60]}",
         "--term", "task_gateway,start",
         "--status", "open"],
        "log-work",
    )

    print(json.dumps({
        "task_id": task_id,
        "systemd_active": systemd_active,
        "work_item_id": work_result.get("work_item_id"),
    }, indent=2, default=str))


def cmd_log(args):
    wi = lookup_work_item(args.task_id)
    work_item_id = wi["work_item_id"] if wi else None

    cmd = ["python3", SUPERBOSS, "log-action",
           "--source", "ai_agent", "--medium", "task_gateway",
           "--content", args.event, "--term", "task_gateway,log"]
    if work_item_id:
        cmd += ["--work-item-id", work_item_id]

    action_result = run_json(cmd, "log-action")

    print(json.dumps({
        "action_id": action_result.get("action_id"),
        "work_item_id": work_item_id,
        "work_item_resolved": work_item_id is not None,
    }, indent=2, default=str))


def extract_section(text, name):
    m = re.search(rf"##\s*{re.escape(name)}\s*\n(.*?)(?=\n##\s|\Z)", text, re.DOTALL)
    return m.group(1).strip() if m else None


def cmd_close(args):
    task_dir = f"{AI_OS}/tasks/{args.task_id}"
    prompt_file = f"{task_dir}/prompt.txt"
    if not os.path.isfile(prompt_file):
        fail(f"prompt.txt not found for task {args.task_id} at {prompt_file}")
    text = open(prompt_file).read()

    success_criteria = extract_section(text, "SUCCESS_CRITERIA")
    if success_criteria is None:
        fail(f"SUCCESS_CRITERIA section not found in {prompt_file}")

    if args.audit_cmd.strip() not in success_criteria:
        fail(
            "verification_command_predefinition_rule violation: --audit-cmd was not found "
            f"verbatim in {args.task_id}'s own pre-defined SUCCESS_CRITERIA ({prompt_file}). "
            "postflight_audit_gate.py's --audit-cmd must be copied VERBATIM from what was "
            "written at plan/dispatch time, never authored fresh at close time (self-certification "
            "is exactly what this rule prevents).",
            provided_audit_cmd=args.audit_cmd,
            predefined_success_criteria=success_criteria,
        )

    wi = lookup_work_item(args.task_id)
    instruction_id = wi.get("instruction_id") if wi else None

    audit_cmd_list = [
        "python3", POSTFLIGHT,
        "--software-task-id", args.task_id,
        "--audit-cmd", args.audit_cmd,
        "--content", args.evidence,
    ]
    if instruction_id:
        audit_cmd_list += ["--instruction-id", instruction_id]

    audit_proc = run(audit_cmd_list)
    try:
        audit_result = json.loads(audit_proc.stdout)
    except json.JSONDecodeError:
        fail("postflight_audit_gate.py did not return parseable JSON",
             stdout=audit_proc.stdout, stderr=audit_proc.stderr)

    verdict = audit_result.get("verdict")
    if verdict != "DONE":
        print(json.dumps({
            "audit_verdict": verdict,
            "reason": audit_result,
        }, indent=2, default=str))
        sys.exit(1)

    close_cmd = ["python3", SUPERBOSS, "log-work",
                 "--software-task-id", args.task_id,
                 "--status", "closed",
                 "--source", "ai_agent", "--medium", "task_gateway",
                 "--content", f"task_close:{args.task_id}"]
    if instruction_id:
        close_cmd += ["--instruction-id", instruction_id]
    close_result = run_json(close_cmd, "log-work(close)")

    checkpoint_proc = run([
        "python3", VERIDIAN_TASK, "checkpoint", args.task_id,
        "--status", "completed", "--note", args.evidence,
    ])
    checkpoint_status = "completed" if checkpoint_proc.returncode == 0 else "checkpoint_failed"

    print(json.dumps({
        "audit_verdict": verdict,
        "checkpoint_status": checkpoint_status,
        "audit_id": audit_result.get("audit_id"),
        "work_item_id": close_result.get("work_item_id"),
    }, indent=2, default=str))


def cmd_register_automation(args):
    result = run_json(
        ["python3", SUPERBOSS, "index-add",
         "--path", args.path, "--category", args.category, "--layer", args.layer,
         "--status", "live", "--purpose", args.purpose, "--tags", args.tags],
        "index-add",
    )
    print(json.dumps(result, indent=2, default=str))


def cmd_status(args):
    task_yaml_path = f"{AI_OS}/tasks/{args.task_id}/task.yaml"
    if not os.path.isfile(task_yaml_path):
        fail(f"task.yaml not found at {task_yaml_path}")
    task = yaml.safe_load(open(task_yaml_path))

    checkpoints = task.get("checkpoints") or []
    last_checkpoint = checkpoints[-1] if checkpoints else None

    service = task.get("service") or f"veridian-worker@{args.task_id}.service"
    active_proc = run(["systemctl", "--user", "is-active", service])
    systemd_active = active_proc.stdout.strip() == "active"

    watchdog_last = None
    watchdog_path = f"{AI_OS}/logs/watchdog.jsonl"
    if os.path.isfile(watchdog_path):
        for line in reversed(open(watchdog_path).readlines()):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("task_id") == args.task_id:
                watchdog_last = entry
                break

    print(json.dumps({
        "status": task.get("status"),
        "last_checkpoint_note": (last_checkpoint or {}).get("note"),
        "systemd_active": systemd_active,
        "watchdog_last_action": watchdog_last,
    }, indent=2, default=str))


def build_parser():
    p = argparse.ArgumentParser(prog="task-gateway.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("submit")
    s.add_argument("--text", required=True)
    s.add_argument("--source", required=True, choices=["owner", "ai_agent"])
    s.add_argument("--session-id", dest="session_id", required=True)
    s.set_defaults(func=cmd_submit)

    st = sub.add_parser("start")
    st.add_argument("--instruction-id", dest="instruction_id", required=True)
    st.add_argument("--title", required=True)
    st.add_argument("--repo", required=True)
    st.add_argument("--prompt-file", dest="prompt_file", required=True)
    st.set_defaults(func=cmd_start)

    lg = sub.add_parser("log")
    lg.add_argument("--task-id", dest="task_id", required=True)
    lg.add_argument("--event", required=True)
    lg.set_defaults(func=cmd_log)

    cl = sub.add_parser("close")
    cl.add_argument("--task-id", dest="task_id", required=True)
    cl.add_argument("--audit-cmd", dest="audit_cmd", required=True)
    cl.add_argument("--evidence", required=True)
    cl.set_defaults(func=cmd_close)

    ra = sub.add_parser("register-automation")
    ra.add_argument("--path", required=True)
    ra.add_argument("--category", required=True)
    ra.add_argument("--layer", required=True)
    ra.add_argument("--purpose", required=True)
    ra.add_argument("--tags", required=True)
    ra.set_defaults(func=cmd_register_automation)

    stt = sub.add_parser("status")
    stt.add_argument("--task-id", dest="task_id", required=True)
    stt.set_defaults(func=cmd_status)

    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
