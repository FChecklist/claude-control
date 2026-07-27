import json, subprocess, sys, os, re

objectives = {o["key"]: o for o in json.load(open("objectives_45.json"))}
sys.path.insert(0, ".")
from classifications import CLASSIFICATIONS
from build_dispatch_prompts import REPO_MAP

os.makedirs("dispatch_logs", exist_ok=True)

def run_submit(key):
    prompt = open(f"dispatch_prompts/{key}.md").read()
    session_id = f"tier3-relevance-triage-2026-07-26-{key}"
    proc = subprocess.run(
        ["python3", "/opt/veridian/scripts/task-gateway.py", "submit",
         "--text", prompt, "--source", "ai_agent", "--session-id", session_id],
        capture_output=True, text=True,
    )
    with open(f"dispatch_logs/{key}.submit.log", "w") as f:
        f.write("RC: %d\n" % proc.returncode)
        f.write("STDOUT:\n" + proc.stdout + "\n")
        f.write("STDERR:\n" + proc.stderr + "\n")
    instruction_id = None
    if proc.returncode == 0:
        try:
            data = json.loads(proc.stdout)
            instruction_id = data.get("instruction_id")
        except json.JSONDecodeError:
            pass
    return proc.returncode, instruction_id

def run_start(key, instruction_id):
    repo = REPO_MAP[key]
    title = CLASSIFICATIONS[key]["title"][:120]
    prompt_file = f"dispatch_prompts/{key}.md"
    proc = subprocess.run(
        ["python3", "/opt/veridian/scripts/task-gateway.py", "start",
         "--instruction-id", str(instruction_id), "--title", title,
         "--repo", repo, "--prompt-file", prompt_file],
        capture_output=True, text=True,
    )
    with open(f"dispatch_logs/{key}.start.log", "w") as f:
        f.write("RC: %d\n" % proc.returncode)
        f.write("STDOUT:\n" + proc.stdout + "\n")
        f.write("STDERR:\n" + proc.stderr + "\n")
    task_id = None
    if proc.returncode == 0:
        m = re.search(r"CREATED:\s*(\S+)", proc.stdout)
        if m:
            task_id = m.group(1)
        else:
            try:
                data = json.loads(proc.stdout)
                task_id = data.get("task_id")
            except Exception:
                pass
    return proc.returncode, task_id, proc.stdout[-1500:], proc.stderr[-1500:]

if __name__ == "__main__":
    key = sys.argv[1]
    rc1, iid = run_submit(key)
    print(f"[{key}] submit rc={rc1} instruction_id={iid}")
    if rc1 != 0 or not iid:
        print("SUBMIT FAILED, see dispatch_logs/%s.submit.log" % key)
        sys.exit(1)
    rc2, tid, tail_out, tail_err = run_start(key, iid)
    print(f"[{key}] start rc={rc2} task_id={tid}")
    if rc2 != 0:
        print("START TAIL STDOUT:", tail_out)
        print("START TAIL STDERR:", tail_err)
    result = {"key": key, "instruction_id": iid, "start_rc": rc2, "task_id": tid}
    with open(f"dispatch_logs/{key}.result.json", "w") as f:
        json.dump(result, f, indent=2)
