import importlib.util as ilu
import sqlite3

spec = ilu.spec_from_file_location('sbr', '/opt/veridian/scripts/superboss-register.py')
m = ilu.module_from_spec(spec)
spec.loader.exec_module(m)
db = m.resolve_superboss_db_path()
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

for umr in ("UMR-20260813-134848-cb1d", "UMR-20260813-134908-e466", "UMR-20260813-104321-99ff"):
    r = conn.execute("SELECT umr_id, status, ts_dispatched, source_trigger FROM umr_tasks WHERE umr_id=?", (umr,)).fetchone()
    print(dict(r) if r else (umr, "NOT FOUND"))

print("--- real dispatches (ts_dispatched) in the last 15 minutes ---")
for r in conn.execute(
    "SELECT umr_id, status, ts_dispatched FROM umr_tasks WHERE ts_dispatched > '2026-08-13T13:35:00' ORDER BY ts_dispatched"
):
    print(dict(r))
