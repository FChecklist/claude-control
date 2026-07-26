import json, os
from classifications import CLASSIFICATIONS

objectives = {o["key"]: o for o in json.load(open("objectives_45.json"))}

REPO_MAP = {
    "delegation-expiry": "compliance-tracker",
    "serverless-resource-limit": "compliance-tracker",
    "chat-context-terminology": "compliance-tracker",
    "preview-deployment-spotcheck": "compliance-tracker",
    "storage-rls-backup-pitr": "compliance-tracker",
    "crm-performance-under-load": "compliance-tracker",
    "hr-performance-payroll": "compliance-tracker",
    "search-performance-gin": "compliance-tracker",
    "e-invoicing-gstrt-irp": "compliance-tracker",
    "cityline-ticketing-reverse-eng": "infisuite-reverse-engineering",
    "mother-router-roster-memory": "compliance-tracker",
    "remove-anthropic-api-key": "compliance-tracker",
}

open_keys = [k for k, v in CLASSIFICATIONS.items() if v["classification"] == "GENUINELY_STILL_OPEN"]

os.makedirs("dispatch_prompts", exist_ok=True)

VERIFY_CMD = {
    "delegation-expiry": '''bash -c 'grep -rln "isDelegated(\\|isDelegationActive(" src --include=*.ts | grep -v "delegation-service"'  # must be non-empty: a real authorization checkpoint outside delegation-service.ts now calls the shared expiry check''',
    "serverless-resource-limit": '''bash -c 'find ai-os -iname "*serverless*resource*" -o -iname "*serverless*limit*"'  # doc must exist and list any workload fixes made''',
    "chat-context-terminology": '''bash -c 'grep -n "contextEntityId" src/lib/services/chat-service.ts'  # must show it consulted inside generateAiReply, not just plumbed elsewhere''',
    "preview-deployment-spotcheck": '''bash -c 'gh pr list --repo FChecklist/compliance-tracker --state open --limit 1 --json number,url; find ai-os -iname "*preview*spot*check*"'  # a fresh note against the CURRENT most-recent open PR must exist''',
    "storage-rls-backup-pitr": '''bash -c 'grep -rn "storage.objects" drizzle/*.sql | grep -i "policy\\|rls"; find ai-os -iname "*RTO*" -o -iname "*PITR*"'  # must show a real RLS policy for the named buckets plus the RTO/RPO audit doc''',
    "crm-performance-under-load": '''bash -c 'grep -n "org_id.*status.*created_at\\|org_id.*stage" drizzle/*.sql src/lib/db/schema.ts; find scripts -iname "*crm*load*test*"'  # composite indexes and a CRM-specific load-test harness must exist''',
    "hr-performance-payroll": '''bash -c 'find ai-os -iname "*payroll*rate*audit*" -o -iname "*fy-rate*"; grep -rln "cache" src/app/api/hr'  # rate-seed audit doc must exist and HR dashboard caching must be wired''',
    "search-performance-gin": '''bash -c 'grep -n "gin_trgm_ops\\|pg_trgm" drizzle/*.sql | grep -i search; find ai-os -iname "*explain*analyze*search*"'  # a GIN index migration for the search-service path plus the EXPLAIN ANALYZE results doc must exist''',
    "e-invoicing-gstrt-irp": '''bash -c 'grep -n "GstRt" src/lib/services/erp-einvoice-service.ts'  # must NOT show the hardcoded "GstRt: 0" stub any more -- must show real per-line tracking''',
    "cityline-ticketing-reverse-eng": '''bash -c 'find docs/cityline-ticketing -type f | wc -l'  # must be a full page-by-page doc set (more than the current single tickets-dashboard.md), covering all 6 roles''',
    "mother-router-roster-memory": '''bash -c 'grep -n "mother_router_memory\\|ai_agent_memory" src/lib/db/schema.ts'  # both tables must exist and be wired into mother-router.ts/roster.ts''',
    "remove-anthropic-api-key": '''bash -c 'grep -rn "ANTHROPIC_API_KEY\\|claude-task" src .github/workflows'  # must return NO hits once the dead path is fully removed''',
}

for key in open_keys:
    o = objectives[key]
    c = CLASSIFICATIONS[key]
    repo = REPO_MAP[key]
    title = c["title"]
    original = o["prompt"].strip()

    text = f"""## OBJECTIVE
{title}

Redispatch of a task originally created ~2026-07-20 that was pre-emptively blocked by a
spend-governance gate ({', '.join(sorted(set(e['gate'] for e in json.load(open('triage_45.json')) if e['task_id'] in o['task_ids'])))})
before any work started. A 2026-07-26 relevance-triage pass (see
ai-os/TIER3_RELEVANCE_TRIAGE_REPORT_2026-07-26.md, objective key `{key}`) independently
re-verified against the live repo, git history, and ACTIVE-CLAIMS.yaml/MASTER-TRACKER.yaml
that this objective is GENUINELY_STILL_OPEN -- nothing shipped since has closed it. This
task carries the same real objective as the original; do not skip real work assuming it
was done elsewhere.

## KNOWN_CONTEXT
Original task prompt (verbatim, the real specific objective to satisfy):
---
{original}
---

Triage evidence confirming this gap is still real as of 2026-07-26:
{c['evidence']}

{c['justification']}

## SCOPE
1. Read the original task prompt above in full; it is the authoritative scope statement.
2. Re-verify current repo state yourself before writing code (things may have changed again
   since the 2026-07-26 triage) -- do not assume the triage evidence above is still accurate,
   confirm it against the live tree first.
3. Implement the objective for real: the actual code/doc/audit artifact the original prompt's
   "WHAT TO BUILD"/"OBJECTIVE" section asks for.
4. Register your claim in ai-os/boss/ACTIVE-CLAIMS.yaml per this repo's own protocol; check for
   collisions with any other active claim or open PR on the same file/module scope first.
5. Maintain PROGRESS.md (## Completed / ## Remaining, markdown checkboxes); commit + push
   incrementally rather than holding everything uncommitted.

## SUCCESS_CRITERIA
The specific "WHAT TO BUILD" / "DONE CRITERIA" stated in the original prompt above is met,
verifiably -- not merely asserted. A real, runnable verification command (run it yourself
before opening the PR, and again in the PR description):

    {VERIFY_CMD[key]}

Open a real PR against {repo} (even WIP-labeled if you must stop early) rather than leaving
work uncommitted.

## EXPECTED_OUTPUT
A real PR against {repo} implementing the objective, or (if the spend-governance gate rejects
this task again for a genuine, currently-real resource constraint) an honest, verifiable
record of that rejection -- report it as a correct governance outcome, not a bug to route
around.

## CONSTRAINTS
Additive-only unless the original prompt above explicitly calls for a fix to existing code.
Tier2 changes (schema/auth/RLS/payment/billing/.env) always hold for Owner sign-off, no
exceptions. Do not merge yourself. Do not duplicate work already covered by
ALREADY_DONE_ELSEWHERE items in ai-os/TIER3_RELEVANCE_TRIAGE_REPORT_2026-07-26.md.

## COMPLEXITY_TIER
judgment
"""
    path = f"dispatch_prompts/{key}.md"
    with open(path, "w") as f:
        f.write(text)
    print(key, "->", path, len(text), "chars, repo:", repo)
