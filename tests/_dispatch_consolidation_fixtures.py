"""Shared fixture-building helpers for the dispatch-consolidation test suite
(test_dispatch_core.py, test_dispatch_tick.py, test_phase_continuation_tick.py,
test_status_remediation_tick.py). Not collected by pytest itself (no test_
prefix) -- imported by the real test modules.

Builds a throwaway ai-os/ + scripts/ tree with mocked systemctl/gh/git/
veridian-task.py/task-gateway.py on PATH, and the real
dispatch_core.py/dispatch-tick.py/phase-continuation-tick.py/
status-remediation-tick.py/superboss-register.py/task-template.py/
backfill_phase_self_report.py copied in -- so every test in this suite runs
the REAL consolidated scripts (subprocess or importlib), never a
re-implementation, against real throwaway state. No test in this suite ever
points at a live production path.
"""
import os
import shutil
import stat
import subprocess

REPO_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")

REAL_FILES_TO_COPY = [
    "dispatch_core.py",
    "dispatch-tick.py",
    "phase-continuation-tick.py",
    "status-remediation-tick.py",
    "superboss-register.py",
    "backfill_phase_self_report.py",
]


def _write_executable(path, content):
    with open(path, "w") as f:
        f.write(content)
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def build_fixture_tree(tmp_path):
    """Returns (work_dir, env) -- env is a full os.environ-style dict pointing
    every dispatch_core/dispatch-tick/phase-continuation-tick/
    status-remediation-tick path override at a throwaway tree under tmp_path,
    with mocked systemctl/gh/git/veridian-task.py/task-gateway.py on PATH."""
    work = tmp_path
    ai_os = work / "ai-os"
    scripts = work / "scripts"
    bin_dir = work / "bin"
    for d in (ai_os / "tasks", ai_os / "queues", scripts, bin_dir):
        d.mkdir(parents=True, exist_ok=True)

    for fname in REAL_FILES_TO_COPY:
        shutil.copy(os.path.join(REPO_SCRIPTS, fname), scripts / fname)

    # task-template.py lives only in production (/opt/veridian/scripts), never
    # committed to this repo (same situation queue-dispatcher.py/
    # module-queue-dispatcher.py were in before this task) -- a minimal,
    # test-only stand-in so module_queue_tick()'s render_task_prompt() import
    # resolves without depending on that production-only file being present
    # wherever this test suite runs.
    _write_executable(scripts / "task-template.py", """#!/usr/bin/env python3
def render_task_prompt(task):
    return f"TASK ID: {task['id']}\\nMODULE: {task['module']}\\nOBJECTIVE: {task['objective']}\\n"
""")

    # Fake systemctl: real running-unit accounting via a shared counter file
    # ($MOCK_RUNNING_UNITS_FILE, one unit name per line) so tests can drive
    # has_free_slot()/running_worker_count() with real, mutating state instead
    # of a python-level monkeypatch -- and so real concurrent processes (the
    # dispatch_core concurrency test) see the SAME real accounting a real
    # systemctl-backed dispatch would.
    _write_executable(bin_dir / "systemctl", """#!/bin/bash
set -u
LOG_FILE="${MOCK_SYSTEMCTL_LOG:-/dev/null}"
echo "systemctl $*" >> "$LOG_FILE"
if [[ "$*" == *"list-units"* ]]; then
    units_file="${MOCK_RUNNING_UNITS_FILE:-}"
    if [[ -n "$units_file" && -f "$units_file" ]]; then
        pattern="veridian-worker@"
        if [[ "$*" == *"veridian-supervisor@"* ]]; then pattern="veridian-supervisor@"; fi
        n=$(grep -c "^${pattern}" "$units_file" 2>/dev/null || true)
        n=${n:-0}
        for ((i = 0; i < n; i++)); do
            echo "${pattern}unit-$i.service loaded active running"
        done
    fi
    exit 0
fi
exit 0
""")

    _write_executable(bin_dir / "gh", """#!/bin/bash
if [[ "$*" == *"pr list"* ]]; then echo "[]"; exit 0; fi
echo "{}"
exit 0
""")

    _write_executable(bin_dir / "git", """#!/bin/bash
exit 1
""")

    # Both mocks below replicate a real, load-bearing side effect of the real
    # veridian-task.py create / task-gateway.py start: each one ends with a
    # real `systemctl --user start veridian-worker@<id>.service` (see
    # veridian-task.py's own cmd_create, line ~320) -- so a just-dispatched
    # task immediately counts as a real running unit on the NEXT
    # running_worker_count() call. Tests proving the shared pool (e.g. a
    # module-queue item correctly deferred because a gap-queue item just took
    # the only free slot) depend on this mock reflecting that real effect.
    _write_executable(scripts / "veridian-task.py", """#!/usr/bin/env python3
import os, sys
if "create" in sys.argv:
    n = 0
    counter_file = os.environ.get("MOCK_TASK_COUNTER_FILE")
    if counter_file and os.path.isfile(counter_file):
        n = int(open(counter_file).read().strip() or "0")
    n += 1
    if counter_file:
        open(counter_file, "w").write(str(n))
    task_id = f"task-mock-{n:04d}"
    units_file = os.environ.get("MOCK_RUNNING_UNITS_FILE")
    if units_file:
        with open(units_file, "a") as f:
            f.write(f"veridian-worker@{task_id}\\n")
    print(f"CREATED: {task_id}")
elif "status" in sys.argv:
    print("=== tasks ===")
""")

    _write_executable(scripts / "task-gateway.py", """#!/usr/bin/env python3
import json, os, sys
if "submit" in sys.argv:
    print(json.dumps({"instruction_id": "INS-TEST-1"}))
elif "start" in sys.argv:
    n = 0
    counter_file = os.environ.get("MOCK_TASK_COUNTER_FILE")
    if counter_file and os.path.isfile(counter_file):
        n = int(open(counter_file).read().strip() or "0")
    n += 1
    if counter_file:
        open(counter_file, "w").write(str(n))
    task_id = f"task-mock-{n:04d}"
    units_file = os.environ.get("MOCK_RUNNING_UNITS_FILE")
    if units_file:
        with open(units_file, "a") as f:
            f.write(f"veridian-worker@{task_id}\\n")
    print(json.dumps({"task_id": task_id, "systemd_active": "active"}))
""")

    env = dict(os.environ)
    env.update({
        "VERIDIAN_ROOT": str(work),
        "VERIDIAN_AI_OS_DIR": str(ai_os),
        "VERIDIAN_TASKS_DIR": str(ai_os / "tasks"),
        "VERIDIAN_SCRIPTS_DIR": str(scripts),
        "VERIDIAN_DISPATCH_LOCK_DIR": str(ai_os / "locks"),
        "VERIDIAN_GAP_QUEUE_PATH": str(ai_os / "gap_queue.yaml"),
        "VERIDIAN_GAP_QUEUE_LOCK": str(ai_os / ".gap_queue.lock"),
        "VERIDIAN_MODULE_QUEUES_DIR": str(ai_os / "queues"),
        "VERIDIAN_MODULE_QUEUES_LOCK": str(ai_os / ".module_queues.lock"),
        "VERIDIAN_TASK_MANAGER": str(scripts / "veridian-task.py"),
        "VERIDIAN_REPO_AI_OS_DIR": str(work / "repo-ai-os"),
        "VERIDIAN_TASKS_DIR_OVERRIDE": str(ai_os / "tasks"),  # backfill_phase_self_report.py's own var name
        "VERIDIAN_PHASE_READY_CACHE": str(ai_os / "PHASE_READY_CACHE.json"),
        "VERIDIAN_LIVE_STATUS_PATH": str(ai_os / "LIVE_STATUS_2026-07-26.yaml"),
        "VERIDIAN_PENDING_REMEDIATION_DIR": str(ai_os / "pending_remediation"),
        "VERIDIAN_REMEDIATION_LOG": str(ai_os / "logs" / "remediation-dispatcher.jsonl"),
        "SUPERBOSS_REGISTER_DB": str(ai_os / "test-superboss.sqlite"),
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
    })
    return work, env


def run_script(work, env, script_name, args=None, timeout=60):
    cmd = ["python3", str(work / "scripts" / script_name)] + (args or [])
    return subprocess.run(cmd, cwd=str(work / "scripts"), env=env,
                           capture_output=True, text=True, timeout=timeout)


def write_task_yaml(work, task_id, status, extra_yaml=""):
    task_dir = work / "ai-os" / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.yaml").write_text(f"id: {task_id}\nstatus: {status}\n{extra_yaml}")
    return task_dir
