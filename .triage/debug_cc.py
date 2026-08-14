import json
d = json.load(open('cc_classified.json'))
for p in d[:2]:
    print(p['number'], p['merge_base'])
    for f in p['files']:
        print('  ', f['path'])
