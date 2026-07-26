#!/usr/bin/env python3
"""
Regression test for veridian-task-watchdog.py's step_3 in-flight RCA dedup
fix (2026-07-26, RCA task-20260726-181517, root-causing task-20260726-171926's
own watchdog escalation).

Before this fix, escalate() had no way to know an RCA task for the exact same
original task_id was already running -- every watchdog poll (every 60s, via
the systemd timer) during a stall/loop window that outlasted one poll cycle
would create ANOTHER billed RCA task, because step_1/step_2 can't see a fix
an in-flight RCA hasn't finished registering yet. Confirmed live: a single
stall on task-20260726-171926 spawned 4 separate RCA task dirs before any of
them completed.

Imports the REAL veridian-task-watchdog.py module (via importlib, since the
filename is not a valid Python identifier) and exercises rca_already_in_flight()
and process_task() against a throwaway TASKS_DIR fixture -- this cannot drift
from what actually ships, unlike a reimplementation of the dedup logic.
"""
import importlib.util
import os
import shutil
import tempfile

import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(REPO_ROOT, "scripts", "veridian-task-watchdog.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("watchdog_under_test", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_task_yaml(tasks_dir, task_id, title, status):
    d = os.path.join(tasks_dir, task_id)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "task.yaml"), "w") as f:
        yaml.safe_dump({"id": task_id, "title": title, "status": status}, f)


def test_detects_in_flight_sibling_rca():
    tmp = tempfile.mkdtemp()
    try:
        tasks_dir = os.path.join(tmp, "tasks")
        os.makedirs(tasks_dir)
        wd = _load_module()
        wd.TASKS_DIR = tasks_dir

        orig_id = "task-20260726-171926-remove-anthropic-api-key-dead-code-path"
        _write_task_yaml(tasks_dir, "task-20260726-175009-rca-task-20260726-171926-remove-anthropi",
                          f"rca-{orig_id}", "in_progress")

        in_flight, existing = wd.rca_already_in_flight(orig_id)
        assert in_flight is True, "expected an in_progress sibling RCA to be detected"
        assert existing == "task-20260726-175009-rca-task-20260726-171926-remove-anthropi"
        print("test_detects_in_flight_sibling_rca: PASS")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_ignores_terminal_sibling_rca():
    tmp = tempfile.mkdtemp()
    try:
        tasks_dir = os.path.join(tmp, "tasks")
        os.makedirs(tasks_dir)
        wd = _load_module()
        wd.TASKS_DIR = tasks_dir

        orig_id = "task-20260726-171926-remove-anthropic-api-key-dead-code-path"
        _write_task_yaml(tasks_dir, "task-20260726-175009-rca-task-20260726-171926-remove-anthropi",
                          f"rca-{orig_id}", "completed")

        in_flight, existing = wd.rca_already_in_flight(orig_id)
        assert in_flight is False, "a completed sibling RCA must not block a fresh escalation"
        assert existing is None
        print("test_ignores_terminal_sibling_rca: PASS")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_process_task_skips_escalation_when_rca_in_flight():
    tmp = tempfile.mkdtemp()
    try:
        tasks_dir = os.path.join(tmp, "tasks")
        os.makedirs(tasks_dir)
        wd = _load_module()
        wd.TASKS_DIR = tasks_dir
        wd.search_prior_occurrence = lambda signature: (False, "")
        wd.escalate = lambda *a, **k: (_ for _ in ()).throw(AssertionError("escalate() must not be called when an RCA is already in flight"))

        orig_id = "task-20260726-171926-remove-anthropic-api-key-dead-code-path"
        _write_task_yaml(tasks_dir, "task-20260726-175009-rca-task-20260726-171926-remove-anthropi",
                          f"rca-{orig_id}", "in_progress")

        task = {
            "status": "in_progress",
            "checkpoints": [
                {"at": "2026-07-26T17:00:00+00:00", "note": "periodic checkpoint"},
                {"at": "2026-07-26T17:05:00+00:00", "note": "periodic checkpoint"},
                {"at": "2026-01-01T00:00:00+00:00", "note": "periodic checkpoint"},  # far in the past -> stalled
            ],
        }
        entry = wd.process_task(orig_id, task, dry_run_escalation=True)
        assert "SKIPPED" in entry["action_taken"], entry["action_taken"]
        print("test_process_task_skips_escalation_when_rca_in_flight: PASS")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_detects_in_flight_sibling_rca()
    test_ignores_terminal_sibling_rca()
    test_process_task_skips_escalation_when_rca_in_flight()
    print("ALL PASS")
