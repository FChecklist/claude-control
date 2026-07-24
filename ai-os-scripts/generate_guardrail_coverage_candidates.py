#!/usr/bin/env python3
"""
generate_guardrail_coverage_candidates.py -- Phase 2 of VERIDIAN 20-ENGINE/
10-GATEWAY architecture (task-20260724-115041-phase2-give-policy-engine-
preflight-guar), closes_engines: [6] (Rule Engine).

Owner directive: "all registry/catalog data must be produced by scripts, not
hand-authored AI prose" -- same discipline generate_capability_registry_candidates.py
already used for Phase 0/1. This script greps 2 real, live files (not
invented lists):

  1. repos/compliance-tracker/src/lib/services/capability-tree-service.ts's
     WIRED_ENGINE_INPUT_FIELDS / MATH_WIRED_ENGINE_INPUT_FIELDS-style
     `Record<string, CapabilityInputField[]>` blocks -- the real capability-
     tree leaves that have explicit, typed input fields (the leaves a
     sanity-bound guardrail can actually validate, same shape as the 4
     leaf-groups guardrail-registrations.ts already covers: GST/loan/
     gratuity/commission).
  2. repos/compliance-tracker/src/lib/guardrail-registrations.ts's real
     registerGuardrail(leafKey, ...) calls -- the leaves already covered.

The diff (leaf keys with input fields but no registerGuardrail call) is
this phase's objective's own "prioritized by Capability Registry
ai_required=false + no business_rules registered" list -- these VCEL
calculation engines are deliberately deterministic (ai_required=false is a
justified default per Phase 1's own finding: "most of this codebase's VCEL
engines are deliberately deterministic"), and their absence from
guardrail-registrations.ts is exactly "no business_rules registered".

This does NOT edit guardrail-registrations.ts (repos/compliance-tracker is a
separate git repo -- see ai-os/POLICY_DECISION_SCHEMA_2026-07-24.yaml's
repo_boundary_honestly_stated). It writes the real, verified candidate list
to ai-os/GUARDRAIL_COVERAGE_CANDIDATES_2026-07-24.yaml for that repo's own
next PR to consume.

Run: python3 ai-os-scripts/generate_guardrail_coverage_candidates.py
"""
import json
import os
import re
import subprocess
import sys

VERIDIAN_ROOT = "/opt/veridian"
# Inputs are read from the real, live source of truth: compliance-tracker (a
# separate repo) and the shared superboss-register.py DB, same absolute-path
# convention populate_capability_registry.py already uses for both.
CAPABILITY_TREE_PATH = f"{VERIDIAN_ROOT}/repos/compliance-tracker/src/lib/services/capability-tree-service.ts"
GUARDRAIL_REGISTRATIONS_PATH = f"{VERIDIAN_ROOT}/repos/compliance-tracker/src/lib/guardrail-registrations.ts"
SUPERBOSS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "superboss-register.py")
# Output is a new, committed deliverable of THIS git repo (claude-control) --
# written relative to this script's own repo checkout (not the absolute
# /opt/veridian/ai-os/ live path), so `git add`/`git commit` in whichever
# workspace this runs from actually picks it up.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(REPO_ROOT, "ai-os", "GUARDRAIL_COVERAGE_CANDIDATES_2026-07-24.yaml")

# Field-schema keys that appear at the same 2-space indent as real leaf keys
# inside CapabilityInputField object literals (`{ key: ..., label: ..., type:
# ... }`) -- these are noise from the shared field-shape declaration, not
# capability leaf keys, and must be excluded.
FIELD_SCHEMA_NOISE = {"key", "label", "type", "leaf", "optional", "options"}


def extract_leaf_keys_with_input_fields(path):
    """Scoped strictly to the 22 real `const X_WIRED_ENGINE_INPUT_FIELDS: Record<string,
    CapabilityInputField[]> = { ... }` blocks (one per VCEL domain engine) -- a naive whole-file scan
    also catches unrelated 2-space-indented object keys (domain/category maps like `crm: [...]`,
    `ERP: "ERP / Finance"`) that are not capability-tree leaves at all."""
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    keys = set()
    in_block = False
    for line in lines:
        if re.match(r"^const [A-Z_]+_WIRED_ENGINE_INPUT_FIELDS: Record<string, CapabilityInputField\[\]> = \{", line):
            in_block = True
            continue
        if in_block and line.startswith("}"):
            in_block = False
            continue
        if in_block:
            m = re.match(r"^  ([a-zA-Z_][a-zA-Z0-9_]*):", line)
            if m and m.group(1) not in FIELD_SCHEMA_NOISE:
                keys.add(m.group(1))
    return keys


def extract_registered_leaf_keys(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    # export const XXX_LEAF = "value" -- resolves the named-constant identifiers registerGuardrail()
    # calls actually pass (e.g. registerGuardrail(GRATUITY_CALCULATOR_LEAF, ...)), not a literal string.
    const_map = dict(re.findall(r'export const ([A-Z0-9_]+)\s*=\s*"([a-zA-Z0-9_.]+)"', text))
    # export const XXX_LEAVES = ["a", "b", ...] -- array-of-leaves constants.
    const_array_map = {}
    for name, body in re.findall(r"export const ([A-Z0-9_]+)\s*=\s*\[(.*?)\]", text, re.DOTALL):
        const_array_map[name] = set(re.findall(r'"([a-zA-Z0-9_.]+)"', body))

    direct = set()
    for m in re.finditer(r"registerGuardrail\(\s*([A-Za-z0-9_]+)", text):
        arg = m.group(1)
        if arg.startswith('"'):
            continue
        if arg in const_map:
            direct.add(const_map[arg])
        elif arg == "leaf":
            continue  # resolved via the for-loop arrays below
    # Direct string-literal calls: registerGuardrail("literal_leaf", ...).
    direct |= set(re.findall(r'registerGuardrail\(\s*"([a-zA-Z0-9_.]+)"', text))
    # for (const leaf of X_LEAVES) registerGuardrail(leaf, ...) -- resolve the named array constants.
    for name in re.findall(r"for \(const leaf of ([A-Z0-9_]+)\)", text):
        direct |= const_array_map.get(name, set())
    return direct


def query_capability_registry():
    """Cross-references the Phase 1 live capability_registry table -- rows already registered there
    with ai_required=false confirm the deterministic assumption for any leaf key that also appears
    as a capability_name, rather than asserting it purely from the TS grep alone."""
    try:
        proc = subprocess.run(["python3", SUPERBOSS, "list-capabilities"], capture_output=True, text=True, timeout=30)
        data = json.loads(proc.stdout)
        return {c["capability_name"]: c for c in data.get("capabilities", [])}
    except Exception:
        return {}


def main():
    tree_leaves = extract_leaf_keys_with_input_fields(CAPABILITY_TREE_PATH)
    registered_leaves = extract_registered_leaf_keys(GUARDRAIL_REGISTRATIONS_PATH)
    registry_rows = query_capability_registry()

    uncovered = sorted(tree_leaves - registered_leaves)

    candidates = []
    for leaf in uncovered:
        registry_row = registry_rows.get(leaf)
        candidates.append({
            "leaf_key": leaf,
            "in_capability_registry": registry_row is not None,
            "ai_required": registry_row["ai_required"] if registry_row else False,
            "ai_required_source": "capability_registry live row" if registry_row else "inferred: WIRED_ENGINE_INPUT_FIELDS leaf, same VCEL-deterministic pattern as every other registered leaf in this file",
            "business_rules_registered": bool(registry_row["business_rules"]) if registry_row else False,
            "mechanism_path_if_registered": "repos/compliance-tracker/src/lib/guardrail-registrations.ts",
        })

    doc_lines = [
        "meta:",
        "  title: VERIDIAN Guardrail Coverage Candidates (Phase 2 deliverable)",
        "  created: '2026-07-24'",
        "  produced_by_task: task-20260724-115041-phase2-give-policy-engine-preflight-guar",
        "  produced_by_script: ai-os-scripts/generate_guardrail_coverage_candidates.py",
        "  scope: 'Prioritized list of real capability-tree leaves (from",
        "    repos/compliance-tracker/src/lib/services/capability-tree-service.ts, live grep, not invented)",
        "    that have explicit typed input fields but zero registerGuardrail() registration in",
        "    repos/compliance-tracker/src/lib/guardrail-registrations.ts (live grep, not invented) -- the",
        "    literal \"ai_required=false + no business_rules registered\" prioritization this phase''s",
        "    objective asks for. Consumed by compliance-tracker''s own next PR (out of this task''s repo",
        "    boundary -- see ai-os/POLICY_DECISION_SCHEMA_2026-07-24.yaml''s repo_boundary_honestly_stated).'",
        f"  tree_leaves_with_input_fields_count: {len(tree_leaves)}",
        f"  already_registered_count: {len(tree_leaves & registered_leaves)}",
        f"  uncovered_candidate_count: {len(uncovered)}",
        "candidates:",
    ]
    for c in candidates:
        doc_lines.append(f"  - leaf_key: {c['leaf_key']}")
        doc_lines.append(f"    in_capability_registry: {str(c['in_capability_registry']).lower()}")
        doc_lines.append(f"    ai_required: {str(c['ai_required']).lower()}")
        doc_lines.append(f"    ai_required_source: \"{c['ai_required_source']}\"")
        doc_lines.append(f"    business_rules_registered: {str(c['business_rules_registered']).lower()}")
        doc_lines.append(f"    mechanism_path_if_registered: {c['mechanism_path_if_registered']}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(doc_lines) + "\n")

    print(json.dumps({
        "tree_leaves_with_input_fields_count": len(tree_leaves),
        "already_registered_count": len(tree_leaves & registered_leaves),
        "uncovered_candidate_count": len(uncovered),
        "uncovered_leaves": uncovered,
        "output_path": OUTPUT_PATH,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
