#!/usr/bin/env python3
"""
backfill_phase_self_report.py -- closes the root cause behind two real,
consecutive manual interventions this session (VERIDIAN_ARCHITECTURE_V2
phase_1 / compliance-tracker PR #559, phase_2 / PR #560): a phase's
worker was told (via auto_phase_continuation.py's own build_prompt())
to update its own phase-plan entry's status/completed_by_task/evidence
fields after merging, but real evidence from two consecutive real phases
shows workers do not reliably do this. is_phase_done() in
auto_phase_continuation.py requires that self-report to exist before it
will even attempt its real merged-PR cross-reference, so a missing
self-report permanently blocks auto-dispatch of whatever depends on it
until a human hand-edits the YAML (see commits fab4ff4, 1f9fd52).

This makes the self-report SOFTWARE's responsibility instead: given a
task id, it independently confirms a real merge via `gh pr view
--json state,mergedAt` (never trusting the task's own self-report), then
mechanically writes status/completed_by_task/evidence into the correct
phase-plan file under /opt/veridian/repos/claude-control (the master
clone every other real-state check in this pipeline already reads via
`git show master:...`) and commits+pushes directly to master -- the same
place the two manual backfills above were made.

Two call sites (both real, both root-caused this session):
  1. supervisor-entrypoint.sh, right after it confirms a tier1 merge for
     itself (`--task-id $TASK_ID`, single task, best-effort, non-fatal).
  2. auto_phase_continuation.py's own tier2 sweep (`--sweep`), since a
     tier2 PR is merged by a human out-of-band -- nothing else ever
     revisits it. --sweep also serves as the one-off retroactive-backfill
     tool for every existing phase plan in the system (SCOPE item 5).

Idempotent by construction: a phase already self-reporting done AND
carrying an extractable task id (the exact condition
auto_phase_continuation.is_phase_done() checks) is left untouched, so
re-running this after a worker DID self-report correctly is a no-op, and
re-running it on every tier1 merge / every 30-minute cron tick never
double-writes or clobbers a worker's own good evidence text.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import yaml

# Overridable via env for the regression tests (tests/backfill_phase_self_report_test.py)
# -- production always uses the real defaults, never a CLI flag, so a real
# invocation can never accidentally point at a test fixture.
REPO_ROOT = os.environ.get("VERIDIAN_REPO_ROOT_OVERRIDE", "/opt/veridian/repos/claude-control")
TASKS_DIR = os.environ.get("VERIDIAN_TASKS_DIR_OVERRIDE", "/opt/veridian/ai-os/tasks")
VERIDIAN_TASK = os.environ.get("VERIDIAN_TASK_CLI_OVERRIDE", "/opt/veridian/scripts/veridian-task.py")
PLAN_GLOB_RE = re.compile(r".*_(?:PHASE_PLAN|IMPLEMENTATION_PLAN)_[0-9]{4}-[0-9]{2}-[0-9]{2}\.yaml$")
TASK_ID_RE = re.compile(r"task-20\d{6}-[a-z0-9-]+")
PHASE_REF_RE = re.compile(
    r"This is (?P<phase_id>[a-zA-Z0-9_-]+) of ai-os/(?P<plan_file>[A-Za-z0-9_.-]+\.yaml)"
)


def log(msg):
    print(msg, file=sys.stderr)


def run(cmd, timeout=60, cwd=None):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)


# ---------------------------------------------------------------------------
# Resolving which phase-plan entry a task corresponds to
# ---------------------------------------------------------------------------

def resolve_phase_ref(task_dir):
    """Prefers the structured phase_plan.yaml sidecar (written by
    auto_phase_continuation.py's dispatch() going forward); falls back to
    regex-parsing the task's own dispatch prompt.txt, which already
    contains "This is <phase_id> of ai-os/<plan_file>" verbatim (same
    text build_prompt() has generated all along) -- needed for every task
    dispatched before this sidecar existed, including any currently
    in-flight task."""
    sidecar = os.path.join(task_dir, "phase_plan.yaml")
    if os.path.isfile(sidecar):
        try:
            with open(sidecar) as f:
                doc = yaml.safe_load(f) or {}
            if doc.get("plan_file") and doc.get("phase_id"):
                return doc["plan_file"], doc["phase_id"]
        except (OSError, yaml.YAMLError) as e:
            log(f"  WARNING: could not parse {sidecar}: {e}")

    prompt_path = os.path.join(task_dir, "prompt.txt")
    if os.path.isfile(prompt_path):
        with open(prompt_path) as f:
            text = f.read()
        m = PHASE_REF_RE.search(text)
        if m:
            return m.group("plan_file"), m.group("phase_id")
    return None, None


# ---------------------------------------------------------------------------
# Real merge confirmation (same proof standard as
# supervisor-entrypoint.sh's own MERGE-DETECTION-BLOCK: gh pr view's
# state/mergedAt fields, never a self-report, never a shell exit code)
# ---------------------------------------------------------------------------

def confirm_merge(task_id, repo, branch=None):
    """Returns (merged: bool, pr_number, merged_at) for task_id's PR on
    FChecklist/<repo>. branch defaults to worker/<task_id> (this
    pipeline's universal convention -- task.yaml's own branch field, task-
    gateway.py, and auto_phase_continuation.py's gh_pr_merged_for_task all
    agree on it)."""
    branch = branch or f"worker/{task_id}"
    proc = run(["gh", "pr", "list", "--repo", f"FChecklist/{repo}", "--head", branch,
                "--state", "all", "--json", "state,number,mergedAt"])
    if proc.returncode != 0:
        return False, None, None
    try:
        rows = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return False, None, None
    for r in rows:
        if r.get("state") == "MERGED" and r.get("mergedAt"):
            return True, r.get("number"), r.get("mergedAt")
    return False, None, None


# ---------------------------------------------------------------------------
# Targeted text-level phase-block edit (never a full YAML re-dump -- this
# repo's own two real hand-backfills (commits fab4ff4, 1f9fd52) are pure
# line-level edits of the status/completed_by_task/evidence fields, and a
# full yaml.safe_load+dump round-trip would reformat every block-scalar
# string in the file for a one-line semantic change)
# ---------------------------------------------------------------------------

def find_phase_block(lines, phase_id):
    """Returns (start, end) line-index range [start, end) for the phase
    entry whose id/phase field matches phase_id, covering both real
    schemas this session's plan files use: `- id: <string>` and
    `- phase: <int>` (normalized the same way
    auto_phase_continuation.normalize_phase_id() does) -- and, unlike a
    fixed-column assumption, both real indent styles this session's plan
    files actually use (`- id:` at column 0 in
    VERIDIAN_ARCHITECTURE_V2_PHASE_PLAN_2026-07-25.yaml, `  - phase:` at
    column 2 in AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml). The end
    boundary is the next list item at the SAME indent depth, not just the
    next line starting with a dash, so a phase's own nested list fields
    (scope:, depends_on:, etc.) are never mistaken for a sibling phase."""
    start = None
    indent = None
    id_re = re.compile(r"^(\s*)- id:\s*(\S+)")
    phase_re = re.compile(r"^(\s*)- phase:\s*(\d+)\s*$")
    target_num = None
    m = re.match(r"phase-(\d+)$", phase_id)
    if m:
        target_num = m.group(1)
    for i, line in enumerate(lines):
        idm = id_re.match(line)
        if idm and idm.group(2) == phase_id:
            start, indent = i, idm.group(1)
            break
        pm = phase_re.match(line)
        if pm and target_num and pm.group(2) == target_num:
            start, indent = i, pm.group(1)
            break
    if start is None:
        return None, None
    list_item_re = re.compile(rf"^{re.escape(indent)}- (id|phase):")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if list_item_re.match(lines[j]):
            end = j
            break
    return start, end


def _find_field_indent(lines, start, end, key):
    """Returns (line_index_or_None, indent_string_or_None) for `  <key>:`
    inside [start, end), tolerant of whatever indent depth this
    particular plan file's phase entries actually use."""
    m_re = re.compile(rf"^(\s+){re.escape(key)}:\s*(.*)$")
    for i in range(start, end):
        m = m_re.match(lines[i])
        if m:
            return i, m.group(1)
    return None, None


def block_self_reports_done(lines, start, end):
    idx, _indent = _find_field_indent(lines, start, end, "status")
    status = ""
    if idx is not None:
        status = lines[idx].split(":", 1)[1].strip().strip("'\"").lower()
    if not ("done" in status or "complete" in status or status == "this_task"):
        return False
    block_text = "".join(lines[start:end])
    return bool(TASK_ID_RE.search(block_text))


def yaml_scalar(value):
    """Renders value the same way PyYAML would render it as a mapping
    value, without dumping the surrounding structure (keeps the edit to
    exactly the lines that change)."""
    dumped = yaml.safe_dump({"v": value}, default_flow_style=False, allow_unicode=True)
    return dumped[len("v: "):].rstrip("\n")


def patch_phase_block(lines, start, end, task_id, evidence):
    """Mutates lines in place. Returns True if anything changed. Field
    indent is derived from whichever field this block already has (status,
    falling back to completed_by_task/evidence, falling back to the list
    marker's own indent + 2) -- never hardcoded, since this session's real
    plan files use more than one indent depth for phase entries."""
    changed = False
    status_idx, field_indent = _find_field_indent(lines, start, end, "status")
    completed_idx, completed_indent = _find_field_indent(lines, start, end, "completed_by_task")
    evidence_idx, evidence_indent = _find_field_indent(lines, start, end, "evidence")
    field_indent = field_indent or completed_indent or evidence_indent
    if field_indent is None:
        marker_indent_len = len(lines[start]) - len(lines[start].lstrip(" "))
        field_indent = " " * (marker_indent_len + 2)

    if status_idx is not None:
        current = lines[status_idx].split(":", 1)[1].strip().strip("'\"").lower()
        if not ("done" in current or "complete" in current):
            lines[status_idx] = f"{field_indent}status: done\n"
            changed = True

    insert_at = end
    if completed_idx is not None:
        lines[completed_idx] = f"{field_indent}completed_by_task: {task_id}\n"
    else:
        lines.insert(insert_at, f"{field_indent}completed_by_task: {task_id}\n")
        insert_at += 1
        if evidence_idx is not None and evidence_idx >= insert_at - 1:
            evidence_idx += 1
        changed = True

    evidence_line = f"{field_indent}evidence: {yaml_scalar(evidence)}\n"
    if evidence_idx is not None:
        lines[evidence_idx] = evidence_line
    else:
        lines.insert(insert_at, evidence_line)
        changed = True

    return changed


# ---------------------------------------------------------------------------
# Repo sync + commit/push (direct to master, same place the two real
# hand-backfills this session landed on -- see module docstring)
# ---------------------------------------------------------------------------

def fetch_master():
    run(["git", "-C", REPO_ROOT, "fetch", "origin", "master"])


def read_master_plan_lines(plan_file):
    """Read-only: the committed origin/master copy of ai-os/<plan_file>,
    with zero working-tree mutation. Used as a cheap up-front check so the
    far more expensive/invasive sync_repo_root() (a hard reset of the
    shared REPO_ROOT checkout) only ever runs on the real, rare path where
    a phase actually needs backfilling -- not on every awaiting_human_approval
    task on every 30-minute cron tick, which is the common case once a
    phase already self-reports correctly."""
    proc = run(["git", "-C", REPO_ROOT, "show", f"origin/master:ai-os/{plan_file}"])
    if proc.returncode != 0:
        return None
    return proc.stdout.splitlines(keepends=True)


def sync_repo_root():
    status = run(["git", "-C", REPO_ROOT, "status", "--porcelain"])
    if status.stdout.strip():
        return False, "repo root has uncommitted local changes, refusing to touch it"
    fetch_master()
    reset = run(["git", "-C", REPO_ROOT, "reset", "--hard", "origin/master"])
    if reset.returncode != 0:
        return False, f"git reset --hard origin/master failed: {reset.stderr}"
    return True, None


def commit_and_push(plan_file, phase_id, task_id):
    msg = (f"Auto-backfill {phase_id} self-report -- confirmed merged PR for "
           f"{task_id}, software-written per INS auto-continuation self-report fix "
           f"(no worker/human edit)")
    add = run(["git", "-C", REPO_ROOT, "add", f"ai-os/{plan_file}"])
    if add.returncode != 0:
        return False, f"git add failed: {add.stderr}"
    commit = run(["git", "-C", REPO_ROOT, "commit", "-m", msg])
    if commit.returncode != 0:
        if "nothing to commit" in (commit.stdout + commit.stderr):
            return True, "nothing to commit (already up to date)"
        return False, f"git commit failed: {commit.stderr}"
    push = run(["git", "-C", REPO_ROOT, "push", "origin", "master"])
    if push.returncode != 0:
        return False, f"git push failed: {push.stderr}"
    return True, None


# ---------------------------------------------------------------------------
# Per-task orchestration
# ---------------------------------------------------------------------------

def backfill_one(task_id, task_dir=None, repo_override=None, dry_run=False, checkpoint_on_success=False):
    task_dir = task_dir or os.path.join(TASKS_DIR, task_id)
    result = {"task_id": task_id, "changed": False, "skipped_reason": None, "error": None}

    if not os.path.isdir(task_dir):
        result["error"] = f"no such task dir: {task_dir}"
        return result

    repo = repo_override
    branch = f"worker/{task_id}"
    task_yaml_path = os.path.join(task_dir, "task.yaml")
    if not repo and os.path.isfile(task_yaml_path):
        try:
            with open(task_yaml_path) as f:
                tdoc = yaml.safe_load(f) or {}
            repo = tdoc.get("repo")
            branch = tdoc.get("branch") or branch
        except (OSError, yaml.YAMLError):
            pass
    if not repo:
        result["skipped_reason"] = "could not determine repo (no task.yaml, no --repo-override)"
        return result

    plan_file, phase_id = resolve_phase_ref(task_dir)
    if not plan_file:
        result["skipped_reason"] = "no phase reference found (no phase_plan.yaml sidecar, no match in prompt.txt)"
        return result
    result["plan_file"] = plan_file
    result["phase_id"] = phase_id

    merged, pr_number, merged_at = confirm_merge(task_id, repo, branch=branch)
    if not merged:
        result["skipped_reason"] = f"no confirmed MERGED PR for {branch} on FChecklist/{repo}"
        return result
    result["pr_number"] = pr_number
    result["merged_at"] = merged_at

    fetch_master()
    precheck_lines = read_master_plan_lines(plan_file)
    if precheck_lines is not None:
        pre_start, pre_end = find_phase_block(precheck_lines, phase_id)
        if pre_start is not None and block_self_reports_done(precheck_lines, pre_start, pre_end):
            result["skipped_reason"] = "already self-reports done with an extractable task id -- no change needed"
            return result

    ok, err = sync_repo_root()
    if not ok:
        result["error"] = err
        return result

    plan_path = os.path.join(REPO_ROOT, "ai-os", plan_file)
    if not os.path.isfile(plan_path):
        result["error"] = f"plan file not found at {plan_path}"
        return result
    with open(plan_path) as f:
        lines = f.readlines()

    start, end = find_phase_block(lines, phase_id)
    if start is None:
        result["error"] = f"phase id {phase_id} not found in {plan_file}"
        return result

    if block_self_reports_done(lines, start, end):
        result["skipped_reason"] = "already self-reports done with an extractable task id -- no change needed"
        return result

    evidence = f"{repo} PR #{pr_number} merged {merged_at} (auto-backfilled by backfill_phase_self_report.py)"
    changed = patch_phase_block(lines, start, end, task_id, evidence)
    if not changed:
        result["skipped_reason"] = "no textual change needed"
        return result

    if dry_run:
        result["changed"] = True
        result["dry_run"] = True
        return result

    with open(plan_path, "w") as f:
        f.writelines(lines)

    ok, err = commit_and_push(plan_file, phase_id, task_id)
    if not ok:
        result["error"] = err
        return result
    result["changed"] = True
    result["commit_note"] = err

    if checkpoint_on_success:
        run(["python3", VERIDIAN_TASK, "checkpoint", task_id, "--status", "completed",
             "--note", f"auto-backfilled phase self-report + confirmed merged PR #{pr_number} "
                       f"({repo}); checkpoint updated by backfill_phase_self_report.py --sweep"],
            timeout=30)
        result["checkpointed"] = True

    return result


def sweep(status_filter, dry_run=False, checkpoint_on_success=False):
    results = []
    if not os.path.isdir(TASKS_DIR):
        return results
    for name in sorted(os.listdir(TASKS_DIR)):
        task_dir = os.path.join(TASKS_DIR, name)
        task_yaml_path = os.path.join(task_dir, "task.yaml")
        if not os.path.isfile(task_yaml_path):
            continue
        try:
            with open(task_yaml_path) as f:
                tdoc = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            continue
        status = tdoc.get("status")
        if status_filter and status not in status_filter:
            continue
        r = backfill_one(tdoc.get("id", name), task_dir=task_dir, dry_run=dry_run,
                          checkpoint_on_success=checkpoint_on_success and status == "awaiting_human_approval")
        if r.get("changed") or r.get("error"):
            results.append(r)
            log(f"  {r['task_id']}: changed={r.get('changed')} error={r.get('error')}")
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--task-id")
    p.add_argument("--repo-override")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--sweep", action="store_true",
                    help="Scan every task dir (completed + awaiting_human_approval) for a "
                         "confirmed merged PR whose phase-plan self-report is still missing.")
    p.add_argument("--checkpoint-on-success", action="store_true",
                    help="When --sweep finds a merged awaiting_human_approval (tier2) task, "
                         "also checkpoint it completed -- nothing else ever revisits a tier2 "
                         "task after a human merges its PR out-of-band.")
    args = p.parse_args()

    if args.sweep:
        results = sweep({"completed", "awaiting_human_approval"}, dry_run=args.dry_run,
                         checkpoint_on_success=args.checkpoint_on_success)
        print(json.dumps({"sweep": True, "dry_run": args.dry_run, "results": results}, indent=2, default=str))
        return

    if not args.task_id:
        p.error("--task-id is required unless --sweep is passed")

    result = backfill_one(args.task_id, repo_override=args.repo_override, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, default=str))
    sys.exit(1 if result.get("error") else 0)


if __name__ == "__main__":
    main()
