# Priority 16 -- PROJEXA End-to-End Test + Multi-Stage Audit Pipeline

STATUS: BLOCKED -- waiting on Priority 15 (see CONTROLLER.yaml PRIORITY-15) to
reach status: done. Do not start Stage 1 until PRIORITY-15's entry says done
and every module it adds (Sales/CRM, HR/Payroll, GRC, Accounting, Invoicing,
landing page) is merged and real -- otherwise this test will report gaps in
modules that don't exist yet, or worse, report a module "works" against a
half-built version of it.

This file is the resumable state for the whole pipeline. Update it in place
as each stage progresses so a new/interrupted session can pick up from here
without re-deriving context. Also update CONTROLLER.yaml's PRIORITY-16 entry
(status + `where`) whenever this file's STATUS line changes.

## Owner's original instruction (verbatim, 2026-07-14)

> Complete end to end testing of all modules and functionalities in PROJEXA,
> by a demo company with 50 fake users and a hierarchy that a mid size
> construction and interior design project management company will have.
> Use claude browser in the claude desktop for this testing. While testing,
> refer to that functionality in the actual software and confirm if its
> working the way intended. Check if input, output getting processed and
> saved in intended tables. Check if the system is working as per design.
> test the complete system as a user using the PROJEXA. make note what is
> the gap. the gap to be analyzed by a seperate audit team on this claude
> desktop. the analysis has to be what was intended, what are the gaps and
> how to fill it. than this audit will be reviewed by a this claude desktop
> seperately to understand why these gaps are there and what to do, should
> it be applied to the complete system. this will be presented to another
> claude desktop seperately to review in depth, with and make the
> implementation plan. than it will be implemented completely.

## Pipeline stages

1. **SETUP** -- build a demo company/org in the real PROJEXA+compliance-tracker
   stack: 50 fake users, org hierarchy realistic for a mid-size (~100-employee
   scale, per [[feedback_no_mvp_full_depth_modules]]) construction + interior
   design PM firm (e.g. Owner/Directors -> PMs -> Site Engineers/Architects ->
   Site Supervisors/Draftspeople -> Labour Contractors/Vendors, plus
   Sales/CRM, HR, Accounts, GRC roles once Priority 15 lands them). Multiple
   concurrent projects, not one.
2. **E2E TEST** -- Claude Desktop's Browser tool (mcp__Claude_Browser__*),
   driven as a real logged-in user per role, exercising every module end to
   end: not just "does the page render" but does each action match the
   documented/intended behaviour, does input reach the correct DB table(s)
   (verify via Supabase MCP `execute_sql`/`list_tables`, not just "no error
   shown"), does output match what was computed, does the system behave per
   its own design docs (AGENTS.md / PROJEXA_TASK_GOVERNANCE.md /
   compliance-tracker service layer it aliases). Log every gap found with:
   module, what was intended, what actually happened, table(s) checked,
   evidence (query result / screenshot / network response).
3. **GAP AUDIT** (separate Claude Desktop session/context) -- takes Stage 2's
   raw gap log, and for each gap determines: what was intended (design
   intent, not assumption), what the real gap is, how to fill it (concrete
   fix direction). Does not write code.
4. **AUDIT REVIEW** (this Claude Desktop session, separate pass from Stage 3)
   -- reviews Stage 3's audit: why does each gap exist (root cause, not just
   symptom), should the fix be applied narrowly or system-wide (i.e. does the
   same bug class appear elsewhere in PROJEXA/compliance-tracker).
5. **IMPLEMENTATION PLAN** (another, separate Claude Desktop session) --
   takes Stage 4's reviewed findings and produces a concrete implementation
   plan (files, sequencing, dependencies, worktree/sub-agent dispatch shape).
6. **IMPLEMENT** -- execute Stage 5's plan completely (real PRs, real merges,
   not partial/local-only -- same bar as every other Priority in
   CONTROLLER.yaml).

Each stage's session should update this file's "## Progress log" section
below before ending, even if the stage isn't finished, so the next session
resumes from real state instead of re-reading everything from scratch.

## Progress log

- 2026-07-14: File created. Logged as CONTROLLER.yaml entry PRIORITY-16,
  status: blocked (on PRIORITY-15). No stage started yet. Priority 15's real
  state as of this date, verified via `gh pr list` (not assumed from
  memory): compliance-tracker PR #328 ("Register Priority 15 GRC/Accounting/
  Invoicing claim") is OPEN, no other Priority-15-labeled PRs exist yet in
  either repo -- i.e. Wave 1's 4 sub-agents (Sales/CRM, HR/Payroll,
  GRC+Accounting+Invoicing, landing page) were dispatched but none has
  landed a merged feature PR yet. Do not start Stage 1 on the assumption
  Priority 15 is further along than this without re-checking `gh pr list`
  fresh.
