import json, subprocess, sys

objectives = {o["key"]: o for o in json.load(open("objectives_45.json"))}
sys.path.insert(0, ".")
from classifications import CLASSIFICATIONS

open_keys = [k for k,v in CLASSIFICATIONS.items() if v["classification"] == "GENUINELY_STILL_OPEN"]

results = []
for key in open_keys:
    prompt = objectives[key]["prompt"]
    session_id = f"tier3-relevance-triage-2026-07-26-{key}"
    proc = subprocess.run(
        ["python3", "/opt/veridian/scripts/task-gateway.py", "submit",
         "--text", prompt, "--source", "ai_agent", "--session-id", session_id],
        capture_output=True, text=True,
    )
    print("=== ", key, " ===")
    print("rc:", proc.returncode)
    print("stdout:", proc.stdout[:2000])
    print("stderr:", proc.stderr[:2000])
    results.append({
        "key": key, "session_id": session_id, "rc": proc.returncode,
        "stdout": proc.stdout, "stderr": proc.stderr,
    })

with open("dispatch_results.json", "w") as f:
    json.dump(results, f, indent=2)
