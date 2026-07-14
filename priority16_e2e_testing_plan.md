# Priority 16 -- PROJEXA End-to-End Test + Multi-Stage Audit Pipeline

STATUS: UNBLOCKED 2026-07-14 -- PRIORITY-15 (incl. Wave 2) reached status:
done, all modules merged and independently audited (see CONTROLLER.yaml
PRIORITY-15's where/wave_2_close_out for the full PR list). Part 1 test
script below is now written against the real, final module list. Next
action: dispatch Part 1 execution (demo org build + E2E test run).

KNOWN RELATED FINDING before Part 1 starts: PROJEXA-IDENTITY-BRIDGE-01
(CONTROLLER.yaml) -- PROJEXA's server-to-server calls to compliance-tracker
carry only an org-wide API key, never a per-user identity, so 17 named
routes gated on "requires a real dbUser session" (quotation approval, leave
decisions, payroll processing/finalization, department/employee creation,
and more) will reject any real logged-in PROJEXA user who attempts them.
Part 1 WILL hit this repeatedly across multiple modules -- do not treat each
occurrence as a new, separate gap; log the first one with full evidence,
then for every subsequent occurrence of the identical "requires a real user
session, not an API key" 400 response, log it tersely with a cross-reference
to the first entry and to PROJEXA-IDENTITY-BRIDGE-01, so Part 2 doesn't have
to de-duplicate 17 near-identical gap entries by hand.

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

## Pipeline structure (revised 2026-07-14 -- 2 parts, mapped to Claude Desktop
effort tiers, managed automatically)

Owner directive 2026-07-14: collapse the original 6-stage/N-separate-session
shape below into 2 parts, each run by Claude Desktop Sonnet 5 at a specific
reasoning-effort tier, with Claude Desktop handling the hand-off between them
automatically (Owner does not manually kick off each stage).

### PART 1 -- E2E testing (Claude Desktop, Sonnet 5, LOW effort)

Runs the mechanical, high-volume half of the work: build the 50-fake-user
demo org, then drive every PROJEXA module end to end as each role via the
Browser tool (mcp__Claude_Browser__*), registering every issue found with
input/output/table evidence. Low effort is deliberately used here because
this is breadth-first, repetitive, procedural execution (click through
module, check table, log result) -- not open-ended judgment.

Because Low effort has less headroom to infer intent from an underspecified
brief, **the instructions handed to this part must be pre-tightened before
the part starts** -- a literal step-by-step test script per module/role, not
a restated version of the Owner's original prose. That tightened script is
Part 1's actual input; write it into "## Part 1 test script" below once
Priority 15 unblocks this and the real module list is final.

Part 1 must, for every module x every relevant role:
  a. State what the module/action is *supposed* to do (from AGENTS.md /
     PROJEXA_TASK_GOVERNANCE.md / the compliance-tracker service it aliases
     -- not assumed).
  b. Perform the action as a real logged-in user via the Browser tool.
  c. Verify the actual outcome against (a).
  d. Verify input/output actually landed in the correct DB table(s) via
     Supabase MCP `execute_sql`/`list_tables` -- not "no error shown in UI."
  e. Log a structured entry per gap found: module, role, intended behaviour,
     actual behaviour, table(s) checked, evidence (query result / screenshot
     / network response). No fixing, no root-causing -- just registration.

Output: a single structured gap log (module/role/intended/actual/evidence),
persisted to a file under this plan (path TBD at Part 1 start, recorded in
Progress log below) -- this is Part 2's entire input.

### PART 2 -- Analysis, planning, implementation (Claude Desktop, Sonnet 5, HIGH effort)

Runs the judgment-heavy half: takes Part 1's gap log and, per gap:
  a. Re-derive what was actually planned/intended (cross-check design docs
     directly, don't trust Part 1's paraphrase alone for anything going into
     a fix).
  b. Understand the bug/gap -- root cause, not just symptom.
  c. Determine whether the fix should be scoped narrowly or applied
     system-wide (same bug class elsewhere in PROJEXA/compliance-tracker).
  d. Produce a concrete implementation plan (files, sequencing, dependencies,
     worktree/sub-agent dispatch shape) covering all gaps together, not one
     plan per gap in isolation, so shared fixes aren't duplicated.
  e. Implement the plan completely -- real merged PRs, not partial/local-only
     work, same bar as every other Priority in CONTROLLER.yaml.

High effort is used here because this stage requires genuine judgment (root
cause vs symptom, narrow vs system-wide, cross-module sequencing) that Low
effort is not suited for.

### Automatic hand-off

Claude Desktop manages the Part 1 -> Part 2 transition itself: once Part 1's
gap log is complete and persisted, the next Claude Desktop session (or a
scheduled wakeup, see control/README.md "Automation") reads this file, sees
Part 1 marked complete in the Progress log, and starts Part 2 without the
Owner needing to manually re-trigger it. Each part must still update the
Progress log before ending (even mid-part) so an interruption resumes from
real recorded state.

## Part 1 test script

Written 2026-07-14, against PROJEXA's real, final `AppSidebar.tsx` (33 pages
across 10 nav sections, confirmed by direct read, not assumed) and its real
role model (confirmed by direct schema read: `memberships.role` is a plain
text column, `owner` | `admin` | `member` are the only values anything in
the codebase actually branches on -- e.g. `use-org-role.ts`'s
`HR_ADMIN_ROLES`. There is NO finer-grained permission tier below `member`;
"site engineer" vs "architect" vs "sales rep" are job-function labels for
realistic *usage pattern* testing, not distinct technical roles).

### Demo org: "Meridian Skyline Group"

New org, NOT a reuse of the existing single-user "Skyline Builders" demo org
(confirmed via direct query: that org has exactly 1 member, likely still in
use from the 2026-07-12/13 real-user test pass -- leave it untouched).

**50-user roster** (org role in brackets; department drives which modules
they realistically exercise, not a real permission difference):

| # | Persona | Org role | Department / function | Primary modules to test as |
|---|---|---|---|---|
| 1 | Founder/CEO | owner | Leadership | Everything (spot-check breadth) |
| 2 | COO | admin | Leadership | Dashboard, Reports, GRC, Finance |
| 3-4 | 2x Finance Manager | admin | Accounting | Accounting, Invoices, Budgets, Expenses |
| 5-6 | 2x Accountant | member | Accounting | Invoices (create/view only), Expenses |
| 7 | HR Manager | admin | HR | HR Dashboard, Employees, Payroll, Recruitment |
| 8-9 | 2x HR Executive | member | HR | Employees (view/create), Recruitment |
| 10 | Payroll Admin | admin | HR/Finance | Payroll (all sub-tabs) |
| 11 | Sales Head | admin | Sales | Sales Dashboard, Leads, Opportunities, Quotations, Sales Orders, Customers |
| 12-14 | 3x Sales Executive | member | Sales | Leads, Opportunities, Quotations (create), Customers (view) |
| 15 | Compliance/Risk Officer | admin | GRC | Risk & Compliance (all tabs) |
| 16 | Internal Auditor | member | GRC | Risk & Compliance (audit/findings tabs only) |
| 17-20 | 4x Project Manager | admin | Execution | Schedule, Scope/BOQ, Work Progress, Site Diary, Meetings, Change Orders, Documents, Permits |
| 21-30 | 10x Site Engineer | member | Execution/Field | Work Progress, Site Diary, Manpower & Attendance, RFIs, Submittals, Punch List |
| 31-33 | 3x Architect | member | Design | Mood Boards, FF&E, Floor Plans, Documents |
| 34-36 | 3x Interior Designer | member | Design | Mood Boards, FF&E, Floor Plans |
| 37-40 | 4x Procurement/Vendor Coordinator | member | Resources | Materials, Vendors |
| 41-44 | 4x QS/Estimator | member | Execution | Scope/BOQ, Budgets |
| 45-46 | 2x Front-desk/Admin | member | Resources | Documents, Permits, Meetings |
| 47-48 | 2x KPI/Reporting Analyst | member | Intelligence | KPIs, Reports |
| 49 | AI Copilot power-user | member | Intelligence | AI Copilot |
| 50 | New hire, no data yet | member | Execution | Every module's real empty-state (deliberately -- confirms empty states render correctly, not just happy-path with pre-seeded data) |

**Project data**: at least 5 real active projects (not the minimum 2 from
the prior real-user test), spanning both construction and interior-design
categories, with enough BOQ/schedule/RFI/expense/labour data on at least 2
of them to exercise pagination/filtering (Wave 1/2's "500-project scale"
depth work is meaningless to test against 1-2 projects with a handful of
rows each).

### Per-module test procedure (apply to every module below)

For each module, as the listed persona(s):
1. **State intended behaviour first** -- from `PROJEXA_TASK_GOVERNANCE.md`,
   `AGENTS.md`, or the specific compliance-tracker service the module
   aliases (named per-module below) -- write this down BEFORE clicking
   anything, so "did it work" has a real target, not a vibe check.
2. Load the page as that persona. Record: does it render, is data real
   (matches what's in the DB, not a loading skeleton stuck forever or a
   silent empty array where rows should exist)?
3. Perform the module's real write action(s) (create/update/status-change/
   approve/download, per the table below).
4. Verify the UI's own success/failure signal.
5. **Verify independently via Supabase MCP `execute_sql`** against the named
   target table(s) -- the actual row exists/changed, with the right values.
   This is the step that catches "UI says success but nothing was written"
   or "UI says 403 but the write actually went through" bugs -- do not skip
   it because the UI looked fine.
6. Log a gap entry ONLY if step 2-5 diverged from step 1's stated intent.
   No entry needed for working modules -- this is a gap log, not a full
   test report.

### Module x verification-target matrix

| Nav section | Page | Aliases (compliance-tracker service) | Target table(s) to verify | Key actions to test |
|---|---|---|---|---|
| Overview | Dashboard | multiple (aggregation) | -- (read-only rollup) | Loads real cross-project numbers |
| Execution | Schedule | pms-issue-service / schedule-service | pms_issues | Create task, drag Gantt date |
| Execution | Meetings | pms-meeting-service | pms_meetings, pms_meeting_outcomes | Schedule meeting, log outcome |
| Execution | Scope (BOQ) | construction-boq-service | construction_boq_line_items | Add BOQ line, verify amount = qty*rate |
| Execution | Work Progress | construction-progress-service | construction_work_progress_entries | Log progress entry |
| Execution | Site Diary | construction-site-diary-service | construction_site_diaries | Create diary entry |
| Execution | Documents | document-service | documents | Upload, category filter |
| Execution | Permits | documents (category=permit) | documents | Create permit, check expiry badge |
| Field | RFIs | (construction field workflow) | rfis-equivalent table | Create RFI, close RFI |
| Field | Submittals | " | submittals-equivalent table | Create, approve |
| Field | Punch List | construction-field-workflow-service | construction_punch_list_items | Create, mark done |
| Field | Change Orders | construction-change-order-service, esignature-service | change_orders-equivalent | Send for approval, e-sign flow |
| Design | Mood Boards | interior-design-service | mood-boards table | Create board, add item |
| Design | FF&E | interior-design-service | ffe table | Add item, verify margin calc |
| Design | Floor Plans | interior-floorplan-service | floor-plans table | View only (2D/3D excluded from scope) |
| Resources | Manpower & Attendance | construction-labour-service | construction_labour_roster, construction_attendance | Mark attendance, verify daily-cost calc |
| Resources | Materials | erp-inventory / construction-specific | materials-equivalent | Add material |
| Resources | Vendors | erp-buying-service | erp_suppliers | Create vendor |
| Sales | Sales Dashboard | crm-service / erp-selling-service | -- (rollup) | Pipeline totals match underlying rows |
| Sales | Leads | crm-service | crm_leads, crm_stage_history | Create lead, move stage, verify history row written |
| Sales | Opportunities | crm-service | crm_opportunities, crm_stage_history | Create, move stage |
| Sales | Quotations | erp-selling-service | erp_quotations | Create, revise, **approve as a manager persona -- EXPECT this to fail per PROJEXA-IDENTITY-BRIDGE-01, log tersely with cross-reference**, download PDF (verify real PDF bytes, not an error page) |
| Sales | Sales Orders | erp-selling-service | erp_sales_orders | Convert from quotation, bulk status update |
| Sales | Customers | erp-selling-service | erp_customers | Create, view Customer 360 |
| GRC | Risk & Compliance | risk-register-service, compliance-service, access-review-service, fraud-case-service | risks, audit_engagements, audit_findings, policies, vendor_risk_profiles, fraud_cases | Create risk (verify severity band computed), create audit finding, advance CAPA status |
| Finance | Budgets | pms-budget-service / erp-budget-service | project-budgets table | Create budget line |
| Finance | Expenses | construction-expense-service | construction_expense_entries | Log expense |
| Finance | Accounting | erp-accounting-service, erp-financial-report-service | erp_journal_entries, erp_journal_entry_lines | Create journal entry (verify debit=credit enforced), view trial balance/P&L/balance sheet, P&L-by-project |
| Finance | Invoices | erp-invoicing-service | erp_sales_invoices, erp_credit_notes | Create invoice, record payment (verify GL posting + outstandingAmount decrement), view AR aging |
| HR | HR Dashboard | hr-service | -- (rollup) | Headcount/leave/payroll numbers match underlying rows |
| HR | Employees | hr-service | employee_profiles | Create employee (verify employmentStatus/emergency-contact fields save), view detail |
| HR | Payroll | erp-payroll-service | payroll runs/payslips tables | **Run payroll as a manager persona -- EXPECT this to fail per PROJEXA-IDENTITY-BRIDGE-01, log tersely with cross-reference**, download payslip PDF (verify real PDF bytes) |
| HR | Recruitment | recruitment-service | job_openings, candidates, applications | Create job opening, move candidate through pipeline stages |
| Intelligence | KPIs | construction-kpi-service, kpi-hub-service | construction_kpi_entries | Log KPI entry |
| Intelligence | Reports | report-engine-service | -- (generated) | Generate a real report, confirm it's not a data_gap placeholder |
| Intelligence | AI Copilot | construction-ai-service (dispatchTool, 7 deterministic tools) | -- (read-only compute) | Run "Budget Status" tool, verify real numbers not hallucinated |
| (root) | Settings | organizations/memberships | organizations, memberships | View org settings, member list |

### Automated pre-flight (Part 1 should run this before touching the browser)
Query row counts per table above for the new demo org before starting, so
"table has data after my action" checks aren't fooled by pre-existing rows
from seed data.

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

- 2026-07-14 (follow-up): Owner restructured the pipeline from the original
  6-stage/N-session shape into 2 parts mapped to Claude Desktop Sonnet 5
  effort tiers -- Part 1 (LOW effort: mechanical E2E testing + gap
  registration, run off a pre-written literal test script since Low effort
  needs explicit instructions, not an open-ended brief) and Part 2 (HIGH
  effort: analysis, root-cause, planning, implementation). Claude Desktop is
  to manage the Part 1 -> Part 2 hand-off automatically. Rewrote this file's
  "Pipeline structure" section and CONTROLLER.yaml's PRIORITY-16 entry
  accordingly. Gate unchanged: still blocked on PRIORITY-15 status: done.
  Priority 15's state as of this check (re-read from CONTROLLER.yaml, not
  re-verified via gh this pass): landing page DONE/MERGED (projexa PR #6),
  HR/Payroll DONE/MERGED (compliance-tracker PR #330 + projexa PR #7),
  Sales/CRM READY but blocked on an external CI outage (compliance-tracker
  PR #332 + projexa PR #8, not yet merged), GRC+Accounting+Invoicing still
  in-progress. Next session should re-verify via `gh pr list` before
  concluding PRIORITY-15 is done -- this entry alone is not sufficient
  confirmation.

- 2026-07-14 (unblock): PRIORITY-15 reached status: done, including a Wave 2
  follow-up (quotation PDF/approval gating, HR employee fields/payslip PDF/
  role UI) the Owner requested after Wave 1 closed -- all 8+4 PRs merged,
  independently audited each time (see CONTROLLER.yaml PRIORITY-15). Gate
  lifted per Owner's explicit "you dont need my permission" instruction to
  proceed straight into Priority 16 without further sign-off. Rewrote this
  file's STATUS line and wrote the full "Part 1 test script" section (50-
  persona roster for a new "Meridian Skyline Group" demo org, per-module
  test procedure, and the module x verification-target matrix covering all
  33 real PROJEXA pages against their real compliance-tracker service +
  target DB table). Flagged PROJEXA-IDENTITY-BRIDGE-01 (logged as its own
  CONTROLLER.yaml entry) as an expected, already-understood recurring
  failure Part 1 will hit ~17 times -- instructed Part 1 to log it once in
  full and cross-reference subsequent occurrences rather than producing 17
  near-duplicate gap entries. Next action: dispatch Part 1 execution.
