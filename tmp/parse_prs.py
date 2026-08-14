import json
d = json.load(open('tmp/open_prs.json'), strict=False)
print(len(d))
for p in d:
    print(p['number'], p['headRefName'], p['headRefOid'][:10], p['mergeable'], p['mergeStateStatus'])
