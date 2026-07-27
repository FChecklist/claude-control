import json
from classifications import CLASSIFICATIONS

objectives = json.load(open("objectives_45.json"))
by_key = {o["key"]: o for o in objectives}

order = ["delegation-expiry","serverless-resource-limit","chat-context-terminology",
"preview-deployment-spotcheck","storage-rls-backup-pitr","crm-performance-under-load",
"hr-performance-payroll","multi-office-selector","prompt-cache-real-metrics",
"search-performance-gin","e-invoicing-gstrt-irp","wave1-crm-schema-service-gaps",
"canary-zero-waste-pipeline-test","billstack-bharatnet-reverse-eng",
"cityline-ticketing-reverse-eng","mother-router-roster-memory",
"shared-cross-repo-prompt-pattern","executive-reporting-drilldown",
"remove-anthropic-api-key","crm-contacts-list-route","continue-autonomous-gap-queue"]

assert set(order) == set(CLASSIFICATIONS.keys()) == set(by_key.keys())

counts = {"ALREADY_DONE_ELSEWHERE":0, "GENUINELY_STILL_OPEN":0, "UNCLEAR_NEEDS_OWNER_DECISION":0}
row_counts = {"ALREADY_DONE_ELSEWHERE":0, "GENUINELY_STILL_OPEN":0, "UNCLEAR_NEEDS_OWNER_DECISION":0}
total_rows = 0
lines = []

lines.append("# Tier-3 Relevance Triage: 45 Stale Credit/OpenRouter-Gated Tasks")
lines.append("")
lines.append("**Date:** 2026-07-26")
lines.append("**Source:** `ai-os/TASK_COMPLETION_AUDIT_2026-07-26.json`")
lines.append("")
lines.append("## Methodology")
lines.append("")
lines.append("The audit JSON's per-row `reason` field only records the top-level recorded/verified "
"status, not the granular pre-flight-gate note. The real 45-task bucket was re-derived live by "
"reading each task's `task.yaml` under `/opt/veridian/ai-os/tasks/<task_id>/` directly: within the "
"audit's 219-row window (tasks created in the 7 days before the audit), a task counts as \"real\" for "
"this triage if its **last checkpoint note** contains `credit_accountant_rejected` or "
"`openrouter_balance_exhausted`, **and** its `real_verified_status` in the audit is not `MERGED` "
"(a handful of tasks hit one of these gates on an early attempt but were later satisfied by a "
"separate PR, so they're excluded here as already resolved). This produced exactly:")
lines.append("")
lines.append("- 29 tasks whose last checkpoint was a `credit_accountant_rejected` pre-flight hard stop")
lines.append("- 16 tasks whose last checkpoint was an `openrouter_balance_exhausted` pre-flight hard stop")
lines.append("- **45 total**, matching the expected bucket size exactly.")
lines.append("")
lines.append("These 45 task rows collapse into **21 unique objectives** — most are `SUPERBOSS_V2_PLAN` "
"items (V2-11 through V2-25) that were dispatched, blocked by the spend gate, and then automatically "
"retried (`[retry 1]`, `[retry 2]`) against the *same* still-exhausted gate, producing 2-3 rows per "
"real objective. Each objective below was independently checked against the live "
"`/opt/veridian/repos/compliance-tracker` (or `infisuite-reverse-engineering` / `veridian-ui-kit` / "
"`projexa`, per scope) git history, `gh pr` records, `ai-os/boss/ACTIVE-CLAIMS.yaml`, "
"`ai-os/MASTER-TRACKER.yaml`, and `ai-os/GAP_ANALYSIS_2026-07-20_HOLD.md` / "
"`ai-os/SUPERBOSS_IMPLEMENTATION_PLAN_2026-07-19_v2.md` for real completion evidence — not assumed.")
lines.append("")
lines.append("## Summary")
lines.append("")
lines.append("| Classification | Objectives | Task rows |")
lines.append("|---|---|---|")

# compute counts first
tmp_counts = {}
for key in order:
    c = CLASSIFICATIONS[key]["classification"]
    tmp_counts.setdefault(c, [0,0])
    tmp_counts[c][0] += 1
    tmp_counts[c][1] += len(by_key[key]["task_ids"])

for c in ["ALREADY_DONE_ELSEWHERE","GENUINELY_STILL_OPEN","UNCLEAR_NEEDS_OWNER_DECISION"]:
    o,r = tmp_counts.get(c,[0,0])
    lines.append(f"| {c} | {o} | {r} |")
lines.append(f"| **Total** | **21** | **45** |")
lines.append("")
lines.append("## Per-objective classifications (all 45 task rows accounted for)")
lines.append("")

n = 0
for key in order:
    o = by_key[key]
    c = CLASSIFICATIONS[key]
    n += 1
    v2 = f" ({c['v2_id']})" if c["v2_id"] else ""
    lines.append(f"### {n}. {c['title']}{v2}")
    lines.append("")
    lines.append(f"**Objective key:** `{key}`  ")
    lines.append(f"**Task rows in this bucket ({len(o['task_ids'])}):** " + ", ".join(f"`{t}`" for t in o["task_ids"]))
    lines.append("")
    lines.append(f"**Classification: {c['classification']}**")
    lines.append("")
    lines.append(f"**Evidence:** {c['evidence']}")
    lines.append("")
    lines.append(f"**Justification:** {c['justification']}")
    lines.append("")

lines.append("## Appendix: all 45 task rows, explicit classification")
lines.append("")
lines.append("Every row below inherits its objective's classification (rows are retry-1/retry-2 "
"duplicates of the same objective that kept re-hitting the same pre-flight gate).")
lines.append("")
lines.append("| # | task_id | gate | objective | classification |")
lines.append("|---|---|---|---|---|")
row_n = 0
for key in order:
    o = by_key[key]
    c = CLASSIFICATIONS[key]
    for tid in o["task_ids"]:
        row_n += 1
        gate = "credit_accountant_rejected" if tid in [e["task_id"] for e in json.load(open("triage_45.json")) if e["gate"]=="credit_accountant_rejected"] else "openrouter_balance_exhausted"
        lines.append(f"| {row_n} | `{tid}` | {gate} | {key} | **{c['classification']}** |")
assert row_n == 45, row_n
lines.append("")

redispatched = json.load(open("redispatched_ids.json"))
lines.append("## Redispatch of GENUINELY_STILL_OPEN objectives")
lines.append("")
lines.append("Per the CONSTRAINTS of this triage, only objectives classified GENUINELY_STILL_OPEN "
"were redispatched -- ONE fresh task per unique objective (not per duplicate retry row), via "
"`scripts/task-gateway.py submit` + `start`, using each objective's real original prompt "
"content as the authoritative scope (wrapped in the required 7-section template with an added "
"runnable SUCCESS_CRITERIA verification command, since `tight_task_validation.py` requires one). "
"All 12 passed pre-flight this time (none hit `credit_accountant_rejected` or "
"`openrouter_balance_exhausted` again) and are actively running as of this report -- real, "
"current evidence that the 2026-07-20 resource-exhaustion condition has since cleared.")
lines.append("")
lines.append("| Objective | New task_id | `task-gateway.py status` at dispatch time |")
lines.append("|---|---|---|")
for key in order:
    if CLASSIFICATIONS[key]["classification"] != "GENUINELY_STILL_OPEN":
        continue
    tid = redispatched[key]
    lines.append(f"| {key} | `{tid}` | `in_progress`, pre-flight passed, systemd active |")
lines.append("")
lines.append("`multi-office-selector`, `shared-cross-repo-prompt-pattern`, and "
"`executive-reporting-drilldown` were classified UNCLEAR_NEEDS_OWNER_DECISION and were "
"deliberately NOT redispatched -- per this triage's own constraints, guessing a classification "
"(and therefore a redispatch decision) without real, citable evidence is exactly what this "
"effort exists to avoid. `billstack-bharatnet-reverse-eng`'s classification is "
"ALREADY_DONE_ELSEWHERE but with a caveat worth flagging separately to the owner: the real "
"deliverable already exists complete on unmerged branch "
"`worker/task-20260720-060747-billstack-bharatnet-reverse-engineering` -- it needs a PR/merge "
"action, not a fresh redispatch (which would duplicate finished work).")
lines.append("")

print("\n".join(lines))
with open("report_body.md", "w") as f:
    f.write("\n".join(lines))

# sanity check for success criteria
total_mentions = sum(("\n".join(lines)).count(x) for x in ["ALREADY_DONE_ELSEWHERE","GENUINELY_STILL_OPEN","UNCLEAR_NEEDS_OWNER_DECISION"])
print("TOTAL MENTIONS (incl table+headers):", total_mentions, file=__import__("sys").stderr)
