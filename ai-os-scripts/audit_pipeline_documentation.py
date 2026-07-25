#!/usr/bin/env python3
"""VERIDIAN Auditor Engine -- Phase 3, documentation domain deterministic
lint pipeline.

Standard cited: Diataxis framework (tutorials / how-to guides / reference /
explanation) as the structural standard for documentation quality. Per this
phase's own AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml documentation row, the
full tool_mapping is Vale (prose-style linter) + markdownlint-cli (structural
Markdown lint), but Vale ships zero rules of its own -- it is a rule *engine*,
not a ruleset -- and needs a VERIDIAN-specific style package authored first
(named as this phase's own custom_work_required, explicitly deferred: "lower-
hanging fruit for an earlier phase than Vale"). markdownlint-cli, by
contrast, is real signal with ZERO authoring required -- its own default
ruleset is used here unmodified, a deliberate difference from this phase's
sibling data-model pipeline (which DID author a curated ai-os/.sqlfluff to
exclude pure-formatting noise): the phase plan explicitly names
markdownlint's default ruleset as sufficient for Phase 3, so no VERIDIAN-
specific markdownlint config is authored. The dominant real finding this
produces (MD013 line-length, unwrapped long-paragraph prose in these repos'
many internal working-note .md files) is left as-is rather than suppressed,
matching that explicit no-authoring instruction.

Lints every real *.md file in each of the 3 repos (whole repo tree, not a
sampled subset -- same "every real file" convention as this phase's own
data-model pipeline), excluding build/dependency directories no one
hand-authors docs into. Normalizes into the finding-record schema Phase 0
designed (ai-os/AUDITOR_ENGINE_FINDING_RECORD_SCHEMA_2026-07-24.schema.json)
and writes into the same shared `audit_findings` table Phase 1/2/this
phase's other pipelines already own.

Real tool quirk documented here rather than worked around silently:
markdownlint-cli 0.49.1's `-j`/--json flag writes its JSON report to STDERR
when no `-o`/--output file is given (confirmed by direct reproduction
2026-07-24) -- this script always passes `-o <tempfile>` and reads the file
back, sidestepping stdout/stderr channel ambiguity entirely rather than
guessing which stream to parse.

Zero AI/LLM involvement anywhere in this file.

Usage:
    python3 audit_pipeline_documentation.py [--dry-run]
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

MARKDOWNLINT_BIN = os.environ.get("AUDIT_MARKDOWNLINT_BIN", os.path.expanduser("~/.local/bin/markdownlint"))

DOMAIN = "documentation"
STANDARD_CITED = "Diataxis framework (tutorials / how-to guides / reference / explanation) as the structural standard for documentation quality"

_REPOS = {
    "compliance-tracker": "/opt/veridian/repos/compliance-tracker",
    "projexa": "/opt/veridian/repos/projexa",
    "veda-advisors": "/opt/veridian/repos/veda-advisors",
}

# Directories no one hand-authors documentation into -- excluded so this
# pipeline lints real authored docs, not vendored/build output.
_IGNORE_DIRS = ["node_modules", ".git", ".next", "out", "build", "dist"]

# A handful of markdownlint's default rules speak directly to whether a
# document has the kind of clear single-entry-point structure Diataxis
# itself cares about (one way in, one top-level heading) -- rated higher
# than the rest of the default ruleset's line-level formatting checks.
_STRUCTURAL_RULES = {"MD025", "MD041", "MD001"}
_STRUCTURAL_SEVERITY = "medium"
_DEFAULT_SEVERITY = "low"


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
    # Identical shared-table DDL to this phase's other pipelines -- one
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


def _tool_version(bin_path):
    try:
        out = subprocess.run([bin_path, "--version"], capture_output=True, text=True, timeout=15)
        return (out.stdout + out.stderr).strip().splitlines()[0][:80]
    except Exception as exc:
        return f"unknown ({exc})"


def run_markdownlint(repo_name, repo_path):
    version = _tool_version(MARKDOWNLINT_BIN)
    fd, out_path = tempfile.mkstemp(prefix="mdlint_", suffix=".json")
    os.close(fd)
    try:
        cmd = [MARKDOWNLINT_BIN, "-j", "-o", out_path]
        for d in _IGNORE_DIRS:
            cmd += ["-i", d]
        cmd.append(".")
        # cwd=repo_path so fileName in the report comes back repo-relative,
        # and so -i's directory patterns match this repo's own tree.
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=repo_path)
        # markdownlint-cli exits 1 when it finds real violations -- that's
        # data, not a pipeline failure (same convention as sqlfluff/spectral/
        # eslint in this phase's sibling pipelines). A genuine execution
        # failure (bad flag, crash) exits with a different code and leaves
        # out_path empty/unwritten.
        if proc.returncode not in (0, 1):
            raise RuntimeError(f"markdownlint failed to execute (exit {proc.returncode}): {proc.stderr[-2000:]}")
        with open(out_path, encoding="utf-8") as fh:
            raw = fh.read().strip()
        if not raw:
            raise RuntimeError(f"markdownlint produced no output file content (stderr: {proc.stderr[-1000:]})")
        data = json.loads(raw)
    finally:
        with contextlib.suppress(OSError):
            os.remove(out_path)

    records = []
    for item in data:
        rel_path = item.get("fileName", "")
        rule_names = item.get("ruleNames", []) or ["unknown"]
        primary_rule = rule_names[0]
        line = item.get("lineNumber")
        severity = _STRUCTURAL_SEVERITY if primary_rule in _STRUCTURAL_RULES else _DEFAULT_SEVERITY
        # Some rules (MD060 table-column-style in particular) legitimately
        # fire more than once on the same line with errorContext=None (one
        # violation per misaligned table pipe) -- errorRange + errorDetail
        # together disambiguate those real, distinct violations rather than
        # collapsing them into a single finding (confirmed by direct
        # reproduction 2026-07-24: 302 same-line groups, up to 12 genuinely
        # distinct violations each, differing only in errorRange/errorDetail).
        extra = f"{item.get('errorContext')}:{item.get('errorRange')}:{item.get('errorDetail')}"
        finding_id = _finding_id("markdownlint", repo_name, primary_rule, rel_path, line, extra)
        records.append({
            "finding_id": finding_id,
            "domain": DOMAIN,
            "standard_cited": STANDARD_CITED,
            "clause_cited": f"markdownlint:{'/'.join(rule_names)}",
            "artifact": {"path": rel_path, "line_start": line, "line_end": line, "commit": None},
            "finding": f"markdownlint {primary_rule} ({item.get('ruleDescription', '')}): "
                       f"{item.get('errorDetail') or item.get('errorContext') or ''} at {rel_path}:{line}",
            "severity": severity,
            "not_covered_by_standard": False,
            "remediation_type": "software_fixable",
            "status": "open",
            "producer": {"kind": "oss_tool", "name": "markdownlint-cli", "version": version},
            "repo": repo_name,
            "event_id": None,
            "owner_decision_ref": None,
            "_raw": item,
        })
    return records, version


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

    if not os.path.isfile(MARKDOWNLINT_BIN):
        print(json.dumps({"ok": False, "error": f"required binary not found: {MARKDOWNLINT_BIN}"}))
        return 2

    run_id = _run_id()
    start = datetime.datetime.now(datetime.timezone.utc)
    per_repo_records = {}
    per_repo_tools = {}
    per_repo_errors = {}

    for repo_name, repo_path in _REPOS.items():
        tools_run = {}
        errors = {}
        records = []
        try:
            records, version = run_markdownlint(repo_name, repo_path)
            tools_run["markdownlint"] = {"version": version, "findings": len(records)}
        except Exception as exc:
            errors["markdownlint"] = str(exc)
        per_repo_records[repo_name] = records
        per_repo_tools[repo_name] = tools_run
        per_repo_errors[repo_name] = errors

    duration = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()
    all_records = [r for records in per_repo_records.values() for r in records]
    any_errors = any(per_repo_errors.values())
    any_tools_ran = any(per_repo_tools.values())
    status = "ok" if not any_errors else ("partial" if any_tools_ran else "failed")

    run_traces = {}
    if not args.dry_run:
        for repo_name in per_repo_records:
            run_traces[repo_name] = _events.start_audit_run(
                domain=DOMAIN, repo=repo_name, producer_name=os.path.basename(__file__), run_id=run_id,
            )

    new_count = 0
    new_by_repo = {}
    if not args.dry_run:
        with _write_lock():
            conn = _connect()
            ensure_tables(conn)
            for repo_name, rt in run_traces.items():
                new_by_repo[repo_name] = _events.stamp_new_finding_events(conn, per_repo_records[repo_name], rt)
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
        for repo_name, rt in run_traces.items():
            repo_status = "ok" if not per_repo_errors[repo_name] else ("partial" if per_repo_tools[repo_name] else "failed")
            _events.complete_audit_run(rt, status=repo_status, total_findings=len(per_repo_records[repo_name]),
                                        new_findings=new_by_repo.get(repo_name, 0), duration_s=duration)

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
