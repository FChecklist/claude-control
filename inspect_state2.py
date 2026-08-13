import importlib.util as ilu
import sqlite3

spec = ilu.spec_from_file_location('sbr', '/opt/veridian/scripts/superboss-register.py')
m = ilu.module_from_spec(spec)
spec.loader.exec_module(m)
db = m.resolve_superboss_db_path()
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

print('--- dispatched rows WITH a unit_name set (candidate for A, unit-not-active case) ---')
for r in conn.execute(
    "SELECT umr_id, unit_name, task_identity, ts_dispatched FROM umr_tasks "
    "WHERE status='dispatched' AND unit_name IS NOT NULL AND unit_name != '' ORDER BY ts_dispatched"
):
    print(dict(r))

print('--- running rows whose unit_name LIKE veridian-worker@% (reconcile_stale_running_workers.py scope) ---')
for r in conn.execute(
    "SELECT umr_id, unit_name FROM umr_tasks WHERE status='running' AND unit_name LIKE 'veridian-worker@%'"
):
    print(dict(r))
