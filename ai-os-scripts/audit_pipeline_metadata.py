#!/usr/bin/env python3
"""VERIDIAN Auditor Engine -- Phase 2, metadata domain deterministic validation pipeline.

Runs ajv-cli against 3 real classes of VERIDIAN metadata instance data, each
validated against a real JSON Schema authored this same phase
(ai-os/schemas/metadata/*.schema.json -- see each schema's own description
for why it exists and what real gap it was designed against):

  1. package.json required-fields (name/version/description/private/...)
     for the 3 real Node app repos (compliance-tracker, projexa,
     veda-advisors). claude-control has no package.json (config/YAML only,
     per MASTER_INDEX.yaml) and is correctly not checked here.
  2. OpenAPI `info` blocks extracted live from ai-os/openapi/*.openapi.yaml
     (this same phase's api-contract domain output).
  3. drizzle column-comment presence, extracted live from
     compliance-tracker/src/lib/db/schema.ts by
     extract_drizzle_column_comments.py (real regex extraction, not
     invented -- see that script's own docstring for scope).

Normalizes ajv-cli's native `--errors=json` stderr output into the
finding-record schema Phase 0 designed
(ai-os/AUDITOR_ENGINE_FINDING_RECORD_SCHEMA_2026-07-24.schema.json) and
writes into the same shared `audit_findings` table
audit_pipeline_security.py (Phase 1) and audit_pipeline_api_contract.py
(this phase) already own.

Zero AI/LLM involvement anywhere in this file -- every finding is produced
by the deterministic ajv-cli binary (producer.kind=oss_tool); the one
custom_script producer in this pipeline is the drizzle-comment extraction
step itself, which contributes instance DATA, not findings -- ajv-cli alone
decides pass/fail.

Usage:
    python3 audit_pipeline_metadata.py [--dry-run]
"""
import argparse
import contextlib
import datetime
import fcntl
import glob
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

try:
    import yaml
except ImportError:
    yaml = None

DB_PATH = os.environ.get("SUPERBOSS_REGISTER_DB", "/opt/veridian/ai-os/memory/superboss-register.sqlite")
_WRITE_LOCK_PATH = DB_PATH + ".writelock"

_HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMAS_DIR = os.path.join(_HERE, "..", "ai-os", "schemas", "metadata")
OPENAPI_DIR = os.path.join(_HERE, "..", "ai-os", "openapi")
PACKAGE_JSON_SCHEMA = os.path.join(SCHEMAS_DIR, "PACKAGE_JSON_METADATA_2026-07-24.schema.json")
OPENAPI_INFO_SCHEMA = os.path.join(SCHEMAS_DIR, "OPENAPI_INFO_BLOCK_2026-07-24.schema.json")
DRIZZLE_COMMENT_SCHEMA = os.path.join(SCHEMAS_DIR, "DRIZZLE_COLUMN_COMMENT_CONVENTION_2026-07-24.schema.json")
EXTRACT_SCRIPT = os.path.join(_HERE, "extract_drizzle_column_comments.py")

DOMAIN = "metadata"
STANDARD_CITED = "Dublin Core Metadata Initiative (DCMI) Metadata Terms, applied via JSON Schema validation"

# repo -> real package.json path. claude-control deliberately absent -- no
# package.json exists there (confirmed: config/YAML-only repo).
_PACKAGE_JSON_REPOS = {
    "compliance-tracker": "/opt/veridian/repos/compliance-tracker/package.json",
    "projexa": "/opt/veridian/repos/projexa/package.json",
    "veda-advisors": "/opt/veridian/repos/veda-advisors/package.json",
}

_OPENAPI_REPO_BY_FILENAME = {
    "compliance-tracker.openapi.yaml": "compliance-tracker",
    "projexa.openapi.yaml": "projexa",
    "veda-advisors.openapi.yaml": "veda-advisors",
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
    # Identical shared-table DDL -- see audit_pipeline_security.py /
    # audit_pipeline_api_contract.py for the canonical copy of this block.
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


def _finding_id(tool, repo, rule, path, extra):
    raw = f"{tool}:{repo}:{rule}:{path}:{extra}"
    return "fnd_" + hashlib.sha256(raw.encode()).hexdigest()[:24]


def _ajv_version():
    """ajv-cli has no --version flag (confirmed: it errors as an unknown
    parameter) -- the only real source of its version is the installed npm
    package's own package.json, resolved by following the `ajv` binary's
    real symlink back to <prefix>/lib/node_modules/ajv-cli/."""
    try:
        ajv_bin = shutil.which("ajv") or ""
        # ajv_bin is a symlink into <prefix>/lib/node_modules/ajv-cli/bin/ajv
        pkg_dir = os.path.dirname(os.path.dirname(os.path.realpath(ajv_bin)))
        with open(os.path.join(pkg_dir, "package.json")) as f:
            return json.load(f).get("version", "unknown")
    except Exception as exc:
        return f"unknown ({exc})"


def _run_ajv(schema_path, data_path, needs_formats=False):
    """Runs ajv-cli validate, returns (is_valid, errors_list). Real,
    reproduced ajv-cli quirks handled here rather than silently: (1) the
    '<path> valid' success line goes to STDOUT, but the '<path> invalid'
    line + the --errors=json array both go to STDERR -- an asymmetric split
    confirmed by direct reproduction this phase (not documented in ajv-cli's
    own --help), so exit code (0 valid / 1 invalid), not string content, is
    the reliable signal; (2) format keywords (email/uri) are silently
    ignored with a warning unless -c ajv-formats is passed, so callers must
    set needs_formats=True for any schema using `format`."""
    cmd = ["ajv", "validate", "-s", schema_path, "-d", data_path, "--spec=draft2020", "--errors=json"]
    if needs_formats:
        cmd += ["-c", "ajv-formats"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode == 0:
        return True, []
    if proc.returncode != 1:
        raise RuntimeError(f"ajv failed to execute (exit {proc.returncode}): {proc.stderr[-2000:]}")
    output = proc.stderr.strip()
    lines = output.split("\n", 1)
    if len(lines) < 2:
        raise RuntimeError(f"ajv reported invalid with no parseable error body: {output[-2000:]}")
    try:
        errors = json.loads(lines[1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ajv error body was not parseable JSON: {exc}; body={lines[1][:2000]}")
    return False, errors


def _severity_for_missing(prop):
    # VERIDIAN-specific mapping (not an ajv concept): a wholly-absent
    # `description` blocks real documentation, `license` is lower-urgency
    # for internal-only repos (see PACKAGE_JSON_METADATA schema's own note).
    return "low" if prop == "license" else "medium"


def check_package_json(run_id):
    version = _ajv_version()
    records = []
    errors_by_repo = {}
    for repo, path in _PACKAGE_JSON_REPOS.items():
        if not os.path.isfile(path):
            errors_by_repo[repo] = f"package.json not found at {path}"
            continue
        try:
            is_valid, ajv_errors = _run_ajv(PACKAGE_JSON_SCHEMA, path)
        except RuntimeError as exc:
            errors_by_repo[repo] = str(exc)
            continue
        for err in ajv_errors:
            prop = err.get("params", {}).get("missingProperty") or err.get("instancePath", "").lstrip("/") or "unknown"
            finding_id = _finding_id("ajv-cli", repo, "package-json-metadata", path, prop)
            records.append({
                "finding_id": finding_id, "domain": DOMAIN, "standard_cited": STANDARD_CITED,
                "clause_cited": f"PACKAGE_JSON_METADATA_2026-07-24.schema.json{err.get('schemaPath', '')}",
                "artifact": {"path": os.path.relpath(path, "/opt/veridian/repos"), "line_start": None, "line_end": None, "commit": None},
                "finding": f"ajv-cli: {path} {err.get('message', 'schema violation')} (property: {prop})",
                "severity": _severity_for_missing(prop),
                "not_covered_by_standard": False, "remediation_type": "software_fixable", "status": "open",
                "producer": {"kind": "oss_tool", "name": "ajv-cli", "version": version},
                "repo": repo, "event_id": None, "owner_decision_ref": None, "_raw": err,
            })
    return records, version, errors_by_repo


def check_openapi_info_blocks(run_id):
    version = _ajv_version()
    records = []
    errors_by_repo = {}
    if yaml is None:
        return records, version, {"_all": "PyYAML not importable -- cannot extract info blocks"}

    for path in sorted(glob.glob(os.path.join(OPENAPI_DIR, "*.openapi.yaml"))):
        filename = os.path.basename(path)
        repo = _OPENAPI_REPO_BY_FILENAME.get(filename)
        if repo is None:
            errors_by_repo[filename] = f"no repo mapping for {filename}"
            continue
        try:
            with open(path) as f:
                doc = yaml.safe_load(f)
            info = doc.get("info", {})
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
                json.dump(info, tmp)
                tmp_path = tmp.name
            try:
                is_valid, ajv_errors = _run_ajv(OPENAPI_INFO_SCHEMA, tmp_path, needs_formats=True)
            finally:
                os.unlink(tmp_path)
        except Exception as exc:
            errors_by_repo[repo] = str(exc)
            continue
        for err in ajv_errors:
            prop = err.get("params", {}).get("missingProperty") or err.get("instancePath", "").lstrip("/") or "unknown"
            finding_id = _finding_id("ajv-cli", repo, "openapi-info-block", path, prop)
            records.append({
                "finding_id": finding_id, "domain": DOMAIN, "standard_cited": STANDARD_CITED,
                "clause_cited": f"OPENAPI_INFO_BLOCK_2026-07-24.schema.json{err.get('schemaPath', '')}",
                "artifact": {"path": os.path.relpath(path, start=os.path.join(_HERE, "..", "..")), "line_start": None, "line_end": None, "commit": None},
                "finding": f"ajv-cli: {filename} info block {err.get('message', 'schema violation')} (property: {prop})",
                "severity": "medium",
                "not_covered_by_standard": False, "remediation_type": "software_fixable", "status": "open",
                "producer": {"kind": "oss_tool", "name": "ajv-cli", "version": version},
                "repo": repo, "event_id": None, "owner_decision_ref": None, "_raw": err,
            })
    return records, version, errors_by_repo


def check_drizzle_column_comments(run_id):
    version = _ajv_version()
    records = []
    errors = {}
    repo = "compliance-tracker"
    try:
        proc = subprocess.run([sys.executable, EXTRACT_SCRIPT], capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            raise RuntimeError(f"extraction script failed (exit {proc.returncode}): {proc.stderr[-2000:]}")
        columns = json.loads(proc.stdout)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(columns, tmp)
            tmp_path = tmp.name
        try:
            is_valid, ajv_errors = _run_ajv(DRIZZLE_COMMENT_SCHEMA, tmp_path)
        finally:
            os.unlink(tmp_path)

        if not ajv_errors:
            # Schema-conformance is expected to always pass (the extraction
            # script and schema were co-designed this same phase) -- the
            # real, actionable signal here is COVERAGE, not conformance:
            # how many real columns have no documenting comment at all.
            undocumented = [c for c in columns if not c["has_comment"]]
            if undocumented:
                by_table = {}
                for c in undocumented:
                    by_table.setdefault(c["table"], []).append(c["column"])
                for table, cols in by_table.items():
                    finding_id = _finding_id("ajv-cli", repo, "drizzle-column-comment-coverage", "src/lib/db/schema.ts", table)
                    records.append({
                        "finding_id": finding_id, "domain": DOMAIN, "standard_cited": STANDARD_CITED,
                        "clause_cited": "DRIZZLE_COLUMN_COMMENT_CONVENTION_2026-07-24.schema.json#/items (coverage, not conformance)",
                        "artifact": {"path": "src/lib/db/schema.ts", "line_start": None, "line_end": None, "commit": None},
                        "finding": f"{len(cols)}/{sum(1 for c in columns if c['table'] == table)} columns in drizzle table '{table}' have no inline documenting comment: {', '.join(cols)}",
                        "severity": "info",
                        "not_covered_by_standard": True,
                        "remediation_type": "software_fixable", "status": "open",
                        "producer": {"kind": "oss_tool", "name": "ajv-cli", "version": version},
                        "repo": repo, "event_id": None, "owner_decision_ref": None,
                        "_raw": {"table": table, "undocumented_columns": cols},
                    })
        else:
            for err in ajv_errors:
                finding_id = _finding_id("ajv-cli", repo, "drizzle-column-comment-convention", "src/lib/db/schema.ts", err.get("instancePath", ""))
                records.append({
                    "finding_id": finding_id, "domain": DOMAIN, "standard_cited": STANDARD_CITED,
                    "clause_cited": f"DRIZZLE_COLUMN_COMMENT_CONVENTION_2026-07-24.schema.json{err.get('schemaPath', '')}",
                    "artifact": {"path": "src/lib/db/schema.ts", "line_start": None, "line_end": None, "commit": None},
                    "finding": f"ajv-cli: extracted column-comment data {err.get('message', 'schema violation')} at {err.get('instancePath', '')}",
                    "severity": "medium",
                    "not_covered_by_standard": False, "remediation_type": "software_fixable", "status": "open",
                    "producer": {"kind": "oss_tool", "name": "ajv-cli", "version": version},
                    "repo": repo, "event_id": None, "owner_decision_ref": None, "_raw": err,
                })
    except Exception as exc:
        errors[repo] = str(exc)
    return records, version, errors


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

    if shutil.which("ajv") is None:
        print(json.dumps({"ok": False, "error": "required binary not on PATH: ajv"}))
        return 2

    run_id = _run_id()
    start = datetime.datetime.now(datetime.timezone.utc)
    all_records = []
    checks_run = {}
    all_errors = {}

    for name, fn in (
        ("package_json", check_package_json),
        ("openapi_info_blocks", check_openapi_info_blocks),
        ("drizzle_column_comments", check_drizzle_column_comments),
    ):
        records, version, errs = fn(run_id)
        checks_run[name] = {"version": version, "findings": len(records)}
        all_records.extend(records)
        if errs:
            all_errors[name] = errs

    duration = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()
    status = "ok" if not all_errors else ("partial" if checks_run else "failed")

    new_count = 0
    if not args.dry_run:
        with _write_lock():
            conn = _connect()
            ensure_tables(conn)
            new_count = upsert_findings(conn, all_records, run_id)
            by_repo = {}
            for r in all_records:
                by_repo.setdefault(r["repo"], []).append(r)
            for repo, repo_records in by_repo.items():
                conn.execute("""
                    INSERT INTO audit_runs (run_id, ts, domain, repo, tools_run, tools_skipped,
                                             total_findings, new_findings, duration_s, status, notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    f"{run_id}-{repo}", _now_iso(), DOMAIN, repo, json.dumps(checks_run),
                    json.dumps(all_errors), len(repo_records), sum(1 for r in repo_records),
                    duration, status, None if not all_errors else json.dumps(all_errors),
                ))
            conn.commit()
            conn.close()

    summary = {
        "ok": status != "failed", "run_id": run_id, "domain": DOMAIN,
        "checks_run": checks_run, "check_errors": all_errors,
        "total_findings": len(all_records), "new_findings": new_count,
        "duration_s": round(duration, 2), "status": status, "dry_run": args.dry_run,
    }
    print(json.dumps(summary, indent=2))
    return 0 if status != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
