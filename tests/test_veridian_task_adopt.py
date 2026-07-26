#!/usr/bin/env python3
"""
Regression tests for veridian-task.py's `adopt` command (2026-07-26, closes
the gap where claude-control PR #84 -- a real branch-recovery PR created
OUTSIDE the normal task-gateway.py -> cmd_create dispatch flow -- had zero
task_dir/task.yaml entry and was therefore permanently invisible to
supervisor-sweep.sh's discovery loop, which only globs
/opt/veridian/ai-os/tasks/*/task.yaml).

Imports the REAL veridian-task.py module (via importlib, since the filename
is not a valid Python identifier) and calls its real cmd_adopt() against a
throwaway git "origin" + repo clone, monkeypatching only the module-level
path constants (AI_OS/CONTROLLER/CONTROLLER_LOCK/REPOS) and the best-effort
telemetry functions (_auto_log_task_event/_sync_to_app), matching the same
convention as veridian_task_branch_resolution_test.py. This cannot drift from
what actually ships, unlike a reimplementation of the adopt logic.
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
    spec = importlib.util.spec_from_file_location("veridian_task_under_test_adopt", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _make_fixture(tmp, branch_name="recovered-lifecycle-fix-fake"):
    """Builds a fake bare 'origin' plus a real /opt/veridian/repos/<repo>-style
    clone, with a real existing branch (simulating a PR's head branch created
    outside cmd_create) pushed to that origin -- mirroring PR #84's actual
    shape (a branch that exists on GitHub with real commits, but no task_dir)."""
    origin_path = os.path.join(tmp, "origin.git")
    os.makedirs(origin_path)
    _git("init", "-q", "--bare", "--initial-branch=master", cwd=origin_path)

    seed_path = os.path.join(tmp, "seed")
    os.makedirs(seed_path)
    _git("init", "-q", "--initial-branch=master", cwd=seed_path)
    _git("config", "user.email", "test@example.com", cwd=seed_path)
    _git("config", "user.name", "Test", cwd=seed_path)
    with open(os.path.join(seed_path, "README.md"), "w") as f:
        f.write("initial\n")
    _git("add", "-A", cwd=seed_path)
    _git("commit", "-q", "-m", "initial", cwd=seed_path)
    _git("remote", "add", "origin", origin_path, cwd=seed_path)
    _git("push", "-q", "origin", "master", cwd=seed_path)

    _git("checkout", "-q", "-b", branch_name, cwd=seed_path)
    with open(os.path.join(seed_path, "recovered.txt"), "w") as f:
        f.write("real recovered work\n")
    _git("add", "-A", cwd=seed_path)
    _git("commit", "-q", "-m", "real recovered commit, never dispatched via cmd_create", cwd=seed_path)
    _git("push", "-q", "origin", branch_name, cwd=seed_path)

    repos_root = os.path.join(tmp, "repos")
    os.makedirs(repos_root)
    repo_path = os.path.join(repos_root, "fake-repo")
    _git("clone", "-q", origin_path, repo_path, cwd=repos_root)
    _git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/master", cwd=repo_path)

    ai_os_root = os.path.join(tmp, "ai_os")
    os.makedirs(os.path.join(ai_os_root, "tasks"))
    with open(os.path.join(ai_os_root, "CONTROLLER.yaml"), "w") as f:
        yaml.safe_dump({"server": "TEST", "tasks": []}, f)

    return ai_os_root, repos_root, repo_path


def _patch_module(mod, ai_os_root, repos_root):
    mod.AI_OS = ai_os_root
    mod.CONTROLLER = f"{ai_os_root}/CONTROLLER.yaml"
    mod.CONTROLLER_LOCK = f"{ai_os_root}/.controller.lock"
    mod.REPOS = repos_root
    # Best-effort telemetry only -- disabled so this test never fires a real
    # subprocess/network call against the live server it happens to run on.
    mod._auto_log_task_event = lambda *a, **kw: None
    mod._sync_to_app = lambda *a, **kw: None


def test_adopt_creates_pending_review_task_with_no_review_json():
    """The core gap-2 fix: adopting an existing branch/PR must produce a real
    task_dir/task.yaml -- status pending_review, no review.json -- exactly
    the shape supervisor-sweep.sh's discovery loop looks for."""
    tmp = tempfile.mkdtemp(prefix="adopt_test_")
    try:
        ai_os_root, repos_root, repo_path = _make_fixture(tmp)
        mod = _load_module()
        _patch_module(mod, ai_os_root, repos_root)

        args = argparse.Namespace(
            title="Recover lifecycle-fix commit (PR84)",
            repo="fake-repo",
            branch="recovered-lifecycle-fix-fake",
            pr_url="https://github.com/FChecklist/fake-repo/pull/84",
            task_id="task-adopted-fake-pr84",
            prompt=None,
        )
        mod.cmd_adopt(args)

        task_dir = os.path.join(ai_os_root, "tasks", "task-adopted-fake-pr84")
        task_yaml_path = os.path.join(task_dir, "task.yaml")
        assert os.path.isfile(task_yaml_path), "adopt did not create task.yaml"
        assert not os.path.isfile(os.path.join(task_dir, "review.json")), (
            "adopt must NOT write a review.json -- supervisor-sweep.sh only "
            "picks up pending_review tasks that lack one"
        )

        with open(task_yaml_path) as f:
            task = yaml.safe_load(f)
        assert task["status"] == "pending_review"
        assert task["branch"] == "recovered-lifecycle-fix-fake"
        assert task["repo"] == "fake-repo"
        assert task["adopted"] is True
        assert task["adopted_pr_url"] == "https://github.com/FChecklist/fake-repo/pull/84"

        workspace = task["workspace"]
        assert os.path.isdir(workspace)
        log = _git("log", "--oneline", "-1", cwd=workspace).stdout
        assert "real recovered commit" in log
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_adopt_falls_back_to_detached_checkout_when_branch_already_in_use():
    """PR #84 repro: the same branch was already checked out in another
    task's own workspace worktree at the time of the accidental merge --
    adopt must not fail just because the branch name is already in use
    elsewhere, it must fall back to a detached-HEAD checkout of the same
    commit (git always permits this regardless of other worktrees)."""
    tmp = tempfile.mkdtemp(prefix="adopt_test_")
    try:
        ai_os_root, repos_root, repo_path = _make_fixture(tmp, branch_name="shared-branch")

        # Simulate another task's workspace already having this branch checked out.
        other_workspace = os.path.join(tmp, "other_workspace")
        _git("worktree", "add", other_workspace, "shared-branch", cwd=repo_path)

        mod = _load_module()
        _patch_module(mod, ai_os_root, repos_root)

        args = argparse.Namespace(
            title="Adopt while branch is checked out elsewhere",
            repo="fake-repo",
            branch="shared-branch",
            pr_url=None,
            task_id="task-adopted-conflict",
            prompt=None,
        )
        mod.cmd_adopt(args)

        task_dir = os.path.join(ai_os_root, "tasks", "task-adopted-conflict")
        with open(os.path.join(task_dir, "task.yaml")) as f:
            task = yaml.safe_load(f)
        assert task["status"] == "pending_review"

        workspace = task["workspace"]
        assert os.path.isdir(workspace)
        head = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=workspace).stdout.strip()
        assert head == "HEAD", f"expected a detached HEAD checkout, got branch '{head}'"
        log = _git("log", "--oneline", "-1", cwd=workspace).stdout
        assert "real recovered commit" in log
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_adopt_refuses_to_overwrite_existing_task_dir():
    tmp = tempfile.mkdtemp(prefix="adopt_test_")
    try:
        ai_os_root, repos_root, repo_path = _make_fixture(tmp)
        mod = _load_module()
        _patch_module(mod, ai_os_root, repos_root)

        args = argparse.Namespace(
            title="First adopt",
            repo="fake-repo",
            branch="recovered-lifecycle-fix-fake",
            pr_url=None,
            task_id="task-adopted-dup",
            prompt=None,
        )
        mod.cmd_adopt(args)

        try:
            mod.cmd_adopt(args)
            assert False, "expected cmd_adopt to sys.exit on an already-existing task_dir"
        except SystemExit as e:
            assert e.code != 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_adopt_creates_pending_review_task_with_no_review_json()
    test_adopt_falls_back_to_detached_checkout_when_branch_already_in_use()
    test_adopt_refuses_to_overwrite_existing_task_dir()
    print("All adopt scenarios passed.")
