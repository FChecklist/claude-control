#!/usr/bin/env python3
"""
generate_capability_registry_candidates.py -- Phase 0 of VERIDIAN 20-ENGINE/
10-GATEWAY architecture (task-20260724-053213), Capability Registry Engine
schema deliverable (ai-os/CAPABILITY_REGISTRY_SCHEMA_2026-07-24.yaml).

Owner directive: "all registry/catalog data must be produced by scripts,
not hand-authored AI prose." This script is the live-verification pass for
every apis[]/ui_screens[]/business_rules[].mechanism_path/documents[] path
cited in populated_capabilities: -- each is a real path found by grepping
compliance-tracker's route/workflow/guardrail definitions this session
(task-execution-engine.ts's dispatchEngine switch, guardrail-registrations.ts,
capability-tree-service.ts, capability-registry-service.ts). The script does
not invent capability names or paths; it verifies the ones a human/AI
pointed it at, exactly as generate_engines_gateways_inventory.py does for
the 20-engine inventory.

Run: python3 ai-os/scripts/generate_capability_registry_candidates.py
Exits non-zero if any cited path is missing (drift signal).
"""
import os
import sys
import yaml

VERIDIAN_ROOT = "/opt/veridian"
SCHEMA_PATH = f"{VERIDIAN_ROOT}/ai-os/CAPABILITY_REGISTRY_SCHEMA_2026-07-24.yaml"


def collect_paths(capability):
    paths = []
    for field in ("apis", "ui_screens", "documents", "reports"):
        for p in (capability.get(field) or []):
            paths.append((f"{capability['capability_name']}.{field}", p))
    for rule in (capability.get("business_rules") or []):
        if rule.get("mechanism_path"):
            paths.append((f"{capability['capability_name']}.business_rules.mechanism_path", rule["mechanism_path"]))
    workflow = capability.get("workflow")
    if workflow and "(" in workflow:
        paths.append((f"{capability['capability_name']}.workflow", workflow.split(" (")[0]))
    automation = capability.get("automation")
    if automation and automation.startswith("repos/") or (automation and automation.startswith("ai-os/")):
        paths.append((f"{capability['capability_name']}.automation", automation.split(" (")[0]))
    return paths


def main():
    with open(SCHEMA_PATH) as f:
        doc = yaml.safe_load(f)
    capabilities = doc.get("populated_capabilities", [])
    all_ok = True
    checked_count = 0
    for cap in capabilities:
        for label, rel_path in collect_paths(cap):
            # documents[] may cite a prose section (e.g. "PLATFORM_STRATEGY.md §24
            # (cited in ...)") rather than a bare path -- only verify tokens that
            # look like a real repo-relative path (contain a "/" and a file
            # extension or known dir prefix).
            candidate = rel_path.split(" (")[0].strip()
            if "/" not in candidate:
                continue
            abs_path = os.path.join(VERIDIAN_ROOT, candidate)
            exists = os.path.exists(abs_path)
            checked_count += 1
            status = "OK" if exists else "MISSING"
            if not exists:
                all_ok = False
            print(f"{status:8s} {label}: {candidate}")
    print(f"\n{checked_count} paths checked, {'ALL VERIFIED' if all_ok else 'DRIFT DETECTED'}")
    print(f"{len(capabilities)} populated_capabilities rows in {SCHEMA_PATH}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
