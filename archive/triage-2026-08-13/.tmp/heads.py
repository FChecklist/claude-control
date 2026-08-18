import json
d = json.load(open('.tmp/api_prs.json'))
for pr in d:
    print(pr['number'], pr['head']['sha'], pr['updated_at'])
