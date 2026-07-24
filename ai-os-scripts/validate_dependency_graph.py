#!/usr/bin/env python3
"""
validate_dependency_graph.py -- Phase 4 of VERIDIAN TESTING ENGINE / IRVF
(TESTING_ENGINE_PHASE_PLAN_2026-07-24.yaml phase_4_dependency_graph_validation).

Owner directive: "all registry/catalog data must be produced by scripts, not
hand-authored AI prose." This turns this task's own hand-verified
expected_path.live_or_planned field (ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml)
into a re-runnable, software-driven check instead of a one-time manual grep.

WHAT IT DOES, per populated_route:
  1. HOP VALIDATION -- for each expected_path hop, statically re-derives
     whether the real call site the hop claims actually exists today:
       - hop_name "Workflow Engine" -> reuses Phase 1's own
         generate_route_tests.derive_dispatch_target() (imported, not
         duplicated) to check task-execution-engine.ts's dispatchEngine()
         switch for a real `case "<capability_name>":`.
       - hop_name "Rule Engine" -> parses guardrail-registrations.ts for
         real registerGuardrail(...) call sites, resolving the same
         const-alias / array-of-leaves indirection that file actually uses
         (e.g. GST_SPLIT_ENGINE_LEAVES iterated in a for-loop), and checks
         whether capability_name is really registered as a leaf.
       - every other hop_type -> real file/dir-exists check on mechanism_path.
     The hop's live_or_planned claim is compared against what was actually
     found; a mismatch (claimed live but not found, or claimed planned but
     already live) is recorded, never silently reconciled.
  2. ENGINE-GRAPH CROSS-VALIDATION -- derives the ordered engine_no sequence
     each route's expected_path implies, turns each consecutive pair into an
     engine-to-engine edge, and cross-checks it against
     20_ENGINES_10_GATEWAYS_PHASE_PLAN_2026-07-24.yaml's own dependency_table
     (parsed for "Engine Name (N)"-shaped from/to entries). Flags both
     directions honestly: a route-implied edge absent from that table, and a
     table edge no populated_route's expected_path actually exercises.
  3. Writes real evidence per route to
     ai-os/testing_engine_evidence/phase4/<route_id>/dependency_validation.json
     plus one combined ai-os/testing_engine_evidence/phase4/dependency_graph_cross_validation.json,
     then updates that route's dependency_validation_status field in
     ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml in place via targeted text surgery
     (same regex-scoped-block discipline as generate_route_tests.py's
     update_route_registry_field / generate_route_replays.py's
     update_replay_status -- every other route's formatting/comments
     untouched).

Run: python3 ai-os-scripts/validate_dependency_graph.py [route_id ...]
  (no args = run against every populated_route in the registry)
Exits non-zero if any route's hops produced a real validated_mismatch.
"""
import json
import os
import re
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_route_tests as grt  # noqa: E402 -- reuse Phase 1's derivation, not duplicate

VERIDIAN_ROOT = "/opt/veridian"
COMPLIANCE_TRACKER_ROOT = f"{VERIDIAN_ROOT}/repos/compliance-tracker"
GUARDRAIL_REGISTRATIONS_PATH = f"{COMPLIANCE_TRACKER_ROOT}/src/lib/guardrail-registrations.ts"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUTE_SCHEMA_PATH = f"{REPO_ROOT}/ai-os/ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml"
ENGINES_GATEWAYS_PLAN_PATH = f"{REPO_ROOT}/ai-os/20_ENGINES_10_GATEWAYS_PHASE_PLAN_2026-07-24.yaml"
EVIDENCE_DIR = f"{REPO_ROOT}/ai-os/testing_engine_evidence/phase4"


# ----------------------------------------------------------------------------
# 1a. Rule Engine hop validation -- real registerGuardrail() call-site parser.
# ----------------------------------------------------------------------------
def resolve_registered_guardrail_leaves():
    """Returns the real set of capability_name leaves guardrail-registrations.ts
    actually calls registerGuardrail() with today, resolving the file's own
    const-alias (`export const X_LEAF = "..."`) and array-of-leaves
    (`export const X_LEAVES = [...]`, iterated via `for (const leaf of X_LEAVES)
    registerGuardrail(leaf, ...)`) indirection -- never a literal string match
    against the file, since most real leaves are registered through one of
    those two indirections, not a bare string in the registerGuardrail(...) call."""
    with open(GUARDRAIL_REGISTRATIONS_PATH) as f:
        text = f.read()

    scalar_const_re = re.compile(r'^export const (\w+)\s*=\s*"([^"]+)"\s*$', re.M)
    const_map = dict(scalar_const_re.findall(text))

    array_const_re = re.compile(r'^export const (\w+)\s*=\s*\[(.*?)\]\s*$', re.M | re.S)
    array_map = {}
    for name, body in array_const_re.findall(text):
        array_map[name] = re.findall(r'"([^"]+)"', body)

    registered = set()
    for_loop_re = re.compile(r'for\s*\(\s*const\s+(\w+)\s+of\s+(\w+)\s*\)\s*registerGuardrail\(\s*\1\s*,')
    direct_call_re = re.compile(r'registerGuardrail\(\s*([A-Za-z0-9_"]+)\s*,')

    for line in text.splitlines():
        loop_match = for_loop_re.search(line)
        if loop_match:
            array_name = loop_match.group(2)
            registered.update(array_map.get(array_name, []))
            continue
        call_match = direct_call_re.search(line)
        if call_match:
            arg = call_match.group(1)
            if arg.startswith('"'):
                registered.add(arg.strip('"'))
            elif arg in const_map:
                registered.add(const_map[arg])
            # else: an identifier this parser can't resolve (e.g. a loop
            # variable outside the for-loop pattern above) -- not silently
            # counted as registered.
    return registered


# ----------------------------------------------------------------------------
# 1b. Per-hop validation dispatcher.
# ----------------------------------------------------------------------------
def validate_hop(capability_name, hop, registered_leaves):
    """Returns (found: bool, evidence: str) for whether this hop's real call
    site exists today, independent of what live_or_planned claims."""
    hop_name = hop.get("hop_name")
    mechanism_path = hop.get("mechanism_path")

    if hop_name == "Workflow Engine":
        target, reason, _extra = grt.derive_dispatch_target(capability_name)
        if target is None:
            return False, reason
        import_path, function_name = target
        return True, f'real dispatchEngine() switch case "{capability_name}" -> {import_path}::{function_name}()'

    if hop_name == "Rule Engine":
        if capability_name in registered_leaves:
            return True, f'real registerGuardrail() registration found for leaf "{capability_name}" in {os.path.relpath(GUARDRAIL_REGISTRATIONS_PATH, VERIDIAN_ROOT)}'
        return False, f'no registerGuardrail() call site (direct or via a resolved leaves-array for-loop) registers leaf "{capability_name}" in {os.path.relpath(GUARDRAIL_REGISTRATIONS_PATH, VERIDIAN_ROOT)}'

    # Structural hop (UI Composition Engine, Capability Registry Engine,
    # Automation Engine, etc.) -- real file/dir-exists check on mechanism_path.
    real_path = os.path.join(VERIDIAN_ROOT, mechanism_path)
    if os.path.exists(real_path):
        return True, f'mechanism_path exists on disk: {mechanism_path}'
    return False, f'mechanism_path does NOT exist on disk: {mechanism_path}'


def validate_route_hops(route, registered_leaves):
    capability_name = route["capability_name"]
    hop_results = []
    route_ok = True
    for hop in route["expected_path"]:
        found, evidence = validate_hop(capability_name, hop, registered_leaves)
        claimed_live = hop["live_or_planned"] == "live"
        verdict = "match" if found == claimed_live else "mismatch"
        if verdict == "mismatch":
            route_ok = False
        hop_results.append({
            "hop_no": hop["hop_no"],
            "hop_name": hop["hop_name"],
            "mechanism_path": hop["mechanism_path"],
            "live_or_planned_claim": hop["live_or_planned"],
            "found_live_today": found,
            "verdict": verdict,
            "evidence": evidence,
        })
    return route_ok, hop_results


# ----------------------------------------------------------------------------
# 2. Engine-to-engine cross-validation against 20_ENGINES_10_GATEWAYS_PHASE_PLAN's
#    dependency_table.
# ----------------------------------------------------------------------------
def load_documented_engine_edges():
    """Parses 20_ENGINES_10_GATEWAYS_PHASE_PLAN_2026-07-24.yaml's dependency_table
    for from/to entries shaped "<Engine Name> (<engine_no>)" -- entries that
    reference an external plan file instead of a named+numbered engine (e.g.
    the Audit/Observability Engine -> all engines external dependency) are
    real rows but not resolvable to a single numeric edge, so they are kept
    separately rather than silently dropped or mis-parsed."""
    with open(ENGINES_GATEWAYS_PLAN_PATH) as f:
        doc = yaml.safe_load(f)

    edge_re = re.compile(r'\((\d+)\)\s*$')
    documented_edges = {}  # (from_no, to_no) -> table row
    unresolvable_rows = []
    for row in doc.get("dependency_table", []):
        from_match = edge_re.search(str(row.get("from", "")))
        to_match = edge_re.search(str(row.get("to", "")))
        if from_match and to_match:
            documented_edges[(int(from_match.group(1)), int(to_match.group(1)))] = row
        else:
            unresolvable_rows.append(row)
    return documented_edges, unresolvable_rows


def route_implied_edges(route):
    """Consecutive (engine_no, engine_no) pairs implied by a route's ordered
    expected_path hops -- the real call-flow direction (hop i calls hop i+1),
    skipping any hop with no engine_no (a gateway hop, none exist yet per
    ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml's own honest_limitation)."""
    engine_nos = [h["engine_no"] for h in route["expected_path"] if h.get("engine_no") is not None]
    edges = []
    for a, b in zip(engine_nos, engine_nos[1:]):
        if a != b:
            edges.append((a, b))
    return edges


def cross_validate_engine_graph(routes):
    documented_edges, unresolvable_rows = load_documented_engine_edges()

    all_route_edges = {}  # (from_no, to_no) -> [route_id, ...]
    for route in routes:
        for edge in route_implied_edges(route):
            all_route_edges.setdefault(edge, []).append(route["route_id"])

    undocumented_route_edges = [
        {"edge": list(edge), "route_ids": route_ids}
        for edge, route_ids in sorted(all_route_edges.items())
        if edge not in documented_edges
    ]
    unexercised_table_edges = [
        {"edge": list(edge), "from": row["from"], "to": row["to"], "mechanism": row["mechanism"], "status": row["status"]}
        for edge, row in sorted(documented_edges.items())
        if edge not in all_route_edges
    ]

    return {
        "route_implied_edges": {f"{a}->{b}": route_ids for (a, b), route_ids in sorted(all_route_edges.items())},
        "documented_table_edges": {f"{a}->{b}": row["mechanism"] for (a, b), row in sorted(documented_edges.items())},
        "unresolvable_table_rows": unresolvable_rows,
        "undocumented_route_edges": undocumented_route_edges,
        "unexercised_table_edges": unexercised_table_edges,
    }


# ----------------------------------------------------------------------------
# 3. Evidence + registry-field update.
# ----------------------------------------------------------------------------
def save_route_evidence(route_id, report):
    out_dir = os.path.join(EVIDENCE_DIR, route_id)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "dependency_validation.json"), "w") as f:
        json.dump(report, f, indent=2)


def save_cross_validation_evidence(report):
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    with open(os.path.join(EVIDENCE_DIR, "dependency_graph_cross_validation.json"), "w") as f:
        json.dump(report, f, indent=2)


def update_dependency_validation_status(route_id, status):
    with open(ROUTE_SCHEMA_PATH) as f:
        text = f.read()
    block_re = re.compile(
        rf'(- route_id: {re.escape(route_id)}\n(?:.*\n)*?)(    dependency_validation_status: )(\S+)(\n)', re.M
    )
    text, n = block_re.subn(rf'\g<1>\g<2>{status}\g<4>', text, count=1)
    if n != 1:
        raise RuntimeError(f"could not locate dependency_validation_status field for {route_id} (matched {n} times)")
    with open(ROUTE_SCHEMA_PATH, "w") as f:
        f.write(text)


def main():
    with open(ROUTE_SCHEMA_PATH) as f:
        doc = yaml.safe_load(f)
    all_routes = doc.get("populated_routes", [])

    requested = sys.argv[1:]
    routes = [r for r in all_routes if r["route_id"] in requested] if requested else all_routes

    registered_leaves = resolve_registered_guardrail_leaves()
    print(f"Resolved {len(registered_leaves)} real registered guardrail leaves: {sorted(registered_leaves)}\n")

    all_ok = True
    for route in routes:
        route_id = route["route_id"]
        print(f"=== {route_id} ({route['capability_name']}) ===")
        route_ok, hop_results = validate_route_hops(route, registered_leaves)
        for hop in hop_results:
            marker = "OK  " if hop["verdict"] == "match" else "MISMATCH"
            print(f"  hop {hop['hop_no']} [{hop['hop_name']}] claim={hop['live_or_planned_claim']} found={hop['found_live_today']} -> {marker}  {hop['evidence']}")

        status = "validated_match" if route_ok else "validated_mismatch"
        report = {"route_id": route_id, "capability_name": route["capability_name"], "hop_results": hop_results, "dependency_validation_status": status}
        save_route_evidence(route_id, report)
        update_dependency_validation_status(route_id, status)
        print(f"RESULT   dependency_validation_status={status}\n")
        if not route_ok:
            all_ok = False

    # Engine-graph cross-validation runs over ALL populated_routes regardless
    # of a route_id filter above, since it is a whole-graph check, not a
    # per-route one.
    print("=== engine-to-engine cross-validation vs 20_ENGINES_10_GATEWAYS_PHASE_PLAN dependency_table ===")
    cross_report = cross_validate_engine_graph(all_routes)
    print(json.dumps(cross_report, indent=2))
    save_cross_validation_evidence(cross_report)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
