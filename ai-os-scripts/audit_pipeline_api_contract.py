#!/usr/bin/env python3
"""VERIDIAN Auditor Engine -- Phase 2, api-contract domain deterministic lint pipeline.

Runs Spectral against the real, hand-authored OpenAPI 3.1 documents in
ai-os/openapi/*.yaml (one per repo: compliance-tracker, projexa,
veda-advisors -- authored this same phase, see each file's own header for
which real route.ts handlers it documents), normalizes Spectral's native JSON
output into the finding-record schema Phase 0 designed
(ai-os/AUDITOR_ENGINE_FINDING_RECORD_SCHEMA_2026-07-24.schema.json), and
writes the result into the same `audit_findings` table
audit_pipeline_security.py (Phase 1) already owns in the shared
knowledge_engine database (ai-os/memory/superboss-register.sqlite) -- not a
new, separate store.

Zero AI/LLM involvement anywhere in this file. Every finding is produced by
the deterministic Spectral binary (producer.kind=oss_tool); this script only
shells out, parses, and writes rows.

Real, reproduced tool quirk documented here rather than worked around
silently: Spectral 6.16.2's CLI (even with `-f json -q`) appends a trailing
human-readable summary string directly after the JSON array on the same
stdout stream with no separating newline (e.g. `[]0 results` or
`[...]1 problem`) -- confirmed by direct reproduction this phase, not assumed.
`_parse_spectral_json()` below uses json.JSONDecoder().raw_decode() to read
only the well-formed JSON prefix and discards the rest, rather than
json.loads() which throws JSONDecodeError("Extra data") on this exact output.

Usage:
    python3 audit_pipeline_api_contract.py [--openapi-dir ai-os/openapi] [--dry-run]

Exit code is always 0 on a completed run (findings are data, not pipeline
failure) unless Spectral itself fails to execute at all (binary missing,
non-lint crash) -- that IS a pipeline failure and exits non-zero so
cron/run-logged.sh correctly marks the job failed.
"""
import argparse
import contextlib
import datetime
import fcntl
import glob
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys

DB_PATH = os.environ.get("SUPERBOSS_REGISTER_DB", "/opt/veridian/ai-os/memory/superboss-register.sqlite")
_WRITE_LOCK_PATH = DB_PATH + ".writelock"

SPECTRAL_RULESET = os.environ.get(
    "AUDIT_SPECTRAL_RULESET",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ai-os", "openapi", ".spectral.yaml"),
)

DOMAIN = "api-contract"
STANDARD_CITED = "OpenAPI Initiative (OAI) Specification 3.1"

# Maps an ai-os/openapi/<repo>.openapi.yaml filename to the repo enum value
# AUDITOR_ENGINE_FINDING_RECORD_SCHEMA_2026-07-24.schema.json's repo property
# requires. Extend this dict (not the schema) the day a 4th OpenAPI document
# is authored for one of the other repos.
_REPO_BY_FILENAME = {
    "compliance-tracker.openapi.yaml": "compliance-tracker",
    "projexa.openapi.yaml": "projexa",
    "veda-advisors.openapi.yaml": "veda-advisors",
}


@contextlib.contextmanager
def _write_lock():
    """Same OS-level flock convention as audit_pipeline_security.py's own
    _write_lock() -- multiple cron-driven writers touch this one shared
    sqlite DB, so every writer serializes through this lock file."""
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
    # Identical DDL to audit_pipeline_security.py's ensure_tables() -- same
    # shared table, CREATE TABLE IF NOT EXISTS makes re-declaring it here safe
    # (this script is runnable standalone, without security's pipeline ever
    # having executed first).
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


def _finding_id(tool, repo, rule, path, line, extra=""):
    raw = f"{tool}:{repo}:{rule}:{path}:{line}:{extra}"
    return "fnd_" + hashlib.sha256(raw.encode()).hexdigest()[:24]


def _tool_version(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (out.stdout + out.stderr).strip().splitlines()[0][:80]
    except Exception as exc:  # binary missing/misbehaving -- surfaced by caller, not swallowed
        return f"unknown ({exc})"


def _parse_spectral_json(raw):
    """See module docstring -- Spectral 6.16.2 appends a trailing human
    summary string directly onto the JSON array with no newline. raw_decode
    reads exactly the JSON prefix and ignores anything after it."""
    raw = raw.strip()
    if not raw:
        return []
    decoder = json.JSONDecoder()
    obj, _end = decoder.raw_decode(raw)
    return obj


_SEVERITY_MAP = {0: "high", 1: "medium", 2: "low", 3: "info"}  # spectral DiagnosticSeverity: error/warn/info/hint


def run_spectral(openapi_path, repo_name):
    version = _tool_version(["spectral", "--version"])
    cmd = ["spectral", "lint", "--ruleset", SPECTRAL_RULESET, "-f", "json", "-q", openapi_path]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    # spectral exits 1 when lint results include anything at/above
    # --fail-severity (default: error) -- that's data, not an execution
    # failure. A genuine execution failure (missing ruleset, crash) prints to
    # stderr and produces no parseable JSON prefix on stdout at all.
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"spectral failed to execute (exit {proc.returncode}): {proc.stderr[-2000:]}")
    try:
        results = _parse_spectral_json(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"spectral produced no parseable JSON on stdout: {exc}; stderr={proc.stderr[-2000:]}")

    records = []
    for res in results:
        code = res.get("code", "unknown-rule")
        sev = _SEVERITY_MAP.get(res.get("severity"), "info")
        range_ = res.get("range", {}) or {}
        start = range_.get("start", {}) or {}
        end = range_.get("end", {}) or {}
        # Spectral's own line numbers are 0-indexed; +1 to match this
        # schema's artifact.line_start/line_end convention (1-indexed, same
        # as every editor/git blame -- audit_pipeline_security.py's checkov
        # adapter follows the same +0/native convention per its own tool's
        # numbering, documented here since Spectral's differs).
        line_start = (start.get("line", 0) or 0) + 1
        line_end = (end.get("line", 0) or 0) + 1
        json_path = "/".join(str(p) for p in res.get("path", []))
        finding_id = _finding_id("spectral", repo_name, code, openapi_path, line_start, json_path)
        records.append({
            "finding_id": finding_id,
            "domain": DOMAIN,
            "standard_cited": STANDARD_CITED,
            "clause_cited": code,
            "artifact": {
                "path": os.path.relpath(openapi_path, start=os.getcwd()) if os.path.isabs(openapi_path) else openapi_path,
                "line_start": line_start, "line_end": line_end, "commit": None,
            },
            "finding": f"spectral rule '{code}' at {json_path or '(document root)'}: {res.get('message', '')}",
            "severity": sev,
            "not_covered_by_standard": False,
            "remediation_type": "software_fixable",
            "status": "open",
            "producer": {"kind": "oss_tool", "name": "spectral", "version": version},
            "repo": repo_name,
            "event_id": None,
            "owner_decision_ref": None,
            "_raw": res,
        })
    return records, version


def upsert_findings(conn, records, run_id):
    # Identical upsert convention to audit_pipeline_security.py's own
    # upsert_findings() -- a triaged status (acknowledged/resolved/wont_fix/
    # false_positive) survives a rerun that re-observes the same finding.
    now = _now_iso()
    new_count = 0
    for r in records:
        art = r["artifact"]
        prod = r["producer"]
        cur = conn.execute("SELECT status, first_seen_ts FROM audit_findings WHERE finding_id = ?", (r["finding_id"],))
        existing = cur.fetchone()
        if existing is None:
            new_count += 1
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
                finding=excluded.finding,
                severity=excluded.severity,
                status=excluded.status,
                detected_at=excluded.detected_at,
                raw_json=excluded.raw_json,
                last_seen_ts=excluded.last_seen_ts,
                run_id=excluded.run_id
        """, (
            r["finding_id"], r["domain"], r["standard_cited"], r["clause_cited"],
            art["path"], art.get("line_start"), art.get("line_end"), art.get("commit"),
            r["finding"], r["severity"], int(r["not_covered_by_standard"]), r["remediation_type"], status,
            prod["kind"], prod["name"], prod.get("version"), now, r["repo"],
            r.get("event_id"), r.get("owner_decision_ref"), json.dumps(r["_raw"], default=str), first_seen, now, run_id,
        ))
    conn.commit()
    return new_count


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    default_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ai-os", "openapi")
    ap.add_argument("--openapi-dir", default=default_dir)
    ap.add_argument("--dry-run", action="store_true", help="run spectral, print summary, do not write to the DB")
    args = ap.parse_args()

    if shutil.which("spectral") is None:
        print(json.dumps({"ok": False, "error": "required scanner binary not on PATH: spectral"}))
        return 2

    openapi_files = sorted(glob.glob(os.path.join(args.openapi_dir, "*.openapi.yaml")))
    if not openapi_files:
        print(json.dumps({"ok": False, "error": f"no *.openapi.yaml documents found under {args.openapi_dir}"}))
        return 2

    run_id = _run_id()
    start = datetime.datetime.now(datetime.timezone.utc)
    tools_run = {}
    all_records = []
    errors = {}
    per_repo_new = {}

    for path in openapi_files:
        filename = os.path.basename(path)
        repo_name = _REPO_BY_FILENAME.get(filename)
        if repo_name is None:
            errors[filename] = f"no repo mapping in _REPO_BY_FILENAME for {filename} -- add one rather than guessing"
            continue
        try:
            records, version = run_spectral(path, repo_name)
            tools_run[filename] = {"repo": repo_name, "version": version, "findings": len(records)}
            all_records.extend(records)
        except Exception as exc:
            errors[filename] = str(exc)

    duration = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()
    status = "ok" if not errors else ("partial" if tools_run else "failed")

    new_count = 0
    if not args.dry_run:
        with _write_lock():
            conn = _connect()
            ensure_tables(conn)
            new_count = upsert_findings(conn, all_records, run_id)
            # One audit_runs row per repo (matches audit_pipeline_security.py's
            # per-repo granularity) rather than one pooled row for all 3 docs.
            for path in openapi_files:
                filename = os.path.basename(path)
                repo_name = _REPO_BY_FILENAME.get(filename)
                if repo_name is None:
                    continue
                repo_records = [r for r in all_records if r["repo"] == repo_name]
                conn.execute("""
                    INSERT INTO audit_runs (run_id, ts, domain, repo, tools_run, tools_skipped,
                                             total_findings, new_findings, duration_s, status, notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    f"{run_id}-{repo_name}", _now_iso(), DOMAIN, repo_name,
                    json.dumps({"spectral": tools_run.get(filename, {})}),
                    json.dumps({k: v for k, v in errors.items() if k == filename}),
                    len(repo_records), sum(1 for r in repo_records), duration, status,
                    None if filename not in errors else errors[filename],
                ))
            conn.commit()
            conn.close()

    summary = {
        "ok": status != "failed",
        "run_id": run_id,
        "domain": DOMAIN,
        "openapi_dir": args.openapi_dir,
        "tools_run": tools_run,
        "tool_errors": errors,
        "total_findings": len(all_records),
        "new_findings": new_count,
        "duration_s": round(duration, 2),
        "status": status,
        "dry_run": args.dry_run,
    }
    print(json.dumps(summary, indent=2))
    return 0 if status != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
