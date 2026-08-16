import json
d = json.load(open("/opt/veridian/ai-os/tasks/task-20260815-215959-rca-and-resume--gtm-certification-worker/workspace/tmp_secaudit/trivy.json"))
for res in d.get("Results") or []:
    for v in res.get("Vulnerabilities") or []:
        if v.get("Severity") in ("HIGH", "CRITICAL"):
            print(v.get("Severity"), v.get("VulnerabilityID"), v.get("PkgName"), v.get("InstalledVersion"), "->", v.get("FixedVersion"))
