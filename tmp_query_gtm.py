import sqlite3
conn = sqlite3.connect('/opt/veridian/ai-os/memory/superboss-register.sqlite')
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT category_index, category_name, passed, evidence_summary, validated_at, fix_pr_number, fix_commit FROM gtm_certification_categories ORDER BY category_index').fetchall()
for r in rows:
    print(r['category_index'], '|', r['category_name'], '| passed=', r['passed'], '| validated_at=', r['validated_at'], '| pr=', r['fix_pr_number'])
    print('   evidence:', (r['evidence_summary'] or '')[:250])
