"""Tests for scripts/resource_governor.py (SERVER RESOURCE GOVERNOR, Owner
directive 2026-07-27). Run with:
    python3 -m pytest tests/ -k resource_governor -v

Covers, per this task's own SUCCESS_CRITERIA: duplicate-submission rejection
(the count-based-cap-insufficient scenario -- rapid-fire duplicate
submissions of the same issue within a short window must produce exactly one
queued/running entry, not N), a real per-metric-99%-freezes-queue scenario
(all 4 metrics independently), the stuck-task SIGTERM/SIGKILL escalation
timing, and the UMR migration-against-pre-existing-schema test. Also covers
dynamic realignment (anti-starvation aging) and the emergency fail-safe
cascade (shed-load + hard-stop), plus one real end-to-end dispatch proving
dispatch_core.py's shared lock/cap/record_dispatch_event integration still
fires for real, not stubbed out.
"""
import concurrent.futures
import importlib.util
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _resource_governor_fixtures import build_governor_fixture_tree, run_script  # noqa: E402


def _load_resource_governor(work, env, monkeypatch):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location("resource_governor_test", str(work / "scripts" / "resource_governor.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _table_names(db_path):
    conn = sqlite3.connect(db_path)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    return names


def _umr_statuses(db_path, task_identity):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT status FROM umr_tasks WHERE task_identity=?", (task_identity,)).fetchall()
    conn.close()
    return [r["status"] for r in rows]


# ---------------------------------------------------------------------------
# UMR migration against a REAL pre-existing (non-fresh) schema
# ---------------------------------------------------------------------------

def test_umr_migration_against_pre_existing_schema(tmp_path, monkeypatch):
    """Regression-shaped test for the exact mistake PR #101 already had to fix
    once (schema-mismatch bug: a bare CREATE TABLE IF NOT EXISTS is a no-op
    against an already-existing DB that predates the new table/column).
    Simulates "this DB was created before the UMR migration existed" by
    suppressing _ensure_umr_table during a real init_db() run -- every OTHER
    real tree (instructions/work_items/actions/wiring_registry/
    knowledge_engine/capability_registry/route_replay) is created exactly as
    production's DB has them today, seeded with one real pre-existing row --
    then restores the real function and runs the real _migrate_schema()."""
    work, env = build_governor_fixture_tree(tmp_path)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location("sbr_premigration_test", str(work / "scripts" / "superboss-register.py"))
    sbr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sbr)

    real_ensure_umr = sbr._ensure_umr_table
    sbr._ensure_umr_table = lambda conn: None
    sbr.init_db()

    conn = sbr._connect()
    conn.execute(
        "INSERT INTO knowledge_engine (artifact_id, ts, artifact_path, content_hash, artifact_type, purpose, "
        "entity_relationships, last_verified_ts, verification_status, metadata_json) VALUES "
        "('ART-preexisting', '2026-07-01T00:00:00+00:00', 'ai-os/some.yaml', 'deadbeef', 'canonical', "
        "'pre-existing row proving real data survives the migration', '[]', '2026-07-01T00:00:00+00:00', "
        "'VERIFIED_MATCH', '{}')"
    )
    conn.commit()
    conn.close()

    tables_before = _table_names(env["SUPERBOSS_REGISTER_DB"])
    assert "umr_tasks" not in tables_before, "fixture setup bug: umr_tasks must not exist yet in the pre-migration DB"
    assert "knowledge_engine" in tables_before

    sbr._ensure_umr_table = real_ensure_umr  # restore the real migration
    conn = sbr._connect()
    sbr._migrate_schema(conn)  # the real idempotent-migration path
    conn.close()

    tables_after = _table_names(env["SUPERBOSS_REGISTER_DB"])
    assert "umr_tasks" in tables_after, "umr_tasks was not created by the real migration against a pre-existing DB"

    conn = sbr._connect()
    preexisting = conn.execute(
        "SELECT artifact_id FROM knowledge_engine WHERE artifact_id='ART-preexisting'"
    ).fetchone()
    assert preexisting is not None, "migration must not disturb real pre-existing data in unrelated trees"

    umr_id = sbr.upsert_umr_task(conn, {
        "task_identity": "task-post-migration", "tier": 2, "status": "queued",
        "source_trigger": "test", "unit_name": "veridian-worker@task-post-migration.service",
    })
    conn.commit()
    row = conn.execute("SELECT * FROM umr_tasks WHERE umr_id=?", (umr_id,)).fetchone()
    conn.close()
    assert row is not None, "a real row must be insertable into umr_tasks immediately after migration"

    # Idempotency: running the migration again against the now-migrated DB must not raise or duplicate.
    conn = sbr._connect()
    sbr._migrate_schema(conn)
    conn.close()
    assert _table_names(env["SUPERBOSS_REGISTER_DB"]) == tables_after


# ---------------------------------------------------------------------------
# Duplicate-submission rejection -- the specific fix for the watchdog incident
# ---------------------------------------------------------------------------

def test_submit_dedup_rejects_rapid_fire_duplicate_submissions(tmp_path, monkeypatch):
    """The count-based-cap-insufficient scenario from this task's own SCOPE:
    dispatch_core.py's shared cap only ever sees concurrent unit COUNT, so a
    trigger firing 10 times within a short window for the SAME task_identity
    (exactly what veridian-task-watchdog.timer did every 60s for 9h18m) must
    still produce exactly one queued/running entry, never N."""
    work, env = build_governor_fixture_tree(tmp_path)
    rg = _load_resource_governor(work, env, monkeypatch)

    task_spec = {
        "task_identity": "task-watchdog-incident",
        "task_kind": "systemctl_action",
        "unit_name": "veridian-worker@task-watchdog-incident.service",
        "inputs": {"action": "restart"},
    }
    results = [rg.submit(task_spec, tier=2, source_trigger="veridian-task-watchdog") for _ in range(10)]

    accepted = [r for r in results if r["accepted"]]
    rejected = [r for r in results if not r["accepted"]]
    assert len(accepted) == 1, f"expected exactly 1 accepted of 10 rapid-fire duplicates, got {len(accepted)}"
    assert len(rejected) == 9
    assert all("duplicate submission rejected" in r["reason"] for r in rejected)

    statuses = _umr_statuses(env["SUPERBOSS_REGISTER_DB"], "task-watchdog-incident")
    assert len(statuses) == 10, "rejected duplicates must be LOGGED as real rows, never silently dropped"
    assert statuses.count("queued") == 1
    assert statuses.count("rejected_duplicate") == 9


def test_submit_does_not_dedup_across_different_task_identities(tmp_path, monkeypatch):
    work, env = build_governor_fixture_tree(tmp_path)
    rg = _load_resource_governor(work, env, monkeypatch)

    r1 = rg.submit({"task_identity": "task-a", "task_kind": "systemctl_action", "unit_name": "u-a",
                     "inputs": {"action": "restart"}}, tier=2, source_trigger="test")
    r2 = rg.submit({"task_identity": "task-b", "task_kind": "systemctl_action", "unit_name": "u-b",
                     "inputs": {"action": "restart"}}, tier=2, source_trigger="test")
    assert r1["accepted"] and r2["accepted"]


def test_submit_allows_resubmission_once_prior_entry_reaches_a_terminal_state(tmp_path, monkeypatch):
    """De-dup only blocks ACTIVE (queued/dispatched/running) entries -- once a
    prior submission for the same identity has reached completed/failed/
    killed/rejected_duplicate, a fresh real recovery attempt must not be
    permanently locked out."""
    work, env = build_governor_fixture_tree(tmp_path)
    rg = _load_resource_governor(work, env, monkeypatch)
    sbr = rg._superboss_register()

    r1 = rg.submit({"task_identity": "task-c", "task_kind": "systemctl_action", "unit_name": "u-c",
                     "inputs": {"action": "restart"}}, tier=2, source_trigger="test")
    assert r1["accepted"]

    conn = sbr._connect()
    with sbr._write_lock():
        sbr.update_umr_task(conn, r1["umr_id"], status="completed")
        conn.commit()
    conn.close()

    r2 = rg.submit({"task_identity": "task-c", "task_kind": "systemctl_action", "unit_name": "u-c",
                     "inputs": {"action": "restart"}}, tier=2, source_trigger="test")
    assert r2["accepted"], "a resubmission after the prior entry reached a terminal state must be allowed"


# ---------------------------------------------------------------------------
# Real per-metric 99% hard cap -- any ONE metric freezes the queue
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("metric", ["cpu", "ram", "disk_io", "network"])
def test_any_single_metric_at_99_percent_freezes_the_queue(tmp_path, monkeypatch, metric):
    work, env = build_governor_fixture_tree(tmp_path)
    rg = _load_resource_governor(work, env, monkeypatch)

    metrics = {"cpu": 10.0, "ram": 10.0, "disk_io": 10.0, "network": 10.0}
    metrics[metric] = 99.5
    monkeypatch.setattr(rg, "sample_metrics", lambda now=None: metrics)

    submitted = rg.submit(
        {"task_identity": "task-frozen", "task_kind": "systemctl_action",
         "unit_name": "veridian-worker@task-frozen.service", "inputs": {"action": "start"}},
        tier=2, source_trigger="test",
    )
    assert submitted["accepted"]

    result = rg.dispatch_one()
    assert result["action"] == "frozen"
    assert metric in result["detail"]

    statuses = _umr_statuses(env["SUPERBOSS_REGISTER_DB"], "task-frozen")
    assert statuses == ["queued"], "a frozen tick must never dispatch the queued item"


def test_all_metrics_under_threshold_does_not_freeze(tmp_path, monkeypatch):
    work, env = build_governor_fixture_tree(tmp_path)
    rg = _load_resource_governor(work, env, monkeypatch)
    monkeypatch.setattr(rg, "sample_metrics", lambda now=None: {"cpu": 98.9, "ram": 1.0, "disk_io": 1.0, "network": 1.0})
    assert rg.over_threshold_metrics(rg.sample_metrics()) == []


def test_dispatch_proceeds_via_real_dispatch_core_when_metrics_are_clear(tmp_path, monkeypatch):
    """Proves the governor's dispatch path is a real integration with
    dispatch_core.py -- not stubbed out -- when nothing is frozen: the real
    shared lock/cap gate a real systemctl start, and record_dispatch_event()
    writes a real wiring_registry row exactly as every other consolidated
    tick script's own dispatch call site does."""
    work, env = build_governor_fixture_tree(tmp_path)
    units_file = work / "units.txt"
    units_file.write_text("")
    env["MOCK_RUNNING_UNITS_FILE"] = str(units_file)
    rg = _load_resource_governor(work, env, monkeypatch)
    monkeypatch.setattr(rg, "sample_metrics", lambda now=None: {"cpu": 5.0, "ram": 5.0, "disk_io": 5.0, "network": 5.0})

    rg.submit({"task_identity": "task-clear", "task_kind": "systemctl_action",
               "unit_name": "veridian-worker@task-clear.service", "inputs": {"action": "start"}},
              tier=2, source_trigger="test")

    result = rg.dispatch_one()
    assert result["action"] == "dispatched"
    assert result["result"]["status"] == "running"
    assert "veridian-worker@task-clear.service" in units_file.read_text()

    conn = sqlite3.connect(env["SUPERBOSS_REGISTER_DB"])
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT status, unit_name FROM umr_tasks WHERE task_identity='task-clear'").fetchone()
    wiring = conn.execute("SELECT entity_id FROM wiring_registry WHERE entity_id LIKE 'dispatch_event-%'").fetchall()
    conn.close()
    assert row["status"] == "running"
    assert len(wiring) == 1, "dispatch_core.record_dispatch_event must fire for a real governor dispatch"


# ---------------------------------------------------------------------------
# Stuck-task SIGTERM/SIGKILL escalation timing
# ---------------------------------------------------------------------------

def test_stuck_task_sigterm_then_sigkill_escalation_timing(tmp_path, monkeypatch):
    work, env = build_governor_fixture_tree(tmp_path)
    kill_log = work / "kills.log"
    ts_file = work / "unit_timestamps.txt"
    env["MOCK_KILL_LOG"] = str(kill_log)
    env["MOCK_UNIT_TIMESTAMPS_FILE"] = str(ts_file)
    env["VERIDIAN_GOVERNOR_STUCK_TIMEOUT_S"] = "600"
    env["VERIDIAN_GOVERNOR_SIGKILL_GRACE_S"] = "60"
    rg = _load_resource_governor(work, env, monkeypatch)
    assert rg.STUCK_TASK_TIMEOUT_SECONDS == 600
    assert rg.SIGTERM_TO_SIGKILL_GRACE_SECONDS == 60

    unit = "veridian-worker@task-stuck.service"
    started_at = datetime(2026, 7, 27, 0, 0, 0, tzinfo=timezone.utc)
    ts_file.write_text(f"{unit}=2026-07-27 00:00:00 UTC\n")

    sbr = rg._superboss_register()
    conn = sbr._connect()
    sbr._ensure_umr_table(conn)
    umr_id = sbr.upsert_umr_task(conn, {
        "task_identity": "task-stuck", "tier": 2, "status": "running",
        "source_trigger": "test", "unit_name": unit, "ts_dispatched": started_at.isoformat(),
    })
    conn.commit()
    conn.close()

    # Before the timeout: nothing happens.
    actions = rg.scan_stuck_tasks(now=started_at + timedelta(seconds=300))
    assert actions == []
    assert not kill_log.exists()

    # At/after the timeout: real SIGTERM.
    actions = rg.scan_stuck_tasks(now=started_at + timedelta(seconds=600))
    assert len(actions) == 1 and actions[0]["action"] == "SIGTERM"
    assert f"SIGTERM {unit}" in kill_log.read_text()

    conn = sbr._connect()
    row = conn.execute("SELECT status, ts_sigterm FROM umr_tasks WHERE umr_id=?", (umr_id,)).fetchone()
    conn.close()
    assert row["status"] == "sigterm_sent"
    ts_sigterm = datetime.fromisoformat(row["ts_sigterm"])

    # Within the 60s grace period: no SIGKILL yet.
    actions = rg.scan_stuck_tasks(now=ts_sigterm + timedelta(seconds=30))
    assert actions == []
    assert "SIGKILL" not in kill_log.read_text()

    # After the grace period: real SIGKILL.
    actions = rg.scan_stuck_tasks(now=ts_sigterm + timedelta(seconds=61))
    assert len(actions) == 1 and actions[0]["action"] == "SIGKILL"
    assert f"SIGKILL {unit}" in kill_log.read_text()

    conn = sbr._connect()
    row = conn.execute("SELECT status FROM umr_tasks WHERE umr_id=?", (umr_id,)).fetchone()
    conn.close()
    assert row["status"] == "killed"


# ---------------------------------------------------------------------------
# Dynamic realignment (anti-starvation aging)
# ---------------------------------------------------------------------------

def test_effective_priority_ages_a_stale_low_tier_item_toward_higher_priority(tmp_path, monkeypatch):
    work, env = build_governor_fixture_tree(tmp_path)
    env["VERIDIAN_GOVERNOR_AGING_INTERVAL_S"] = "900"  # 15 min
    rg = _load_resource_governor(work, env, monkeypatch)

    now = datetime(2026, 7, 27, 12, 0, 0, tzinfo=timezone.utc)
    fresh = {"tier": 3, "ts_submitted": now.isoformat()}
    aged_45min = {"tier": 3, "ts_submitted": (now - timedelta(minutes=45)).isoformat()}

    assert rg.effective_priority(fresh, now=now) == 3
    assert rg.effective_priority(aged_45min, now=now) == 0  # 3 intervals of promotion, floored at TIER_MIN


def test_next_queued_task_prefers_aged_low_tier_over_fresh_high_tier_once_promoted(tmp_path, monkeypatch):
    work, env = build_governor_fixture_tree(tmp_path)
    env["VERIDIAN_GOVERNOR_AGING_INTERVAL_S"] = "900"
    rg = _load_resource_governor(work, env, monkeypatch)
    sbr = rg._superboss_register()

    now = datetime(2026, 7, 27, 12, 0, 0, tzinfo=timezone.utc)
    conn = sbr._connect()
    sbr._ensure_umr_table(conn)
    old_ts = (now - timedelta(minutes=45)).isoformat()
    sbr.upsert_umr_task(conn, {"task_identity": "stale-maintenance", "tier": 3, "status": "queued",
                                "source_trigger": "test", "ts_submitted": old_ts})
    sbr.upsert_umr_task(conn, {"task_identity": "fresh-standard", "tier": 2, "status": "queued",
                                "source_trigger": "test", "ts_submitted": now.isoformat()})
    conn.commit()

    winner = rg.next_queued_task(conn, now=now)
    conn.close()
    assert winner["task_identity"] == "stale-maintenance", (
        "a tier-3 item queued 45 minutes ago (3 aging promotions -> effective tier 0) must win over a "
        "fresh tier-2 item -- anti-starvation aging is not working"
    )


# ---------------------------------------------------------------------------
# Emergency fail-safe cascade
# ---------------------------------------------------------------------------

def test_emergency_cascade_sheds_load_then_hard_stops_on_sustained_overload(tmp_path, monkeypatch):
    work, env = build_governor_fixture_tree(tmp_path)
    kill_log = work / "kills.log"
    env["MOCK_KILL_LOG"] = str(kill_log)
    env["VERIDIAN_GOVERNOR_EMERGENCY_SHED_TICKS"] = "3"
    env["VERIDIAN_GOVERNOR_EMERGENCY_HARDSTOP_TICKS"] = "6"
    rg = _load_resource_governor(work, env, monkeypatch)
    sbr = rg._superboss_register()

    conn = sbr._connect()
    sbr._ensure_umr_table(conn)
    sbr.upsert_umr_task(conn, {"task_identity": "task-victim", "tier": 4, "status": "running",
                                "source_trigger": "test", "unit_name": "veridian-worker@task-victim.service"})
    conn.commit()
    conn.close()

    assert not os.path.exists(rg.EMERGENCY_STOP_PATH)

    for _ in range(2):
        rg._record_emergency_tick(["cpu"])
    assert not kill_log.exists() or "SIGTERM" not in kill_log.read_text()

    rg._record_emergency_tick(["cpu"])  # 3rd consecutive tick -> shed load
    assert "SIGTERM veridian-worker@task-victim.service" in kill_log.read_text()
    assert not os.path.exists(rg.EMERGENCY_STOP_PATH)

    for _ in range(3):
        rg._record_emergency_tick(["cpu"])  # ticks 4,5,6 -> hard stop at 6
    assert os.path.exists(rg.EMERGENCY_STOP_PATH)

    # A tick with the metric back under threshold resets the counter and clearing removes the sentinel.
    rg.clear_emergency_stop()
    assert not os.path.exists(rg.EMERGENCY_STOP_PATH)


def test_emergency_stop_blocks_all_dispatch_including_tier_0_until_cleared(tmp_path, monkeypatch):
    work, env = build_governor_fixture_tree(tmp_path)
    rg = _load_resource_governor(work, env, monkeypatch)
    rg._save_json(rg.EMERGENCY_STOP_PATH, {"ts": "test", "state": {}})

    rg.submit({"task_identity": "task-emergency", "task_kind": "systemctl_action", "unit_name": "u",
               "inputs": {"action": "start"}}, tier=0, source_trigger="test")

    result = rg.dispatch_one()
    assert result["action"] == "emergency_stopped"

    rg.clear_emergency_stop()
    monkeypatch.setattr(rg, "sample_metrics", lambda now=None: {"cpu": 1.0, "ram": 1.0, "disk_io": 1.0, "network": 1.0})
    result = rg.dispatch_one()
    assert result["action"] != "emergency_stopped"


# ---------------------------------------------------------------------------
# Concurrent dispatch -- the real TOCTOU race the round-2 audit reproduced:
# dispatch_one() used to select the next queued row BEFORE acquiring
# dispatch_core.acquire_dispatch_lock(), so two concurrent callers could both
# select and spawn the SAME queued row.
# ---------------------------------------------------------------------------

def test_concurrent_dispatch_never_double_dispatches_the_same_queued_row(tmp_path, monkeypatch):
    """Two REAL subprocess `--tick` invocations (not just two threads inside
    one interpreter -- this is how the real cron/timer callers actually
    overlap) racing against the same fixture DB and the same dispatch_core
    lock file must produce exactly one real spawn for the one queued row:
    the other must observe it already claimed, never fire the real systemctl
    call a second time."""
    work, env = build_governor_fixture_tree(tmp_path)
    units_file = work / "units.txt"
    units_file.write_text("")
    systemctl_log = work / "systemctl.log"
    env["MOCK_RUNNING_UNITS_FILE"] = str(units_file)
    env["MOCK_SYSTEMCTL_LOG"] = str(systemctl_log)
    # Set unreachably high so real host load on the test box can never freeze
    # the queue -- the concurrency race is the only thing under test here.
    env["VERIDIAN_GOVERNOR_METRIC_THRESHOLD"] = "1000000"

    rg = _load_resource_governor(work, env, monkeypatch)
    rg.submit(
        {"task_identity": "task-race", "task_kind": "systemctl_action",
         "unit_name": "veridian-worker@task-race.service", "inputs": {"action": "start"}},
        tier=2, source_trigger="test",
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_script, work, env, "resource_governor.py", ["--tick"]) for _ in range(2)]
        results = [f.result(timeout=60) for f in futures]

    for r in results:
        assert r.returncode == 0, f"--tick subprocess failed: {r.stderr}"

    ticks = [json.loads(r.stdout) for r in results]
    race_dispatches = [
        d for tick in ticks for d in tick["dispatches"]
        if d["action"] == "dispatched" and d["result"].get("unit_name") == "veridian-worker@task-race.service"
    ]
    assert len(race_dispatches) == 1, (
        f"expected exactly 1 real dispatch of task-race across 2 concurrent --tick invocations, "
        f"got {len(race_dispatches)}: {race_dispatches}"
    )

    start_calls = [line for line in systemctl_log.read_text().splitlines()
                   if "start veridian-worker@task-race.service" in line]
    assert len(start_calls) == 1, (
        f"the real systemctl start call for task-race fired {len(start_calls)} times across the "
        f"concurrent tick -- the TOCTOU race was not closed: {systemctl_log.read_text()!r}"
    )

    statuses = _umr_statuses(env["SUPERBOSS_REGISTER_DB"], "task-race")
    assert statuses == ["running"], f"expected exactly one umr_tasks row left in status=running, got {statuses}"
