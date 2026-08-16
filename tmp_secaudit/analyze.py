import json
d = json.load(open("/opt/veridian/ai-os/tasks/task-20260815-215959-rca-and-resume--gtm-certification-worker/workspace/tmp_secaudit/report.json"))
for f in d:
    print(f.get("RuleID"), "|", f.get("File"), "|", (f.get("Secret") or "")[:40])
