#!/usr/bin/env python3
"""
Thin pytest wrapper around the real supervisor-entrypoint.sh merge-execution
regression tests (tests/supervisor_merge_detection_test.sh and
tests/supervisor_pr_url_guard_test.sh), so `pytest -k merge_execution` runs
them alongside the rest of the suite. Each .sh test already extracts and
evals the REAL block out of the live script -- this file does not
re-implement any of that logic, it only runs those scripts as subprocesses
and asserts they exit 0, so a failure here always means one of those real
scenario checks failed.

Covers gap 1 end-to-end: given VERDICT=approve, TIER=tier1, SCOPE_OK=1, and a
correctly-resolved PR_URL, the merge decision path must actually execute the
merge (supervisor_merge_detection_test.sh); given a PR_URL that could not be
resolved (the real claude-control PR #84 incident, 2026-07-26), the script
must refuse to proceed rather than silently operate on an unrelated PR
(supervisor_pr_url_guard_test.sh).
"""
import os
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(REPO_ROOT, "scripts", "supervisor-entrypoint.sh")
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


def _run(test_script):
    result = subprocess.run(
        ["bash", os.path.join(TESTS_DIR, test_script), SCRIPT_PATH],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"{test_script} failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_merge_execution_runs_when_approved_tier1_and_pr_url_resolved():
    """The real merge-decision path (VERDICT=approve, TIER=tier1, SCOPE_OK=1,
    a resolvable PR) must actually execute the merge and judge success solely
    via a fresh `gh pr view` call, never a shell exit code."""
    _run("supervisor_merge_detection_test.sh")


def test_merge_execution_refuses_when_pr_url_unresolved_pr84_repro():
    """The real fix for the PR #84 incident: an unresolved PR_URL must block
    the task rather than let any later gh pr call silently fall back to
    whatever PR the workspace's checked-out branch happens to match."""
    _run("supervisor_pr_url_guard_test.sh")


if __name__ == "__main__":
    test_merge_execution_runs_when_approved_tier1_and_pr_url_resolved()
    test_merge_execution_refuses_when_pr_url_unresolved_pr84_repro()
    print("All merge_execution scenarios passed.")
