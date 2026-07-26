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


def scenario_audit_reverts_worker_bypass_self_report():
    """Reproduces the real 2026-07-26 incident: VERIDIAN_ARCHITECTURE_V2
    phase_4's status was set to done by commit 4611924, authored by the
    worker task itself, citing only a branch name -- while the real PR
    #562 stayed OPEN with mergeStateStatus DIRTY/CONFLICTING. That commit
    bypassed backfill_phase_self_report.py entirely (no --task-id/--sweep
    call ever ran for it); it was only caught because a human happened to
    manually cross-check `gh pr view` (see commit a82ee2d). This locks in
    --audit-plans as the software fix: it must independently re-verify
    every already-"done" phase (not just newly-completing ones) and revert
    any that fail re-verification, while leaving a real merged phase (and
    everything outside the phases: list) completely untouched.
    """
    tmp = tempfile.mkdtemp(prefix="backfill_audit_test_")
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

        plan_path = os.path.join(repo_root, "ai-os", "FAKE_INCIDENT_PHASE_PLAN_2026-07-25.yaml")
        with open(plan_path, "w") as f:
            f.write(textwrap.dedent("""\
                meta:
                  title: Fake Phase-4-incident Initiative
                phases:
                - id: phase_a_legit
                  name: Legit phase
                  depends_on: []
                  status: done
                  target_repo: fake-target-repo
                  completed_by_task: task-20260101-000010-legit
                  evidence: 'fake-target-repo PR #2000 merged 2026-07-26T06:00:00Z'
                - id: phase_b_bypass
                  name: Defense-in-depth phase (the one a worker later fakes)
                  depends_on: []
                  status: not_started
                  target_repo: fake-target-repo
                """))
        run(["git", "add", "-A"], cwd=repo_root)
        run(["git", "commit", "-q", "-m", "init"], cwd=repo_root)

        # The false self-report: a worker's own commit, mimicking the real
        # commit 4611924 -- cites only a branch name, no real merged PR.
        with open(plan_path) as f:
            content = f.read()
        content = content.replace(
            "  status: not_started\n  target_repo: fake-target-repo\n",
            "  status: done\n  target_repo: fake-target-repo\n"
            "  completed_by_task: task-20260726-043023-defense-in-depth-bypass\n"
            "  evidence: 'compliance-tracker branch worker/task-20260726-043023-defense-in-depth-bypass'\n",
        )
        with open(plan_path, "w") as f:
            f.write(content)
        run(["git", "add", "-A"], cwd=repo_root)
        run(["git", "commit", "-q", "-m",
             "phase_b defense-in-depth: status done (compliance-tracker branch "
             "worker/task-20260726-043023-defense-in-depth-bypass)\n\n"
             "Same self-report convention as the phase_1/phase_2/phase_3 backfill commits."],
            cwd=repo_root)

        run(["git", "init", "-q", "--bare", remote])
        run(["git", "remote", "add", "origin", remote], cwd=repo_root)
        run(["git", "push", "-q", "-u", "origin", "master"], cwd=repo_root)

        gh_path = os.path.join(bin_dir, "gh")
        with open(gh_path, "w") as f:
            f.write(textwrap.dedent("""\
                #!/bin/bash
                if [ "$1" = "pr" ] && [ "$2" = "list" ]; then
                  head=""
                  prev=""
                  for arg in "$@"; do
                    if [ "$prev" = "--head" ]; then
                      head="$arg"
                    fi
                    prev="$arg"
                  done
                  if [ "$head" = "worker/task-20260101-000010-legit" ]; then
                    echo '[{"state":"MERGED","number":2000,"mergedAt":"2026-07-26T06:00:00Z"}]'
                  else
                    echo '[{"state":"OPEN","number":2001,"mergedAt":null}]'
                  fi
                  exit 0
                fi
                exit 0
                """))
        os.chmod(gh_path, 0o755)

        env = dict(os.environ)
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        env["VERIDIAN_REPO_ROOT_OVERRIDE"] = repo_root
        env["VERIDIAN_TASKS_DIR_OVERRIDE"] = tasks_dir

        log_before = run(["git", "log", "--oneline", "--", "ai-os/FAKE_INCIDENT_PHASE_PLAN_2026-07-25.yaml"],
                          cwd=repo_root).stdout
        check("audit fixture: 2 real commits touched the plan file before the audit runs",
              len(log_before.strip().splitlines()) == 2)

        proc = run(["python3", SCRIPT, "--audit-plans"], env=env)
        out = json.loads(proc.stdout)
        check("audit: exits 0", proc.returncode == 0)
        check("audit: reports changed=True", out.get("changed") is True)
        check("audit: exactly one incident recorded",
              len(out.get("incidents") or []) == 1)
        check("audit: incident cites the bypassing task id",
              "task-20260726-043023-defense-in-depth-bypass" in (out.get("incidents") or [""])[0])

        with open(plan_path) as f:
            content = f.read()
        check("audit: phase_b status reverted to not_started",
              "phase_b_bypass" in content and "  status: not_started\n" in
              content.split("phase_b_bypass")[1])
        check("audit: phase_b's fake completed_by_task removed",
              "task-20260726-043023-defense-in-depth-bypass" not in content)
        check("audit: phase_a (real merged PR) left completely untouched",
              "status: done" in content.split("phase_b_bypass")[0]
              and "task-20260101-000010-legit" in content)

        log_after = run(["git", "log", "--oneline", "--", "ai-os/FAKE_INCIDENT_PHASE_PLAN_2026-07-25.yaml"],
                         cwd=repo_root).stdout
        check("audit: history is intact, not rewritten -- 2 real commits + 1 new revert commit",
              len(log_after.strip().splitlines()) == 3)
        check("audit: revert commit message names the real incident",
              "no real MERGED PR" in run(["git", "log", "-1", "--format=%B"], cwd=repo_root).stdout)

        proc2 = run(["python3", SCRIPT, "--audit-plans"], env=env)
        out2 = json.loads(proc2.stdout)
        check("audit idempotency: re-running after revert finds nothing more to fix",
              out2.get("changed") is False and out2.get("incidents") == [])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scenario_audit_skips_ambiguous_gh_failure():
    """Real regression this locks in: a prior --audit-plans revision
    collapsed 'gh confirmed this PR/branch is NOT merged' and 'the gh call
    itself failed' (non-zero returncode from auth failure/rate-limiting/
    a transient network error) into the same False result, and treated
    any False as a violation eligible for revert. On an unattended cron
    sweep, a transient gh failure would therefore auto-revert a genuinely-
    done phase and auto-commit+push a factually false incident straight
    to master. The ambiguous case must skip-with-warning -- same pattern
    already used correctly for blame_line/parent-lookup failures in this
    file -- and must NOT revert or push anything.
    """
    tmp = tempfile.mkdtemp(prefix="backfill_audit_ambiguous_test_")
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

        plan_path = os.path.join(repo_root, "ai-os", "FAKE_AMBIGUOUS_PHASE_PLAN_2026-07-25.yaml")
        with open(plan_path, "w") as f:
            f.write(textwrap.dedent("""\
                meta:
                  title: Fake Ambiguous-gh-failure Initiative
                phases:
                - id: phase_x_maybe_bypass
                  name: Phase whose gh check will fail transiently
                  depends_on: []
                  status: done
                  target_repo: fake-target-repo
                  completed_by_task: task-20260101-000020-ambiguous
                  evidence: 'fake-target-repo branch worker/task-20260101-000020-ambiguous'
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
                  echo "simulated: authentication failed" >&2
                  exit 1
                fi
                exit 0
                """))
        os.chmod(gh_path, 0o755)

        env = dict(os.environ)
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        env["VERIDIAN_REPO_ROOT_OVERRIDE"] = repo_root
        env["VERIDIAN_TASKS_DIR_OVERRIDE"] = tasks_dir

        log_before = run(["git", "log", "--oneline"], cwd=repo_root).stdout

        proc = run(["python3", SCRIPT, "--audit-plans"], env=env)
        out = json.loads(proc.stdout)
        check("ambiguous gh failure: audit exits 0", proc.returncode == 0)
        check("ambiguous gh failure: reports changed=False (no revert)",
              out.get("changed") is False)
        check("ambiguous gh failure: no incidents recorded",
              out.get("incidents") == [])
        check("ambiguous gh failure: a warning is recorded instead",
              any("task-20260101-000020-ambiguous" in w for w in (out.get("warnings") or [])))

        with open(plan_path) as f:
            content = f.read()
        check("ambiguous gh failure: phase left untouched (still done)",
              "status: done" in content and "task-20260101-000020-ambiguous" in content)

        log_after = run(["git", "log", "--oneline"], cwd=repo_root).stdout
        check("ambiguous gh failure: no new commit was pushed", log_before == log_after)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scenario_audit_flags_missing_target_repo():
    """Real gap this locks in: ai-os/AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml
    (a real existing file in this repo) has zero target_repo fields on any
    phase, so --audit-plans provides no real gh coverage there. A phase
    self-reporting done with no target_repo at all must not be silently
    treated as 'nothing to check' -- it must be logged/flagged so the
    absence of coverage stays visible instead of reading as "audited
    clean"."""
    tmp = tempfile.mkdtemp(prefix="backfill_audit_notarget_test_")
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

        plan_path = os.path.join(repo_root, "ai-os", "FAKE_NOTARGET_PHASE_PLAN_2026-07-24.yaml")
        with open(plan_path, "w") as f:
            f.write(textwrap.dedent("""\
                meta:
                  title: Fake No-target-repo Initiative
                phases:
                  - phase: 0
                    name: Entry phase
                    depends_on: []
                    status: done
                    completed_by_task: task-20260101-000021-notarget
                """))
        run(["git", "add", "-A"], cwd=repo_root)
        run(["git", "commit", "-q", "-m", "init"], cwd=repo_root)
        run(["git", "init", "-q", "--bare", remote])
        run(["git", "remote", "add", "origin", remote], cwd=repo_root)
        run(["git", "push", "-q", "-u", "origin", "master"], cwd=repo_root)

        gh_path = os.path.join(bin_dir, "gh")
        with open(gh_path, "w") as f:
            f.write("#!/bin/bash\nexit 0\n")
        os.chmod(gh_path, 0o755)

        env = dict(os.environ)
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        env["VERIDIAN_REPO_ROOT_OVERRIDE"] = repo_root
        env["VERIDIAN_TASKS_DIR_OVERRIDE"] = tasks_dir

        proc = run(["python3", SCRIPT, "--audit-plans"], env=env)
        out = json.loads(proc.stdout)
        check("no target_repo: audit exits 0", proc.returncode == 0)
        check("no target_repo: reports changed=False (no revert)",
              out.get("changed") is False)
        check("no target_repo: no incidents recorded", out.get("incidents") == [])
        check("no target_repo: a warning flags the missing coverage",
              any("task-20260101-000021-notarget" in w and "target_repo" in w
                  for w in (out.get("warnings") or [])))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scenario_audit_records_incident_for_fabricated_block_no_parent():
    """The most direct reproduction of the original phase_4/PR#562
    incident: a worker fabricates an entirely new phase block from
    scratch (the block does not exist at all in the parent revision --
    there is no prior state to revert to), citing a merge that gh does
    not confirm. audit_and_correct_plan_file() cannot auto-correct this
    (nothing to revert TO), but it must still record a real, visible
    incident rather than silently breaking with a stderr-only warning and
    result['changed'] staying False with zero trace anywhere else."""
    tmp = tempfile.mkdtemp(prefix="backfill_audit_fabricated_test_")
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

        plan_path = os.path.join(repo_root, "ai-os", "FAKE_FABRICATED_PHASE_PLAN_2026-07-25.yaml")
        with open(plan_path, "w") as f:
            f.write(textwrap.dedent("""\
                meta:
                  title: Fake Fabricated-block Initiative
                phases:
                - id: phase_a_legit
                  name: Pre-existing legit phase
                  depends_on: []
                  status: not_started
                  target_repo: fake-target-repo
                """))
        run(["git", "add", "-A"], cwd=repo_root)
        run(["git", "commit", "-q", "-m", "init"], cwd=repo_root)

        # Worker's own PR commit fabricates an entirely new phase block
        # from scratch, self-reporting done with no gh-confirmed merge.
        with open(plan_path, "a") as f:
            f.write(textwrap.dedent("""\
                - id: phase_z_fabricated
                  name: Phase fabricated whole-cloth by a bypassing worker
                  depends_on: []
                  status: done
                  target_repo: fake-target-repo
                  completed_by_task: task-20260726-050000-fabricated-bypass
                  evidence: 'fake-target-repo branch worker/task-20260726-050000-fabricated-bypass'
                """))
        run(["git", "add", "-A"], cwd=repo_root)
        run(["git", "commit", "-q", "-m",
             "phase_z: status done (fake-target-repo branch "
             "worker/task-20260726-050000-fabricated-bypass)"],
            cwd=repo_root)

        run(["git", "init", "-q", "--bare", remote])
        run(["git", "remote", "add", "origin", remote], cwd=repo_root)
        run(["git", "push", "-q", "-u", "origin", "master"], cwd=repo_root)

        gh_path = os.path.join(bin_dir, "gh")
        with open(gh_path, "w") as f:
            f.write(textwrap.dedent("""\
                #!/bin/bash
                if [ "$1" = "pr" ] && [ "$2" = "list" ]; then
                  echo '[{"state":"OPEN","number":3001,"mergedAt":null}]'
                  exit 0
                fi
                exit 0
                """))
        os.chmod(gh_path, 0o755)

        env = dict(os.environ)
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        env["VERIDIAN_REPO_ROOT_OVERRIDE"] = repo_root
        env["VERIDIAN_TASKS_DIR_OVERRIDE"] = tasks_dir

        log_before = run(["git", "log", "--oneline"], cwd=repo_root).stdout
        check("fabricated block fixture: 2 real commits before the audit runs",
              len(log_before.strip().splitlines()) == 2)

        proc = run(["python3", SCRIPT, "--audit-plans"], env=env)
        out = json.loads(proc.stdout)
        check("fabricated block: audit exits 0", proc.returncode == 0)
        check("fabricated block: reports changed=True (incident-only commit persists the finding)",
              out.get("changed") is True)
        check("fabricated block: exactly one real incident recorded",
              len(out.get("incidents") or []) == 1)
        check("fabricated block: incident names the bypassing task id",
              "task-20260726-050000-fabricated-bypass" in (out.get("incidents") or [""])[0])
        check("fabricated block: incident explains no parent state exists",
              "fabricated" in (out.get("incidents") or [""])[0].lower())

        with open(plan_path) as f:
            content = f.read()
        check("fabricated block: file left untouched (nothing to revert to)",
              "status: done" in content and "task-20260726-050000-fabricated-bypass" in content)

        log_after = run(["git", "log", "--oneline"], cwd=repo_root).stdout
        check("fabricated block: an incident-only commit landed (persists past process exit)",
              len(log_after.strip().splitlines()) == len(log_before.strip().splitlines()) + 1)
        check("fabricated block: the incident-only commit changed no files (nothing to revert to)",
              run(["git", "diff", "--stat", "HEAD~1", "HEAD"], cwd=repo_root).stdout.strip() == "")
        check("fabricated block: incident-only commit message names the bypassing task id",
              "task-20260726-050000-fabricated-bypass" in
              run(["git", "log", "-1", "--format=%B"], cwd=repo_root).stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scenario_audit_reverts_two_violations_in_one_file():
    """Reviewer-reproduced regression (AUDIT: REJECT on this same fix's
    previous round): a single plan file with TWO separate phases both
    falsely self-reporting done, where the FIRST violation's revert
    deletes lines -- its parent revision has no completed_by_task/evidence
    fields at all, so revert_block_fields() deletes those 2 lines outright
    rather than overwriting them in place.

    The real bug: audit_and_correct_plan_file()'s while-loop reverted the
    first violation (phase_b), wrote the now-shorter file to disk, then
    re-read that mutated file and computed the SECOND violation's (phase_c)
    status-line number against it -- but blamed that line via `git blame
    HEAD`, where HEAD still pointed at the larger, pre-revert commit (the
    revert hadn't been committed yet). The 2-line offset meant the "status
    line" blame_line() actually blamed was, in HEAD's real tree, a
    different line entirely (phase_c's own untouched `depends_on: []`
    line) -- which had last been touched by this repo's own root/init
    commit. Since blame_line() passes `-l` (full hash) but no `--root`,
    `git blame` prefixed that line's hash with its own boundary-commit '^'
    marker, producing a corrupted "hash" string. The `{hash}^` parent
    lookup on that corrupted string then failed, phase_c's false
    self-report was left un-reverted, and the run still auto-committed and
    pushed phase_b's real revert plus a misleading "could not auto-revert"
    incident for phase_c straight to master.

    This locks in the fix: both violations must be correctly reverted, in
    one pass, each attributed to its OWN real, well-formed (non-'^') commit
    hash -- not the other's, not a corrupted boundary marker.
    """
    tmp = tempfile.mkdtemp(prefix="backfill_audit_twoviol_test_")
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

        plan_path = os.path.join(repo_root, "ai-os", "FAKE_TWOVIOL_PHASE_PLAN_2026-07-25.yaml")
        with open(plan_path, "w") as f:
            f.write(textwrap.dedent("""\
                meta:
                  title: Fake Two-violation Initiative
                phases:
                - id: phase_a_legit
                  name: Legit phase
                  depends_on: []
                  status: done
                  target_repo: fake-target-repo
                  completed_by_task: task-20260101-000030-legit
                  evidence: 'fake-target-repo PR #4000 merged 2026-07-26T07:00:00Z'
                - id: phase_b_bypass
                  name: First bypassed phase (revert deletes lines)
                  depends_on: []
                  status: not_started
                  target_repo: fake-target-repo
                - id: phase_c_bypass
                  name: Second bypassed phase (must still get correct blame)
                  depends_on: []
                  status: not_started
                  target_repo: fake-target-repo
                """))
        run(["git", "add", "-A"], cwd=repo_root)
        run(["git", "commit", "-q", "-m", "init"], cwd=repo_root)

        # Bypass commit #1: phase_b, its own separate commit (own distinct
        # blame hash). Its parent (the init commit above) has no
        # completed_by_task/evidence fields at all, so reverting it deletes
        # those 2 lines outright -- the exact shape that shrinks the file.
        with open(plan_path) as f:
            content = f.read()
        content = content.replace(
            "- id: phase_b_bypass\n"
            "  name: First bypassed phase (revert deletes lines)\n"
            "  depends_on: []\n"
            "  status: not_started\n"
            "  target_repo: fake-target-repo\n",
            "- id: phase_b_bypass\n"
            "  name: First bypassed phase (revert deletes lines)\n"
            "  depends_on: []\n"
            "  status: done\n"
            "  target_repo: fake-target-repo\n"
            "  completed_by_task: task-20260726-060000-bypass-b\n"
            "  evidence: 'fake-target-repo branch worker/task-20260726-060000-bypass-b'\n",
        )
        with open(plan_path, "w") as f:
            f.write(content)
        run(["git", "add", "-A"], cwd=repo_root)
        run(["git", "commit", "-q", "-m",
             "phase_b bypass: status done (fake-target-repo branch worker/task-20260726-060000-bypass-b)"],
            cwd=repo_root)
        bypass_b_hash = run(["git", "rev-parse", "--short=7", "HEAD"], cwd=repo_root).stdout.strip()

        # Bypass commit #2: phase_c, its own separate commit (own distinct
        # blame hash) -- must still resolve correctly after phase_b's
        # revert shrinks the file.
        with open(plan_path) as f:
            content = f.read()
        content = content.replace(
            "- id: phase_c_bypass\n"
            "  name: Second bypassed phase (must still get correct blame)\n"
            "  depends_on: []\n"
            "  status: not_started\n"
            "  target_repo: fake-target-repo\n",
            "- id: phase_c_bypass\n"
            "  name: Second bypassed phase (must still get correct blame)\n"
            "  depends_on: []\n"
            "  status: done\n"
            "  target_repo: fake-target-repo\n"
            "  completed_by_task: task-20260726-060500-bypass-c\n"
            "  evidence: 'fake-target-repo branch worker/task-20260726-060500-bypass-c'\n",
        )
        with open(plan_path, "w") as f:
            f.write(content)
        run(["git", "add", "-A"], cwd=repo_root)
        run(["git", "commit", "-q", "-m",
             "phase_c bypass: status done (fake-target-repo branch worker/task-20260726-060500-bypass-c)"],
            cwd=repo_root)
        bypass_c_hash = run(["git", "rev-parse", "--short=7", "HEAD"], cwd=repo_root).stdout.strip()

        run(["git", "init", "-q", "--bare", remote])
        run(["git", "remote", "add", "origin", remote], cwd=repo_root)
        run(["git", "push", "-q", "-u", "origin", "master"], cwd=repo_root)

        gh_path = os.path.join(bin_dir, "gh")
        with open(gh_path, "w") as f:
            f.write(textwrap.dedent("""\
                #!/bin/bash
                if [ "$1" = "pr" ] && [ "$2" = "list" ]; then
                  head=""
                  prev=""
                  for arg in "$@"; do
                    if [ "$prev" = "--head" ]; then
                      head="$arg"
                    fi
                    prev="$arg"
                  done
                  if [ "$head" = "worker/task-20260101-000030-legit" ]; then
                    echo '[{"state":"MERGED","number":4000,"mergedAt":"2026-07-26T07:00:00Z"}]'
                  else
                    echo '[{"state":"OPEN","number":4001,"mergedAt":null}]'
                  fi
                  exit 0
                fi
                exit 0
                """))
        os.chmod(gh_path, 0o755)

        env = dict(os.environ)
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        env["VERIDIAN_REPO_ROOT_OVERRIDE"] = repo_root
        env["VERIDIAN_TASKS_DIR_OVERRIDE"] = tasks_dir

        log_before = run(["git", "log", "--oneline", "--", "ai-os/FAKE_TWOVIOL_PHASE_PLAN_2026-07-25.yaml"],
                          cwd=repo_root).stdout
        check("two-violation fixture: 3 real commits touched the plan file before the audit runs",
              len(log_before.strip().splitlines()) == 3)

        proc = run(["python3", SCRIPT, "--audit-plans"], env=env)
        out = json.loads(proc.stdout)
        check("two-violation audit: exits 0", proc.returncode == 0)
        check("two-violation audit: reports changed=True", out.get("changed") is True)

        incidents = out.get("incidents") or []
        check("two-violation audit: exactly two incidents recorded (both reverted, none un-corrected)",
              len(incidents) == 2)
        check("two-violation audit: no incident reports a failed auto-revert",
              all("could NOT" not in inc for inc in incidents))

        b_incident = next((i for i in incidents if "task-20260726-060000-bypass-b" in i), None)
        c_incident = next((i for i in incidents if "task-20260726-060500-bypass-c" in i), None)
        check("two-violation audit: phase_b's incident recorded", b_incident is not None)
        check("two-violation audit: phase_c's incident recorded", c_incident is not None)
        if b_incident:
            b_hash_cited = b_incident.split("commit ")[-1].split(" ")[0]
            check("two-violation audit: phase_b's incident cites its OWN real, well-formed commit hash",
                  b_hash_cited == bypass_b_hash and "^" not in b_hash_cited)
        if c_incident:
            c_hash_cited = c_incident.split("commit ")[-1].split(" ")[0]
            check("two-violation audit: phase_c's incident cites its OWN real, well-formed commit hash "
                  "(not corrupted, not phase_b's hash)",
                  c_hash_cited == bypass_c_hash and c_hash_cited != bypass_b_hash and "^" not in c_hash_cited)

        with open(plan_path) as f:
            content = f.read()
        b_block = content.split("phase_b_bypass")[1].split("phase_c_bypass")[0]
        c_block = content.split("phase_c_bypass")[1]
        check("two-violation audit: phase_b reverted to not_started", "status: not_started\n" in b_block)
        check("two-violation audit: phase_b's fake completed_by_task removed",
              "task-20260726-060000-bypass-b" not in content)
        check("two-violation audit: phase_c reverted to not_started", "status: not_started\n" in c_block)
        check("two-violation audit: phase_c's fake completed_by_task removed",
              "task-20260726-060500-bypass-c" not in content)
        check("two-violation audit: phase_a (real merged PR) left completely untouched",
              "status: done" in content.split("phase_b_bypass")[0]
              and "task-20260101-000030-legit" in content)

        log_after = run(["git", "log", "--oneline", "--", "ai-os/FAKE_TWOVIOL_PHASE_PLAN_2026-07-25.yaml"],
                         cwd=repo_root).stdout
        check("two-violation audit: exactly one new revert commit landed (both reverts, one commit)",
              len(log_after.strip().splitlines()) == 4)

        proc2 = run(["python3", SCRIPT, "--audit-plans"], env=env)
        out2 = json.loads(proc2.stdout)
        check("two-violation audit idempotency: re-running after both reverts finds nothing more to fix",
              out2.get("changed") is False and out2.get("incidents") == [])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


ALL_SCENARIOS = [
    scenario_merged_missing_self_report,
    scenario_already_self_reported_untouched,
    scenario_not_merged_skipped,
    scenario_dry_run_makes_no_commit,
    scenario_indented_phase_int_schema,
    scenario_sweep_tier2_checkpoints,
    scenario_audit_reverts_worker_bypass_self_report,
    scenario_audit_skips_ambiguous_gh_failure,
    scenario_audit_flags_missing_target_repo,
    scenario_audit_records_incident_for_fabricated_block_no_parent,
    scenario_audit_reverts_two_violations_in_one_file,
]


# ---------------------------------------------------------------------------
# pytest entry points -- `python3 -m pytest tests/backfill_phase_self_report_
# test.py` collects functions matching `test_*` by default; the scenarios
# above are intentionally named `scenario_*` (this file's own convention,
# predating pytest use, still run directly via `python3 tests/....py` in
# the __main__ block below) so these thin wrappers are what pytest actually
# discovers and runs. Each wrapper only asserts on the failures its own
# scenario adds to the shared FAILURES list, so one scenario's failure
# doesn't fail every other test in the same run.
# ---------------------------------------------------------------------------

def _run_scenario_for_pytest(fn):
    start = len(FAILURES)
    fn()
    new_failures = FAILURES[start:]
    assert not new_failures, f"{fn.__name__}: {new_failures}"


def test_merged_missing_self_report():
    _run_scenario_for_pytest(scenario_merged_missing_self_report)


def test_already_self_reported_untouched():
    _run_scenario_for_pytest(scenario_already_self_reported_untouched)


def test_not_merged_skipped():
    _run_scenario_for_pytest(scenario_not_merged_skipped)


def test_dry_run_makes_no_commit():
    _run_scenario_for_pytest(scenario_dry_run_makes_no_commit)


def test_indented_phase_int_schema():
    _run_scenario_for_pytest(scenario_indented_phase_int_schema)


def test_sweep_tier2_checkpoints():
    _run_scenario_for_pytest(scenario_sweep_tier2_checkpoints)


def test_audit_reverts_worker_bypass_self_report():
    _run_scenario_for_pytest(scenario_audit_reverts_worker_bypass_self_report)


def test_audit_skips_ambiguous_gh_failure():
    _run_scenario_for_pytest(scenario_audit_skips_ambiguous_gh_failure)


def test_audit_flags_missing_target_repo():
    _run_scenario_for_pytest(scenario_audit_flags_missing_target_repo)


def test_audit_records_incident_for_fabricated_block_no_parent():
    _run_scenario_for_pytest(scenario_audit_records_incident_for_fabricated_block_no_parent)


def test_audit_reverts_two_violations_in_one_file():
    _run_scenario_for_pytest(scenario_audit_reverts_two_violations_in_one_file)


if __name__ == "__main__":
    for scenario in ALL_SCENARIOS:
        scenario()

    if FAILURES:
        print(f"\n{len(FAILURES)} scenario(s) failed.")
        sys.exit(1)
    print("\nAll scenarios passed.")
    sys.exit(0)
