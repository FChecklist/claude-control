import json
d = json.load(open("/opt/veridian/ai-os/tasks/task-20260815-215959-rca-and-resume--gtm-certification-worker/workspace/tmp_secaudit/trivy.json"))
for res in d.get("Results") or []:
    for v in res.get("Vulnerabilities") or []:
        if v.get("Severity") in ("HIGH", "CRITICAL"):
            print(json.dumps(v, indent=2))
    print("TARGET:", res.get("Target"), "CLASS:", res.get("Class"), "TYPE:", res.get("Type"))
