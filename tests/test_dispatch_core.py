"""Regression tests for scripts/dispatch_core.py (task-20260726-210339
dispatch/status script consolidation). Run with:
    python3 -m pytest tests/ -k "dispatch_core" -v

test_dispatch_core_concurrency_real_processes below is the real concurrency
proof this task's SUCCESS_CRITERIA requires: multiple real OS processes race
to acquire dispatch_core.acquire_dispatch_lock() and "spawn" against a real,
shared, mock systemctl-backed running-unit count -- not a single-process unit
test of the lock function in isolation.
"""
import importlib.util
import json
import multiprocessing
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _dispatch_consolidation_fixtures import build_fixture_tree, write_task_yaml  # noqa: E402


def _load_dispatch_core(work, env, monkeypatch):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location("dispatch_core_test", str(work / "scripts" / "dispatch_core.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_dispatch_core_task_status_sync_single_walk(tmp_path, monkeypatch):
    work, env = build_fixture_tree(tmp_path)
    write_task_yaml(work, "task-a", "completed")
    write_task_yaml(work, "task-b", "pending_review")
    dc = _load_dispatch_core(work, env, monkeypatch)

    tasks = dc.task_status_sync()
    assert set(tasks) == {"task-a", "task-b"}
    assert tasks["task-a"]["status"] == "completed"
    assert tasks["task-b"]["status"] == "pending_review"
    assert tasks["task-b"]["_has_review_json"] is False


def test_dispatch_core_task_status_sync_detects_review_json(tmp_path, monkeypatch):
    work, env = build_fixture_tree(tmp_path)
    task_dir = write_task_yaml(work, "task-c", "pending_review")
    (task_dir / "review.json").write_text('{"verdict": "approve"}')
    dc = _load_dispatch_core(work, env, monkeypatch)

    tasks = dc.task_status_sync()
    assert tasks["task-c"]["_has_review_json"] is True


def test_dispatch_core_has_free_slot_respects_shared_cap(tmp_path, monkeypatch):
    work, env = build_fixture_tree(tmp_path)
    units_file = work / "units.txt"
    env["MOCK_RUNNING_UNITS_FILE"] = str(units_file)
    env["VERIDIAN_DISPATCH_CONCURRENCY_CAP"] = "2"
    dc = _load_dispatch_core(work, env, monkeypatch)
    dc.CONCURRENCY_CAP = 2

    units_file.write_text("")
    assert dc.has_free_slot() is True

    units_file.write_text("veridian-worker@a\nveridian-worker@b\n")
    assert dc.running_worker_count() == 2
    assert dc.has_free_slot() is False

    # both unit templates count together against the ONE shared cap -- 1
    # worker + 1 supervisor must also read as "at cap", not as "1 worker,
    # separately-tracked 1 supervisor, still under either individual limit".
    units_file.write_text("veridian-worker@a\nveridian-supervisor@b\n")
    assert dc.running_worker_count() == 2
    assert dc.has_free_slot() is False


def test_dispatch_core_record_tick_and_dispatch_event_write_wiring_registry_rows(tmp_path, monkeypatch):
    work, env = build_fixture_tree(tmp_path)
    dc = _load_dispatch_core(work, env, monkeypatch)

    dc.record_tick("dispatch-tick", status="ok", dispatched_this_tick=3, extra={"note": "test"})
    dc.record_dispatch_event(task_id="task-xyz", dispatched_by="dispatch-tick.py:gap_queue",
                              source_queue_or_plan="gap_queue.yaml",
                              worker_unit="veridian-worker@task-xyz.service")

    conn = sqlite3.connect(env["SUPERBOSS_REGISTER_DB"])
    rows = {r[0]: r[1] for r in conn.execute("SELECT entity_id, entity_type FROM wiring_registry")}
    assert rows["cron_job-dispatch-tick"] == "cron_job"
    assert rows["dispatch_event-task-xyz"] == "dispatch_event"

    rel = json.loads(conn.execute(
        "SELECT relationships FROM wiring_registry WHERE entity_id='dispatch_event-task-xyz'"
    ).fetchone()[0])
    assert rel[0]["dispatched_by"] == "dispatch-tick.py:gap_queue"
    assert rel[0]["source_queue_or_plan"] == "gap_queue.yaml"
    assert rel[0]["worker_unit"] == "veridian-worker@task-xyz.service"
    conn.close()


# Pre-migration entity_type CHECK constraint: WIRING_ENTITY_TYPES minus
# 'dispatch_event', which is exactly what real production's wiring_registry
# table looks like today (created before the 2026-07-27 dispatch-script
# consolidation added 'dispatch_event'). Field-for-field identical to
# _ensure_wiring_registry_table()'s DDL otherwise -- only the CHECK list
# differs -- so this is a faithful pre-migration fixture, not a simplified one.
_PRE_MIGRATION_ENTITY_TYPES = (
    "engine", "gateway", "supabase_table", "function", "route", "file", "script", "cron_job",
    "ai_role", "vercel_project", "github_repo", "browser_component",
)


def _seed_pre_migration_wiring_registry_db(db_path):
    """Creates a throwaway sqlite file whose wiring_registry table has the
    real, narrower, pre-migration entity_type CHECK constraint (no
    'dispatch_event') -- the actual shape production's DB has today -- so
    tests against it exercise the real migration path, not a fresh DB that
    already has the widened CHECK baked in from WIRING_ENTITY_TYPES."""
    entity_types_sql = ",".join("'" + t + "'" for t in _PRE_MIGRATION_ENTITY_TYPES)
    conn = sqlite3.connect(db_path)
    conn.executescript(f"""
    CREATE TABLE wiring_registry (
        entity_id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        entity_type TEXT NOT NULL CHECK(entity_type IN ({entity_types_sql})),
        source_system TEXT NOT NULL CHECK(source_system IN ('server','vercel','supabase','github')),
        path TEXT,
        relationships TEXT NOT NULL DEFAULT '[]',
        last_verified_ts TEXT NOT NULL,
        verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED'
            CHECK(verification_status IN ('VERIFIED_MATCH','HASH_DRIFTED','PATH_MISSING','UNVERIFIED')),
        source_ref TEXT NOT NULL DEFAULT '[]',
        metadata_json TEXT NOT NULL DEFAULT '{{}}'
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
    """)
    # A real pre-existing row, proving the migration's copy-across-unchanged
    # step (INSERT INTO wiring_registry__migrate SELECT ... FROM
    # wiring_registry) preserves real data, not just that the table swap works
    # on an empty table.
    conn.execute(
        "INSERT INTO wiring_registry (entity_id, ts, entity_type, source_system, path, "
        "relationships, last_verified_ts, verification_status, source_ref, metadata_json) "
        "VALUES ('cron_job-preexisting', '2026-07-01T00:00:00+00:00', 'cron_job', 'server', "
        "'scripts/preexisting.py', '[]', '2026-07-01T00:00:00+00:00', 'VERIFIED_MATCH', '[]', '{}')"
    )
    conn.commit()
    conn.close()


def test_dispatch_core_record_dispatch_event_migrates_pre_existing_narrow_check_schema(tmp_path, monkeypatch):
    """Regression test for the real bug this task fixes: _upsert_wiring_row()
    used to call ONLY _ensure_wiring_registry_table() (a bare CREATE TABLE IF
    NOT EXISTS -- a no-op against an already-existing table), never the real
    _migrate_schema()/_migrate_wiring_registry_entity_types() CHECK-widening
    migration. Against a fixture DB seeded with the REAL pre-migration
    (narrower) entity_type CHECK constraint -- matching what production's DB
    looks like today -- record_dispatch_event()'s INSERT of an entity_type=
    'dispatch_event' row used to raise sqlite3.IntegrityError ('CHECK
    constraint failed: entity_type IN (...)'), silently swallowed by
    record_dispatch_event()'s own best-effort try/except, so the row was NEVER
    written. This asserts the write actually succeeds and the row is genuinely
    queryable afterward -- not just that no exception propagated out to the
    caller (that would also pass with the swallowed-exception bug present)."""
    work, env = build_fixture_tree(tmp_path)
    db_path = env["SUPERBOSS_REGISTER_DB"]
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    _seed_pre_migration_wiring_registry_db(db_path)
    dc = _load_dispatch_core(work, env, monkeypatch)

    dc.record_dispatch_event(task_id="task-premig", dispatched_by="dispatch-tick.py:gap_queue",
                              source_queue_or_plan="gap_queue.yaml",
                              worker_unit="veridian-worker@task-premig.service")

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT entity_type, relationships FROM wiring_registry WHERE entity_id='dispatch_event-task-premig'"
    ).fetchone()
    assert row is not None, (
        "dispatch_event row was not written against a pre-migration-schema DB -- "
        "the CHECK constraint was never widened before the write"
    )
    assert row[0] == "dispatch_event"
    rel = json.loads(row[1])
    assert rel[0]["dispatched_by"] == "dispatch-tick.py:gap_queue"
    assert rel[0]["worker_unit"] == "veridian-worker@task-premig.service"

    # The pre-existing row must have survived the migration's table rebuild
    # unchanged -- proving this is a real ALTER-equivalent migration, not a
    # DROP+recreate that would have silently lost production's 7000+ rows.
    preexisting = conn.execute(
        "SELECT entity_type FROM wiring_registry WHERE entity_id='cron_job-preexisting'"
    ).fetchone()
    assert preexisting is not None and preexisting[0] == "cron_job"
    conn.close()


def test_dispatch_core_record_tick_is_best_effort_never_raises(tmp_path, monkeypatch):
    """A wiring_registry write failure must never propagate into the real
    dispatch tick it only instruments (same 'fails open' principle
    run-logged.sh already applies to its own logging)."""
    work, env = build_fixture_tree(tmp_path)
    # Point SUPERBOSS_REGISTER_DB at an unwritable location to force a failure.
    env["SUPERBOSS_REGISTER_DB"] = "/nonexistent-dir-xyz/does-not-exist.sqlite"
    dc = _load_dispatch_core(work, env, monkeypatch)
    dc.record_tick("dispatch-tick", status="ok")  # must not raise
    dc.record_dispatch_event(task_id="t1", dispatched_by="x", source_queue_or_plan="y", worker_unit="z")  # must not raise


def _race_worker(work_str, env, cap, results_dir, idx):
    """Run in a real, separate OS process (see test below). Mirrors the exact
    pattern dispatch-tick.py/phase-continuation-tick.py use at every real spawn
    call site: acquire the shared lock, check the shared cap, and only if a
    slot is free, perform the 'spawn' (append this worker's own unit name to
    the shared running-units file) -- all while still holding the lock, so the
    next racer's running_worker_count() is guaranteed to see it."""
    from pathlib import Path
    for k, v in env.items():
        os.environ[k] = v
    os.environ["VERIDIAN_DISPATCH_CONCURRENCY_CAP"] = str(cap)
    spec = importlib.util.spec_from_file_location(
        f"dispatch_core_race_{idx}", str(Path(work_str) / "scripts" / "dispatch_core.py"))
    dc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dc)
    dc.CONCURRENCY_CAP = cap

    units_file = Path(env["MOCK_RUNNING_UNITS_FILE"])
    with dc.acquire_dispatch_lock():
        spawned = dc.has_free_slot()
        if spawned:
            with open(units_file, "a") as f:
                f.write(f"veridian-worker@race-{idx}\n")
    with open(f"{results_dir}/{idx}.json", "w") as f:
        json.dump({"idx": idx, "spawned": spawned}, f)


def test_dispatch_core_concurrency_real_processes_enforce_shared_cap(tmp_path):
    """Real multi-process concurrency test (not a single-process unit test of
    the lock in isolation): N real OS processes race to acquire
    dispatch_core.acquire_dispatch_lock() and 'spawn' at the same time.
    Asserts exactly CAP of them succeed -- proving the shared lock closes the
    TOCTOU race queue-dispatcher.py/module-queue-dispatcher.py each had
    independently (check free slot, then spawn, as two separate unlocked
    steps) that this task's SPEC names as the real root cause."""
    work, env = build_fixture_tree(tmp_path)
    units_file = work / "units.txt"
    units_file.write_text("")
    env["MOCK_RUNNING_UNITS_FILE"] = str(units_file)
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    cap = 3
    n_racers = 10
    ctx = multiprocessing.get_context("fork")
    procs = [
        ctx.Process(target=_race_worker, args=(str(work), env, cap, str(results_dir), i))
        for i in range(n_racers)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=30)
        assert p.exitcode == 0

    outcomes = [json.loads((results_dir / f"{i}.json").read_text()) for i in range(n_racers)]
    spawned_count = sum(1 for o in outcomes if o["spawned"])

    assert spawned_count == cap, (
        f"expected exactly {cap} of {n_racers} racing processes to win a slot under the shared "
        f"lock, got {spawned_count} -- the shared cap was not correctly enforced under real "
        f"concurrent contention"
    )
    # The real running-units file must show exactly `cap` real spawned units,
    # matching the model's own accounting -- no double-count, no lost update.
    assert len([l for l in units_file.read_text().splitlines() if l.strip()]) == cap
