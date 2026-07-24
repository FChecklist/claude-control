#!/usr/bin/env python3
"""
populate_capability_registry.py -- Phase 1 of VERIDIAN 20-ENGINE/10-GATEWAY
architecture (task-20260724-083420-phase1-capability-registry-live-wiring),
closes_engines: [3].

Wires ai-os/CAPABILITY_REGISTRY_SCHEMA_2026-07-24.yaml's populated_capabilities
live: reads the 5 real, already-verified capability rows from that file
(each one live-verified once already by
ai-os-scripts/generate_capability_registry_candidates.py against the real
filesystem -- not re-invented here) and registers each into the new
capability_registry table via scripts/superboss-register.py's
register-capability CLI. Owner directive: "all registry/catalog data must be
produced by scripts, not hand-authored AI prose" -- this script is that
producer for the live table, same discipline as
generate_capability_registry_candidates.py used for the schema document.

Run: python3 ai-os-scripts/populate_capability_registry.py
Exits non-zero if any row fails to register.
"""
import json
import os
import subprocess
import sys
import tempfile

import yaml

VERIDIAN_ROOT = "/opt/veridian"
SCHEMA_PATH = f"{VERIDIAN_ROOT}/ai-os/CAPABILITY_REGISTRY_SCHEMA_2026-07-24.yaml"
SUPERBOSS = f"{VERIDIAN_ROOT}/scripts/superboss-register.py"


def main():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    capabilities = doc.get("populated_capabilities", [])
    if not capabilities:
        print(json.dumps({"error": "no populated_capabilities found in schema file", "path": SCHEMA_PATH}))
        sys.exit(1)

    # Ensures the DB (and every table init_db() defines, including
    # capability_registry) exists even on a brand-new DB_PATH -- register-capability's
    # own init_db_silent() fast-path assumes an already-initialized DB, same
    # precondition every other superboss-register.py write subcommand relies on.
    init_proc = subprocess.run(["python3", SUPERBOSS, "init"], capture_output=True, text=True)
    if init_proc.returncode != 0:
        print(json.dumps({"error": "superboss-register.py init failed", "stderr": init_proc.stderr[-1000:]}))
        sys.exit(1)

    registered = []
    failed = []
    for cap in capabilities:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            json.dump(cap, tf)
            record_file = tf.name
        try:
            proc = subprocess.run(
                ["python3", SUPERBOSS, "register-capability", "--record-file", record_file],
                capture_output=True, text=True,
            )
        finally:
            os.unlink(record_file)

        if proc.returncode != 0:
            failed.append({"capability_name": cap.get("capability_name"), "stderr": proc.stderr[-1000:]})
            continue
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            failed.append({"capability_name": cap.get("capability_name"), "stdout": proc.stdout[-1000:]})
            continue
        registered.append(result)

    list_proc = subprocess.run(["python3", SUPERBOSS, "list-capabilities"], capture_output=True, text=True)
    live_count = None
    if list_proc.returncode == 0:
        try:
            live_count = json.loads(list_proc.stdout).get("count")
        except json.JSONDecodeError:
            pass

    print(json.dumps({
        "schema_rows_found": len(capabilities),
        "registered_count": len(registered),
        "failed_count": len(failed),
        "registered": registered,
        "failed": failed,
        "live_row_count_after_run": live_count,
    }, indent=2, default=str))
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
