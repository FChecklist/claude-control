#!/usr/bin/env python3
"""
Thin pytest wrapper around the real supervisor-entrypoint.sh WORKSPACE-RESYNC-
BLOCK regression test (tests/supervisor_workspace_resync_test.sh), so
`pytest -k workspace_resync` runs it alongside the rest of the suite. The
.sh test already extracts and evals the REAL block out of the live script
against real, throwaway local git repos -- this file does not re-implement
any of that logic, it only runs it as a subprocess and asserts it exits 0.

Real gap this fixes: GAP-SUPERVISOR-RETRIGGER-STALE-WORKSPACE
(UMR-20260803-025317-0c64, fixed UMR-20260803-040529-15c9) --
veridian-task.py adopt checks out a task's workspace to a detached HEAD
snapshot at adoption time; retriggering a review later (archive
review.json + service restart) never resynced that snapshot to the
branch's real current remote tip, so a review after additional commits
were pushed silently reviewed stale, pre-push content. Directly observed
on claude-control PR #123: 4 consecutive AUDIT: FAIL comments reported an
IDENTICAL diff-stat despite 4 real fix commits landing in between.
"""
import os
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(REPO_ROOT, "scripts", "supervisor-entrypoint.sh")
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


def test_workspace_resync_reproduces_and_fixes_the_real_stale_workspace_gap():
    result = subprocess.run(
        ["bash", os.path.join(TESTS_DIR, "supervisor_workspace_resync_test.sh"), SCRIPT_PATH],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, (
        f"supervisor_workspace_resync_test.sh failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
