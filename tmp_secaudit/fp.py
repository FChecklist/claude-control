import json
d = json.load(open("tmp_secaudit/report.json"))
for f in d:
    print(f.get("Fingerprint"))
