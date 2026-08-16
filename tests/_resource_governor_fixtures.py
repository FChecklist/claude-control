"""Shared fixture-building helpers for tests/test_resource_governor.py. Not
collected by pytest itself (no test_ prefix) -- imported by the real test
module. Mirrors tests/_dispatch_consolidation_fixtures.py's own convention
(a throwaway ai-os/+scripts/ tree, real scripts copied in, mocked systemctl
on PATH) rather than duplicating it, since resource_governor.py needs a
richer systemctl mock (show -p ActiveEnterTimestamp, kill -s SIG...) than
that fixture's own mock provides.
"""
import os
import shutil
import stat
import subprocess

REPO_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")

REAL_FILES_TO_COPY = [
    "dispatch_core.py",
    "superboss-register.py",
    "resource_governor.py",
    "veridian-task-watchdog.py",
]


def _write_executable(path, content):
    with open(path, "w") as f:
        f.write(content)
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def build_governor_fixture_tree(tmp_path):
    """Returns (work_dir, env). env points VERIDIAN_*/SUPERBOSS_REGISTER_DB at
    a throwaway tree under tmp_path, with a mocked systemctl on PATH that
    supports everything resource_governor.py's real call sites use:
    list-units (dispatch_core's running_worker_count), show -p
    ActiveEnterTimestamp --value (stuck-task scan), kill -s SIGTERM/SIGKILL
    (stuck-task escalation + emergency load-shed), and start/restart/
    reset-failed (real dispatch)."""
    work = tmp_path
    ai_os = work / "ai-os"
    scripts = work / "scripts"
    bin_dir = work / "bin"
    for d in (ai_os / "tasks", ai_os / "locks", ai_os / "logs", scripts, bin_dir):
        d.mkdir(parents=True, exist_ok=True)

    for fname in REAL_FILES_TO_COPY:
        shutil.copy(os.path.join(REPO_SCRIPTS, fname), scripts / fname)

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

if [[ "$1" == "--user" && "$2" == "show" ]]; then
    unit="$3"
    ts_file="${MOCK_UNIT_TIMESTAMPS_FILE:-}"
    if [[ -n "$ts_file" && -f "$ts_file" ]]; then
        grep "^${unit}=" "$ts_file" | tail -1 | cut -d= -f2-
    fi
    exit 0
fi

if [[ "$1" == "--user" && "$2" == "kill" ]]; then
    sig="$4"
    unit="$5"
    kill_log="${MOCK_KILL_LOG:-}"
    if [[ -n "$kill_log" ]]; then
        echo "${sig} ${unit}" >> "$kill_log"
    fi
    exit 0
fi

if [[ "$1" == "--user" && ( "$2" == "start" || "$2" == "restart" || "$2" == "reset-failed" ) ]]; then
    unit="$3"
    units_file="${MOCK_RUNNING_UNITS_FILE:-}"
    if [[ -n "$units_file" && "$2" != "reset-failed" ]]; then
        echo "$unit" >> "$units_file"
    fi
    exit "${MOCK_SYSTEMCTL_SPAWN_EXIT:-0}"
fi

exit 0
""")

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
""")

    env = dict(os.environ)
    env.update({
        "VERIDIAN_ROOT": str(work),
        "VERIDIAN_AI_OS_DIR": str(ai_os),
        "VERIDIAN_TASKS_DIR": str(ai_os / "tasks"),
        "VERIDIAN_SCRIPTS_DIR": str(scripts),
        "VERIDIAN_DISPATCH_LOCK_DIR": str(ai_os / "locks"),
        "VERIDIAN_GOVERNOR_ATTENTION_PATH": str(ai_os / "logs" / "ATTENTION.md"),
        "SUPERBOSS_REGISTER_DB": str(ai_os / "test-superboss.sqlite"),
        "MOCK_TASK_COUNTER_FILE": str(work / "task_counter.txt"),
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
    })
    return work, env


def run_script(work, env, script_name, args=None, timeout=60):
    cmd = ["python3", str(work / "scripts" / script_name)] + (args or [])
    return subprocess.run(cmd, cwd=str(work / "scripts"), env=env, capture_output=True, text=True, timeout=timeout)
