#!/usr/bin/env python3
"""Real, cron-driven status monitor. Closes the gap named in this task's own SPEC:
"status" today means an AI/Owner manually running gh/task.yaml checks by hand, not
reading real software output. This script IS that software: it scans the real,
existing data sources every other engine on this server already produces (task.yaml
files under ai-os/tasks/*, open PRs across the 3 tracked repos via `gh`, each PR's
real audit comments, and auto_phase_continuation.py's own --dry-run output) and
writes ONE structured, current status artifact this assistant (or anything else)
can read instead of re-deriving status from scratch every time it's asked.

Overwrites ai-os/LIVE_STATUS_2026-07-26.yaml every run -- this is a live snapshot,
not an append log (same convention as veridian_self_check.py's PASS/FAIL run, not
an accumulating history). The "remediation:" section is intentionally left
untouched by this script if already populated -- scripts/veridian_remediation_dispatcher.py
reads this file's findings and writes its own actions back into that one section,
never re-computing or duplicating the scan this script already did.

No AI/LLM calls anywhere in this run path (matches the Owner's "audit run by
software, not AI" mandate, same posture as audit_pipeline_security.py).
"""
import json
import os
import re
import subprocess
import sys
import datetime

AI_OS = "/opt/veridian/ai-os"
SCRIPTS = "/opt/veridian/scripts"
TASKS_DIR = f"{AI_OS}/tasks"
OUTPUT_PATH = f"{AI_OS}/LIVE_STATUS_2026-07-26.yaml"
AUTO_PHASE_CONTINUATION = f"{SCRIPTS}/auto_phase_continuation.py"

GH_OWNER = "FChecklist"
TRACKED_REPOS = ["claude-control", "compliance-tracker", "projexa"]

# A "live" snapshot means recently-relevant, not the full multi-week backlog --
# real data confirms 244 of 405 real task.yaml files are status=blocked, the vast
# majority weeks-old and already superseded by retries. Only tasks blocked within
# this window are surfaced as actionable; older ones are real history, not live status.
BLOCKED_LOOKBACK_HOURS = 24

PR_URL_RE = re.compile(r"(https://github\.com/\S+/pull/\d+)")


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def parse_ts(ts):
    if not ts:
        return None
    try:
        return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def human_elapsed(delta):
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        total_seconds = 0
    hours, rem = divmod(total_seconds, 3600)
    minutes, _ = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes}m"
    return f"{minutes}m"


def run(cmd, timeout=30):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        return 124, "", str(e)
    except FileNotFoundError as e:
        return 127, "", str(e)


def run_json(cmd, timeout=30):
    code, out, err = run(cmd, timeout=timeout)
    if code != 0:
        return None, f"exit {code}: {err.strip()[:300]}"
    try:
        return json.loads(out), None
    except json.JSONDecodeError as e:
        return None, f"bad json: {e}"


# ---------------------------------------------------------------------------
# task.yaml scan
# ---------------------------------------------------------------------------

def scan_tasks(errors):
    in_progress = []
    blocked_recent = []
    if not os.path.isdir(TASKS_DIR):
        errors.append(f"TASKS_DIR missing: {TASKS_DIR}")
        return in_progress, blocked_recent

    import yaml
    cutoff = now_utc() - datetime.timedelta(hours=BLOCKED_LOOKBACK_HOURS)

    for entry in sorted(os.listdir(TASKS_DIR)):
        task_yaml_path = os.path.join(TASKS_DIR, entry, "task.yaml")
        if not os.path.isfile(task_yaml_path):
            continue
        try:
            task = yaml.safe_load(open(task_yaml_path)) or {}
        except Exception as e:
            errors.append(f"unreadable task.yaml {entry}: {e}")
            continue

        status = task.get("status")
        task_id = task.get("id") or entry
        checkpoints = task.get("checkpoints") or []
        last_checkpoint = checkpoints[-1] if checkpoints else {}

        if status == "in_progress":
            created_at = parse_ts(task.get("created_at"))
            started_at = created_at or parse_ts(task.get("last_checkpoint_at"))
            elapsed = (now_utc() - started_at) if started_at else None
            in_progress.append({
                "task_id": task_id,
                "title": task.get("title"),
                "repo": task.get("repo"),
                "created_at": task.get("created_at"),
                "elapsed_seconds": int(elapsed.total_seconds()) if elapsed else None,
                "elapsed_human": human_elapsed(elapsed) if elapsed else "unknown",
                "workspace": task.get("workspace"),
            })

        elif status == "blocked":
            last_ts = parse_ts(task.get("last_checkpoint_at"))
            if last_ts is None or last_ts < cutoff:
                continue
            note = last_checkpoint.get("note") or task.get("status_reason") or ""
            pr_match = PR_URL_RE.search(note)
            review_verdict = None
            review_summary = None
            review_issues = []
            review_path = os.path.join(TASKS_DIR, entry, "review.json")
            if os.path.isfile(review_path):
                try:
                    review = json.load(open(review_path))
                    review_verdict = review.get("verdict")
                    review_summary = review.get("summary")
                    review_issues = review.get("issues") or []
                except Exception as e:
                    errors.append(f"unreadable review.json {entry}: {e}")

            blocked_recent.append({
                "task_id": task_id,
                "repo": task.get("repo"),
                "blocked_since": task.get("last_checkpoint_at"),
                "reason": note,
                "pr_url": pr_match.group(1) if pr_match else None,
                "review_verdict": review_verdict,
                "review_summary": review_summary,
                "review_issues": review_issues,
            })

    return in_progress, blocked_recent


# ---------------------------------------------------------------------------
# PR scan (audit-fail + merge-conflict)
# ---------------------------------------------------------------------------

def scan_prs(errors):
    audit_fail_unfixed = []
    merge_conflict = []

    for repo in TRACKED_REPOS:
        prs, err = run_json([
            "gh", "pr", "list", "--repo", f"{GH_OWNER}/{repo}", "--state", "open",
            "--json", "number,title,url,mergeStateStatus,updatedAt,headRefOid,headRefName",
        ])
        if prs is None:
            errors.append(f"gh pr list failed for {repo}: {err}")
            continue

        for pr in prs:
            number = pr["number"]
            url = pr["url"]

            if pr.get("mergeStateStatus") == "DIRTY":
                merge_conflict.append({
                    "repo": repo,
                    "number": number,
                    "url": url,
                    "title": pr.get("title"),
                    "merge_state_status": "DIRTY",
                    "updated_at": pr.get("updatedAt"),
                    "head_ref_name": pr.get("headRefName"),
                    "head_ref_oid": pr.get("headRefOid"),
                })

            comments, cerr = run_json([
                "gh", "api", f"repos/{GH_OWNER}/{repo}/issues/{number}/comments",
                "--jq", "[.[] | {created_at, body}]",
            ])
            if comments is None:
                errors.append(f"gh api comments failed for {repo}#{number}: {cerr}")
                continue

            audit_comments = [c for c in comments if (c.get("body") or "").startswith("AUDIT:")]
            if not audit_comments:
                continue
            audit_comments.sort(key=lambda c: c.get("created_at") or "")
            latest_audit = audit_comments[-1]
            if not (latest_audit.get("body") or "").startswith("AUDIT: FAIL"):
                continue  # most recent structured verdict is PASS -- not currently failing

            fail_ts = parse_ts(latest_audit.get("created_at"))

            commits_info, comerr = run_json([
                "gh", "pr", "view", str(number), "--repo", f"{GH_OWNER}/{repo}",
                "--json", "commits",
            ])
            last_commit_ts = None
            if commits_info and commits_info.get("commits"):
                last_commit_ts = parse_ts(commits_info["commits"][-1].get("committedDate"))
            elif comerr:
                errors.append(f"gh pr view commits failed for {repo}#{number}: {comerr}")

            corrective_commit_since = bool(
                last_commit_ts and fail_ts and last_commit_ts > fail_ts
            )
            if corrective_commit_since:
                continue

            checks, cherr = run_json([
                "gh", "pr", "view", str(number), "--repo", f"{GH_OWNER}/{repo}",
                "--json", "statusCheckRollup",
            ])
            check_runs = (checks or {}).get("statusCheckRollup") or []

            audit_fail_unfixed.append({
                "repo": repo,
                "number": number,
                "url": url,
                "title": pr.get("title"),
                "head_ref_name": pr.get("headRefName"),
                "head_ref_oid": pr.get("headRefOid"),
                "audit_fail_comment_at": latest_audit.get("created_at"),
                "audit_fail_excerpt": (latest_audit.get("body") or "")[:1200],
                "last_commit_at": commits_info["commits"][-1].get("committedDate")
                if commits_info and commits_info.get("commits") else None,
                "check_runs": [
                    {"name": c.get("name"), "conclusion": c.get("conclusion"),
                     "startedAt": c.get("startedAt"), "completedAt": c.get("completedAt")}
                    for c in check_runs if c.get("name")
                ],
            })

    return audit_fail_unfixed, merge_conflict


# ---------------------------------------------------------------------------
# auto_phase_continuation.py --dry-run
# ---------------------------------------------------------------------------

def scan_phases_ready(errors):
    if not os.path.isfile(AUTO_PHASE_CONTINUATION):
        errors.append(f"auto_phase_continuation.py missing at {AUTO_PHASE_CONTINUATION}")
        return []

    code, out, err = run(["python3", AUTO_PHASE_CONTINUATION, "--dry-run"], timeout=90)
    if code != 0:
        errors.append(f"auto_phase_continuation.py --dry-run exit {code}: {err.strip()[:300]}")
        return []
    try:
        result = json.loads(out)
    except json.JSONDecodeError as e:
        errors.append(f"auto_phase_continuation.py --dry-run bad json: {e}")
        return []

    ready = []
    for entry in result.get("initiatives") or []:
        if entry.get("would_dispatch") and not entry.get("already_dispatched"):
            ready.append({
                "initiative": entry.get("initiative") if "initiative" in entry else entry.get("name"),
                "next_phase": entry.get("next_phase"),
                "generated_title": entry.get("generated_title"),
            })
    return ready


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import yaml

    errors = []
    in_progress, blocked_recent = scan_tasks(errors)
    audit_fail_unfixed, merge_conflict = scan_prs(errors)
    phases_ready = scan_phases_ready(errors)

    existing_remediation = {"last_run_at": None, "auto_dispatched": [], "drafted_pending_review": []}
    if os.path.isfile(OUTPUT_PATH):
        try:
            prior = yaml.safe_load(open(OUTPUT_PATH)) or {}
            if isinstance(prior.get("remediation"), dict):
                existing_remediation = prior["remediation"]
        except Exception:
            pass  # a corrupt/foreign prior file must never block a fresh, real overwrite

    artifact = {
        "generated_at": now_utc().isoformat(),
        "generator": "scripts/veridian_status_monitor.py",
        "tracked_repos": [f"{GH_OWNER}/{r}" for r in TRACKED_REPOS],
        "blocked_lookback_hours": BLOCKED_LOOKBACK_HOURS,
        "tasks_in_progress": in_progress,
        "tasks_blocked_recent": blocked_recent,
        "prs_audit_fail_unfixed": audit_fail_unfixed,
        "prs_merge_conflict": merge_conflict,
        "phases_ready_to_advance": phases_ready,
        "scan_errors": errors,
        "remediation": existing_remediation,
    }

    tmp_path = OUTPUT_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        yaml.safe_dump(artifact, f, sort_keys=False, default_flow_style=False, width=100)
    os.replace(tmp_path, OUTPUT_PATH)

    summary = {
        "written_to": OUTPUT_PATH,
        "tasks_in_progress": len(in_progress),
        "tasks_blocked_recent": len(blocked_recent),
        "prs_audit_fail_unfixed": len(audit_fail_unfixed),
        "prs_merge_conflict": len(merge_conflict),
        "phases_ready_to_advance": len(phases_ready),
        "scan_errors": len(errors),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
