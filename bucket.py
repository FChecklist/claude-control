import yaml, json, glob, os

TASKS_ROOT = "/opt/veridian/ai-os/tasks"

credit_rej = []
openrouter_ex = []
other = []
errors = []

for d in sorted(glob.glob(os.path.join(TASKS_ROOT, "task-*"))):
    tid = os.path.basename(d)
    tyaml = os.path.join(d, "task.yaml")
    if not os.path.isfile(tyaml):
        continue
    try:
        with open(tyaml) as f:
            data = yaml.safe_load(f)
    except Exception as e:
        errors.append((tid, str(e)))
        continue
    checkpoints = data.get("checkpoints") or []
    if not checkpoints:
        continue
    last = checkpoints[-1]
    note = last.get("note") or ""
    entry = {
        "task_id": tid,
        "title": data.get("title"),
        "status": data.get("status"),
        "last_checkpoint_at": data.get("last_checkpoint_at"),
        "note": note,
    }
    if "credit_accountant_rejected" in note:
        credit_rej.append(entry)
    elif "openrouter_balance_exhausted" in note:
        openrouter_ex.append(entry)

print("credit_accountant_rejected:", len(credit_rej))
print("openrouter_balance_exhausted:", len(openrouter_ex))
print("total:", len(credit_rej) + len(openrouter_ex))
print("yaml errors:", len(errors))

with open("bucket_result.json", "w") as f:
    json.dump({"credit_accountant_rejected": credit_rej, "openrouter_balance_exhausted": openrouter_ex, "errors": errors}, f, indent=2)
