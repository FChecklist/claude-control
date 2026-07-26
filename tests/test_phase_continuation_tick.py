"""Regression tests for scripts/phase-continuation-tick.py (task-20260726-210339).
Run: python3 -m pytest tests/ -k "phase_continuation" -v
"""
import json
import os
import sys

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


def test_phase_continuation_tick_dispatches_and_writes_cache(tmp_path):
    work, env = build_fixture_tree(tmp_path)
    (work / "ai-os" / "TEST_PHASE_PLAN_2026-07-24.yaml").write_text(PLAN_YAML)
    env["MOCK_TASK_COUNTER_FILE"] = str(work / "task_counter.txt")
    env["MOCK_RUNNING_UNITS_FILE"] = str(work / "units.txt")

    result = run_script(work, env, "phase-continuation-tick.py")
    assert result.returncode == 0, result.stderr

    cache = json.loads((work / "ai-os" / "PHASE_READY_CACHE.json").read_text())
    assert cache["generator"] == "scripts/phase-continuation-tick.py"
    assert cache["generated_at"]
    ready = cache["phases_ready_to_advance"]
    # This run actually dispatched phase-1 -- already_dispatched() is evaluated
    # BEFORE the dispatch call, so it correctly still shows as "ready" for this
    # snapshot (see build_phase_ready_cache()'s docstring reasoning).
    assert ready == [{"initiative": "Test Initiative", "next_phase": "phase-1",
                       "generated_title": "phase1-first"}]

    report = json.loads(result.stdout)
    assert report["initiatives"][0]["dispatch_result"]["dispatched"] is True


def test_phase_continuation_tick_defers_dispatch_when_cap_reached(tmp_path):
    """The real spawn call site (task-gateway.py start) must never be invoked
    once the shared cap is reached -- proves the gate is at the right call
    site, not just present somewhere in the file."""
    work, env = build_fixture_tree(tmp_path)
    (work / "ai-os" / "TEST_PHASE_PLAN_2026-07-24.yaml").write_text(PLAN_YAML)
    units_file = work / "units.txt"
    units_file.write_text("veridian-worker@a\nveridian-worker@b\nveridian-worker@c\n"
                           "veridian-worker@d\nveridian-worker@e\n")  # == default CONCURRENCY_CAP
    env["MOCK_RUNNING_UNITS_FILE"] = str(units_file)
    env["MOCK_TASK_COUNTER_FILE"] = str(work / "task_counter.txt")

    result = run_script(work, env, "phase-continuation-tick.py")
    assert result.returncode == 0, result.stderr

    report = json.loads(result.stdout)
    dispatch_result = report["initiatives"][0]["dispatch_result"]
    assert dispatch_result["dispatched"] is False
    assert "cap reached" in dispatch_result["deferred_reason"]
    assert not (work / "task_counter.txt").exists()  # task-gateway.py start never ran

    # Still ready-to-advance in the cache -- correctly left for the next tick.
    cache = json.loads((work / "ai-os" / "PHASE_READY_CACHE.json").read_text())
    assert cache["phases_ready_to_advance"][0]["next_phase"] == "phase-1"


def test_phase_continuation_tick_writes_empty_cache_when_no_plans_found(tmp_path):
    work, env = build_fixture_tree(tmp_path)
    result = run_script(work, env, "phase-continuation-tick.py")
    assert result.returncode != 0  # original auto_phase_continuation.py behavior: sys.exit(1)

    cache = json.loads((work / "ai-os" / "PHASE_READY_CACHE.json").read_text())
    assert cache["phases_ready_to_advance"] == []
