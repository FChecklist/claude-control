#!/usr/bin/env python3
"""VERIDIAN Auditor Engine -- Phase 7, shared event-emitter library.

The single, shared implementation of
ai-os/AUDITOR_ENGINE_EVENT_SCHEMA_2026-07-24.schema.json (Phase 0's design
artifact -- PART6's "one event schema"). Every audit_pipeline_*.py script
built in Phases 1-6 imports THIS module rather than re-inventing its own
event emission -- none of them did before this phase (confirmed by grep:
zero shared library existed, each script only shared the write-lock/upsert
*pattern* by copy-paste, not actual code).

What this module does, concretely:
  1. Validates every event it builds against the real schema file (via the
     `jsonschema` package, already present in this environment) before it
     is ever persisted -- a malformed event raises, it is never silently
     written.
  2. Persists every event into a new, append-only `audit_events` table in
     the same knowledge_engine database every pipeline already writes
     audit_findings/audit_runs into (ai-os/memory/superboss-register.sqlite)
     -- this table IS the literal "event stream" Phase 8's own
     dependency_mechanism note says the master report software will query.
  3. Opens a real OpenTelemetry span per audit-run (and a child span per
     newly-emitted finding) using the OTel Python SDK, installed this phase
     into ~/.local/share/veridian-tool-venvs/otel (same user-local venv
     convention Phase 0 used for checkov/sqlfluff/dependency-check) --
     appended to sys.path here so pipeline scripts invoked via the system
     python3 (no venv activation) can still `import auditor_engine_events`
     and get real spans, not just event rows.
  4. Exports those spans via OTLP/HTTP to whatever `AUDIT_OTEL_EXPORTER_ENDPOINT`
     names. No OTel Collector process was stood up this phase (see this
     phase's own known_gaps: doing so would be an always-on network
     listener, the same risk category this session's precedent
     (OWNER_DECISIONS_NEEDED_2026-07-23.yaml#webhook-receiver-network-exposure)
     already flagged as needing Owner sign-off, not assumed) -- so by
     default (`AUDIT_OTEL_EXPORTER_ENDPOINT` unset) spans export to a real,
     local, append-only JSONL file exporter instead
     (ai-os/logs/otel-spans-auditor-engine.jsonl) so every span is still
     genuinely captured and inspectable, just not yet centrally collected.
     The moment an Owner-approved collector endpoint exists, setting that
     one env var switches every pipeline to real OTLP export with no code
     change.

Zero AI/LLM involvement anywhere in this file, consistent with every other
audit-run script in this engine.
"""
import contextlib
import datetime
import fcntl
import json
import os
import secrets
import sqlite3
import sys

DB_PATH = os.environ.get("SUPERBOSS_REGISTER_DB", "/opt/veridian/ai-os/memory/superboss-register.sqlite")
_WRITE_LOCK_PATH = DB_PATH + ".writelock"

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.join(_HERE, "..")
EVENT_SCHEMA_PATH = os.path.join(_REPO_ROOT, "ai-os", "AUDITOR_ENGINE_EVENT_SCHEMA_2026-07-24.schema.json")
SCHEMA_VERSION = "2026-07-24.0"

_SPANS_JSONL_PATH = os.environ.get(
    "AUDIT_OTEL_SPANS_FILE",
    "/opt/veridian/ai-os/logs/otel-spans-auditor-engine.jsonl",
)
_OTLP_ENDPOINT = os.environ.get("AUDIT_OTEL_EXPORTER_ENDPOINT")  # e.g. http://127.0.0.1:4318/v1/traces once approved

# ---------------------------------------------------------------------------
# jsonschema validation -- real, not hand-rolled (confirmed installed this
# phase: `python3 -c "import jsonschema"` -> 4.10.3, no new dependency needed)
# ---------------------------------------------------------------------------
try:
    import jsonschema as _jsonschema
    _JSONSCHEMA_AVAILABLE = True
except ImportError:  # pragma: no cover -- environment regression, not expected
    _JSONSCHEMA_AVAILABLE = False

with open(EVENT_SCHEMA_PATH) as _f:
    _EVENT_SCHEMA = json.load(_f)


def validate_event(event):
    """Raises jsonschema.ValidationError (or a plain AssertionError if the
    jsonschema package somehow became unavailable) on any schema violation.
    Never called with a silent bypass -- every emit_* function below calls
    this before persisting."""
    if _JSONSCHEMA_AVAILABLE:
        _jsonschema.validate(instance=event, schema=_EVENT_SCHEMA)
    else:  # pragma: no cover
        assert event.get("schema_version") == SCHEMA_VERSION, "event missing/wrong schema_version"
        for req in _EVENT_SCHEMA["required"]:
            assert req in event, f"event missing required field: {req}"


# ---------------------------------------------------------------------------
# OpenTelemetry wiring -- real SDK, venv-sourced, graceful no-op fallback
# ---------------------------------------------------------------------------
_OTEL_VENV = os.path.expanduser("~/.local/share/veridian-tool-venvs/otel")
_otel_status = "not_attempted"
_tracer = None


def _find_venv_site_packages(venv_root):
    lib_dir = os.path.join(venv_root, "lib")
    if not os.path.isdir(lib_dir):
        return None
    for name in sorted(os.listdir(lib_dir)):
        candidate = os.path.join(lib_dir, name, "site-packages")
        if os.path.isdir(candidate):
            return candidate
    return None


def _init_otel():
    """Idempotent -- safe to call from every emit_* entrypoint. Sets module
    globals _tracer + _otel_status rather than raising, since a real OTel
    export failure must never take down an audit-run pipeline (findings are
    the primary deliverable; tracing is observability on top)."""
    global _tracer, _otel_status
    if _otel_status != "not_attempted":
        return
    site_packages = _find_venv_site_packages(_OTEL_VENV)
    if site_packages and site_packages not in sys.path:
        sys.path.insert(0, site_packages)
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SpanExporter, SpanExportResult
        from opentelemetry.sdk.resources import Resource

        if _OTLP_ENDPOINT:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=_OTLP_ENDPOINT)
            _otel_status = f"exporting_otlp:{_OTLP_ENDPOINT}"
        else:
            exporter = _JsonlFileSpanExporter(_SPANS_JSONL_PATH)
            _otel_status = f"exporting_local_jsonl:{_SPANS_JSONL_PATH}"

        provider = TracerProvider(resource=Resource.create({"service.name": "veridian-auditor-engine"}))
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("veridian.auditor_engine")
    except Exception as exc:  # opentelemetry not importable, or exporter init failed -- honest no-op, not a crash
        _tracer = None
        _otel_status = f"unavailable:{exc}"


class _JsonlFileSpanExporter:
    """Minimal SpanExporter (duck-typed to the OTel SDK's SpanExporter
    interface) that appends each finished span as one JSON line -- used as
    the default, zero-network-exposure sink until an Owner-approved OTel
    Collector endpoint exists (see module docstring)."""

    def __init__(self, path):
        self._path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def export(self, spans):
        from opentelemetry.sdk.trace.export import SpanExportResult
        try:
            with open(self._path, "a") as f:
                for span in spans:
                    ctx = span.get_span_context()
                    parent = span.parent
                    f.write(json.dumps({
                        "name": span.name,
                        "trace_id": format(ctx.trace_id, "032x"),
                        "span_id": format(ctx.span_id, "016x"),
                        "parent_span_id": format(parent.span_id, "016x") if parent else None,
                        "start_time": span.start_time,
                        "end_time": span.end_time,
                        "attributes": dict(span.attributes or {}),
                        "status": span.status.status_code.name,
                    }) + "\n")
            return SpanExportResult.SUCCESS
        except Exception:
            return SpanExportResult.FAILURE

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        return True


def otel_status():
    _init_otel()
    return _otel_status


@contextlib.contextmanager
def _otel_span(name, attributes, trace_id_hex=None, parent_span_id_hex=None):
    """Yields (trace_id_hex, span_id_hex) for the span (real ones if OTel is
    wired, deterministically-shaped random ones if not) -- callers use these
    to populate the event schema's own `trace` object either way, since the
    schema's trace_id/span_id fields are required regardless of whether a
    real OTel SDK is present.

    When trace_id_hex/parent_span_id_hex are given, the new span is created
    as a REAL child of that (trace_id, span_id) pair via a reconstructed
    OTel SpanContext -- not just a same-named-but-disconnected root span.
    Without this, start_as_current_span() with no ambient context starts a
    brand-new trace every call (confirmed by this module's own self-test
    before this fix: 3 calls in one run produced 3 different trace_ids in
    the exported spans, even though the sqlite audit_events rows looked
    correctly linked because those hardcode run_trace.trace_id directly).
    """
    _init_otel()
    if _tracer is not None:
        from opentelemetry.trace import SpanContext, NonRecordingSpan, TraceFlags, set_span_in_context
        ctx = None
        if trace_id_hex and parent_span_id_hex:
            parent_ctx = SpanContext(
                trace_id=int(trace_id_hex, 16),
                span_id=int(parent_span_id_hex, 16),
                is_remote=True,
                trace_flags=TraceFlags(TraceFlags.SAMPLED),
            )
            ctx = set_span_in_context(NonRecordingSpan(parent_ctx))
        with _tracer.start_as_current_span(name, context=ctx, attributes=attributes) as span:
            sctx = span.get_span_context()
            yield format(sctx.trace_id, "032x"), format(sctx.span_id, "016x")
    else:
        # No SDK available -- still hand back schema-conformant hex ids so
        # every event this library emits has a real, correctly-shaped trace
        # object; just not exported/collected anywhere.
        yield (trace_id_hex or secrets.token_hex(16)), secrets.token_hex(8)


# ---------------------------------------------------------------------------
# ID generation (schema-conformant shapes)
# ---------------------------------------------------------------------------

def _new_event_id():
    return "evt_" + secrets.token_hex(12)


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Persistence -- audit_events table, same write-lock/WAL convention every
# audit_pipeline_*.py script already uses for audit_findings/audit_runs.
# ---------------------------------------------------------------------------

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


def ensure_events_table(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS audit_events (
        event_id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        schema_version TEXT NOT NULL,
        repo TEXT NOT NULL,
        domain TEXT,
        ts TEXT NOT NULL,
        producer_kind TEXT NOT NULL,
        producer_name TEXT NOT NULL,
        producer_version TEXT,
        trace_id TEXT NOT NULL,
        span_id TEXT NOT NULL,
        parent_span_id TEXT,
        finding_id TEXT,
        pgaudit_statement_id TEXT,
        severity TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        run_id TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_audit_events_trace ON audit_events(trace_id);
    CREATE INDEX IF NOT EXISTS idx_audit_events_repo_domain ON audit_events(repo, domain);
    CREATE INDEX IF NOT EXISTS idx_audit_events_finding ON audit_events(finding_id);
    CREATE INDEX IF NOT EXISTS idx_audit_events_run ON audit_events(run_id);
    """)
    conn.commit()


def _persist_event(event, conn=None):
    validate_event(event)
    trace = event["trace"]
    producer = event["producer"]
    row = (
        event["event_id"], event["event_type"], event["schema_version"], event["repo"],
        event.get("domain"), event["timestamp"], producer["kind"], producer["name"],
        producer.get("version"), trace["trace_id"], trace["span_id"], trace.get("parent_span_id"),
        event.get("finding_id"), event.get("pgaudit_statement_id"), event.get("severity"),
        json.dumps(event.get("metadata", {}), default=str), event.get("metadata", {}).get("run_id"),
    )
    sql = """INSERT OR IGNORE INTO audit_events (
        event_id, event_type, schema_version, repo, domain, ts, producer_kind, producer_name,
        producer_version, trace_id, span_id, parent_span_id, finding_id, pgaudit_statement_id,
        severity, metadata_json, run_id
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    if conn is not None:
        ensure_events_table(conn)
        conn.execute(sql, row)
        conn.commit()
    else:
        with _write_lock():
            c = _connect()
            ensure_events_table(c)
            c.execute(sql, row)
            c.commit()
            c.close()
    return event["event_id"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class AuditRunTrace:
    """Correlation handle threaded through one pipeline run: the trace_id is
    shared by every event the run emits (audit_run_started/*/finding_emitted/
    audit_run_completed), the root span_id becomes each finding event's
    parent_span_id -- real W3C-Trace-Context-shaped parent/child linkage,
    not just a shared run_id string."""

    __slots__ = ("trace_id", "root_span_id", "domain", "repo", "producer_name", "producer_version", "run_id")

    def __init__(self, trace_id, root_span_id, domain, repo, producer_name, producer_version, run_id):
        self.trace_id = trace_id
        self.root_span_id = root_span_id
        self.domain = domain
        self.repo = repo
        self.producer_name = producer_name
        self.producer_version = producer_version
        self.run_id = run_id


def start_audit_run(domain, repo, producer_name, producer_version=None, run_id=None, metadata=None):
    """Call once near the top of a pipeline's main(), before its scanners
    run. Emits `audit_run_started`, self-manages its own DB connection/lock
    (there is nothing else holding the lock at this point in any of the 10
    pipeline scripts -- confirmed by reading each one's main())."""
    attrs = {"repo": repo, "domain": domain or "", "producer.name": producer_name, "run_id": run_id or ""}
    with _otel_span(f"audit_run:{domain}:{repo}", attrs) as (trace_id, span_id):
        event = {
            "event_id": _new_event_id(),
            "event_type": "audit_run_started",
            "schema_version": SCHEMA_VERSION,
            "repo": repo,
            "domain": domain,
            "timestamp": _now_iso(),
            "producer": {"kind": "orchestrator", "name": producer_name, "version": producer_version},
            "trace": {"trace_id": trace_id, "span_id": span_id, "parent_span_id": None},
            "metadata": {**(metadata or {}), "run_id": run_id},
        }
        _persist_event(event)
    return AuditRunTrace(trace_id, span_id, domain, repo, producer_name, producer_version, run_id)


def emit_finding(run_trace, finding_id, domain, repo, severity, producer_kind, producer_name,
                  producer_version=None, conn=None):
    """Emits one `finding_emitted` event as a child of the run's root span.
    Callers MUST only call this for genuinely NEW findings (see
    stamp_new_finding_events below) -- a rerun that re-observes an unchanged
    finding must not re-emit an event for it, matching every pipeline's own
    idempotent-upsert convention."""
    attrs = {"finding_id": finding_id, "domain": domain, "repo": repo, "severity": severity or ""}
    with _otel_span(f"finding_emitted:{finding_id}", attrs,
                     trace_id_hex=run_trace.trace_id, parent_span_id_hex=run_trace.root_span_id) as (trace_id, span_id):
        event = {
            "event_id": _new_event_id(),
            "event_type": "finding_emitted",
            "schema_version": SCHEMA_VERSION,
            "repo": repo,
            "domain": domain,
            "timestamp": _now_iso(),
            "producer": {"kind": producer_kind, "name": producer_name, "version": producer_version},
            "trace": {"trace_id": run_trace.trace_id, "span_id": span_id, "parent_span_id": run_trace.root_span_id},
            "finding_id": finding_id,
            "severity": severity,
            "metadata": {"run_id": run_trace.run_id},
        }
        event_id = _persist_event(event, conn=conn)
    return event_id


def stamp_new_finding_events(conn, records, run_trace):
    """The one call every audit_pipeline_*.py script's main() adds, right
    after ensure_tables(conn) and BEFORE upsert_findings(conn, records, ...).
    Mutates `records` in place:
      - finding_id already present in audit_findings -> preserves its
        existing event_id (idempotent rerun, no duplicate event).
      - finding_id not yet present -> emits a real finding_emitted event and
        sets record["event_id"] to the new event's id, so the upsert that
        follows writes a real, non-null event_id into audit_findings for
        every genuinely new finding.
    Returns the count of genuinely-new records (for logging only -- each
    pipeline's own upsert_findings remains the authoritative new_findings
    count already written into audit_runs)."""
    ids = [r["finding_id"] for r in records]
    existing = {}
    if ids:
        placeholders = ",".join("?" * len(ids))
        for row in conn.execute(
            f"SELECT finding_id, event_id FROM audit_findings WHERE finding_id IN ({placeholders})", ids
        ):
            existing[row["finding_id"]] = row["event_id"]
    new_count = 0
    for r in records:
        if r["finding_id"] in existing:
            r["event_id"] = existing[r["finding_id"]]
        else:
            new_count += 1
            prod = r["producer"]
            r["event_id"] = emit_finding(
                run_trace, finding_id=r["finding_id"], domain=r["domain"], repo=r["repo"],
                severity=r.get("severity"), producer_kind=prod["kind"], producer_name=prod["name"],
                producer_version=prod.get("version"), conn=conn,
            )
    return new_count


def complete_audit_run(run_trace, status, total_findings, new_findings, duration_s, notes=None):
    """Call once at the very end of a pipeline's main(), after its
    write-lock persistence block has already closed. Emits
    `audit_run_completed` (status in {ok,partial}) or `audit_run_failed`
    (status == failed)."""
    event_type = "audit_run_failed" if status == "failed" else "audit_run_completed"
    attrs = {"repo": run_trace.repo, "domain": run_trace.domain or "", "status": status}
    with _otel_span(f"{event_type}:{run_trace.domain}:{run_trace.repo}", attrs,
                     trace_id_hex=run_trace.trace_id, parent_span_id_hex=run_trace.root_span_id) as (trace_id, span_id):
        event = {
            "event_id": _new_event_id(),
            "event_type": event_type,
            "schema_version": SCHEMA_VERSION,
            "repo": run_trace.repo,
            "domain": run_trace.domain,
            "timestamp": _now_iso(),
            "producer": {"kind": "orchestrator", "name": run_trace.producer_name, "version": run_trace.producer_version},
            "trace": {"trace_id": run_trace.trace_id, "span_id": span_id, "parent_span_id": run_trace.root_span_id},
            "metadata": {
                "run_id": run_trace.run_id, "total_findings": total_findings,
                "new_findings": new_findings, "duration_s": duration_s, "notes": notes,
            },
        }
        _persist_event(event)


# ---------------------------------------------------------------------------
# Self-test -- real end-to-end smoke test, not a mock. Emits a synthetic
# observability-layer-self-check run through the exact same code path every
# real pipeline uses, validates every event against the real schema file,
# and reports whether OTel export is wired to a collector or the local
# JSONL fallback.
# ---------------------------------------------------------------------------

def _self_test():
    run_trace = start_audit_run(
        domain="observability-layer-self-check", repo="claude-control",
        producer_name="auditor_engine_events.py", producer_version="2026-07-24", run_id="SELFTEST-0",
    )
    fake_records = [{
        "finding_id": "fnd_selftest_" + secrets.token_hex(6),
        "domain": "observability-layer-self-check",
        "repo": "claude-control",
        "severity": "info",
        "producer": {"kind": "custom_script", "name": "auditor_engine_events.py", "version": "2026-07-24"},
    }]
    with _write_lock():
        conn = _connect()
        ensure_events_table(conn)
        new_count = stamp_new_finding_events(conn, fake_records, run_trace)
        conn.commit()
        conn.close()
    complete_audit_run(run_trace, status="ok", total_findings=1, new_findings=new_count, duration_s=0.01,
                        notes="self-test run, safe to ignore/delete")
    result = {
        "ok": True,
        "trace_id": run_trace.trace_id,
        "event_id_sample": fake_records[0]["event_id"],
        "new_finding_events_emitted": new_count,
        "otel_status": otel_status(),
        "jsonschema_available": _JSONSCHEMA_AVAILABLE,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print("auditor_engine_events.py is a library -- run with --self-test for a smoke test.")
    sys.exit(1)
