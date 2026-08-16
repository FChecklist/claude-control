#!/usr/bin/env python3
"""
Regression test for veridian-task.py's cmd_checkpoint() real-branch
resolution fix (2026-07-26, root-caused against the PR561/PR562/PR78
corrective-fix incidents).

Before this fix, task.yaml's 'branch' field was set once at cmd_create time
(always f"worker/{task_id}") and never updated. When a corrective task's own
dispatch prompt instructed the worker to check out and push its real commits
to a different, pre-existing branch instead, supervisor-entrypoint.sh kept
using the stale creation-time value for `gh pr create --head`/`gh pr list
--head`, so it could never find a PR to comment on or merge -- a human had
to intervene every time.

Imports the REAL veridian-task.py module (via importlib, since the filename
is not a valid Python identifier) and calls its real cmd_checkpoint()
against a throwaway git workspace and task.yaml, monkeypatching only the
module-level path constants (AI_OS/CONTROLLER/CONTROLLER_LOCK) and the
best-effort telemetry functions (_auto_log_task_event/_sync_to_app -- both
already no-op on failure in production, disabled here purely so this test
never makes a real subprocess/network call against the live server this
happens to run on). This cannot drift from what actually ships, unlike a
reimplementation of the branch-resolution logic.
"""
import argparse
import importlib.util
import os
import shutil
import subprocess
import tempfile

import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(REPO_ROOT, "scripts", "veridian-task.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("veridian_task_under_test", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _make_fixture(tmp):
    ai_os_root = os.path.join(tmp, "ai_os")
    task_id = "task-fake-branch-resolution"
    task_dir = os.path.join(ai_os_root, "tasks", task_id)
    workspace = os.path.join(task_dir, "workspace")
    os.makedirs(workspace)

    _git("init", "-q", cwd=workspace)
    _git("config", "user.email", "test@example.com", cwd=workspace)
    _git("config", "user.name", "Test", cwd=workspace)
    with open(os.path.join(workspace, "README.md"), "w") as f:
        f.write("initial\n")
    _git("add", "-A", cwd=workspace)
    _git("commit", "-q", "-m", "initial", cwd=workspace)

    # Mirrors cmd_create's `git worktree add -b <branch>` -- the workspace
    # really is checked out onto its own task-derived branch at creation time.
    original_branch = f"worker/{task_id}"
    _git("checkout", "-q", "-b", original_branch, cwd=workspace)

    task = {
        "id": task_id,
        "title": "fake corrective task",
        "status": "in_progress",
        "repo": "claude-control",
        "branch": original_branch,
        "workspace": workspace,
        "task_dir": task_dir,
        "service": f"veridian-worker@{task_id}.service",
        "created_at": "2026-07-26T00:00:00+00:00",
        "last_checkpoint_at": None,
        "completed_steps": [],
        "remaining_steps": [],
        "files_modified": [],
        "checkpoints": [],
        "execution_seconds": 0,
        "restart_count": 0,
        "token_usage": None,
        "hold_for_owner_signoff": False,
    }
    with open(os.path.join(task_dir, "task.yaml"), "w") as f:
        yaml.safe_dump(task, f, sort_keys=False)

    with open(os.path.join(ai_os_root, "CONTROLLER.yaml"), "w") as f:
        yaml.safe_dump({"server": "TEST", "tasks": []}, f)

    return ai_os_root, task_dir, workspace, task_id, original_branch


def _run_checkpoint(mod, ai_os_root, task_id, status, note):
    mod.AI_OS = ai_os_root
    mod.CONTROLLER = f"{ai_os_root}/CONTROLLER.yaml"
    mod.CONTROLLER_LOCK = f"{ai_os_root}/.controller.lock"
    # Best-effort telemetry only -- disabled so this test never fires a real
    # subprocess/network call against the live server it happens to run on.
    mod._auto_log_task_event = lambda *a, **kw: None
    mod._sync_to_app = lambda *a, **kw: None

    args = argparse.Namespace(task_id=task_id, status=status, note=note, auto=False)
    mod.cmd_checkpoint(args)


def test_branch_resolution_reflects_real_worker_pushed_branch():
    """PR561/PR562/PR78 repro: worker's real commits landed on a different,
    pre-existing branch than its own task-derived one -- the checkpoint that
    hands off to supervisor-entrypoint.sh must record the REAL branch."""
    tmp = tempfile.mkdtemp(prefix="branch_resolution_test_")
    try:
        ai_os_root, task_dir, workspace, task_id, original_branch = _make_fixture(tmp)

        real_branch = "hotfix/pr563-corrective-fix"
        _git("checkout", "-q", "-b", real_branch, cwd=workspace)
        with open(os.path.join(workspace, "fix.txt"), "w") as f:
            f.write("real corrective commit\n")
        _git("add", "-A", cwd=workspace)
        _git("commit", "-q", "-m", "real corrective fix, pushed to pre-existing branch", cwd=workspace)

        mod = _load_module()
        _run_checkpoint(mod, ai_os_root, task_id, "pending_review", "quality gates passed, awaiting review")

        with open(os.path.join(task_dir, "task.yaml")) as f:
            saved = yaml.safe_load(f)

        assert saved["branch"] == real_branch, (
            f"expected task.yaml branch to be updated to the REAL current branch "
            f"'{real_branch}', got '{saved['branch']}' (still the stale creation-time "
            f"value '{original_branch}' -- this is exactly the PR561/562/78 bug)"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_branch_resolution_prefers_upstream_over_local_alias():
    """task-20260726-105110 repro: the worker checked out a LOCAL branch
    ('pr80-work') that tracks the real remote branch
    ('worker/task-...-083833-...') and pushed its real commits there via the
    tracking relationship. `rev-parse --abbrev-ref HEAD` returns the local
    alias, not the remote branch supervisor-entrypoint.sh actually needs for
    `gh pr create --head`/`gh pr list --head` -- so the resolved branch must
    come from the upstream tracking ref, not the local checked-out name."""
    tmp = tempfile.mkdtemp(prefix="branch_resolution_test_")
    try:
        ai_os_root, task_dir, workspace, task_id, original_branch = _make_fixture(tmp)

        # Simulate a real remote: a bare repo the workspace can push to and
        # track, so `@{upstream}` reflects a genuine tracking relationship
        # rather than just another local branch.
        remote_dir = os.path.join(tmp, "remote.git")
        _git("init", "-q", "--bare", remote_dir, cwd=tmp)
        _git("remote", "add", "origin", remote_dir, cwd=workspace)
        _git("push", "-q", "origin", f"{original_branch}:{original_branch}", cwd=workspace)

        real_remote_branch = "worker/task-20260726-083833-build-interactive-session-write-gate--re"
        _git("push", "-q", "origin", f"{original_branch}:{real_remote_branch}", cwd=workspace)

        local_alias = "pr80-work"
        _git("checkout", "-q", "-b", local_alias, f"origin/{real_remote_branch}", cwd=workspace)
        with open(os.path.join(workspace, "fix.txt"), "w") as f:
            f.write("real corrective commit pushed via tracking relationship\n")
        _git("add", "-A", cwd=workspace)
        _git("commit", "-q", "-m", "real corrective fix, pushed via tracked upstream", cwd=workspace)
        _git("push", "-q", "origin", f"{local_alias}:{real_remote_branch}", cwd=workspace)

        mod = _load_module()
        _run_checkpoint(mod, ai_os_root, task_id, "pending_review", "quality gates passed, awaiting review")

        with open(os.path.join(task_dir, "task.yaml")) as f:
            saved = yaml.safe_load(f)

        assert saved["branch"] == real_remote_branch, (
            f"expected task.yaml branch to be updated to the REAL remote tracking "
            f"branch '{real_remote_branch}', got '{saved['branch']}' (resolved to the "
            f"local checked-out alias instead -- this is exactly the pr80-work bug)"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_branch_resolution_noop_when_still_on_original_branch():
    """Baseline: a normal task that never diverges keeps its original branch
    (this fix must not corrupt the common, non-divergent case)."""
    tmp = tempfile.mkdtemp(prefix="branch_resolution_test_")
    try:
        ai_os_root, task_dir, workspace, task_id, original_branch = _make_fixture(tmp)

        with open(os.path.join(workspace, "normal.txt"), "w") as f:
            f.write("normal commit\n")
        _git("add", "-A", cwd=workspace)
        _git("commit", "-q", "-m", "normal work on the original branch", cwd=workspace)

        mod = _load_module()
        _run_checkpoint(mod, ai_os_root, task_id, "pending_review", "quality gates passed, awaiting review")

        with open(os.path.join(task_dir, "task.yaml")) as f:
            saved = yaml.safe_load(f)

        assert saved["branch"] == original_branch
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_branch_resolution_not_corrupted_to_default_branch_before_first_push():
    """Real root cause found live (2026-07-27) against 2 stuck rca- tasks whose
    task.yaml ended up with branch: master, which then made
    supervisor-entrypoint.sh fail with "supervisor could not resolve a real PR
    for branch 'master'": cmd_create's real invocation
    (`git worktree add -b <branch> workspace origin/<default>`) checks the new
    branch out FROM a remote-tracking ref, and git's own
    branch.autoSetupMerge default means that new branch's @{upstream} points
    at origin/<default> from the INSTANT it is created -- before any commit or
    push. Any checkpoint that runs before the first real `git push -u origin
    <branch>` (e.g. the very first in_progress checkpoint, or any checkpoint on
    a task that never gets past pre-flight, exactly what happened to both real
    stuck instances) must not mistake that default fork-point tracking ref for
    a real, already-pushed branch name."""
    tmp = tempfile.mkdtemp(prefix="branch_resolution_test_")
    try:
        ai_os_root = os.path.join(tmp, "ai_os")
        task_id = "task-fake-fresh-branch-never-pushed"
        task_dir = os.path.join(ai_os_root, "tasks", task_id)
        workspace = os.path.join(task_dir, "workspace")
        os.makedirs(workspace)

        # Real remote with a "master" default branch (matches this repo's own
        # real default branch, and the exact literal observed live).
        remote_dir = os.path.join(tmp, "remote.git")
        _git("init", "-q", "--bare", remote_dir, cwd=tmp)
        seed = os.path.join(tmp, "seed")
        os.makedirs(seed)
        _git("init", "-q", cwd=seed)
        _git("config", "user.email", "test@example.com", cwd=seed)
        _git("config", "user.name", "Test", cwd=seed)
        with open(os.path.join(seed, "README.md"), "w") as f:
            f.write("initial\n")
        _git("add", "-A", cwd=seed)
        _git("commit", "-q", "-m", "initial", cwd=seed)
        _git("branch", "-M", "master", cwd=seed)
        _git("remote", "add", "origin", remote_dir, cwd=seed)
        _git("push", "-q", "origin", "master", cwd=seed)

        # Mirrors cmd_create exactly: `git worktree add -b <branch> workspace
        # origin/<default>` off a real clone (not a plain local checkout) --
        # this remote-tracking start point is what triggers
        # branch.autoSetupMerge, which the prior fixture (_make_fixture, a
        # plain local `checkout -b` with no remote at all) never exercised.
        _git("clone", "-q", remote_dir, workspace, cwd=tmp)
        _git("remote", "set-head", "origin", "master", cwd=workspace)
        original_branch = f"worker/{task_id}"
        _git("checkout", "-q", "-b", original_branch, "origin/master", cwd=workspace)

        # No commit, no push -- exactly the state of a task whose worker never
        # got past pre-flight (both real stuck instances: 3-5 consecutive
        # PRE-FLIGHT REJECTED checkpoints, zero real commits, zero pushes).

        task = {
            "id": task_id,
            "title": "fake rca task, never got past pre-flight",
            "status": "failed",
            "repo": "compliance-tracker",
            "branch": original_branch,
            "workspace": workspace,
            "task_dir": task_dir,
            "service": f"veridian-worker@{task_id}.service",
            "created_at": "2026-07-27T00:00:00+00:00",
            "last_checkpoint_at": None,
            "completed_steps": [],
            "remaining_steps": [],
            "files_modified": [],
            "checkpoints": [],
            "execution_seconds": 0,
            "restart_count": 0,
            "token_usage": None,
            "hold_for_owner_signoff": False,
        }
        with open(os.path.join(task_dir, "task.yaml"), "w") as f:
            yaml.safe_dump(task, f, sort_keys=False)
        with open(os.path.join(ai_os_root, "CONTROLLER.yaml"), "w") as f:
            yaml.safe_dump({"server": "TEST", "tasks": []}, f)

        mod = _load_module()
        _run_checkpoint(mod, ai_os_root, task_id, "failed",
                         "PRE-FLIGHT REJECTED (crontab_unauthorized_change, transient): no model call made")

        with open(os.path.join(task_dir, "task.yaml")) as f:
            saved = yaml.safe_load(f)

        assert saved["branch"] == original_branch, (
            f"expected task.yaml branch to stay the real worker branch "
            f"'{original_branch}', got '{saved['branch']}' -- if this is 'master' "
            f"(the repo's own default branch), that is exactly the live bug: git's "
            f"default fork-point tracking ref was mistaken for a real pushed branch "
            f"before any push ever happened."
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _load_watchdog_bound_to_governor_fixture(tmp_path, monkeypatch, module_name):
    """2026-07-27 (SERVER RESOURCE GOVERNOR): escalate() now calls
    resource_governor.submit() -- a plain `import resource_governor` inside
    veridian-task-watchdog.py, since both files share scripts/ -- instead of
    invoking subprocess.run directly. That plain import is cached process-wide
    in sys.modules, so each test here must force a fresh import bound to ITS
    OWN throwaway env (popping any stale cached module first), otherwise a
    second test in the same pytest session would silently keep writing to the
    first test's already-torn-down tmp_path DB."""
    import sys as _sys
    for stale in ("resource_governor", "dispatch_core_governor", "superboss_register_governor"):
        _sys.modules.pop(stale, None)

    ai_os = tmp_path / "ai-os"
    (ai_os / "locks").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("VERIDIAN_ROOT", str(tmp_path))
    monkeypatch.setenv("VERIDIAN_AI_OS_DIR", str(ai_os))
    monkeypatch.setenv("VERIDIAN_SCRIPTS_DIR", os.path.join(REPO_ROOT, "scripts"))
    monkeypatch.setenv("VERIDIAN_DISPATCH_LOCK_DIR", str(ai_os / "locks"))
    monkeypatch.setenv("SUPERBOSS_REGISTER_DB", str(ai_os / "test-superboss.sqlite"))

    import importlib.util as _ilu
    watchdog_path = os.path.join(REPO_ROOT, "scripts", "veridian-task-watchdog.py")
    spec = _ilu.spec_from_file_location(module_name, watchdog_path)
    wd = _ilu.module_from_spec(spec)
    spec.loader.exec_module(wd)
    return wd


def _umr_inputs_for_identity(task_identity):
    import json
    import sqlite3
    conn = sqlite3.connect(os.environ["SUPERBOSS_REGISTER_DB"])
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT inputs_json FROM umr_tasks WHERE task_identity=? ORDER BY ts_submitted DESC LIMIT 1",
        (task_identity,),
    ).fetchone()
    conn.close()
    assert row is not None, f"escalate() never submitted a umr_tasks row for task_identity={task_identity!r}"
    return json.loads(row["inputs_json"])


def test_escalate_passes_stalled_tasks_real_repo_not_hardcoded_claude_control(tmp_path, monkeypatch):
    """Real bug confirmed live in the deployed veridian-task-watchdog.py:
    escalate() hardcoded --repo claude-control for every auto-escalated rca-
    task regardless of the stalled task's own real repo -- confirmed against 2
    historical instances whose stalled task's real repo was compliance-tracker.
    escalate() must read the stalled task's own already-loaded task.yaml
    'repo' field instead. escalate() now submits (via resource_governor.py,
    ai-os/SERVER_RESOURCE_GOVERNOR_2026-07-27.md) rather than calling
    veridian-task.py create directly -- this asserts the real repo made it
    into the queued task_spec's inputs."""
    wd = _load_watchdog_bound_to_governor_fixture(tmp_path, monkeypatch, "veridian_task_watchdog_under_test")

    stalled_task = {
        "id": "task-20260726-172000-hr-performance-error-handling---payroll",
        "repo": "compliance-tracker",
        "branch": "worker/task-20260726-172000-hr-performance-error-handling---payroll",
        "status": "blocked",
    }
    result_msg = wd.escalate("task-20260726-172000-hr-performance-error-handling---payroll",
                              stalled_task, "some failure signature")
    assert "escalation queued via resource governor" in result_msg, result_msg

    inputs = _umr_inputs_for_identity("rca-task-20260726-172000-hr-performance-error-handling---payroll")
    assert inputs["repo"] == "compliance-tracker", (
        f"expected escalate() to pass the stalled task's own real repo "
        f"'compliance-tracker', got {inputs.get('repo')!r} -- this is exactly the live "
        f"hardcoded-claude-control bug"
    )


def test_escalate_falls_back_to_claude_control_when_repo_unknown(tmp_path, monkeypatch):
    """Defensive fallback: if the stalled task's own task.yaml is somehow
    unreadable/missing a 'repo' field, escalate() must still queue a valid
    repo (the pre-fix default) rather than crash or pass repo=None."""
    wd = _load_watchdog_bound_to_governor_fixture(tmp_path, monkeypatch, "veridian_task_watchdog_under_test_fallback")

    result_msg = wd.escalate("task-with-unreadable-yaml", None, "some failure signature")
    assert "escalation queued via resource governor" in result_msg, result_msg

    inputs = _umr_inputs_for_identity("rca-task-with-unreadable-yaml")
    assert inputs["repo"] == "claude-control"


if __name__ == "__main__":
    test_branch_resolution_reflects_real_worker_pushed_branch()
    test_branch_resolution_prefers_upstream_over_local_alias()
    test_branch_resolution_noop_when_still_on_original_branch()
    test_branch_resolution_not_corrupted_to_default_branch_before_first_push()
    test_escalate_passes_stalled_tasks_real_repo_not_hardcoded_claude_control()
    test_escalate_falls_back_to_claude_control_when_repo_unknown()
    print("All branch_resolution scenarios passed.")
