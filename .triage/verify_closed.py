import json
d = json.load(open('closed_vs.json'))
nums = {p['number'] for p in d}
expected = [169,81,84,83,108,216,207] + [24,28,74,75,80,89,94,101,113,182,183,203,209,215,219,220,222,223,225,226,229,236,239,240,243,267]
missing = [n for n in expected if n not in nums]
print('total expected', len(expected))
print('missing from closed list', missing)
