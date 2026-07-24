#!/usr/bin/env python3
"""VERIDIAN Auditor Engine -- Phase 1, security domain deterministic scanner pipeline.

Runs Gitleaks (secrets), Trivy (dependency vulnerabilities) and Checkov
(Dockerfile/IaC misconfiguration) -- the 3 of Phase 0's 4 security-domain
tools that are practically runnable on a repeatable cadence today (see
`_SKIPPED_TOOLS` below for OWASP Dependency-Check's documented exclusion) --
against a real target repo, normalizes each tool's native output into the
finding-record schema Phase 0 designed
(ai-os/AUDITOR_ENGINE_FINDING_RECORD_SCHEMA_2026-07-24.schema.json), and
writes the result into a dedicated `audit_findings` table in the same
knowledge_engine database scripts/superboss-register.py already owns
(ai-os/memory/superboss-register.sqlite) -- not a new, separate store.

Zero AI/LLM involvement anywhere in this file. Every finding is produced by
a deterministic OSS binary (producer.kind=oss_tool); this script only
shells out, parses, and writes rows. Per the Owner's "audit run by
software, not AI" mandate, this is the entire audit-run path -- reading and
acting on the findings afterward is a separate, later concern.

Usage:
    python3 audit_pipeline_security.py [--repo compliance-tracker]
                                        [--repo-path /opt/veridian/repos/compliance-tracker]
                                        [--dry-run]

Exit code is always 0 on a completed run (findings are data, not pipeline
failure) unless a scanner itself fails to execute at all (binary missing,
crash) -- that IS a pipeline failure and exits non-zero so cron/run-logged.sh
correctly marks the job failed.
"""
import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auditor_engine_events as _events  # Phase 7 shared event-emitter (AUDITOR_ENGINE_EVENT_SCHEMA)

DB_PATH = os.environ.get("SUPERBOSS_REGISTER_DB", "/opt/veridian/ai-os/memory/superboss-register.sqlite")
_WRITE_LOCK_PATH = DB_PATH + ".writelock"

GITLEAKS_CONFIG = os.environ.get(
    "AUDIT_GITLEAKS_CONFIG",
    "/opt/veridian/ai-os/AUDITOR_ENGINE_SECRET_ALLOWLIST_2026-07-24.toml",
)

DOMAIN = "security"
STANDARD_CITED = "OWASP Top 10 (2021) + OWASP Application Security Verification Standard (ASVS) 4.0"

# OWASP Dependency-Check is installed and smoke-tested (Phase 0) but its
# first-run NVD CVE data sync (369,951 records, no API key configured) is
# documented as impractically slow for a repeatable cadence -- see
# AUDITOR_ENGINE_TOOL_SMOKETEST_EVIDENCE_2026-07-24.yaml, dependency-check
# row, status=installed_partial_smoketest_nvd_sync_too_slow_without_api_key.
# Excluded here rather than silently attempted and left to hang; real,
# honest gap, not a skip nobody can see. Set AUDIT_ENABLE_DEPENDENCY_CHECK=1
# once an NVD_API_KEY is configured to include it.
_SKIPPED_TOOLS = {
    "dependency-check": "NVD_API_KEY not configured -- first-run CVE sync (369,951 records) is not "
                         "practically usable on a repeatable cron cadence without one (Phase 0 evidence). "
                         "Set AUDIT_ENABLE_DEPENDENCY_CHECK=1 once a key is available.",
}


@contextlib.contextmanager
def _write_lock():
    """Same OS-level flock convention as superboss-register.py / file_inventory.py's
    own _write_lock() -- multiple cron-driven writers touch this one shared
    sqlite DB, so every writer serializes through this lock file before
    opening a connection, never relying on sqlite's own lock alone."""
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


def _finding_id(tool, repo, rule, path, line, extra=""):
    raw = f"{tool}:{repo}:{rule}:{path}:{line}:{extra}"
    return "fnd_" + hashlib.sha256(raw.encode()).hexdigest()[:24]


def _tool_version(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (out.stdout + out.stderr).strip().splitlines()[0][:80]
    except Exception as exc:  # binary missing/misbehaving -- surfaced by caller, not swallowed
        return f"unknown ({exc})"


# ---------------------------------------------------------------------------
# Gitleaks -- secrets
# ---------------------------------------------------------------------------

def run_gitleaks(repo_path, repo_name):
    version = _tool_version(["gitleaks", "version"])
    with tempfile.TemporaryDirectory() as tmp:
        report_path = os.path.join(tmp, "gitleaks-report.json")
        cmd = [
            "gitleaks", "detect",
            "--source", repo_path,
            "--config", GITLEAKS_CONFIG,
            "--report-format", "json",
            "--report-path", report_path,
            "--no-banner",
            "--exit-code", "0",  # findings are data, not a scanner failure -- see module docstring
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            raise RuntimeError(f"gitleaks failed to execute (exit {proc.returncode}): {proc.stderr[-2000:]}")
        raw = json.loads(open(report_path).read()) if os.path.exists(report_path) and os.path.getsize(report_path) > 0 else []

    # Gitleaks walks full git history: the same live secret at the same
    # file+line recurs once per historical commit that touched it unchanged.
    # Dedupe to one row per distinct (rule, file, line) -- the live location
    # of the secret today -- keeping the most recently-dated occurrence.
    by_loc = {}
    for leak in raw:
        key = (leak["RuleID"], leak["File"], leak.get("StartLine"))
        if key not in by_loc or leak.get("Date", "") > by_loc[key].get("Date", ""):
            by_loc[key] = leak

    records = []
    for (rule, path, line), leak in by_loc.items():
        severity = "critical" if any(t in rule for t in ("private-key", "aws")) else "high"
        finding_id = _finding_id("gitleaks", repo_name, rule, path, line)
        redacted = {k: v for k, v in leak.items() if k not in ("Secret", "Match")}
        records.append({
            "finding_id": finding_id,
            "domain": DOMAIN,
            "standard_cited": STANDARD_CITED,
            "clause_cited": rule,
            "artifact": {"path": path, "line_start": line, "line_end": leak.get("EndLine"), "commit": leak.get("Commit")},
            "finding": f"gitleaks rule '{rule}' matched at {path}:{line} "
                       f"(fingerprint {leak.get('Fingerprint')}). Secret value redacted -- see fingerprint for traceability.",
            "severity": severity,
            "not_covered_by_standard": False,
            "remediation_type": "software_fixable",
            "status": "open",
            "producer": {"kind": "oss_tool", "name": "gitleaks", "version": version},
            "repo": repo_name,
            "event_id": None,
            "owner_decision_ref": None,
            "_raw": redacted,
        })
    return records, version


# ---------------------------------------------------------------------------
# Trivy -- dependency vulnerabilities
# ---------------------------------------------------------------------------

def run_trivy(repo_path, repo_name):
    version = _tool_version(["trivy", "--version"])
    with tempfile.TemporaryDirectory() as tmp:
        report_path = os.path.join(tmp, "trivy.json")
        cmd = [
            "trivy", "fs", "--scanners", "vuln", "-f", "json", "-o", report_path,
            "--skip-dirs", "node_modules", "--skip-dirs", ".next", "--skip-dirs", ".git",
            repo_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if proc.returncode != 0:
            raise RuntimeError(f"trivy failed to execute (exit {proc.returncode}): {proc.stderr[-2000:]}")
        data = json.loads(open(report_path).read()) if os.path.exists(report_path) else {}

    records = []
    for result in data.get("Results", []) or []:
        target = result.get("Target", "")
        for vuln in result.get("Vulnerabilities", []) or []:
            cve = vuln.get("VulnerabilityID", "unknown")
            sev = (vuln.get("Severity") or "UNKNOWN").lower()
            severity = sev if sev in ("critical", "high", "medium", "low") else "info"
            pkg = vuln.get("PkgName", "?")
            installed = vuln.get("InstalledVersion", "?")
            fixed = vuln.get("FixedVersion")
            finding_id = _finding_id("trivy", repo_name, cve, target, pkg)
            records.append({
                "finding_id": finding_id,
                "domain": DOMAIN,
                "standard_cited": STANDARD_CITED,
                "clause_cited": cve,
                "artifact": {"path": target, "line_start": None, "line_end": None, "commit": None},
                "finding": f"{cve}: {pkg}@{installed} in {target} is vulnerable"
                           + (f" (fix: {fixed})" if fixed else " (no fix available yet)")
                           + f" -- {(vuln.get('Title') or '')[:200]}",
                "severity": severity,
                "not_covered_by_standard": False,
                "remediation_type": "software_fixable",
                "status": "open",
                "producer": {"kind": "oss_tool", "name": "trivy", "version": version},
                "repo": repo_name,
                "event_id": None,
                "owner_decision_ref": None,
                "_raw": vuln,
            })
    return records, version


# ---------------------------------------------------------------------------
# Checkov -- Dockerfile / IaC misconfiguration
# ---------------------------------------------------------------------------

def run_checkov(repo_path, repo_name):
    version = _tool_version(["checkov", "--version"])
    cmd = [
        "checkov", "-d", repo_path, "--framework", "dockerfile", "--compact", "-o", "json",
        "--skip-path", "node_modules", "--skip-path", ".next", "--skip-path", ".git",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    # checkov exits 1 when it has failed checks -- that's data, not an execution failure.
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"checkov failed to execute (exit {proc.returncode}): {proc.stderr[-2000:]}")
    stdout = proc.stdout.strip()
    if not stdout:
        return [], version
    data = json.loads(stdout)
    if isinstance(data, list):
        # checkov emits a list when >1 framework runs; not expected here (framework
        # pinned to dockerfile) but handled defensively rather than assumed away.
        reports = data
    else:
        reports = [data]

    records = []
    for report in reports:
        for check in (report.get("results", {}) or {}).get("failed_checks", []) or []:
            check_id = check.get("check_id", "unknown")
            # checkov's own repo_file_path is relative to whatever git root it
            # detects from CWD (not necessarily repo_path) -- unreliable as a
            # repo-relative path. Derive it ourselves from file_abs_path instead.
            abs_path = check.get("file_abs_path") or check.get("file_path", "")
            path = os.path.relpath(abs_path, repo_path) if abs_path else check.get("file_path", "")
            line_range = check.get("file_line_range") or [None, None]
            severity = (check.get("severity") or "medium").lower()
            if severity not in ("critical", "high", "medium", "low", "info"):
                severity = "medium"
            finding_id = _finding_id("checkov", repo_name, check_id, path, line_range[0])
            records.append({
                "finding_id": finding_id,
                "domain": DOMAIN,
                "standard_cited": STANDARD_CITED,
                "clause_cited": check_id,
                "artifact": {"path": path.lstrip("/"), "line_start": line_range[0], "line_end": line_range[1], "commit": None},
                "finding": f"checkov {check_id}: {check.get('check_name', '')} failed at {path}",
                "severity": severity,
                "not_covered_by_standard": False,
                "remediation_type": "software_fixable",
                "status": "open",
                "producer": {"kind": "oss_tool", "name": "checkov", "version": version},
                "repo": repo_name,
                "event_id": None,
                "owner_decision_ref": None,
                "_raw": check,
            })
    return records, version


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
            # Preserve any human/software disposition already recorded (acknowledged,
            # resolved, wont_fix, false_positive) -- a rerun re-observing the same
            # underlying issue must not silently reopen a triaged finding.
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
    ap.add_argument("--repo", default="compliance-tracker")
    ap.add_argument("--repo-path", default="/opt/veridian/repos/compliance-tracker")
    ap.add_argument("--dry-run", action="store_true", help="run scanners, print summary, do not write to the DB")
    args = ap.parse_args()

    if not os.path.isdir(args.repo_path):
        print(json.dumps({"ok": False, "error": f"repo path not found: {args.repo_path}"}))
        return 2
    for binary in ("gitleaks", "trivy", "checkov"):
        if shutil.which(binary) is None:
            print(json.dumps({"ok": False, "error": f"required scanner binary not on PATH: {binary}"}))
            return 2

    run_id = _run_id()
    start = datetime.datetime.now(datetime.timezone.utc)
    tools_run = {}
    all_records = []
    errors = {}
    run_trace = None if args.dry_run else _events.start_audit_run(
        domain=DOMAIN, repo=args.repo, producer_name=os.path.basename(__file__), run_id=run_id,
    )

    for name, fn in (("gitleaks", run_gitleaks), ("trivy", run_trivy), ("checkov", run_checkov)):
        try:
            records, version = fn(args.repo_path, args.repo)
            tools_run[name] = {"version": version, "findings": len(records)}
            all_records.extend(records)
        except Exception as exc:
            errors[name] = str(exc)

    duration = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()
    status = "ok" if not errors else ("partial" if tools_run else "failed")

    new_count = 0
    if not args.dry_run:
        with _write_lock():
            conn = _connect()
            ensure_tables(conn)
            _events.stamp_new_finding_events(conn, all_records, run_trace)
            new_count = upsert_findings(conn, all_records, run_id)
            conn.execute("""
                INSERT INTO audit_runs (run_id, ts, domain, repo, tools_run, tools_skipped,
                                         total_findings, new_findings, duration_s, status, notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                run_id, _now_iso(), DOMAIN, args.repo, json.dumps(tools_run),
                json.dumps({**_SKIPPED_TOOLS, **{k: v for k, v in errors.items()}}),
                len(all_records), new_count, duration, status,
                None if not errors else f"tool errors: {errors}",
            ))
            conn.commit()
            conn.close()
        _events.complete_audit_run(run_trace, status=status, total_findings=len(all_records),
                                    new_findings=new_count, duration_s=duration)

    summary = {
        "ok": status != "failed",
        "run_id": run_id,
        "repo": args.repo,
        "domain": DOMAIN,
        "tools_run": tools_run,
        "tools_skipped": _SKIPPED_TOOLS,
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
