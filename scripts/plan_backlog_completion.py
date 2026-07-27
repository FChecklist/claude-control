#!/usr/bin/env python3
"""
plan_backlog_completion.py -- real, script-driven completion plan for every
task currently sitting in {failed, blocked, awaiting_human_approval,
pending_review}.

Why this exists (Owner directive): raw ai-os/tasks/*/task.yaml status counts
overstate real remaining work -- repeated "rca-" auto-remediation attempts of
the SAME root issue get counted as separate tasks, and a "blocked" status
frequently just means "PR already open, pending review/merge by the
pipeline" (task itself is DONE). Redispatching those from scratch would be
pure duplication. This script:

  1. Loads every task.yaml under ai-os/tasks/.
  2. Deduplicates repeat attempts of the same underlying issue into one
     representative "issue" (rca-chains, "(redispatch)"/"(round N)" chains).
  3. For each issue currently in a non-terminal state, checks the REAL
     GitHub PR state (not the possibly-stale task.yaml status) for any PR
     referenced in its checkpoints.
  4. Cross-checks wiring_registry (superboss-register.sqlite, kept current
     by generate_wiring_registry.py) for keyword/file overlap, flagging
     candidates that may already be covered by completed work elsewhere.
  5. Classifies each issue into one action category and assigns dispatch
     "waves" (same repo => sequential waves, different repo => parallel,
     capped at dispatch_core.py's real CONCURRENCY_CAP) so the plan can be
     executed in the fewest possible sequential rounds with zero duplicate
     dispatches.
  6. Before ever concluding an issue is ALREADY_DONE_STALE_STATUS, re-runs
     the ORIGINAL task's own SUCCESS_CRITERIA against a fresh checkout of the
     real current default branch -- a PR merging is not proof it satisfied
     THIS issue's objective (2026-07-27 incident: a merged PR referenced in
     an rca-chain's checkpoints turned out to be a content-unrelated fix).
  7. --apply is the ONLY code path in this repo allowed to write
     status=superseded/duplicate_of/superseded_reason into a real task.yaml,
     and only for issues this same run verified via (6). Plan-only (no
     --apply) never touches task.yaml. --audit-report is a separate,
     always-read-only mode that cross-checks existing superseded records
     against a fresh run of this fixed classifier.

Outputs JSON (full detail) + Markdown (human-readable plan) to the given paths.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import sqlite3
import tempfile
from collections import defaultdict

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tight_task_validation import parse_labeled_fields  # noqa: E402  (reuse the one real prompt-field parser)

AI_OS = "/opt/veridian/ai-os"
TASKS_DIR = f"{AI_OS}/tasks"
DB_PATH = f"{AI_OS}/memory/superboss-register.sqlite"
GH_OWNER = "FChecklist"
CONCURRENCY_CAP = 5

TERMINAL_INCOMPLETE = {"failed", "blocked", "awaiting_human_approval", "pending_review"}

ID_RE = re.compile(r'^task-(\d{8})-(\d{6})-(.*)$')
RCA_TARGET_RE = re.compile(r'^rca-task-(\d{8})-(\d{6})-')
PR_REF_RE = re.compile(r'PR\s*#(\d+)', re.IGNORECASE)

GATE_MARKERS = [
    (re.compile(r'AUDIT\s*REJECT', re.I), "audit_reject"),
    (re.compile(r'AUDIT\s*FAIL', re.I), "audit_fail"),
    (re.compile(r'contradiction', re.I), "contradiction_detector"),
    (re.compile(r'crontab_unauthorized_change|crontab.{0,20}drift|crontab.{0,20}stale', re.I), "crontab_drift_gate"),
    (re.compile(r'ddl_authorization|DDL pre-?flight|DDL gate', re.I), "ddl_gate"),
    (re.compile(r'PRE-FLIGHT REJECTED', re.I), "preflight_rejected"),
    (re.compile(r'credit.?accountant|credit_accountant_propose', re.I), "credit_accountant"),
    (re.compile(r'HOLD_FOR_OWNER_SIGNOFF|pending (real )?review/merge|awaiting (real )?review', re.I), "pending_review_merge"),
]


def load_all_tasks():
    tasks = []
    for task_id in sorted(os.listdir(TASKS_DIR)):
        yaml_path = os.path.join(TASKS_DIR, task_id, "task.yaml")
        if not os.path.isfile(yaml_path):
            continue
        try:
            with open(yaml_path) as f:
                d = yaml.safe_load(f) or {}
        except Exception as e:
            d = {"status": f"PARSE_ERROR: {e}"}
        d.setdefault("id", task_id)
        tasks.append(d)
    return tasks


def parse_id_parts(task_id):
    m = ID_RE.match(task_id)
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3)


def rca_target_ts(slug):
    m = RCA_TARGET_RE.match(slug)
    if m:
        return m.group(1) + m.group(2)
    return None


def build_groups(tasks):
    for t in tasks:
        parts = parse_id_parts(t["id"])
        if not parts:
            t["_date"], t["_time"], t["_slug"] = "00000000", "000000", t["id"]
        else:
            t["_date"], t["_time"], t["_slug"] = parts
        ts = rca_target_ts(t["_slug"])
        if ts:
            t["_group_key"] = ("rca_target", ts)
        else:
            t["_group_key"] = ("slug", t["_slug"])

    timestamp_index = {}
    for t in tasks:
        if t["_group_key"][0] == "slug":
            timestamp_index[t["_date"] + t["_time"]] = t["_group_key"]

    key_alias = {}
    for t in tasks:
        gk = t["_group_key"]
        if gk[0] == "rca_target" and gk[1] in timestamp_index:
            key_alias[gk] = timestamp_index[gk[1]]

    def resolve(gk):
        seen = set()
        while gk in key_alias and gk not in seen:
            seen.add(gk)
            gk = key_alias[gk]
        return gk

    groups = defaultdict(list)
    for t in tasks:
        final_key = resolve(t["_group_key"])
        t["_final_group"] = final_key
        groups[final_key].append(t)

    return groups


def steps_text(task):
    parts = []
    for field in ("completed_steps", "remaining_steps"):
        v = task.get(field) or []
        if isinstance(v, list):
            parts.extend(str(x) for x in v)
        elif v:
            parts.append(str(v))
    return "\n".join(parts)


def gh_pr_state(repo, pr_number):
    try:
        out = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--repo", f"{GH_OWNER}/{repo}",
             "--json", "state,mergedAt,mergeable,reviewDecision,url,title"],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode != 0:
            return {"error": out.stderr.strip()[:300]}
        return json.loads(out.stdout)
    except Exception as e:
        return {"error": str(e)}


def wiring_registry_matches(cur, title, limit=5):
    words = [w for w in re.findall(r'[a-zA-Z][a-zA-Z0-9_\-]{3,}', title.lower())
             if w not in {"task", "with", "from", "into", "this", "that", "real",
                           "redispatch", "round", "adopted", "fix", "tier2", "tier1"}]
    if not words:
        return []
    try:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(wiring_registry)").fetchall()]
    except sqlite3.OperationalError:
        return []
    text_cols = [c for c in ("workflow", "documents", "capability_name", "owner") if c in cols]
    if not text_cols:
        return []
    clauses = " OR ".join(f"{c} LIKE ?" for c in text_cols)
    matches = []
    seen_ids = set()
    for w in words[:6]:
        params = [f"%{w}%"] * len(text_cols)
        try:
            rows = cur.execute(
                f"SELECT capability_id, capability_name, workflow, last_verified_ts "
                f"FROM wiring_registry WHERE {clauses} LIMIT 5", params
            ).fetchall()
        except sqlite3.OperationalError:
            continue
        for r in rows:
            if r[0] not in seen_ids:
                seen_ids.add(r[0])
                matches.append({"capability_id": r[0], "capability_name": r[1],
                                 "workflow": r[2], "last_verified_ts": r[3]})
    return matches[:limit]


_BACKTICK_CMD_RE = re.compile(r'`([^`]+)`')
_RUNNABLE_CMD_PREFIXES = ("python3 -m pytest", "pytest ", "grep ")
_CHECKOUT_CACHE = {}


def find_group_original(group):
    """The task whose own SUCCESS_CRITERIA is authoritative for this issue --
    the first REAL attempt (not an "rca-task-..." auto-retry), regardless of
    which attempt is `rep` (latest checkpoint) or which attempt's checkpoint
    prose happens to mention the highest PR number. Falls back to the
    earliest attempt if every member of the group is itself an rca- retry
    (e.g. the true original task.yaml is missing/renamed)."""
    non_rca = [t for t in group if not RCA_TARGET_RE.match(t["_slug"])]
    pool = non_rca or group
    return min(pool, key=lambda t: (t.get("created_at") or "", t["_date"] + t["_time"]))


def load_success_criteria_text(original_task):
    prompt_path = os.path.join(TASKS_DIR, original_task["id"], "prompt.txt")
    if not os.path.isfile(prompt_path):
        return None
    with open(prompt_path) as f:
        text = f.read()
    fields = parse_labeled_fields(text)
    if not fields:
        return None
    return fields.get("successCriteria")


def extract_verifiable_commands(success_criteria_text):
    """Pull out backtick-quoted pytest/grep invocations from a SUCCESS_CRITERIA
    section -- this project's dispatch prompts already write SUCCESS_CRITERIA
    in exactly this style (see task-20260726-083946's prompt.txt). A bullet
    with no backtick command, or backticks around something that isn't a
    pytest/grep call, cannot be mechanically run and is intentionally
    excluded rather than guessed at."""
    if not success_criteria_text:
        return []
    commands = []
    for line in success_criteria_text.splitlines():
        line = line.strip()
        if not line.startswith(("-", "*")):
            continue
        for m in _BACKTICK_CMD_RE.finditer(line):
            cmd = m.group(1).strip()
            if cmd.startswith(_RUNNABLE_CMD_PREFIXES):
                commands.append(cmd)
    return commands


def get_repo_checkout(repo):
    """Fresh, isolated, --depth 1 clone of the repo's real default branch,
    memoized per repo for the lifetime of this process. Never touches any
    existing/shared checkout -- verification must reflect the real current
    default branch, not whatever state a long-lived local clone happens to
    be in. Caller must eventually call cleanup_checkouts()."""
    if repo in _CHECKOUT_CACHE:
        return _CHECKOUT_CACHE[repo]
    tmpdir = tempfile.mkdtemp(prefix="dedup_verify_")
    clone = subprocess.run(
        ["git", "clone", "--depth", "1", "--quiet", f"https://github.com/{GH_OWNER}/{repo}.git", tmpdir],
        capture_output=True, text=True, timeout=120,
    )
    if clone.returncode != 0:
        shutil.rmtree(tmpdir, ignore_errors=True)
        _CHECKOUT_CACHE[repo] = None
        return None
    _CHECKOUT_CACHE[repo] = tmpdir
    return tmpdir


def cleanup_checkouts():
    for path in _CHECKOUT_CACHE.values():
        if path:
            shutil.rmtree(path, ignore_errors=True)
    _CHECKOUT_CACHE.clear()


def verify_success_criteria(repo, commands):
    """Actually run the original task's own mechanically-runnable
    SUCCESS_CRITERIA commands against a fresh checkout of the real current
    default branch (not the group's own checkpoint prose). Commands are
    restricted at extraction time (extract_verifiable_commands) to a
    pytest/grep safelist authored by this project's own trusted dispatch
    prompts -- not arbitrary/external input. Returns (all_passed, details)."""
    if not commands:
        return False, []
    checkout = get_repo_checkout(repo)
    if not checkout:
        return False, [{"command": None, "passed": False, "error": f"could not clone {repo} for verification"}]
    head = subprocess.run(
        ["git", "-C", checkout, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10
    ).stdout.strip()
    details = []
    for cmd in commands:
        try:
            run = subprocess.run(cmd, shell=True, cwd=checkout, capture_output=True, text=True, timeout=180)
            passed = run.returncode == 0
            details.append({
                "command": cmd, "passed": passed, "checked_commit": head,
                "returncode": run.returncode, "stderr_tail": (None if passed else run.stderr[-500:]),
            })
        except Exception as e:
            details.append({"command": cmd, "passed": False, "checked_commit": head, "error": str(e)})
    all_passed = all(d["passed"] for d in details)
    return all_passed, details


def classify(rep, group, db_cur, effective_repo, verify_fn=verify_success_criteria):
    # Search the FULL attempt history for this issue, not just the latest
    # attempt -- blind auto-retry ("rca-") attempts routinely crash with zero
    # progress of their own while an EARLIER attempt in the same chain
    # already opened a real PR; only looking at the latest attempt would
    # wrongly recommend a fresh redispatch of already-done work.
    all_text = "\n".join(steps_text(t) for t in group)
    rep_text = steps_text(rep)
    pr_matches = [int(m) for m in PR_REF_RE.findall(all_text)]
    max_completed = max((len(t.get("completed_steps") or []) for t in group), default=0)
    best_progress_task = max(group, key=lambda t: len(t.get("completed_steps") or []))
    result = {
        "pr_number": None,
        "pr_state": None,
        "gate_markers": [pattern_name for pattern, pattern_name in GATE_MARKERS if pattern.search(all_text)],
        "attempts": len(group),
        "wiring_registry_candidates": [],
        "max_completed_steps_in_history": max_completed,
        "best_progress_attempt_id": best_progress_task["id"] if max_completed else None,
    }

    if pr_matches:
        # PR numbers on GitHub only go up -- if multiple were referenced
        # across attempts (e.g. a closed PR from an early try, then a fresh
        # one from a later try), the highest number is the most recent.
        pr_number = max(pr_matches)
        result["pr_number"] = pr_number
        pr_state = gh_pr_state(effective_repo or rep.get("repo", ""), pr_number)
        result["pr_state"] = pr_state
        if pr_state.get("mergedAt"):
            # A merged PR referenced somewhere in this chain's checkpoint
            # prose is NOT proof it satisfied THIS issue's actual objective
            # -- 2026-07-27 incident: an rca-chain's checkpoint mentioned a
            # real merged PR that turned out to be unrelated work (fixed a
            # different gate entirely). Re-run the ORIGINAL task's own
            # SUCCESS_CRITERIA against the real current default branch before
            # ever concluding "already done".
            original = find_group_original(group)
            success_criteria_text = load_success_criteria_text(original)
            commands = extract_verifiable_commands(success_criteria_text)
            if not commands:
                result["category"] = "CANNOT_AUTO_VERIFY_NEEDS_HUMAN_READ"
                result["action"] = (
                    f"PR #{pr_number} merged, but original task `{original['id']}`'s SUCCESS_CRITERIA is "
                    f"missing or has no mechanically-runnable (pytest/grep) lines -- a merged PR mention "
                    f"alone is not proof this issue's real objective was met. Needs a human to read the "
                    f"original SUCCESS_CRITERIA and the merged PR's real diff before any status change."
                )
                result["success_criteria_verification"] = {
                    "original_task_id": original["id"], "commands": [], "verified": False,
                    "reason": "no mechanically-runnable SUCCESS_CRITERIA found",
                }
            else:
                verified, details = verify_fn(effective_repo or rep.get("repo", ""), commands)
                result["success_criteria_verification"] = {
                    "original_task_id": original["id"], "commands": commands,
                    "verified": verified, "details": details,
                }
                if verified:
                    checked_commit = (details[0].get("checked_commit") if details else None) or "unknown"
                    result["category"] = "ALREADY_DONE_STALE_STATUS"
                    result["action"] = (
                        f"Real PR #{pr_number} merged AND original task `{original['id']}`'s own "
                        f"SUCCESS_CRITERIA independently re-run and passing against the real current "
                        f"default branch (commit {checked_commit}) -- patch task.yaml status to "
                        f"completed, no redispatch."
                    )
                else:
                    result["category"] = "PR_MERGED_BUT_SUCCESS_CRITERIA_UNVERIFIED"
                    result["action"] = (
                        f"PR #{pr_number} merged, but re-running original task `{original['id']}`'s own "
                        f"SUCCESS_CRITERIA against the real current default branch did NOT pass -- the "
                        f"merged PR referenced in this chain's checkpoints does not actually satisfy the "
                        f"original objective (may be unrelated work sharing the same rca-chain lineage). "
                        f"Do not collapse -- needs an Owner/reviewer decision."
                    )
        elif pr_state.get("state") == "OPEN":
            result["category"] = "PR_PENDING_MERGE"
            result["action"] = f"Real work done, PR #{pr_number} open ({pr_state.get('reviewDecision') or 'no review yet'}, mergeable={pr_state.get('mergeable')}). Route through the merge pipeline -- do not redispatch."
        elif pr_state.get("state") == "CLOSED":
            result["category"] = "PR_CLOSED_NEEDS_REDISPATCH"
            result["action"] = f"PR #{pr_number} was closed without merging -- needs fresh redispatch with root-cause fix."
        else:
            result["category"] = "PR_STATE_UNKNOWN_NEEDS_REVIEW"
            result["action"] = f"Could not resolve real state for PR #{pr_number} ({pr_state.get('error','unknown')}) -- manual check needed before deciding."
    elif rep.get("status") in ("awaiting_human_approval", "pending_review"):
        result["category"] = "OWNER_OR_REVIEWER_DECISION_NEEDED"
        result["action"] = "No PR yet -- needs a human/owner decision recorded before this can proceed, not a redispatch."
    elif result["gate_markers"]:
        result["category"] = "GATE_REJECTED_NEEDS_PROMPT_FIX"
        result["action"] = f"Blocked by known gate(s) {result['gate_markers']} with no PR opened -- fix the prompt for that gate, then redispatch once."
    else:
        if max_completed >= 3:
            result["category"] = "SUBSTANTIAL_WORK_NO_PR_NEEDS_REVIEW"
            result["action"] = (f"Real progress recorded in attempt `{result['best_progress_attempt_id']}` "
                                 f"({max_completed} completed steps, no PR opened, no gate marker) -- inspect that "
                                 f"attempt's workspace branch before redispatching; may just need a PR opened, "
                                 f"not fresh work.")
        else:
            result["category"] = "NEEDS_FRESH_REDISPATCH"
            result["action"] = "Crashed early in every attempt, no real progress and no PR anywhere in the chain -- safe to redispatch fresh."

    if result["category"] in ("GATE_REJECTED_NEEDS_PROMPT_FIX", "NEEDS_FRESH_REDISPATCH", "PR_CLOSED_NEEDS_REDISPATCH"):
        result["wiring_registry_candidates"] = wiring_registry_matches(db_cur, rep.get("title", ""))

    return result


def assign_waves(issues):
    """Greedy: within a wave, at most CONCURRENCY_CAP issues and no two issues
    share the same repo (avoids branch/merge collisions observed earlier this
    session with PR79/80/85/89)."""
    needing_dispatch = [i for i in issues if i["classification"]["category"] in
                         ("GATE_REJECTED_NEEDS_PROMPT_FIX", "NEEDS_FRESH_REDISPATCH", "PR_CLOSED_NEEDS_REDISPATCH")]
    waves = []
    remaining = list(needing_dispatch)
    while remaining:
        wave = []
        used_repos = set()
        still = []
        for issue in remaining:
            repo = issue["repo"]
            if len(wave) < CONCURRENCY_CAP and repo not in used_repos:
                wave.append(issue)
                used_repos.add(repo)
            else:
                still.append(issue)
        waves.append(wave)
        remaining = still
    for wave_num, wave in enumerate(waves, start=1):
        for issue in wave:
            issue["wave"] = wave_num
    return waves


def apply_collapse(task_id, duplicate_of, category, evidence, dry_run=True):
    """The ONLY code path in this repo allowed to write
    status=superseded/duplicate_of/superseded_reason into a real task.yaml.
    Root-causes the 2026-07-27 incident directly: 32 real task.yaml files
    were hand-edited outside any code path, citing this tool for a collapse
    decision it never made and never had a mechanism to make. Refuses unless
    category is exactly the verified ALREADY_DONE_STALE_STATUS conclusion
    from THIS run's own classify(), and refuses a missing/empty evidence
    string -- the superseded_reason it writes must always cite the real
    checked commit/PR, never a generic "same underlying issue" claim."""
    if category != "ALREADY_DONE_STALE_STATUS":
        raise ValueError(
            f"refuse to collapse {task_id}: classification category is {category!r}, not the "
            f"SUCCESS_CRITERIA-verified ALREADY_DONE_STALE_STATUS -- only that category is collapse-eligible."
        )
    if not evidence or not evidence.strip():
        raise ValueError(f"refuse to collapse {task_id}: no cited verification evidence given.")
    yaml_path = os.path.join(TASKS_DIR, task_id, "task.yaml")
    with open(yaml_path) as f:
        d = yaml.safe_load(f) or {}
    d["status"] = "superseded"
    d["duplicate_of"] = duplicate_of
    d["superseded_reason"] = (
        f"Collapsed by plan_backlog_completion.py --apply on {datetime.date.today().isoformat()} -- {evidence}"
    )
    if not dry_run:
        with open(yaml_path, "w") as f:
            yaml.safe_dump(d, f, sort_keys=False)
    return d


def run_audit_report(out_path, db_cur):
    """Read-only: cross-check every real task.yaml already marked
    status=superseded with a superseded_reason citing this dedup routine
    against what the FIXED, SUCCESS_CRITERIA-verifying classify() concludes
    when run fresh against current live state (real gh pr view + real
    default-branch re-verification) -- not against a stale plan JSON. Never
    writes to ai-os/tasks/*/task.yaml; only writes the report at out_path."""
    tasks = load_all_tasks()
    groups = build_groups(tasks)  # also sets t["_final_group"] on every task
    task_by_id = {t["id"]: t for t in tasks}

    target_ids = sorted(
        t["id"] for t in tasks
        if t.get("status") == "superseded"
        and "plan_backlog_completion" in (t.get("superseded_reason") or "")
    )
    target_group_keys = {task_by_id[tid]["_final_group"] for tid in target_ids}

    group_result = {}
    for gk in target_group_keys:
        group = groups[gk]
        group_sorted = sorted(group, key=lambda t: (t.get("created_at") or "", t.get("last_checkpoint_at") or ""))
        rep = group_sorted[-1]
        effective_repo = group_sorted[0].get("repo") or rep.get("repo")
        classification = classify(rep, group_sorted, db_cur, effective_repo)
        group_result[gk] = (classification, rep["id"])

    mismatches = []
    for tid in target_ids:
        t = task_by_id[tid]
        classification, rep_id = group_result[t["_final_group"]]
        category = classification["category"]
        if category == "ALREADY_DONE_STALE_STATUS":
            continue
        mismatches.append({
            "task_id": tid,
            "recorded_duplicate_of": t.get("duplicate_of"),
            "recorded_superseded_reason": t.get("superseded_reason"),
            "fresh_classification_category": category,
            "fresh_representative_task_id": rep_id,
            "reason_not_qualified": (
                f"real classifier concludes '{category}', not the verified ALREADY_DONE_STALE_STATUS -- "
                f"{classification.get('action')}"
            ),
        })

    report = {
        "generated_note": (
            "Non-mutating audit: real ai-os/tasks/*/task.yaml records with status=superseded whose "
            "superseded_reason cites plan_backlog_completion.py's dedup routine, cross-checked against "
            "what the FIXED, SUCCESS_CRITERIA-verifying classify() concludes when run fresh against "
            "current live state (real gh pr view + real default-branch re-verification). Read-only: "
            "reads ai-os/tasks/*/task.yaml but never writes to it."
        ),
        "total_superseded_by_this_routine": len(target_ids),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }
    with open(out_path, "w") as f:
        yaml.safe_dump(report, f, sort_keys=False, default_flow_style=False, width=100)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-out", default=f"{AI_OS}/BACKLOG_COMPLETION_PLAN_2026-07-27.json")
    ap.add_argument("--md-out", default=f"{AI_OS}/BACKLOG_COMPLETION_PLAN_2026-07-27.md")
    ap.add_argument("--skip-gh", action="store_true", help="skip live gh pr view calls (faster, less accurate)")
    ap.add_argument("--hours-back", type=float, default=None,
                     help="only include issues whose latest attempt was created within this many hours of now (scopes to the Owner's requested window; omit for full history)")
    ap.add_argument("--apply", action="store_true",
                     help="ACTUALLY WRITE status=superseded/duplicate_of/superseded_reason to real task.yaml "
                          "files, but ONLY for issues this run classified ALREADY_DONE_STALE_STATUS with a "
                          "passing SUCCESS_CRITERIA re-verification. This is the ONLY code path in this repo "
                          "allowed to perform that write. Default is off (plan-only, read-only).")
    ap.add_argument("--apply-only-issue-key", action="append", default=None,
                     help="restrict --apply to specific issue_key(s) (repeatable); omit to apply to every "
                          "verified ALREADY_DONE_STALE_STATUS issue found this run.")
    ap.add_argument("--audit-report", action="store_true",
                     help="read-only mode: cross-check every real task.yaml already marked status=superseded "
                          "with a superseded_reason citing this dedup routine against what this FIXED "
                          "classifier concludes today, and write mismatches to --audit-report-out. Never "
                          "writes to ai-os/tasks/*/task.yaml. Ignores all other flags below.")
    ap.add_argument("--audit-report-out", default=f"{AI_OS}/DEDUP_MISMATCH_MANUAL_REVIEW_2026-07-27.yaml")
    args = ap.parse_args()

    if args.audit_report:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        try:
            report = run_audit_report(args.audit_report_out, cur)
        finally:
            cleanup_checkouts()
        print(json.dumps({
            "total_superseded_by_this_routine": report["total_superseded_by_this_routine"],
            "mismatch_count": report["mismatch_count"],
            "out": args.audit_report_out,
        }, indent=2))
        return

    tasks = load_all_tasks()
    if args.hours_back is not None:
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(hours=args.hours_back)
        def in_window(t):
            ts = t.get("created_at")
            if not ts:
                return True
            try:
                dt = datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            except Exception:
                return True
            return dt >= cutoff
        tasks = [t for t in tasks if in_window(t)]
    groups = build_groups(tasks)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    issues = []
    total_raw_incomplete = 0
    for group_key, group in groups.items():
        group_sorted = sorted(group, key=lambda t: (t.get("created_at") or "", t.get("last_checkpoint_at") or ""))
        rep = group_sorted[-1]
        # The repo field on later blind-retry ("rca-") attempts has been
        # observed wrong/misassigned relative to the real issue (e.g. an
        # earlier attempt correctly shows compliance-tracker, a later rca-
        # retry of the exact same issue shows claude-control). The FIRST
        # attempt in the chain is the one that was actually scoped by a
        # human/owner-reviewed dispatch, so trust its repo field over later
        # auto-retries when they disagree.
        repos_seen = [t.get("repo") for t in group_sorted if t.get("repo")]
        effective_repo = group_sorted[0].get("repo") or rep.get("repo")
        statuses_in_group = [t.get("status") for t in group_sorted]
        raw_incomplete_in_group = sum(1 for s in statuses_in_group if s in TERMINAL_INCOMPLETE)
        total_raw_incomplete += raw_incomplete_in_group
        if rep.get("status") not in TERMINAL_INCOMPLETE:
            continue
        if args.skip_gh:
            classification = {"category": "SKIPPED_GH_CHECK", "action": "gh check skipped", "attempts": len(group), "gate_markers": [], "wiring_registry_candidates": []}
        else:
            classification = classify(rep, group_sorted, cur, effective_repo)
        issues.append({
            "issue_key": f"{group_key[0]}:{group_key[1]}",
            "representative_task_id": rep["id"],
            "all_attempt_ids": [t["id"] for t in group_sorted],
            "attempts": len(group_sorted),
            "raw_incomplete_attempts_in_group": raw_incomplete_in_group,
            "repos_disagree_across_attempts": len(set(repos_seen)) > 1,
            "title": rep.get("title") or group_sorted[0].get("title"),
            "repo": effective_repo,
            "status": rep.get("status"),
            "created_at": group_sorted[0].get("created_at"),
            "last_checkpoint_at": rep.get("last_checkpoint_at"),
            "classification": classification,
        })

    waves = assign_waves(issues)

    category_counts = defaultdict(int)
    for i in issues:
        category_counts[i["classification"]["category"]] += 1

    summary = {
        "generated_note": "Real data pulled from ai-os/tasks/*/task.yaml + live gh pr view + wiring_registry on VERIDIAN-DEV.",
        "raw_incomplete_task_rows": total_raw_incomplete,
        "distinct_issues_after_dedup": len(issues),
        "duplication_collapsed": total_raw_incomplete - len(issues),
        "category_counts": dict(category_counts),
        "total_waves_needed": len(waves),
        "concurrency_cap_per_wave": CONCURRENCY_CAP,
    }

    out = {"summary": summary, "issues": sorted(issues, key=lambda i: (i.get("wave") or 0, i["repo"] or "", i["representative_task_id"]))}

    with open(args.json_out, "w") as f:
        json.dump(out, f, indent=2, default=str)

    # Markdown
    lines = []
    lines.append("# VERIDIAN Backlog Completion Plan -- 2026-07-27")
    lines.append("")
    lines.append(f"Raw incomplete task rows (failed/blocked/awaiting/pending_review): **{total_raw_incomplete}**")
    lines.append(f"Distinct real issues after dedup: **{len(issues)}** (collapsed **{summary['duplication_collapsed']}** duplicate re-attempts)")
    lines.append("")
    lines.append("## By category")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- **{cat}**: {count}")
    lines.append("")
    lines.append(f"## Dispatch waves needed for genuine redispatches: {len(waves)} (cap {CONCURRENCY_CAP}/wave, one repo per wave-slot)")
    lines.append("")
    for i in out["issues"]:
        c = i["classification"]
        lines.append(f"### [{c['category']}] {i['title']}")
        lines.append(f"- issue_key: `{i['issue_key']}`")
        lines.append(f"- representative: `{i['representative_task_id']}` (repo: {i['repo']}, attempts collapsed: {i['attempts']})")
        lines.append(f"- action: {c['action']}")
        if i.get("wave"):
            lines.append(f"- wave: {i['wave']}")
        if c.get("wiring_registry_candidates"):
            lines.append(f"- possible existing coverage: {[m['capability_name'] for m in c['wiring_registry_candidates']]}")
        lines.append("")

    with open(args.md_out, "w") as f:
        f.write("\n".join(lines))

    applied_count = 0
    if args.apply:
        for issue in issues:
            c = issue["classification"]
            if c.get("category") != "ALREADY_DONE_STALE_STATUS":
                continue
            verification = c.get("success_criteria_verification") or {}
            if not verification.get("verified"):
                continue
            if args.apply_only_issue_key and issue["issue_key"] not in args.apply_only_issue_key:
                continue
            details = verification.get("details") or []
            checked_commit = details[0].get("checked_commit") if details else "unknown"
            evidence = (
                f"PR #{c.get('pr_number')} merged; original task `{verification.get('original_task_id')}`'s "
                f"SUCCESS_CRITERIA ({len(verification.get('commands') or [])} command(s)) independently "
                f"re-run and passing at commit {checked_commit}."
            )
            rep_id = issue["representative_task_id"]
            for attempt_id in issue["all_attempt_ids"]:
                if attempt_id == rep_id:
                    continue
                apply_collapse(attempt_id, rep_id, c["category"], evidence, dry_run=False)
                applied_count += 1
        print(f"--apply: wrote real collapse to {applied_count} task.yaml file(s).", file=sys.stderr)

    cleanup_checkouts()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
