"""Regression tests for scripts/dispatch-tick.py (task-20260726-210339). Run:
    python3 -m pytest tests/ -k "dispatch_tick" -v

Runs the REAL dispatch-tick.py script as a subprocess against a throwaway
fixture tree (mocked systemctl/gh/git/veridian-task.py) -- same convention
tests/supervisor_sweep_discovery_test.sh already established for
supervisor-sweep.sh, extended here to cover the merged gap_queue/module_queue
behavior too.
"""
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _dispatch_consolidation_fixtures import build_fixture_tree, run_script, write_task_yaml  # noqa: E402


def _write_gap_queue(work, dispatch_paused, held_task_ids, queue):
    doc = {"dispatch_paused": dispatch_paused, "held_task_ids": held_task_ids,
            "pause_reason": "Owner directive test fixture", "queue": queue}
    (work / "ai-os" / "gap_queue.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))
    return doc


def _one_gap_item(item_id="gap-item-1", status="queued"):
    return {"id": item_id, "category": "TestCat", "sub_category": "TestSub", "row_count": 1,
            "status": status, "findings": [{"severity": "HIGH", "parameter": "p",
                                             "gap_identified": "g", "recommended_approach": "r"}]}


def test_dispatch_tick_gap_queue_dispatch_paused_dispatches_nothing(tmp_path):
    """Preserves gap_queue.yaml's Owner-set dispatch_paused/held_task_ids gate
    EXACTLY as queue-dispatcher.py enforced it -- this task's PR body must be
    able to say these values were carried forward unchanged."""
    work, env = build_fixture_tree(tmp_path)
    before = _write_gap_queue(work, dispatch_paused=True,
                               held_task_ids=["task-held-1", "task-held-2"],
                               queue=[_one_gap_item()])
    counter_file = work / "task_counter.txt"
    env["MOCK_TASK_COUNTER_FILE"] = str(counter_file)

    result = run_script(work, env, "dispatch-tick.py")
    assert result.returncode == 0, result.stderr

    after = yaml.safe_load((work / "ai-os" / "gap_queue.yaml").read_text())
    assert after["dispatch_paused"] is True
    assert after["held_task_ids"] == ["task-held-1", "task-held-2"]
    assert after["queue"][0]["status"] == "queued"  # untouched, never dispatched
    assert not counter_file.exists()  # veridian-task.py create was never invoked


def test_dispatch_tick_gap_queue_dispatches_when_unpaused_and_under_cap(tmp_path):
    work, env = build_fixture_tree(tmp_path)
    _write_gap_queue(work, dispatch_paused=False, held_task_ids=[], queue=[_one_gap_item()])
    counter_file = work / "task_counter.txt"
    env["MOCK_TASK_COUNTER_FILE"] = str(counter_file)
    env["MOCK_RUNNING_UNITS_FILE"] = str(work / "units.txt")

    result = run_script(work, env, "dispatch-tick.py")
    assert result.returncode == 0, result.stderr

    after = yaml.safe_load((work / "ai-os" / "gap_queue.yaml").read_text())
    assert after["queue"][0]["status"] == "dispatched"
    assert after["queue"][0]["task_id"].startswith("task-mock-")


def test_dispatch_tick_supervisor_sweep_matches_original_adopt_scenarios(tmp_path):
    """Reproduces the 3 scenarios tests/supervisor_sweep_discovery_test.sh
    already covers for the original supervisor-sweep.sh, against the new
    consolidated dispatch-tick.py: (1) pending_review + no review.json (the
    adopt/missed-trigger shape) -> supervisor started; (2) pending_review +
    review.json already exists -> not re-triggered; (3) any other status ->
    not touched."""
    work, env = build_fixture_tree(tmp_path)
    _write_gap_queue(work, dispatch_paused=True, held_task_ids=[], queue=[])  # no gap-queue noise
    write_task_yaml(work, "task-missed-trigger", "pending_review")
    reviewed_dir = write_task_yaml(work, "task-already-reviewed", "pending_review")
    (reviewed_dir / "review.json").write_text('{"verdict": "approve"}')
    write_task_yaml(work, "task-completed", "completed")
    env["MOCK_SYSTEMCTL_LOG"] = str(work / "systemctl.log")
    env["MOCK_RUNNING_UNITS_FILE"] = str(work / "units.txt")

    result = run_script(work, env, "dispatch-tick.py")
    assert result.returncode == 0, result.stderr

    log = (work / "systemctl.log").read_text()
    assert "start veridian-supervisor@task-missed-trigger.service" in log
    assert "start veridian-supervisor@task-already-reviewed.service" not in log
    assert "start veridian-supervisor@task-completed.service" not in log


def test_dispatch_tick_module_queue_shares_pool_with_gap_queue(tmp_path):
    """module-queue-dispatcher.py's own docstring said its cap was MEANT to be
    shared with queue-dispatcher.py's pool, not additive -- but the two used
    separate lock files and separate cap checks, so nothing enforced that.
    This proves dispatch-tick.py's consolidated version actually shares one
    pool: with CAP=1 and the gap_queue item consuming the only slot, the
    module_queue item must NOT also dispatch in the same tick."""
    work, env = build_fixture_tree(tmp_path)
    _write_gap_queue(work, dispatch_paused=False, held_task_ids=[], queue=[_one_gap_item()])
    (work / "ai-os" / "queues" / "backend.yaml").write_text(yaml.safe_dump({
        "module": "backend",
        "queue": [{"id": "mod-item-1", "module": "backend", "objective": "obj",
                    "status": "NEW", "dependencies": [], "files_allowed": []}],
    }, sort_keys=False))
    env["VERIDIAN_DISPATCH_CONCURRENCY_CAP"] = "1"
    env["MOCK_TASK_COUNTER_FILE"] = str(work / "task_counter.txt")
    env["MOCK_RUNNING_UNITS_FILE"] = str(work / "units.txt")

    result = run_script(work, env, "dispatch-tick.py")
    assert result.returncode == 0, result.stderr

    gap_after = yaml.safe_load((work / "ai-os" / "gap_queue.yaml").read_text())
    module_after = yaml.safe_load((work / "ai-os" / "queues" / "backend.yaml").read_text())

    assert gap_after["queue"][0]["status"] == "dispatched"  # took the one shared slot
    assert module_after["queue"][0]["status"] == "NEW"  # cap reached -- correctly deferred, not dispatched


def test_dispatch_tick_module_queue_round_robins_across_modules(tmp_path):
    """Regression test for the pre-existing (not introduced by this task)
    module-queue-dispatcher.py bug this task also fixes: candidates used to be
    built module-by-module (drain module A's whole queue, then module B's),
    contradicting the "round-robin across module queues" fairness the
    original script's own comment claimed but its code never actually did.
    With 2 items queued in each of 2 modules and cap headroom to dispatch all
    4, the real dispatch order (recovered from the mock task-id counter, which
    increments in real dispatch call order) must alternate between modules --
    not drain one module's queue before starting the other's."""
    work, env = build_fixture_tree(tmp_path)
    _write_gap_queue(work, dispatch_paused=True, held_task_ids=[], queue=[])  # keep gap_queue out of the way
    for module, item_ids in (("backend", ["b-item-1", "b-item-2"]), ("frontend", ["f-item-1", "f-item-2"])):
        (work / "ai-os" / "queues" / f"{module}.yaml").write_text(yaml.safe_dump({
            "module": module,
            "queue": [{"id": iid, "module": module, "objective": "obj",
                       "status": "NEW", "dependencies": [], "files_allowed": []} for iid in item_ids],
        }, sort_keys=False))
    env["VERIDIAN_DISPATCH_CONCURRENCY_CAP"] = "10"  # enough headroom to dispatch all 4 in one tick
    env["MOCK_TASK_COUNTER_FILE"] = str(work / "task_counter.txt")
    env["MOCK_RUNNING_UNITS_FILE"] = str(work / "units.txt")

    result = run_script(work, env, "dispatch-tick.py")
    assert result.returncode == 0, result.stderr

    backend_after = yaml.safe_load((work / "ai-os" / "queues" / "backend.yaml").read_text())
    frontend_after = yaml.safe_load((work / "ai-os" / "queues" / "frontend.yaml").read_text())
    all_items = {it["id"]: it for it in backend_after["queue"] + frontend_after["queue"]}
    for iid in ("b-item-1", "b-item-2", "f-item-1", "f-item-2"):
        assert all_items[iid]["status"] == "RUNNING", f"{iid} did not dispatch"

    dispatch_order = sorted(all_items, key=lambda iid: all_items[iid]["task_id"])
    modules_in_order = ["backend" if iid.startswith("b-") else "frontend" for iid in dispatch_order]
    assert modules_in_order == ["backend", "frontend", "backend", "frontend"], (
        f"expected round-robin dispatch order alternating modules, got {dispatch_order} "
        f"(modules: {modules_in_order}) -- module_queue_tick() drained one module's queue "
        f"before starting the other's instead of interleaving"
    )


def test_dispatch_tick_writes_cron_job_wiring_registry_row(tmp_path):
    import sqlite3
    work, env = build_fixture_tree(tmp_path)
    _write_gap_queue(work, dispatch_paused=True, held_task_ids=[], queue=[])

    result = run_script(work, env, "dispatch-tick.py")
    assert result.returncode == 0, result.stderr

    conn = sqlite3.connect(env["SUPERBOSS_REGISTER_DB"])
    row = conn.execute(
        "SELECT entity_type FROM wiring_registry WHERE entity_id='cron_job-dispatch-tick'"
    ).fetchone()
    assert row is not None and row[0] == "cron_job"
    conn.close()
