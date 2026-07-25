#!/usr/bin/env python3
"""VERIDIAN Auditor Engine -- Phase 8, master orchestration entrypoint.

Per this plan's own SCOPE: "Orchestrate all domains' audit-run scripts
under one cron-driven entrypoint (zero AI in the loop, per PART5)". This
script does not re-implement any domain's scan logic -- Phases 1-6 already
built and wired 10 real, independently-runnable audit_pipeline_*.py
scripts (security, api-contract, architecture [ddd + clean-architecture +
enterprise-architecture], data-model, documentation, integration,
metadata, product-quality, workflow[-transitions], ai-governance),
covering all 15 domains named in Phase 0's own inventory except
business-capability (AI-Review-only, no software pipeline exists or is
expected -- see this plan's own domains[].business-capability row) and
test-coverage/ux (Phase 1's own sub-scopes, explicitly not started per
that phase's known_gaps -- carried forward, not fabricated here).

What this script actually does: shells out to each existing pipeline
script's own `python3 <script>.py [--dry-run]` CLI (the exact same
invocation a human or cron would use), one at a time, in the same process
so a single crontab line can eventually replace the 10 separate ones a
future Owner-approved cron entry would otherwise need -- then writes one
`audit_orchestration_runs` summary row and (unless --skip-report) invokes
the Phase 8 master report generator as its final step. It parses each
sub-pipeline's own already-emitted JSON summary rather than re-deriving
finding counts itself -- zero duplication of Phases 1-7's real logic.

Zero AI/LLM involvement anywhere in this file (the ai-governance
sub-pipeline's own LLM-under-test calls are that pipeline's business, not
this orchestrator's -- see --skip-ai-governance-live-run below to avoid
that real cost during verification/dry-run use, same convention Phase 7's
own close-out evidence used).

Usage:
    python3 audit_pipeline_master_orchestrator.py [--dry-run]
                                                    [--domains security,data_model,...]
                                                    [--skip-ai-governance-live-run]
                                                    [--skip-report]

Exit code is 0 only if every invoked sub-pipeline itself exited 0
(status != failed); a non-zero exit from any sub-pipeline is a real
pipeline failure and this script propagates that (same "findings are
data, execution failure is not" convention every audit_pipeline_*.py
already follows).
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
import sqlite3
import subprocess
import sys

DB_PATH = os.environ.get("SUPERBOSS_REGISTER_DB", "/opt/veridian/ai-os/memory/superboss-register.sqlite")
_WRITE_LOCK_PATH = DB_PATH + ".writelock"
_HERE = os.path.dirname(os.path.abspath(__file__))

# Ordered so cheaper/faster pipelines (no npm install, no live LLM calls) run
# first -- purely a wall-clock convenience, no dependency between entries:
# each sub-pipeline already owns and writes its own domain(s)' rows
# independently, same as if invoked separately by cron.
PIPELINES = [
    {"key": "security", "script": "audit_pipeline_security.py", "domains": ["security"]},
    {"key": "metadata", "script": "audit_pipeline_metadata.py", "domains": ["metadata"]},
    {"key": "api_contract", "script": "audit_pipeline_api_contract.py", "domains": ["api-contract"]},
    {"key": "data_model", "script": "audit_pipeline_data_model.py", "domains": ["data-model"]},
    {"key": "product_quality", "script": "audit_pipeline_product_quality.py", "domains": ["product-quality"]},
    {"key": "documentation", "script": "audit_pipeline_documentation.py", "domains": ["documentation"]},
    {"key": "workflow_transitions", "script": "audit_pipeline_workflow_transitions.py", "domains": ["workflow"]},
    {"key": "architecture", "script": "audit_pipeline_architecture.py",
     "domains": ["ddd", "clean-architecture", "enterprise-architecture"]},
    {"key": "integration", "script": "audit_pipeline_integration.py", "domains": ["integration"]},
    {"key": "ai_governance", "script": "audit_pipeline_ai_governance.py", "domains": ["ai-governance"]},
]
_PIPELINE_KEYS = [p["key"] for p in PIPELINES]


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_id():
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"AUDORC-{ts}-{os.getpid():04x}"


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS audit_orchestration_runs (
        orchestration_run_id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        pipelines_requested TEXT NOT NULL,
        pipelines_ok TEXT NOT NULL,
        pipelines_partial TEXT NOT NULL,
        pipelines_failed TEXT NOT NULL,
        total_findings INTEGER NOT NULL,
        total_new_findings INTEGER NOT NULL,
        duration_s REAL NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('ok','partial','failed')),
        report_ref TEXT,
        notes TEXT
    );
    """)
    conn.commit()


def _write_lock():
    os.makedirs(os.path.dirname(_WRITE_LOCK_PATH), exist_ok=True)
    lockfile = open(_WRITE_LOCK_PATH, "w")
    fcntl.flock(lockfile, fcntl.LOCK_EX)
    return lockfile


def _parse_summary(stdout):
    """Each audit_pipeline_*.py's main() prints exactly one JSON object as
    its last (and, on a normal successful run, only) stdout write. Parse
    the whole stream first (the common case); fall back to locating the
    last top-level `{...}` block for resilience against any stray text a
    sub-pipeline might emit before its own summary print."""
    text = stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.rfind("\n{")
    candidate = text[start + 1:] if start != -1 else text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def run_pipeline(entry, dry_run, skip_ai_governance_live_run):
    script_path = os.path.join(_HERE, entry["script"])
    cmd = [sys.executable, script_path]
    if dry_run:
        cmd.append("--dry-run")
    if entry["key"] == "ai_governance" and skip_ai_governance_live_run:
        cmd.append("--skip-run")

    start = datetime.datetime.now(datetime.timezone.utc)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired as exc:
        duration = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()
        return {
            "key": entry["key"], "domains": entry["domains"], "ok": False, "status": "failed",
            "exit_code": None, "duration_s": round(duration, 2),
            "error": f"timed out after {exc.timeout}s", "summary": None,
        }
    duration = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()
    summary = _parse_summary(proc.stdout)
    status = (summary or {}).get("status")
    ok = proc.returncode == 0 and status != "failed"
    return {
        "key": entry["key"], "domains": entry["domains"], "ok": ok,
        "status": status or ("ok" if ok else "failed"),
        "exit_code": proc.returncode, "duration_s": round(duration, 2),
        "error": None if ok else (proc.stderr[-2000:] or f"non-zero exit {proc.returncode}, no summary parsed"),
        "summary": summary,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                     help="pass --dry-run through to every sub-pipeline; nothing is written to the DB")
    ap.add_argument("--domains", default=None,
                     help=f"comma-separated subset of pipeline keys to run (default: all). Valid keys: {','.join(_PIPELINE_KEYS)}")
    ap.add_argument("--skip-ai-governance-live-run", action="store_true",
                     help="pass --skip-run to audit_pipeline_ai_governance.py (reuse cached results, avoid a real LLM call cost)")
    ap.add_argument("--skip-report", action="store_true",
                     help="do not invoke the master report generator after running pipelines")
    args = ap.parse_args()

    requested_keys = _PIPELINE_KEYS
    if args.domains:
        requested_keys = [k.strip() for k in args.domains.split(",") if k.strip()]
        unknown = [k for k in requested_keys if k not in _PIPELINE_KEYS]
        if unknown:
            print(json.dumps({"ok": False, "error": f"unknown pipeline key(s): {unknown}. Valid: {_PIPELINE_KEYS}"}))
            return 2

    run_id = _run_id()
    start = datetime.datetime.now(datetime.timezone.utc)
    results = []
    for entry in PIPELINES:
        if entry["key"] not in requested_keys:
            continue
        results.append(run_pipeline(entry, args.dry_run, args.skip_ai_governance_live_run))

    duration = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()
    ok_keys = [r["key"] for r in results if r["ok"] and r["status"] == "ok"]
    partial_keys = [r["key"] for r in results if r["ok"] and r["status"] == "partial"]
    failed_keys = [r["key"] for r in results if not r["ok"]]
    total_findings = sum((r["summary"] or {}).get("total_findings", 0) or 0 for r in results)
    total_new_findings = sum((r["summary"] or {}).get("new_findings", 0) or 0 for r in results)
    overall_status = "failed" if (failed_keys and not ok_keys and not partial_keys) else ("partial" if failed_keys or partial_keys else "ok")

    report_ref = None
    if not args.dry_run and not args.skip_report:
        report_script = os.path.join(_HERE, "generate_auditor_engine_master_report.py")
        rproc = subprocess.run([sys.executable, report_script], capture_output=True, text=True, timeout=300)
        rsummary = _parse_summary(rproc.stdout)
        report_ref = (rsummary or {}).get("report_path") if rproc.returncode == 0 else None

    if not args.dry_run:
        lockfile = _write_lock()
        try:
            conn = _connect()
            ensure_table(conn)
            conn.execute("""
                INSERT INTO audit_orchestration_runs (
                    orchestration_run_id, ts, pipelines_requested, pipelines_ok, pipelines_partial,
                    pipelines_failed, total_findings, total_new_findings, duration_s, status, report_ref, notes
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                run_id, _now_iso(), json.dumps(requested_keys), json.dumps(ok_keys), json.dumps(partial_keys),
                json.dumps(failed_keys), total_findings, total_new_findings, duration, overall_status, report_ref,
                None if not failed_keys else json.dumps({r["key"]: r["error"] for r in results if not r["ok"]}),
            ))
            conn.commit()
            conn.close()
        finally:
            fcntl.flock(lockfile, fcntl.LOCK_UN)
            lockfile.close()

    summary = {
        "ok": overall_status != "failed",
        "orchestration_run_id": run_id,
        "status": overall_status,
        "pipelines_requested": requested_keys,
        "pipelines_ok": ok_keys,
        "pipelines_partial": partial_keys,
        "pipelines_failed": failed_keys,
        "total_findings": total_findings,
        "total_new_findings": total_new_findings,
        "duration_s": round(duration, 2),
        "report_ref": report_ref,
        "dry_run": args.dry_run,
        "results": results,
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0 if overall_status != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
