## OBJECTIVE
Search performance EXPLAIN ANALYZE + GIN index

Redispatch of a task originally created ~2026-07-20 that was pre-emptively blocked by a
spend-governance gate (credit_accountant_rejected, openrouter_balance_exhausted)
before any work started. A 2026-07-26 relevance-triage pass (see
ai-os/TIER3_RELEVANCE_TRIAGE_REPORT_2026-07-26.md, objective key `search-performance-gin`) independently
re-verified against the live repo, git history, and ACTIVE-CLAIMS.yaml/MASTER-TRACKER.yaml
that this objective is GENUINELY_STILL_OPEN -- nothing shipped since has closed it. This
task carries the same real objective as the original; do not skip real work assuming it
was done elsewhere.

## KNOWN_CONTEXT
Original task prompt (verbatim, the real specific objective to satisfy):
---
TASK: V2-20 -- Search performance EXPLAIN ANALYZE + GIN index

### V2-20 — Search performance EXPLAIN ANALYZE + GIN index [C11]
- READY: yes
- SOFTWARE TEAM LEVEL: L2 Sequential Worker
- TASK ID: V2-20-SEARCH-PERF
- MODULE: compliance-tracker
- OBJECTIVE: `EXPLAIN ANALYZE` on Standard search at realistic volume; add `pg_trgm`/GIN index if the plan says. Closes CSV row #67.
- READ FIRST: the search service/query; existing indexes; `pg_trgm` extension availability.
- WHAT TO BUILD: A migration adding the GIN index + the EXPLAIN results doc.
- CONSTRAINTS: Tier2 (migration + live DB) — supervisor holds. Register claim.
- DONE CRITERIA: Index applied + EXPLAIN doc; row re-scored; PR open.

CONSTRAINTS (apply on top of anything stated above):
- Server-side only, routes through the Mother Router's software_team scope -> GLM-5.2 via OpenRouter, cheapest real provider at dispatch time.
- Register your claim in the relevant repo's ai-os/boss/ACTIVE-CLAIMS.yaml before real work, per this repo's own protocol -- check for collisions with any other active claim or open PR on the same file/module scope first.
- Maintain PROGRESS.md with '## Completed' / '## Remaining' checklists as usual.
- Commit + push incrementally. Open a real PR (even WIP-labeled if you must stop early) rather than holding everything uncommitted.
- Tier1 (docs/tests/additive-only, no schema/auth/RLS/payment/billing/.env changes) may be merged autonomously once CI is genuinely green on all required checks. Tier2 always holds for Owner sign-off, no exceptions, regardless of audit verdict.
- If the finding turns out to already be resolved, or doesn't match what you find in the current code, say so in PROGRESS.md rather than making an unnecessary change -- the codebase has moved since this plan was written.
---

Triage evidence confirming this gap is still real as of 2026-07-26:
search-service.ts (the general/Standard search) uses plain ilike() against complianceItems.title/description, tasks.title/description, clients.name -- no pg_trgm/GIN index backs these columns. The pg_trgm/gin_trgm_ops hits that do exist (drizzle/0079_wave93_mdm_duplicate_detection.sql, drizzle/0085_wave107_fm_asset_registry...) serve an unrelated feature (MDM/FM dedup), not the general search path. No EXPLAIN ANALYZE results doc exists anywhere under ai-os/.

The GIN infrastructure that exists is for a different feature; the search-service path this task targets is untouched.

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

    bash -c 'grep -n "gin_trgm_ops\|pg_trgm" drizzle/*.sql | grep -i search; find ai-os -iname "*explain*analyze*search*"'  # a GIN index migration for the search-service path plus the EXPLAIN ANALYZE results doc must exist

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
