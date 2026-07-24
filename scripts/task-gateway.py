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
TIGHT_VALIDATION = f"{SCRIPTS}/tight_task_validation.py"
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
    knowledge_result = run_json(
        ["python3", SUPERBOSS, "query-knowledge", keyword_str],
        "query-knowledge",
    )
    # Phase 1 Capability Registry live wiring (task-20260724-083420,
    # closes_engines: [3]): lookup_contract's call_site_requirement --
    # "any code path about to construct an LLM prompt to accomplish a named
    # task MUST call lookupCapability() first". task-gateway.py submit is
    # exactly that entrypoint (the first stop before a task is dispatched to
    # an AI worker), so it belongs alongside check-duplicate/search/
    # query-knowledge above, not as a separate gate a caller could skip.
    capability_result = run_json(
        ["python3", SUPERBOSS, "lookup-capability", "--intent-text", keyword_str],
        "lookup-capability",
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
        "knowledge_matches": knowledge_result,
        "capability_matches": capability_result.get("matches", []),
        "capability_deterministic_path_available": any(
            (not m.get("ai_required")) and m.get("apis") for m in capability_result.get("matches", [])
        ),
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

    # INS-20260724-113032-8032: the section-presence check above only proves
    # SUCCESS_CRITERIA exists and isn't empty -- it does not catch prose-only
    # SUCCESS_CRITERIA that reads as satisfied but gives postflight_audit_gate.py's
    # audit_cmd nothing real to run. tight_task_validation.py's fuller check
    # (placeholders/ambiguity/contradiction/tier + the runnable-command check)
    # runs here, before veridian-task.py create, so dispatch is blocked until
    # the prompt is actually fixed rather than merely well-formed.
    tight_proc = run(["python3", TIGHT_VALIDATION, args.prompt_file])
    try:
        tight_result = json.loads(tight_proc.stdout)
    except json.JSONDecodeError:
        fail("tight_task_validation.py did not return parseable JSON",
             stdout=tight_proc.stdout, stderr=tight_proc.stderr)
    if not tight_result.get("valid", False):
        fail(
            "tight_task_validation.py rejected this prompt-file -- dispatch blocked until fixed",
            reason=tight_result.get("reason"),
            guidance=tight_result.get("guidance"),
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


def check_branch_merged_to_master(task_id):
    """Real fix for a genuine gap found 2026-07-24: a full-repo audit showed only
    4 of 28 real worker branches from 2026-07-23 had ever been merged to master --
    every phase's own EXPECTED_OUTPUT said "COMMIT+PUSH" and every phase did push
    a branch, but nothing ever verified the push reached the canonical branch.
    Master sat frozen at a ~10:38am commit while 8+ hours of real, closed-out work
    (governance items, the watchdog service, task-gateway.py itself, the Knowledge
    Engine) sat on disconnected branches nobody ever opened or merged a PR for.
    This makes that check part of every close, not something a human has to
    remember to audit for separately. Best-effort: a task with no workspace git
    repo, or no matching worker branch, returns NO_GIT_ACTIVITY rather than
    failing -- most tasks are legitimate non-code work."""
    workspace = f"{AI_OS}/tasks/{task_id}/workspace"
    if not os.path.exists(os.path.join(workspace, ".git")):
        return {"status": "NO_GIT_ACTIVITY", "detail": "no .git in task workspace"}
    branch_proc = subprocess.run(
        ["git", "-C", workspace, "branch", "--show-current"],
        capture_output=True, text=True, timeout=15,
    )
    branch = branch_proc.stdout.strip()
    if not branch:
        return {"status": "NO_GIT_ACTIVITY", "detail": "workspace not on a named branch"}
    # gh pr, not git merge-base --is-ancestor: GitHub squash/rebase merges create a NEW
    # commit on master, so the original branch tip is never a literal git ancestor even
    # when its content genuinely landed -- confirmed 2026-07-24 against a known-merged
    # branch (PR #4) that a naive ancestor-check incorrectly called NOT_MERGED.
    pr_proc = subprocess.run(
        ["gh", "pr", "list", "--repo", "FChecklist/claude-control",
         "--head", branch, "--state", "all", "--json", "number,state,mergedAt"],
        capture_output=True, text=True, timeout=30,
    )
    try:
        prs = json.loads(pr_proc.stdout) if pr_proc.returncode == 0 else []
    except json.JSONDecodeError:
        prs = []
    merged_prs = [pr for pr in prs if pr.get("state") == "MERGED"]
    if merged_prs:
        return {"status": "MERGED", "branch": branch, "pr_number": merged_prs[0]["number"]}
    open_prs = [pr for pr in prs if pr.get("state") == "OPEN"]
    return {
        "status": "NOT_MERGED",
        "branch": branch,
        "open_pr_number": open_prs[0]["number"] if open_prs else None,
        "action_needed": (
            f"PR #{open_prs[0]["number"]} is open but not merged -- merge it" if open_prs
            else f"no PR exists for '{branch}' -- open one and merge it, or fold it into a reconciliation pass"
        ),
    }


# Knowledge Engine Phase 2 (task-20260724-033446), SCOPE item 4 /
# candidate auto_update_on_task_completion: a task's real changed-file set
# (from its own git diff) mapped to live absolute paths, using the same
# repo-root -> live-path prefix convention every prior phase has used to
# deploy tracked files (ai-os/ and scripts/ mirror their live counterparts
# 1:1; ai-os-scripts/ mirrors ai-os/scripts/ -- see ai-os-scripts/file_inventory.py's
# own live deployment history). Best-effort: an unrecognized prefix is
# skipped, never guessed.
REPO_PATH_PREFIXES = [
    ("ai-os-scripts/", f"{AI_OS}/scripts/"),
    ("ai-os/", f"{AI_OS}/"),
    ("scripts/", f"{SCRIPTS}/"),
]


def _map_repo_path_to_live(repo_relative_path):
    for prefix, live_prefix in REPO_PATH_PREFIXES:
        if repo_relative_path.startswith(prefix):
            return live_prefix + repo_relative_path[len(prefix):]
    if repo_relative_path == "CONTROLLER.yaml":
        return f"{VERIDIAN_ROOT}/repos/claude-control/CONTROLLER.yaml"
    return None


def reverify_touched_knowledge_engine_rows(task_id):
    """Real fix for Phase2 candidate auto_update_on_task_completion: knowledge_engine
    rows were only ever written by an explicit register-knowledge call -- nothing
    re-checked content_hash when a governed artifact actually changed, so
    verification_status could silently go stale. This computes the just-closed
    task's own real changed-file set (git diff against its branch point), maps
    each to a live absolute path, and calls verify-knowledge (in-place UPDATE,
    never a duplicate INSERT) for every knowledge_engine row whose artifact_path
    matches -- so every close is a real re-verify, not a one-off manual run."""
    workspace = f"{AI_OS}/tasks/{task_id}/workspace"
    if not os.path.exists(os.path.join(workspace, ".git")):
        return {"status": "NO_GIT_ACTIVITY", "touched_knowledge_engine_paths": [], "reverify_result": None}

    diff_proc = subprocess.run(
        ["git", "-C", workspace, "diff", "--name-only", "origin/master...HEAD"],
        capture_output=True, text=True, timeout=15,
    )
    changed = [line.strip() for line in diff_proc.stdout.splitlines() if line.strip()]
    live_paths = sorted({p for p in (_map_repo_path_to_live(c) for c in changed) if p})

    if not os.path.isfile(DB_PATH) or not live_paths:
        return {"status": "NO_TOUCHED_ROWS", "changed_files": changed, "touched_knowledge_engine_paths": [], "reverify_result": None}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    known_paths = {r["artifact_path"] for r in conn.execute("SELECT DISTINCT artifact_path FROM knowledge_engine")}
    conn.close()
    matched = [p for p in live_paths if p in known_paths]

    if not matched:
        return {"status": "NO_TOUCHED_ROWS", "changed_files": changed, "touched_knowledge_engine_paths": [], "reverify_result": None}

    cmd = ["python3", SUPERBOSS, "verify-knowledge"]
    for p in matched:
        cmd += ["--path", p]
    result = run_json(cmd, "verify-knowledge")
    return {"status": "REVERIFIED", "changed_files": changed, "touched_knowledge_engine_paths": matched, "reverify_result": result}


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

    git_merge_status = check_branch_merged_to_master(args.task_id)
    if git_merge_status["status"] == "NOT_MERGED":
        run([
            "python3", SUPERBOSS, "log-action",
            "--source", "ai_agent", "--medium", "task_gateway",
            "--content", f"unmerged_branch:{args.task_id}:{git_merge_status['branch']}"
            f":{git_merge_status['commits_ahead_of_master']}_commits_ahead",
        ])

    knowledge_engine_reverify = reverify_touched_knowledge_engine_rows(args.task_id)

    print(json.dumps({
        "audit_verdict": verdict,
        "checkpoint_status": checkpoint_status,
        "audit_id": audit_result.get("audit_id"),
        "work_item_id": close_result.get("work_item_id"),
        "git_merge_status": git_merge_status,
        "knowledge_engine_reverify": knowledge_engine_reverify,
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
