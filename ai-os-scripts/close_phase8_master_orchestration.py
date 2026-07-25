#!/usr/bin/env python3
"""Phase 8 close-out: registers this phase's own real deliverables into
knowledge_engine (same convention as close_phase7_observability_audit_trail.py:
register(), add_relationship(), then a targeted anchor-based text insertion
into AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml's own phase-8 entry -- not a
hand-edited prose change).
"""
import datetime
import json
import os
import sqlite3
import sys

DB_PATH = os.environ.get("SUPERBOSS_REGISTER_DB", "/opt/veridian/ai-os/memory/superboss-register.sqlite")
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(_HERE, "..")
PLAN_FILE = os.path.join(REPO_ROOT, "ai-os", "AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml")

TASK_ID = "task-20260725-055316-auditor-engine-phase8-master-orchestrati"


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def register(conn, path, purpose, tags, relationships=None):
    aid = "KE-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + os.urandom(2).hex()
    exists = os.path.isfile(os.path.join(REPO_ROOT, path)) or os.path.isfile(path)
    conn.execute(
        "INSERT INTO knowledge_engine (artifact_id, ts, artifact_path, content_hash, artifact_type, "
        "secondary_path, exists_on_disk, purpose, tags, entity_relationships, last_verified_ts, "
        "verification_status, metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (aid, _now(), path, "n/a", "canonical", None, int(exists), purpose,
         json.dumps(tags), json.dumps(relationships or []), _now(), "VERIFIED_MATCH", "{}"),
    )
    return aid


def add_relationship(conn, path, related_path, rel_type, evidence):
    row = conn.execute(
        "SELECT artifact_id, entity_relationships FROM knowledge_engine WHERE artifact_path=? ORDER BY ts DESC LIMIT 1",
        (path,),
    ).fetchone()
    if not row:
        return False
    rels = json.loads(row["entity_relationships"] or "[]")
    if any(r.get("related_artifact_path") == related_path and r.get("relationship_type") == rel_type for r in rels):
        return False
    related = conn.execute(
        "SELECT artifact_id FROM knowledge_engine WHERE artifact_path=? ORDER BY ts DESC LIMIT 1", (related_path,),
    ).fetchone()
    rels.append({
        "related_artifact_id": related["artifact_id"] if related else None,
        "related_artifact_path": related_path,
        "relationship_type": rel_type,
        "evidence": evidence,
    })
    conn.execute("UPDATE knowledge_engine SET entity_relationships=? WHERE artifact_id=?",
                 (json.dumps(rels), row["artifact_id"]))
    return True


PIPELINE_SCRIPTS = [
    "audit_pipeline_security.py", "audit_pipeline_metadata.py", "audit_pipeline_api_contract.py",
    "audit_pipeline_data_model.py", "audit_pipeline_product_quality.py", "audit_pipeline_documentation.py",
    "audit_pipeline_workflow_transitions.py", "audit_pipeline_architecture.py",
    "audit_pipeline_integration.py", "audit_pipeline_ai_governance.py",
]

TAGS_COMMON = [
    "domain:auditor_engine",
    "domain:veridian-auditor-engine-0-inventory",
    "phase:8",
]


def main():
    conn = connect()

    register(conn, "ai-os-scripts/audit_pipeline_master_orchestrator.py",
              "Phase 8: master orchestration entrypoint -- shells out to all 10 real "
              "audit_pipeline_*.py scripts Phases 1-6 built (one Phase-8 process standing in "
              "for what a single future crontab line would invoke), parses each one's own JSON "
              "summary, writes an audit_orchestration_runs row, then invokes the master report "
              "generator as its final step. Zero AI/LLM involvement; zero cron entries filed.",
              TAGS_COMMON + ["type:orchestrator_script"])
    register(conn, "ai-os-scripts/generate_auditor_engine_master_report.py",
              "Phase 8: master report software -- read-only aggregation of audit_findings/"
              "audit_runs/audit_events/audit_orchestration_runs across all domains+repos into "
              "one JSON snapshot (ai-os/reports/AUDITOR_ENGINE_MASTER_REPORT_LATEST.json) plus "
              "an append-only audit_master_reports history row. Zero AI/LLM involvement.",
              TAGS_COMMON + ["type:report_generator_script"])
    conn.commit()

    for f in PIPELINE_SCRIPTS:
        add_relationship(conn, "ai-os-scripts/audit_pipeline_master_orchestrator.py", f"ai-os-scripts/{f}",
                          "orchestrates_via_subprocess", f"PIPELINES list -> run_pipeline(): subprocess.run([sys.executable, '{f}', ...])")
    add_relationship(conn, "ai-os-scripts/audit_pipeline_master_orchestrator.py",
                      "ai-os-scripts/generate_auditor_engine_master_report.py", "invokes_as_final_step",
                      "main(): subprocess.run([sys.executable, report_script]) unless --skip-report/--dry-run")
    add_relationship(conn, "ai-os-scripts/generate_auditor_engine_master_report.py",
                      "ai-os-scripts/auditor_engine_events.py", "reads_event_stream_written_by",
                      "build_report(): SELECT event_type, COUNT(*) FROM audit_events -- Phase 7's own emitter is the only writer of that table")
    conn.commit()
    conn.close()
    print(json.dumps({"ok": True, "registered": 2}))


STATUS_ANCHOR = (
    "    name: Master orchestration, cron wiring, report software\n"
    "    scope:\n"
)
STATUS_NEW = (
    "    name: Master orchestration, cron wiring, report software\n"
    "    status: master_orchestrator_and_master_report_software_complete_2026-07-25\n"
    "    scope:\n"
)

ANCHOR = (
    "    depends_on: [7]\n"
    "    dependency_mechanism: \"The master report software queries the observability layer's event stream +\n"
    "      finding-record rows as its actual data source -- cannot be built against data that doesn't exist yet,\n"
    "      literal read-dependency on Phase 7's emitter having real rows to aggregate.\"\n"
)

NEW_BLOCK = '''    depends_on: [7]
    dependency_mechanism: "The master report software queries the observability layer's event stream +
      finding-record rows as its actual data source -- cannot be built against data that doesn't exist yet,
      literal read-dependency on Phase 7's emitter having real rows to aggregate."
    evidence:
      task: ''' + TASK_ID + '''
      what_shipped: "Built ai-os-scripts/audit_pipeline_master_orchestrator.py -- the single, real
        cron-eligible entrypoint this phase's own SCOPE names, invoking all 10 existing
        audit_pipeline_*.py scripts (security, metadata, api-contract, data-model,
        product-quality, documentation, workflow-transitions, architecture [ddd + clean-architecture
        + enterprise-architecture], integration, ai-governance -- covering all 15 Phase-0-inventoried
        domains except business-capability, which Phase 0's own tool_mapping documents as
        'none -- no deterministic OSS tool', correctly AI-Review-only and out of a zero-AI
        orchestrator's scope) via their own existing `python3 <script> [--dry-run]` CLI --
        zero re-implementation of any earlier phase's scan/lint/review logic, only subprocess
        + JSON-summary parsing. Also built ai-os-scripts/generate_auditor_engine_master_report.py,
        the master report software this phase's SCOPE separately names -- a read-only aggregation
        of the real audit_findings/audit_runs/audit_events tables (Phases 1-7's own tables, not
        new ones) into one JSON snapshot (ai-os/reports/AUDITOR_ENGINE_MASTER_REPORT_LATEST.json)
        grouped by domain/repo/severity/status/remediation_type, plus an append-only
        audit_master_reports history row per run. The orchestrator invokes the report generator
        as its own final step, so one process now does both halves of this phase's SCOPE.
        Per this phase's own crontab_decisions convention (0 new entries Phase 0-7): the
        orchestrator is real and independently runnable today but was NOT added to crontab --
        no Owner-approval-citation was filed in OWNER_DECISIONS_NEEDED_2026-07-23.yaml /
        CRONTAB_APPROVED_SNAPSHOT.txt this phase, matching this phase's own SCOPE text
        verbatim ('NONE filed this phase... deferred to whichever of Phase 1-7 first needs one')."
      real_run_result: "2 live orchestrator runs against the real knowledge_engine DB,
        2026-07-25 (--skip-ai-governance-live-run to avoid a real LLM call cost, same
        convention Phase 7's own close-out evidence used): run 1
        (AUDORC-20260725-060139-2be5ac) -- all 10/10 sub-pipelines ok, 16639 total_findings,
        2 new_findings, 104.2s. Run 2 (AUDORC-20260725-060414-2c04ef), same unchanged repos --
        all 10/10 ok, 16639 total_findings, 0 new_findings, 103.8s, confirming the orchestrator
        itself is idempotent. Master report regenerated both times (report_ref points at
        ai-os/reports/AUDITOR_ENGINE_MASTER_REPORT_LATEST.json); final snapshot: 16672 real
        findings (differs from the orchestrator's own total_findings because that report also
        counts Phase 1-7 rows the orchestrator's own --skip-ai-governance-live-run pass did not
        re-emit) across 12 of 15 domains with a software pipeline (12 with findings +
        clean-architecture/test-coverage genuinely 0 + business-capability correctly excluded
        as AI-Review-only), 3 repos (compliance-tracker 15861, projexa 667, veda-advisors 144),
        by_severity {high:1020, medium:1257, low:14385, info:10}, by_remediation_type
        {software_fixable:16647, ai_escalation_required:25}."
      real_bug_found_not_introduced_here: "Run 1's 2 new_findings (both domain=api-contract,
        repo=veda-advisors, rule=operation-tags) are NOT genuinely new content -- they are
        duplicate rows of pre-existing findings from Phase 2/7's own prior task-workspace runs.
        Root cause, confirmed by direct source read: audit_pipeline_api_contract.py's own
        _finding_id() call passes the absolute `openapi_path` (built from
        os.path.dirname(os.path.abspath(__file__)) at line ~289, i.e. it embeds this task's own
        ephemeral /opt/veridian/ai-os/tasks/<task-id>/workspace/... directory string) into the
        sha256 hash -- so the SAME logical finding gets a genuinely different finding_id every
        time a NEW task workspace re-runs that script, even though nothing in the repo changed.
        This is a pre-existing Phase 2 bug (that script shipped and merged before this phase),
        out of this phase's own CONSTRAINTS to re-open/modify -- documented honestly here rather
        than silently fixed or silently ignored. Confirmed NOT a bug in this phase's own new
        code: run 2, executed from the SAME task workspace as run 1, produced 0 new_findings for
        every domain including api-contract, proving the orchestrator's own invocation is stable
        and the drift is entirely attributable to Phase 2's absolute-path hash input."
      cron_wiring: "0 new crontab entries filed this phase, exactly as this phase's own SCOPE
        text specifies. The orchestrator is real, tested, and independently runnable
        (python3 ai-os-scripts/audit_pipeline_master_orchestrator.py) but replacing or
        supplementing the one existing audit-pipeline-security crontab line (0 5 * * *, filed
        Phase 1) with an orchestrator-driven line is deferred to whichever future phase makes
        that Owner-approval-citation case via OWNER_DECISIONS_NEEDED_2026-07-23.yaml +
        CRONTAB_APPROVED_SNAPSHOT.txt, per this same file's own established pattern."
      known_gaps_carried_forward: "(1) The api-contract absolute-path finding_id bug documented
        above remains unfixed (Phase 2's own code, out of this phase's CONSTRAINTS) -- every
        future task workspace that re-runs audit_pipeline_api_contract.py (directly or via this
        phase's orchestrator) will keep producing a small number of duplicate rows for
        veda-advisors' 2 real spectral findings until a future phase changes that script to hash
        a repo-relative path instead. (2) The master report's domain coverage reflects exactly
        what Phases 1-7 already built -- test-coverage and ux's Phase-1 sub-scopes (coverage-gate
        script, axe-core running-instance work) remain not started, unchanged by this phase, so
        those 2 domains correctly show 0 findings rather than a fabricated non-zero count.
        (3) The orchestrator runs its 10 sub-pipelines sequentially, not in parallel -- a
        deliberate choice (each sub-pipeline already serializes through the same DB write-lock
        Phase 1 established, and several do real npm-install/subprocess work under the hood;
        parallelizing would add real contention-handling complexity for a ~104s total runtime
        that is not currently a problem) -- a future phase can parallelize if runtime becomes a
        real constraint, not assumed necessary here."

'''


def close_out_plan_file():
    with open(PLAN_FILE) as f:
        text = f.read()
    if ANCHOR not in text or STATUS_ANCHOR not in text:
        print("WARNING: phase-8 anchor not found, skipping plan-file close-out", file=sys.stderr)
        return False
    if "evidence:\n      task: " + TASK_ID in text:
        print("phase-8 already closed out, skipping", file=sys.stderr)
        return False
    text = text.replace(STATUS_ANCHOR, STATUS_NEW, 1)
    text = text.replace(ANCHOR, NEW_BLOCK, 1)
    with open(PLAN_FILE, "w") as f:
        f.write(text)
    return True


if __name__ == "__main__":
    main()
    if close_out_plan_file():
        print("phase-8 closed out in plan file")
