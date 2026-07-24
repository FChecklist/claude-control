#!/usr/bin/env python3
"""
generate_route_registry_candidates.py -- Phase 0 of VERIDIAN TESTING ENGINE /
IRVF (task-20260724-063645), Route Registry schema deliverable
(ai-os/ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml).

Owner directive: "all registry/catalog data must be produced by scripts, not
hand-authored AI prose." This script is the live-verification pass for every
source/destination/expected_path[].mechanism_path cited in populated_routes:
-- each is a real path derived from ai-os/CAPABILITY_REGISTRY_SCHEMA_2026-07-24.yaml's
populated_capabilities and ai-os/20_ENGINES_10_GATEWAYS_PHASE_PLAN_2026-07-24.yaml's
engine_inventory. It does not invent route names or paths; it verifies the
ones this task derived, exactly as generate_capability_registry_candidates.py
does for the Capability Registry, and cross-checks that every route's
capability_name has a matching row in the Capability Registry (1:1 parity is
this task's own SUCCESS_CRITERIA floor).

Run: python3 ai-os-scripts/generate_route_registry_candidates.py
Exits non-zero if any cited path is missing or any route lacks a matching
capability (drift signal).
"""
import os
import sys
import yaml

VERIDIAN_ROOT = "/opt/veridian"
ROUTE_SCHEMA_PATH = f"{VERIDIAN_ROOT}/ai-os/ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml"
CAPABILITY_SCHEMA_PATH = f"{VERIDIAN_ROOT}/ai-os/CAPABILITY_REGISTRY_SCHEMA_2026-07-24.yaml"


def collect_paths(route):
    paths = [
        (f"{route['route_id']}.source", route["source"]),
        (f"{route['route_id']}.destination", route["destination"]),
    ]
    for hop in route.get("expected_path", []):
        paths.append((f"{route['route_id']}.expected_path[{hop['hop_no']}].mechanism_path", hop["mechanism_path"]))
    return paths


def main():
    with open(ROUTE_SCHEMA_PATH) as f:
        route_doc = yaml.safe_load(f)
    with open(CAPABILITY_SCHEMA_PATH) as f:
        capability_doc = yaml.safe_load(f)

    routes = route_doc.get("populated_routes", [])
    capability_names = {c["capability_name"] for c in capability_doc.get("populated_capabilities", [])}

    all_ok = True
    checked_count = 0

    for route in routes:
        cap_name = route.get("capability_name")
        if cap_name not in capability_names:
            print(f"MISSING  {route['route_id']}: no matching capability_name '{cap_name}' in "
                  f"CAPABILITY_REGISTRY_SCHEMA_2026-07-24.yaml populated_capabilities")
            all_ok = False
            continue

        for label, rel_path in collect_paths(route):
            abs_path = os.path.join(VERIDIAN_ROOT, rel_path)
            exists = os.path.exists(abs_path)
            checked_count += 1
            status = "OK" if exists else "MISSING"
            if not exists:
                all_ok = False
            print(f"{status:8s} {label}: {rel_path}")

    route_capability_names = {r["capability_name"] for r in routes}
    uncovered = capability_names - route_capability_names
    if uncovered:
        print(f"\nWARNING: {len(uncovered)} capability(ies) with no route yet: {sorted(uncovered)}")
        all_ok = False

    print(f"\n{checked_count} paths checked, {'ALL VERIFIED' if all_ok else 'DRIFT DETECTED'}")
    print(f"{len(routes)} populated_routes rows covering {len(route_capability_names)}/"
          f"{len(capability_names)} registered capabilities")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
