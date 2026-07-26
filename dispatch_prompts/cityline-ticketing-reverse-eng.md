## OBJECTIVE
Cityline Ticketing 6-role reverse-engineering

Redispatch of a task originally created ~2026-07-20 that was pre-emptively blocked by a
spend-governance gate (credit_accountant_rejected)
before any work started. A 2026-07-26 relevance-triage pass (see
ai-os/TIER3_RELEVANCE_TRIAGE_REPORT_2026-07-26.md, objective key `cityline-ticketing-reverse-eng`) independently
re-verified against the live repo, git history, and ACTIVE-CLAIMS.yaml/MASTER-TRACKER.yaml
that this objective is GENUINELY_STILL_OPEN -- nothing shipped since has closed it. This
task carries the same real objective as the original; do not skip real work assuming it
was done elsewhere.

## KNOWN_CONTEXT
Original task prompt (verbatim, the real specific objective to satisfy):
---
You are reverse-engineering a live web application from the front end only (no source code access — black-box exploration via Playwright MCP browser tools). Authorized exercise, credentials provided directly by the system's owner.

## Target
- URL: http://citylinenetworks.infisuite.in/ticketing
- Password for all 6 accounts below: infi123
- Roles/accounts (log into each SEPARATELY, one at a time):
  1. Admin — admin@citylinenetworks.infisuite.in
  2. Client — ticket_customer@citylinenetworks.infisuite.in
  3. Assigner — assigner@citylinenetworks.infisuite.in
  4. Fixer — fixer@citylinenetworks.infisuite.in
  5. Tester — tester@citylinenetworks.infisuite.in
  6. Escalate — escalation@citylinenetworks.infisuite.in

This is a 6-role ticketing/support-desk workflow system — a genuinely rare chance to map a full multi-role approval/escalation lifecycle end to end (Client raises → Assigner routes → Fixer resolves → Tester verifies → Escalate handles failures → Admin oversees). This is the MOST VALUABLE part of this dispatch — the role-to-role workflow transitions matter more than any single screen's field list.

## Job
For EACH of the 6 accounts:
1. Map navigation available to this role: `docs/cityline-ticketing/00-navigation-map-<role>.md`.
2. Identify exactly what this role CAN and CANNOT do (create ticket? assign? change status? close? reopen? escalate?) — infer from visible/enabled UI, confirm restrictions by noting any 403/permission-denied you hit.
3. If a real ticket exists (created by an earlier account in this same run, e.g. the Client), trace it through subsequent role logins to observe real state transitions (status changes, assignment, comments) — this is the core deliverable, worth spending real time on.

Standard per-page depth for whatever each role CAN see: 1. Purpose. 2. Navigation path. 3. UI/page design. 4. Data fields. 5. Underlying data structure (inferred). 6. Functionality/logic. 7. Inputs/outputs. 8. Data conditions.

## Methodology
1. Log in as Client FIRST. If safe to do so without side effects to a real support queue, create ONE clearly-test-labeled ticket (e.g. "TEST-REVERSE-ENGINEERING-DO-NOT-ACTION", low/no-urgency category if selectable) specifically so the workflow can be traced through the other 5 roles — this is the one exception to the usual read-only rule, because observing a real status-transition lifecycle is the actual point of this task; do not create more than this one ticket, and say clearly in SUMMARY.md that you created it and why.
2. Log into Assigner, find and route the test ticket, document the assign flow.
3. Log into Fixer, observe/action the ticket, document.
4. Log into Tester, observe/verify, document.
5. Log into Escalate, document what's visible even if the test ticket never needs escalation (describe the mechanism from the UI).
6. Log into Admin last, confirm oversight view shows the full lifecycle.
7. Write `docs/cityline-ticketing/workflow-lifecycle.md` — the actual state machine observed (statuses, who can transition what to what), plus one file per role's distinct UI under `docs/cityline-ticketing/<role>.md`.
8. Final `docs/cityline-ticketing/SUMMARY.md`: full role-permission matrix, data model, Known Gaps.

## Hard rules
- No password in committed files. No fabricating unobserved functionality — mark inferences as inferred. Document errors/bugs as-is.
- Commit+push after each role's pass.
- Aside from the ONE explicitly-labeled test ticket described above, read-only: no other real records, no submitting other forms with data, no emails/SMS beyond whatever the ticket system itself triggers as a normal side effect of the one test ticket.
- Maintain PROGRESS.md, update after each step, commit+push incrementally — this task may be interrupted and resumed.
---

Triage evidence confirming this gap is still real as of 2026-07-26:
main has only docs/cityline-ticketing/tickets-dashboard.md (53 lines, one page). Merge commit 9c5538b narrates 'Only 1 of the 6 originally-scoped roles was exercised' via the Owner's own already-authenticated session. Worker branch worker/task-20260720-060752-cityline-ticketing-6-role-reverse-engine contains only 00-BLOCKER-login-failures.md -- all 6 role-account logins failed and were never resolved.

The core 6-role, function-by-function documentation objective remains largely unmet; nothing since 2026-07-20 has closed this gap.

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

    bash -c 'find docs/cityline-ticketing -type f | wc -l'  # must be a full page-by-page doc set (more than the current single tickets-dashboard.md), covering all 6 roles

Open a real PR against infisuite-reverse-engineering (even WIP-labeled if you must stop early) rather than leaving
work uncommitted.

## EXPECTED_OUTPUT
A real PR against infisuite-reverse-engineering implementing the objective, or (if the spend-governance gate rejects
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
