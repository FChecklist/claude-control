#!/usr/bin/env python3
"""VERIDIAN Auditor Engine -- Phase 8, master report software.

Per this plan's own SCOPE: "Build the master report software (aggregates
finding-record rows across all domains + repos)". This is pure
read-and-aggregate over the real `audit_findings` / `audit_runs` /
`audit_orchestration_runs` tables Phases 1-8 already write into (the same
knowledge_engine sqlite DB, ai-os/memory/superboss-register.sqlite) --
zero new findings are produced here, zero AI/LLM involvement, and nothing
in the underlying tables is mutated (read-only queries only, aside from
this script's own `audit_master_reports` history/snapshot row).

Per Phase 8's own dependency_mechanism note in the plan file: "the master
report software's queries are written against Phase 7's actual
event-stream + finding-record tables" -- this script queries
audit_findings (Phase 1+) and audit_events (Phase 7) directly, not a
re-derived or cached copy.

Usage:
    python3 generate_auditor_engine_master_report.py [--dry-run]

Writes (unless --dry-run):
  - ai-os/reports/AUDITOR_ENGINE_MASTER_REPORT_LATEST.json (overwritten every run --
    the current-state snapshot)
  - one new row in `audit_master_reports` (append-only history, same convention as
    audit_runs/audit_orchestration_runs) so trend-over-time queries are possible
    later without re-aggregating from audit_findings each time.

Exit code is always 0 unless the DB itself cannot be reached (real
execution failure, not "found 0 findings" which is valid data).
"""
import argparse
import datetime
import fcntl
import json
import os
import sqlite3
import sys

DB_PATH = os.environ.get("SUPERBOSS_REGISTER_DB", "/opt/veridian/ai-os/memory/superboss-register.sqlite")
_WRITE_LOCK_PATH = DB_PATH + ".writelock"
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.join(_HERE, "..")
REPORT_DIR = os.path.join(_REPO_ROOT, "ai-os", "reports")
REPORT_PATH = os.path.join(REPORT_DIR, "AUDITOR_ENGINE_MASTER_REPORT_LATEST.json")

# The full 15-domain inventory from Phase 0's own domains[] list, so the
# report can honestly show which domains have zero software-pipeline
# findings because no pipeline has run yet, vs. which don't have (and per
# Phase 0's own tool_mapping are never expected to have) a software
# pipeline at all.
ALL_15_DOMAINS = [
    "business-capability", "ddd", "enterprise-architecture", "clean-architecture",
    "product-quality", "data-model", "workflow", "api-contract", "metadata",
    "security", "ux", "ai-governance", "integration", "test-coverage", "documentation",
]
# Per Phase 0's own execution_path notes: business-capability is AI-Review-only
# with "tool_mapping: none" (no deterministic tool exists) -- correctly excluded
# from "software pipeline expected" rather than reported as a false gap.
NO_SOFTWARE_PIPELINE_EXPECTED = {"business-capability"}


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _report_id():
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"RPT-{ts}-{os.getpid():04x}"


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn, name):
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return row is not None


def ensure_table(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS audit_master_reports (
        report_id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        total_findings INTEGER NOT NULL,
        total_open INTEGER NOT NULL,
        domains_covered INTEGER NOT NULL,
        repos_covered INTEGER NOT NULL,
        summary_json TEXT NOT NULL
    );
    """)
    conn.commit()


def _count_by(conn, column):
    rows = conn.execute(f"SELECT {column} AS k, COUNT(*) AS n FROM audit_findings GROUP BY {column}").fetchall()
    return {r["k"]: r["n"] for r in rows}


def build_report(conn):
    if not _table_exists(conn, "audit_findings"):
        return {
            "generated_at": _now_iso(), "total_findings": 0, "error": "audit_findings table does not exist yet",
        }

    total_findings = conn.execute("SELECT COUNT(*) AS n FROM audit_findings").fetchone()["n"]
    by_severity = _count_by(conn, "severity")
    by_status = _count_by(conn, "status")
    by_remediation_type = _count_by(conn, "remediation_type")
    by_domain_total = _count_by(conn, "domain")
    by_repo_total = _count_by(conn, "repo")

    domain_rows = conn.execute("""
        SELECT domain, repo, severity, status, COUNT(*) AS n
        FROM audit_findings GROUP BY domain, repo, severity, status
    """).fetchall()
    by_domain = {}
    for row in domain_rows:
        d = by_domain.setdefault(row["domain"], {
            "total": 0, "open": 0, "by_severity": {}, "by_repo": {},
        })
        d["total"] += row["n"]
        if row["status"] == "open":
            d["open"] += row["n"]
        d["by_severity"][row["severity"]] = d["by_severity"].get(row["severity"], 0) + row["n"]
        d["by_repo"][row["repo"]] = d["by_repo"].get(row["repo"], 0) + row["n"]

    domains_with_findings = set(by_domain.keys())
    zero_finding_domains_with_pipeline = sorted(
        d for d in ALL_15_DOMAINS
        if d not in domains_with_findings and d not in NO_SOFTWARE_PIPELINE_EXPECTED
    )
    no_pipeline_expected_domains = sorted(NO_SOFTWARE_PIPELINE_EXPECTED)

    latest_runs = []
    orchestration_runs_recent = []
    if _table_exists(conn, "audit_runs"):
        rows = conn.execute("""
            SELECT domain, repo, MAX(ts) AS ts, status, total_findings, new_findings
            FROM audit_runs GROUP BY domain, repo ORDER BY ts DESC
        """).fetchall()
        latest_runs = [dict(r) for r in rows]
    if _table_exists(conn, "audit_orchestration_runs"):
        rows = conn.execute("""
            SELECT orchestration_run_id, ts, status, total_findings, total_new_findings, duration_s
            FROM audit_orchestration_runs ORDER BY ts DESC LIMIT 5
        """).fetchall()
        orchestration_runs_recent = [dict(r) for r in rows]

    events_by_type = {}
    if _table_exists(conn, "audit_events"):
        rows = conn.execute("SELECT event_type, COUNT(*) AS n FROM audit_events GROUP BY event_type").fetchall()
        events_by_type = {r["event_type"]: r["n"] for r in rows}

    return {
        "generated_at": _now_iso(),
        "totals": {
            "total_findings": total_findings,
            "by_severity": by_severity,
            "by_status": by_status,
            "by_remediation_type": by_remediation_type,
            "by_domain": by_domain_total,
            "by_repo": by_repo_total,
        },
        "by_domain": by_domain,
        "domains_with_zero_findings_and_pipeline_run": zero_finding_domains_with_pipeline,
        "domains_with_no_software_pipeline_expected": no_pipeline_expected_domains,
        "latest_run_per_domain_repo": latest_runs,
        "orchestration_runs_recent": orchestration_runs_recent,
        "audit_events_by_type": events_by_type,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="build and print the report, do not write file or DB row")
    args = ap.parse_args()

    conn = _connect()
    report = build_report(conn)
    report_id = _report_id()
    report["report_id"] = report_id

    report_path = None
    if not args.dry_run:
        os.makedirs(REPORT_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(_WRITE_LOCK_PATH), exist_ok=True)
        lockfile = open(_WRITE_LOCK_PATH, "w")
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        try:
            ensure_table(conn)
            with open(REPORT_PATH, "w") as f:
                json.dump(report, f, indent=2, default=str)
            report_path = REPORT_PATH
            totals = report.get("totals", {})
            conn.execute("""
                INSERT INTO audit_master_reports (report_id, ts, total_findings, total_open, domains_covered, repos_covered, summary_json)
                VALUES (?,?,?,?,?,?,?)
            """, (
                report_id, report["generated_at"], totals.get("total_findings", 0),
                (totals.get("by_status", {}) or {}).get("open", 0),
                len(report.get("by_domain", {})), len(totals.get("by_repo", {}) or {}),
                json.dumps(report, default=str),
            ))
            conn.commit()
        finally:
            fcntl.flock(lockfile, fcntl.LOCK_UN)
            lockfile.close()
    conn.close()

    output = {"ok": True, "report_id": report_id, "report_path": report_path, "dry_run": args.dry_run, **report}
    print(json.dumps(output, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
