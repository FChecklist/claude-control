import json
data = json.load(open('.tmp/api_prs.json'))
print(len(data))
for pr in data:
    print(pr['number'], pr['head']['sha'][:10], pr['head']['ref'], pr['title'])
