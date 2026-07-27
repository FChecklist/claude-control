"""Tests for task-20260727-025248 (knowledge-engine/wiring-registry integration):
content_hash staleness detection, first-class governance_doc entities, coverage-delta
detection, and the new combined query helper. Run with:
    python3 -m pytest tests/test_wiring_registry_full_coverage.py -v

Every DB-touching test builds its own REALISTIC PRE-EXISTING schema snapshot (the
wiring_registry table exactly as it looked live before this task -- 'dispatch_event'
already in the entity_type CHECK, no content_hash column) rather than a freshly
init_db()'d DB. This is deliberate: PR #101's round-1 was rejected because its own
migration for a new wiring_registry entity_type never ran against a real pre-existing
schema (all 18 of that round's tests used fresh fixture DBs, so a write that silently
failed against a live, already-populated table went undetected). See
_build_pre_existing_db() below for the exact DDL this reproduces.
"""
import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
import time

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")

# Real, pre-task DDL for wiring_registry -- copied from what
# _ensure_wiring_registry_table() generated BEFORE this task's edits (dispatch_event
# already widened by the 2026-07-27 dispatch-consolidation migration, no content_hash
# column, no 'governance_doc' member). A genuinely non-fresh, already-populated table,
# not something init_db() would produce today.
_PRE_EXISTING_WIRING_REGISTRY_DDL = """
CREATE TABLE wiring_registry (
    entity_id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK(entity_type IN (
        'engine','gateway','supabase_table','function','route','file','script','cron_job',
        'ai_role','vercel_project','github_repo','browser_component','dispatch_event'
    )),
    source_system TEXT NOT NULL CHECK(source_system IN ('server','vercel','supabase','github')),
    path TEXT,
    relationships TEXT NOT NULL DEFAULT '[]',
    last_verified_ts TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED'
        CHECK(verification_status IN ('VERIFIED_MATCH','HASH_DRIFTED','PATH_MISSING','UNVERIFIED')),
    source_ref TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE VIRTUAL TABLE wiring_registry_fts USING fts5(
    path, entity_type, source_ref,
    content='wiring_registry', content_rowid='rowid'
);
CREATE TRIGGER wiring_registry_ai AFTER INSERT ON wiring_registry BEGIN
    INSERT INTO wiring_registry_fts(rowid, path, entity_type, source_ref)
    VALUES (new.rowid, new.path, new.entity_type, new.source_ref);
END;
CREATE TRIGGER wiring_registry_au AFTER UPDATE ON wiring_registry BEGIN
    INSERT INTO wiring_registry_fts(wiring_registry_fts, rowid, path, entity_type, source_ref)
    VALUES ('delete', old.rowid, old.path, old.entity_type, old.source_ref);
    INSERT INTO wiring_registry_fts(rowid, path, entity_type, source_ref)
    VALUES (new.rowid, new.path, new.entity_type, new.source_ref);
END;
CREATE TRIGGER wiring_registry_ad AFTER DELETE ON wiring_registry BEGIN
    INSERT INTO wiring_registry_fts(wiring_registry_fts, rowid, path, entity_type, source_ref)
    VALUES ('delete', old.rowid, old.path, old.entity_type, old.source_ref);
END;
CREATE INDEX idx_wiring_registry_entity_type ON wiring_registry(entity_type);
CREATE INDEX idx_wiring_registry_source_system ON wiring_registry(source_system);
"""

_KNOWLEDGE_ENGINE_DDL = """
CREATE TABLE knowledge_engine (
    artifact_id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    artifact_type TEXT NOT NULL CHECK(artifact_type IN ('canonical','derived')),
    secondary_path TEXT,
    exists_on_disk INTEGER NOT NULL DEFAULT 1,
    purpose TEXT NOT NULL,
    tags TEXT,
    entity_relationships TEXT NOT NULL DEFAULT '[]',
    last_verified_ts TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED'
        CHECK(verification_status IN ('VERIFIED_MATCH','HASH_DRIFTED','PATH_MISSING','UNVERIFIED')),
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE VIRTUAL TABLE knowledge_engine_fts USING fts5(
    artifact_path, purpose, tags, entity_relationships,
    content='knowledge_engine', content_rowid='rowid'
);
CREATE TRIGGER knowledge_engine_ai AFTER INSERT ON knowledge_engine BEGIN
    INSERT INTO knowledge_engine_fts(rowid, artifact_path, purpose, tags, entity_relationships)
    VALUES (new.rowid, new.artifact_path, new.purpose, new.tags, new.entity_relationships);
END;
"""


def _build_pre_existing_db(db_path, wiring_rows=(), knowledge_rows=()):
    """Real pre-existing (non-fresh) schema snapshot -- see module docstring. Seeds
    both tables with real rows (not an empty freshly-created table) via plain INSERTs,
    each row a tuple matching the DDL's column order."""
    conn = sqlite3.connect(db_path)
    conn.executescript(_PRE_EXISTING_WIRING_REGISTRY_DDL)
    conn.executescript(_KNOWLEDGE_ENGINE_DDL)
    for row in wiring_rows:
        conn.execute(
            "INSERT INTO wiring_registry (entity_id, ts, entity_type, source_system, path, "
            "relationships, last_verified_ts, verification_status, source_ref, metadata_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            row,
        )
    for row in knowledge_rows:
        conn.execute(
            "INSERT INTO knowledge_engine (artifact_id, ts, artifact_path, content_hash, artifact_type, "
            "secondary_path, exists_on_disk, purpose, tags, entity_relationships, last_verified_ts, "
            "verification_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            row,
        )
    conn.commit()
    conn.close()


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS_DIR, filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def sbr():
    return _load_module("sbr_test", "superboss-register.py")


@pytest.fixture
def gwr():
    return _load_module("gwr_test", "generate_wiring_registry.py")


@pytest.fixture
def wq():
    return _load_module("wq_test", "wiring_query.py")


# ---------------------------------------------------------------------------
# (a) coverage-delta detection + content_hash migration against a pre-existing schema
# ---------------------------------------------------------------------------

def test_content_hash_migration_preserves_pre_existing_rows(tmp_path, sbr):
    db_path = str(tmp_path / "pre-existing.sqlite")
    _build_pre_existing_db(
        db_path,
        wiring_rows=[
            ("engine-01", "2026-07-01T00:00:00Z", "engine", "server", "src/foo.ts",
             "[]", "2026-07-01T00:00:00Z", "VERIFIED_MATCH", "[]", "{}"),
            ("dispatch_event-task-1", "2026-07-01T00:00:00Z", "dispatch_event", "server", None,
             "[]", "2026-07-01T00:00:00Z", "VERIFIED_MATCH", "[]", "{}"),
        ],
    )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cols_before = {r["name"] for r in conn.execute("PRAGMA table_info(wiring_registry)").fetchall()}
    assert "content_hash" not in cols_before, "fixture must start WITHOUT content_hash (pre-existing schema)"

    sbr._migrate_wiring_registry_entity_types(conn)

    cols_after = {r["name"] for r in conn.execute("PRAGMA table_info(wiring_registry)").fetchall()}
    assert "content_hash" in cols_after

    # Pre-existing rows survived the rebuild unchanged.
    rows = {r["entity_id"] for r in conn.execute("SELECT entity_id FROM wiring_registry").fetchall()}
    assert rows == {"engine-01", "dispatch_event-task-1"}

    # governance_doc is now a real, insertable entity_type (the CHECK constraint widened).
    sbr.register_entity_row(conn, {
        "entity_id": "governance_doc-test",
        "entity_type": "governance_doc",
        "source_system": "server",
        "path": "/tmp/fake.md",
        "relationships": [],
        "last_verified_ts": sbr._now_iso(),
        "verification_status": "VERIFIED_MATCH",
        "source_ref": ["test"],
        "content_hash": "abc123",
    })
    conn.commit()
    row = conn.execute(
        "SELECT entity_type, content_hash FROM wiring_registry WHERE entity_id='governance_doc-test'"
    ).fetchone()
    assert row["entity_type"] == "governance_doc"
    assert row["content_hash"] == "abc123"
    conn.close()


def test_migration_called_directly_by_dispatch_style_write_path(tmp_path, sbr):
    """dispatch_core._upsert_wiring_row calls _migrate_wiring_registry_entity_types()
    directly, bypassing _migrate_schema() by design (see that function's own
    docstring) -- prove the content_hash column still gets added on THAT path, not
    only via the broader _migrate_schema() entrypoint."""
    db_path = str(tmp_path / "pre-existing.sqlite")
    _build_pre_existing_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    sbr._migrate_wiring_registry_entity_types(conn)

    cols = {r["name"] for r in conn.execute("PRAGMA table_info(wiring_registry)").fetchall()}
    assert "content_hash" in cols
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='wiring_registry'"
    ).fetchone()
    assert "'governance_doc'" in row["sql"]
    conn.close()


def test_migration_is_idempotent(tmp_path, sbr):
    db_path = str(tmp_path / "pre-existing.sqlite")
    _build_pre_existing_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    sbr._migrate_wiring_registry_entity_types(conn)
    count_after_first = conn.execute("SELECT COUNT(*) FROM wiring_registry").fetchone()[0]
    sbr._migrate_wiring_registry_entity_types(conn)
    sbr._migrate_wiring_registry_entity_types(conn)
    count_after_more = conn.execute("SELECT COUNT(*) FROM wiring_registry").fetchone()[0]
    assert count_after_first == count_after_more == 0
    conn.close()


def test_coverage_delta_detects_real_gap(tmp_path, gwr, monkeypatch):
    """A real coverage gap: 2 engines expected, only 1 present in wiring_registry;
    2 governance docs expected, only 1 reflected."""
    db_path = str(tmp_path / "db.sqlite")
    doc1 = tmp_path / "doc1.md"
    doc1.write_text("doc one")
    doc2 = tmp_path / "doc2.md"
    doc2.write_text("doc two")

    _build_pre_existing_db(
        db_path,
        wiring_rows=[
            ("engine-01", "t", "engine", "server", "x", "[]", "t", "VERIFIED_MATCH", "[]", "{}"),
        ],
        knowledge_rows=[
            ("KE-1", "t", str(doc1), "h1", "canonical", None, 1, "p",
             json.dumps(["governance"]), "[]", "t", "VERIFIED_MATCH"),
            ("KE-2", "t", str(doc2), "h2", "canonical", None, 1, "p",
             json.dumps(["governance"]), "[]", "t", "VERIFIED_MATCH"),
        ],
    )
    # Reflect doc1 (but not doc2) as an already-covered wiring_registry file entity.
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO wiring_registry (entity_id, ts, entity_type, source_system, path, relationships, "
        "last_verified_ts, verification_status, source_ref, metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("file-ke-KE-1", "t", "file", "server", str(doc1), "[]", "t", "VERIFIED_MATCH", '["knowledge_engine"]', "{}"),
    )
    conn.commit()
    conn.close()

    gwr.DB_PATH = db_path
    monkeypatch.setattr(gwr, "load_engines_gateways", lambda: {
        "engine_inventory": [{"engine_no": 1}, {"engine_no": 2}],
    })

    report = gwr.coverage_delta()
    assert report["engines_expected"] == 2
    assert report["engines_covered"] == 1
    assert report["engines_missing"] == ["engine-02"]
    assert report["governance_docs_expected"] == 2
    assert report["governance_docs_covered"] == 1
    assert report["governance_docs_missing"] == [str(doc2)]


# ---------------------------------------------------------------------------
# (b) content-hash staleness detection on a modified doc
# ---------------------------------------------------------------------------

def test_compute_content_hash_changes_when_file_content_changes(tmp_path, gwr):
    f = tmp_path / "doc.md"
    f.write_text("original content")
    h1 = gwr.compute_content_hash([str(f)])
    assert h1 is not None
    assert h1 == gwr.compute_content_hash([str(f)])  # deterministic given unchanged content

    f.write_text("modified content")
    h2 = gwr.compute_content_hash([str(f)])
    assert h2 is not None
    assert h1 != h2


def test_build_governance_docs_only_updates_the_changed_doc(tmp_path, gwr, monkeypatch):
    db_path = str(tmp_path / "db.sqlite")
    changed_doc = tmp_path / "changed.md"
    changed_doc.write_text("v1")
    control_doc = tmp_path / "control.md"
    control_doc.write_text("unchanged")

    _build_pre_existing_db(
        db_path,
        knowledge_rows=[
            ("KE-changed", "t", str(changed_doc), "h", "canonical", None, 1, "p",
             json.dumps(["governance"]), "[]", "t", "VERIFIED_MATCH"),
            ("KE-control", "t", str(control_doc), "h", "canonical", None, 1, "p",
             json.dumps(["constitution"]), "[]", "t", "VERIFIED_MATCH"),
        ],
    )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    sbr = _load_module("sbr_test2", "superboss-register.py")
    sbr._migrate_wiring_registry_entity_types(conn)
    conn.close()

    gwr.DB_PATH = db_path
    gwr._sbr.DB_PATH = db_path

    def run_and_capture():
        reg = gwr.Registry()
        gwr.build_governance_docs(reg)
        gwr.upsert_live_wiring_registry(reg.entities)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = {
            r["entity_id"]: (r["content_hash"], r["ts"])
            for r in conn.execute("SELECT entity_id, content_hash, ts FROM wiring_registry "
                                   "WHERE entity_type='governance_doc'").fetchall()
        }
        conn.close()
        return rows

    before = run_and_capture()
    assert before["governance_doc-KE-changed"][0] is not None
    assert before["governance_doc-KE-control"][0] is not None

    time.sleep(0.01)
    changed_doc.write_text("v2 -- real content change")
    after = run_and_capture()

    assert after["governance_doc-KE-changed"][0] != before["governance_doc-KE-changed"][0]
    assert after["governance_doc-KE-control"][0] == before["governance_doc-KE-control"][0]


# ---------------------------------------------------------------------------
# (c) query-helper correctness + sub-second timing
# ---------------------------------------------------------------------------

def test_query_helper_correctness_and_timing(tmp_path, wq):
    db_path = str(tmp_path / "db.sqlite")
    _build_pre_existing_db(
        db_path,
        wiring_rows=[
            (f"engine-{i:02d}", "t", "engine", "server", f"src/engine{i}.ts",
             "[]", "t", "VERIFIED_MATCH", "[]", "{}")
            for i in range(1, 21)
        ],
        knowledge_rows=[
            ("KE-const", "t", "/opt/veridian/ai-os/CONSTITUTION.yaml", "h", "canonical", None, 1,
             "the constitution", json.dumps(["governance", "constitution"]), "[]", "t", "VERIFIED_MATCH"),
        ],
    )

    t0 = time.time()
    result = wq.query("engine-05", db_path=db_path)
    elapsed = time.time() - t0

    assert elapsed < 1.0, f"query took {elapsed}s, expected sub-second"
    assert result["wiring_registry"]["stage"] == "exact_id_match"
    assert result["wiring_registry"]["count"] == 1
    assert result["wiring_registry"]["matches"][0]["entity_id"] == "engine-05"

    t0 = time.time()
    result2 = wq.query("CONSTITUTION", db_path=db_path)
    elapsed2 = time.time() - t0
    assert elapsed2 < 1.0
    assert result2["knowledge_engine"]["count"] >= 1
    assert result2["knowledge_engine"]["matches"][0]["artifact_id"] == "KE-const"


def test_query_helper_miss_returns_empty_not_error(tmp_path, wq):
    db_path = str(tmp_path / "db.sqlite")
    _build_pre_existing_db(db_path)
    result = wq.query("nonexistent-term-xyz", db_path=db_path)
    assert result["wiring_registry"]["count"] == 0
    assert result["wiring_registry"]["stage"] == "none"
    assert result["knowledge_engine"]["count"] == 0
