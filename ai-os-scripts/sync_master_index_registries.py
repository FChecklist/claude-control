#!/usr/bin/env python3
"""
sync_master_index_registries.py -- Phase 5 (metadata_knowledge_consolidation)
of 20_ENGINES_10_GATEWAYS_PHASE_PLAN_2026-07-24.yaml
(task-20260724-140008-phase5-reconcile-master-index-yaml-s-reg),
closes_engines: [14, 15].

Reconciles MASTER_INDEX.yaml's registries: section (hand-authored prose,
scope/status/mandatory_before per entry) with knowledge_engine (the queryable
half of the Metadata Engine, per engine_inventory row 14's own
gap_description) -- WITHOUT a disruptive full merge (registries: entries stay
exactly where every doc/script/human that greps MASTER_INDEX.yaml already
expects them, per this phase's own OBJECTIVE hedge "or a documented, enforced
sync direction between the two, if full merge is too disruptive").

ENFORCED SYNC DIRECTION (one-way, MASTER_INDEX.yaml -> knowledge_engine):
MASTER_INDEX.yaml's registries: list is the authored source of truth for
scope/status/mandatory_before narrative. This script is the enforced,
re-runnable mechanism that keeps knowledge_engine's queryable layer current
with it -- one knowledge_engine row per registries: entry
(scripts/superboss-register.py's new upsert-knowledge-fragment subcommand,
Phase 5's own additive extension -- idempotent per artifact_path, never a
duplicate row), keyed at the virtual artifact_path
'ai-os/MASTER_INDEX.yaml#registries.<id>' with secondary_path pointing at the
real file. Never writes back to MASTER_INDEX.yaml itself -- that direction
stays a human/AI-session edit, same as every other governance doc on this
server (Rule 4bd23... "no self-certification"-adjacent discipline: a script
should never rewrite the doc it is also grading).

DRIFT DETECTION, both directions:
  - forward: an entry's upsert reports verification_status=HASH_DRIFTED when
    its content changed since the last sync run (same semantics
    verify_knowledge already uses for whole-file rows) -- signals "someone
    edited this registries: entry and this is the first sync to notice."
  - reverse (orphan detection): every existing knowledge_engine row tagged
    type:master_index_registry_entry whose id is no longer present in
    MASTER_INDEX.yaml's current registries: list is reported (never silently
    deleted -- same PATH_MISSING-not-hidden discipline knowledge_engine
    already uses elsewhere) as orphaned_registry_rows, so a deleted/renamed
    registries: entry is visible, not a silent stale row.

ENFORCEMENT: wired into scripts/task-gateway.py's cmd_close (see
sync_master_index_registries_if_touched()) -- every task that closes having
touched ai-os/MASTER_INDEX.yaml automatically re-runs this sync, the same
"every close is a real re-verify, not a one-off manual run" discipline Phase 2
already established for reverify_touched_knowledge_engine_rows(). Also
directly runnable standalone/cron-safe (idempotent).

Run: python3 ai-os-scripts/sync_master_index_registries.py [--master-index-path PATH]
"""
import argparse
import json
import subprocess
import sys

import yaml

VERIDIAN_ROOT = "/opt/veridian"
DEFAULT_MASTER_INDEX = f"{VERIDIAN_ROOT}/ai-os/MASTER_INDEX.yaml"
SUPERBOSS = f"{VERIDIAN_ROOT}/scripts/superboss-register.py"
REGISTRY_ENTRY_TAG = "type:master_index_registry_entry"


def _artifact_path(entry_id):
    return f"ai-os/MASTER_INDEX.yaml#registries.{entry_id}"


def sync(master_index_path=DEFAULT_MASTER_INDEX):
    with open(master_index_path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    registries = doc.get("registries", [])
    if not registries:
        print(json.dumps({"error": "no registries: list found", "path": master_index_path}))
        sys.exit(1)

    init_proc = subprocess.run(["python3", SUPERBOSS, "init"], capture_output=True, text=True)
    if init_proc.returncode != 0:
        print(json.dumps({"error": "superboss-register.py init failed", "stderr": init_proc.stderr[-1000:]}))
        sys.exit(1)

    synced, failed = [], []
    live_ids = set()
    for entry in registries:
        entry_id = entry.get("id")
        if not entry_id:
            failed.append({"error": "registries: entry missing its own id field", "entry": entry})
            continue
        live_ids.add(entry_id)

        content = json.dumps(entry, sort_keys=True, default=str)
        scope_text = (entry.get("scope") or entry.get("title") or entry.get("what") or "").strip()
        purpose = f"MASTER_INDEX.yaml registries.{entry_id} ({entry.get('type', 'untyped')}): {scope_text}"[:960]
        tags = [REGISTRY_ENTRY_TAG, f"registry-id:{entry_id}", "source:LOCAL"]
        if entry.get("status"):
            tags.append(f"registry-status:{entry['status']}")

        proc = subprocess.run(
            ["python3", SUPERBOSS, "upsert-knowledge-fragment",
             "--path", _artifact_path(entry_id),
             "--content", content,
             "--purpose", purpose,
             "--tags", ",".join(tags),
             "--secondary-path", "ai-os/MASTER_INDEX.yaml",
             "--metadata", json.dumps({"registry_id": entry_id, "registry_type": entry.get("type")})],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            failed.append({"id": entry_id, "stderr": proc.stderr[-1000:]})
            continue
        try:
            synced.append(json.loads(proc.stdout))
        except json.JSONDecodeError:
            failed.append({"id": entry_id, "stdout": proc.stdout[-1000:]})

    # Reverse-direction drift: existing rows tagged as a registry entry whose
    # id no longer exists in MASTER_INDEX.yaml's current registries: list.
    list_proc = subprocess.run(
        ["python3", SUPERBOSS, "list-knowledge", "--tag", REGISTRY_ENTRY_TAG],
        capture_output=True, text=True,
    )
    orphaned = []
    if list_proc.returncode == 0:
        try:
            existing_rows = json.loads(list_proc.stdout).get("matches", [])
        except json.JSONDecodeError:
            existing_rows = []
        for row in existing_rows:
            row_tags = json.loads(row.get("tags") or "[]")
            registry_id_tags = [t for t in row_tags if t.startswith("registry-id:")]
            if not registry_id_tags:
                continue
            row_id = registry_id_tags[0].split(":", 1)[1]
            if row_id not in live_ids:
                orphaned.append({"artifact_id": row["artifact_id"], "artifact_path": row["artifact_path"], "registry_id": row_id})

    drifted = [r for r in synced if r.get("verification_status") == "HASH_DRIFTED"]
    result = {
        "master_index_path": master_index_path,
        "registries_entries_found": len(registries),
        "synced_count": len(synced),
        "failed_count": len(failed),
        "hash_drifted_this_run": drifted,
        "orphaned_registry_rows": orphaned,
        "failed": failed,
    }
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if not failed else 1)


def main():
    parser = argparse.ArgumentParser(description=(
        "Sync MASTER_INDEX.yaml's registries: section into knowledge_engine, one row per entry."
    ))
    parser.add_argument("--master-index-path", dest="master_index_path", default=DEFAULT_MASTER_INDEX)
    args = parser.parse_args()
    sync(args.master_index_path)


if __name__ == "__main__":
    main()
