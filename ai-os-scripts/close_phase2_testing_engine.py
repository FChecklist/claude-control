#!/usr/bin/env python3
"""
close_phase2_testing_engine.py -- closes out
TESTING_ENGINE_PHASE_PLAN_2026-07-24.yaml's phase_2_distributed_trace_verification_wiring
entry in place, same targeted-text-surgery discipline
ai-os-scripts/close_phase3_testing_engine.py already used for phase_3 (regex-scoped to
the one phase's block, so every other phase's existing formatting/comments are left
untouched -- yaml.safe_dump would blow away this file's extensive inline comments).

Inserts `status:` + `status_detail:` right after phase_2's own `scope:` block (phase_2
currently has neither field). status_detail cites this task's own real task_id so
scripts/auto_phase_continuation.py's extract_produced_task_id() can resolve it via a live
`gh pr list --head worker/<task_id> --state merged` check, exactly like it already does
for Phase 1/3 -- never a self-reported status string alone.

Run: python3 ai-os-scripts/close_phase2_testing_engine.py
"""
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN_PATH = f"{REPO_ROOT}/ai-os/TESTING_ENGINE_PHASE_PLAN_2026-07-24.yaml"

TASK_ID = "task-20260724-230014-phase2-distributed-trace-verification-wi"

STATUS_DETAIL = (
    "DONE (real, scoped) as of " + TASK_ID + ". Unblocked once "
    "AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml's own Phase 7 (PART6 observability layer) shipped a real "
    "event-emitter, ai-os-scripts/auditor_engine_events.py (PR #55, "
    "task-20260724-213832-phase7-part6-observability-audit-trail-l) -- this phase's own hard external "
    "dependency. Delivered: ai-os-scripts/verify_route_trace.py, the real route-side consumer of "
    "AUDITOR_ENGINE_EVENT_SCHEMA_2026-07-24.schema.json's trace object, extending the OTel "
    "collector/event stream Phase 7 stood up rather than inventing a second tracing mechanism (per this "
    "phase's own SCOPE item 2). For each route: (1) finds the one hop this harness can actually execute "
    "(the 'Workflow Engine' hop whose mechanism_path is task-execution-engine.ts, the same real dispatch "
    "target Phase 1's generate_route_tests.derive_dispatch_target() derives -- imported, not duplicated); "
    "(2) emits a REAL distributed trace via Phase 7's shared emitter (start_audit_run/_otel_span/"
    "complete_audit_run, domain=test-coverage) bracketing a real `bunx bun test` execution of that hop's "
    "dispatch-target function; (3) force-flushes the OTel tracer and RE-QUERIES the real event stream -- "
    "the audit_events sqlite table AND the OTel spans JSONL file (ai-os/logs/otel-spans-auditor-engine.jsonl) "
    "-- by trace_id, to reconstruct the actually-observed hop-span sequence (a genuine re-consumption, not "
    "in-memory bookkeeping); (4) diffs the observed sequence against expected_path and writes the verdict "
    "into trace_verification_status. Run for real against all 5 populated_routes: RT-gratuity_calculator-001, "
    "RT-commission_calculator-001, RT-gst_calculation_engine-001, RT-trend_analysis_engine-001 all now "
    "trace_verification_status=instrumented_unverified -- a real trace_id/span_id was captured and "
    "re-verified from the event stream for the one hop independently observable by this harness; "
    "verified_match/verified_mismatch honestly stays out of reach until a live authenticated Next.js "
    "server+browser exists to exercise the UI Composition Engine and Rule Engine hops too, the same "
    "honest test-layer boundary generate_route_tests.py's own SCOPE NOTE already draws for test_status -- "
    "never a fabricated full-path pass. RT-capability_registry_dedup-001 stays honestly "
    "trace_verification_status=not_instrumented: its expected_path has no Workflow Engine hop at all "
    "(same real blocker Phase 1/3 already documented -- no live dispatchEngine() case for this "
    "capability). Evidence: ai-os/testing_engine_evidence/phase2/<route_id>/trace_verification.json per "
    "route (trace_id, span ids, the real re-queried spans/audit_events rows, verdict + reason). "
    "Registered in knowledge_engine: `python3 scripts/superboss-register.py query-knowledge "
    "\"phase_2_distributed_trace_verification_wiring\" --tag domain:veridian-testing-engine-irvf-phased`. "
    "Deferred (honestly, not silently): true multi-hop verified_match/verified_mismatch needs a live "
    "server + real OTel JS SDK instrumentation inside compliance-tracker's own UI Composition Engine and "
    "Rule Engine call sites -- neither exists yet; this phase wires the real read/write plumbing so that "
    "the diff logic is already correct and re-runnable the moment that instrumentation lands, same "
    "'plumbing ready, ceiling honestly documented' pattern this plan's own "
    "ceiling_this_framework_cannot_exceed_yet note describes for route_coverage."
)


def close_phase(path):
    with open(path) as f:
        text = f.read()

    existing_block_re = re.compile(
        r'  - id: phase_2_distributed_trace_verification_wiring\n(?:.*\n)*?(?=  - id: phase_3_route_replay_storage_and_diff)'
    )
    existing_block = existing_block_re.search(text)
    if existing_block and "\n    status: done\n" in existing_block.group(0):
        print(f"{path}: phase_2 already shows status: done, no change")
        return False

    block_re = re.compile(
        r'(  - id: phase_2_distributed_trace_verification_wiring\n    name: Distributed trace verification wiring\n)',
        re.M,
    )
    # YAML single-quoted scalars escape an embedded ' by doubling it (''),
    # never a backslash -- same discipline close_phase3_testing_engine.py
    # already established for this exact failure mode.
    escaped_detail = STATUS_DETAIL.replace("'", "''")
    status_lines = f"    status: done\n    status_detail: '{escaped_detail}'\n"
    new_text, n = block_re.subn(lambda m: m.group(1) + status_lines, text, count=1)
    if n != 1:
        raise RuntimeError(f"could not locate phase_2 name: line in {path} (matched {n} times)")

    with open(path, "w") as f:
        f.write(new_text)
    print(f"{path}: set phase_2_distributed_trace_verification_wiring status: done")
    return True


if __name__ == "__main__":
    targets = sys.argv[1:] or [PLAN_PATH]
    for t in targets:
        close_phase(t)
