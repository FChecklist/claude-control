import importlib.util as ilu
import sqlite3

spec = ilu.spec_from_file_location('sbr', '/opt/veridian/scripts/superboss-register.py')
m = ilu.module_from_spec(spec)
spec.loader.exec_module(m)
db = m.resolve_superboss_db_path()
print('DB:', db)
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

print('--- status counts ---')
for r in conn.execute("SELECT status, COUNT(*) c FROM umr_tasks GROUP BY status ORDER BY c DESC"):
    print(dict(r))

print('--- queued with ts_dispatched NULL ---')
for r in conn.execute(
    "SELECT umr_id, task_identity, ts_submitted, ts_dispatched, task_kind, source_trigger "
    "FROM umr_tasks WHERE status='queued' AND ts_dispatched IS NULL ORDER BY ts_submitted"
):
    print(dict(r))

print('--- running rows with unit_name ---')
for r in conn.execute(
    "SELECT umr_id, unit_name, task_identity, ts_dispatched FROM umr_tasks "
    "WHERE status='running' ORDER BY ts_dispatched"
):
    print(dict(r))
