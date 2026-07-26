"""Regression tests for scripts/status-remediation-tick.py (task-20260726-210339).
Run: python3 -m pytest tests/ -k "status_remediation" -v
"""
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _dispatch_consolidation_fixtures import build_fixture_tree, run_script  # noqa: E402

PLAN_YAML = """meta:
  title: Test Initiative
phases:
  - id: phase-1
    name: First phase
    objective: Do the first real thing.
    scope: [Implement thing A]
    depends_on: []
    status: not_done
"""


def test_status_remediation_tick_end_to_end_cache_handoff_from_phase_continuation_tick(tmp_path):
    """The real end-to-end proof this task's SCOPE item 8 requires: run the
    REAL phase-continuation-tick.py first (writes PHASE_READY_CACHE.json),
    then the REAL status-remediation-tick.py (reads it) -- against the same
    fixture tree, two real subprocess invocations, no shortcuts. Confirms
    status-remediation-tick.py's phases_ready_to_advance in LIVE_STATUS
    matches exactly what phase-continuation-tick.py determined, and that this
    happens WITHOUT status-remediation-tick.py re-running any plan discovery
    of its own (no plan yaml is even reachable from its own PLAN_DIRS
    resolution -- it never imports/looks for one)."""
    work, env = build_fixture_tree(tmp_path)
    (work / "ai-os" / "TEST_PHASE_PLAN_2026-07-24.yaml").write_text(PLAN_YAML)
    env["MOCK_TASK_COUNTER_FILE"] = str(work / "task_counter.txt")
    env["MOCK_RUNNING_UNITS_FILE"] = str(work / "units.txt")

    phase_result = run_script(work, env, "phase-continuation-tick.py")
    assert phase_result.returncode == 0, phase_result.stderr
    written_cache = json.loads((work / "ai-os" / "PHASE_READY_CACHE.json").read_text())

    status_result = run_script(work, env, "status-remediation-tick.py")
    assert status_result.returncode == 0, status_result.stderr

    live_status = yaml.safe_load((work / "ai-os" / "LIVE_STATUS_2026-07-26.yaml").read_text())
    assert live_status["phases_ready_to_advance"] == written_cache["phases_ready_to_advance"]
    assert live_status["scan_errors"] == []  # cache was found and read cleanly, no fallback error
    assert live_status["generator"] == "scripts/status-remediation-tick.py"


def test_status_remediation_tick_reports_scan_error_when_cache_missing(tmp_path):
    """If phase-continuation-tick.py has never run this deployment, the cache
    file is absent -- status-remediation-tick.py must degrade to an empty
    phases_ready_to_advance list plus a visible scan_errors entry, never
    silently invent data or crash."""
    work, env = build_fixture_tree(tmp_path)

    result = run_script(work, env, "status-remediation-tick.py")
    assert result.returncode == 0, result.stderr

    live_status = yaml.safe_load((work / "ai-os" / "LIVE_STATUS_2026-07-26.yaml").read_text())
    assert live_status["phases_ready_to_advance"] == []
    assert any("PHASE_READY_CACHE.json missing" in e for e in live_status["scan_errors"])


def test_status_remediation_tick_self_test_passes(tmp_path):
    """Preserves veridian_remediation_dispatcher.py's --self-test synthetic
    classification proof verbatim (mechanical vs judgment_needed paths)."""
    work, env = build_fixture_tree(tmp_path)
    result = run_script(work, env, "status-remediation-tick.py", args=["--self-test"])
    assert result.returncode == 0, result.stderr
    assert "SELF-TEST PASSED" in result.stdout


def test_status_remediation_tick_apply_defaults_to_dry_run(tmp_path):
    """Same safe default as veridian_remediation_dispatcher.py: mechanical
    actions never run for real unless --apply is passed."""
    work, env = build_fixture_tree(tmp_path)
    result = run_script(work, env, "status-remediation-tick.py")
    assert result.returncode == 0, result.stderr
    live_status = yaml.safe_load((work / "ai-os" / "LIVE_STATUS_2026-07-26.yaml").read_text())
    assert live_status["remediation"]["apply_mode"] is False
