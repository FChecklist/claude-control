## OBJECTIVE
Chat context + terminology + mode-pill analytics

Redispatch of a task originally created ~2026-07-20 that was pre-emptively blocked by a
spend-governance gate (credit_accountant_rejected, openrouter_balance_exhausted)
before any work started. A 2026-07-26 relevance-triage pass (see
ai-os/TIER3_RELEVANCE_TRIAGE_REPORT_2026-07-26.md, objective key `chat-context-terminology`) independently
re-verified against the live repo, git history, and ACTIVE-CLAIMS.yaml/MASTER-TRACKER.yaml
that this objective is GENUINELY_STILL_OPEN -- nothing shipped since has closed it. This
task carries the same real objective as the original; do not skip real work assuming it
was done elsewhere.

## KNOWN_CONTEXT
Original task prompt (verbatim, the real specific objective to satisfy):
---
TASK: V2-13 -- Chat context + terminology + mode-pill analytics

### V2-13 — Chat context + terminology + mode-pill analytics [C4]
- READY: yes
- SOFTWARE TEAM LEVEL: L3 Feature Worker
- TASK ID: V2-13-CHAT-CONTEXT-ANALYTICS
- MODULE: compliance-tracker
- OBJECTIVE: Verify and wire `contextEntityId` data fetch into the AI reply prompt; add an org-glossary hook into the system prompt; add usage analytics on mode-pills vs free-text. Closes CSV rows #16/#17/#20.
- READ FIRST: chat reply prompt construction; `contextEntityId` plumbing; existing analytics infra.
- WHAT TO BUILD: context fetch wiring + glossary hook + mode-pill analytics event; tests.
- CONSTRAINTS: No new analytics vendor; reuse existing. Register claim.
- DONE CRITERIA: Three rows' fixes shipped + tested; rows re-scored; PR open.

CONSTRAINTS (apply on top of anything stated above):
- Server-side only, routes through the Mother Router's software_team scope -> GLM-5.2 via OpenRouter, cheapest real provider at dispatch time.
- Register your claim in the relevant repo's ai-os/boss/ACTIVE-CLAIMS.yaml before real work, per this repo's own protocol -- check for collisions with any other active claim or open PR on the same file/module scope first.
- Maintain PROGRESS.md with '## Completed' / '## Remaining' checklists as usual.
- Commit + push incrementally. Open a real PR (even WIP-labeled if you must stop early) rather than holding everything uncommitted.
- Tier1 (docs/tests/additive-only, no schema/auth/RLS/payment/billing/.env changes) may be merged autonomously once CI is genuinely green on all required checks. Tier2 always holds for Owner sign-off, no exceptions, regardless of audit verdict.
- If the finding turns out to already be resolved, or doesn't match what you find in the current code, say so in PROGRESS.md rather than making an unnecessary change -- the codebase has moved since this plan was written.
---

Triage evidence confirming this gap is still real as of 2026-07-26:
`contextEntityId` is set/read via veri-chat-service.ts/veri-meeting-service.ts but never fetched inside `generateAiReply()` in chat-service.ts (system prompt built purely from resolvePromptTemplate + buildPurposeClause). A glossary feature exists (glossary-service.ts, GlossaryTermTooltip) but is a UI hover-tooltip, not a system-prompt hook -- no glossary reference in chat-service.ts. No mode-pill-vs-free-text analytics events found anywhere. No ACTIVE-CLAIMS/COMPLETED/MASTER-TRACKER entry for V2-13.

All three sub-asks (context wiring, glossary hook, mode-pill analytics) remain unbuilt.

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

    bash -c 'grep -n "contextEntityId" src/lib/services/chat-service.ts'  # must show it consulted inside generateAiReply, not just plumbed elsewhere

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
