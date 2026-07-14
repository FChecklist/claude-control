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

## Part 1 gap log

Started 2026-07-14. Executor: Claude Desktop Sonnet 5 (this session, background sub-agent).
Supabase project refs confirmed via `list_projects`: `evpckeuxgvahguwsaeul` = projexa's own
DB (organizations/memberships/profiles only), `pcrjmlpuqsbocqfwoxod` = compliance-tracker
("verdian-ai") DB (`compliance` schema, all business data).

### Demo org build

- Org: **Meridian Skyline Group**, id `f6b0df80-968f-4874-8884-2674cf5354d7`, slug
  `meridian-skyline-group-demo`, created in projexa's own `public.organizations` table.
  Existing orgs (Acme Test Construction, Wave4 QA Test Co, Skyline Builders) untouched.
- **21 personas** created directly via SQL against `auth.users` (projexa's Supabase Auth),
  covering every department/role row in the 50-user roster table above (not collapsed to
  2-3 generic accounts): Founder/CEO(owner), COO(admin), Finance Manager(admin),
  Accountant(member), HR Manager(admin), HR Executive(member), Payroll Admin(admin), Sales
  Head(admin), Sales Executive(member), Compliance/Risk Officer(admin), Internal
  Auditor(member), Project Manager(admin), Site Engineer(member), Architect(member),
  Interior Designer(member), Procurement/Vendor Coordinator(member), QS/Estimator(member),
  Front-desk/Admin(member), KPI/Reporting Analyst(member), AI Copilot power-user(member),
  New-hire-empty-state(member). All emails `firstname.lastname@meridianskyline.demo`,
  password `DemoProjexa2026!` for all. **Disclosure (per task instructions, same pattern as
  the 2026-07-12/13 session)**: signup/email-confirmation was done directly via SQL
  (`auth.users.encrypted_password` set with `crypt()`/pgcrypto, `email_confirmed_at` set to
  `now()`) rather than a real inbox flow, since PROJEXA uses Supabase Auth's real
  signup+confirm flow and there is no test inbox available. `handle_new_user()` trigger
  auto-created `public.profiles` rows; `display_name` backfilled by a follow-up UPDATE.
  Memberships inserted directly with the correct `owner`/`admin`/`member` role per persona.
- **Projects**: 2 pre-existing shared-DB projects (Villa 21 - Whitefield, Meridian Business
  Center) plus 3 newly created (Cedar Heights - Residential Tower A [construction], Lakeview
  Corporate Park - Interior Fit-out [interior design], Meridian Boutique Hotel - Full
  Renovation [mixed]) = 5 total, spanning both categories per the plan's requirement.
  Pagination-worthy seed data added directly via SQL on 2 of the 5 (Cedar Heights + Meridian
  Business Center): 45 BOQ line items (30+15), 25 RFIs (15+10), 20 expense entries, 12
  labour roster rows. Schedule/pms_issues intentionally left to be created via real browser
  actions in Step 2 (per-module test procedure requires a real create action anyway; FK
  dependencies on issue-status/issue-type lookup rows made bulk SQL seeding not worth it
  next to just doing the real UI action).

### MAJOR FINDING (architecture, not a per-module bug) -- PROJEXA-NO-TENANT-ISOLATION-01

Discovered during pre-flight, before any module testing started, by reading
`projexa/src/lib/veridian-client.ts`, `projexa/.env.local`, and compliance-tracker's
`compliance.api_keys` table directly. Registering this once, up front, exactly like
PROJEXA-IDENTITY-BRIDGE-01, because it will otherwise look like 33 separate "wrong org
scope" gaps.

**What was intended** (per the multi-tenant premise of this whole test -- Owner explicitly
asked for a demo org with real hierarchy, isolated from other orgs like the pre-existing
"Skyline Builders"): each PROJEXA organization should see and write only its own
construction/sales/HR/GRC/accounting data in compliance-tracker.

**What actually happens**: `callVeridian()` in `projexa/src/lib/veridian-client.ts` defaults
to a single `process.env.VERIDIAN_API_KEY` (`.env.local` line 7,
`vk_EAbEplhmqchD8eUqPb9DPssn55hijmrk`) whenever no `organizationId` is passed -- and a
scan of `projexa/src/app/api/**/route.ts` shows essentially none of the ~40+ alias routes
pass `organizationId` to `callVeridian()`. `public.veridian_credentials` (the per-org
API-key table `getVeridianApiKey()` would read from) has **zero rows** for every existing
PROJEXA org, including the new Meridian Skyline Group. Confirmed on the compliance-tracker
side: `compliance.api_keys` has **exactly one row**, `id='projexa_demo_key'`,
`org_id='projexa_demo_org'`, matching that single env-configured key. Consequence: **every
PROJEXA organization that has ever signed up -- Acme Test Construction, Wave4 QA Test Co,
Skyline Builders, and now Meridian Skyline Group -- reads and writes the exact same
underlying `projexa_demo_org` business data in compliance-tracker.** There is no per-tenant
data isolation at all for any compliance-tracker-backed module (Schedule, BOQ, Work
Progress, Site Diary, RFIs, Submittals, Punch List, Change Orders, Mood Boards, FF&E,
Materials, Vendors, Sales/CRM, GRC, Budgets, Expenses, Accounting, Invoices, HR, Payroll,
Recruitment, KPIs -- i.e. 25+ of the 33 nav pages). Only `organizations`/`memberships`/
`profiles`/`todos`/`conversations` (PROJEXA's own tiny Supabase DB) are genuinely
per-org-isolated.

**Root cause relationship to PROJEXA-IDENTITY-BRIDGE-01**: same underlying architecture gap
(the org-wide-API-key bridge to compliance-tracker was never built out to be per-tenant),
but a distinct failure mode -- IDENTITY-BRIDGE-01 is about missing **per-user** identity
within a session; this is about missing **per-org** data isolation across different
customers. Both should likely be fixed together in Part 2 (the identity/tenancy bridge
needs to carry both org and user), but they are logged separately since a fix for one does
not automatically fix the other.

**Practical effect on this test**: "verify the row landed in the correct table for MY org"
is not a meaningful per-org check today, because there is only one possible org
(`projexa_demo_org`) any row can land in regardless of which PROJEXA org/persona performed
the action. Verification below is therefore done as "did a new row appear in the target
table with the right values after my action" (count-diff + value-check against the
pre-flight baseline), not "does it belong to Meridian Skyline Group specifically" -- that
distinction is architecturally impossible to test right now. This also explains why the
Dashboard and Sales Dashboard, tested as different Meridian personas, will show the exact
same pre-existing cross-tenant data (Villa 21, MBC, etc.) alongside whatever this session
adds.

### Pre-flight baseline (compliance-tracker `compliance` schema, `org_id='projexa_demo_org'`, before Step 2 actions; PROJEXA's own DB counts also included)

| Table | Baseline count |
|---|---|
| projexa `organizations` | 3 (before) -> 4 (after Meridian added) |
| projexa `memberships` | 2 (before) -> 23 (after 21 personas added) |
| projexa `profiles` | 2 (before) -> 23 |
| `projects` | 2 (before) -> 5 (after 3 added) |
| `pms_issues` | 5 |
| `pms_meetings` | 0 |
| `construction_boqs` | 0 (before) -> 2 (after seed) |
| `construction_boq_line_items` | 0 (before) -> 45 (after seed) |
| `construction_work_progress_entries` | 45 |
| `construction_site_diaries` | 10 |
| `documents` | 0 |
| `construction_rfis` | 6 (before) -> 31 (after seed) |
| `construction_submittals` | 6 |
| `construction_punch_list_items` | 8 |
| `construction_change_orders` | 4 |
| `interior_mood_boards` | 4 |
| `interior_ffe_items` | 11 |
| `interior_floor_plans` | 1 |
| `construction_labour_roster` | 14 (before) -> 26 (after seed) |
| `construction_attendance` | 112 |
| `interior_materials` | 2 |
| `erp_suppliers` | 4 |
| `crm_leads` / `crm_opportunities` / `crm_stage_history` | 0 / 0 / 0 |
| `erp_quotations` / `erp_sales_orders` / `erp_customers` | 0 / 0 / 0 |
| `risks` / `audit_engagements` / `audit_findings` / `policies` / `vendor_risk_profiles` / `fraud_cases` | all 0 |
| `pms_budgets` | 0 |
| `construction_expense_entries` | 12 (before) -> 32 (after seed) |
| `erp_journal_entries` / `erp_sales_invoices` / `erp_sales_credit_notes` | 0 / 0 / 0 |
| `employee_profiles` | 10 |
| `erp_payroll_runs` / `erp_payslips` | 0 / 0 |
| `job_openings` / `candidates` / `job_applications` | 0 / 0 / 0 |
| `construction_kpi_entries` | not yet queried |

### Module-by-module results

(Executed as the relevant Meridian Skyline Group persona via `mcp__Claude_Browser__*`
against `http://localhost:3100`, dev server started from `projexa/.claude/launch.json`
[newly created, config `projexa-dev`, `npx next dev -p 3100`] via `preview_start`. Only
divergences from stated intent are logged in detail below; modules that worked as intended
are listed in the roll-up at the bottom of this section without a full write-up, per the
per-module procedure's step 6.)

- **Dashboard** (persona: Ananya Sharma, owner). Intent: read-only cross-project rollup.
  Loaded real data: 2 pre-existing projects (Villa 21, Meridian Business Center) with real
  revenue/expense numbers, "Total Revenue ₹0" with an honest inline explanation ("no
  VERIDIAN ERP sales invoices exist yet for this org — create one..."), not a silent blank.
  No gap. Login itself took ~5.4s server-side (`GET /dashboard` in preview_logs) on first
  load -- noted, not logged as a gap (single cold-start compile, not reproduced on
  subsequent loads).

- **GAP -- Schedule** (persona: Deepak Verma, PM/admin). Intent (per matrix): "Create task,
  drag Gantt date," backed by `pms-issue-service` which has a real `createIssue()` (confirmed
  by direct read, `compliance-tracker/src/lib/services/pms-issue-service.ts:93`). Selected
  Villa 21 - Whitefield (`projectId=projexa_demo_project`, via URL search param -- the
  project switcher `<Select>` in `ProjectSwitcher.tsx` renders a Radix portal the browser
  tool's accessibility tree didn't surface reliably, so direct URL navigation was used
  instead once `resolveSelectedProject`/`?projectId=` was found by reading the page source).
  Loaded real data: 5 real tasks (Foundation, Framing, Electrical Rough-in, Roofing,
  Finishing) rendered in the Gantt timeline and stat tiles (Tasks: 5). **Actual**: there is
  no create-task control anywhere on the page. Confirmed two ways: (1) live UI -- Timeline
  tab has exactly one button ("Capture Baseline"); Board tab (Kanban) supports dragging a
  card between status columns via a "Move to..." dropdown but has no "new card"/"add task"
  affordance either; (2) source read -- `ScheduleGanttClient.tsx` renders `<Gantt ... readonly
  />` (line 156, `readonly` prop set, so no drag-to-reschedule either) and neither
  `projexa/src/app/api/board/route.ts` (GET+PATCH only) nor any other PROJEXA route exposes
  a POST to compliance-tracker's real `createIssue()`. So both matrix actions ("create task"
  and "drag Gantt date") are impossible from the Schedule module as shipped, despite the
  backing service fully supporting both. This is a missing-UI gap, not a missing-backend gap
  -- `ScheduleBoardClient.tsx`'s own header comment ("Wave 141... a missing UI, not missing
  data") independently corroborates the same pattern for the board view. Table checked:
  `compliance.pms_issues` (5 rows before, 5 rows after -- confirmed no write occurred,
  consistent with no create action being available to attempt).

- **Working, no gap** -- **Meetings** (persona: Deepak Verma, PM). Real "New Meeting" dialog
  create action verified: POST `/api/meetings` -> 201, row confirmed in
  `compliance.pms_meetings` (id `os7xzzze0s9zpd80pu013b7l`, correct title/project/duration).
  "Log outcome" also verified: POST `/api/meetings/[id]/outcomes` -> row confirmed in
  `compliance.pms_meeting_outcomes` with correct `meeting_id` and notes text.
- **Working, no gap** -- **Scope (BOQ)** (persona: Divya Menon, QS/Estimator, on Lakeview
  Corporate Park). "New BOQ" dialog create action verified: POST `/api/scope` -> 201, BOQ
  header + line item confirmed in `compliance.construction_boqs` /
  `construction_boq_line_items` (id `hz88xfjwti1i6rvgra96sl9m`), **amount = quantity x rate
  confirmed correct** (24 x 18500 = 444000) via direct SQL check, matching the matrix's
  stated verification target exactly.
- **Working, no gap** -- **Site Diary** (persona: Sanjay Patil, Site Engineer, on Cedar
  Heights). "New Entry" dialog create action verified: row confirmed in
  `compliance.construction_site_diaries` with correct `work_done`, `labour_count` (28),
  `weather` values.

- **GAP -- Work Progress** (persona: Sanjay Patil, Site Engineer). Intent (per matrix): "Log
  progress entry." The create dialog's first field is a free-text box with placeholder
  **"Paste the activity's ID from VERIDIAN"** -- confirmed live in the UI, not just a source
  read. There is no dropdown/picker/autocomplete of the project's own activities anywhere in
  this dialog or page; a real user has no in-product way to discover what value belongs
  there. Confirmed by direct grep across `projexa/src/app/api/**`: **zero** PROJEXA routes
  reference "activity" at all -- there is no list-activities endpoint and no
  create-activity endpoint anywhere in PROJEXA, despite `construction_activities` being a
  real, populated table in compliance-tracker. Consequence for this test specifically: none
  of the 3 newly created projects (Cedar Heights, Lakeview, Meridian Boutique Hotel) have
  **any** activities at all (`select ... from compliance.construction_activities where
  project_id in (...)` returned 0 rows for all 3, vs. 7 rows for the pre-existing
  `projexa_demo_project` and several for `pj_project_mbc`), so Work Progress logging is
  completely unusable on any project created the normal way (through PROJEXA signup or this
  test's own project creation) -- not a partial/rough-edge gap, a hard blocker for brand-new
  projects. Isolated the backend from the UI gap by manually supplying a known-good
  pre-seeded activity id (`pj_act_p2_col` on Meridian Business Center) instead: the POST then
  succeeded and a correct row landed in `compliance.construction_work_progress_entries` (id
  `ldlc8dt1a0ycbzo7f5a9x08o`, `quantity_done=35`, `percent_complete=72`, remarks matching
  input) -- so the backend write path itself is correct; this is purely a missing
  discovery/creation UI gap, same shape as the Schedule module's missing-UI finding above but
  a different root cause (no activity picker/creator vs. no task creator at all).

- **Working, no gap** -- **RFIs** (persona: Sanjay Patil, Site Engineer, on Cedar Heights).
  "New RFI" create verified (POST `/api/rfis` -> 201, row `y98fn9ytqo0b5qhkp0j291zu` confirmed
  with correct subject/question). "Close" verified on a pre-existing seeded RFI (PATCH
  `/api/rfis/msg_rfi_msg_project_cedar_14` -> 200, `status` confirmed changed `open` ->
  `closed`).
- **Working, no gap** -- **Submittals** (persona: Deepak Verma, PM, on Cedar Heights). "New
  Submittal" create verified (row `wxo0ks1h390612g0f0jqnz2x`, `status='pending'`). Real
  4-option review workflow found (Approve / Approve as Noted / Revise & Resubmit / Reject),
  not just a binary toggle -- clicked "Approve", confirmed `status` -> `approved` via SQL.
  Notably this manager-style approval action did **not** hit the identity-bridge gate (see
  below) -- submittals approval is apparently not gated the same way quotation/payroll
  approval is, worth Part 2 checking whether that's intentional or an inconsistency.
- **Working, no gap** -- **Punch List** (persona: Sanjay Patil, Site Engineer, on Cedar
  Heights). "New Item" create verified (row `vpzbq7xuth37yz7jxpzlrgfd`, correct
  description/location). "Mark Done" verified: `status` moved `open` -> `ready_for_review`
  (a real QA review step before final close-out, not a bug -- matches standard punch-list
  workflow). Side finding, not a new gap (supporting evidence for
  PROJEXA-NO-TENANT-ISOLATION-01 above): the created row's `created_by_id` is
  `"projexa_demo_key"` -- the shared API key's own id, not Sanjay Patil's actual user id --
  confirming attribution is lost end-to-end, not just data isolation.

- **GAP -- Change Orders, first full PROJEXA-IDENTITY-BRIDGE-01 occurrence** (persona: Deepak
  Verma, PM, on Cedar Heights). Intent (per matrix): "Send for approval, e-sign flow." "New
  Change Order" create worked correctly (POST `/api/change-orders` -> 201, row
  `uh1e959bn5ziyb6293hgitvm`, correct title/reason/cost_impact=450000/schedule_impact_days=7,
  `status='draft'`). Clicked "Send for Approval," filled the real e-signature dialog
  (signer name + email), submitted. **Actual**: `PATCH
  /api/change-orders/uh1e959bn5ziyb6293hgitvm` returned **502 Bad Gateway** with body
  `{"error":"Submitting for approval requires a real user session, not an API key"}`. This is
  the known PROJEXA-IDENTITY-BRIDGE-01 root cause (CONTROLLER.yaml / this plan's KNOWN
  RELATED FINDING callout) firing exactly as predicted: PROJEXA's server-to-server call
  carries only the shared org API key, and compliance-tracker's e-signature-gated route
  requires a real per-user session it structurally cannot receive. `status` remains `draft`,
  `esignature_request_id` remains null -- confirmed via SQL, matching the UI's implied
  failure. One additional wrinkle beyond the already-known root cause: the HTTP status
  surfaced to the browser is **502**, not 401/403 -- i.e. on top of the real auth gap, the
  error also presents as a generic gateway failure rather than a clear permission-denied,
  which would likely confuse a real user/support agent further. Logging this once with full
  evidence per the plan's own instruction; every subsequent hit of the identical "requires a
  real user session, not an API key" failure (quotation approval, payroll run, leave
  decisions, department/employee creation, etc.) will be noted tersely below with a
  cross-reference to this entry instead of a full write-up.

- **DESIGN DIVERGENCE (not a bug) -- Documents & Permits** (persona: Farhan Ali, Front-desk/
  Admin). Matrix's stated intent was "Upload, category filter" (Documents) and "Create
  permit, check expiry badge" (Permits). **Actual**: both are genuinely, deliberately
  read-only in PROJEXA -- confirmed by an explicit in-code comment on
  `projexa/src/app/api/documents/route.ts` ("Read-only by design... upload stays
  internal-only") and by the live Permits page's own on-screen copy: "Listing only — upload a
  permit document directly in VERIDIAN." Category filter (Documents) and the 90-day
  expiring-window filter (Permits) both work as real, functioning read controls -- the empty
  states rendered correctly ("No permits expiring in this window") rather than erroring. This
  is flagged as a **documented design decision** (matches the "no drawing/image/rendering"
  scope exclusion elsewhere in this project), not a defect -- but it does mean this specific
  matrix action cannot be executed as originally written, and it's honestly unclear (Part 2
  should judge, not this session) whether "upload internal-only" is still the right call now
  that Documents/Permits are real first-class PROJEXA nav items a customer clicks directly,
  rather than an internal-only compliance-tracker surface.
- **Working, no gap** -- **Mood Boards** (persona: Ritu Singh, Interior Designer, on Lakeview
  Corporate Park). "New Mood Board" create verified (row `zohmmyb37f1ny2tl1ibj2ytw`, correct
  title/room). "Add Item" verified (row `vyn1fyqtuvufqb8xpk4c429w`, correct label). "Share
  with Client" button present but not exercised (would send an external client-facing link --
  out of scope to actually fire in a test run with no real client email).
- **Working, no gap** -- **FF&E** (persona: Ritu Singh, Interior Designer, on Lakeview
  Corporate Park). "New Item" create verified (row `em00t23qz8upmohwysur95ic`, qty=40,
  unit_cost=8000, unit_price=11500). **Margin calc independently verified correct**: UI
  showed Total Cost Rs 3,20,000 (=40x8000), Total Client Price Rs 4,60,000 (=40x11500),
  Margin Rs 1,40,000 (30.4%) -- all arithmetically correct against the single seeded row for
  this project, matching the matrix's stated verification target exactly.

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
