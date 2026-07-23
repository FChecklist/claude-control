#!/usr/bin/env python3
"""
Superboss Register -- three searchable trees, server-side, SQLite+FTS5.
Deployed 2026-07-20 per Owner directive: no session starts from zero again.

SCOPE (deliberately distinct from the AI-work cost-control system built
earlier the same night -- that governs dispatched WORKER tasks; this
governs the OWNER<->SUPERBOSS operational dialogue itself, which nothing
else in this codebase tracks. Not a duplicate of `conversations`/`messages`
in schema.ts either -- those are VERI Chat's end-customer product tables,
a different population/purpose entirely, confirmed by direct inspection
before building this.

THREE TREES:
  instructions -- one row per distinct request/instruction (the INPUT side:
                  what was asked, by whom, when, tagged UTM-style).
  work_items   -- one row per unit of work registered in response (the
                  OUTPUT side). software_task_id XOR ai_task_id populated
                  depending on route (§1 triage in
                  AI_CACHE_AND_TRIAGE_ARCHITECTURE.md). Links back to the
                  instruction(s) that spawned it.
  actions      -- finest-grained audit trail: one row per individual action
                  by ANY actor (owner, end_user, org, ai_agent, software).
                  Links to the work_item and/or instruction it serves.

STORAGE FORMAT: structured records (typed columns + a JSON metadata blob),
not narrative text -- per Owner directive, this store is for AI/software
consumption, not human reading. Raw instruction/action text is still
stored (full-text search needs it), but every record is tag-indexed so a
query never requires re-reading raw prose to find what's relevant.

ID SCHEMES (all sortable-by-construction, timestamp-prefixed):
  INS-YYYYMMDD-HHMMSS-<4hex>   instruction_id
  SFT-YYYYMMDD-HHMMSS-<4hex>   software_task_id  (work done with zero AI calls)
  (existing CONTROLLER.yaml task_id reused verbatim as ai_task_id when work
   routes through the existing AI worker fleet -- NOT reissued, avoids a
   second ID for the same real task)
  CCH-<16 hex of the real cache key>   cache_id / ai_cache_id (references
   the existing L1 exact-match cache in glm-response-cache.sqlite by its
   own key, not a new ID space -- avoids yet another duplicate index)
  ACT-YYYYMMDD-HHMMSS-<4hex>   action_id

UTM-STYLE TAGS (literal UTM parameter names, since that's the vocabulary
the Owner specified): utm_source (who: owner|end_user|org|ai_agent|software),
utm_medium (channel: ssh_session|claude_code_cli|chat_ui|api|cron),
utm_campaign (initiative/project grouping, freeform slug),
utm_content (short structured label of what, not a sentence),
utm_term (comma-separated search keywords).
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import secrets
import sqlite3
import sys
import time
from datetime import datetime, timezone

DB_PATH = os.environ.get("SUPERBOSS_REGISTER_DB", "/opt/veridian/ai-os/memory/superboss-register.sqlite")
_WRITE_LOCK_PATH = DB_PATH + ".writelock"


@contextlib.contextmanager
def _write_lock():
    """Serializes every write-path CLI invocation of this script across
    processes -- same proven pattern as veridian-task.py's controller_lock()
    (built for the 2026-07-18 CONTROLLER.yaml corruption). Root cause found
    2026-07-23 for this DB's same-day repeated corruption (3 distinct
    signatures): concurrent writers contend for SQLite's own write lock
    inside their 30s busy_timeout (_connect() below), but the outer caller
    -- veridian-task.py's _log_to_register(), fired every 5 minutes by every
    active worker's background checkpoint loop, plus ad-hoc log-work/
    log-action calls -- only waited 10s before SIGKILLing a still-blocked
    child (see veridian-task.py _log_to_register). A kill landing while a
    process holds the SQLite write lock mid-transaction/mid-WAL-checkpoint
    (each INSERT here also fires an FTS5 AFTER INSERT trigger, widening
    that window) leaves partially-written b-tree pages -- matching exactly
    the page-truncation/tree-damage/freelist-mismatch signatures seen today.
    Acquiring this OS file lock BEFORE opening any sqlite write connection
    means a losing process blocks entirely outside any sqlite transaction,
    so killing it while it waits can never corrupt the file; flock is also
    auto-released if the holder itself is killed, so this cannot deadlock.
    """
    os.makedirs(os.path.dirname(_WRITE_LOCK_PATH), exist_ok=True)
    with open(_WRITE_LOCK_PATH, "w") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lockfile, fcntl.LOCK_UN)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix):
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    rand = secrets.token_hex(2)
    return f"{prefix}-{ts}-{rand}"


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS instructions (
        instruction_id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        session_id TEXT,
        utm_source TEXT NOT NULL,
        utm_medium TEXT NOT NULL,
        utm_campaign TEXT,
        utm_content TEXT,
        utm_term TEXT,
        raw_text TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        response_summary TEXT
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS instructions_fts USING fts5(
        instruction_id UNINDEXED, raw_text, utm_content, utm_term, response_summary,
        content='instructions', content_rowid='rowid'
    );
    CREATE TRIGGER IF NOT EXISTS instructions_ai AFTER INSERT ON instructions BEGIN
        INSERT INTO instructions_fts(rowid, instruction_id, raw_text, utm_content, utm_term, response_summary)
        VALUES (new.rowid, new.instruction_id, new.raw_text, new.utm_content, new.utm_term, new.response_summary);
    END;

    CREATE TABLE IF NOT EXISTS work_items (
        work_item_id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        instruction_id TEXT,
        software_task_id TEXT,
        ai_task_id TEXT,
        cache_id TEXT,
        ai_cache_id TEXT,
        utm_source TEXT NOT NULL,
        utm_medium TEXT NOT NULL,
        utm_campaign TEXT,
        utm_content TEXT,
        utm_term TEXT,
        status TEXT NOT NULL DEFAULT 'open',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        FOREIGN KEY (instruction_id) REFERENCES instructions(instruction_id)
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS work_items_fts USING fts5(
        work_item_id UNINDEXED, utm_content, utm_term,
        content='work_items', content_rowid='rowid'
    );
    CREATE TRIGGER IF NOT EXISTS work_items_ai AFTER INSERT ON work_items BEGIN
        INSERT INTO work_items_fts(rowid, work_item_id, utm_content, utm_term)
        VALUES (new.rowid, new.work_item_id, new.utm_content, new.utm_term);
    END;

    CREATE TABLE IF NOT EXISTS actions (
        action_id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        work_item_id TEXT,
        instruction_id TEXT,
        utm_source TEXT NOT NULL,
        utm_medium TEXT NOT NULL,
        utm_campaign TEXT,
        utm_content TEXT NOT NULL,
        utm_term TEXT,
        result TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        FOREIGN KEY (work_item_id) REFERENCES work_items(work_item_id),
        FOREIGN KEY (instruction_id) REFERENCES instructions(instruction_id)
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS actions_fts USING fts5(
        action_id UNINDEXED, utm_content, utm_term, result,
        content='actions', content_rowid='rowid'
    );
    CREATE TRIGGER IF NOT EXISTS actions_ai AFTER INSERT ON actions BEGIN
        INSERT INTO actions_fts(rowid, action_id, utm_content, utm_term, result)
        VALUES (new.rowid, new.action_id, new.utm_content, new.utm_term, new.result);
    END;

    CREATE INDEX IF NOT EXISTS idx_instructions_campaign ON instructions(utm_campaign);
    CREATE INDEX IF NOT EXISTS idx_work_items_instruction ON work_items(instruction_id);
    CREATE INDEX IF NOT EXISTS idx_work_items_campaign ON work_items(utm_campaign);
    CREATE INDEX IF NOT EXISTS idx_actions_work_item ON actions(work_item_id);
    CREATE INDEX IF NOT EXISTS idx_actions_campaign ON actions(utm_campaign);

    -- 4th tree (2026-07-20, Owner directive: "indexation of everything we
    -- do is missing... that's why wrong files/scripts/tables keep getting
    -- picked"). Catalogs every real mechanism (script/service/table) found
    -- during this session's audits, not the work-event history above --
    -- this answers "does X already exist and where" BEFORE building
    -- anything, which the other 3 trees cannot (they log what happened,
    -- not what exists).
    CREATE TABLE IF NOT EXISTS system_index (
        index_id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        path TEXT NOT NULL,
        category TEXT NOT NULL,
        layer TEXT NOT NULL,
        status TEXT NOT NULL,
        purpose TEXT NOT NULL,
        utm_term TEXT,
        calls TEXT,
        called_by TEXT,
        verified_ts TEXT,
        tags TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS system_index_fts USING fts5(
        index_id UNINDEXED, path, purpose, utm_term, calls, called_by,
        content='system_index', content_rowid='rowid'
    );
    CREATE TRIGGER IF NOT EXISTS system_index_ai AFTER INSERT ON system_index BEGIN
        INSERT INTO system_index_fts(rowid, index_id, path, purpose, utm_term, calls, called_by)
        VALUES (new.rowid, new.index_id, new.path, new.purpose, new.utm_term, new.calls, new.called_by);
    END;
    -- 2026-07-23 fix (sqlite-corruption diagnosis): index_add() upserts via
    -- ON CONFLICT(path) DO UPDATE, but this external-content FTS5 table only
    -- had an AFTER INSERT sync trigger -- every re-verification of an
    -- already-indexed path (the documented, intended, common case) silently
    -- desynced system_index_fts from system_index (stale search results, not
    -- what today's page/freelist corruption looked like, but a real bug in
    -- the same area named for scrutiny). IF NOT EXISTS makes this additive
    -- for pre-existing DBs too, no separate migration needed.
    CREATE TRIGGER IF NOT EXISTS system_index_au AFTER UPDATE ON system_index BEGIN
        INSERT INTO system_index_fts(system_index_fts, rowid, index_id, path, purpose, utm_term, calls, called_by)
        VALUES ('delete', old.rowid, old.index_id, old.path, old.purpose, old.utm_term, old.calls, old.called_by);
        INSERT INTO system_index_fts(rowid, index_id, path, purpose, utm_term, calls, called_by)
        VALUES (new.rowid, new.index_id, new.path, new.purpose, new.utm_term, new.calls, new.called_by);
    END;
    CREATE INDEX IF NOT EXISTS idx_system_index_category ON system_index(category);
    CREATE INDEX IF NOT EXISTS idx_system_index_status ON system_index(status);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_system_index_path ON system_index(path);

    -- 5th tree (2026-07-23, ai-os/EXECUTION_RULES_AUDIT_2026-07-23.yaml Part 40 --
    -- pre_execution_checklist_automation phase). Per-task machine-readable
    -- Pre-Execution Log / Post-Execution Log: one row per (task, phase), each
    -- row holding every checklist field's real YES/NO + evidence, not a
    -- fabricated claim. Additive new table, same pattern as task_audits in
    -- postflight_audit_gate.py -- not a parallel store to the 4 trees above,
    -- which log work-events/system-inventory, not per-field checklist compliance.
    -- 6th tree (2026-07-23, governance item 52, searchable_indexed_logs):
    -- ai-os/logs/*.log(.jsonl) are plain-text/JSONL, grep-only -- no
    -- index/search service existed. Same FTS5 CREATE VIRTUAL TABLE + AFTER
    -- INSERT trigger convention as instructions/actions/system_index above,
    -- populated by scripts/index-logs.py (idempotent per-file line-tracking,
    -- same pattern as index_transcript()'s own state file).
    CREATE TABLE IF NOT EXISTS log_index (
        log_index_id TEXT PRIMARY KEY,
        log_file TEXT NOT NULL,
        line_no INTEGER NOT NULL,
        ts TEXT,
        content TEXT NOT NULL
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS log_index_fts USING fts5(
        log_index_id UNINDEXED, log_file, content,
        content='log_index', content_rowid='rowid'
    );
    CREATE TRIGGER IF NOT EXISTS log_index_ai AFTER INSERT ON log_index BEGIN
        INSERT INTO log_index_fts(rowid, log_index_id, log_file, content)
        VALUES (new.rowid, new.log_index_id, new.log_file, new.content);
    END;
    CREATE UNIQUE INDEX IF NOT EXISTS idx_log_index_file_line ON log_index(log_file, line_no);

    CREATE TABLE IF NOT EXISTS execution_log (
        execution_log_id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        phase TEXT NOT NULL,
        work_item_id TEXT,
        software_task_id TEXT,
        source_script TEXT NOT NULL,
        fields_json TEXT NOT NULL,
        yes_count INTEGER NOT NULL,
        no_count INTEGER NOT NULL,
        total_fields INTEGER NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_execution_log_software_task ON execution_log(software_task_id);
    CREATE INDEX IF NOT EXISTS idx_execution_log_work_item ON execution_log(work_item_id);

    -- 2026-07-23, task-20260723-142643 (veridian-task-watchdog.py): per-
    -- error-signature auto-recovery memory. A signature is the first 60
    -- chars of a stalled/looping task's checkpoint note -- deliberately
    -- coarse (not a full hash) so near-identical recurrences of the same
    -- failure (e.g. same exception, different task_id/timestamp suffix)
    -- still match. One row per signature (PRIMARY KEY, not autoincrement):
    -- the watchdog's step_2 looks up a signature and, if a fix_action is
    -- already on file, re-applies the SAME action instead of re-escalating
    -- to a fresh RCA task every time the identical failure recurs.
    CREATE TABLE IF NOT EXISTS known_fixes (
        signature TEXT PRIMARY KEY,
        fix_action TEXT NOT NULL,
        last_applied TEXT,
        success_count INTEGER NOT NULL DEFAULT 0
    );

    -- 7th tree (2026-07-23, Knowledge Engine Phase 1, task-20260723-181151).
    -- Builds the real table proposed in
    -- ai-os/KNOWLEDGE_ENGINE_SCHEMA_DESIGN_2026-07-23.yaml's proposed_table
    -- (verbatim create_statement -- Phase 0 already reviewed this design,
    -- this phase builds it, does not redesign it), extending system_index's
    -- own proven "path + metadata, not a content copy" contract. One row per
    -- real knowledge/rules/constitution artifact found in
    -- ai-os/KNOWLEDGE_ENGINE_INVENTORY_2026-07-23.yaml -- artifact_path +
    -- content_hash let a query detect drift without ever storing the bytes.
    CREATE TABLE IF NOT EXISTS knowledge_engine (
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
    CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_engine_fts USING fts5(
        purpose, tags, entity_relationships,
        content='knowledge_engine', content_rowid='rowid'
    );
    CREATE TRIGGER IF NOT EXISTS knowledge_engine_ai AFTER INSERT ON knowledge_engine BEGIN
        INSERT INTO knowledge_engine_fts(rowid, purpose, tags, entity_relationships)
        VALUES (new.rowid, new.purpose, new.tags, new.entity_relationships);
    END;
    CREATE INDEX IF NOT EXISTS idx_knowledge_engine_type ON knowledge_engine(artifact_type);
    CREATE INDEX IF NOT EXISTS idx_knowledge_engine_path ON knowledge_engine(artifact_path);
    """)
    conn.commit()
    _migrate_schema(conn)
    conn.close()
    print(json.dumps({"ok": True, "db": DB_PATH}))


def _ensure_execution_log_table(conn):
    """Standalone idempotent create, mirrors postflight_audit_gate.py's own
    ensure_tables() defensiveness -- works even if init_db() was never run
    against this DB (e.g. an older DB re-created outside init_db)."""
    conn.execute("""CREATE TABLE IF NOT EXISTS execution_log (
        execution_log_id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        phase TEXT NOT NULL,
        work_item_id TEXT,
        software_task_id TEXT,
        source_script TEXT NOT NULL,
        fields_json TEXT NOT NULL,
        yes_count INTEGER NOT NULL,
        no_count INTEGER NOT NULL,
        total_fields INTEGER NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_log_software_task ON execution_log(software_task_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_log_work_item ON execution_log(work_item_id)")
    conn.commit()


def _migrate_schema(conn):
    """Additive, idempotent migrations for DBs created before a column existed.
    CREATE TABLE IF NOT EXISTS above only covers brand-new DBs; a pre-existing
    system_index needs ALTER TABLE to pick up new columns (2026-07-23:
    nullable `tags`, JSON-encoded list, per ai-os/EXECUTION_RULES_AUDIT_2026-07-23.yaml
    Part 14/15/20 -- zero-duplication extension of the existing table, not a
    second tags store)."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(system_index)").fetchall()}
    if "tags" not in cols:
        conn.execute("ALTER TABLE system_index ADD COLUMN tags TEXT")
        conn.commit()


def log_instruction(args):
    init_db_silent()
    conn = _connect()
    iid = _new_id("INS")
    conn.execute(
        "INSERT INTO instructions (instruction_id, ts, session_id, utm_source, utm_medium, utm_campaign, utm_content, utm_term, raw_text, metadata_json, response_summary) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (iid, _now_iso(), args.session_id, args.source, args.medium, args.campaign, args.content, args.term,
         args.text, json.dumps(json.loads(args.metadata) if args.metadata else {}), args.response_summary),
    )
    conn.commit()
    conn.close()
    print(json.dumps({"instruction_id": iid}))


def index_transcript(args):
    """Auto-indexes a laptop-chat transcript JSONL (pushed word-for-word by the
    Stop hook) into the existing instructions table + its FTS5 index -- reuses
    the existing schema/search path per STANDING_DIRECTIVE.yaml zero-duplication
    mandate, no parallel table. Idempotent via a per-file .indexed_line state
    file, same pattern the laptop-side push hook already uses."""
    state_path = args.file + ".indexed_line"
    last = 0
    if os.path.isfile(state_path):
        try:
            last = int(open(state_path).read().strip())
        except Exception:
            last = 0

    if not os.path.isfile(args.file):
        print(json.dumps({"indexed": 0, "note": "file not found"}))
        return

    init_db_silent()
    conn = _connect()
    indexed = 0
    line_no = last
    with open(args.file, encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            if line_no <= last:
                continue
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                d = json.loads(raw_line)
            except Exception:
                continue
            t = d.get("type")
            entry_uuid = d.get("uuid", "")
            ts = d.get("timestamp") or _now_iso()

            text = None
            role = None
            if t == "user":
                content = d.get("message", {}).get("content")
                if isinstance(content, str) and content.strip():
                    text = content
                    role = "owner"
            elif t == "assistant":
                content = d.get("message", {}).get("content")
                if isinstance(content, list):
                    parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                    joined = "\n".join(part for part in parts if part.strip())
                    if joined.strip():
                        text = joined
                        role = "ai_agent"

            if text and role:
                iid = _new_id("INS")
                try:
                    conn.execute(
                        "INSERT INTO instructions (instruction_id, ts, session_id, utm_source, utm_medium, utm_campaign, utm_content, utm_term, raw_text, metadata_json, response_summary) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (iid, ts, args.session_id, role, "laptop_chat_auto", "", "", "",
                         text, json.dumps({"transcript_uuid": entry_uuid, "transcript_line": line_no}), None),
                    )
                    indexed += 1
                except Exception:
                    pass

    conn.commit()
    conn.close()

    with open(state_path, "w") as f:
        f.write(str(line_no))

    print(json.dumps({"indexed": indexed, "through_line": line_no}))


def log_work(args):
    init_db_silent()
    conn = _connect()
    wid = _new_id("WRK")
    # --ts override (2026-07-20, historical-import support): a bulk import of
    # past sessions needs to carry each entry's REAL date, not the moment of
    # import -- otherwise the whole point (an accurate timeline) is lost.
    ts = getattr(args, "ts", None) or _now_iso()
    conn.execute(
        "INSERT INTO work_items (work_item_id, ts, instruction_id, software_task_id, ai_task_id, cache_id, ai_cache_id, "
        "utm_source, utm_medium, utm_campaign, utm_content, utm_term, status, metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (wid, ts, args.instruction_id, args.software_task_id, args.ai_task_id, args.cache_id, args.ai_cache_id,
         args.source, args.medium, args.campaign, args.content, args.term, args.status,
         json.dumps(json.loads(args.metadata) if args.metadata else {})),
    )
    conn.commit()
    conn.close()
    print(json.dumps({"work_item_id": wid}))


def log_action(args):
    init_db_silent()
    conn = _connect()
    aid = _new_id("ACT")
    conn.execute(
        "INSERT INTO actions (action_id, ts, work_item_id, instruction_id, utm_source, utm_medium, utm_campaign, utm_content, utm_term, result, metadata_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (aid, _now_iso(), args.work_item_id, args.instruction_id, args.source, args.medium, args.campaign,
         args.content, args.term, args.result, json.dumps(json.loads(args.metadata) if args.metadata else {})),
    )
    conn.commit()
    conn.close()
    print(json.dumps({"action_id": aid}))


def log_login(user, source_ip, method):
    """Governance item 11 (veridian_built_login_logging): reuses the existing
    actions table + actions_fts index (zero-duplication) instead of a parallel
    login table -- a login is just another action, source_ip/method carried in
    the same utm_content/utm_term columns log_action already uses for other
    action kinds. Callable directly (security-check.py imports this, since it
    already owns the only real auth.log parser -- see its own module docstring)
    as well as via the log-login CLI subcommand below."""
    init_db_silent()
    conn = _connect()
    aid = _new_id("ACT")
    conn.execute(
        "INSERT INTO actions (action_id, ts, work_item_id, instruction_id, utm_source, utm_medium, utm_campaign, utm_content, utm_term, result, metadata_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (aid, _now_iso(), None, None, "login", "ssh", None, source_ip, method, "success", json.dumps({"user": user})),
    )
    conn.commit()
    conn.close()
    return aid


STOPWORDS = {"the", "a", "an", "of", "to", "for", "and", "or", "in", "on", "vs", "is", "are", "be", "do", "does"}


def _fts_query(raw):
    """2026-07-20 fix: FTS5's default MATCH syntax is implicit AND across
    space-separated bare terms -- a natural query like 'software vs AI
    classification' silently returns ZERO rows if even one word (here:
    'vs') isn't indexed anywhere, which is exactly the false-negative this
    whole tool exists to prevent (a missed duplicate is worse than noise
    from a false positive). Strip stopwords, OR the remaining terms
    together -- forgiving by design for a discovery search."""
    terms = [t.strip('"') for t in raw.split() if t.strip('"').lower() not in STOPWORDS and t.strip('"')]
    if not terms:
        terms = raw.split() or [raw]
    escaped = [t.replace('"', '""') for t in terms]
    return " OR ".join(f'"{t}"' for t in escaped)


def search(args):
    init_db_silent()
    conn = _connect()
    results = {"instructions": [], "work_items": [], "actions": [], "system_index": [], "log_index": []}
    q = _fts_query(args.query)
    for table, fts in [("instructions", "instructions_fts"), ("work_items", "work_items_fts"),
                        ("actions", "actions_fts"), ("system_index", "system_index_fts"),
                        ("log_index", "log_index_fts")]:
        try:
            rows = conn.execute(
                f"SELECT t.* FROM {fts} f JOIN {table} t ON t.rowid = f.rowid WHERE {fts} MATCH ? ORDER BY rank LIMIT ?",
                (q, args.limit),
            ).fetchall()
            results[table] = [dict(r) for r in rows]
        except sqlite3.OperationalError as e:
            results[table] = {"error": str(e)}
    if getattr(args, "tag", None):
        # tags is a JSON-encoded list (see index_add) -- membership check done
        # in Python rather than a JSON1 SQL function, since JSON1 is an
        # optional sqlite3 build-time extension not confirmed present here.
        rows = conn.execute("SELECT * FROM system_index").fetchall()
        results["system_index"] = [
            dict(r) for r in rows if args.tag in json.loads(r["tags"] or "[]")
        ]
    conn.close()
    print(json.dumps(results, indent=2, default=str))


def index_add(args):
    """Add or re-verify one system_index entry. path is UNIQUE -- re-running
    this on an already-indexed path UPDATES it (refreshes verified_ts,
    status, etc.) rather than erroring, since this is meant to be a living
    catalog re-checked over time, not a write-once log."""
    init_db_silent()
    conn = _connect()
    iid = _new_id("IDX")
    now = _now_iso()
    tags_list = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
    conn.execute(
        "INSERT INTO system_index (index_id, ts, path, category, layer, status, purpose, utm_term, calls, called_by, verified_ts, tags, metadata_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(path) DO UPDATE SET category=excluded.category, layer=excluded.layer, status=excluded.status, "
        "purpose=excluded.purpose, utm_term=excluded.utm_term, calls=excluded.calls, called_by=excluded.called_by, "
        "verified_ts=excluded.verified_ts, tags=excluded.tags, metadata_json=excluded.metadata_json",
        (iid, now, args.path, args.category, args.layer, args.status, args.purpose, args.term,
         args.calls, args.called_by, now, json.dumps(tags_list), json.dumps(json.loads(args.metadata) if args.metadata else {})),
    )
    conn.commit()
    row = conn.execute("SELECT index_id FROM system_index WHERE path=?", (args.path,)).fetchone()
    conn.close()
    print(json.dumps({"index_id": row["index_id"], "path": args.path}))


def check_duplicate(args):
    """The concrete fix for 'we keep duplicating': search system_index by
    category and/or keyword BEFORE building something new. Prints every
    existing mechanism that might already do what's being considered."""
    init_db_silent()
    conn = _connect()
    conditions = []
    params = []
    if args.category:
        conditions.append("category = ?")
        params.append(args.category)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = []
    if args.query:
        q = _fts_query(args.query)
        fts_rows = conn.execute(
            "SELECT t.* FROM system_index_fts f JOIN system_index t ON t.rowid = f.rowid WHERE system_index_fts MATCH ?",
            (q,),
        ).fetchall()
        if args.category:
            rows = [r for r in fts_rows if r["category"] == args.category]
        else:
            rows = fts_rows
    elif conditions:
        rows = conn.execute(f"SELECT * FROM system_index {where}", params).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    print(json.dumps({
        "found": len(result),
        "verdict": "STOP -- existing mechanism(s) found, review before building" if result else "no existing match found -- safe to proceed, but this is not exhaustive",
        "matches": result,
    }, indent=2, default=str))


VALID_PRE_EXECUTION_FIELDS = {
    "Context Loaded", "Owner Memory Loaded", "Organization Memory Loaded", "End User Memory Loaded",
    "Previous Conversations Loaded", "Previous Commitments Loaded", "Pending Tasks Loaded",
    "Metadata Searched", "YAML Files Searched", "Entity Relationships Searched", "Dependencies Searched",
    "Configuration Searched", "Business Rules Searched", "Documentation Searched", "Existing Software Searched",
    "Existing Scripts Searched", "Existing Automation Searched", "Existing APIs Searched", "Cache Searched",
    "Logs Searched", "Audit Records Searched", "History Searched", "Existing Solution Found",
    "Existing Software Reused", "Task Broken into Steps", "Software Steps Identified", "AI Steps Identified",
    "Human Approval Required", "Execution Plan Created", "Execution Plan Validated", "Dependencies Verified",
    "Permissions Verified", "Configuration Verified", "AI Required", "Software Can Execute Without AI",
    "Previous Commitments Verified", "Duplicate Work Prevented", "Safety Validation Passed",
    "Ready for Execution",
}

VALID_POST_EXECUTION_FIELDS = {
    "Task Completed", "Software Updated", "Script Created/Updated", "Automation Updated", "Workflow Updated",
    "Metadata Updated", "YAML Updated", "Relationships Updated", "Documentation Updated", "Logs Created",
    "Audit Created", "History Updated", "Memory Updated", "Reusable Software Created",
    "AI Work Converted to Software", "Future AI Dependency Reduced", "Testing Completed", "Validation Passed",
    "Owner Approval Required", "Task Successfully Closed",
}


def log_execution(args):
    """Write one Pre-Execution Log or Post-Execution Log row (ai-os/EXECUTION_RULES_AUDIT_2026-07-23.yaml
    Part 40 -- VERIDIAN_EXECUTION_RULES_2026-07-23.md's literal field lists). --fields-file must be a JSON
    object of {field_name: {"status": "YES"|"NO", "evidence": "<real, citable evidence>"}}. Every field name
    is validated against the doc's own literal list for its phase -- typos/invented fields are rejected
    rather than silently accepted, since this table exists specifically to prevent fabricated compliance
    claims. This function does not decide YES/NO itself -- the caller (session_bootstrap.py for PRE,
    postflight_audit_gate.py for POST) must have already run a real check per field."""
    init_db_silent()
    conn = _connect()
    _ensure_execution_log_table(conn)

    with open(args.fields_file, encoding="utf-8") as f:
        fields = json.load(f)

    valid_names = VALID_PRE_EXECUTION_FIELDS if args.phase == "PRE" else VALID_POST_EXECUTION_FIELDS
    unknown = sorted(set(fields) - valid_names)
    if unknown:
        print(json.dumps({"error": f"unknown field name(s) for phase {args.phase} (not in Part 40's literal list)", "unknown": unknown}))
        sys.exit(1)

    bad_status = sorted(k for k, v in fields.items() if v.get("status") not in ("YES", "NO"))
    if bad_status:
        print(json.dumps({"error": "every field's status must be exactly 'YES' or 'NO'", "bad_fields": bad_status}))
        sys.exit(1)

    yes_count = sum(1 for v in fields.values() if v["status"] == "YES")
    no_count = sum(1 for v in fields.values() if v["status"] == "NO")
    elid = _new_id("EXL")
    conn.execute(
        "INSERT INTO execution_log (execution_log_id, ts, phase, work_item_id, software_task_id, source_script, "
        "fields_json, yes_count, no_count, total_fields, metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (elid, _now_iso(), args.phase, args.work_item_id, args.software_task_id, args.source_script,
         json.dumps(fields), yes_count, no_count, len(fields),
         json.dumps(json.loads(args.metadata) if args.metadata else {})),
    )
    conn.commit()
    conn.close()
    print(json.dumps({
        "execution_log_id": elid, "phase": args.phase, "software_task_id": args.software_task_id,
        "work_item_id": args.work_item_id, "yes_count": yes_count, "no_count": no_count, "total_fields": len(fields),
    }))


def _ensure_known_fixes_table(conn):
    """Standalone idempotent create, same defensiveness convention as
    _ensure_execution_log_table -- works even if init_db() was never run
    against this DB."""
    conn.execute("""CREATE TABLE IF NOT EXISTS known_fixes (
        signature TEXT PRIMARY KEY,
        fix_action TEXT NOT NULL,
        last_applied TEXT,
        success_count INTEGER NOT NULL DEFAULT 0
    )""")
    conn.commit()


def log_fix(args):
    """INSERT OR REPLACE keyed on signature -- a repeat call for the same
    signature means the watchdog (or an RCA task, per the escalation spec)
    is re-recording the same fix, so success_count increments instead of
    resetting; a brand-new signature starts at success_count=1. fix_action
    is stored as opaque text, looked up by veridian-task-watchdog.py's own
    fixed, whitelisted action registry -- never shell-executed from here or
    there, so this table cannot become an arbitrary-code-execution vector
    even though its contents come from AI-authored RCA output."""
    conn = _connect()
    _ensure_known_fixes_table(conn)
    row = conn.execute("SELECT success_count FROM known_fixes WHERE signature=?", (args.signature,)).fetchone()
    new_count = (row["success_count"] + 1) if row else 1
    conn.execute(
        "INSERT INTO known_fixes (signature, fix_action, last_applied, success_count) VALUES (?,?,?,?) "
        "ON CONFLICT(signature) DO UPDATE SET fix_action=excluded.fix_action, "
        "last_applied=excluded.last_applied, success_count=excluded.success_count",
        (args.signature, args.fix_action, _now_iso(), new_count),
    )
    conn.commit()
    conn.close()
    print(json.dumps({"signature": args.signature, "fix_action": args.fix_action, "success_count": new_count}))


def _ensure_knowledge_engine_table(conn):
    """Standalone idempotent create, same defensiveness convention as
    _ensure_execution_log_table/_ensure_known_fixes_table -- works even if
    init_db() was never run against this DB."""
    conn.execute("""CREATE TABLE IF NOT EXISTS knowledge_engine (
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
    )""")
    conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_engine_fts USING fts5(
        purpose, tags, entity_relationships,
        content='knowledge_engine', content_rowid='rowid'
    )""")
    conn.execute("""CREATE TRIGGER IF NOT EXISTS knowledge_engine_ai AFTER INSERT ON knowledge_engine BEGIN
        INSERT INTO knowledge_engine_fts(rowid, purpose, tags, entity_relationships)
        VALUES (new.rowid, new.purpose, new.tags, new.entity_relationships);
    END""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_engine_type ON knowledge_engine(artifact_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_engine_path ON knowledge_engine(artifact_path)")
    conn.commit()


def register_knowledge(args):
    """Add one knowledge_engine pointer row. Real content_hash + exists_on_disk
    are computed from a live read of --path (never guessed) -- a missing file
    is recorded as a real exists_on_disk=0 / verification_status=PATH_MISSING
    row (per KNOWLEDGE_ENGINE_SCHEMA_DESIGN_2026-07-23.yaml's drift-visibility
    requirement), not silently rejected. --relationships is a JSON list of
    {"path": ..., "relationship_type": ..., "evidence": <optional>} objects;
    each is resolved against already-registered rows so related_artifact_id
    is populated whenever the target artifact already has a row (falls back
    to null, never fabricated, if it doesn't yet)."""
    init_db_silent()
    conn = _connect()
    _ensure_knowledge_engine_table(conn)

    aid = _new_id("KE")
    now = _now_iso()
    exists = os.path.isfile(args.path)
    if exists:
        with open(args.path, "rb") as f:
            content_hash = hashlib.sha256(f.read()).hexdigest()
        verification_status = "VERIFIED_MATCH"
    else:
        # No bytes to hash for a referenced-but-missing artifact -- sha256 of
        # the empty string is a documented sentinel, paired with
        # verification_status=PATH_MISSING so this is never confused with a
        # real verified empty file.
        content_hash = hashlib.sha256(b"").hexdigest()
        verification_status = "PATH_MISSING"

    tags_list = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []

    relationships_in = json.loads(args.relationships) if args.relationships else []
    entity_relationships = []
    for rel in relationships_in:
        related_path = rel["path"]
        related_row = conn.execute(
            "SELECT artifact_id FROM knowledge_engine WHERE artifact_path = ? ORDER BY ts DESC LIMIT 1",
            (related_path,),
        ).fetchone()
        entity_relationships.append({
            "related_artifact_id": related_row["artifact_id"] if related_row else None,
            "related_artifact_path": related_path,
            "relationship_type": rel["relationship_type"],
            "evidence": rel.get("evidence"),
        })

    conn.execute(
        "INSERT INTO knowledge_engine (artifact_id, ts, artifact_path, content_hash, artifact_type, "
        "secondary_path, exists_on_disk, purpose, tags, entity_relationships, last_verified_ts, "
        "verification_status, metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (aid, now, args.path, content_hash, args.artifact_type, args.secondary_path,
         1 if exists else 0, args.purpose, json.dumps(tags_list), json.dumps(entity_relationships),
         now, verification_status, json.dumps(json.loads(args.metadata) if args.metadata else {})),
    )
    conn.commit()
    conn.close()
    print(json.dumps({
        "artifact_id": aid, "artifact_path": args.path, "artifact_type": args.artifact_type,
        "exists_on_disk": exists, "verification_status": verification_status,
        "entity_relationships": entity_relationships,
    }, indent=2, default=str))


def query_knowledge(args):
    """FTS5 search over knowledge_engine (purpose/tags/entity_relationships),
    same MATCH-via-_fts_query + rowid-join pattern as search()'s other trees.
    --tag filters to rows whose tags list contains that exact tag, same
    Python-side membership check search() already uses for system_index.tags
    (JSON1 not confirmed present on this host)."""
    init_db_silent()
    conn = _connect()
    _ensure_knowledge_engine_table(conn)
    q = _fts_query(args.query)
    try:
        rows = conn.execute(
            "SELECT t.* FROM knowledge_engine_fts f JOIN knowledge_engine t ON t.rowid = f.rowid "
            "WHERE knowledge_engine_fts MATCH ? ORDER BY rank",
            (q,),
        ).fetchall()
        result = [dict(r) for r in rows]
    except sqlite3.OperationalError as e:
        result = []
    if getattr(args, "tag", None):
        result = [r for r in result if args.tag in json.loads(r["tags"] or "[]")]
    conn.close()
    print(json.dumps({"found": len(result), "matches": result}, indent=2, default=str))
def init_db_silent():
    if not os.path.exists(DB_PATH):
        conn = _connect()
        conn.close()
    conn = _connect()
    conn.execute("SELECT 1 FROM instructions LIMIT 1")
    _migrate_schema(conn)
    conn.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")

    p_ins = sub.add_parser("log-instruction")
    p_ins.add_argument("--text", required=True)
    p_ins.add_argument("--source", default="owner")
    p_ins.add_argument("--medium", default="ssh_session")
    p_ins.add_argument("--campaign", default="")
    p_ins.add_argument("--content", default="")
    p_ins.add_argument("--term", default="")
    p_ins.add_argument("--session-id", dest="session_id", default="")
    p_ins.add_argument("--metadata", default="")
    p_ins.add_argument("--response-summary", dest="response_summary", default="")

    p_work = sub.add_parser("log-work")
    p_work.add_argument("--instruction-id", dest="instruction_id", default=None)
    p_work.add_argument("--software-task-id", dest="software_task_id", default=None)
    p_work.add_argument("--ai-task-id", dest="ai_task_id", default=None)
    p_work.add_argument("--cache-id", dest="cache_id", default=None)
    p_work.add_argument("--ai-cache-id", dest="ai_cache_id", default=None)
    p_work.add_argument("--source", default="ai_agent")
    p_work.add_argument("--medium", default="claude_code_cli")
    p_work.add_argument("--campaign", default="")
    p_work.add_argument("--content", default="")
    p_work.add_argument("--term", default="")
    p_work.add_argument("--status", default="open")
    p_work.add_argument("--metadata", default="")
    p_work.add_argument("--ts", default=None, help="ISO8601 override for historical imports; defaults to now")

    p_act = sub.add_parser("log-action")
    p_act.add_argument("--work-item-id", dest="work_item_id", default=None)
    p_act.add_argument("--instruction-id", dest="instruction_id", default=None)
    p_act.add_argument("--source", default="ai_agent")
    p_act.add_argument("--medium", default="claude_code_cli")
    p_act.add_argument("--campaign", default="")
    p_act.add_argument("--content", required=True)
    p_act.add_argument("--term", default="")
    p_act.add_argument("--result", default="")
    p_act.add_argument("--metadata", default="")

    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=10)
    p_search.add_argument("--tag", default=None, help="filter system_index results to rows whose tags list contains this exact tag")

    p_idx = sub.add_parser("index-add")
    p_idx.add_argument("--path", required=True, help="file/table/mechanism location, e.g. src/lib/task-tightening.ts")
    p_idx.add_argument("--category", required=True, help="cache|validation|guardrail|router|monitor|task_register|hallucination_detection|confidence_scoring|dispatch_entrypoint|classification|other")
    p_idx.add_argument("--layer", required=True, help="shell|typescript|database|documentation")
    p_idx.add_argument("--status", required=True, help="live|partial|dead|deprecated|designed_not_built")
    p_idx.add_argument("--purpose", required=True)
    p_idx.add_argument("--term", default="")
    p_idx.add_argument("--calls", default="")
    p_idx.add_argument("--called-by", dest="called_by", default="")
    p_idx.add_argument("--tags", default="", help="comma-separated list, e.g. module:dispatch,priority:high -- stored as a JSON-encoded list")
    p_idx.add_argument("--metadata", default="")

    p_dup = sub.add_parser("check-duplicate")
    p_dup.add_argument("query", nargs="?", default="")
    p_dup.add_argument("--category", default="")

    p_exec = sub.add_parser("log-execution")
    p_exec.add_argument("--phase", required=True, choices=["PRE", "POST"])
    p_exec.add_argument("--work-item-id", dest="work_item_id", default=None)
    p_exec.add_argument("--software-task-id", dest="software_task_id", default=None)
    p_exec.add_argument("--source-script", dest="source_script", required=True,
                         help="e.g. ai-os/scripts/session_bootstrap.py or ai-os/scripts/postflight_audit_gate.py")
    p_exec.add_argument("--fields-file", dest="fields_file", required=True,
                         help="path to a JSON file: {field_name: {\"status\": \"YES\"|\"NO\", \"evidence\": \"...\"}}")
    p_exec.add_argument("--metadata", default="")

    p_idxt = sub.add_parser("index-transcript")
    p_idxt.add_argument("--file", required=True, help="path to the raw laptop-chat transcript JSONL")
    p_idxt.add_argument("--session-id", dest="session_id", required=True)

    p_login = sub.add_parser("log-login")
    p_login.add_argument("--user", required=True, help="linux username")
    p_login.add_argument("--source-ip", dest="source_ip", required=True)
    p_login.add_argument("--method", required=True, help="publickey|password")

    p_fix = sub.add_parser("log-fix")
    p_fix.add_argument("--signature", required=True, help="first 60 chars of the stalled/looping checkpoint note")
    p_fix.add_argument("--fix-action", dest="fix_action", required=True,
                        help="name of a known, whitelisted recovery action (see veridian-task-watchdog.py's FIX_ACTIONS registry)")

    p_regk = sub.add_parser("register-knowledge")
    p_regk.add_argument("--path", required=True, help="real, absolute artifact_path -- exists_on_disk is detected live, not asserted")
    p_regk.add_argument("--artifact-type", dest="artifact_type", required=True, choices=["canonical", "derived"])
    p_regk.add_argument("--purpose", required=True, help="one line, sourced from the artifact's own self-declared header/meta, never guessed from filename")
    p_regk.add_argument("--tags", default="", help="comma-separated list, stored as a JSON-encoded list (same convention as index-add)")
    p_regk.add_argument("--relationships", default="[]",
                        help='JSON list of {"path": "<real path>", "relationship_type": "<free text>", "evidence": "<optional file:line/quote>"}')
    p_regk.add_argument("--secondary-path", dest="secondary_path", default=None,
                         help="nullable -- only for artifacts with a real dual-location precedent (e.g. MASTER_INDEX.yaml)")
    p_regk.add_argument("--metadata", default="")

    p_queryk = sub.add_parser("query-knowledge")
    p_queryk.add_argument("query")
    p_queryk.add_argument("--tag", default=None, help="filter results to rows whose tags list contains this exact tag")
    args = p.parse_args()
    if args.cmd == "init":
        with _write_lock():
            init_db()
    elif args.cmd == "log-instruction":
        with _write_lock():
            log_instruction(args)
    elif args.cmd == "log-work":
        with _write_lock():
            log_work(args)
    elif args.cmd == "log-action":
        with _write_lock():
            log_action(args)
    elif args.cmd == "search":
        search(args)
    elif args.cmd == "index-add":
        with _write_lock():
            index_add(args)
    elif args.cmd == "check-duplicate":
        check_duplicate(args)
    elif args.cmd == "log-execution":
        with _write_lock():
            log_execution(args)
    elif args.cmd == "index-transcript":
        with _write_lock():
            index_transcript(args)
    elif args.cmd == "log-login":
        with _write_lock():
            aid = log_login(args.user, args.source_ip, args.method)
            print(json.dumps({"action_id": aid}))
    elif args.cmd == "log-fix":
        with _write_lock():
            log_fix(args)
    elif args.cmd == "register-knowledge":
        with _write_lock():
            register_knowledge(args)
    elif args.cmd == "query-knowledge":
        query_knowledge(args)
