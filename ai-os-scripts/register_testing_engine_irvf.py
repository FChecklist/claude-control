#!/usr/bin/env python3
"""Idempotently adds the registries.testing_engine_irvf entry to a MASTER_INDEX.yaml
path given on argv[1] (or /opt/veridian/ai-os/MASTER_INDEX.yaml by default). Real gap
found by SESSION_AUDIT_2026-07-24 (task-20260724-081715): task-20260724-063645's own 3
deliverable files (ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml, ROUTE_COVERAGE_METHODOLOGY_2026-07-24.yaml,
TESTING_ENGINE_PHASE_PLAN_2026-07-24.yaml) each declared master_index_registry_id:
testing_engine_irvf in their own registration field, but no registries entry with that id
was ever added -- this script closes that gap the same way every other engine's registry
entry in this file was added (a single dict appended to the registries list), run against
the live copy and the git-tracked copy, never hand-typed into either file directly.
"""
import sys
import yaml

ENTRY = {
    "id": "testing_engine_irvf",
    "type": "route_registry_coverage_methodology_and_phase_plan",
    "path": (
        "ai-os/ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml + "
        "ai-os/ROUTE_COVERAGE_METHODOLOGY_2026-07-24.yaml + "
        "ai-os/TESTING_ENGINE_PHASE_PLAN_2026-07-24.yaml"
    ),
    "scope": (
        "Phase 0 (task-20260724-063645, VERIDIAN Testing Engine / IRVF -- Intent-Route-"
        "Verification-Framework) of the platform's route-level testing engine: a real "
        "route registry (5 populated_routes, one per real capability from "
        "registries.engines_gateways_architecture's Capability Registry, each with a real "
        "expected_path of engine hops), a 9-type coverage methodology (each type either "
        "MEASURABLE_TODAY with a real computed value or NOT_YET_MEASURABLE with an explicit, "
        "specific gap and unblocking_phase), and this engine's own phased build plan "
        "(TESTING_ENGINE_PHASE_PLAN_2026-07-24.yaml phases[] + dependency_table), sequenced "
        "after registries.engines_gateways_architecture and registries.auditor_engine where "
        "genuinely dependent (e.g. integration_coverage blocked on Auditor Engine's own "
        "api-contract domain authoring real OpenAPI docs)."
    ),
    "status": "phase_0_complete_phase_1_plus_not_yet_dispatched",
    "query_command": (
        'python3 scripts/superboss-register.py query-knowledge "testing_engine_irvf" '
        "--tag domain:testing_engine_irvf"
    ),
    "next_phase": (
        "Phase 1 (route/capability auto-generation + leaf-enumeration script per "
        "ROUTE_COVERAGE_METHODOLOGY_2026-07-24.yaml's capability_coverage gap) per "
        "TESTING_ENGINE_PHASE_PLAN_2026-07-24.yaml phases[] -- dispatched as a separate "
        "task, not part of this registry entry's own scope."
    ),
}


def add_entry(path):
    with open(path) as f:
        doc = yaml.safe_load(f)
    ids = [r.get("id") for r in doc["registries"]]
    if ENTRY["id"] in ids:
        print(f"{path}: already present, no change")
        return False
    doc["registries"].append(dict(ENTRY))
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        yaml.safe_dump(doc, f, sort_keys=False, default_flow_style=False)
    import os
    os.replace(tmp, path)
    print(f"{path}: added registries.testing_engine_irvf")
    return True


if __name__ == "__main__":
    targets = sys.argv[1:] or ["/opt/veridian/ai-os/MASTER_INDEX.yaml"]
    for t in targets:
        add_entry(t)
