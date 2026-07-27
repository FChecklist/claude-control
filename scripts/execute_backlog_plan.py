#!/usr/bin/env python3
"""
execute_backlog_plan.py -- executes a FRESH dedup/completion plan for real,
reusing the existing dispatch_core.py concurrency lock/cap and
wiring_registry writer (PR #101), and delegating every classify/verify/write
decision to this same repo's plan_backlog_completion.py (PR #102) -- never
an independent copy of dedup logic.

2026-07-27 incident root cause: an untracked copy of this file used to live
directly at /opt/veridian/ai-os/execute_backlog_plan.py, driven by an
untracked, pre-fix copy of plan_backlog_completion.py that also lived
directly in ai-os/ -- neither under version control, neither reviewed. That
pair loaded a FROZEN, STALE BACKLOG_COMPLETION_PLAN_2026-07-27.json (with no
SUCCESS_CRITERIA re-verification behind its classifications) and wrote its
recorded category verbatim into real task.yaml files at execution time with
no re-check. 32 real task.yaml files were mass-mislabeled this way. This
version, now under version control in this repo:
  - regenerates the plan FRESH at execution time by invoking this repo's
    own plan_backlog_completion.py as a subprocess (real gh pr view + a real
    re-run of each candidate's own SUCCESS_CRITERIA against a fresh
    checkout of the actual current default branch) -- it never trusts a
    frozen JSON snapshot for a write decision again;
  - performs the only real task.yaml writes (duplicate-collapse +
    representative-completion) through plan_backlog_completion.py's own
    apply_verified_collapses() / apply_collapse() / apply_representative_completion(),
    imported directly rather than reimplemented, so this script has no
    write logic of its own to drift out of sync with the tested one.

The real, live entry point is /opt/veridian/ai-os/execute_backlog_plan.py,
which is now a thin delegator (os.execv) into this file -- see that file's
own docstring. There is exactly one real implementation of this
orchestration; ai-os/ is just how the operational surface reaches it.

Phases (each independently re-runnable/idempotent -- checks real current
state before acting, never blind):
  1+2. Collapse: for every issue the FRESH, fixed classify() verifies as
     ALREADY_DONE_STALE_STATUS (SUCCESS_CRITERIA independently re-run and
     passing), mark non-representative repeat attempts status=superseded
     AND patch the representative's own status to completed -- both halves
     of classify()'s own promised action, via apply_verified_collapses().
  3. For PR_PENDING_MERGE representatives (excluding any flagged
     low-confidence match), flip status=pending_review (same shape
     veridian-task.py adopt produces) and start a ONE-SHOT
     veridian-supervisor@<id>.service for a real audit+merge decision --
     never `systemctl enable`, never touches crontab.
  3b. For SUBSTANTIAL_WORK_NO_PR_NEEDS_REVIEW issues with real committed
     work sitting in a task's own workspace worktree/branch, push the
     branch (never force) and open a real PR if one doesn't already exist,
     then route through the same supervisor audit path as phase 3.
  4. Redispatch NEEDS_FRESH_REDISPATCH / PR_CLOSED_NEEDS_REDISPATCH issues
     by resubmitting their own original prompt.txt (already passed gates
     once) via task-gateway.py submit+start, wave-sequenced per the fresh
     plan's repo-conflict-free waves.
  5. Records a wiring_registry dispatch_event row (dispatch_core's own
     writer) for every real action taken in phases 1-4.

Resource guard: refuses to start anything new once real CPU load or the
active worker/supervisor count would push past a safe ceiling -- checks
BOTH dispatch_core's own CONCURRENCY_CAP-based slot check AND raw /proc
load average against an 8-core box, so total usage never approaches 99%.
"""
import datetime
import importlib.util
import json
import os
import subprocess
import sys
import time
import yaml

sys.path.insert(0, "/opt/veridian/scripts")
import dispatch_core  # noqa: E402

AI_OS = "/opt/veridian/ai-os"
TASKS_DIR = f"{AI_OS}/tasks"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from plan_backlog_completion import GH_OWNER  # noqa: E402  (reuse the one real org-name constant)
FIXED_SCRIPT = os.path.join(SCRIPT_DIR, "plan_backlog_completion.py")
GATEWAY = "/opt/veridian/scripts/task-gateway.py"
CORES = 8
MAX_LOAD1 = CORES * 0.90  # stay well clear of the 99% ceiling with margin

LOW_CONFIDENCE_ISSUE_KEYS = {"slug:tier2-fix--pr-563-migration-drift-ci-fai"}


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load_fixed_module():
    """Import plan_backlog_completion.py (same directory, same repo, same
    review) by file path so this script's write phase can call its real
    apply_collapse()/apply_representative_completion()/apply_verified_collapses()
    directly -- never a local reimplementation of that logic."""
    spec = importlib.util.spec_from_file_location("plan_backlog_completion_fixed", FIXED_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def regenerate_fresh_plan():
    """Shell out to plan_backlog_completion.py to produce a plan reflecting
    CURRENT live state -- real gh pr view + a real re-run of each
    candidate's own SUCCESS_CRITERIA against a fresh checkout of the actual
    current default branch. Never trust a frozen on-disk plan for a write
    decision again (this is the exact 2026-07-27 incident root cause)."""
    today = datetime.date.today().isoformat()
    json_out = f"{AI_OS}/BACKLOG_COMPLETION_PLAN_{today}_FRESH.json"
    md_out = f"{AI_OS}/BACKLOG_COMPLETION_PLAN_{today}_FRESH.md"
    r = subprocess.run(
        [sys.executable, FIXED_SCRIPT, "--json-out", json_out, "--md-out", md_out],
        capture_output=True, text=True, timeout=1800,
    )
    if r.returncode != 0:
        sys.exit(f"FATAL: plan_backlog_completion.py run failed (rc={r.returncode}): {r.stderr[-2000:]}")
    with open(json_out) as f:
        return json.load(f), json_out


def real_load1():
    with open("/proc/loadavg") as f:
        return float(f.read().split()[0])


def resource_headroom_ok():
    load1 = real_load1()
    return load1 < MAX_LOAD1


def wait_for_slot(label, timeout_s=120):
    """Blocks (briefly) until dispatch_core's own concurrency cap AND real
    load average both have headroom. Never busy-loops past timeout_s --
    logs and returns False rather than hanging the whole run forever."""
    waited = 0
    while waited < timeout_s:
        with dispatch_core.acquire_dispatch_lock():
            if dispatch_core.has_free_slot() and resource_headroom_ok():
                return True
        time.sleep(5)
        waited += 5
    print(f"WARNING: no free slot for {label} after {timeout_s}s (load1={real_load1():.2f}, "
          f"running={dispatch_core.running_worker_count()}) -- skipping this run, retry later",
          file=sys.stderr)
    return False


def phase1and2_collapse_verified(plan, results, mod):
    """The ONLY phase in this script allowed to write status=superseded/
    duplicate_of/completed to a real task.yaml -- delegates entirely to
    plan_backlog_completion.py's apply_verified_collapses(), which only ever
    acts on issues THIS fresh run's own classify() verified as
    ALREADY_DONE_STALE_STATUS with a passing SUCCESS_CRITERIA re-run.
    Replaces the old phase1_mark_duplicates + phase2_mark_already_done,
    which used to trust a frozen JSON plan's category with no
    re-verification at execution time."""
    print("=== PHASE 1+2: collapse duplicates + complete representative (fresh, verified classify() only) ===")
    applied = mod.apply_verified_collapses(plan["issues"], dry_run=False)
    for issue in plan["issues"]:
        c = issue["classification"]
        verification = c.get("success_criteria_verification") or {}
        if c.get("category") != "ALREADY_DONE_STALE_STATUS" or not verification.get("verified"):
            continue
        rep = issue["representative_task_id"]
        results["marked_completed"].append(rep)
        results["duplicates_marked"].extend(
            a for a in issue["all_attempt_ids"] if a != rep
        )
        dispatch_core.record_dispatch_event(
            rep, dispatched_by="execute_backlog_plan.py",
            source_queue_or_plan="fresh-verified-classify",
            worker_unit=None,
            extra={"action": "status_corrected_to_completed_verified", "pr": c.get("pr_number")},
        )
    print(f"  applied {applied} real task.yaml write(s) via apply_verified_collapses()")


def phase3_route_pending_merges(plan, results):
    print("=== PHASE 3: route real open PRs through supervisor audit+merge ===")
    for issue in plan["issues"]:
        c = issue["classification"]
        if c["category"] != "PR_PENDING_MERGE":
            continue
        if issue["issue_key"] in LOW_CONFIDENCE_ISSUE_KEYS:
            print(f"  SKIP (low-confidence PR match, needs manual check): {issue['issue_key']}")
            results["skipped_low_confidence"].append(issue["issue_key"])
            continue
        rep = issue["representative_task_id"]
        path = f"{TASKS_DIR}/{rep}/task.yaml"
        with open(path) as f:
            doc = yaml.safe_load(f) or {}
        review_json = f"{TASKS_DIR}/{rep}/review.json"
        if doc.get("status") == "pending_review" and not os.path.exists(review_json):
            print(f"  already pending_review with no review.json, skipping re-trigger: {rep}")
        else:
            doc["status"] = "pending_review"
            doc["adopted_existing_pr"] = c["pr_state"]["url"] if c.get("pr_state") else None
            doc["routed_to_supervisor_at"] = now_iso()
            with open(path, "w") as f:
                yaml.safe_dump(doc, f, default_flow_style=False, sort_keys=False)
            if os.path.exists(review_json):
                os.rename(review_json, review_json + f".pre-reroute-{int(time.time())}.bak")

        if not wait_for_slot(rep):
            results["deferred_no_slot"].append(rep)
            continue

        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        r = subprocess.run(
            ["systemctl", "--user", "start", f"veridian-supervisor@{rep}.service"],
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            results["routed_to_supervisor"].append(rep)
            dispatch_core.record_dispatch_event(
                rep, dispatched_by="execute_backlog_plan.py",
                source_queue_or_plan="fresh-verified-classify",
                worker_unit=f"veridian-supervisor@{rep}.service",
                extra={"action": "routed_existing_pr_to_supervisor", "pr": c.get("pr_number")},
            )
            print(f"  started veridian-supervisor@{rep} (PR #{c.get('pr_number')})")
        else:
            results["supervisor_start_failed"].append({"task_id": rep, "stderr": r.stderr[:300]})
            print(f"  FAILED to start supervisor for {rep}: {r.stderr[:200]}", file=sys.stderr)
        time.sleep(3)  # stagger starts, avoid a thundering-herd CPU spike


def phase3b_open_prs_for_substantial_work(plan, results):
    """The SUBSTANTIAL_WORK_NO_PR_NEEDS_REVIEW issues have real committed
    work sitting in their task's own workspace worktree/branch but were never
    pushed/PR'd before the worker crashed or got swept up in the OOM
    incident. Push the branch (never force) and open a real PR if one
    doesn't already exist, then route through the same supervisor audit
    path as phase 3 -- reuses that logic rather than inventing a second
    merge path."""
    print("=== PHASE 3b: open PRs for issues with real uncommitted-to-PR work ===")
    for issue in plan["issues"]:
        c = issue["classification"]
        if c["category"] != "SUBSTANTIAL_WORK_NO_PR_NEEDS_REVIEW":
            continue
        rep = issue["representative_task_id"]
        best_id = c.get("best_progress_attempt_id") or rep
        workspace = f"{TASKS_DIR}/{best_id}/workspace"
        if not os.path.isdir(os.path.join(workspace, ".git")) and not os.path.isfile(os.path.join(workspace, ".git")):
            print(f"  SKIP {best_id}: no git workspace found")
            results.setdefault("substantial_work_skipped_no_workspace", []).append(best_id)
            continue

        branch_r = subprocess.run(["git", "-C", workspace, "branch", "--show-current"],
                                   capture_output=True, text=True)
        branch = branch_r.stdout.strip()
        if not branch:
            print(f"  SKIP {best_id}: detached HEAD, no branch to push")
            results.setdefault("substantial_work_skipped_detached", []).append(best_id)
            continue

        base_r = subprocess.run(["git", "-C", workspace, "remote", "show", "origin"],
                                 capture_output=True, text=True)
        default_branch = "master"
        for line in base_r.stdout.splitlines():
            if "HEAD branch" in line:
                default_branch = line.split(":")[-1].strip()
        ahead_r = subprocess.run(
            ["git", "-C", workspace, "rev-list", "--count", f"origin/{default_branch}..HEAD"],
            capture_output=True, text=True,
        )
        try:
            ahead = int(ahead_r.stdout.strip())
        except ValueError:
            ahead = 0
        if ahead == 0:
            print(f"  SKIP {best_id}: no commits ahead of origin/{default_branch} despite recorded completed_steps")
            results.setdefault("substantial_work_skipped_nothing_ahead", []).append(best_id)
            continue

        push_r = subprocess.run(["git", "-C", workspace, "push", "-u", "origin", branch],
                                 capture_output=True, text=True)
        if push_r.returncode != 0:
            print(f"  FAILED push for {best_id} ({branch}): {push_r.stderr[-300:]}", file=sys.stderr)
            results.setdefault("substantial_work_push_failed", []).append(best_id)
            continue

        existing_pr = subprocess.run(
            ["gh", "pr", "list", "--repo", f"{GH_OWNER}/{issue['repo']}", "--head", branch,
             "--json", "number,url,state"],
            capture_output=True, text=True,
        )
        pr_url = None
        try:
            existing = json.loads(existing_pr.stdout)
        except Exception:
            existing = []
        if existing:
            pr_url = existing[0]["url"]
            print(f"  PR already exists for {branch}: {pr_url}")
        else:
            create_r = subprocess.run(
                ["gh", "pr", "create", "--repo", f"{GH_OWNER}/{issue['repo']}",
                 "--head", branch, "--base", default_branch,
                 "--title", issue["title"][:120],
                 "--body", f"Auto-opened by execute_backlog_plan.py for real, "
                           f"already-committed work found in {best_id}'s workspace "
                           f"({ahead} commit(s) ahead of origin/{default_branch}) that "
                           f"crashed/got interrupted before a PR was opened."],
                capture_output=True, text=True,
            )
            if create_r.returncode == 0:
                pr_url = create_r.stdout.strip()
                print(f"  opened PR for {best_id}: {pr_url}")
            else:
                print(f"  FAILED gh pr create for {best_id}: {create_r.stderr[-300:]}", file=sys.stderr)
                results.setdefault("substantial_work_pr_create_failed", []).append(best_id)
                continue

        results.setdefault("substantial_work_pr_opened", []).append({"task_id": rep, "pr_url": pr_url})

        path = f"{TASKS_DIR}/{rep}/task.yaml"
        with open(path) as f:
            doc = yaml.safe_load(f) or {}
        review_json = f"{TASKS_DIR}/{rep}/review.json"
        doc["status"] = "pending_review"
        doc["opened_pr_url"] = pr_url
        doc["routed_to_supervisor_at"] = now_iso()
        with open(path, "w") as f:
            yaml.safe_dump(doc, f, default_flow_style=False, sort_keys=False)
        if os.path.exists(review_json):
            os.rename(review_json, review_json + f".pre-reroute-{int(time.time())}.bak")

        if not wait_for_slot(rep):
            results["deferred_no_slot"].append(rep)
            continue
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        r = subprocess.run(["systemctl", "--user", "start", f"veridian-supervisor@{rep}.service"],
                            capture_output=True, text=True)
        if r.returncode == 0:
            results["routed_to_supervisor"].append(rep)
            dispatch_core.record_dispatch_event(
                rep, dispatched_by="execute_backlog_plan.py",
                source_queue_or_plan="fresh-verified-classify",
                worker_unit=f"veridian-supervisor@{rep}.service",
                extra={"action": "opened_pr_and_routed_to_supervisor", "pr_url": pr_url},
            )
        else:
            results["supervisor_start_failed"].append({"task_id": rep, "stderr": r.stderr[:300]})
        time.sleep(3)


def phase4_redispatch(plan, results):
    print("=== PHASE 4: redispatch genuinely-needed-fresh-work issues (waves) ===")
    redispatch_cats = {"NEEDS_FRESH_REDISPATCH", "PR_CLOSED_NEEDS_REDISPATCH"}
    waves = {}
    for issue in plan["issues"]:
        if issue["classification"]["category"] in redispatch_cats and issue.get("wave"):
            waves.setdefault(issue["wave"], []).append(issue)

    for wave_num in sorted(waves):
        print(f"  -- wave {wave_num} --")
        for issue in waves[wave_num]:
            rep = issue["representative_task_id"]
            prompt_path = f"{TASKS_DIR}/{rep}/prompt.txt"
            if not os.path.isfile(prompt_path):
                print(f"  SKIP {rep}: no prompt.txt on disk to reuse", file=sys.stderr)
                results["redispatch_skipped_no_prompt"].append(rep)
                continue
            if not wait_for_slot(rep):
                results["deferred_no_slot"].append(rep)
                continue
            prompt_text = open(prompt_path).read()
            submit = subprocess.run(
                ["python3", GATEWAY, "submit", "--text", prompt_text,
                 "--source", "ai_agent", "--session-id", "execute-backlog-plan"],
                capture_output=True, text=True,
            )
            instr_id = None
            try:
                submit_json = json.loads(submit.stdout)
                instr_id = submit_json.get("instruction_id")
            except Exception:
                pass
            if not instr_id:
                print(f"  FAILED submit for {rep}: {submit.stdout[-500:]} {submit.stderr[-300:]}", file=sys.stderr)
                results["redispatch_submit_failed"].append(rep)
                continue
            start = subprocess.run(
                ["python3", GATEWAY, "start", "--instruction-id", instr_id,
                 "--title", issue["title"][:120], "--repo", issue["repo"],
                 "--prompt-file", prompt_path],
                capture_output=True, text=True,
            )
            try:
                start_json = json.loads(start.stdout)
            except Exception:
                start_json = {"raw": start.stdout[-500:], "stderr": start.stderr[-300:]}
            new_task_id = start_json.get("task_id")
            if new_task_id:
                results["redispatched"].append({"original": rep, "new_task_id": new_task_id})
                dispatch_core.record_dispatch_event(
                    new_task_id, dispatched_by="execute_backlog_plan.py",
                    source_queue_or_plan="fresh-verified-classify",
                    worker_unit=start_json.get("work_item_id"),
                    extra={"action": "redispatch_of_original_prompt", "original_task_id": rep, "wave": wave_num},
                )
                print(f"  redispatched {rep} -> {new_task_id}")
            else:
                results["redispatch_start_failed"].append({"task_id": rep, "detail": start_json})
                print(f"  FAILED start for {rep}: {start_json}", file=sys.stderr)
            time.sleep(3)


def main():
    mod = load_fixed_module()
    plan, fresh_json_path = regenerate_fresh_plan()

    results = {
        "duplicates_marked": [], "marked_completed": [], "routed_to_supervisor": [],
        "supervisor_start_failed": [], "redispatched": [], "redispatch_submit_failed": [],
        "redispatch_start_failed": [], "redispatch_skipped_no_prompt": [],
        "skipped_low_confidence": [], "deferred_no_slot": [],
        "substantial_work_skipped_no_workspace": [], "substantial_work_skipped_detached": [],
        "substantial_work_skipped_nothing_ahead": [], "substantial_work_push_failed": [],
        "substantial_work_pr_create_failed": [], "substantial_work_pr_opened": [],
        "fresh_plan_used": fresh_json_path,
        "started_at": now_iso(),
    }

    phase1and2_collapse_verified(plan, results, mod)
    phase3_route_pending_merges(plan, results)
    phase3b_open_prs_for_substantial_work(plan, results)
    phase4_redispatch(plan, results)

    results["finished_at"] = now_iso()
    out_path = f"{AI_OS}/BACKLOG_PLAN_EXECUTION_RESULT_{datetime.date.today().isoformat()}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n=== DONE. Full results: {out_path} ===")
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in results.items()}, indent=2))


if __name__ == "__main__":
    main()
