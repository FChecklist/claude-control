#!/usr/bin/env python3
"""
close_phase3_testing_engine.py -- closes out
TESTING_ENGINE_PHASE_PLAN_2026-07-24.yaml's phase_3_route_replay_storage_and_diff
entry in place, same targeted-text-surgery discipline
ai-os-scripts/generate_route_tests.py already uses for
ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml's per-route fields (regex-scoped to the
one phase's block, so every other phase's existing formatting/comments are
left untouched -- yaml.safe_dump would blow away this file's extensive inline
comments, same reason that script avoids it too).

Inserts `status:` + `status_detail:` right after phase_3's own `name:` line
(phase_3 currently has neither field -- phase_1 is the precedent for what
those two fields look like once a phase is real-done). status_detail cites
this task's own real task_id so scripts/auto_phase_continuation.py's
extract_produced_task_id() can resolve it via a live `gh pr list --head
worker/<task_id> --state merged` check, exactly like it already does for
Phase 1 -- never a self-reported status string alone.

Run: python3 ai-os-scripts/close_phase3_testing_engine.py
"""
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN_PATH = f"{REPO_ROOT}/ai-os/TESTING_ENGINE_PHASE_PLAN_2026-07-24.yaml"

TASK_ID = "task-20260724-115924-phase3-route-replay-storage-diff"

STATUS_DETAIL = (
    "DONE (real, scoped) as of " + TASK_ID + ". Delivered: (1) a real replay store -- "
    "scripts/superboss-register.py's new route_replay table (extends the existing "
    "ai-os/memory/superboss-register.sqlite DB, reusing knowledge_engine's own "
    "artifact_path/content_hash pattern per this session's 'extend, don't duplicate' rule, "
    "not a new database) plus capture-replay/run-replay/list-replays CLI subcommands, "
    "insert-only so a route's full capture/replay history stays queryable; (2) a real "
    "replay-and-diff runner -- ai-os-scripts/generate_route_replays.py, which reuses Phase 1's "
    "generate_route_tests.py dispatch-target derivation + curated REGISTERED_FIXTURES call_args "
    "directly (imported, not re-derived/re-curated) to execute each route's real dispatch-target "
    "function twice (capture, then replay) via `bunx bun run` against compliance-tracker's real "
    "checkout, diffing the two real JSON responses by sha256 response_hash equality. Run for real "
    "against all 5 populated_routes: RT-gratuity_calculator-001, RT-commission_calculator-001, "
    "RT-gst_calculation_engine-001, RT-trend_analysis_engine-001 all now replay_status=replayed_match "
    "(real capture + real replay + real hash-equal diff, since all 4 dispatch-target functions are "
    "confirmed side-effect-free/deterministic -- no Date.now()/Math.random() found by direct source "
    "grep before this was written -- so a genuine diff will surface automatically the next time this "
    "script runs after a real source change). RT-capability_registry_dedup-001 stays honestly "
    "replay_status=not_yet_captured: same real blocker Phase 1 already documented (no dispatchEngine() "
    "switch case for this capability), never a fabricated capture. Evidence: "
    "ai-os/testing_engine_evidence/phase3/<route_id>/ (run_script.ts + capture_output.json + "
    "replay_output.json + replay_verdict.json per real route, blocked_reason.txt for the one honestly "
    "blocked route). Registered in knowledge_engine: "
    "`python3 scripts/superboss-register.py query-knowledge \"phase_3_route_replay_storage_and_diff\" "
    "--tag domain:veridian-testing-engine-irvf-phased`. Deferred (honestly, not silently): Phase 2's "
    "trace_id enrichment (soft dependency only, per this phase's own dependency_mechanism -- replay "
    "capture/diff is meaningful with request/response payloads alone) remains unwired until Phase 2 "
    "ships, since Phase 2 itself is still blocked on the Auditor Engine's Phase 7 OTel emitter (zero "
    "spans exist anywhere today)."
)


def close_phase(path):
    with open(path) as f:
        text = f.read()

    existing_block_re = re.compile(
        r'  - id: phase_3_route_replay_storage_and_diff\n(?:.*\n)*?(?=  - id: phase_4_dependency_graph_validation)'
    )
    existing_block = existing_block_re.search(text)
    if existing_block and "\n    status: done\n" in existing_block.group(0):
        print(f"{path}: phase_3 already shows status: done, no change")
        return False

    block_re = re.compile(
        r'(  - id: phase_3_route_replay_storage_and_diff\n    name: Route replay storage \+ diff\n)',
        re.M,
    )
    # YAML single-quoted scalars escape an embedded ' by doubling it (''),
    # never a backslash -- STATUS_DETAIL's own apostrophes (don't, route's,
    # etc.) would otherwise break the block mapping exactly like this did on
    # the first (reverted) run of this script.
    escaped_detail = STATUS_DETAIL.replace("'", "''")
    status_lines = f"    status: done\n    status_detail: '{escaped_detail}'\n"
    new_text, n = block_re.subn(lambda m: m.group(1) + status_lines, text, count=1)
    if n != 1:
        raise RuntimeError(f"could not locate phase_3 name: line in {path} (matched {n} times)")

    with open(path, "w") as f:
        f.write(new_text)
    print(f"{path}: set phase_3_route_replay_storage_and_diff status: done")
    return True


if __name__ == "__main__":
    targets = sys.argv[1:] or [PLAN_PATH]
    for t in targets:
        close_phase(t)
