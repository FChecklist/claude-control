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

Outputs JSON (full detail) + Markdown (human-readable plan) to the given paths.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import sqlite3
from collections import defaultdict

import yaml

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


def classify(rep, group, db_cur, effective_repo):
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
            result["category"] = "ALREADY_DONE_STALE_STATUS"
            result["action"] = f"Real PR #{pr_number} already merged -- patch task.yaml status to completed, no redispatch."
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-out", default=f"{AI_OS}/BACKLOG_COMPLETION_PLAN_2026-07-27.json")
    ap.add_argument("--md-out", default=f"{AI_OS}/BACKLOG_COMPLETION_PLAN_2026-07-27.md")
    ap.add_argument("--skip-gh", action="store_true", help="skip live gh pr view calls (faster, less accurate)")
    ap.add_argument("--hours-back", type=float, default=None,
                     help="only include issues whose latest attempt was created within this many hours of now (scopes to the Owner's requested window; omit for full history)")
    args = ap.parse_args()

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

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
