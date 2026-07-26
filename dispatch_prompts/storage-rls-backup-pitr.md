## OBJECTIVE
Storage RLS + backup PITR + Supabase monitoring audit

Redispatch of a task originally created ~2026-07-20 that was pre-emptively blocked by a
spend-governance gate (credit_accountant_rejected, openrouter_balance_exhausted)
before any work started. A 2026-07-26 relevance-triage pass (see
ai-os/TIER3_RELEVANCE_TRIAGE_REPORT_2026-07-26.md, objective key `storage-rls-backup-pitr`) independently
re-verified against the live repo, git history, and ACTIVE-CLAIMS.yaml/MASTER-TRACKER.yaml
that this objective is GENUINELY_STILL_OPEN -- nothing shipped since has closed it. This
task carries the same real objective as the original; do not skip real work assuming it
was done elsewhere.

## KNOWN_CONTEXT
Original task prompt (verbatim, the real specific objective to satisfy):
---
TASK: V2-15 -- Storage RLS + backup PITR + Supabase monitoring audit

### V2-15 — Storage RLS + backup PITR + Supabase monitoring audit [C6]
- READY: yes
- SOFTWARE TEAM LEVEL: L2 Sequential Worker
- TASK ID: V2-15-SUPABASE-DR-AUDIT
- MODULE: compliance-tracker
- OBJECTIVE: `get_advisors` audit on `storage.objects` RLS for both buckets; verify PITR/backup via Supabase MCP/dashboard; document RTO/RPO; confirm Sentry monitoring activation. Closes CSV rows #40/#41/#42.
- READ FIRST: Supabase MCP; `sentry.*.config.ts`; the bucket definitions.
- WHAT TO BUILD: An audit doc + any missing RLS policy fix (tier2 if schema/policy) + RTO/RPO statement.
- CONSTRAINTS: The DSN-provisioning half is Owner-dashboard (V2-6/C17); the audit is code/MCP. Tier2 if RLS policy changed — supervisor holds. Register claim.
- DONE CRITERIA: Audit doc + RTO/RPO; rows re-scored; PR open.

CONSTRAINTS (apply on top of anything stated above):
- Server-side only, routes through the Mother Router's software_team scope -> GLM-5.2 via OpenRouter, cheapest real provider at dispatch time.
- Register your claim in the relevant repo's ai-os/boss/ACTIVE-CLAIMS.yaml before real work, per this repo's own protocol -- check for collisions with any other active claim or open PR on the same file/module scope first.
- Maintain PROGRESS.md with '## Completed' / '## Remaining' checklists as usual.
- Commit + push incrementally. Open a real PR (even WIP-labeled if you must stop early) rather than holding everything uncommitted.
- Tier1 (docs/tests/additive-only, no schema/auth/RLS/payment/billing/.env changes) may be merged autonomously once CI is genuinely green on all required checks. Tier2 always holds for Owner sign-off, no exceptions, regardless of audit verdict.
- If the finding turns out to already be resolved, or doesn't match what you find in the current code, say so in PROGRESS.md rather than making an unnecessary change -- the codebase has moved since this plan was written.
---

Triage evidence confirming this gap is still real as of 2026-07-26:
`drizzle/0221_wave_b_white_label_branding.sql` (lines 15-19, 66-76) explicitly documents the org-branding bucket 'carries no storage.objects RLS policies (consistent with this repo's existing compliance-documents/voice-memos buckets...)' -- i.e. the exact two buckets named in the task still have zero RLS as of the newest migration touching this area. No PITR/RTO/RPO doc found anywhere. sentry.server.config.ts/sentry.edge.config.ts exist but only reference `process.env.SENTRY_DSN` (no-op if unset); SUPERBOSS_IMPLEMENTATION_PLAN_2026-07-19_v2.md confirms the DSN provisioning itself is explicitly out of code scope and was never confirmed active. No ACTIVE-CLAIMS/COMPLETED/MASTER-TRACKER entry for V2-15.

RLS gap on storage.objects is confirmed still real by the newest migration's own comment; PITR doc and Sentry activation confirmation also never produced.

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

    bash -c 'grep -rn "storage.objects" drizzle/*.sql | grep -i "policy\|rls"; find ai-os -iname "*RTO*" -o -iname "*PITR*"'  # must show a real RLS policy for the named buckets plus the RTO/RPO audit doc

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
