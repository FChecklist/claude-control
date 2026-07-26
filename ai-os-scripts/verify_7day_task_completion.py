#!/usr/bin/env python3
"""Real, automated verification of ai-os/tasks/ completion claims.

Cross-references every task-*/task.yaml created in the last N days against
independently-verifiable outcomes -- real PR state via `gh pr list` (not
`gh pr view` in a per-task loop -- one paginated list call per repo covers
every PR at once) and, where no PR evidence exists, real commit ancestry on
the repo's actual default branch. Never trusts task.yaml's own self-reported
`status` field as the final answer: that field is recorded as `recorded_status`
for comparison only.

Usage:
  python3 verify_7day_task_completion.py --count-only
  python3 verify_7day_task_completion.py --out-md ai-os/TASK_COMPLETION_AUDIT_2026-07-26.md \
      --out-json ai-os/TASK_COMPLETION_AUDIT_2026-07-26.json
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent
TASKS_ROOT_DEFAULT = "/opt/veridian/ai-os/tasks"
REPOS_ROOT_DEFAULT = "/opt/veridian/repos"
GITHUB_ORG_DEFAULT = "FChecklist"
LIVE_AI_OS_DEFAULT = "/opt/veridian/ai-os"

PR_URL_RE = re.compile(r"github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)")
TITLE_PR_RE = re.compile(r"\bPR\s*#?\s*(\d{2,5})\b", re.IGNORECASE)
PHASE_NUM_RE = re.compile(r"phase\s*[-_]?\s*(\d+)")

PHASE_PLAN_FILES = {
    "20_ENGINES_10_GATEWAYS_PHASE_PLAN_2026-07-24.yaml": [
        "20 engine", "20-engine", "10 gateway", "gateways"
    ],
    "WIRING_ENGINE_PHASE_PLAN_2026-07-25.yaml": [
        "wiring engine", "wiring_engine", "wiring-engine"
    ],
    "AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml": [
        "auditor engine", "auditor_engine", "auditor-engine"
    ],
    "TESTING_ENGINE_PHASE_PLAN_2026-07-24.yaml": [
        "testing engine", "testing_engine", "testing-engine"
    ],
    "TERMINOLOGY_STANDARDIZATION_PHASE_PLAN_2026-07-24.yaml": [
        "terminology standardization", "terminology_standardization", "terminology-standardization"
    ],
    "VERIDIAN_ARCHITECTURE_V2_PHASE_PLAN_2026-07-25.yaml": [
        "architecture v2", "architecture-v2", "veridian architecture v2", "archv2"
    ],
}

TERMINAL_TOP_STATUSES = {"completed"}
LOG_FILENAMES = ["worker.log", "supervisor.log", "supervisor-systemd.log", "systemd.log"]


def run(cmd, timeout=60):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return 1, "", str(e)


def normalize(s):
    return re.sub(r"[-_]+", " ", (s or "").lower())


def load_phase_plans(live_ai_os, repo_ai_os):
    """Load the 6 named phase-plan files, preferring live runtime state over
    the (potentially stale) git-tracked snapshot committed in this repo."""
    plans = {}
    for fname in PHASE_PLAN_FILES:
        for candidate in (Path(live_ai_os) / fname, repo_ai_os / fname):
            if candidate.exists():
                try:
                    plans[fname] = yaml.safe_load(candidate.read_text())
                except Exception:
                    plans[fname] = None
                break
        else:
            plans[fname] = None
    return plans


def phase_plan_cross_ref(title, plans):
    norm_title = normalize(title)
    m = PHASE_NUM_RE.search(norm_title)
    if not m:
        return None
    phase_num = m.group(1)
    for fname, keywords in PHASE_PLAN_FILES.items():
        if not any(kw in norm_title for kw in keywords):
            continue
        plan = plans.get(fname)
        if not plan or not isinstance(plan.get("phases"), list):
            continue
        for phase in plan["phases"]:
            pid = str(phase.get("id", ""))
            if re.match(rf"phase[_-]?0*{phase_num}(?!\d)", pid):
                return f"{fname}#{pid} status={phase.get('status')}"
    return None


def collect_tasks(tasks_root, cutoff):
    tasks = []
    omitted = []
    for task_dir in sorted(Path(tasks_root).glob("task-*")):
        yaml_path = task_dir / "task.yaml"
        if not yaml_path.exists():
            omitted.append((task_dir.name, "no task.yaml"))
            continue
        try:
            data = yaml.safe_load(yaml_path.read_text())
        except Exception as e:
            omitted.append((task_dir.name, f"unparseable task.yaml: {e}"))
            continue
        if not data:
            omitted.append((task_dir.name, "empty task.yaml"))
            continue
        created_raw = data.get("created_at")
        try:
            created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        except Exception:
            omitted.append((task_dir.name, f"unparseable created_at: {created_raw!r}"))
            continue
        if created < cutoff:
            continue
        tasks.append((task_dir, data, created))
    return tasks, omitted


def find_pr_in_logs(task_dir):
    matches = []
    for fname in LOG_FILENAMES:
        p = task_dir / fname
        if not p.exists():
            continue
        try:
            text = p.read_text(errors="replace")
        except Exception:
            continue
        matches.extend(PR_URL_RE.findall(text))
    if not matches:
        return None
    # last occurrence across log files = most likely the final/authoritative one
    org, repo, num = matches[-1]
    return org, repo, int(num)


def gh_pr_list(repo_full, timeout=120):
    code, out, err = run(
        [
            "gh", "pr", "list", "--repo", repo_full, "--state", "all",
            "--json", "number,state,mergedAt,headRefName,baseRefName,title,url",
            "-L", "2000",
        ],
        timeout=timeout,
    )
    if code != 0:
        print(f"WARN: gh pr list failed for {repo_full}: {err.strip()}", file=sys.stderr)
        return {}, {}
    try:
        prs = json.loads(out)
    except Exception as e:
        print(f"WARN: could not parse gh pr list output for {repo_full}: {e}", file=sys.stderr)
        return {}, {}
    by_number = {pr["number"]: pr for pr in prs}
    by_headref = {}
    for pr in prs:
        by_headref.setdefault(pr.get("headRefName"), pr)
    return by_number, by_headref


def gh_default_branch(repo_full):
    code, out, err = run(["gh", "repo", "view", repo_full, "--json", "defaultBranchRef", "-q", ".defaultBranchRef.name"])
    if code != 0 or not out.strip():
        return None
    return out.strip()


def git_commit_ancestry_check(repo_local_path, default_branch, task_id, do_fetch):
    if not repo_local_path.exists():
        return None
    if do_fetch:
        run(["git", "-C", str(repo_local_path), "fetch", "origin", default_branch, "--quiet"], timeout=90)
    ref = f"origin/{default_branch}"
    code, out, err = run(
        ["git", "-C", str(repo_local_path), "log", ref, "--oneline", f"--grep={task_id}", "-i", "-n", "3"],
        timeout=60,
    )
    if code != 0 or not out.strip():
        return None
    first_line = out.strip().splitlines()[0]
    return first_line


def verify_task(task_dir, data, org, repos_root, live_ai_os, repo_ai_os_root, phase_plans,
                 prs_cache, headref_cache, default_branch_cache, do_fetch, no_gh):
    task_id = data.get("id", task_dir.name)
    title = data.get("title", "")
    recorded_status = data.get("status", "unknown")
    repo_name = data.get("repo", "")
    branch = data.get("branch", "")
    checkpoints = data.get("checkpoints") or []

    evidence = {
        "method": None,
        "pr_repo": None,
        "pr_number": None,
        "pr_url": None,
        "pr_state": None,
        "pr_merged_at": None,
        "title_target_pr_number": None,
        "title_target_pr_state": None,
        "title_target_pr_mismatch": False,
        "commit_grep_hit": None,
        "phase_plan_ref": None,
    }
    evidence["phase_plan_ref"] = phase_plan_cross_ref(title, phase_plans)

    # --- Step 1: locate the task's own recorded/implied PR ---
    pr_org, pr_repo, pr_num, method = None, None, None, None

    pr_url_path = task_dir / "pr_url.txt"
    if pr_url_path.exists():
        raw = pr_url_path.read_text().strip()
        m = PR_URL_RE.search(raw)
        if m:
            pr_org, pr_repo, pr_num = m.group(1), m.group(2), int(m.group(3))
            method = "pr_url.txt"

    if pr_num is None:
        found = find_pr_in_logs(task_dir)
        if found:
            pr_org, pr_repo, pr_num = found
            method = "grepped from worker/supervisor log"

    repo_full = f"{pr_org}/{pr_repo}" if pr_org and pr_repo else (f"{org}/{repo_name}" if repo_name else None)

    # gh pr list --headRefName fallback if still no direct PR reference
    if pr_num is None and repo_full and branch and not no_gh:
        if repo_full not in headref_cache:
            prs_cache[repo_full], headref_cache[repo_full] = gh_pr_list(repo_full)
        hr = headref_cache.get(repo_full, {})
        if branch in hr:
            pr_num = hr[branch]["number"]
            method = "matched via gh pr list headRefName == task branch"

    # --- Step 2: title-referenced target PR (for mismatch detection) ---
    m = TITLE_PR_RE.search(title)
    if m:
        evidence["title_target_pr_number"] = int(m.group(1))

    # --- Step 3: resolve PR state via cached gh pr list per repo ---
    pr_data = None
    if pr_num is not None and repo_full and not no_gh:
        if repo_full not in prs_cache:
            prs_cache[repo_full], headref_cache[repo_full] = gh_pr_list(repo_full)
        pr_data = prs_cache.get(repo_full, {}).get(pr_num)

    if evidence["title_target_pr_number"] is not None and repo_full and not no_gh:
        if repo_full not in prs_cache:
            prs_cache[repo_full], headref_cache[repo_full] = gh_pr_list(repo_full)
        target_data = prs_cache.get(repo_full, {}).get(evidence["title_target_pr_number"])
        if target_data:
            evidence["title_target_pr_state"] = target_data.get("state")
        if evidence["title_target_pr_number"] != pr_num:
            evidence["title_target_pr_mismatch"] = True

    if pr_num is not None:
        evidence["method"] = method
        evidence["pr_repo"] = repo_full
        evidence["pr_number"] = pr_num
        evidence["pr_url"] = pr_data.get("url") if pr_data else f"https://github.com/{repo_full}/pull/{pr_num}"
        evidence["pr_state"] = pr_data.get("state") if pr_data else "UNKNOWN (gh lookup failed or PR not found)"
        evidence["pr_merged_at"] = pr_data.get("mergedAt") if pr_data else None

        if pr_data is None:
            real_status = "NO_PR_FOUND"
            reason = (f"task.yaml/logs reference PR #{pr_num} in {repo_full}, but it was not found via "
                      f"`gh pr list --repo {repo_full} --state all` -- could not independently confirm.")
        elif pr_data.get("state") == "MERGED":
            real_status = "MERGED"
            reason = (f"PR #{pr_num} ({evidence['pr_url']}) is MERGED (mergedAt={pr_data.get('mergedAt')}), "
                      f"confirmed via `gh pr list --repo {repo_full}` (source: {method}).")
        elif pr_data.get("state") == "CLOSED":
            real_status = "OPEN_NOT_DONE"
            reason = (f"PR #{pr_num} ({evidence['pr_url']}) was CLOSED WITHOUT MERGING -- "
                      f"task.yaml recorded status={recorded_status!r} but the real PR state is not merged.")
        else:  # OPEN
            real_status = "OPEN_NOT_DONE"
            reason = (f"PR #{pr_num} ({evidence['pr_url']}) is still OPEN -- "
                      f"task.yaml recorded status={recorded_status!r} but the real PR is not merged.")

        if evidence["title_target_pr_mismatch"]:
            tnum = evidence["title_target_pr_number"]
            tstate = evidence["title_target_pr_state"] or "unknown (not found via gh)"
            reason += (f" WARNING: task title references PR #{tnum}, a DIFFERENT PR than the one actually "
                       f"delivered (#{pr_num}) -- PR #{tnum}'s real state is {tstate}, not resolved by this task.")
        return real_status, reason, evidence

    # --- Step 4: no PR evidence anywhere -- try real commit ancestry on default branch ---
    if repo_name and not no_gh:
        repo_full2 = f"{org}/{repo_name}"
        if repo_full2 not in default_branch_cache:
            default_branch_cache[repo_full2] = gh_default_branch(repo_full2)
        default_branch = default_branch_cache[repo_full2]
        if default_branch:
            local_path = Path(repos_root) / repo_name
            hit = git_commit_ancestry_check(local_path, default_branch, data.get("id", task_dir.name), do_fetch)
            if hit:
                evidence["method"] = "git log origin/<default-branch> --grep=<task_id>"
                evidence["commit_grep_hit"] = hit
                return ("MERGED",
                        f"No PR reference found, but a commit citing this task ID is reachable from "
                        f"origin/{default_branch} of {repo_full2}: `{hit}` (confirmed via local clone at {local_path}).",
                        evidence)

    # --- Step 5: no code deliverable evidence at all -- fall back to genuine checkpoint terminal state ---
    last_cp_status = checkpoints[-1].get("status") if checkpoints else None
    last_cp_note = (checkpoints[-1].get("note") or "").strip() if checkpoints else ""
    if recorded_status in TERMINAL_TOP_STATUSES and last_cp_status in ("completed", "pending_review") and len(checkpoints) >= 2:
        return ("INVESTIGATION_ONLY",
                f"No PR or commit deliverable found anywhere (pr_url.txt, logs, gh headRefName match, or default-branch "
                f"commit grep). Treated as a non-code investigation/analysis task: task.yaml shows {len(checkpoints)} "
                f"checkpoints reaching terminal status={last_cp_status!r} (last note: {last_cp_note[:200]!r}).",
                evidence)

    return ("NO_PR_FOUND",
            f"No PR or commit deliverable found anywhere, and checkpoint history does not show a genuine terminal "
            f"completion (recorded top-level status={recorded_status!r}, last checkpoint status={last_cp_status!r} "
            f"across {len(checkpoints)} checkpoints) -- cannot independently confirm completion.",
            evidence)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tasks-root", default=TASKS_ROOT_DEFAULT)
    ap.add_argument("--repos-root", default=REPOS_ROOT_DEFAULT)
    ap.add_argument("--live-ai-os", default=LIVE_AI_OS_DEFAULT)
    ap.add_argument("--github-org", default=GITHUB_ORG_DEFAULT)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--count-only", action="store_true")
    ap.add_argument("--out-md")
    ap.add_argument("--out-json")
    ap.add_argument("--no-fetch", action="store_true", help="skip `git fetch` before commit-ancestry checks")
    ap.add_argument("--no-gh", action="store_true", help="skip all gh calls (offline/testing)")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=args.days)

    tasks, omitted = collect_tasks(args.tasks_root, cutoff)

    if args.count_only:
        print(len(tasks))
        if omitted:
            print(f"(omitted {len(omitted)} task dirs -- unparseable/missing task.yaml, see stderr)", file=sys.stderr)
            for name, why in omitted:
                print(f"  OMITTED {name}: {why}", file=sys.stderr)
        return

    repo_ai_os_root = REPO_ROOT / "ai-os"
    phase_plans = load_phase_plans(args.live_ai_os, repo_ai_os_root)

    prs_cache, headref_cache, default_branch_cache = {}, {}, {}

    rows = []
    for task_dir, data, created in tasks:
        real_status, reason, evidence = verify_task(
            task_dir, data, args.github_org, args.repos_root, args.live_ai_os,
            repo_ai_os_root, phase_plans, prs_cache, headref_cache, default_branch_cache,
            do_fetch=not args.no_fetch, no_gh=args.no_gh,
        )
        rows.append({
            "task_id": data.get("id", task_dir.name),
            "title": data.get("title", ""),
            "repo": data.get("repo", ""),
            "branch": data.get("branch", ""),
            "created_at": data.get("created_at", ""),
            "recorded_status": data.get("status", "unknown"),
            "real_verified_status": real_status,
            "reason": reason,
            "phase_plan_ref": evidence.get("phase_plan_ref"),
            "evidence": evidence,
        })

    summary = {}
    for r in rows:
        summary[r["real_verified_status"]] = summary.get(r["real_verified_status"], 0) + 1

    generated_at = now.isoformat()
    json_out = {
        "generated_at": generated_at,
        "cutoff": cutoff.isoformat(),
        "tasks_root": args.tasks_root,
        "total_tasks_in_window": len(rows),
        "omitted_task_dirs": [{"dir": n, "reason": w} for n, w in omitted],
        "summary": summary,
        "rows": rows,
    }

    if args.out_json:
        out_path = Path(args.out_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(json_out, indent=2))
        print(f"Wrote {out_path} ({len(rows)} rows)")

    if args.out_md:
        lines = []
        lines.append(f"# Task Completion Audit -- {now.date().isoformat()}")
        lines.append("")
        lines.append(
            f"Real, automated, independently-verified completion status for every "
            f"`ai-os/tasks/task-*` created in the {args.days} days before {generated_at} "
            f"(cutoff: {cutoff.isoformat()}). Generated by `ai-os-scripts/verify_7day_task_completion.py`.\n"
        )
        lines.append(
            "Verification method: for each task, resolve its real PR via `pr_url.txt`, "
            "worker/supervisor log grep, or a `gh pr list --repo <repo> --state all` headRefName match "
            "(one paginated `gh pr list` call per repo, not per-task `gh pr view` calls); PR state "
            "(`MERGED` / `OPEN` / `CLOSED`) is read live from GitHub, never from task.yaml's own "
            "`status` field. If no PR exists, fall back to real commit-ancestry evidence "
            "(`git log origin/<default-branch> --grep=<task_id>` against the repo's local clone). "
            "If neither exists, the task is treated as a non-code investigation task and judged only "
            "by whether its own checkpoint history reached a genuine terminal state.\n"
        )
        lines.append("## Summary")
        lines.append("")
        lines.append("| real_verified_status | count |")
        lines.append("|---|---|")
        for k in sorted(summary):
            lines.append(f"| {k} | {summary[k]} |")
        lines.append("")
        lines.append(f"Total tasks in window: **{len(rows)}**")
        if omitted:
            lines.append(f"\nOmitted (unparseable/missing task.yaml, excluded from count and table): **{len(omitted)}**")
            for n, w in omitted:
                lines.append(f"- `{n}`: {w}")
        lines.append("")
        lines.append("## Full audit table")
        lines.append("")
        lines.append("| task_id | title | recorded_status | real_verified_status | reason | phase_plan_ref |")
        lines.append("|---|---|---|---|---|---|")

        def esc(s):
            return str(s).replace("|", "\\|").replace("\n", " ")

        for r in sorted(rows, key=lambda r: r["created_at"]):
            lines.append(
                f"| {esc(r['task_id'])} | {esc(r['title'])} | {esc(r['recorded_status'])} | "
                f"{esc(r['real_verified_status'])} | {esc(r['reason'])} | {esc(r['phase_plan_ref'] or '')} |"
            )
        lines.append("")

        out_path = Path(args.out_md)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(lines))
        print(f"Wrote {out_path} ({len(rows)} rows)")

    if not args.out_md and not args.out_json:
        print(json.dumps(json_out, indent=2))


if __name__ == "__main__":
    main()
