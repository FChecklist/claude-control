#!/usr/bin/env python3
"""
generate_route_tests.py -- Phase 1 of VERIDIAN TESTING ENGINE / IRVF
(TESTING_ENGINE_PHASE_PLAN_2026-07-24.yaml phase_1_route_test_autogeneration).

Owner directive: "all registry/catalog data must be produced by scripts, not
hand-authored AI prose." This script is the real, runnable route-test
generator for ai-os/ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml's populated_routes.

WHAT IT DOES (per route_id):
  1. Statically derives the real (module, function) the route's capability_name
     actually dispatches to, by grepping compliance-tracker's real
     task-execution-engine.ts dispatchEngine() switch for a matching
     `case "<capability_name>":` block and brace-matching it out, then
     regexing that block's own `await import("...")` + destructure for the
     function it really calls. This is the same "walk the real call chain,
     never invent it" discipline generate_route_registry_candidates.py used
     for the route registry itself (see this file's REGISTERED_FIXTURES for
     the one piece that cannot be auto-derived: representative domain
     inputs/expected outputs, curated from each capability's own registered
     `inputs` schema in CAPABILITY_REGISTRY_SCHEMA_2026-07-24.yaml and the
     destination engine's own documented formula).
  2. If no matching dispatch case exists (e.g. capability_registry_dedup,
     whose capability_record_schema.workflow is null), the route is honestly
     marked test_status=quarantined with the concrete grep evidence for why
     -- never a fabricated pass.
  3. For a route with a real dispatch target, generates a real bun:test file,
     runs it for real via `bunx bun test` against compliance-tracker's actual
     checkout (real module resolution, real tsconfig `@/` alias, real
     decimal.js, no mocks), and captures the real exit code + stdout/stderr.
  4. Writes the generated test source + raw run output to
     ai-os/testing_engine_evidence/phase1/<route_id>/ as committed evidence,
     then deletes the transient copy from compliance-tracker's own working
     tree (that repo is a separate, live product repo this task does not
     have a PR open against -- see EXPECTED_OUTPUT scoping to claude-control
     only. Running the real test against its real code is not the same as
     checking new files into it).
  5. Updates that route's test_status (and notes) field in
     ai-os/ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml in place via targeted text
     surgery (regex-scoped to the one route's block) so every other route's
     existing formatting/comments are left untouched -- yaml.safe_dump would
     blow away this file's extensive inline comments.

SCOPE NOTE (honest, not a shortcut): full Playwright browser E2E per this
phase's original scope text needs a running authenticated Next.js server --
confirmed not to exist yet by compliance-tracker's own playwright.config.ts
comment ("zero E2E tests exist yet ... separate, larger scope", testDir
`./e2e` is empty). This script instead exercises each route's real
destination-engine function exactly as task-execution-engine.ts's real
dispatchEngine() switch invokes it -- the deepest layer of the real
source->destination path that is honestly testable without a live server,
auth fixtures, or a seeded database. See TESTING_ENGINE_PHASE_PLAN_2026-07-24.yaml
phase_1's own external_depends_on for why the originally-scoped on-create
auto-generation trigger itself is still blocked on a live Capability
Registry table that does not exist yet.

Run: python3 ai-os-scripts/generate_route_tests.py [route_id ...]
  (no args = run against every populated_route in the registry)
Exits non-zero if any executed test fails for a real (non-blocked) reason.
"""
import os
import re
import subprocess
import sys
import yaml

VERIDIAN_ROOT = "/opt/veridian"
COMPLIANCE_TRACKER_ROOT = f"{VERIDIAN_ROOT}/repos/compliance-tracker"
TASK_EXEC_ENGINE_PATH = f"{COMPLIANCE_TRACKER_ROOT}/src/lib/task-execution-engine.ts"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUTE_SCHEMA_PATH = f"{REPO_ROOT}/ai-os/ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml"
EVIDENCE_DIR = f"{REPO_ROOT}/ai-os/testing_engine_evidence/phase1"

GENERATED_SUBDIR = "src/lib/engines/__generated_route_tests__"

# ----------------------------------------------------------------------------
# The one piece of this generator that is curated, not auto-derived: a real
# representative input set per capability, and the real expected output --
# computed by hand against the destination engine's own documented formula
# (its file header comment cites the exact statute/convention), the same way
# a human test author would. Everything else (which module, which function,
# whether a route even has a live dispatch target) is derived live below.
# ----------------------------------------------------------------------------
REGISTERED_FIXTURES = {
    "gratuity_calculator": {
        "call_args": '{ lastDrawnMonthlySalary: 50000, yearsOfService: 10, isCoveredUnderAct: true }',
        "assertions": [
            # Payment of Gratuity Act 1972, covered (15/26 formula), Sec 4(2)
            # rounding: 10.0 years rounds to 10; 50000 * 15 / 26 * 10 = 288461.538...
            'expect(result.gratuityAmount).toBe(288461.54)',
            'expect(result.roundedYearsOfService).toBe(10)',
            'expect(result.statutoryCapApplied).toBe(false)',
        ],
    },
    "commission_calculator": {
        "call_args": '100000, 5',
        "assertions": [
            # calculatePayrollCommission(saleAmount, commissionRatePercent) = saleAmount * rate / 100
            'expect(result).toBe(5000)',
        ],
    },
    "gst_calculation_engine": {
        "call_args": '{ taxableAmount: 10000, gstRatePercent: 18, supplierStateCode: "27", buyerStateCode: "29" }',
        "assertions": [
            # Inter-state (27 != 29) -> IGST only, no CGST/SGST split.
            'expect(result.isInterState).toBe(true)',
            'expect(result.igst).toBe(1800)',
            'expect(result.cgst).toBe(0)',
            'expect(result.sgst).toBe(0)',
            'expect(result.totalAmount).toBe(11800)',
        ],
    },
    "trend_analysis_engine": {
        "call_args": '[1, 2, 3, 4, 5]',
        "assertions": [
            'expect(result.value.direction).toBe("increasing")',
            'expect(result.explanation).toContain("upward")',
        ],
    },
}


def extract_case_block(source, capability_name):
    """Brace-match the real `case "<capability_name>": { ... }` block out of
    task-execution-engine.ts's dispatchEngine() switch. Returns the block
    text, or None if no such case exists (a real, checkable absence)."""
    marker = f'case "{capability_name}":'
    idx = source.find(marker)
    if idx == -1:
        return None
    brace_start = source.find("{", idx)
    if brace_start == -1:
        return None
    depth = 0
    for i in range(brace_start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[brace_start:i + 1]
    return None


def derive_dispatch_target(capability_name):
    """Returns (import_path, function_name, real_source_file) for the real
    function task-execution-engine.ts's dispatchEngine() switch calls for
    this capability_name, or (None, None, reason) if no live dispatch case
    exists for it."""
    with open(TASK_EXEC_ENGINE_PATH) as f:
        source = f.read()

    block = extract_case_block(source, capability_name)
    if block is None:
        reason = (
            f'grep of {os.path.relpath(TASK_EXEC_ENGINE_PATH, VERIDIAN_ROOT)}\'s dispatchEngine() switch found no '
            f'case "{capability_name}": -- no live Workflow Engine dispatch target for this capability today.'
        )
        return None, reason, None

    import_match = re.search(r'\{\s*([a-zA-Z0-9_]+)(?:\s*,\s*[a-zA-Z0-9_]+)*\s*\}\s*=\s*await import\("([^"]+)"\)', block)
    if not import_match:
        reason = f'case "{capability_name}" block found but no single-function `await import(...)` pattern could be extracted from it (block: {block[:200]!r}).'
        return None, reason, None

    function_name = import_match.group(1)
    import_path = import_match.group(2)  # e.g. "@/lib/engines/payroll-engine"
    real_source_file = os.path.join(COMPLIANCE_TRACKER_ROOT, import_path.replace("@/", "src/") + ".ts")
    return (import_path, function_name), None, real_source_file if os.path.exists(real_source_file) else None


def generate_test_source(route_id, capability_name, import_path, function_name):
    fixture = REGISTERED_FIXTURES[capability_name]
    assertions = "\n  ".join(fixture["assertions"])
    return f"""// AUTO-GENERATED by ai-os-scripts/generate_route_tests.py -- Phase 1 route
// test auto-generation, route_id={route_id}, capability_name={capability_name}.
// Real call target derived by grepping task-execution-engine.ts's live
// dispatchEngine() switch; call_args/assertions are the one curated fixture
// (REGISTERED_FIXTURES) for this capability, computed against the engine's
// own documented formula. Do not hand-edit -- regenerate via the script.
import {{ describe, expect, test }} from "bun:test"
import {{ {function_name} }} from "{import_path}"

describe("route test: {route_id} ({capability_name})", () => {{
  test("real dispatch target {function_name}() executes and matches the documented formula", () => {{
    const result = {function_name}({fixture['call_args']})
    {assertions}
  }})
}})
"""


def run_generated_test(route_id, test_source):
    gen_dir = os.path.join(COMPLIANCE_TRACKER_ROOT, GENERATED_SUBDIR)
    os.makedirs(gen_dir, exist_ok=True)
    test_path = os.path.join(gen_dir, f"{route_id}.test.ts")
    rel_test_path = os.path.join(GENERATED_SUBDIR, f"{route_id}.test.ts")
    with open(test_path, "w") as f:
        f.write(test_source)
    try:
        proc = subprocess.run(
            ["bunx", "bun", "test", rel_test_path],
            cwd=COMPLIANCE_TRACKER_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return proc.returncode, proc.stdout + proc.stderr
    finally:
        os.remove(test_path)
        try:
            os.rmdir(gen_dir)
        except OSError:
            pass  # other route tests still running/left artifacts this invocation


def save_evidence(route_id, test_source, run_output, blocked_reason=None):
    out_dir = os.path.join(EVIDENCE_DIR, route_id)
    os.makedirs(out_dir, exist_ok=True)
    if blocked_reason:
        with open(os.path.join(out_dir, "blocked_reason.txt"), "w") as f:
            f.write(blocked_reason + "\n")
    else:
        with open(os.path.join(out_dir, "test_source.test.ts"), "w") as f:
            f.write(test_source)
        with open(os.path.join(out_dir, "run_output.txt"), "w") as f:
            f.write(run_output)


def update_route_registry_field(route_id, test_status, notes):
    with open(ROUTE_SCHEMA_PATH) as f:
        text = f.read()

    block_re = re.compile(
        rf'(- route_id: {re.escape(route_id)}\n(?:.*\n)*?)(    test_status: )(\S+)(\n)', re.M
    )
    text, n = block_re.subn(rf'\g<1>\g<2>{test_status}\g<4>', text, count=1)
    if n != 1:
        raise RuntimeError(f"could not locate test_status field for {route_id} (matched {n} times)")

    notes_re = re.compile(
        rf'(- route_id: {re.escape(route_id)}\n(?:.*\n)*?    notes: )(.*(?:\n(?!  - route_id:|\nregistration:).*)*)',
        re.M,
    )
    escaped_notes = notes.replace('"', '\\"')
    new_notes_block = f'"{escaped_notes}"'

    def notes_replacer(m):
        return m.group(1) + new_notes_block

    text, n2 = notes_re.subn(notes_replacer, text, count=1)
    if n2 != 1:
        raise RuntimeError(f"could not locate notes field for {route_id} (matched {n2} times)")

    with open(ROUTE_SCHEMA_PATH, "w") as f:
        f.write(text)


def main():
    with open(ROUTE_SCHEMA_PATH) as f:
        doc = yaml.safe_load(f)
    routes = doc.get("populated_routes", [])

    requested = sys.argv[1:]
    if requested:
        routes = [r for r in routes if r["route_id"] in requested]

    all_ok = True
    for route in routes:
        route_id = route["route_id"]
        capability_name = route["capability_name"]
        print(f"\n=== {route_id} ({capability_name}) ===")

        target, no_dispatch_reason, extra = derive_dispatch_target(capability_name)

        if target is None:
            print(f"BLOCKED  {no_dispatch_reason}")
            update_route_registry_field(route_id, "quarantined", no_dispatch_reason)
            save_evidence(route_id, None, None, blocked_reason=no_dispatch_reason)
            continue

        import_path, function_name = target
        if capability_name not in REGISTERED_FIXTURES:
            reason = (
                f'Real dispatch target found ({import_path}::{function_name}) but no curated input/expected-output '
                f'fixture is registered for capability "{capability_name}" in REGISTERED_FIXTURES yet -- generating '
                f'a call with unverified arguments would not be a real correctness test.'
            )
            print(f"BLOCKED  {reason}")
            update_route_registry_field(route_id, "quarantined", reason)
            save_evidence(route_id, None, None, blocked_reason=reason)
            all_ok = False
            continue

        print(f"DERIVED  dispatch target: {import_path}::{function_name}()")
        test_source = generate_test_source(route_id, capability_name, import_path, function_name)
        returncode, output = run_generated_test(route_id, test_source)
        print(output)

        status = "passing" if returncode == 0 else "failing"
        note = (
            f'Phase 1 route-test auto-generation: real dispatch target {import_path}::{function_name}() '
            f'(dispatchEngine() switch case "{capability_name}" in task-execution-engine.ts), executed via '
            f'`bunx bun test` against compliance-tracker\'s real checkout, exit_code={returncode}. '
            f'Evidence: ai-os/testing_engine_evidence/phase1/{route_id}/.'
        )
        save_evidence(route_id, test_source, output)
        update_route_registry_field(route_id, status, note)
        print(f"RESULT   test_status={status}")
        if returncode != 0:
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
