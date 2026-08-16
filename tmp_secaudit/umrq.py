import sqlite3
conn = sqlite3.connect('/opt/veridian/ai-os/memory/superboss-register.sqlite')
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT umr_id, status, reason, outputs_json FROM umr_tasks WHERE umr_id=?", ('UMR-20260805-112247-3ad0',)).fetchone()
print(dict(row) if row else 'not found')
