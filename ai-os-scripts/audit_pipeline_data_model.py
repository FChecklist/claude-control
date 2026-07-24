#!/usr/bin/env python3
"""VERIDIAN Auditor Engine -- Phase 3, data-model domain deterministic pipeline.

Standard cited: relational schema design conventions consistent with
ISO/IEC 11179 (metadata registries), applied to VERIDIAN's real Postgres/
Supabase schemas per AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml's own
data-model domain row.

Three real checks, dispatched per repo by which ORM that repo actually uses
(confirmed via package.json read, not assumed -- see the phase plan's own
stack_confirmed_2026-07-24 block):

  1. sqlfluff (Python, oss_tool) -- lints compliance-tracker/drizzle/*.sql
     and projexa/drizzle/*.sql directly, using ai-os/.sqlfluff (postgres
     dialect, layout/capitalisation rule groups excluded -- see that file's
     own header for the real before/after violation counts that motivated
     the exclusion).
  2. rls_presence (custom_script) -- the one custom rule sqlfluff does not
     ship (per the phase plan's own custom_work_required note): for every
     real `CREATE TABLE` in a repo's drizzle/*.sql tree, confirms a matching
     `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` exists somewhere in that
     same tree. VERIDIAN's schemas are RLS-heavy by design (Supabase/
     Postgres backing every exposed table) -- a table with no RLS-enable
     statement anywhere is a real, high-severity finding, not a style
     preference.
  3. prisma validate (oss_tool, via veda-advisors' own @prisma/client CLI)
     -- veda-advisors uses Prisma instead of drizzle (confirmed divergence,
     not an oversight), so it gets schema.prisma structural validation
     instead of sqlfluff/RLS presence (Prisma's own RLS story is different
     from raw Postgres ALTER TABLE statements and out of this phase's scope
     -- prisma validate covers what its own CLI actually checks: schema
     syntax/type validity).

Normalizes into the finding-record schema Phase 0 designed
(ai-os/AUDITOR_ENGINE_FINDING_RECORD_SCHEMA_2026-07-24.schema.json) and
writes into the same shared `audit_findings` table Phase 1/2's pipelines
already own. Zero AI/LLM involvement anywhere in this file.

Usage:
    python3 audit_pipeline_data_model.py [--dry-run]
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

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(_HERE, "..")
SQLFLUFF_CONFIG = os.path.join(REPO_ROOT, "ai-os", ".sqlfluff")
SQLFLUFF_BIN = os.environ.get("AUDIT_SQLFLUFF_BIN", os.path.expanduser("~/.local/bin/sqlfluff"))

DOMAIN = "data-model"
STANDARD_CITED = "Relational schema design conventions consistent with ISO/IEC 11179 (metadata registries)"

# repo -> real drizzle/*.sql directory. Only compliance-tracker and projexa
# use drizzle (confirmed via package.json read, phase plan stack_confirmed
# block) -- veda-advisors uses Prisma and is handled by run_prisma_validate.
_DRIZZLE_REPOS = {
    "compliance-tracker": "/opt/veridian/repos/compliance-tracker",
    "projexa": "/opt/veridian/repos/projexa",
}

_PRISMA_REPOS = {
    "veda-advisors": "/opt/veridian/repos/veda-advisors",
}


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
    # Identical shared-table DDL to audit_pipeline_security.py /
    # audit_pipeline_api_contract.py / audit_pipeline_metadata.py -- one
    # audit_findings/audit_runs table, every domain's pipeline writes into it.
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
    except Exception as exc:
        return f"unknown ({exc})"


_SQLFLUFF_SEVERITY = {
    # sqlfluff itself only has warning=True/False; VERIDIAN's own severity
    # mapping below is deliberate, not sqlfluff-native: PG01 (excessive
    # locks) is a real operational-risk signal on RLS-heavy Supabase
    # migrations (a long lock on a live table), so it's rated higher than
    # pure reference/aliasing style deviations.
    "PG01": "high",
}
_SQLFLUFF_DEFAULT_SEVERITY = "medium"


# ---------------------------------------------------------------------------
# sqlfluff -- structural SQL lint of drizzle/*.sql
# ---------------------------------------------------------------------------

def run_sqlfluff(repo_path, repo_name):
    version = _tool_version([SQLFLUFF_BIN, "--version"])
    drizzle_dir = os.path.join(repo_path, "drizzle")
    sql_files = sorted(glob.glob(os.path.join(drizzle_dir, "*.sql")))
    if not sql_files:
        raise RuntimeError(f"no drizzle/*.sql files found under {drizzle_dir}")

    cmd = [SQLFLUFF_BIN, "lint", "--config", SQLFLUFF_CONFIG, "--format", "json", *sql_files]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    # sqlfluff exits 1 when it finds real violations -- that's data, not a
    # pipeline failure (same convention as checkov's exit 1 in Phase 1).
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"sqlfluff failed to execute (exit {proc.returncode}): {proc.stderr[-2000:]}")
    if not proc.stdout.strip():
        raise RuntimeError(f"sqlfluff produced no output (stderr: {proc.stderr[-1000:]})")
    data = json.loads(proc.stdout)

    records = []
    for file_result in data:
        abs_path = file_result.get("filepath", "")
        rel_path = os.path.relpath(abs_path, repo_path)
        for v in file_result.get("violations", []):
            code = v.get("code", "unknown")
            severity = _SQLFLUFF_SEVERITY.get(code, _SQLFLUFF_DEFAULT_SEVERITY)
            line = v.get("start_line_no")
            finding_id = _finding_id("sqlfluff", repo_name, code, rel_path, line, v.get("start_line_pos"))
            records.append({
                "finding_id": finding_id,
                "domain": DOMAIN,
                "standard_cited": STANDARD_CITED,
                "clause_cited": f"sqlfluff:{code}:{v.get('name', '')}",
                "artifact": {"path": rel_path, "line_start": line, "line_end": v.get("end_line_no"), "commit": None},
                "finding": f"sqlfluff {code} ({v.get('name', '')}): {v.get('description', '')} at {rel_path}:{line}",
                "severity": severity,
                "not_covered_by_standard": False,
                "remediation_type": "software_fixable",
                "status": "open",
                "producer": {"kind": "oss_tool", "name": "sqlfluff", "version": version},
                "repo": repo_name,
                "event_id": None,
                "owner_decision_ref": None,
                "_raw": v,
            })
    return records, version


# ---------------------------------------------------------------------------
# rls_presence -- custom rule: every CREATE TABLE must have a matching
# ALTER TABLE ... ENABLE ROW LEVEL SECURITY somewhere in the same drizzle tree
# ---------------------------------------------------------------------------

_CREATE_TABLE_RE = re.compile(
    r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?'
    r'(?:"?(?P<schema>\w+)"?\.)?"?(?P<table>\w+)"?',
    re.IGNORECASE,
)
_ENABLE_RLS_RE = re.compile(
    r'ALTER\s+TABLE\s+(?:ONLY\s+)?'
    r'(?:"?(?P<schema>\w+)"?\.)?"?(?P<table>\w+)"?\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY',
    re.IGNORECASE,
)
_RLS_TOOL_VERSION = "veridian-custom-rule-1.0"


def run_rls_presence(repo_path, repo_name):
    drizzle_dir = os.path.join(repo_path, "drizzle")
    sql_files = sorted(glob.glob(os.path.join(drizzle_dir, "*.sql")))
    if not sql_files:
        raise RuntimeError(f"no drizzle/*.sql files found under {drizzle_dir}")

    # First pass: collect every real ENABLE ROW LEVEL SECURITY target across
    # the WHOLE tree -- RLS is commonly enabled in a later migration than the
    # one that created the table, so this must not be a single-file check.
    rls_enabled_tables = set()
    for path in sql_files:
        text = open(path, encoding="utf-8", errors="replace").read()
        for m in _ENABLE_RLS_RE.finditer(text):
            schema = (m.group("schema") or "public").lower()
            table = m.group("table").lower()
            rls_enabled_tables.add(f"{schema}.{table}")

    # Second pass: every real CREATE TABLE without a matching entry above is
    # a genuine finding, recorded at the file:line it was actually created.
    records = []
    seen_tables = set()
    for path in sql_files:
        rel_path = os.path.relpath(path, repo_path)
        text = open(path, encoding="utf-8", errors="replace").read()
        for lineno, line in enumerate(text.splitlines(), start=1):
            m = _CREATE_TABLE_RE.search(line)
            if not m:
                continue
            schema = (m.group("schema") or "public").lower()
            table = m.group("table").lower()
            key = f"{schema}.{table}"
            if key in seen_tables:
                continue  # a later migration re-creating/altering the same table name
            seen_tables.add(key)
            if key in rls_enabled_tables:
                continue
            finding_id = _finding_id("rls_presence", repo_name, "RLS-PRESENCE", rel_path, lineno, key)
            records.append({
                "finding_id": finding_id,
                "domain": DOMAIN,
                "standard_cited": STANDARD_CITED,
                "clause_cited": "VERIDIAN-RLS-PRESENCE-001",
                "artifact": {"path": rel_path, "line_start": lineno, "line_end": lineno, "commit": None},
                "finding": f"Table '{key}' is created at {rel_path}:{lineno} but no "
                           f"'ALTER TABLE {key} ENABLE ROW LEVEL SECURITY' statement was found anywhere "
                           f"under {os.path.relpath(drizzle_dir, repo_path)}/ -- VERIDIAN's Postgres/Supabase "
                           f"schemas are RLS-heavy by design; a table with no RLS-enable statement is "
                           f"reachable by any role with schema access with no row-level restriction.",
                "severity": "high",
                "not_covered_by_standard": True,  # sqlfluff/ISO 11179 don't check this -- VERIDIAN's own rule
                "remediation_type": "software_fixable",
                "status": "open",
                "producer": {"kind": "custom_script", "name": "rls_presence_check", "version": _RLS_TOOL_VERSION},
                "repo": repo_name,
                "event_id": None,
                "owner_decision_ref": None,
                "_raw": {"table": key, "created_at": f"{rel_path}:{lineno}", "rls_enabled_tables_seen": sorted(rls_enabled_tables)},
            })
    return records, _RLS_TOOL_VERSION


# ---------------------------------------------------------------------------
# prisma validate -- veda-advisors' own schema.prisma
# ---------------------------------------------------------------------------

def run_prisma_validate(repo_path, repo_name):
    schema_path = os.path.join(repo_path, "prisma", "schema.prisma")
    if not os.path.isfile(schema_path):
        raise RuntimeError(f"no schema.prisma found at {schema_path}")
    rel_schema = os.path.relpath(schema_path, repo_path)

    cmd = ["npx", "--yes", "prisma", "validate", "--schema", schema_path]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=repo_path)
    combined = (proc.stdout or "") + (proc.stderr or "")
    version_line = next((l for l in combined.splitlines() if "prisma" in l.lower() and "loaded" not in l.lower()), "prisma (cli)")
    version = "prisma-cli"

    records = []
    if proc.returncode != 0:
        # A real schema.prisma validation failure -- one finding per run
        # (prisma validate reports one structural error at a time, does not
        # emit a machine-parseable list of independent violations).
        finding_id = _finding_id("prisma-validate", repo_name, "PRISMA-SCHEMA-INVALID", rel_schema, 0, hashlib.sha256(combined.encode()).hexdigest()[:8])
        records.append({
            "finding_id": finding_id,
            "domain": DOMAIN,
            "standard_cited": STANDARD_CITED,
            "clause_cited": "prisma-validate:schema-invalid",
            "artifact": {"path": rel_schema, "line_start": None, "line_end": None, "commit": None},
            "finding": f"prisma validate failed against {rel_schema}: {combined.strip()[-1500:]}",
            "severity": "high",
            "not_covered_by_standard": False,
            "remediation_type": "software_fixable",
            "status": "open",
            "producer": {"kind": "oss_tool", "name": "prisma-validate", "version": version},
            "repo": repo_name,
            "event_id": None,
            "owner_decision_ref": None,
            "_raw": {"stdout": proc.stdout, "stderr": proc.stderr, "returncode": proc.returncode},
        })
    return records, version, combined.strip()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def upsert_findings(conn, records, run_id):
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
                finding=excluded.finding, severity=excluded.severity, status=excluded.status,
                detected_at=excluded.detected_at, raw_json=excluded.raw_json,
                last_seen_ts=excluded.last_seen_ts, run_id=excluded.run_id
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
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if shutil.which("npx") is None:
        print(json.dumps({"ok": False, "error": "required binary not on PATH: npx"}))
        return 2
    if not os.path.isfile(SQLFLUFF_BIN):
        print(json.dumps({"ok": False, "error": f"required binary not found: {SQLFLUFF_BIN}"}))
        return 2

    run_id = _run_id()
    start = datetime.datetime.now(datetime.timezone.utc)
    per_repo_records = {}
    per_repo_tools = {}
    per_repo_errors = {}

    for repo_name, repo_path in _DRIZZLE_REPOS.items():
        records_all = []
        tools_run = {}
        errors = {}
        for check_name, fn in (("sqlfluff", run_sqlfluff), ("rls_presence", run_rls_presence)):
            try:
                records, version = fn(repo_path, repo_name)
                tools_run[check_name] = {"version": version, "findings": len(records)}
                records_all.extend(records)
            except Exception as exc:
                errors[check_name] = str(exc)
        per_repo_records[repo_name] = records_all
        per_repo_tools[repo_name] = tools_run
        per_repo_errors[repo_name] = errors

    for repo_name, repo_path in _PRISMA_REPOS.items():
        records_all = []
        tools_run = {}
        errors = {}
        try:
            records, version, raw_output = run_prisma_validate(repo_path, repo_name)
            tools_run["prisma-validate"] = {"version": version, "findings": len(records), "raw_output": raw_output[:300]}
            records_all.extend(records)
        except Exception as exc:
            errors["prisma-validate"] = str(exc)
        per_repo_records[repo_name] = records_all
        per_repo_tools[repo_name] = tools_run
        per_repo_errors[repo_name] = errors

    duration = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()
    all_records = [r for records in per_repo_records.values() for r in records]
    any_errors = any(per_repo_errors.values())
    any_tools_ran = any(per_repo_tools.values())
    status = "ok" if not any_errors else ("partial" if any_tools_ran else "failed")

    new_count = 0
    if not args.dry_run:
        with _write_lock():
            conn = _connect()
            ensure_tables(conn)
            new_count = upsert_findings(conn, all_records, run_id)
            for repo_name, records in per_repo_records.items():
                repo_status = "ok" if not per_repo_errors[repo_name] else ("partial" if per_repo_tools[repo_name] else "failed")
                conn.execute("""
                    INSERT INTO audit_runs (run_id, ts, domain, repo, tools_run, tools_skipped,
                                             total_findings, new_findings, duration_s, status, notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    f"{run_id}-{repo_name}", _now_iso(), DOMAIN, repo_name,
                    json.dumps(per_repo_tools[repo_name]), json.dumps(per_repo_errors[repo_name]),
                    len(records), sum(1 for r in records), duration, repo_status,
                    None if not per_repo_errors[repo_name] else json.dumps(per_repo_errors[repo_name]),
                ))
            conn.commit()
            conn.close()

    summary = {
        "ok": status != "failed",
        "run_id": run_id,
        "domain": DOMAIN,
        "per_repo_tools_run": per_repo_tools,
        "per_repo_errors": per_repo_errors,
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
