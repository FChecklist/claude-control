import json, yaml, os

TASKS_ROOT = "/opt/veridian/ai-os/tasks"
# NOTE: this script now lives in scripts/batch45/ (moved 2026-08-18, see AGENTS.md
# "Report filing rules"); repo-root-relative paths below were updated accordingly.
audit = json.load(open('../../ai-os/TASK_COMPLETION_AUDIT_2026-07-26.json'))
ids = {r['task_id']: r for r in audit['rows']}
bucket = json.load(open('bucket_result.json'))

def in_window_not_merged(entries):
    out = []
    for e in bucket_entries(entries):
        r = ids.get(e['task_id'])
        if r and r['real_verified_status'] != 'MERGED':
            out.append(e)
    return out

def bucket_entries(entries):
    return [e for e in entries if e['task_id'] in ids]

cr = in_window_not_merged(bucket['credit_accountant_rejected'])
orx = in_window_not_merged(bucket['openrouter_balance_exhausted'])

print(len(cr), len(orx), len(cr)+len(orx))

full = []
for gate, lst in [('credit_accountant_rejected', cr), ('openrouter_balance_exhausted', orx)]:
    for e in lst:
        tid = e['task_id']
        tdir = os.path.join(TASKS_ROOT, tid)
        prompt_path = os.path.join(tdir, 'prompt.txt')
        prompt = ''
        if os.path.isfile(prompt_path):
            prompt = open(prompt_path, errors='replace').read()
        full.append({
            'task_id': tid,
            'title': e['title'],
            'gate': gate,
            'repo': ids[tid]['repo'],
            'created_at': ids[tid]['created_at'],
            'recorded_status': ids[tid]['recorded_status'],
            'real_verified_status': ids[tid]['real_verified_status'],
            'last_note': e['note'],
            'prompt_excerpt': prompt[:2000],
            'prompt_len': len(prompt),
        })

with open('triage_45.json', 'w') as f:
    json.dump(full, f, indent=2)

print("Saved", len(full), "tasks")
