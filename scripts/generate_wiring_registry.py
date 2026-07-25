#!/usr/bin/env python3
"""
generate_wiring_registry.py -- Wiring Engine Phase 0 (task-20260725-032718-
wiring-engine-phase0-schema-registry), SCOPE item 2: mechanically populates
ai-os/WIRING_ENGINE_SCHEMA_2026-07-25.yaml's entity_record_schema FROM 8 real,
already-existing data sources -- never hand-authored:

  DATABASE_CATALOG.json          -> entity_type=table
  FUNCTION_CATALOG.json          -> entity_type=function (+ implements_engine
                                     cross-reference against engine_inventory)
  AI_ROSTER_CATALOG.json         -> entity_type=ai_role
  20_ENGINES_10_GATEWAYS_PHASE_PLAN_2026-07-24.yaml
                                  -> entity_type=engine, entity_type=gateway
                                     (+ shares_implementation_with when two
                                     engines/gateways cite the same real file)
  ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml
                                  -> entity_type=route
  SOFTWARE_CATALOG.yaml          -> entity_type=script, entity_type=cron_job
  knowledge_engine (live sqlite table, scripts/superboss-register.py)
                                  -> entity_type=file, one per existing row
                                     (verification_status/last_verified_ts
                                     reused verbatim, not recomputed)
  capability_registry (live sqlite table, same DB)
                                  -> no new entity_type (not in this schema's
                                     closed enum) -- cross-checked against
                                     route entities' capability_name

Every "file" entity referenced by more than one source (engine/gateway
exists_as, route source/destination, table/function/ai_role defining file,
script path, cron_job command, knowledge_engine artifact_path) collapses into
ONE entity keyed by its real, live-verified absolute path -- not duplicated
per source. Idempotent: rewrites ai-os/WIRING_ENGINE_REGISTRY_2026-07-25.json
from scratch every run (a full snapshot; see WIRING_ENGINE_SCHEMA's own
generation.idempotent note for why Phase 0 does not need incremental diffing).

Usage: python3 scripts/generate_wiring_registry.py [--out PATH]
Exit code 0 on success. Prints a JSON summary (counts per entity_type +
relationship_type + total) to stdout.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

import yaml

VERIDIAN_ROOT = "/opt/veridian"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
REPO_AI_OS = os.path.join(REPO_ROOT, "ai-os")
# os.path.exists (not isdir) -- a git WORKTREE checkout (like this task's own
# workspace) has .git as a FILE ("gitdir: ..."), not a directory. The isdir-only
# check this used to be silently treated every worktree as a non-git deployment
# and fell through to MIRROR_AI_OS below, so local, not-yet-merged edits made in
# a worktree (e.g. this same phase's own ROUTE_REGISTRY_SCHEMA changes) were
# invisible to this script even when run directly against that worktree -- a
# real bug found and fixed by WIRING_ENGINE_PHASE_PLAN_2026-07-25.yaml phase_1.
IS_GIT_CHECKOUT = os.path.exists(os.path.join(REPO_ROOT, ".git"))
# The real, sync-repos.sh-kept-current (every 2h cron) git mirror -- same
# second location scripts/auto_phase_continuation.py's own PLAN_DIRS already
# reads. /opt/veridian/ai-os/ itself is NOT git-tracked and was confirmed this
# run to drift from it (its 20_ENGINES_10_GATEWAYS_PHASE_PLAN copy still lacks
# the gateway_inventory block a later, already-merged phase added).
MIRROR_AI_OS = f"{VERIDIAN_ROOT}/repos/claude-control/ai-os"


def resolve_doc_path(filename):
    """When run from an actual git checkout (this task's own workspace,
    possibly with not-yet-merged local changes), that checkout's own ai-os/
    is authoritative. When run from a flat, non-git deployment (this
    script's own live cron copy at /opt/veridian/scripts/), prefer the real
    git mirror over the drifted, non-git-tracked /opt/veridian/ai-os/."""
    if IS_GIT_CHECKOUT:
        return os.path.join(REPO_AI_OS, filename)
    mirror_path = os.path.join(MIRROR_AI_OS, filename)
    if os.path.isfile(mirror_path):
        return mirror_path
    return os.path.join(REPO_AI_OS, filename)


# The 3 huge catalogs are machine-generated live artifacts, never committed to
# git (too large, regenerated from live app code) -- only reachable at their
# real absolute /opt/veridian path. The knowledge_engine/capability_registry
# tables are likewise only real as the one live SQLite DB.
DATABASE_CATALOG = f"{VERIDIAN_ROOT}/ai-os/DATABASE_CATALOG.json"
FUNCTION_CATALOG = f"{VERIDIAN_ROOT}/ai-os/FUNCTION_CATALOG.json"
AI_ROSTER_CATALOG = f"{VERIDIAN_ROOT}/ai-os/AI_ROSTER_CATALOG.json"
ENGINES_GATEWAYS_PLAN = resolve_doc_path("20_ENGINES_10_GATEWAYS_PHASE_PLAN_2026-07-24.yaml")
ROUTE_REGISTRY_SCHEMA = resolve_doc_path("ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml")
SOFTWARE_CATALOG = resolve_doc_path("SOFTWARE_CATALOG.yaml")
DB_PATH = f"{VERIDIAN_ROOT}/ai-os/memory/superboss-register.sqlite"

DEFAULT_OUT = os.path.join(REPO_AI_OS, "WIRING_ENGINE_REGISTRY_2026-07-25.json")

VALID_VERIFICATION = {"VERIFIED_MATCH", "HASH_DRIFTED", "PATH_MISSING", "UNVERIFIED"}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def slug(s):
    return "".join(c if c.isalnum() else "_" for c in s).strip("_").lower()


def normalize_path(p):
    if not p:
        return p
    return p if p.startswith("/") else os.path.join(VERIDIAN_ROOT, p)


def source_system_for_path(p):
    return "github" if ("repos/" in p or p.startswith(f"{VERIDIAN_ROOT}/repos/")) else "server"


def path_exists(p):
    return os.path.exists(normalize_path(p))


class Registry:
    """Accumulates entities and de-duplicates file entities by their real
    normalized absolute path, so a path cited by N sources becomes ONE
    entity carrying N source_ref entries, not N rows."""

    def __init__(self):
        self.entities = []
        self.path_to_id = {}

    def add(self, entity):
        self.entities.append(entity)
        return entity["entity_id"]

    def get_or_create_file(self, raw_path, source_ref):
        abs_path = normalize_path(raw_path)
        if abs_path in self.path_to_id:
            eid = self.path_to_id[abs_path]
            for e in self.entities:
                if e["entity_id"] == eid:
                    if source_ref not in e["source_ref"]:
                        e["source_ref"].append(source_ref)
                    return eid
        eid = f"file-{hashlib.sha1(abs_path.encode()).hexdigest()[:12]}"
        self.path_to_id[abs_path] = eid
        self.add({
            "entity_id": eid,
            "entity_type": "file",
            "source_system": source_system_for_path(abs_path),
            "path": abs_path,
            "relationships": [],
            "last_verified_ts": now_iso(),
            "verification_status": "VERIFIED_MATCH" if os.path.exists(abs_path) else "PATH_MISSING",
            "source_ref": [source_ref],
            "metadata": None,
        })
        return eid

    def find_by_id(self, eid):
        for e in self.entities:
            if e["entity_id"] == eid:
                return e
        return None


def load_engines_gateways():
    with open(ENGINES_GATEWAYS_PLAN) as f:
        return yaml.safe_load(f)


def load_route_registry():
    with open(ROUTE_REGISTRY_SCHEMA) as f:
        return yaml.safe_load(f)


def load_software_catalog():
    with open(SOFTWARE_CATALOG) as f:
        return yaml.safe_load(f)


def build_engines_and_gateways(reg, doc):
    """entity_type=engine, entity_type=gateway + shares_implementation_with
    whenever two engine/gateway entities cite the exact same real file."""
    path_owners = {}  # abs_path -> [ (entity_id, kind) ]
    engine_ids_by_no = {}
    gateway_ids_by_id = {}

    for row in doc.get("engine_inventory", []):
        eid = f"engine-{row['engine_no']:02d}"
        engine_ids_by_no[row["engine_no"]] = eid
        rels = []
        for p in row.get("exists_as", []):
            fid = reg.get_or_create_file(p, "engine_inventory")
            rels.append({"target_entity_id": fid, "relationship_type": "implemented_by", "evidence": p})
            path_owners.setdefault(normalize_path(p), []).append((eid, row["engine_name"]))
        reg.add({
            "entity_id": eid,
            "entity_type": "engine",
            "source_system": "server",
            "path": "; ".join(row.get("exists_as", [])) or None,
            "relationships": rels,
            "last_verified_ts": now_iso(),
            "verification_status": "VERIFIED_MATCH" if row.get("verified_on_disk") else "UNVERIFIED",
            "source_ref": ["engine_inventory"],
            "metadata": {"engine_no": row["engine_no"], "engine_name": row["engine_name"],
                         "purpose": row.get("purpose"), "coverage": row.get("coverage")},
        })

    for row in doc.get("gateway_inventory", []):
        gid = f"gateway-{row['gateway_id']}"
        gateway_ids_by_id[row["gateway_id"]] = gid
        rels = []
        for p in row.get("exists_as", []):
            fid = reg.get_or_create_file(p, "gateway_inventory")
            rels.append({"target_entity_id": fid, "relationship_type": "implemented_by", "evidence": p})
            path_owners.setdefault(normalize_path(p), []).append((gid, row["gateway_name"]))
        reg.add({
            "entity_id": gid,
            "entity_type": "gateway",
            "source_system": "server",
            "path": "; ".join(row.get("exists_as", [])) or None,
            "relationships": rels,
            "last_verified_ts": now_iso(),
            "verification_status": "VERIFIED_MATCH" if row.get("verified_on_disk") else "UNVERIFIED",
            "source_ref": ["gateway_inventory"],
            "metadata": {"gateway_no": row["gateway_no"], "gateway_id": row["gateway_id"],
                         "gateway_name": row["gateway_name"], "purpose": row.get("purpose"),
                         "coverage": row.get("coverage")},
        })

    # shares_implementation_with: two distinct engine/gateway entities citing
    # the exact same real path (a fact, never an inferred call relationship --
    # see WIRING_ENGINE_SCHEMA meta.honest_limitation).
    shared_count = 0
    for abs_path, owners in path_owners.items():
        distinct_ids = sorted(set(o[0] for o in owners))
        if len(distinct_ids) < 2:
            continue
        for i in range(len(distinct_ids)):
            for j in range(len(distinct_ids)):
                if i == j:
                    continue
                e = reg.find_by_id(distinct_ids[i])
                e["relationships"].append({
                    "target_entity_id": distinct_ids[j],
                    "relationship_type": "shares_implementation_with",
                    "evidence": f"both cite {abs_path}",
                })
        shared_count += 1

    return engine_ids_by_no, gateway_ids_by_id


def build_tables(reg):
    if not os.path.isfile(DATABASE_CATALOG):
        print(f"  ! {DATABASE_CATALOG} not found, skipping table entities", file=sys.stderr)
        return 0
    with open(DATABASE_CATALOG) as f:
        cat = json.load(f)
    source_file = cat.get("source_file")
    file_id = reg.get_or_create_file(source_file, "database_catalog") if source_file else None
    count = 0
    for t in cat.get("tables", []):
        eid = f"table-{slug(t.get('schema', 'public'))}__{slug(t['table_name'])}"
        rels = []
        if file_id:
            rels.append({"target_entity_id": file_id, "relationship_type": "defined_in", "evidence": source_file})
        reg.add({
            "entity_id": eid,
            "entity_type": "table",
            "source_system": "supabase",
            "path": f"{t.get('schema', 'public')}.{t['table_name']}",
            "relationships": rels,
            "last_verified_ts": now_iso(),
            "verification_status": "VERIFIED_MATCH" if (file_id and path_exists(source_file)) else "UNVERIFIED",
            "source_ref": ["database_catalog"],
            "metadata": {"export_name": t.get("export_name"), "column_count": t.get("column_count")},
        })
        count += 1
    return count


def build_functions(reg, engine_ids_by_no, engine_inventory):
    if not os.path.isfile(FUNCTION_CATALOG):
        print(f"  ! {FUNCTION_CATALOG} not found, skipping function entities", file=sys.stderr)
        return 0
    with open(FUNCTION_CATALOG) as f:
        cat = json.load(f)
    # source_root e.g. "src/ (compliance-tracker)" -- every function's own
    # "file" field is relative to repos/compliance-tracker.
    repo_prefix = "repos/compliance-tracker"

    # Pre-build (engine_no, real_exists_as_path) pairs for prefix matching --
    # cheap mechanical cross-reference, not a guess.
    engine_paths = [(row["engine_no"], p) for row in engine_inventory for p in row.get("exists_as", [])]

    count = 0
    for fn in cat.get("functions", []):
        rel_path = f"{repo_prefix}/{fn['file']}"
        abs_path = normalize_path(rel_path)
        fn_key = f"{rel_path}:{fn.get('line')}:{fn['name']}"
        eid = f"function-{hashlib.sha1(fn_key.encode()).hexdigest()[:12]}"
        file_id = reg.get_or_create_file(rel_path, "function_catalog")
        rels = [{"target_entity_id": file_id, "relationship_type": "defined_in", "evidence": rel_path}]
        for engine_no, ep in engine_paths:
            ep_abs = normalize_path(ep)
            if abs_path == ep_abs or abs_path.startswith(ep_abs.rstrip("/") + "/"):
                rels.append({
                    "target_entity_id": engine_ids_by_no.get(engine_no),
                    "relationship_type": "implements_engine",
                    "evidence": f"{rel_path} matches engine exists_as {ep}",
                })
        reg.add({
            "entity_id": eid,
            "entity_type": "function",
            "source_system": "github",
            "path": rel_path,
            "relationships": rels,
            "last_verified_ts": now_iso(),
            "verification_status": "VERIFIED_MATCH" if os.path.exists(abs_path) else "PATH_MISSING",
            "source_ref": ["function_catalog"],
            "metadata": {"name": fn["name"], "kind": fn.get("kind"), "exported": fn.get("exported"),
                         "async": fn.get("async"), "line": fn.get("line")},
        })
        count += 1
    return count


def build_ai_roles(reg):
    if not os.path.isfile(AI_ROSTER_CATALOG):
        print(f"  ! {AI_ROSTER_CATALOG} not found, skipping ai_role entities", file=sys.stderr)
        return 0
    with open(AI_ROSTER_CATALOG) as f:
        cat = json.load(f)
    source_file = cat.get("source_file")
    file_id = reg.get_or_create_file(source_file, "ai_roster_catalog") if source_file else None
    count = 0
    for r in cat.get("roles", []):
        eid = f"ai_role-{slug(r['roleKey'])}"
        rels = []
        if file_id:
            rels.append({"target_entity_id": file_id, "relationship_type": "defined_in", "evidence": source_file})
        reg.add({
            "entity_id": eid,
            "entity_type": "ai_role",
            "source_system": "github",
            "path": r["roleKey"],
            "relationships": rels,
            "last_verified_ts": now_iso(),
            "verification_status": "VERIFIED_MATCH" if (file_id and path_exists(source_file)) else "UNVERIFIED",
            "source_ref": ["ai_roster_catalog"],
            "metadata": {"team": r.get("team"), "title": r.get("title"), "model": r.get("model"),
                         "isHuman": r.get("isHuman"), "escalationLevel": r.get("escalationLevel")},
        })
        count += 1
    return count


def build_routes(reg, engine_ids_by_no, gateway_ids_by_id, cap_by_name):
    if not os.path.isfile(ROUTE_REGISTRY_SCHEMA):
        print(f"  ! {ROUTE_REGISTRY_SCHEMA} not found, skipping route entities", file=sys.stderr)
        return 0
    doc = load_route_registry()
    count = 0
    for r in doc.get("populated_routes", []):
        eid = f"route-{r['route_id']}"
        src_id = reg.get_or_create_file(r["source"], "route_registry_schema")
        dst_id = reg.get_or_create_file(r["destination"], "route_registry_schema")
        rels = [
            {"target_entity_id": src_id, "relationship_type": "originates_at", "evidence": r["source"]},
            {"target_entity_id": dst_id, "relationship_type": "terminates_at", "evidence": r["destination"]},
        ]
        for hop in r.get("expected_path", []):
            if hop.get("engine_no"):
                rels.append({
                    "target_entity_id": engine_ids_by_no.get(hop["engine_no"]),
                    "relationship_type": "hops_through",
                    "evidence": f"hop {hop['hop_no']}: {hop['hop_name']} ({hop['live_or_planned']}) via {hop['mechanism_path']}",
                })
            elif hop.get("gateway_id"):
                # Same real, evidence-only convention as the engine_no branch above --
                # previously MISSING entirely (a hop_type: gateway entry was silently
                # dropped no matter what expected_path said), the literal reason this
                # registry's hops_through relationships have never once targeted a
                # gateway entity. See WIRING_ENGINE_PHASE_PLAN_2026-07-25.yaml phase_1.
                rels.append({
                    "target_entity_id": gateway_ids_by_id.get(hop["gateway_id"]),
                    "relationship_type": "hops_through",
                    "evidence": f"hop {hop['hop_no']}: {hop['hop_name']} ({hop['live_or_planned']}) via {hop['mechanism_path']}",
                })
        both_paths_real = path_exists(r["source"]) and path_exists(r["destination"])
        cap_row = cap_by_name.get(r["capability_name"])
        if cap_row:
            rels.append({
                "target_entity_id": None,
                "relationship_type": "registered_capability_match",
                "evidence": f"capability_registry row found live (confidence={cap_row[0]}, ai_required={bool(cap_row[1])})",
            })
        dvs = r.get("dependency_validation_status")
        if not both_paths_real:
            status = "PATH_MISSING"
        elif dvs == "validated_match":
            status = "VERIFIED_MATCH"
        elif dvs == "validated_mismatch":
            status = "HASH_DRIFTED"
        else:
            status = "UNVERIFIED"
        reg.add({
            "entity_id": eid,
            "entity_type": "route",
            "source_system": "github",
            "path": f"{r['source']} -> {r['destination']}",
            "relationships": rels,
            "last_verified_ts": now_iso(),
            "verification_status": status,
            "source_ref": ["route_registry_schema"] + (["capability_registry"] if cap_row else []),
            "metadata": {"capability_name": r["capability_name"], "test_status": r.get("test_status"),
                         "trace_verification_status": r.get("trace_verification_status")},
        })
        count += 1
    return count


def build_scripts_and_cron(reg):
    if not os.path.isfile(SOFTWARE_CATALOG):
        print(f"  ! {SOFTWARE_CATALOG} not found, skipping script/cron_job entities", file=sys.stderr)
        return 0, 0
    doc = load_software_catalog()

    script_ids_by_path = {}
    script_count = 0
    for s in doc.get("scripts", []):
        eid = f"script-{slug(os.path.basename(s['path']))}"
        reg.add({
            "entity_id": eid,
            "entity_type": "script",
            "source_system": source_system_for_path(s["path"]),
            "path": s["path"],
            "relationships": [],
            "last_verified_ts": now_iso(),
            "verification_status": "VERIFIED_MATCH" if os.path.exists(s["path"]) else "PATH_MISSING",
            "source_ref": ["software_catalog"],
            "metadata": {"purpose": s.get("purpose"), "cron_scheduled": s.get("cron_scheduled")},
        })
        script_ids_by_path[s["path"]] = eid
        script_count += 1

    cron_count = 0
    for i, c in enumerate(doc.get("cron_jobs", [])):
        eid = f"cron_job-{i:03d}"
        command = c.get("raw", c.get("command", ""))
        rels = []
        for spath, sid in script_ids_by_path.items():
            if spath in command:
                rels.append({"target_entity_id": sid, "relationship_type": "triggers", "evidence": command})
                script_entity = reg.find_by_id(sid)
                script_entity["relationships"].append({
                    "target_entity_id": eid, "relationship_type": "triggered_by", "evidence": command,
                })
        reg.add({
            "entity_id": eid,
            "entity_type": "cron_job",
            "source_system": "server",
            "path": command,
            "relationships": rels,
            "last_verified_ts": now_iso(),
            "verification_status": "VERIFIED_MATCH" if rels else "UNVERIFIED",
            "source_ref": ["software_catalog"],
            "metadata": {"schedule": c.get("schedule")},
        })
        cron_count += 1

    return script_count, cron_count


def load_capability_registry():
    """Live read-only query -- never mutates the DB. Returns
    {capability_name: (confidence, ai_required)}."""
    if not os.path.isfile(DB_PATH):
        return {}
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=10)
        rows = conn.execute("SELECT capability_name, confidence, ai_required FROM capability_registry").fetchall()
        conn.close()
        return {r[0]: (r[1], r[2]) for r in rows}
    except sqlite3.Error as e:
        print(f"  ! capability_registry read failed: {e}", file=sys.stderr)
        return {}


def build_from_knowledge_engine(reg):
    """entity_type=file, one per existing knowledge_engine row.
    verification_status/last_verified_ts reused VERBATIM (not recomputed --
    avoids a duplicate verification pass over an artifact already tracked
    there). entity_relationships passed through as ke:<type>, target
    resolved against this run's own path->entity_id map when possible."""
    if not os.path.isfile(DB_PATH):
        print(f"  ! {DB_PATH} not found, skipping knowledge_engine rows", file=sys.stderr)
        return 0
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=10)
        rows = conn.execute(
            "SELECT artifact_id, artifact_path, verification_status, last_verified_ts, tags, entity_relationships "
            "FROM knowledge_engine"
        ).fetchall()
        conn.close()
    except sqlite3.Error as e:
        print(f"  ! knowledge_engine read failed: {e}", file=sys.stderr)
        return 0

    count = 0
    for artifact_id, artifact_path, verification_status, last_verified_ts, tags, entity_relationships in rows:
        abs_path = normalize_path(artifact_path)
        tag_list = (tags or "").split(",")
        if "source:VERCEL" in tag_list:
            src_sys = "vercel"
        elif "source:SUPABASE" in tag_list:
            src_sys = "supabase"
        elif "source:GITHUB" in tag_list:
            src_sys = "github"
        else:
            src_sys = "server"  # SERVER / LOCAL both live on this box

        vstatus = verification_status if verification_status in VALID_VERIFICATION else "UNVERIFIED"

        rels = []
        try:
            ke_rels = json.loads(entity_relationships) if entity_relationships else []
        except json.JSONDecodeError:
            ke_rels = []
        for kr in ke_rels:
            target_path = kr.get("path")
            target_id = reg.path_to_id.get(normalize_path(target_path)) if target_path else None
            rels.append({
                "target_entity_id": target_id,
                "relationship_type": f"ke:{kr.get('relationship_type', 'related_to')}",
                "evidence": kr.get("evidence") or target_path or "",
            })

        if abs_path in reg.path_to_id:
            # Already emitted as a file entity by another source (e.g. an
            # engine/gateway exists_as path) -- enrich, don't duplicate.
            eid = reg.path_to_id[abs_path]
            e = reg.find_by_id(eid)
            e["source_ref"].append("knowledge_engine")
            e["relationships"].extend(rels)
            e["verification_status"] = vstatus
            e["last_verified_ts"] = last_verified_ts or e["last_verified_ts"]
            e["metadata"] = e.get("metadata") or {}
            e["metadata"]["knowledge_engine_artifact_id"] = artifact_id
        else:
            eid = f"file-ke-{artifact_id}"
            reg.path_to_id[abs_path] = eid
            reg.add({
                "entity_id": eid,
                "entity_type": "file",
                "source_system": src_sys,
                "path": abs_path,
                "relationships": rels,
                "last_verified_ts": last_verified_ts or now_iso(),
                "verification_status": vstatus,
                "source_ref": ["knowledge_engine"],
                "metadata": {"knowledge_engine_artifact_id": artifact_id},
            })
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()

    reg = Registry()

    ge_doc = load_engines_gateways()
    engine_ids_by_no, gateway_ids_by_id = build_engines_and_gateways(reg, ge_doc)

    table_count = build_tables(reg)
    function_count = build_functions(reg, engine_ids_by_no, ge_doc.get("engine_inventory", []))
    ai_role_count = build_ai_roles(reg)
    cap_by_name = load_capability_registry()
    route_count = build_routes(reg, engine_ids_by_no, gateway_ids_by_id, cap_by_name)
    script_count, cron_count = build_scripts_and_cron(reg)
    ke_count = build_from_knowledge_engine(reg)

    counts_by_type = {}
    counts_by_rel = {}
    for e in reg.entities:
        counts_by_type[e["entity_type"]] = counts_by_type.get(e["entity_type"], 0) + 1
        for r in e["relationships"]:
            counts_by_rel[r["relationship_type"]] = counts_by_rel.get(r["relationship_type"], 0) + 1

    output = {
        "meta": {
            "generated_by": "scripts/generate_wiring_registry.py",
            "generated_ts": now_iso(),
            "schema": "ai-os/WIRING_ENGINE_SCHEMA_2026-07-25.yaml",
            "entity_count": len(reg.entities),
        },
        "entities": reg.entities,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(output, f, indent=2)

    summary = {
        "ok": True,
        "output_path": args.out,
        "entity_count": len(reg.entities),
        "counts_by_entity_type": counts_by_type,
        "counts_by_relationship_type": counts_by_rel,
        "raw_source_counts": {
            "engine_inventory": len(ge_doc.get("engine_inventory", [])),
            "gateway_inventory": len(ge_doc.get("gateway_inventory", [])),
            "database_catalog_tables": table_count,
            "function_catalog_functions": function_count,
            "ai_roster_roles": ai_role_count,
            "route_registry_routes": route_count,
            "software_catalog_scripts": script_count,
            "software_catalog_cron_jobs": cron_count,
            "knowledge_engine_rows": ke_count,
            "capability_registry_rows_crosschecked": len(cap_by_name),
        },
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
