#!/usr/bin/env python3
"""Real repair for the 2026-08-14 disk_low (and, for one task, a pre-2026-07-20
credit_accountant_rejected) infrastructure-rejection over-charging bug in
worker-entrypoint.sh's lifetime .invocation_count counter.

For each affected task, reconstructs the REAL invocation history from that task's
own task.yaml checkpoints (never guesses, never touches the live .invocation_count
value as an input) and derives the corrected count as:

    corrected = (# checkpoints that started a distinct script invocation)
              - (# of those whose note contains "no model call made, no cost incurred")

"Started a distinct script invocation" is recognized by note prefix:
  - "worker started" / "doc-worker started"   -> a REAL invocation (preflight passed)
  - "PRE-FLIGHT REJECTED"                      -> one invocation, preflight-rejected (transient)
  - "PRE-FLIGHT HARD STOP"                     -> one invocation, preflight-rejected (hard stop)
  - "PREVENTION CAP HIT"                       -> one invocation, cap already exceeded
Any other note (periodic checkpoint, worker exited with code N, pending_review,
completed, blocked-for-other-reasons, ...) is a CONTINUATION of an already-counted
invocation, not a new one, and is not counted again.

Only "PRE-FLIGHT REJECTED ... -- no model call made, no cost incurred" checkpoints
are discounted -- this is the literal, mechanical signal named in the task SPEC.
Hard-stop / cap-hit checkpoints are NOT discounted here even though they also never
called the model -- that is a deliberate, conservative, spec-scoped choice (the
mechanical text match is unambiguous; broadening it is a separate decision left for
a human to make explicitly via VERIDIAN_MAX_INFRA_REJECTIONS-style follow-up, not
silently folded into this repair).
"""
import os
import sys
import yaml

TASKS_DIR = "/opt/veridian/ai-os/tasks"
DISCOUNT_TEXT = "no model call made, no cost incurred"

AFFECTED_TASKS = [
    "task-20260718-171007-commercial--subscription---pricing-model",
    "task-20260807-062740-cleanup-closed-6-stale-awaiting-approval",
    "task-20260807-064722-retry-ai-documentation-lifecycle",
    "task-20260807-064727-retry-ai-documentation-ai-readable-techn",
    "task-20260807-071557-retry-ai-cost-governance-finops-cost-vis",
    "task-20260814-023018-live-deploy-drift-p0--the-live-veridian",
    "task-20260814-030259-live-deploy-drift-p0--the-live-veridian",
    "task-20260814-031827-rca--umr-20260807-153242-ee23-killed",
    "task-20260814-031834-rca--umr-20260807-151622-15cd-killed",
    "task-20260814-031840-rca--umr-20260807-063851-df5e-killed",
    "task-20260814-031847-rca--umr-20260807-063839-3e0e-killed",
]

START_PREFIXES = [
    "worker started",
    "doc-worker started",
    "PRE-FLIGHT REJECTED",
    "PRE-FLIGHT HARD STOP",
    "PREVENTION CAP HIT",
]


def classify(note):
    note = note or ""
    for prefix in START_PREFIXES:
        if note.startswith(prefix):
            is_discounted = DISCOUNT_TEXT in note
            return prefix, is_discounted
    return None, False


def analyze(task_id, apply_fix):
    task_dir = os.path.join(TASKS_DIR, task_id)
    yaml_path = os.path.join(task_dir, "task.yaml")
    count_path = os.path.join(task_dir, ".invocation_count")

    with open(yaml_path) as f:
        d = yaml.safe_load(f)
    checkpoints = d.get("checkpoints", [])

    before = None
    if os.path.exists(count_path):
        with open(count_path) as f:
            before = f.read().strip()

    starts_total = 0
    starts_discounted = 0
    breakdown = {}
    for c in checkpoints:
        prefix, discounted = classify(c.get("note", ""))
        if prefix is None:
            continue
        starts_total += 1
        breakdown[prefix] = breakdown.get(prefix, 0) + 1
        if discounted:
            starts_discounted += 1

    corrected = starts_total - starts_discounted

    result = {
        "task_id": task_id,
        "total_checkpoints": len(checkpoints),
        "starts_total": starts_total,
        "starts_discounted": starts_discounted,
        "breakdown": breakdown,
        "before": before,
        "corrected": corrected,
    }

    if apply_fix:
        with open(count_path, "w") as f:
            f.write(str(corrected) + "\n")
        result["written"] = True
    else:
        result["written"] = False

    return result


def main():
    apply_fix = "--apply" in sys.argv
    results = []
    for task_id in AFFECTED_TASKS:
        try:
            results.append(analyze(task_id, apply_fix))
        except Exception as e:
            results.append({"task_id": task_id, "error": str(e)})

    print(f"{'task_id':<62} {'before':>7} {'corrected':>10} {'starts':>7} {'discounted':>11} {'written':>8}")
    for r in results:
        if "error" in r:
            print(f"{r['task_id']:<62} ERROR: {r['error']}")
            continue
        print(f"{r['task_id']:<62} {str(r['before']):>7} {r['corrected']:>10} {r['starts_total']:>7} {r['starts_discounted']:>11} {str(r['written']):>8}")
    print()
    print("Per-task breakdown (checkpoint-note-prefix counts):")
    for r in results:
        if "error" in r:
            continue
        print(f"  {r['task_id']}: {r['breakdown']} (total checkpoints in task.yaml: {r['total_checkpoints']})")


if __name__ == "__main__":
    main()
