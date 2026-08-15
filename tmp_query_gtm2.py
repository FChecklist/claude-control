import sqlite3
conn = sqlite3.connect('/opt/veridian/ai-os/memory/superboss-register.sqlite')
conn.row_factory = sqlite3.Row
for idx in (3, 17, 23, 25, 10, 11, 13, 15, 16):
    r = conn.execute('SELECT * FROM gtm_certification_categories WHERE category_index=?', (idx,)).fetchone()
    print("="*20, idx, r['category_name'], "="*20)
    print("passed:", r['passed'])
    print("evidence_summary:", r['evidence_summary'])
    print("evidence_json:", r['evidence_json'] if 'evidence_json' in r.keys() else 'N/A')
    print()
