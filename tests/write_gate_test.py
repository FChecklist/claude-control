#!/usr/bin/env python3
"""
pytest entry point for tests/interactive_session_guard_test.sh -- the real
regression suite for the interactive-session write gate (see
ai-os/OWNER_DIRECTIVES/interactive-session-guard.bashrc-snippet and
ai-os/OWNER_DIRECTIVES/PROTOCOL_OWNER_AI.yaml article A15).

That suite is a shell script (it needs to source the real guard snippet and
run real subprocess argv parsing against faked gh/git binaries -- not
something worth reimplementing in Python) and is normally run directly via
`bash tests/interactive_session_guard_test.sh`. This wrapper runs it as a
subprocess so `python3 -m pytest tests/ -k write_gate -v` also exercises it,
without duplicating or reimplementing any of its logic -- pass/fail here is
entirely determined by the real shell suite's own exit code and PASS/FAIL
output.
"""
import os
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUITE = os.path.join(REPO_ROOT, "tests", "interactive_session_guard_test.sh")


def test_write_gate_regression_suite():
    result = subprocess.run(
        ["bash", SUITE],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    failing_lines = [
        line for line in result.stdout.splitlines() if line.startswith("FAIL:")
    ]
    assert result.returncode == 0 and not failing_lines, (
        f"interactive_session_guard_test.sh exited {result.returncode}\n"
        f"--- failing scenarios ---\n" + "\n".join(failing_lines) + "\n"
        f"--- full stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )
