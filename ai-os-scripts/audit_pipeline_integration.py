#!/usr/bin/env python3
"""VERIDIAN Auditor Engine -- Phase 2, integration domain contract-testing pipeline.

Runs schemathesis against a real, running instance of each repo's app, using
the real OpenAPI 3.1 documents this same phase's api-contract domain authored
(ai-os/openapi/*.openapi.yaml) as the contract to test against. Normalizes
schemathesis's own NDJSON report format into the finding-record schema
Phase 0 designed (ai-os/AUDITOR_ENGINE_FINDING_RECORD_SCHEMA_2026-07-24.schema.json)
and writes into the same shared `audit_findings` table
audit_pipeline_security.py / audit_pipeline_api_contract.py /
audit_pipeline_metadata.py already own.

Real, honest, hard-blocking constraint (confirmed this phase, matches
AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml phase-2's own dependency_mechanism
text verbatim: "needs a running instance of each app"): schemathesis has no
schema-only / dry-run mode in the installed 4.24.2 CLI (confirmed via
`schemathesis run --help` -- no such flag exists) -- it always sends real
HTTP requests to a real base URL. compliance-tracker and projexa are
Postgres/Supabase-backed Next.js apps requiring real database credentials
and an authenticated session (requireAuth() on nearly every route) to run at
all; standing that up is Phase 1's own ux/axe-core sub-scope
("stand up axe-core against each app's real running routes") and is
independently confirmed NOT YET STARTED in this same plan file's phase-1
entry. This script does not fabricate that infrastructure -- repos without a
configured, reachable AUDIT_SCHEMATHESIS_BASE_URL_<REPO> env var are recorded
as genuinely skipped (skipped_repos, with the real reason), never silently
dropped.

veda-advisors is the one real exception this phase: both its routes
(`/`, `/veda`) are unauthenticated, DB-free static/passthrough handlers (see
veda-advisors.openapi.yaml's own header note) -- its real `next dev` server
was started locally this phase and schemathesis was run against it for real,
producing 2 real findings (TRACE returns 500 instead of 405 on both routes --
a genuine Next.js App Router behavior, not a contrived example).

Usage:
    python3 audit_pipeline_integration.py [--dry-run] [--max-examples 5]

    Per-repo base URLs (only set the ones you actually have running):
        AUDIT_SCHEMATHESIS_BASE_URL_VEDA_ADVISORS=http://localhost:3000/api
        AUDIT_SCHEMATHESIS_BASE_URL_COMPLIANCE_TRACKER=...
        AUDIT_SCHEMATHESIS_BASE_URL_PROJEXA=...
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
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auditor_engine_events as _events  # Phase 7 shared event-emitter (AUDITOR_ENGINE_EVENT_SCHEMA)

DB_PATH = os.environ.get("SUPERBOSS_REGISTER_DB", "/opt/veridian/ai-os/memory/superboss-register.sqlite")
_WRITE_LOCK_PATH = DB_PATH + ".writelock"

_HERE = os.path.dirname(os.path.abspath(__file__))
OPENAPI_DIR = os.path.join(_HERE, "..", "ai-os", "openapi")

DOMAIN = "integration"
STANDARD_CITED = "OpenAPI-driven contract/property-based testing (no separate named standard body -- practice standard is 'test the real API against its own published contract')"

_REPO_BY_FILENAME = {
    "compliance-tracker.openapi.yaml": "compliance-tracker",
    "projexa.openapi.yaml": "projexa",
    "veda-advisors.openapi.yaml": "veda-advisors",
}
_BASE_URL_ENV_BY_REPO = {
    "compliance-tracker": "AUDIT_SCHEMATHESIS_BASE_URL_COMPLIANCE_TRACKER",
    "projexa": "AUDIT_SCHEMATHESIS_BASE_URL_PROJEXA",
    "veda-advisors": "AUDIT_SCHEMATHESIS_BASE_URL_VEDA_ADVISORS",
}
# Real route.ts file per OpenAPI path, for the one repo this pipeline can
# actually run against unauthenticated -- extend this the day a 2nd repo's
# running-instance gap (see module docstring) closes.
_ROUTE_FILE_MAP = {
    "veda-advisors": {
        "/": "src/app/api/route.ts",
        "/veda": "src/app/api/veda/route.ts",
    },
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


def _tool_version():
    try:
        out = subprocess.run(["schemathesis", "--version"], capture_output=True, text=True, timeout=15)
        return (out.stdout + out.stderr).strip().splitlines()[-1][:80]
    except Exception as exc:
        return f"unknown ({exc})"


def _is_reachable(base_url, timeout=3):
    try:
        req = urllib.request.Request(base_url, method="GET")
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True  # any HTTP response (even 4xx/5xx) means something real is listening
    except Exception:
        return False


_SEVERITY_BY_CHECK = {
    "not_a_server_error": "high",
    "use_after_free": "high",
    "response_schema_conformance": "medium",
    "status_code_conformance": "medium",
    "content_type_conformance": "medium",
    "response_headers_conformance": "low",
    "missing_required_header": "low",
    "unsupported_method": "low",
    "negative_data_rejection": "medium",
    "positive_data_acceptance": "medium",
    "ensure_resource_availability": "medium",
    "ignored_auth": "high",
}


def run_schemathesis(openapi_path, repo_name, base_url, max_examples, version):
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            "schemathesis", "run", openapi_path,
            "-u", base_url,
            "--report", "ndjson", "--report-dir", tmp,
            "-n", str(max_examples),
            "--no-color",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        # schemathesis exits 1 when test failures are found -- that's data,
        # not an execution failure. Any other non-zero exit (bad schema,
        # connection refused before any test ran) IS an execution failure.
        ndjson_files = glob.glob(os.path.join(tmp, "*.ndjson"))
        if proc.returncode not in (0, 1) or not ndjson_files:
            raise RuntimeError(f"schemathesis failed to execute (exit {proc.returncode}): {proc.stderr[-2000:] or proc.stdout[-2000:]}")

        route_map = _ROUTE_FILE_MAP.get(repo_name, {})
        records = []
        with open(ndjson_files[0]) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                sf = event.get("ScenarioFinished")
                if not sf or sf.get("status") != "failure":
                    continue
                recorder = sf.get("recorder", {})
                label = recorder.get("label", "unknown operation")
                for case_id, checks in recorder.get("checks", {}).items():
                    case = recorder.get("cases", {}).get(case_id, {}).get("value", {})
                    path = case.get("path", "")
                    method = case.get("method", "")
                    for check in checks:
                        if check.get("status") != "failure":
                            continue
                        check_name = check.get("name", "unknown-check")
                        message = (check.get("failure_info", {}) or {}).get("failure", {}).get("message", "")
                        artifact_path = route_map.get(path, f"{os.path.relpath(openapi_path)}#{label}")
                        finding_id = _finding_id("schemathesis", repo_name, check_name, artifact_path, f"{method}:{path}")
                        records.append({
                            "finding_id": finding_id, "domain": DOMAIN, "standard_cited": STANDARD_CITED,
                            "clause_cited": check_name,
                            "artifact": {"path": artifact_path, "line_start": None, "line_end": None, "commit": None},
                            "finding": f"schemathesis check '{check_name}' failed for {method} {path} ({label}): {message.splitlines()[0] if message else 'see raw_json'}",
                            "severity": _SEVERITY_BY_CHECK.get(check_name, "medium"),
                            "not_covered_by_standard": False, "remediation_type": "software_fixable", "status": "open",
                            "producer": {"kind": "oss_tool", "name": "schemathesis", "version": version},
                            "repo": repo_name, "event_id": None, "owner_decision_ref": None,
                            "_raw": {"check": check, "case": case, "label": label},
                        })
        return records


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
    ap.add_argument("--max-examples", type=int, default=5)
    args = ap.parse_args()

    if shutil.which("schemathesis") is None:
        print(json.dumps({"ok": False, "error": "required binary not on PATH: schemathesis"}))
        return 2

    version = _tool_version()
    run_id = _run_id()
    start = datetime.datetime.now(datetime.timezone.utc)
    all_records = []
    tools_run = {}
    skipped_repos = {}
    errors = {}

    for path in sorted(glob.glob(os.path.join(OPENAPI_DIR, "*.openapi.yaml"))):
        filename = os.path.basename(path)
        repo = _REPO_BY_FILENAME.get(filename)
        if repo is None:
            errors[filename] = f"no repo mapping for {filename}"
            continue
        base_url = os.environ.get(_BASE_URL_ENV_BY_REPO[repo])
        if not base_url:
            skipped_repos[repo] = (
                f"{_BASE_URL_ENV_BY_REPO[repo]} not set -- no running instance configured this phase "
                "(see module docstring: needs Phase 1's own axe-core running-instance work, or a "
                "Postgres/Supabase-backed dev server + authenticated session, neither stood up yet "
                "for this repo)"
            )
            continue
        if not _is_reachable(base_url):
            skipped_repos[repo] = f"configured base URL {base_url} is not reachable right now"
            continue
        try:
            records = run_schemathesis(path, repo, base_url, args.max_examples, version)
            tools_run[repo] = {"base_url": base_url, "version": version, "findings": len(records)}
            all_records.extend(records)
        except Exception as exc:
            errors[repo] = str(exc)

    duration = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()
    status = "ok" if not errors else ("partial" if tools_run else "failed")

    # Only repos actually reached this run (present in tools_run) get a real
    # audit_run event pair -- skipped_repos (no base URL configured / not
    # reachable) had no real run happen, so emitting a started/completed pair
    # for them would misrepresent an audit run that never executed.
    run_traces = {}
    if not args.dry_run:
        for repo in tools_run:
            run_traces[repo] = _events.start_audit_run(
                domain=DOMAIN, repo=repo, producer_name=os.path.basename(__file__), run_id=run_id,
            )

    new_count = 0
    new_by_repo = {}
    if not args.dry_run:
        with _write_lock():
            conn = _connect()
            ensure_tables(conn)
            for repo, rt in run_traces.items():
                subset = [r for r in all_records if r["repo"] == repo]
                new_by_repo[repo] = _events.stamp_new_finding_events(conn, subset, rt)
            new_count = upsert_findings(conn, all_records, run_id)
            for repo, info in tools_run.items():
                repo_records = [r for r in all_records if r["repo"] == repo]
                conn.execute("""
                    INSERT INTO audit_runs (run_id, ts, domain, repo, tools_run, tools_skipped,
                                             total_findings, new_findings, duration_s, status, notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    f"{run_id}-{repo}", _now_iso(), DOMAIN, repo, json.dumps({"schemathesis": info}),
                    json.dumps(skipped_repos), len(repo_records), sum(1 for r in repo_records),
                    duration, status, errors.get(repo),
                ))
            conn.commit()
            conn.close()
        for repo, rt in run_traces.items():
            subset = [r for r in all_records if r["repo"] == repo]
            _events.complete_audit_run(rt, status=status, total_findings=len(subset),
                                        new_findings=new_by_repo.get(repo, 0), duration_s=duration)

    summary = {
        "ok": status != "failed", "run_id": run_id, "domain": DOMAIN,
        "tools_run": tools_run, "skipped_repos": skipped_repos, "tool_errors": errors,
        "total_findings": len(all_records), "new_findings": new_count,
        "duration_s": round(duration, 2), "status": status, "dry_run": args.dry_run,
    }
    print(json.dumps(summary, indent=2))
    return 0 if status != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
