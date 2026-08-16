## OBJECTIVE
E-invoicing per-line GstRt fix + IRP format scaffolding

Redispatch of a task originally created ~2026-07-20 that was pre-emptively blocked by a
spend-governance gate (credit_accountant_rejected, openrouter_balance_exhausted)
before any work started. A 2026-07-26 relevance-triage pass (see
ai-os/TIER3_RELEVANCE_TRIAGE_REPORT_2026-07-26.md, objective key `e-invoicing-gstrt-irp`) independently
re-verified against the live repo, git history, and ACTIVE-CLAIMS.yaml/MASTER-TRACKER.yaml
that this objective is GENUINELY_STILL_OPEN -- nothing shipped since has closed it. This
task carries the same real objective as the original; do not skip real work assuming it
was done elsewhere.

## KNOWN_CONTEXT
Original task prompt (verbatim, the real specific objective to satisfy):
---
TASK: V2-21 -- E-invoicing per-line GstRt fix + IRP format scaffolding

### V2-21 — E-invoicing per-line GstRt fix + IRP format scaffolding [C12]
- READY: yes (GstRt half); GSP-sandbox half blocked on Owner-provisioned creds
- SOFTWARE TEAM LEVEL: L3 Feature Worker
- TASK ID: V2-21-EINVOICING-GSTRT
- MODULE: compliance-tracker
- OBJECTIVE: Fix the per-line GstRt tracking gap in code; add the UAE/India e-invoice format scaffolding behind the country-config (ties to V2-1). Closes CSV row #70's code half; the GSP-sandbox live-test half stays deferred on Owner-provisioned creds (record in V2-6).
- READ FIRST: the e-invoice service; `erp_invoice_lines` GstRt field; V2-1's country-config.
- WHAT TO BUILD: per-line GstRt fix + format scaffolding + tests; the live-IRP-sandbox test is a separate gated task.
- CONSTRAINTS: No live IRP call without sandbox creds. Tier2 if schema. Register claim.
- DONE CRITERIA: GstRt fix + scaffolding + tests; deferred half recorded; row partly re-scored; PR open.

CONSTRAINTS (apply on top of anything stated above):
- Server-side only, routes through the Mother Router's software_team scope -> GLM-5.2 via OpenRouter, cheapest real provider at dispatch time.
- Register your claim in the relevant repo's ai-os/boss/ACTIVE-CLAIMS.yaml before real work, per this repo's own protocol -- check for collisions with any other active claim or open PR on the same file/module scope first.
- Maintain PROGRESS.md with '## Completed' / '## Remaining' checklists as usual.
- Commit + push incrementally. Open a real PR (even WIP-labeled if you must stop early) rather than holding everything uncommitted.
- Tier1 (docs/tests/additive-only, no schema/auth/RLS/payment/billing/.env changes) may be merged autonomously once CI is genuinely green on all required checks. Tier2 always holds for Owner sign-off, no exceptions, regardless of audit verdict.
- If the finding turns out to already be resolved, or doesn't match what you find in the current code, say so in PROGRESS.md rather than making an unnecessary change -- the codebase has moved since this plan was written.
---

Triage evidence confirming this gap is still real as of 2026-07-26:
src/lib/services/erp-einvoice-service.ts:77 (on origin/main) still hardcodes `GstRt: 0, // per-line GST rate isn't separately tracked`. erpSalesInvoiceItems has no per-line tax-rate column (only taxTemplateId). No countryConfig/UAE e-invoice scaffolding exists anywhere in src/. The ACTIVE-CLAIMS.yaml 'Purchase-invoice text assumed... stale' reference is an unrelated duplicate-invoice-detection gap closure, not GstRt. No commit since 2026-07-20 touches erp-einvoice-service.ts.

The exact hardcoded gap the task names is still present verbatim in the current code.

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

    bash -c 'grep -n "GstRt" src/lib/services/erp-einvoice-service.ts'  # must NOT show the hardcoded "GstRt: 0" stub any more -- must show real per-line tracking

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
