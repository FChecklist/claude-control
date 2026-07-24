#!/usr/bin/env python3
"""VERIDIAN Auditor Engine -- Phase 6, ai-governance domain deterministic
pipeline (the promptfoo slice; bias/transparency/appropriate-use judgment
is already covered, separately, by ai-os/AI_GOVERNANCE_REVIEW_2026-07-24.yaml,
Phase 5's AI Review).

Per AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml phases[6].scope: "ai-governance
domain -- author + wire promptfoo test suites against real production
prompts (software-only slice)". Every prompt tested is the REAL,
'production'-labeled prompt text extracted live from compliance-tracker's
own drizzle migrations by extract_production_prompts_ai_governance.py (see
ai-os/promptfoo/prompts/MANIFEST.json), not hand-typed. Every promptfoo
assertion is deterministic (contains-json / javascript with no LLM call
inside it) -- see each suite's own assertions.js for the exact checks, all
of which either mirror compliance-tracker's real stripJsonFence()+
JSON.parse() production parse path or directly operationalize a literal
instruction the prompt's own text already states (0-100 bound, under-400-
words, never-invent-a-number). promptfoo itself calls a real LLM (groq,
llama-3.3-70b-versatile -- picked because it does NOT emit the
reasoning-preamble a reasoning-tier model would, matching production's own
non-reasoning-model expectation for a directly-JSON-parseable response;
confirmed via a live smoke-test comparison this task ran before choosing
it) to produce the text under test, but the VERDICT on that text is 100%
fixed assertions -- zero AI-in-the-loop for the finding-generation itself,
per this plan's own PART5 distinction ("promptfoo doesn't use an LLM to
decide the verdict, it uses fixed string/schema assertions").

Normalizes into the finding-record schema Phase 0 designed
(ai-os/AUDITOR_ENGINE_FINDING_RECORD_SCHEMA_2026-07-24.schema.json) and
writes into the same shared `audit_findings` table Phase 1-6's pipelines
already own.

Usage:
    python3 audit_pipeline_ai_governance.py [--dry-run] [--skip-run]
"""
import argparse
import contextlib
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
REPO_ROOT = os.path.join(_HERE, "..")
PROMPTFOO_DIR = os.path.join(REPO_ROOT, "ai-os", "promptfoo")
PROMPTFOO_VERSION = "0.121.19"

DOMAIN = "ai-governance"
STANDARD_CITED = "NIST AI Risk Management Framework (AI RMF 1.0) + EU AI Act (Regulation (EU) 2024/1689) risk-tiering obligations"

_SUITES = [
    "crm_intelligence_score_lead",
    "crm_intelligence_analyze_opportunity",
    "gst_ai_review_report",
    "construction_detect_budget_schedule_risk",
    "construction_generate_progress_summary",
]

# Assertion-name substrings -> severity. Injection/security-relevant
# failures (a real bound bypassed via prompt injection) outrank plain
# business-rule or format-compliance regressions -- same severity
# discipline as this plan's other domains (e.g. dependency-cruiser's
# error/warn -> high/medium mapping).
_SEVERITY_RULES = [
    ("injectionresistant", "high"),
    ("noinventednumbers", "medium"),
    ("acknowledgesmissingdata", "medium"),
    ("confidencelow", "low"),
    ("flagspastclosedate", "low"),
    ("riskleveli", "low"),
    ("verdictisvalid", "low"),
    ("reportunder400", "low"),
    ("scorewithinbounds", "medium"),
    ("winprobabilitywithinbounds", "medium"),
]


@contextlib.contextmanager
def _write_lock():
    os.makedirs(os.path.dirname(_WRITE_LOCK_PATH), exist_ok=True)
    with open(_WRITE_LOCK_PATH, "w") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lockfile, fcntl.LOCK_UN)


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS audit_findings (
        finding_id TEXT PRIMARY KEY,
        domain TEXT NOT NULL,
        standard_cited TEXT NOT NULL,
        clause_cited TEXT NOT NULL,
        artifact_path TEXT NOT NULL,
        artifact_line_start INTEGER,
        artifact_line_end INTEGER,
        artifact_commit TEXT,
        finding TEXT NOT NULL,
        severity TEXT NOT NULL CHECK(severity IN ('critical','high','medium','low','info')),
        not_covered_by_standard INTEGER NOT NULL DEFAULT 0,
        remediation_type TEXT NOT NULL CHECK(remediation_type IN ('software_fixable','ai_escalation_required')),
        status TEXT NOT NULL DEFAULT 'open'
            CHECK(status IN ('open','acknowledged','in_remediation','resolved','wont_fix','false_positive')),
        producer_kind TEXT NOT NULL,
        producer_name TEXT NOT NULL,
        producer_version TEXT,
        detected_at TEXT NOT NULL,
        repo TEXT NOT NULL,
        event_id TEXT,
        owner_decision_ref TEXT,
        raw_json TEXT NOT NULL DEFAULT '{}',
        first_seen_ts TEXT NOT NULL,
        last_seen_ts TEXT NOT NULL,
        run_id TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_audit_findings_domain ON audit_findings(domain);
    CREATE INDEX IF NOT EXISTS idx_audit_findings_repo ON audit_findings(repo);
    CREATE INDEX IF NOT EXISTS idx_audit_findings_status ON audit_findings(status);
    CREATE INDEX IF NOT EXISTS idx_audit_findings_producer ON audit_findings(producer_name);

    CREATE TABLE IF NOT EXISTS audit_runs (
        run_id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        domain TEXT NOT NULL,
        repo TEXT NOT NULL,
        tools_run TEXT NOT NULL,
        tools_skipped TEXT NOT NULL DEFAULT '{}',
        total_findings INTEGER NOT NULL,
        new_findings INTEGER NOT NULL,
        duration_s REAL NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('ok','partial','failed')),
        notes TEXT
    );
    """)
    conn.commit()


def _run_id():
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"AUD-{ts}-{os.getpid():04x}"


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _severity_for(assertion_type, assertion_value):
    key = ""
    if isinstance(assertion_value, str):
        key = assertion_value.split(":")[-1].lower().replace("_", "")
    for needle, sev in _SEVERITY_RULES:
        if needle in key:
            return sev
    return "low" if assertion_type != "contains-json" else "medium"


def run_suite(suite_name, skip_run):
    suite_dir = os.path.join(PROMPTFOO_DIR, suite_name)
    config_path = os.path.join(suite_dir, "promptfooconfig.yaml")
    out_path = os.path.join(suite_dir, ".last_result.json")
    if not skip_run:
        proc = subprocess.run(
            ["npx", "--yes", f"promptfoo@{PROMPTFOO_VERSION}", "eval", "-c", "promptfooconfig.yaml",
             "--output", ".last_result.json", "--no-progress-bar", "--no-table"],
            cwd=suite_dir, capture_output=True, text=True, timeout=180,
        )
        if not os.path.isfile(out_path):
            raise RuntimeError(f"promptfoo produced no output for {suite_name} (exit {proc.returncode}): {proc.stderr[-1500:]}")
    with open(out_path) as f:
        data = json.load(f)

    records = []
    total_tests = 0
    total_asserts = 0
    for result in data.get("results", {}).get("results", []):
        total_tests += 1
        test_desc = (result.get("testCase", {}) or {}).get("description", "unnamed test")
        for g in result.get("gradingResult", {}).get("componentResults", []) or []:
            total_asserts += 1
            if g.get("pass"):
                continue
            assertion = g.get("assertion", {}) or {}
            atype = assertion.get("type", "unknown")
            aval = assertion.get("value")
            reason = g.get("reason", "assertion failed")
            raw = f"promptfoo:{suite_name}:{test_desc}:{atype}:{aval}"
            finding_id = "fnd_" + hashlib.sha256(raw.encode()).hexdigest()[:24]
            records.append({
                "finding_id": finding_id,
                "domain": DOMAIN,
                "standard_cited": STANDARD_CITED,
                "clause_cited": f"promptfoo:{suite_name}:{atype}",
                "artifact_path": f"ai-os/promptfoo/{suite_name}/promptfooconfig.yaml (test: {test_desc})",
                "finding": f"{suite_name} -- test '{test_desc}' failed assertion ({atype}): {reason}",
                "severity": _severity_for(atype, aval),
                "not_covered_by_standard": False,
                "remediation_type": "software_fixable",
                "status": "open",
                "producer": {"kind": "oss_tool", "name": "promptfoo", "version": PROMPTFOO_VERSION},
                "repo": "compliance-tracker",
                "_raw": {"suite": suite_name, "test": test_desc, "assertion_type": atype, "reason": reason},
            })
    return records, {"suite": suite_name, "tests": total_tests, "assertions": total_asserts, "failed": len(records)}


def upsert_findings(conn, records, run_id):
    now = _now_iso()
    new_count = 0
    new_finding_ids = set()
    for r in records:
        prod = r["producer"]
        cur = conn.execute("SELECT status, first_seen_ts FROM audit_findings WHERE finding_id = ?", (r["finding_id"],))
        existing = cur.fetchone()
        if existing is None:
            new_count += 1
            new_finding_ids.add(r["finding_id"])
            status = r["status"]
            first_seen = now
        else:
            status = existing["status"] if existing["status"] != "open" else r["status"]
            first_seen = existing["first_seen_ts"]
        conn.execute("""
            INSERT INTO audit_findings (
                finding_id, domain, standard_cited, clause_cited,
                artifact_path, artifact_line_start, artifact_line_end, artifact_commit,
                finding, severity, not_covered_by_standard, remediation_type, status,
                producer_kind, producer_name, producer_version, detected_at, repo,
                event_id, owner_decision_ref, raw_json, first_seen_ts, last_seen_ts, run_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(finding_id) DO UPDATE SET
                finding=excluded.finding, severity=excluded.severity, status=excluded.status,
                detected_at=excluded.detected_at, raw_json=excluded.raw_json,
                last_seen_ts=excluded.last_seen_ts, run_id=excluded.run_id
        """, (
            r["finding_id"], r["domain"], r["standard_cited"], r["clause_cited"],
            r["artifact_path"], None, None, None,
            r["finding"], r["severity"], int(r["not_covered_by_standard"]), r["remediation_type"], status,
            prod["kind"], prod["name"], prod.get("version"), now, r["repo"],
            None, None, json.dumps(r["_raw"], default=str), first_seen, now, run_id,
        ))
    conn.commit()
    return new_count, new_finding_ids


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-run", action="store_true", help="reuse each suite's last .last_result.json instead of re-invoking promptfoo")
    args = ap.parse_args()

    run_id = _run_id()
    start = datetime.datetime.now(datetime.timezone.utc)
    all_records = []
    suite_stats = []
    errors = {}
    for suite in _SUITES:
        try:
            records, stats = run_suite(suite, args.skip_run)
            all_records.extend(records)
            suite_stats.append(stats)
        except Exception as exc:
            errors[suite] = str(exc)
    duration = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()

    new_count = 0
    if not args.dry_run:
        with _write_lock():
            conn = _connect()
            ensure_tables(conn)
            new_count, new_finding_ids = upsert_findings(conn, all_records, run_id)
            conn.execute("""
                INSERT INTO audit_runs (run_id, ts, domain, repo, tools_run, tools_skipped,
                                         total_findings, new_findings, duration_s, status, notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                run_id, _now_iso(), DOMAIN, "compliance-tracker",
                json.dumps({"promptfoo": {"version": PROMPTFOO_VERSION, "suites": suite_stats}}),
                json.dumps(errors),
                len(all_records), new_count, duration, "ok" if not errors else "partial", json.dumps(errors) if errors else None,
            ))
            conn.commit()
            conn.close()

    summary = {
        "ok": not errors, "run_id": run_id, "domain": DOMAIN,
        "suite_stats": suite_stats, "errors": errors,
        "total_findings": len(all_records), "new_findings": new_count,
        "duration_s": round(duration, 2), "dry_run": args.dry_run,
    }
    print(json.dumps(summary, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
