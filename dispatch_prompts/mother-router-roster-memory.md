## OBJECTIVE
mother-router-and-roster-persistent-memory

Redispatch of a task originally created ~2026-07-20 that was pre-emptively blocked by a
spend-governance gate (credit_accountant_rejected)
before any work started. A 2026-07-26 relevance-triage pass (see
ai-os/TIER3_RELEVANCE_TRIAGE_REPORT_2026-07-26.md, objective key `mother-router-roster-memory`) independently
re-verified against the live repo, git history, and ACTIVE-CLAIMS.yaml/MASTER-TRACKER.yaml
that this objective is GENUINELY_STILL_OPEN -- nothing shipped since has closed it. This
task carries the same real objective as the original; do not skip real work assuming it
was done elsewhere.

## KNOWN_CONTEXT
Original task prompt (verbatim, the real specific objective to satisfy):
---
Add ground-up persistent memory to Mother Router (src/lib/ai-router/mother-router.ts) and the AI agent roster (src/lib/ai-team/roster.ts), per ai-os/SYSTEM_MEMORY_ARCHITECTURE.yaml design: mother_router_memory table (dispatch_id, ts, input_capability_tag, resolved_role, resolved_model, outcome, cost, cross_ref_work_item_id) and ai_agent_memory table (role_id, ts, task_id, outcome, escalation_flag, cross_ref_work_item_id). Add Drizzle schema, apply real migration to live Supabase DB, wire writes at actual dispatch decision points, typecheck, commit to a branch, push to GitHub. Zero customers, ground-up changes authorized, no shortcuts.
---

Triage evidence confirming this gap is still real as of 2026-07-26:
ai-os/SYSTEM_MEMORY_ARCHITECTURE.yaml (authored 2026-07-22, AFTER the credit-gate block) explicitly states layer_3_mother_router: status: CONFIRMED_GAP_DESIGNED_NOT_BUILT and layer_5_ai_agents_roster: status: CONFIRMED_GAP_DESIGNED_NOT_BUILT. Independent grep of schema.ts and the whole repo for mother_router_memory/ai_agent_memory returns zero matches; no migration references them.

A later, independent review (2026-07-22) reconfirmed the exact same gap and notes it is deliberately deferred per the Owner's own sequencing rule -- the gap is real, current, and explicitly still open by the system's own architecture doc.

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

    bash -c 'grep -n "mother_router_memory\|ai_agent_memory" src/lib/db/schema.ts'  # both tables must exist and be wired into mother-router.ts/roster.ts

Open a real PR against compliance-tracker (even WIP-labeled if you must stop early) rather than leaving
work uncommitted.

## EXPECTED_OUTPUT
A real PR against compliance-tracker implementing the objective, or (if the spend-governance gate rejects
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
