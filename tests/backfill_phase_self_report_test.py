#!/usr/bin/env python3
"""
Regression test for scripts/backfill_phase_self_report.py -- the software-
driven fix for the real, repeated manual-backfill incidents this session
(VERIDIAN_ARCHITECTURE_V2 phase_1 / compliance-tracker PR #559, phase_2 /
PR #560: both merged for real, neither worker updated its own phase-plan
entry, both needed a human to hand-edit the YAML -- commits fab4ff4 and
1f9fd52).

Builds a throwaway local git repo (bare "origin" + working clone) and a
throwaway tasks dir, points the script at them via its env-var overrides
(VERIDIAN_REPO_ROOT_OVERRIDE / VERIDIAN_TASKS_DIR_OVERRIDE /
VERIDIAN_TASK_CLI_OVERRIDE -- production code never reads these except
through the override, so a real invocation can't accidentally hit a
fixture), and fakes `gh` via a PATH-prepended shell script so no real
GitHub call is made. Runs the real script as a subprocess -- this cannot
drift from what actually ships, unlike a reimplementation.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "backfill_phase_self_report.py")

FAILURES = []


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def make_fixture():
    tmp = tempfile.mkdtemp(prefix="backfill_test_")
    repo_root = os.path.join(tmp, "repo_root")
    remote = os.path.join(tmp, "remote.git")
    tasks_dir = os.path.join(tmp, "tasks")
    bin_dir = os.path.join(tmp, "bin")
    os.makedirs(os.path.join(repo_root, "ai-os"))
    os.makedirs(tasks_dir)
    os.makedirs(bin_dir)

    run(["git", "init", "-q", "-b", "master"], cwd=repo_root)
    run(["git", "config", "user.email", "test@test.com"], cwd=repo_root)
    run(["git", "config", "user.name", "Test"], cwd=repo_root)

    plan_path = os.path.join(repo_root, "ai-os", "FAKE_PHASE_PLAN_2026-07-25.yaml")
    with open(plan_path, "w") as f:
        f.write(textwrap.dedent("""\
            meta:
              title: Fake Initiative
            phases:
            - id: phase_1_foo
              name: Foo phase
              depends_on: []
              status: not_started
              target_repo: fake-target-repo
            - id: phase_2_bar
              name: Bar phase
              depends_on:
              - phase_1_foo
              status: 'done'
              completed_by_task: task-preexisting
              evidence: 'a worker already did this correctly'
              target_repo: fake-target-repo
            """))
    run(["git", "add", "-A"], cwd=repo_root)
    run(["git", "commit", "-q", "-m", "init"], cwd=repo_root)

    run(["git", "init", "-q", "--bare", remote])
    run(["git", "remote", "add", "origin", remote], cwd=repo_root)
    run(["git", "push", "-q", "-u", "origin", "master"], cwd=repo_root)

    gh_path = os.path.join(bin_dir, "gh")
    with open(gh_path, "w") as f:
        f.write(textwrap.dedent("""\
            #!/bin/bash
            if [ "$1" = "pr" ] && [ "$2" = "list" ]; then
              echo "$GH_MOCK_PR_LIST_RESPONSE"
              exit 0
            fi
            exit 0
            """))
    os.chmod(gh_path, 0o755)

    return tmp, repo_root, tasks_dir, bin_dir, plan_path


def make_task(tasks_dir, task_id, repo, status, phase_id, plan_file):
    task_dir = os.path.join(tasks_dir, task_id)
    os.makedirs(task_dir)
    with open(os.path.join(task_dir, "task.yaml"), "w") as f:
        f.write(f"id: {task_id}\nrepo: {repo}\nbranch: worker/{task_id}\nstatus: {status}\n")
    with open(os.path.join(task_dir, "prompt.txt"), "w") as f:
        f.write(f"This is {phase_id} of ai-os/{plan_file}, part of the Fake Initiative initiative.\n")
    return task_dir


def env_for(tmp, repo_root, tasks_dir, bin_dir, pr_list_response):
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["VERIDIAN_REPO_ROOT_OVERRIDE"] = repo_root
    env["VERIDIAN_TASKS_DIR_OVERRIDE"] = tasks_dir
    env["GH_MOCK_PR_LIST_RESPONSE"] = pr_list_response
    return env


def check(label, cond):
    status = "PASS" if cond else "FAIL"
    print(f"{status}: {label}")
    if not cond:
        FAILURES.append(label)


def scenario_merged_missing_self_report():
    tmp, repo_root, tasks_dir, bin_dir, plan_path = make_fixture()
    try:
        make_task(tasks_dir, "task-20260101-000000-fake-phase1", "fake-target-repo",
                   "completed", "phase_1_foo", "FAKE_PHASE_PLAN_2026-07-25.yaml")
        merged_resp = '[{"state":"MERGED","number":999,"mergedAt":"2026-07-25T18:46:17Z"}]'
        env = env_for(tmp, repo_root, tasks_dir, bin_dir, merged_resp)

        proc = run(["python3", SCRIPT, "--task-id", "task-20260101-000000-fake-phase1"], env=env)
        out = json.loads(proc.stdout)
        check("merged+missing-self-report: backfill reports changed=True", out.get("changed") is True)

        with open(plan_path) as f:
            content = f.read()
        check("merged+missing-self-report: status flipped to done",
              "status: done" in content)
        check("merged+missing-self-report: completed_by_task written",
              "completed_by_task: task-20260101-000000-fake-phase1" in content)
        check("merged+missing-self-report: evidence cites the real PR number",
              "PR #999" in content)

        log = run(["git", "log", "--oneline"], cwd=repo_root).stdout
        check("merged+missing-self-report: exactly one new commit landed on master",
              len(log.strip().splitlines()) == 2)

        proc2 = run(["python3", SCRIPT, "--task-id", "task-20260101-000000-fake-phase1"], env=env)
        out2 = json.loads(proc2.stdout)
        check("idempotency: re-running after backfill is a no-op",
              out2.get("changed") is False and "already self-reports done" in (out2.get("skipped_reason") or ""))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scenario_already_self_reported_untouched():
    tmp, repo_root, tasks_dir, bin_dir, plan_path = make_fixture()
    try:
        make_task(tasks_dir, "task-20260101-000001-fake-phase2", "fake-target-repo",
                   "completed", "phase_2_bar", "FAKE_PHASE_PLAN_2026-07-25.yaml")
        merged_resp = '[{"state":"MERGED","number":1001,"mergedAt":"2026-07-26T01:00:00Z"}]'
        env = env_for(tmp, repo_root, tasks_dir, bin_dir, merged_resp)

        with open(plan_path) as f:
            before = f.read()
        proc = run(["python3", SCRIPT, "--task-id", "task-20260101-000001-fake-phase2"], env=env)
        out = json.loads(proc.stdout)
        with open(plan_path) as f:
            after = f.read()
        check("already-self-reported phase: left completely untouched",
              out.get("changed") is False and before == after)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scenario_not_merged_skipped():
    tmp, repo_root, tasks_dir, bin_dir, plan_path = make_fixture()
    try:
        make_task(tasks_dir, "task-20260101-000002-fake-phase1", "fake-target-repo",
                   "pending_review", "phase_1_foo", "FAKE_PHASE_PLAN_2026-07-25.yaml")
        open_resp = '[{"state":"OPEN","number":1002,"mergedAt":null}]'
        env = env_for(tmp, repo_root, tasks_dir, bin_dir, open_resp)

        proc = run(["python3", SCRIPT, "--task-id", "task-20260101-000002-fake-phase1"], env=env)
        out = json.loads(proc.stdout)
        check("PR not merged: skipped, no write attempted",
              out.get("changed") is False and "no confirmed MERGED PR" in (out.get("skipped_reason") or ""))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scenario_dry_run_makes_no_commit():
    tmp, repo_root, tasks_dir, bin_dir, plan_path = make_fixture()
    try:
        make_task(tasks_dir, "task-20260101-000003-fake-phase1", "fake-target-repo",
                   "completed", "phase_1_foo", "FAKE_PHASE_PLAN_2026-07-25.yaml")
        merged_resp = '[{"state":"MERGED","number":1003,"mergedAt":"2026-07-26T02:00:00Z"}]'
        env = env_for(tmp, repo_root, tasks_dir, bin_dir, merged_resp)

        log_before = run(["git", "log", "--oneline"], cwd=repo_root).stdout
        proc = run(["python3", SCRIPT, "--task-id", "task-20260101-000003-fake-phase1", "--dry-run"], env=env)
        out = json.loads(proc.stdout)
        log_after = run(["git", "log", "--oneline"], cwd=repo_root).stdout
        check("dry-run: reports changed=True but commits nothing",
              out.get("changed") is True and log_before == log_after)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scenario_indented_phase_int_schema():
    """Real bug caught by testing against production data: AUDITOR_ENGINE_
    PHASE_PLAN_2026-07-24.yaml uses `  - phase: N` (2-space indent, bare
    int) not `- id: <string>` (0-indent, string) -- a fixed-column/fixed-
    schema assumption silently failed to find every single one of that
    file's real phases ("phase id phase-5 not found in ..."), which would
    have made the retroactive sweep miss genuine gaps in that indent style
    forever. This locks the fix in."""
    tmp = tempfile.mkdtemp(prefix="backfill_test_")
    try:
        repo_root = os.path.join(tmp, "repo_root")
        remote = os.path.join(tmp, "remote.git")
        tasks_dir = os.path.join(tmp, "tasks")
        bin_dir = os.path.join(tmp, "bin")
        os.makedirs(os.path.join(repo_root, "ai-os"))
        os.makedirs(tasks_dir)
        os.makedirs(bin_dir)
        run(["git", "init", "-q", "-b", "master"], cwd=repo_root)
        run(["git", "config", "user.email", "test@test.com"], cwd=repo_root)
        run(["git", "config", "user.name", "Test"], cwd=repo_root)

        plan_path = os.path.join(repo_root, "ai-os", "FAKE_AUDITOR_PLAN_2026-07-24.yaml")
        with open(plan_path, "w") as f:
            f.write(textwrap.dedent("""\
                meta:
                  title: Fake Auditor Initiative
                phases:
                  - phase: 0
                    name: Entry phase
                    depends_on: []
                    status: this_task

                  - phase: 1
                    name: Second phase
                    depends_on: [0]
                    status: not_started
                """))
        run(["git", "add", "-A"], cwd=repo_root)
        run(["git", "commit", "-q", "-m", "init"], cwd=repo_root)
        run(["git", "init", "-q", "--bare", remote])
        run(["git", "remote", "add", "origin", remote], cwd=repo_root)
        run(["git", "push", "-q", "-u", "origin", "master"], cwd=repo_root)

        gh_path = os.path.join(bin_dir, "gh")
        with open(gh_path, "w") as f:
            f.write(textwrap.dedent("""\
                #!/bin/bash
                if [ "$1" = "pr" ] && [ "$2" = "list" ]; then
                  echo "$GH_MOCK_PR_LIST_RESPONSE"
                  exit 0
                fi
                exit 0
                """))
        os.chmod(gh_path, 0o755)

        make_task(tasks_dir, "task-20260101-000005-fake-auditor-phase1", "fake-target-repo",
                   "completed", "phase-1", "FAKE_AUDITOR_PLAN_2026-07-24.yaml")
        merged_resp = '[{"state":"MERGED","number":1005,"mergedAt":"2026-07-26T04:00:00Z"}]'
        env = env_for(tmp, repo_root, tasks_dir, bin_dir, merged_resp)

        proc = run(["python3", SCRIPT, "--task-id", "task-20260101-000005-fake-auditor-phase1"], env=env)
        out = json.loads(proc.stdout)
        check("2-space-indented bare-int phase schema: block is found and backfilled",
              out.get("changed") is True and out.get("error") is None)

        with open(plan_path) as f:
            content = f.read()
        check("2-space-indented bare-int phase schema: status/evidence written at the correct indent",
              "  - phase: 1\n    name: Second phase\n    depends_on: [0]\n    status: done\n" in content)
        check("2-space-indented bare-int phase schema: sibling phase 0 left untouched",
              "  - phase: 0\n    name: Entry phase\n    depends_on: []\n    status: this_task\n" in content)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scenario_sweep_tier2_checkpoints():
    tmp, repo_root, tasks_dir, bin_dir, plan_path = make_fixture()
    try:
        make_task(tasks_dir, "task-20260101-000004-fake-phase1", "fake-target-repo",
                   "awaiting_human_approval", "phase_1_foo", "FAKE_PHASE_PLAN_2026-07-25.yaml")
        merged_resp = '[{"state":"MERGED","number":1004,"mergedAt":"2026-07-26T03:00:00Z"}]'
        env = env_for(tmp, repo_root, tasks_dir, bin_dir, merged_resp)
        fake_task_cli = os.path.join(tmp, "fake_veridian_task.py")
        with open(fake_task_cli, "w") as f:
            f.write("import sys\nprint('CHECKPOINT', sys.argv[1:])\n")
        env["VERIDIAN_TASK_CLI_OVERRIDE"] = fake_task_cli

        proc = run(["python3", SCRIPT, "--sweep", "--checkpoint-on-success"], env=env)
        out = json.loads(proc.stdout)
        results = out.get("results") or []
        check("tier2 sweep: finds and backfills the merged awaiting_human_approval task",
              any(r.get("task_id") == "task-20260101-000004-fake-phase1" and r.get("changed") for r in results))
        check("tier2 sweep: checkpoints the task completed once backfilled",
              any(r.get("checkpointed") for r in results))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    scenario_merged_missing_self_report()
    scenario_already_self_reported_untouched()
    scenario_not_merged_skipped()
    scenario_dry_run_makes_no_commit()
    scenario_indented_phase_int_schema()
    scenario_sweep_tier2_checkpoints()

    if FAILURES:
        print(f"\n{len(FAILURES)} scenario(s) failed.")
        sys.exit(1)
    print("\nAll scenarios passed.")
    sys.exit(0)
