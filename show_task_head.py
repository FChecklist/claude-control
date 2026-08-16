import sys, yaml
task_id = sys.argv[1]
d = yaml.safe_load(open(f"/opt/veridian/ai-os/tasks/{task_id}/task.yaml"))
cps = d.get("checkpoints", [])
if cps:
    print("note:", cps[-1].get("note"))
    print("---recent_commits---")
    for c in cps[-1].get("recent_commits", []) or []:
        print(c)
else:
    print("no checkpoints")
