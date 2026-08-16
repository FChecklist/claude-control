import json

def load_concat_arrays(path):
    data = open(path).read()
    dec = json.JSONDecoder()
    idx = 0
    items = []
    n = len(data)
    while idx < n:
        while idx < n and data[idx] in ' \t\r\n':
            idx += 1
        if idx >= n:
            break
        obj, end = dec.raw_decode(data, idx)
        if isinstance(obj, list):
            items.extend(obj)
        else:
            items.append(obj)
        idx = end
    return items

vs = load_concat_arrays('vs_all.json')
cc = load_concat_arrays('cc_all.json')
print('vs total open', len(vs))
print('cc total open', len(cc))

CUTOFF = '2026-08-08T00:00:00Z'

def simplify(p):
    return {
        'number': p['number'],
        'title': p['title'],
        'updated_at': p['updated_at'],
        'created_at': p['created_at'],
        'head_ref': p['head']['ref'],
        'head_sha': p['head']['sha'],
        'base_ref': p['base']['ref'],
        'url': p['html_url'],
        'body': p.get('body') or '',
    }

vs_simple = [simplify(p) for p in vs]
cc_simple = [simplify(p) for p in cc]

vs_old = sorted([p for p in vs_simple if p['updated_at'] < CUTOFF], key=lambda p: p['number'])
cc_old = sorted([p for p in cc_simple if p['updated_at'] < CUTOFF], key=lambda p: p['number'])

print('vs_old count', len(vs_old))
print('cc_old count', len(cc_old))

with open('vs_old.json', 'w') as f:
    json.dump(vs_old, f, indent=2)
with open('cc_old.json', 'w') as f:
    json.dump(cc_old, f, indent=2)

for p in vs_old:
    print('vs', p['number'], p['updated_at'], p['head_ref'])
print('---')
for p in cc_old:
    print('cc', p['number'], p['updated_at'], p['head_ref'])
