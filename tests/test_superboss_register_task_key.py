#!/usr/bin/env python3
"""
Regression tests for scripts/superboss-register.py's claim-task-key /
check-task-key subcommands -- the real fix behind task-20260731-074406's
#634-vs-#639 / #641-vs-#629 duplicate-dispatch incidents, wired into
task-gateway.py's cmd_start/cmd_submit. Added 2026-08-03 after independent
review (claude-control PR #123) correctly flagged this feature had zero
test coverage, which is why a live-vs-repo drift (these subcommands existed
live but not in this repo) went uncaught until a live invocation was run.
Run with: python3 -m pytest tests/ -k superboss_register_task_key
"""
import json
import os
import subprocess
import sys
import tempfile

import pytest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "superboss-register.py")


@pytest.fixture
def isolated_db(tmp_path):
    db_path = str(tmp_path / "test-superboss-register.sqlite")
    env = dict(os.environ)
    env["SUPERBOSS_REGISTER_DB"] = db_path
    rc, out, err = _run(["init"], env)
    assert rc == 0, err
    return env


def _run(args, env=None):
    proc = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, env=env, timeout=30)
    return proc.returncode, proc.stdout, proc.stderr


def test_check_task_key_on_unclaimed_key_reports_not_claimed(isolated_db):
    rc, out, err = _run(["check-task-key", "--task-key", "fresh-key-never-claimed"], isolated_db)
    assert rc == 0, err
    result = json.loads(out)
    assert result["already_claimed"] is False


def test_claim_task_key_succeeds_first_time(isolated_db):
    rc, out, err = _run(
        ["claim-task-key", "--task-key", "real-task-slug", "--title", "Real Task", "--source", "ai_agent"],
        isolated_db,
    )
    assert rc == 0, err
    result = json.loads(out)
    assert result["claimed"] is True
    assert result["task_key"] == "real-task-slug"


def test_claim_task_key_rejects_a_real_duplicate(isolated_db):
    """The exact real incident this feature exists for: two concurrent
    dispatches of the same title-derived slug -- the second claim must be
    rejected, not silently allowed to duplicate."""
    rc1, out1, err1 = _run(
        ["claim-task-key", "--task-key", "duplicate-slug", "--title", "First Dispatch", "--source", "ai_agent"],
        isolated_db,
    )
    assert rc1 == 0, err1
    assert json.loads(out1)["claimed"] is True

    rc2, out2, err2 = _run(
        ["claim-task-key", "--task-key", "duplicate-slug", "--title", "Second Dispatch (duplicate)", "--source", "ai_agent"],
        isolated_db,
    )
    assert rc2 == 0, err2
    result2 = json.loads(out2)
    assert result2["claimed"] is False
    assert result2["error"] == "duplicate_task_key"
    assert result2["existing_title"] == "First Dispatch"


def test_check_task_key_reflects_a_real_claim(isolated_db):
    _run(["claim-task-key", "--task-key", "checked-slug", "--title", "Checked Task", "--source", "ai_agent"], isolated_db)
    rc, out, err = _run(["check-task-key", "--task-key", "checked-slug"], isolated_db)
    assert rc == 0, err
    result = json.loads(out)
    assert result["already_claimed"] is True
    assert result["existing_title"] == "Checked Task"


def test_different_task_keys_do_not_collide(isolated_db):
    rc1, out1, _ = _run(["claim-task-key", "--task-key", "slug-a", "--title", "A", "--source", "ai_agent"], isolated_db)
    rc2, out2, _ = _run(["claim-task-key", "--task-key", "slug-b", "--title", "B", "--source", "ai_agent"], isolated_db)
    assert json.loads(out1)["claimed"] is True
    assert json.loads(out2)["claimed"] is True
