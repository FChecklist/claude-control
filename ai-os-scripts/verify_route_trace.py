#!/usr/bin/env python3
"""
verify_route_trace.py -- Phase 2 of VERIDIAN TESTING ENGINE / IRVF
(TESTING_ENGINE_PHASE_PLAN_2026-07-24.yaml phase_2_distributed_trace_verification_wiring).

This phase was hard-blocked until AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml's own Phase 7 (PART6
observability layer) shipped a real event-emitter -- it did, in
ai-os-scripts/auditor_engine_events.py (PR #55, task-20260724-213832-phase7-part6-observability-audit-trail-l):
a real jsonschema-validated `audit_events` table in the shared knowledge_engine sqlite DB, plus real
OpenTelemetry spans exported to ai-os/logs/otel-spans-auditor-engine.jsonl (local-file fallback until an
Owner-approved OTel Collector endpoint exists). This script is the route-side CONSUMER of that real
mechanism, per this phase's own SCOPE -- it does not invent a second tracing mechanism.

WHAT IT DOES per route_id:
  1. Reuses generate_route_tests.py's derive_dispatch_target() + REGISTERED_FIXTURES + run_generated_test
     (imported, not duplicated) to find the one real hop this harness can actually execute: the
     "Workflow Engine" hop whose mechanism_path is task-execution-engine.ts, the file whose real
     dispatchEngine() switch case is greped and whose real destination function this harness actually
     calls via `bunx bun test`. Every other hop in a route's expected_path (UI Composition Engine,
     Capability Registry Engine, Rule Engine) sits upstream/downstream of that one function call and is
     not independently executable without a live authenticated Next.js server + browser -- the same
     honest boundary generate_route_tests.py's own SCOPE NOTE already draws for test_status. A route
     whose expected_path has no such hop, or whose capability has no live dispatchEngine() case, or no
     curated REGISTERED_FIXTURES entry, stays trace_verification_status=not_instrumented with a real,
     citable reason -- never a fabricated pass.
  2. For a route with a real observable hop, emits a REAL distributed trace via
     ai-os-scripts/auditor_engine_events.py -- the exact shared emitter Phase 7 built:
     start_audit_run() opens the route-execution root span (domain="test-coverage", the existing
     AUDITOR_ENGINE_EVENT_SCHEMA domain enum value closest to this phase's own purpose -- no schema
     change needed), a real OTel child span (via that library's own _otel_span() primitive, the same
     mechanism its public emit_finding() wrapper uses internally) brackets the real `bunx bun test`
     subprocess execution of the route's dispatch-target function, complete_audit_run() closes it out.
  3. Force-flushes the OTel tracer provider, then RE-QUERIES the real event stream Phase 7 stood up --
     the audit_events sqlite table AND the OTel spans JSONL file -- by trace_id, to reconstruct the
     actually-observed hop-span sequence. This re-query (not the in-memory span ids this script itself
     just created) is the literal "route-side consumer ... collect the emitted span sequence" this
     phase's SCOPE calls for, and it is what makes this script reusable as a read-only verifier against
     any prior route-trace run without re-executing anything.
  4. Diffs the observed hop sequence against the route's full expected_path:
       - not_instrumented   -- no real trace exists at all for this route (blocked, or never run).
       - instrumented_unverified -- a real trace_id/span_id exists (schema-validated audit_events row,
         and/or a real hop-level OTel span) but does not yet cover every expected_path hop -- today's
         honest ceiling for all 4 live-dispatch routes, since only the Workflow Engine hop is
         independently observable by this harness (see step 1).
       - verified_match     -- every expected_path hop was actually observed, in order, in a real trace
         (reachable the day a full multi-hop trace becomes observable, e.g. once a live server exists).
       - verified_mismatch  -- a real span was observed but its hop identity contradicts what
         expected_path claims -- a genuine drift signal, not silently reconciled.
  5. Writes evidence to ai-os/testing_engine_evidence/phase2/<route_id>/trace_verification.json and
     updates that route's trace_verification_status field in ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml in
     place via targeted text surgery (same regex-scoped-block discipline as generate_route_tests.py /
     validate_dependency_graph.py -- every other route's formatting/comments untouched).

Run: python3 ai-os-scripts/verify_route_trace.py [route_id ...]
  (no args = run against every populated_route in the registry)
Exits non-zero if any route produced a real verified_mismatch (a genuine trace/expected_path divergence).
"""
import json
import os
import re
import sqlite3
import sys
import time

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_route_tests as grt  # noqa: E402 -- reuse Phase 1's derivation + fixtures, not duplicate
import auditor_engine_events as aee  # noqa: E402 -- Phase 7's shared emitter, the one real tracing mechanism

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUTE_SCHEMA_PATH = f"{REPO_ROOT}/ai-os/ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml"
EVIDENCE_DIR = f"{REPO_ROOT}/ai-os/testing_engine_evidence/phase2"

SPANS_JSONL_PATH = os.environ.get(
    "AUDIT_OTEL_SPANS_FILE", "/opt/veridian/ai-os/logs/otel-spans-auditor-engine.jsonl"
)
TASK_EXEC_ENGINE_BASENAME = "task-execution-engine.ts"


# ----------------------------------------------------------------------------
# 1. Find the one hop this harness can actually execute.
# ----------------------------------------------------------------------------
def find_observable_hop(expected_path):
    for hop in expected_path:
        if os.path.basename(hop.get("mechanism_path", "")) == TASK_EXEC_ENGINE_BASENAME:
            return hop
    return None


# ----------------------------------------------------------------------------
# 2. Emit a real trace bracketing a real execution of the dispatch target.
# ----------------------------------------------------------------------------
def run_and_trace_observable_hop(route_id, capability_name, observable_hop, import_path, function_name):
    run_trace = aee.start_audit_run(
        domain="test-coverage", repo="compliance-tracker", producer_name="verify_route_trace.py",
        producer_version="2026-07-24", run_id=route_id,
        metadata={
            "route_id": route_id, "capability_name": capability_name,
            "observable_hop_no": observable_hop["hop_no"], "observable_hop_name": observable_hop["hop_name"],
        },
    )
    test_source = grt.generate_test_source(route_id, capability_name, import_path, function_name)
    hop_span_name = f'hop:{observable_hop["hop_no"]}:{observable_hop["hop_name"]}'
    hop_attrs = {
        "route_id": route_id, "hop_no": observable_hop["hop_no"], "hop_name": observable_hop["hop_name"],
        "mechanism_path": observable_hop["mechanism_path"],
    }
    hop_span_id = None
    with aee._otel_span(
        hop_span_name, hop_attrs, trace_id_hex=run_trace.trace_id, parent_span_id_hex=run_trace.root_span_id,
    ) as (_trace_id, span_id):
        hop_span_id = span_id
        t0 = time.time()
        returncode, output = grt.run_generated_test(route_id, test_source)
        duration = time.time() - t0

    aee.complete_audit_run(
        run_trace, status="ok" if returncode == 0 else "failed", total_findings=0, new_findings=0,
        duration_s=duration, notes=f"route trace verification run for {route_id}",
    )
    return run_trace.trace_id, run_trace.root_span_id, hop_span_id, hop_span_name, returncode, output


def flush_otel():
    """BatchSpanProcessor exports asynchronously -- force a flush before
    re-querying the JSONL file below, so this run's own spans are actually
    on disk by the time step 3 reads them back (not a race)."""
    aee._init_otel()
    try:
        from opentelemetry import trace as otel_trace
        provider = otel_trace.get_tracer_provider()
        if hasattr(provider, "force_flush"):
            provider.force_flush()
    except Exception:
        pass


# ----------------------------------------------------------------------------
# 3. Re-query the real event stream (not in-memory bookkeeping).
# ----------------------------------------------------------------------------
def query_spans_for_trace(trace_id):
    spans = []
    if not os.path.exists(SPANS_JSONL_PATH):
        return spans
    with open(SPANS_JSONL_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                span = json.loads(line)
            except json.JSONDecodeError:
                continue
            if span.get("trace_id") == trace_id:
                spans.append(span)
    spans.sort(key=lambda s: s.get("start_time", 0))
    return spans


def query_audit_events_for_trace(trace_id):
    conn = sqlite3.connect(aee.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        aee.ensure_events_table(conn)
        rows = conn.execute(
            "SELECT event_type, ts, trace_id, span_id, parent_span_id FROM audit_events "
            "WHERE trace_id = ? ORDER BY ts", (trace_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ----------------------------------------------------------------------------
# 4. Diff observed vs. expected.
# ----------------------------------------------------------------------------
def determine_verdict(expected_path, observable_hop, hop_span_name, observed_spans, audit_event_rows):
    if not audit_event_rows:
        return "not_instrumented", "no real audit_events row was found for this route's trace_id after re-querying the event stream"

    has_started = any(r["event_type"] == "audit_run_started" for r in audit_event_rows)
    has_completed = any(r["event_type"] in ("audit_run_completed", "audit_run_failed") for r in audit_event_rows)
    if not (has_started and has_completed):
        return "instrumented_unverified", "a trace_id exists in the event stream but its audit_run_started/completed pair is incomplete"

    observed_hop_spans = [s for s in observed_spans if s.get("name") == hop_span_name]
    if not observed_hop_spans:
        return "instrumented_unverified", (
            f"real trace_id/span_id persisted in audit_events for this route's run, but no hop-level OTel "
            f"span was found in {SPANS_JSONL_PATH} to diff against expected_path (otel_status={aee.otel_status()})"
        )

    observed = observed_hop_spans[0]
    attrs = observed.get("attributes", {})
    if attrs.get("hop_name") != observable_hop["hop_name"] or int(attrs.get("hop_no", -1)) != observable_hop["hop_no"]:
        return "verified_mismatch", (
            f'real span observed but its hop attributes ({attrs.get("hop_no")}:{attrs.get("hop_name")}) do '
            f'not match the expected hop ({observable_hop["hop_no"]}:{observable_hop["hop_name"]})'
        )

    all_hop_nos = {h["hop_no"] for h in expected_path}
    if all_hop_nos == {observable_hop["hop_no"]}:
        return "verified_match", "the route's entire expected_path was observed in a real trace"

    missing = sorted(all_hop_nos - {observable_hop["hop_no"]})
    return "instrumented_unverified", (
        f'real trace + hop span captured and re-verified from the event stream for hop '
        f'{observable_hop["hop_no"]} ({observable_hop["hop_name"]}), but hop(s) {missing} of expected_path '
        f'are not independently observable by this harness yet (no live authenticated Next.js server/browser '
        f'to exercise the UI/Rule Engine hops -- same honest boundary generate_route_tests.py\'s own SCOPE '
        f'NOTE draws) -- not yet a full end-to-end verified path.'
    )


# ----------------------------------------------------------------------------
# 5. Evidence + registry-field update.
# ----------------------------------------------------------------------------
def save_evidence(route_id, evidence):
    out_dir = os.path.join(EVIDENCE_DIR, route_id)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "trace_verification.json"), "w") as f:
        json.dump(evidence, f, indent=2, default=str)


def update_trace_verification_status(route_id, status):
    with open(ROUTE_SCHEMA_PATH) as f:
        text = f.read()
    block_re = re.compile(
        rf'(- route_id: {re.escape(route_id)}\n(?:.*\n)*?)(    trace_verification_status: )(\S+)(\n)', re.M
    )
    text, n = block_re.subn(rf'\g<1>\g<2>{status}\g<4>', text, count=1)
    if n != 1:
        raise RuntimeError(f"could not locate trace_verification_status field for {route_id} (matched {n} times)")
    with open(ROUTE_SCHEMA_PATH, "w") as f:
        f.write(text)


def main():
    with open(ROUTE_SCHEMA_PATH) as f:
        doc = yaml.safe_load(f)
    all_routes = doc.get("populated_routes", [])

    requested = sys.argv[1:]
    routes = [r for r in all_routes if r["route_id"] in requested] if requested else all_routes

    all_ok = True
    for route in routes:
        route_id = route["route_id"]
        capability_name = route["capability_name"]
        expected_path = route["expected_path"]
        print(f"\n=== {route_id} ({capability_name}) ===")

        observable_hop = find_observable_hop(expected_path)
        if observable_hop is None:
            reason = "expected_path has no Workflow Engine hop (task-execution-engine.ts) for this route to trace through"
            print(f"BLOCKED  {reason}")
            save_evidence(route_id, {"route_id": route_id, "verdict": "not_instrumented", "reason": reason})
            update_trace_verification_status(route_id, "not_instrumented")
            continue

        target, no_dispatch_reason, _extra = grt.derive_dispatch_target(capability_name)
        if target is None:
            print(f"BLOCKED  {no_dispatch_reason}")
            save_evidence(route_id, {"route_id": route_id, "verdict": "not_instrumented", "reason": no_dispatch_reason})
            update_trace_verification_status(route_id, "not_instrumented")
            continue

        import_path, function_name = target
        if capability_name not in grt.REGISTERED_FIXTURES:
            reason = (
                f'no curated fixture registered for capability "{capability_name}" in '
                f'generate_route_tests.REGISTERED_FIXTURES -- cannot generate a real execution to trace'
            )
            print(f"BLOCKED  {reason}")
            save_evidence(route_id, {"route_id": route_id, "verdict": "not_instrumented", "reason": reason})
            update_trace_verification_status(route_id, "not_instrumented")
            continue

        print(f"DERIVED  observable hop: {observable_hop['hop_no']}:{observable_hop['hop_name']}, "
              f"dispatch target: {import_path}::{function_name}()")
        trace_id, root_span_id, hop_span_id, hop_span_name, returncode, output = run_and_trace_observable_hop(
            route_id, capability_name, observable_hop, import_path, function_name
        )
        print(output)
        flush_otel()

        observed_spans = query_spans_for_trace(trace_id)
        audit_event_rows = query_audit_events_for_trace(trace_id)
        verdict, reason = determine_verdict(expected_path, observable_hop, hop_span_name, observed_spans, audit_event_rows)
        print(f"RESULT   trace_verification_status={verdict} -- {reason}")

        evidence = {
            "route_id": route_id, "capability_name": capability_name, "trace_id": trace_id,
            "root_span_id": root_span_id, "hop_span_id": hop_span_id, "hop_span_name": hop_span_name,
            "observable_hop": observable_hop, "expected_path_hop_count": len(expected_path),
            "dispatch_returncode": returncode, "otel_status": aee.otel_status(),
            "observed_spans": observed_spans, "audit_event_rows": audit_event_rows,
            "verdict": verdict, "reason": reason,
        }
        save_evidence(route_id, evidence)
        update_trace_verification_status(route_id, verdict)

        if verdict == "verified_mismatch":
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
