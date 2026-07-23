# PROGRESS -- task-20260723-095201-gap-closing-phase2-sqlite-corruption-roo

## Completed
- [x] Confirmed current live db was actually corrupted right now (not just historically): `PRAGMA integrity_check` -> "Freelist: size is 0 but should be 1" via a plain read-write connection (not a WAL read-race false positive).
- [x] Read superboss-register.py in full (662 lines) and veridian-task.py's `_auto_log_task_event`/`_log_to_register` in full -- traced every write path.
- [x] Root-cause investigation, ruled in/out with real evidence:
  - Ruled OUT (confirmed via `mount`/grep by phase 1, re-confirmed): ext4 local disk, no missing WAL/busy_timeout, no raw-copy-into-live-path script.
  - Confirmed REAL defect #1: `veridian-task.py`'s `_auto_log_task_event` wraps every `superboss-register.py` subprocess call (fired every 5 min by EVERY active worker's background checkpoint loop, plus ad-hoc log-work/log-action calls) in `subprocess.run(..., timeout=10)` -- shorter than `superboss-register.py`'s own `sqlite3.connect(DB_PATH, timeout=30)` busy_timeout. A writer still legitimately inside its own 30s busy-wait can be SIGKILLed by its own caller at 10s, failure silently swallowed by `except Exception: pass`.
  - Confirmed REAL defect #2: no serialization existed across concurrent `superboss-register.py` writer processes -- all rely solely on SQLite's internal busy_timeout to arbitrate, unlike the proven `fcntl.flock`-based `controller_lock()` pattern already used for CONTROLLER.yaml (built after the 2026-07-18 CONTROLLER.yaml corruption incident).
  - Confirmed REAL, distinct defect #3 (FTS5-specific, in scope per task spec): `system_index` table's `index_add()` does an `ON CONFLICT(path) DO UPDATE` upsert, but `system_index_fts` (external-content FTS5) only had an `AFTER INSERT` sync trigger, no `AFTER UPDATE` -- every re-verification of an existing indexed path silently desynced the FTS shadow table.
  - HONESTY NOTE: attempted to reproduce actual db corruption via a blind concurrent-SIGKILL stress test (up to 150 concurrent `log-action` processes, sustained random kills over 3s, larger payloads to grow the WAL) against BOTH the pre-fix and post-fix code. Did NOT succeed in reproducing corruption on either version in the available test budget -- the vulnerable window (killed while actually holding the SQLite write lock mid-commit/mid-WAL-checkpoint) is narrow relative to process-startup overhead in a synthetic test. Full certainty on exact causal mechanism NOT reached. Defects #1/#2/#3 are real, code-evidenced, and directly consistent with phase 1's observation (an ordinary write coincided with the pass->fail integrity flip), and #1/#2 mirror an already-proven fix pattern in this exact codebase -- applied as the most defensible mitigation, not a guaranteed-proven root cause.
- [x] Fix implemented in `/opt/veridian/scripts/superboss-register.py`: added `_write_lock()` (fcntl.flock-based), wraps every write subcommand (init/log-instruction/log-work/log-action/index-add/log-execution/index-transcript) at CLI dispatch.
- [x] Fix implemented in `/opt/veridian/scripts/veridian-task.py`: raised `_auto_log_task_event`'s subprocess timeout from 10s to 35s (>30s busy_timeout + margin) for all 3 call sites (create/checkpoint/record_usage).
- [x] Fix implemented in `/opt/veridian/scripts/superboss-register.py`: added missing `system_index_au AFTER UPDATE` FTS5 sync trigger.
- [x] Functional verification: 40 concurrent `log-action` invocations against a scratch db with 20 SIGKILLed mid-flight at randomized delays -> `integrity_check` = ok, repeated across trials, with the fix applied.
- [x] Functional verification of FTS5 UPDATE-sync fix on a scratch db (old search term correctly disappears, new term appears after upsert).
- [x] Real repair performed on the live db, single sequential operation: quarantined corrupted file as `superboss-register.sqlite.CORRUPTED-2026-07-23-1000-freelist-mismatch`, ran `superboss-register.py init` (fixed code), recovered ALL 449 rows (235 instructions + 13 work_items + 169 actions + 32 system_index + 2 execution_log) from the quarantined file (data was still fully readable despite the freelist corruption) with zero data loss -- row counts and FTS parity verified to match exactly.
- [x] Post-repair smoke test via the real CLI: `search`, `log-action`, `check-duplicate` all work; `integrity_check` = ok.

## Remaining
- [ ] Observe across the next 15-min health-check cron cycle (next fires ~10:15 UTC) for real recurrence-free evidence, per task success criteria.
- [ ] Update `ai-os/MASTER_GAP_AUDIT_2026-07-23.yaml` source_3 finding with real before/after + append gap_closing_worker_log phase 2 entry.
- [ ] Commit + push.
- [ ] Checkpoint status=pending_review with evidence-cited note.
- [ ] Self-dispatch phase 3 continuing through remaining ai-os/MASTER_GAP_AUDIT_2026-07-23.yaml consolidated_summary items.
