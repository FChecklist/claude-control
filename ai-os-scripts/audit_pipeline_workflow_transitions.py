#!/usr/bin/env python3
"""VERIDIAN Auditor Engine -- Phase 6, workflow domain deterministic pipeline
(the transition-legality slice; business-logic-correctness judgment is
already covered, separately, by ai-os/WORKFLOW_LOGIC_REVIEW_2026-07-24.yaml,
Phase 5's AI Review -- see this file's own rules config for the exact
non-overlap).

Per AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml phases[6].scope: "workflow
domain -- build the custom status-enum transition-validator script
(software-only slice)". Per that same plan's workflow domain row
(custom_work_required): "a custom script that statically extracts every
status-enum + its real transition call sites (grep for
.update({status:...)) and asserts transitions only ever move through
allowed edges -- deterministic, software-only, VERIDIAN-specific".

This is a real static analyzer, not a fixed finding list: every run reads
the REAL, LIVE compliance-tracker source files named in
ai-os/workflow-transitions/TRANSITION_RULES_2026-07-24.yaml (the
hand-authored rule file encoding which enum/table/allowed-edges/writer this
phase's own live source read discovered -- see that file's own `method`
field), re-locates each writer function by name (not by hardcoded line
number, so a few lines of unrelated drift elsewhere in the file does not
silently invalidate the check), and re-derives live whether that function's
own body still contains a status-write matching the rule file's `to` value
and, if a guard is claimed, whether that guard's literal quoted text is
still actually present in the function body before the write. A writer
whose write has moved/disappeared, whose claimed guard text is no longer
found, or whose guard_style is "none" is a real, live-verified
software_fixable finding -- not a replay of this rule file's own prose.

projexa is confirmed to have zero locally status-bearing workflow tables
(its own schema.ts header states construction-domain data lives entirely in
compliance-tracker) -- this pipeline is compliance-tracker-only, matching
the rule file's own documented scope boundary, not a silent omission.

Normalizes into the finding-record schema Phase 0 designed
(ai-os/AUDITOR_ENGINE_FINDING_RECORD_SCHEMA_2026-07-24.schema.json) and
writes into the same shared `audit_findings` table Phase 1-5's pipelines
already own. Zero AI/LLM involvement anywhere in this file.

Usage:
    python3 audit_pipeline_workflow_transitions.py [--dry-run]
"""
import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auditor_engine_events as _events  # Phase 7 shared event-emitter (AUDITOR_ENGINE_EVENT_SCHEMA)

DB_PATH = os.environ.get("SUPERBOSS_REGISTER_DB", "/opt/veridian/ai-os/memory/superboss-register.sqlite")
_WRITE_LOCK_PATH = DB_PATH + ".writelock"

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(_HERE, "..")
RULES_FILE = os.path.join(REPO_ROOT, "ai-os", "workflow-transitions", "TRANSITION_RULES_2026-07-24.yaml")

DOMAIN = "workflow"
STANDARD_CITED = "OMG BPMN 2.0 (Business Process Model and Notation)"
VALIDATOR_VERSION = "1.0.0"

_REPO_PATHS = {
    "compliance-tracker": "/opt/veridian/repos/compliance-tracker",
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
    # Identical shared-table DDL to every other domain pipeline (Phase 1-5).
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


def _finding_id(enum_id, function_name, to_value, kind):
    raw = f"workflow-transition:{enum_id}:{function_name}:{to_value}:{kind}"
    return "fnd_" + hashlib.sha256(raw.encode()).hexdigest()[:24]


def _find_function_body(source, function_name):
    """Locates `function <name>(` / `async function <name>(` and returns
    (body_text, start_line, end_line) via naive brace-depth counting from
    the matching '{' that opens the function -- adequate for this repo's
    real TS service-file style (no minification, no braces-in-strings
    inside these specific functions, confirmed by this task's own live
    read of every function this rule file references). Returns None if the
    function can no longer be found -- a real, reportable drift signal in
    its own right (handled by the caller, not silently swallowed)."""
    pattern = re.compile(r"(?:export\s+)?(?:async\s+)?function\s+" + re.escape(function_name) + r"\s*\(")
    m = pattern.search(source)
    if not m:
        return None
    # m.end() is right after the parameter list's OPENING '(' -- balance
    # parens (not braces) to find where the parameter list actually ends,
    # since TS parameter type annotations routinely contain their own
    # '{ ... }' object-type braces (e.g. `ctx: { orgId: string }`) that
    # would otherwise be mistaken for the function body's opening brace.
    paren_depth = 1
    j = m.end()
    while j < len(source) and paren_depth > 0:
        if source[j] == "(":
            paren_depth += 1
        elif source[j] == ")":
            paren_depth -= 1
        j += 1
    if paren_depth != 0:
        return None
    brace_start = source.find("{", j)
    if brace_start == -1:
        return None
    depth = 0
    i = brace_start
    while i < len(source):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                body = source[brace_start:i + 1]
                start_line = source.count("\n", 0, m.start()) + 1
                end_line = source.count("\n", 0, i) + 1
                return body, start_line, end_line
        i += 1
    return None


def _write_present(body, to_value):
    """Real extraction (not assumed): does this function body still contain
    a `.set({ ... status: ... })` (UPDATE) or `.values({ ... status: ... })`
    (INSERT, for the one is_create writer, createReverseAuction) call whose
    status target is either the literal `to` value, or (for the one
    caller-supplied-value writer, reviewSubmittal) the dynamic
    `status as ...` cast pattern the rule file itself documents for that
    case."""
    if to_value.startswith("("):
        # documented dynamic-value writer (rule file's own free-text `to`)
        return bool(re.search(r"\.set\(\{[^}]*status:\s*status\s+as\b", body, re.S))
    call_pattern = r'\.(?:set|values)\(\{[^}]*status:\s*["\']' + re.escape(to_value) + r'["\']'
    return bool(re.search(call_pattern, body, re.S))


def evaluate_writer(repo_name, enum_row, writer):
    repo_path = _REPO_PATHS[repo_name]
    file_rel = enum_row["file"]
    file_abs = os.path.join(repo_path, file_rel)
    if not os.path.isfile(file_abs):
        return {"ok": False, "reason": f"source file not found on disk: {file_rel}", "write_confirmed": False}

    with open(file_abs, "r") as f:
        source = f.read()

    located = _find_function_body(source, writer["function"])
    if located is None:
        return {"ok": False, "reason": f"function {writer['function']} not found in {file_rel} (real drift vs this rule file)", "write_confirmed": False}
    body, start_line, end_line = located

    write_confirmed = _write_present(body, str(writer["to"]))
    if not write_confirmed:
        return {
            "ok": False,
            "reason": f"expected status write to {writer['to']!r} no longer found in {writer['function']} (real drift vs this rule file)",
            "write_confirmed": False, "start_line": start_line, "end_line": end_line,
        }

    if writer.get("is_create") or writer.get("error_path"):
        return {"ok": True, "reason": "exempted (create/error_path per rule file)", "write_confirmed": True, "start_line": start_line, "end_line": end_line}

    guard_style = writer.get("guard_style", "none")
    if guard_style == "none":
        return {
            "ok": False,
            "reason": f"no status precondition guard in {writer['function']} before writing status={writer['to']!r} "
                      f"-- reachable from any current status, not just {writer.get('required_from')}",
            "write_confirmed": True, "start_line": start_line, "end_line": end_line,
        }

    guard_quote = writer.get("guard_quote", "")
    guard_found = guard_quote and guard_quote in body
    if not guard_found:
        return {
            "ok": False,
            "reason": f"claimed guard text no longer found live in {writer['function']} "
                      f"(rule file's own guard_quote is stale -- real drift, re-author this rule): {guard_quote!r}",
            "write_confirmed": True, "start_line": start_line, "end_line": end_line,
        }

    return {"ok": True, "reason": f"guard confirmed live ({guard_style})", "write_confirmed": True, "start_line": start_line, "end_line": end_line}


def _severity_for(writer, result):
    if not result["write_confirmed"]:
        return "medium"  # rule/code drift -- needs a human to re-author the rule, not urgent but real
    if writer["function"] == "verifyPunchListItemClosed":
        return "medium"  # comment-vs-code mismatch on a self-approval-guarded control, highest-value finding
    return "low"


def build_records(rules):
    now = _now_iso()
    records = []
    stats = {"writers_evaluated": 0, "writers_passed": 0, "writers_flagged": 0, "writers_exempted": 0}
    for enum_row in rules["enums"]:
        for writer in enum_row["writers"]:
            stats["writers_evaluated"] += 1
            result = evaluate_writer("compliance-tracker", enum_row, writer)
            if result["ok"]:
                if writer.get("is_create") or writer.get("error_path"):
                    stats["writers_exempted"] += 1
                else:
                    stats["writers_passed"] += 1
                continue
            stats["writers_flagged"] += 1
            kind = "no_write_found" if not result["write_confirmed"] else "no_transition_guard"
            severity = _severity_for(writer, result)
            records.append({
                "finding_id": _finding_id(enum_row["id"], writer["function"], str(writer["to"]), kind),
                "domain": DOMAIN,
                "standard_cited": STANDARD_CITED,
                "clause_cited": f"transition-legality:{enum_row['id']}:{writer['function']}->{writer['to']}",
                "artifact_path": f"{enum_row['file']} ({writer['function']}, ~line {result.get('start_line', writer.get('write_line'))})",
                "artifact_line_start": result.get("start_line"), "artifact_line_end": result.get("end_line"),
                "finding": f"{enum_row['id']}.{enum_row['column']}: {writer['function']} -- {result['reason']}. "
                           f"See ai-os/workflow-transitions/TRANSITION_RULES_2026-07-24.yaml for this enum's full "
                           f"allowed-edges graph and rationale.",
                "severity": severity,
                "not_covered_by_standard": False,
                "remediation_type": "software_fixable",
                "status": "open",
                "producer": {"kind": "custom_script", "name": "veridian-workflow-transition-validator", "version": VALIDATOR_VERSION},
                "repo": "compliance-tracker",
                "_raw": {"enum": enum_row["id"], "writer": writer, "result": result},
            })
    return records, stats, now


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
            r["artifact_path"], r.get("artifact_line_start"), r.get("artifact_line_end"), None,
            r["finding"], r["severity"], int(r["not_covered_by_standard"]), r["remediation_type"], status,
            prod["kind"], prod["name"], prod.get("version"), now, r["repo"],
            None, None, json.dumps(r["_raw"], default=str), first_seen, now, run_id,
        ))
    conn.commit()
    return new_count, new_finding_ids


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(RULES_FILE):
        print(json.dumps({"ok": False, "error": f"missing rules file: {RULES_FILE}"}))
        return 2

    with open(RULES_FILE) as f:
        rules = yaml.safe_load(f)

    start = datetime.datetime.now(datetime.timezone.utc)
    run_id = _run_id()
    records, stats, _now = build_records(rules)
    duration = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()

    new_count = 0
    run_trace = None if args.dry_run else _events.start_audit_run(
        domain=DOMAIN, repo="compliance-tracker", producer_name=os.path.basename(__file__), run_id=run_id,
    )
    if not args.dry_run:
        with _write_lock():
            conn = _connect()
            ensure_tables(conn)
            _events.stamp_new_finding_events(conn, records, run_trace)
            new_count, new_finding_ids = upsert_findings(conn, records, run_id)
            conn.execute("""
                INSERT INTO audit_runs (run_id, ts, domain, repo, tools_run, tools_skipped,
                                         total_findings, new_findings, duration_s, status, notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                run_id, _now_iso(), DOMAIN, "compliance-tracker",
                json.dumps({"veridian-workflow-transition-validator": {"version": VALIDATOR_VERSION, **stats}}),
                json.dumps({}),
                len(records), new_count, duration, "ok", None,
            ))
            conn.commit()
            conn.close()
        _events.complete_audit_run(run_trace, status="ok", total_findings=len(records),
                                    new_findings=new_count, duration_s=duration)

    summary = {
        "ok": True, "run_id": run_id, "domain": DOMAIN,
        "stats": stats, "total_findings": len(records), "new_findings": new_count,
        "duration_s": round(duration, 2), "dry_run": args.dry_run,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
