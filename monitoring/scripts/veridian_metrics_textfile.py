#!/usr/bin/env python3
"""VERIDIAN observability textfile-collector generator (task-20260814-131031).

Read-only. Writes exactly two gauges to a .prom file that node_exporter's
--collector.textfile.directory picks up on its own scrape, so Prometheus
gets these without a bespoke HTTP metrics endpoint:

  - veridian_concurrent_worker_count: count of running
    'veridian-worker@*' + 'veridian-supervisor@*' systemd --user units.
    Mirrors dispatch_core.py's running_worker_count() definition exactly
    (same `systemctl --user list-units ... --state=running` query), but
    this script does NOT import dispatch_core.py or any dispatch-decision
    module -- it only shells out to `systemctl --user list-units`, a
    read-only query of unit state. Zero coupling to dispatch-decision
    logic, per task-20260814-131031's explicit instruction not to touch
    pm-sentinel-tick.sh or any dispatch-decision code.

  - veridian_dispatch_queue_depth: count of superboss-register.sqlite
    work_items rows with status IN ('open', 'pending') -- opened via a
    read-only ("mode=ro") sqlite3 URI connection, so this can never write
    to the register.

Invoked by veridian-metrics-textfile.timer every 30s. Writes atomically
(tmp file + os.rename) so node_exporter never reads a half-written file.
"""
import os
import sqlite3
import subprocess
import sys

TEXTFILE_DIR = "/opt/veridian/monitoring/textfile_collector"
OUTPUT_FILE = os.path.join(TEXTFILE_DIR, "veridian_metrics.prom")
REGISTER_DB = "/opt/veridian/ai-os/memory/superboss-register.sqlite"
WORKER_UNIT_GLOBS = ["veridian-worker@*", "veridian-supervisor@*"]


def running_worker_count():
    """Real count of running veridian-worker@*/veridian-supervisor@*
    systemd --user units. Read-only `systemctl --user list-units` query,
    same definition dispatch_core.py's running_worker_count() uses --
    duplicated here (not imported) to keep this script fully decoupled
    from dispatch-decision code."""
    total = 0
    for unit_glob in WORKER_UNIT_GLOBS:
        try:
            r = subprocess.run(
                ["systemctl", "--user", "list-units", unit_glob,
                 "--state=running", "--no-legend"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            total += len([line for line in r.stdout.splitlines() if line.strip()])
        except Exception:
            pass
    return total


def dispatch_queue_depth():
    """Real count of not-yet-completed work_items rows in
    superboss-register.sqlite, opened strictly read-only via a sqlite3
    URI connection (mode=ro) -- this process can never write to the
    register."""
    try:
        uri = f"file:{REGISTER_DB}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5)
        try:
            cur = conn.execute(
                "SELECT COUNT(*) FROM work_items WHERE status IN ('open', 'pending')"
            )
            return cur.fetchone()[0]
        finally:
            conn.close()
    except Exception:
        return None


def main():
    worker_count = running_worker_count()
    queue_depth = dispatch_queue_depth()

    lines = [
        "# HELP veridian_concurrent_worker_count Real count of running "
        "veridian-worker@*/veridian-supervisor@* systemd --user units.",
        "# TYPE veridian_concurrent_worker_count gauge",
        f"veridian_concurrent_worker_count {worker_count}",
    ]
    if queue_depth is not None:
        lines += [
            "# HELP veridian_dispatch_queue_depth Real count of "
            "superboss-register.sqlite work_items rows with status IN "
            "('open','pending').",
            "# TYPE veridian_dispatch_queue_depth gauge",
            f"veridian_dispatch_queue_depth {queue_depth}",
        ]

    os.makedirs(TEXTFILE_DIR, exist_ok=True)
    tmp_path = OUTPUT_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.rename(tmp_path, OUTPUT_FILE)


if __name__ == "__main__":
    sys.exit(main())
