#!/usr/bin/env python3
"""VERIDIAN Auditor Engine -- Phase 3, product-quality domain deterministic
lint pipeline.

Standard cited: ISO/IEC 25010:2023 (SQuaRE product quality model). Per this
phase's own AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml product-quality row,
sonar-scanner is the real industry tool but is excluded from this phase
(needs a running SonarQube server -- infra stand-up, not a standalone
binary). ESLint is already a devDependency in all 3 real repos (confirmed
via package.json read) and is the named lower-risk substitute.

Runs ai-os/eslint/ISO25010_QUALITY_RULESET_2026-07-24.mjs -- this phase's own
custom_work_required deliverable, a ruleset mapped explicitly to ISO 25010
maintainability/reliability sub-characteristics rather than generic style --
against each real repo's own `src/lib` tree, using that repo's own installed
`node_modules/.bin/eslint` binary (never a globally-installed one: the
ruleset's parser wiring resolves eslint-config-next/typescript-eslint
relative to the repo being linted, see that file's own header). Normalizes
into the finding-record schema Phase 0 designed
(ai-os/AUDITOR_ENGINE_FINDING_RECORD_SCHEMA_2026-07-24.schema.json) and
writes into the same shared `audit_findings` table Phase 1/2/this-phase's
data-model pipeline already own.

Zero AI/LLM involvement anywhere in this file.

Usage:
    python3 audit_pipeline_product_quality.py [--dry-run]
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auditor_engine_events as _events  # Phase 7 shared event-emitter (AUDITOR_ENGINE_EVENT_SCHEMA)

DB_PATH = os.environ.get("SUPERBOSS_REGISTER_DB", "/opt/veridian/ai-os/memory/superboss-register.sqlite")
_WRITE_LOCK_PATH = DB_PATH + ".writelock"

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(_HERE, "..")
RULESET_PATH = os.path.join(REPO_ROOT, "ai-os", "eslint", "ISO25010_QUALITY_RULESET_2026-07-24.mjs")

DOMAIN = "product-quality"
STANDARD_CITED = "ISO/IEC 25010:2023 (SQuaRE product quality model)"

# repo -> (repo root, lint target relative to repo root). All 3 real repos
# have a src/lib tree (confirmed via direct `find` 2026-07-24).
_REPOS = {
    "compliance-tracker": "/opt/veridian/repos/compliance-tracker",
    "projexa": "/opt/veridian/repos/projexa",
    "veda-advisors": "/opt/veridian/repos/veda-advisors",
}
_LINT_TARGET = "src/lib"

# Maps a ruleId in ISO25010_QUALITY_RULESET_2026-07-24.mjs's own
# ISO25010_RULES block to the specific ISO 25010 sub-characteristic it was
# chosen for (see that file's own section comments) -- used to build
# clause_cited so a finding cites the actual sub-characteristic, not just a
# bare rule name. Any ruleId NOT in this map (i.e. inherited from
# eslint-config-next's own typescript-eslint recommended base, which this
# ruleset deliberately layers on top of rather than replaces) is real signal
# too, but wasn't part of this phase's explicit ISO 25010 mapping work --
# recorded with not_covered_by_standard=True rather than silently folded in.
_RULE_SUBCHARACTERISTIC = {
    "complexity": "maintainability-analysability",
    "max-depth": "maintainability-analysability",
    "max-nested-callbacks": "maintainability-analysability",
    "max-params": "maintainability-analysability",
    "max-lines-per-function": "maintainability-modularity",
    "max-classes-per-file": "maintainability-modularity",
    "@typescript-eslint/no-unused-vars": "maintainability-reusability-modifiability",
    "@typescript-eslint/no-shadow": "maintainability-reusability-modifiability",
    "no-var": "maintainability-reusability-modifiability",
    "prefer-const": "maintainability-reusability-modifiability",
    "no-redeclare": "maintainability-reusability-modifiability",
    "no-empty": "reliability-maturity-fault-tolerance",
    "no-fallthrough": "reliability-maturity-fault-tolerance",
    "no-unreachable": "reliability-maturity-fault-tolerance",
    "no-case-declarations": "reliability-maturity-fault-tolerance",
    "no-unsafe-optional-chaining": "reliability-maturity-fault-tolerance",
    "no-async-promise-executor": "reliability-maturity-fault-tolerance",
    "no-compare-neg-zero": "reliability-maturity-fault-tolerance",
    "no-cond-assign": "reliability-maturity-fault-tolerance",
    "no-constant-condition": "reliability-maturity-fault-tolerance",
    "no-dupe-keys": "reliability-maturity-fault-tolerance",
    "no-dupe-args": "reliability-maturity-fault-tolerance",
    "no-duplicate-case": "reliability-maturity-fault-tolerance",
    "no-func-assign": "reliability-maturity-fault-tolerance",
    "no-import-assign": "reliability-maturity-fault-tolerance",
    "no-self-compare": "reliability-maturity-fault-tolerance",
    "no-unmodified-loop-condition": "reliability-maturity-fault-tolerance",
    "no-ex-assign": "reliability-recoverability",
}

# eslint message.severity: 1=warn, 2=error. This ruleset deliberately chose
# "error" for reliability rules (real fault-tolerance/recoverability risk)
# and "warn" for maintainability rules (more subjective, still real signal)
# -- see ISO25010_QUALITY_RULESET_2026-07-24.mjs's own section comments.
# Reusing that same calibration here rather than inventing a second one.
_ESLINT_SEVERITY_MAP = {2: "high", 1: "medium"}


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
    # Identical shared-table DDL to audit_pipeline_data_model.py /
    # audit_pipeline_api_contract.py / audit_pipeline_security.py -- one
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


def _tool_version(eslint_bin):
    try:
        out = subprocess.run([eslint_bin, "--version"], capture_output=True, text=True, timeout=15)
        return (out.stdout + out.stderr).strip().splitlines()[0][:80]
    except Exception as exc:
        return f"unknown ({exc})"


def run_eslint(repo_name, repo_path):
    eslint_bin = os.path.join(repo_path, "node_modules", ".bin", "eslint")
    if not os.path.isfile(eslint_bin):
        raise RuntimeError(f"no repo-local eslint binary found at {eslint_bin}")
    lint_target_abs = os.path.join(repo_path, _LINT_TARGET)
    if not os.path.isdir(lint_target_abs):
        raise RuntimeError(f"lint target does not exist: {lint_target_abs}")

    version = _tool_version(eslint_bin)
    cmd = [eslint_bin, "--config", RULESET_PATH, "--format", "json", _LINT_TARGET]
    # cwd=repo_path is load-bearing, not incidental: the ruleset resolves
    # eslint-config-next/typescript-eslint via createRequire(process.cwd())
    # so it finds *this* repo's own installed copy (see the ruleset file's
    # own resolution-note comment) -- running from any other cwd would break
    # that resolution or silently pick up the wrong repo's dependencies.
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=repo_path)
    # eslint exits 1 when lint errors are present -- that's data, not a
    # pipeline failure (same convention as sqlfluff/spectral in this phase's
    # sibling pipelines). A genuine execution failure (bad config, missing
    # plugin) exits 2 and produces no parseable JSON on stdout.
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"eslint failed to execute (exit {proc.returncode}): {proc.stderr[-2000:]}")
    if not proc.stdout.strip():
        raise RuntimeError(f"eslint produced no output (stderr: {proc.stderr[-1000:]})")
    data = json.loads(proc.stdout)

    records = []
    for file_result in data:
        abs_path = file_result.get("filePath", "")
        rel_path = os.path.relpath(abs_path, repo_path)
        for m in file_result.get("messages", []):
            rule_id = m.get("ruleId") or "unknown"
            subcharacteristic = _RULE_SUBCHARACTERISTIC.get(rule_id)
            not_covered = subcharacteristic is None
            severity = _ESLINT_SEVERITY_MAP.get(m.get("severity"), "low")
            line = m.get("line")
            finding_id = _finding_id("eslint", repo_name, rule_id, rel_path, line, m.get("column"))
            clause = (
                f"ISO25010:{subcharacteristic}:eslint:{rule_id}"
                if subcharacteristic
                else f"eslint:{rule_id} (not part of this phase's explicit ISO 25010 rule mapping -- "
                     f"inherited from eslint-config-next's typescript-eslint recommended base)"
            )
            records.append({
                "finding_id": finding_id,
                "domain": DOMAIN,
                "standard_cited": STANDARD_CITED,
                "clause_cited": clause,
                "artifact": {"path": rel_path, "line_start": line, "line_end": m.get("endLine", line), "commit": None},
                "finding": f"eslint {rule_id}: {m.get('message', '')} at {rel_path}:{line}",
                "severity": severity,
                "not_covered_by_standard": not_covered,
                "remediation_type": "software_fixable",
                "status": "open",
                "producer": {"kind": "oss_tool", "name": "eslint", "version": version},
                "repo": repo_name,
                "event_id": None,
                "owner_decision_ref": None,
                "_raw": m,
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

    if shutil.which("node") is None:
        print(json.dumps({"ok": False, "error": "required binary not on PATH: node"}))
        return 2
    if not os.path.isfile(RULESET_PATH):
        print(json.dumps({"ok": False, "error": f"required ruleset not found: {RULESET_PATH}"}))
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
            records, version = run_eslint(repo_name, repo_path)
            tools_run["eslint"] = {"version": version, "findings": len(records)}
        except Exception as exc:
            errors["eslint"] = str(exc)
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
