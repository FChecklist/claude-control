#!/usr/bin/env python3
"""VERIDIAN Auditor Engine -- Phase 4, architecture-judgment domains
deterministic pipeline (ddd, clean-architecture, enterprise-architecture).

Per AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml phases[4]:
  "ddd domain -- dependency-cruiser bounded-context rules
   clean-architecture domain -- dependency-cruiser dependency-rule enforcement
   enterprise-architecture domain -- dependency-cruiser layer rules + AI Review drift-check"

This file covers the 3 dependency-cruiser (software/deterministic) slices.
The enterprise-architecture AI Review drift-check is a separate artifact
(ai-os/ENTERPRISE_ARCHITECTURE_DRIFT_REVIEW_2026-07-24.yaml) -- real judgment
content, not something a lint tool produces, so it is not in this pipeline.

Prerequisite: ai-os/ARCHITECTURE_BOUNDED_CONTEXT_MAP_2026-07-24.yaml (the
bounded-context map + layer-boundary map this same phase authored) is the
real source the 3 rule files under ai-os/dependency-cruiser/ encode -- see
that map file's own header for the live-repo-read method used, and each rule
file's own header comment for why its specific pattern was chosen (including
one real self-correction: enterprise-architecture-layers.config.cjs's first
draft flagged src/lib/openapi/generate.ts importing src/lib/schemas/*.ts as
a "violation", which a live smoke-test this task ran caught as a real
modeling mistake -- schemas/data should be the innermost, freely-importable
ring, not outranked by technology -- fixed before this pipeline was written,
not left in).

dependency-cruiser is not a pre-existing devDependency in any of the 3 real
repos (confirmed via package.json read, phase plan's own tool_mapping note)
-- this pipeline installs it locally into each repo's own node_modules via
`npm install --no-save` (never touches package.json/bun.lock -- node_modules
is gitignored in all 3 repos, zero git-visible footprint in those separate
repos) specifically because dependency-cruiser's own TypeScript-parsing
depends on resolving the `typescript` package from the SAME node_modules
tree it runs in (confirmed via live source read of
dependency-cruiser's own extractGroups/environment-check code this task did
before writing this pipeline) -- running it via a bare `npx --yes
dependency-cruiser` (an isolated npx-cache install with no sibling
`typescript`) silently cruised 0 real files in a live test, a real,
documented gap this pipeline avoids by installing next to each repo's own
already-present `typescript` devDependency instead.

Normalizes into the finding-record schema Phase 0 designed
(ai-os/AUDITOR_ENGINE_FINDING_RECORD_SCHEMA_2026-07-24.schema.json) and
writes into the same shared `audit_findings` table Phase 1/2/3's pipelines
already own. Zero AI/LLM involvement anywhere in this file.

Usage:
    python3 audit_pipeline_architecture.py [--dry-run] [--skip-install]
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
RULES_DIR = os.path.join(REPO_ROOT, "ai-os", "dependency-cruiser")

DEPCRUISE_VERSION = "18.1.0"
STANDARD_CITED = {
    "ddd": "Eric Evans, Domain-Driven Design (2003) + Vaughn Vernon, Implementing Domain-Driven Design (2013)",
    "clean-architecture": "Robert C. Martin, Clean Architecture: A Craftsman's Guide to Software Structure and Design (2017) -- The Dependency Rule",
    "enterprise-architecture": "The Open Group TOGAF 10 Standard",
}

# config filename -> (domain, whether this config's own findings are covered
# by the cited standard's own text, or are a VERIDIAN-specific encoding of
# it). All 3 are real, direct implementations of what the phase plan itself
# names as this phase's scope (not a generic ruleset with some inherited/
# uncovered rules mixed in, unlike Phase 3's eslint pipeline) -- so
# not_covered_by_standard=False for all 3, same treatment sqlfluff got in
# Phase 3's data-model pipeline.
_CONFIGS = {
    "ddd-bounded-context.config.cjs": "ddd",
    "clean-architecture-dependency-rule.config.cjs": "clean-architecture",
    "enterprise-architecture-layers.config.cjs": "enterprise-architecture",
}

_REPOS = {
    "compliance-tracker": "/opt/veridian/repos/compliance-tracker",
    "projexa": "/opt/veridian/repos/projexa",
    "veda-advisors": "/opt/veridian/repos/veda-advisors",
}

_DC_SEVERITY = {"error": "high", "warn": "medium", "info": "low"}


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
    # Identical shared-table DDL to every other domain pipeline (Phase 1/2/3)
    # -- one audit_findings/audit_runs table, every domain writes into it.
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


def _finding_id(domain, repo, rule, from_path, to_path):
    raw = f"depcruise:{domain}:{repo}:{rule}:{from_path}:{to_path}"
    return "fnd_" + hashlib.sha256(raw.encode()).hexdigest()[:24]


def ensure_depcruise_installed(repo_path, skip_install):
    bin_path = os.path.join(repo_path, "node_modules", ".bin", "depcruise")
    if os.path.isfile(bin_path):
        return bin_path
    if skip_install:
        raise RuntimeError(f"dependency-cruiser not installed at {bin_path} and --skip-install passed")
    proc = subprocess.run(
        ["npm", "install", "--no-save", "--silent", f"dependency-cruiser@{DEPCRUISE_VERSION}"],
        cwd=repo_path, capture_output=True, text=True, timeout=300,
    )
    if proc.returncode != 0 or not os.path.isfile(bin_path):
        raise RuntimeError(f"npm install dependency-cruiser@{DEPCRUISE_VERSION} failed in {repo_path}: {proc.stderr[-1500:]}")
    return bin_path


def run_depcruise(bin_path, config_path, repo_path, repo_name, domain):
    cmd = [bin_path, "--config", config_path, "--output-type", "json", "src"]
    proc = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, timeout=300)
    # dependency-cruiser exits non-zero when `error`-severity violations are
    # found -- that's real data, not a pipeline failure (same convention as
    # sqlfluff/checkov's non-zero-on-findings exit code in earlier phases).
    if not proc.stdout.strip():
        raise RuntimeError(f"depcruise produced no output for {repo_name}/{domain} (exit {proc.returncode}): {proc.stderr[-2000:]}")
    data = json.loads(proc.stdout)

    records = []
    for v in data.get("summary", {}).get("violations", []):
        rule_name = v.get("rule", {}).get("name", "unknown")
        dc_severity = v.get("rule", {}).get("severity", "warn")
        severity = _DC_SEVERITY.get(dc_severity, "medium")
        from_path = v.get("from", "")
        to_path = v.get("to", "")
        finding_id = _finding_id(domain, repo_name, rule_name, from_path, to_path)
        records.append({
            "finding_id": finding_id,
            "domain": domain,
            "standard_cited": STANDARD_CITED[domain],
            "clause_cited": f"dependency-cruiser:{rule_name}",
            "artifact": {"path": from_path, "line_start": None, "line_end": None, "commit": None},
            "finding": f"{rule_name}: {from_path} imports {to_path}, violating VERIDIAN's own "
                       f"{domain} boundary rule encoded in {os.path.basename(config_path)} (dependency-cruiser "
                       f"severity={dc_severity}). See ai-os/ARCHITECTURE_BOUNDED_CONTEXT_MAP_2026-07-24.yaml "
                       f"for the boundary this rule encodes.",
            "severity": severity,
            "not_covered_by_standard": False,
            "remediation_type": "software_fixable",
            "status": "open",
            "producer": {"kind": "oss_tool", "name": "dependency-cruiser", "version": DEPCRUISE_VERSION},
            "repo": repo_name,
            "event_id": None,
            "owner_decision_ref": None,
            "_raw": v,
        })
    return records, data.get("summary", {}).get("totalCruised", 0)


def upsert_findings(conn, records, run_id):
    now = _now_iso()
    new_count = 0
    new_finding_ids = set()
    for r in records:
        art = r["artifact"]
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
            art["path"], art.get("line_start"), art.get("line_end"), art.get("commit"),
            r["finding"], r["severity"], int(r["not_covered_by_standard"]), r["remediation_type"], status,
            prod["kind"], prod["name"], prod.get("version"), now, r["repo"],
            r.get("event_id"), r.get("owner_decision_ref"), json.dumps(r["_raw"], default=str), first_seen, now, run_id,
        ))
    conn.commit()
    return new_count, new_finding_ids


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-install", action="store_true", help="fail rather than npm-install dependency-cruiser if missing")
    args = ap.parse_args()

    if shutil.which("npm") is None:
        print(json.dumps({"ok": False, "error": "required binary not on PATH: npm"}))
        return 2
    missing_configs = [c for c in _CONFIGS if not os.path.isfile(os.path.join(RULES_DIR, c))]
    if missing_configs:
        print(json.dumps({"ok": False, "error": f"missing rule config(s): {missing_configs}"}))
        return 2

    run_id = _run_id()
    start = datetime.datetime.now(datetime.timezone.utc)
    per_repo_records = {}
    per_repo_tools = {}
    per_repo_errors = {}

    for repo_name, repo_path in _REPOS.items():
        records_all = []
        tools_run = {}
        errors = {}
        try:
            bin_path = ensure_depcruise_installed(repo_path, args.skip_install)
        except Exception as exc:
            per_repo_records[repo_name] = []
            per_repo_tools[repo_name] = {}
            per_repo_errors[repo_name] = {"install": str(exc)}
            continue

        for config_name, domain in _CONFIGS.items():
            config_path = os.path.join(RULES_DIR, config_name)
            try:
                records, total_cruised = run_depcruise(bin_path, config_path, repo_path, repo_name, domain)
                tools_run[domain] = {"version": DEPCRUISE_VERSION, "findings": len(records), "total_cruised": total_cruised}
                records_all.extend(records)
            except Exception as exc:
                errors[domain] = str(exc)
        per_repo_records[repo_name] = records_all
        per_repo_tools[repo_name] = tools_run
        per_repo_errors[repo_name] = errors

    duration = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()
    all_records = [r for records in per_repo_records.values() for r in records]
    any_errors = any(per_repo_errors.values())
    any_tools_ran = any(per_repo_tools.values())
    status = "ok" if not any_errors else ("partial" if any_tools_ran else "failed")

    # domain=None at the run level: this pipeline fans out across 3 domains
    # (ddd/clean-architecture/enterprise-architecture) per repo -- the event
    # schema's own domain field explicitly allows null "for repo-wide events
    # ... before per-domain fan-out begins", which is exactly this case.
    # Individual finding_emitted events still carry each record's own real
    # per-finding domain (set from r["domain"] inside stamp_new_finding_events).
    run_traces = {}
    if not args.dry_run:
        for repo_name in per_repo_records:
            run_traces[repo_name] = _events.start_audit_run(
                domain=None, repo=repo_name, producer_name=os.path.basename(__file__), run_id=run_id,
            )

    new_count = 0
    new_by_repo = {}
    if not args.dry_run:
        with _write_lock():
            conn = _connect()
            ensure_tables(conn)
            for repo_name, rt in run_traces.items():
                new_by_repo[repo_name] = _events.stamp_new_finding_events(conn, per_repo_records[repo_name], rt)
            new_count, new_finding_ids = upsert_findings(conn, all_records, run_id)
            for repo_name, records in per_repo_records.items():
                repo_status = "ok" if not per_repo_errors[repo_name] else ("partial" if per_repo_tools[repo_name] else "failed")
                for domain in set(_CONFIGS.values()):
                    domain_records = [r for r in records if r["domain"] == domain]
                    domain_new = sum(1 for r in domain_records if r["finding_id"] in new_finding_ids)
                    conn.execute("""
                        INSERT INTO audit_runs (run_id, ts, domain, repo, tools_run, tools_skipped,
                                                 total_findings, new_findings, duration_s, status, notes)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        f"{run_id}-{repo_name}-{domain}", _now_iso(), domain, repo_name,
                        json.dumps({domain: per_repo_tools[repo_name].get(domain, {})}),
                        json.dumps({k: v for k, v in per_repo_errors[repo_name].items() if k in (domain, "install")}),
                        len(domain_records), domain_new, duration, repo_status,
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
        "domains": sorted(set(_CONFIGS.values())),
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
