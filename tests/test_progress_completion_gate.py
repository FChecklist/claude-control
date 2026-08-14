#!/usr/bin/env python3
"""Real tests for scripts/progress_completion_gate.py -- real git repos, real
merges, no mocks. Proves the two claims task-20260814-054242's SPEC required:

  1. A doc-only diff (progress/<task_id>.md only) against a prompt.txt that
     names a real source file is REJECTED (check_completion returns
     ok=False, and the `check-completion` CLI exits 1).
  2. The identical objective with a real change to the named source file is
     ACCEPTED (ok=True, CLI exits 0).

Plus the surrounding real-behavior claims from the same SPEC: per-task
progress/<task_id>.md files don't collide on merge (two workers merge
cleanly), an objective naming no code file is never gated, an empty diff is
never gated (that's the separate no-op path), and `rollup` deterministically
regenerates its generated view from every progress/*.md file.
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import progress_completion_gate as gate  # noqa: E402

GATE_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "scripts", "progress_completion_gate.py"
)


def run_git(cwd, *args):
    res = subprocess.run(
        ["git", "-C", cwd, *args], capture_output=True, text=True
    )
    assert res.returncode == 0, f"git {args} failed in {cwd}: {res.stderr}"
    return res.stdout


def init_repo_with_remote(root):
    """Real bare 'origin' + a real clone, one initial commit on master,
    origin/HEAD symbolic-ref set so merge-base resolution works exactly like
    a live worker workspace."""
    origin = os.path.join(root, "origin.git")
    clone = os.path.join(root, "clone")
    subprocess.run(["git", "init", "--quiet", "--bare", origin], check=True)
    # Bare repo's own HEAD symref may default to "main" (init.defaultBranch)
    # regardless of what branch name we push -- pin it to "master" up front
    # so a fresh clone always resolves a real checkout ref instead of
    # warning "cloned an empty repository" and leaving refs/remotes/origin/*
    # inconsistent.
    subprocess.run(
        ["git", "-C", origin, "symbolic-ref", "HEAD", "refs/heads/master"], check=True
    )
    subprocess.run(["git", "clone", "--quiet", origin, clone], check=True)
    run_git(clone, "config", "user.email", "test@example.com")
    run_git(clone, "config", "user.name", "test")
    run_git(clone, "checkout", "--quiet", "-B", "master")
    with open(os.path.join(clone, "README.md"), "w") as f:
        f.write("init\n")
    run_git(clone, "add", "-A")
    run_git(clone, "commit", "--quiet", "-m", "initial")
    run_git(clone, "push", "--quiet", "origin", "HEAD:master")
    run_git(
        clone, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/master"
    )
    return origin, clone


def clone_worker_branch(origin, root, name, branch):
    ws = os.path.join(root, name)
    subprocess.run(["git", "clone", "--quiet", origin, ws], check=True)
    run_git(ws, "config", "user.email", "test@example.com")
    run_git(ws, "config", "user.name", "test")
    run_git(
        ws, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/master"
    )
    run_git(ws, "checkout", "--quiet", "-b", branch)
    return ws


class ExtractNamedCodeFilesTest(unittest.TestCase):
    def test_finds_path_prefixed_source_file(self):
        text = "ACTION: fix scripts/dispatch_core.py, the swap-gate veto logic."
        self.assertEqual(gate.extract_named_code_files(text), ["scripts/dispatch_core.py"])

    def test_excludes_progress_and_rca_artifacts(self):
        text = "update progress/foo.md and RCA_bar.md, do not touch PROGRESS.md"
        self.assertEqual(gate.extract_named_code_files(text), [])

    def test_no_code_file_named(self):
        text = "Investigate the dispatch pipeline and write up findings."
        self.assertEqual(gate.extract_named_code_files(text), [])


class CheckCompletionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.origin, _ = init_repo_with_remote(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def _task_dir(self, prompt_text):
        task_dir = tempfile.mkdtemp(dir=self.root)
        with open(os.path.join(task_dir, "prompt.txt"), "w") as f:
            f.write(prompt_text)
        return task_dir

    def test_doc_only_diff_against_named_source_file_is_rejected(self):
        """The exact real shape of the bug this task exists to close: SPEC
        names scripts/dispatch_core.py as the objective, worker only ever
        writes progress/<task_id>.md."""
        ws = clone_worker_branch(self.origin, self.root, "ws1", "worker/task-1")
        task_id = "task-20260814-999999-fake-fix"
        os.makedirs(os.path.join(ws, "progress"), exist_ok=True)
        with open(os.path.join(ws, "progress", f"{task_id}.md"), "w") as f:
            f.write("# PROGRESS -- task-1\n\n## Completed\n- [x] investigated\n")
        run_git(ws, "add", "-A")
        run_git(ws, "commit", "--quiet", "-m", "progress only")

        task_dir = self._task_dir(
            "ACTION: fix the swap-gate veto bug in scripts/dispatch_core.py."
        )
        ok, reason = gate.check_completion(task_dir, ws, "master")
        self.assertFalse(ok, reason)
        self.assertIn("dispatch_core.py", reason)

        # Real CLI path, real subprocess, real exit code -- not just the
        # Python function.
        cli = subprocess.run(
            [
                sys.executable, GATE_SCRIPT, "check-completion",
                "--task-dir", task_dir, "--workspace", ws, "--default-branch", "master",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(cli.returncode, 1, cli.stdout + cli.stderr)
        self.assertIn("dispatch_core.py", cli.stdout)

    def test_real_code_diff_against_named_file_passes(self):
        """Identical objective, but this time the worker actually touched
        scripts/dispatch_core.py -- must be accepted."""
        ws = clone_worker_branch(self.origin, self.root, "ws2", "worker/task-2")
        task_id = "task-20260814-999998-fake-fix-real"
        os.makedirs(os.path.join(ws, "scripts"), exist_ok=True)
        with open(os.path.join(ws, "scripts", "dispatch_core.py"), "w") as f:
            f.write("# real fix: swap gate vetoes on STATIC occupancy\n")
        os.makedirs(os.path.join(ws, "progress"), exist_ok=True)
        with open(os.path.join(ws, "progress", f"{task_id}.md"), "w") as f:
            f.write("# PROGRESS -- task-2\n\n## Completed\n- [x] fixed dispatch_core.py\n")
        run_git(ws, "add", "-A")
        run_git(ws, "commit", "--quiet", "-m", "real fix + progress")

        task_dir = self._task_dir(
            "ACTION: fix the swap-gate veto bug in scripts/dispatch_core.py."
        )
        ok, reason = gate.check_completion(task_dir, ws, "master")
        self.assertTrue(ok, reason)
        self.assertIn("dispatch_core.py", reason)

        cli = subprocess.run(
            [
                sys.executable, GATE_SCRIPT, "check-completion",
                "--task-dir", task_dir, "--workspace", ws, "--default-branch", "master",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(cli.returncode, 0, cli.stdout + cli.stderr)

    def test_uncommitted_real_change_also_passes(self):
        """The gate must see staged/unstaged work too -- it runs before the
        worker's own final `git add -A && git commit`."""
        ws = clone_worker_branch(self.origin, self.root, "ws3", "worker/task-3")
        with open(os.path.join(ws, "scripts_dispatch_core_marker.py"), "w") as f:
            # unstaged, uncommitted
            f.write("placeholder\n")
        os.rename(
            os.path.join(ws, "scripts_dispatch_core_marker.py"),
            os.path.join(ws, "dispatch_core.py"),
        )
        task_dir = self._task_dir("ACTION: fix dispatch_core.py.")
        ok, reason = gate.check_completion(task_dir, ws, "master")
        self.assertTrue(ok, reason)

    def test_objective_names_no_code_file_never_gated(self):
        ws = clone_worker_branch(self.origin, self.root, "ws4", "worker/task-4")
        os.makedirs(os.path.join(ws, "progress"), exist_ok=True)
        with open(os.path.join(ws, "progress", "task-4.md"), "w") as f:
            f.write("# PROGRESS\n")
        run_git(ws, "add", "-A")
        run_git(ws, "commit", "--quiet", "-m", "progress only, no code objective")

        task_dir = self._task_dir("Investigate the dead-letter queue backlog.")
        ok, reason = gate.check_completion(task_dir, ws, "master")
        self.assertTrue(ok, reason)
        self.assertIn("no specific source", reason)

    def test_empty_diff_not_gated(self):
        ws = clone_worker_branch(self.origin, self.root, "ws5", "worker/task-5")
        task_dir = self._task_dir("ACTION: fix dispatch_core.py.")
        ok, reason = gate.check_completion(task_dir, ws, "master")
        self.assertTrue(ok, reason)
        self.assertIn("empty diff", reason)

    def test_missing_prompt_txt_not_gated(self):
        ws = clone_worker_branch(self.origin, self.root, "ws6", "worker/task-6")
        task_dir = tempfile.mkdtemp(dir=self.root)  # no prompt.txt written
        ok, reason = gate.check_completion(task_dir, ws, "master")
        self.assertTrue(ok, reason)


class PerTaskProgressFileNoCollisionTest(unittest.TestCase):
    """Real proof of the SPEC's second requirement: per-task progress/<task_
    identity>.md files, two workers merging back into master one after
    another, real git merge, zero conflicts -- versus the old shared-
    PROGRESS.md scheme, which really does conflict."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_per_task_files_merge_without_conflict(self):
        origin, _ = init_repo_with_remote(self.root)
        ws_a = clone_worker_branch(origin, self.root, "wsA", "worker/task-a")
        ws_b = clone_worker_branch(origin, self.root, "wsB", "worker/task-b")

        os.makedirs(os.path.join(ws_a, "progress"), exist_ok=True)
        with open(os.path.join(ws_a, "progress", "task-a.md"), "w") as f:
            f.write("# PROGRESS -- task-a\n\n## Completed\n- [x] step 1\n")
        run_git(ws_a, "add", "-A")
        run_git(ws_a, "commit", "--quiet", "-m", "task-a progress")
        run_git(ws_a, "push", "--quiet", "origin", "worker/task-a:master")

        os.makedirs(os.path.join(ws_b, "progress"), exist_ok=True)
        with open(os.path.join(ws_b, "progress", "task-b.md"), "w") as f:
            f.write("# PROGRESS -- task-b\n\n## Completed\n- [x] step 1\n")
        run_git(ws_b, "add", "-A")
        run_git(ws_b, "commit", "--quiet", "-m", "task-b progress")
        # task-b's branch was cut before task-a's push landed on master --
        # pull (real merge, not rebase) then push. Distinct files -> no
        # conflict, unlike the old single shared PROGRESS.md scheme.
        res = subprocess.run(
            ["git", "-C", ws_b, "pull", "--no-rebase", "--quiet", "origin", "master"],
            capture_output=True, text=True,
        )
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        push = subprocess.run(
            ["git", "-C", ws_b, "push", "--quiet", "origin", "worker/task-b:master"],
            capture_output=True, text=True,
        )
        self.assertEqual(push.returncode, 0, push.stdout + push.stderr)

    def test_control_shared_progress_md_really_does_conflict(self):
        """Negative control proving the fix is a real behavior change: the
        OLD scheme (both workers editing the same PROGRESS.md) really does
        conflict under the identical two-worker scenario."""
        origin, _ = init_repo_with_remote(self.root)
        ws_a = clone_worker_branch(origin, self.root, "wsA2", "worker/task-a2")
        ws_b = clone_worker_branch(origin, self.root, "wsB2", "worker/task-b2")

        with open(os.path.join(ws_a, "PROGRESS.md"), "w") as f:
            f.write("# PROGRESS\n\n## Completed\n- [x] task-a2 did step 1\n")
        run_git(ws_a, "add", "-A")
        run_git(ws_a, "commit", "--quiet", "-m", "task-a2 progress")
        run_git(ws_a, "push", "--quiet", "origin", "worker/task-a2:master")

        with open(os.path.join(ws_b, "PROGRESS.md"), "w") as f:
            f.write("# PROGRESS\n\n## Completed\n- [x] task-b2 did step 1\n")
        run_git(ws_b, "add", "-A")
        run_git(ws_b, "commit", "--quiet", "-m", "task-b2 progress")
        subprocess.run(
            ["git", "-C", ws_b, "fetch", "--quiet", "origin"], check=True
        )
        merge = subprocess.run(
            ["git", "-C", ws_b, "merge", "--no-edit", "origin/master"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(merge.returncode, 0, "expected a real merge conflict on shared PROGRESS.md")
        self.assertIn("PROGRESS.md", merge.stdout + merge.stderr)


class RollupTest(unittest.TestCase):
    def test_rollup_is_deterministic_and_generated(self):
        with tempfile.TemporaryDirectory() as ws:
            progress_dir = os.path.join(ws, "progress")
            os.makedirs(progress_dir)
            with open(os.path.join(progress_dir, "task-b.md"), "w") as f:
                f.write("# b\n")
            with open(os.path.join(progress_dir, "task-a.md"), "w") as f:
                f.write("# a\n")
            out1 = subprocess.run(
                [sys.executable, GATE_SCRIPT, "rollup", "--workspace", ws],
                capture_output=True, text=True,
            )
            out2 = subprocess.run(
                [sys.executable, GATE_SCRIPT, "rollup", "--workspace", ws],
                capture_output=True, text=True,
            )
            self.assertEqual(out1.stdout, out2.stdout)
            self.assertIn("GENERATED", out1.stdout)
            # filename-sorted: task-a.md before task-b.md regardless of
            # creation order above.
            self.assertLess(out1.stdout.index("task-a.md"), out1.stdout.index("task-b.md"))


if __name__ == "__main__":
    unittest.main()
