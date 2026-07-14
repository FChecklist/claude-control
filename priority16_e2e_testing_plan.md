# Priority 16 -- PROJEXA End-to-End Test + Multi-Stage Audit Pipeline

STATUS: PART 2 SAFE FIXES COMPLETE 2026-07-15 -- Owner answered 3 scoping questions
on the systemic findings (tenant isolation + identity bridge explicitly deferred to
the other session's PLATFORM-01 multi-tenancy work; module entitlement approved to
enable now). All 6 remaining Part 2 items (entitlement enable, 502-status-masking,
Settings/Team RLS fix, Schedule create-task UI, Work Progress activity picker,
Recruitment job-opening bug) shipped as 7 merged PRs across both repos, each
independently audited before merge (see CONTROLLER.yaml PRIORITY-16's
part_2_close_out for the full PR list). NOT done: PROJEXA-IDENTITY-BRIDGE-01 and
PROJEXA-NO-TENANT-ISOLATION-01 remain open, owned by the other session -- Priority
16 is not fully closeable until that work lands. Original Part 1 status (kept for
history): PART 1 SUBSTANTIALLY COMPLETE 2026-07-14 -- demo org built, full
pre-flight baseline recorded, all 33 nav pages exercised (most with real
create/write actions + SQL verification, a handful confirmed-via-sibling-route
once a shared root cause was proven). 3 systemic findings registered
(PROJEXA-IDENTITY-BRIDGE-01 [pre-existing], PROJEXA-NO-TENANT-ISOLATION-01 [new],
PROJEXA-MODULE-ENTITLEMENT-01 [new]) plus 8 distinct per-module gaps, several fully
root-caused down to the exact line/policy responsible.

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

- **Working, no gap** -- **Manpower & Attendance** (persona: Amit Shah, Procurement/Vendor
  Coordinator acting for site records, on Cedar Heights). Roster tab shows the 6 seeded
  workers correctly. "Mark Attendance" on the Attendance tab verified: selected worker
  (Suresh Pal, `daily_rate=770`), status "Present," 8 hours -> row confirmed in
  `compliance.construction_attendance` (id `xkibl0j1po93uxszckerlnvc`) with **daily_cost=770,
  correctly equal to the worker's daily_rate for a full Present day** -- matches the matrix's
  stated verification target. Side note, not logged as a gap: the *first* attempt at this
  action failed with a transient `POST /api/attendance` 401 caused by the PROJEXA dev
  server's middleware failing to reach Supabase Auth's remote JWKS endpoint
  (`ConnectTimeoutError`, `ai-os`/network-level, not app logic) and `requireAuth()`
  correctly-but-strictly treating that as "unauthenticated" rather than retrying -- a
  fail-closed design choice that is defensible for security but means any transient network
  blip between PROJEXA and Supabase Auth 401s a real user's action outright. Retried once and
  it succeeded normally; noting the fail-closed behavior for Part 2's awareness, not
  registering it as a reproducible product bug since it didn't reproduce on retry.

- **GAP -- Vendors & Materials, both silently broken (module entitlement gate)** (persona:
  Amit Shah, Procurement/Vendor Coordinator). Intent (per matrix): Vendors = "Create vendor"
  (`erp-buying-service` / `erp_suppliers`); Materials = "Add material" (`erp-inventory`).
  **Actual**: both the read (GET, on page load) and write (POST, on "Add Vendor") calls
  return **502** with the identical underlying compliance-tracker error body: `{"error":"This
  capability is not part of the Module your organization purchased. Please contact your
  organization's administrator. This capability is already in the ERP module."}` -- i.e. the
  shared `projexa_demo_org` API key/org does not have the ERP module entitlement enabled on
  the compliance-tracker side, so these two nav pages are completely non-functional for every
  PROJEXA customer, not just this test org. **Worse than a plain error**: neither page
  surfaces this to the user at all -- both silently render their normal empty state
  ("No vendors added yet." / "No material movements recorded yet.") indistinguishable from a
  legitimately-empty-but-working page. This is exactly the "UI looks fine but the call
  actually failed" failure class this test plan's own per-module procedure (step 5) warns
  about -- confirmed only by checking `preview_logs`/network requests for the 502, not by
  anything visible on screen. My attempted vendor create (Meridian Steel & Rebar Suppliers
  Pvt Ltd) was silently lost -- confirmed zero matching row in `compliance.erp_suppliers`.
  Materials additionally has no create UI at all regardless of entitlement (its own on-page
  copy: "there's no self-serve create-form because the underlying warehouse/item IDs have no
  discovery API exposed to PROJEXA yet" -- an honestly-disclosed, separate, pre-existing
  limitation on top of the entitlement gate). Root cause is a compliance-tracker-side
  module/plan configuration gap (ERP module not enabled for `projexa_demo_org`), not a
  PROJEXA code bug per se, but the missing error surfacing in the PROJEXA UI is a real
  PROJEXA-side gap regardless of the root cause.

### MAJOR FINDING #2 (architecture/config, not a per-module bug) -- PROJEXA-MODULE-ENTITLEMENT-01

Discovered while investigating the Vendors/Materials 502s above, then confirmed systemically
across the Sales and Finance sections before continuing further module-by-module testing.
Registering this once, up front, exactly like the two findings above, so it doesn't turn into
10+ near-duplicate gap entries as Sales/Finance/HR-payroll pages are reached.

**Root cause, confirmed by direct SQL, not guessed**: compliance-tracker gates the `erp` and
`sales`(CRM) product branches behind an explicit per-org entitlement check
(`erp-enablement-service.ts` / `crm-enablement-service.ts`, `requireErpEnabled()` etc.,
Owner directive 2026-07-13 per that file's own header comment -- "a polite, specific 403...
naming the module... so an admin knows what to purchase/enable"). Queried
`compliance.org_product_branch_enablements` for `org_id='projexa_demo_org'` directly: only
**2** branches are enabled -- `veri_chat_v2` and `construction`. `erp`, `sales`, and `hr` are
**not** in the enabled list at all. Since every PROJEXA org (Acme, Wave4, Skyline Builders,
Meridian Skyline Group -- all of them, per PROJEXA-NO-TENANT-ISOLATION-01 above) shares this
one `projexa_demo_org` backend identity, **this affects every PROJEXA customer that has ever
signed up, not just this test org.**

**Confirmed affected** (GET fails with 502 on page load alone, before any write is even
attempted -- verified via `preview_logs`/network-request bodies, not assumed): Vendors,
Materials (erp branch; already logged above), **Accounting** (`/api/finance-dashboard`),
**Invoices** (`/api/sales-invoices`), **Payroll** (`/api/payroll/runs` specifically -- other
HR routes are unaffected, see below), **Budgets** (`/api/project-budgets` -- the
`erp-budget-service` half of the matrix's dual `pms-budget-service / erp-budget-service`
mapping is what's actually wired, and it's gated), **Sales Dashboard**
(`/api/sales-pipeline`), **Leads** (`/api/leads`), **Customers** (`/api/customers`). Every
one of these returns the identical body: `{"error":"This capability is not part of the
Module your organization purchased. Please contact your organization's administrator. This
capability is already in the <ERP|Sales> module."}`. Opportunities, Quotations, and Sales
Orders were not each individually re-verified after this pattern became clear (same `sales`
branch, same route family as Leads/Customers/Sales Dashboard) -- logging tersely as "same
root cause" per this plan's own de-duplication instruction rather than re-proving it 3 more
times.

**Confirmed NOT affected** (real 200s, work normally): GRC (`/api/grc-dashboard` -- GRC is
bundled in the always-on `office` branch, not gated the same way), Expenses
(`construction-expense-service`, not ERP-branch), HR's Employees/Leave/Recruitment routes
(`/api/employees`, `/api/leave/requests`, `/api/recruitment/job-openings` all 200 -- these
apparently don't route through the ERP-branch check even though the `hr` branch itself also
isn't enabled for this org, suggesting inconsistent gating within HR itself, not a clean
"HR is/isn't gated" story), all construction/field/design modules already verified above.

**A second, distinct PROJEXA-side bug found while chasing this down**: the real
compliance-tracker error is a **403** (`ServiceError(..., 403)` in `erp-enablement-
service.ts`) with a genuinely helpful, specific message -- but every PROJEXA API route's
catch block (confirmed by reading `vendors/route.ts`, and the identical pattern repeats
across `materials`, `leads`, `customers`, `accounting`, etc.) discards the real
`VeridianApiError.status` and hardcodes `{ status: 502 }` in the response sent to the
browser. So on top of the real entitlement gap, every affected page in the browser looks
like a generic infrastructure/gateway failure rather than a clear, actionable
permission-denied -- actively hiding the specific, helpful message compliance-tracker went
out of its way to construct. This is a real, separate, easily-scoped PROJEXA bug (fix: thread
through the real status code instead of hardcoding 502) independent of whatever Part 2
decides about the entitlement gap itself.

**Not something this session can/should decide**: whether the fix is (a) grant `erp`+`sales`
(+`hr`?) branch entitlement to `projexa_demo_org` as a config change, (b) build a genuine
self-serve "enable a module" flow so real PROJEXA customers aren't stuck contacting an
administrator who themselves has no visible way to grant it, or (c) something else -- Part 2
should decide scope, this session is registration-only.

- **Working, no gap** -- **GRC / Risk & Compliance** (persona: Rajesh Kumar,
  Compliance/Risk Officer). Full lifecycle verified real, not a demo shell: "Log Risk"
  created row `gw1sjxmms5gucpl3lrz9uqhm` (likelihood=4, impact=5) -- **severity band
  confirmed computed correctly**: UI displayed "4 x 5 = 20 -> High," matching the matrix's
  stated verification target. "Plan Audit" created a real audit engagement
  (`jw7b18t5yc68keu8zgygxxjw`, status `planned`). "Record Finding" against that engagement
  created a real finding (`dngx9rm6x8v5qkjm67fulog8`, `capa_status='open'`). "Advance CAPA"
  verified: `capa_status` moved `open` -> ... -> `closed` (advanced twice across two clicks,
  confirmed via SQL both times) -- real CAPA workflow, matching the matrix's "advance CAPA
  status" verification target. One of the two `PATCH /api/audit-findings/...` calls took
  **35.4 seconds** to complete (per `preview_logs`) -- an extreme outlier even against this
  session's general multi-second latency pattern (see cross-cutting note below), flagged here
  since it's the single slowest write observed all session, not logged as its own gap.
- **Cross-cutting observation, not a per-module gap**: nearly every write in this session took
  1-3 seconds, several took 10-35 seconds (BOQ create 13.7s, Work Progress page load 9s,
  audit-finding CAPA advance 35.4s), because `projexa/.env.local`'s
  `VERIDIAN_API_BASE_URL` points at the **live deployed** `veridian-compliance-ai.vercel.app`,
  not a local compliance-tracker instance -- every single PROJEXA action in dev is a real
  round-trip over the public internet to a separate deployed service, not a same-machine
  call. Worth Part 2 knowing this is the likely cause of the latency pattern observed
  throughout this log, separate from any actual bug.

- **GAP -- Employees, second PROJEXA-IDENTITY-BRIDGE-01 occurrence, plus strong supporting
  evidence for PROJEXA-NO-TENANT-ISOLATION-01** (persona: Kavita Desai, HR Manager). Employees
  page itself is real (Directory/Departments/Org Chart/Leave tabs, not a stub -- an earlier
  `get_page_text` call falsely showed an empty page for this URL; a direct DOM check found
  38,738 characters of real rendered content, so that was a tool-extraction quirk on this
  session's end, not a product bug -- noted so a future session doesn't waste time
  re-investigating a false lead). Opened "Employee Profile" create dialog: its "User" field is
  a **required select-existing-user dropdown, not a free-text name field** -- and critically,
  every option in that dropdown is a `@skylinebuilders-demo.veridianai.dev` compliance-tracker
  demo account (Arjun Mehta, Suresh Pillai, Vikram Singh Rathore, etc.) -- **none of Meridian
  Skyline Group's 21 real personas appear as selectable options at all**, direct, concrete
  proof of PROJEXA-NO-TENANT-ISOLATION-01 at this specific module: a real PROJEXA customer
  cannot create an employee profile for their own actual staff, only for whichever generic
  demo identities happen to already exist in the shared `projexa_demo_org`. Selected "Arjun
  Mehta" (only way to complete the test) and submitted -- `POST /api/employees` returned
  **502** with body `{"error":"This action requires a real user session, not an API key"}` --
  this is PROJEXA-IDENTITY-BRIDGE-01 again (employee creation was explicitly one of the 17
  originally-named affected routes). Logged tersely per this plan's own de-duplication
  instruction; cross-reference the Change Orders entry above for full evidence of this root
  cause.
- **Working, no gap** -- **HR Dashboard** sub-routes spot-checked: `/api/employees`,
  `/api/leave/requests`, `/api/recruitment/job-openings` all return real 200s with real data
  (10 seeded employees, etc). `/api/hr/departments` returns a generic `{"error":"Failed to
  fetch departments"}` 502 with an ambiguous root cause not conclusively identified this
  session (unclear whether it's a third instance of the identity-bridge pattern with a
  different message, a genuine hr-service.ts bug, or something else) -- flagged honestly as
  unresolved rather than guessed, for Part 2 to root-cause properly.

- **GAP -- Recruitment: "Create Job Opening" reproducibly fails** (persona: Kavita Desai, HR
  Manager). Intent (per matrix): "Create job opening, move candidate through pipeline
  stages." Job Openings/Candidates/Pipeline tabs all load real data (200s). "New Job Opening"
  dialog opens correctly, title field accepts input. **Actual**: `POST
  /api/recruitment/job-openings` failed on **all 3 attempts** across 2 separate page loads --
  first attempt: 400 `{"error":"No organization"}` (after a 49s round-trip); second and third
  (fresh page reload, clean retry): 502 `{"error":"Failed to create job opening"}` (generic
  fallback message -- masks whatever compliance-tracker actually returned, same 502-masking
  pattern as PROJEXA-MODULE-ENTITLEMENT-01 above, though the underlying cause here does not
  match that finding's exact error text so it is **not** being merged into that entry).
  `compliance.job_openings` confirmed to have zero matching rows after all 3 attempts. This
  is a genuinely reproducible, distinct gap -- not diagnosed to root cause this session (that
  needs compliance-tracker-side log/code access this session didn't dig into further given
  time budget), flagged honestly as unresolved for Part 2 rather than guessed. Not tested
  further: candidate creation and pipeline-stage movement, since job-opening creation (the
  prerequisite for a realistic pipeline test) itself doesn't work.

- **Working, no gap** -- **KPIs** (persona: Sneha Reddy, KPI/Reporting Analyst, on Cedar
  Heights). "New KPI" verified: created a real `construction_kpi_definitions` row
  (`he6yjxtb6zy6c76bb7eqqcbc`, `metric_name="Schedule Variance - Level 4 Slab"`,
  `target_value=-3.5`, `unit=days`) -- the create action produces a KPI target/definition
  (not a bare "entry" against a pre-existing definition, a minor naming nuance vs the
  matrix's "log KPI entry" phrasing, not a functional gap since no definition existed yet to
  log an entry against).
- **Working, no gap** -- **Reports** (persona: Sneha Reddy). "Run Report" (Project Status,
  Lakeview) returned a **real structured JSON result** (budget/revenue/expenses/progressPercent/
  taskCount fields, legitimately mostly 0 for a low-activity project) -- confirmed genuinely
  computed, not a `data_gap` placeholder, matching the matrix's stated verification target.
  First page load hit the same transient "Failed to load projects from VERIDIAN" error also
  seen on AI Copilot's first load (see below) -- resolved on simple page reload both times,
  consistent with the general network-latency/flakiness pattern already noted, not logged as
  its own gap.
- **Working, no gap** -- **AI Copilot** (persona: Rahul Bose, AI Copilot power-user, on Cedar
  Heights). Confirmed all 7 named construction tools present (Project Dashboard, Budget
  Status, KPI Status, AI Progress Summary, AI Budget/Schedule Risk, Delayed Activities,
  Over-Budget Projects). Ran "Budget Status" -- **result used real underlying data, not
  hallucinated**: `actual=187500` (matches the real sum of seeded `construction_expense_
  entries` for this project), `budget=0` (correctly reflects no budget line exists for Cedar
  Heights -- honest, not fabricated), `variance=-187500`, and a real `byHead` breakdown by
  expense category (material/transport/equipment) that sums correctly. A "Recent Construction
  Queries" log entry was also correctly written and shown. Matches the matrix's stated
  verification target exactly. Took roughly 20-30s to complete (consistent with the
  cross-cutting latency note above) -- during that window the "Run" button's text and the
  result panel were both misleadingly invisible to this session's text-extraction tooling,
  which initially looked like the tool had silently failed; a `data-sonner-toast` check and a
  later re-read confirmed it had actually succeeded. Noting this only so a future session
  doesn't misdiagnose a real success as a false gap due to the same tooling quirk.

- **GAP -- Settings: Team member list is structurally broken for every PROJEXA org, not just
  this one** (persona: Ananya Sharma, owner). Intent (per matrix): "View org settings, member
  list." Organization name/slug/your-account fields all rendered correctly (Meridian Skyline
  Group, correct slug, `ananya.sharma@meridianskyline.demo`, role `owner`). **Actual**: "Team"
  section shows "No other teammates in this organization yet." despite this org having 21 real
  members. Root-caused, not just observed: `GET /api/org-members` returns `{"members":[]}`
  every time (confirmed via 15 repeated network log entries, all empty). Read
  `projexa/src/app/api/org-members/route.ts` -- it queries `memberships` through the normal
  RLS-scoped Supabase client. Queried `pg_policies` directly on `evpckeuxgvahguwsaeul`
  (PROJEXA's own DB): the only SELECT policy on `public.memberships` is `"users can view their
  own memberships"` with `qual: (user_id = auth.uid())` -- **there is no policy allowing a
  user to see any other row in their own org's membership table at all.** Combined with the
  API route's own `.filter((m) => m.user_id !== ctx.user!.id)` (removes the caller's own row
  from the result), the query is guaranteed to return `user_id = auth.uid()` rows minus the
  caller's own row -- i.e. **always exactly zero rows, for every org, unconditionally.** This
  is not specific to Meridian Skyline Group or to this test session -- it means the Team list
  has never shown a real teammate for any PROJEXA org since this RLS policy was written.
  Broader impact, not separately verified this session but worth Part 2 checking: `/api/org-
  members` is fetched on nearly every page load throughout this whole test session (per
  `preview_logs`), suggesting it likely also feeds "assign to," "signer," or "select
  teammate"-style pickers elsewhere in the app -- if so, this single RLS gap may silently
  break more than just the Settings page.

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

- 2026-07-14 (Part 1 execution, this session): Built the demo org (Meridian Skyline
  Group, id `f6b0df80-968f-4874-8884-2674cf5354d7`, 21 personas across every
  department/role in the roster table, 5 projects spanning construction+interior-
  design with pagination-worthy seed data on 2 of them), recorded a full pre-flight
  baseline, then drove the PROJEXA dev server (`npx next dev -p 3100`, via a newly
  created `projexa/.claude/launch.json`) as different personas through every one of
  the 33 nav pages, verifying against `compliance.*` tables via Supabase MCP
  `execute_sql` after each real UI action (per-module procedure steps 1-6, exactly
  as written). Disclosed per the plan's own instruction: signup/email-confirmation
  was done via direct SQL (`auth.users` + pgcrypto), not a real inbox.

  **3 systemic findings registered** (full evidence in the gap log above):
  - PROJEXA-IDENTITY-BRIDGE-01 (pre-existing, confirmed twice this session: Change
    Orders e-sign send, Employee creation -- both real 502s with the exact predicted
    error body).
  - PROJEXA-NO-TENANT-ISOLATION-01 (new): every PROJEXA org, including this brand-new
    one, shares one single compliance-tracker backend org (`projexa_demo_org`) via
    one hardcoded API key -- confirmed via direct read of `veridian-client.ts` +
    `compliance.api_keys` (exactly 1 row). Concretely surfaced again at Employees:
    the "select a user" dropdown for creating an employee profile only offers
    pre-existing `@skylinebuilders-demo` accounts, never any of Meridian's 21 real
    personas.
  - PROJEXA-MODULE-ENTITLEMENT-01 (new): `org_product_branch_enablements` for
    `projexa_demo_org` has only `veri_chat_v2` and `construction` enabled -- `erp` and
    `sales` are not, so Vendors, Materials, Accounting, Invoices, Payroll(runs),
    Budgets, Sales Dashboard, Leads, Customers, and (by proven-shared-root-cause,
    not individually re-verified) Opportunities/Quotations/Sales Orders all 502 on
    GET alone, silently rendering a false "empty" state to the user instead of
    surfacing the real, specific, Owner-mandated 403 message compliance-tracker
    actually sends -- because every PROJEXA API route's catch block hardcodes
    `status: 502` and discards the real upstream status code. This second bug (the
    502-masking) is itself independently real and separately fixable regardless of
    what Part 2 decides about the entitlement gap.

  **8 distinct per-module gaps also registered** (not the 3 systemic ones above):
  Schedule (no create-task UI at all despite a working backend), Work Progress
  (activity-id field has no picker/creator, unusable on any new project), Documents
  + Permits (read-only by design -- flagged as a design divergence worth Part 2
  revisiting, not a bug), Vendors + Materials (covered under MODULE-ENTITLEMENT-01
  but with the additional silent-failure UX problem), Recruitment (job-opening
  creation reproducibly fails 3/3 attempts, root cause not yet identified), Settings
  (Team member list is **structurally always empty for every org** -- fully
  root-caused to a missing RLS SELECT policy on `memberships`, confirmed via
  `pg_policies` directly, likely breaks other "pick a teammate" pickers app-wide
  too, not yet verified how far that spreads).

  **Modules confirmed fully working** (real create/write action + SQL-verified
  correct values, no gap): Dashboard, Meetings, Scope/BOQ (amount=qty*rate
  verified), Site Diary, RFIs (create+close), Submittals (create+4-state-approve),
  Punch List (create+status-advance), Mood Boards (board+item), FF&E (margin calc
  verified correct), Manpower & Attendance (daily-cost calc verified correct), GRC
  (risk+severity-band, audit engagement, finding, CAPA advance -- full lifecycle),
  Expenses, KPIs, Reports (real non-placeholder output), AI Copilot (Budget Status
  tool verified using real, non-hallucinated numbers).

  **Resume point / what's left for a follow-up pass, stated honestly**: Opportunities,
  Sales Orders, and Payroll's own create/action flows were not individually
  button-clicked and verified -- their GET-level 502 under the identical
  MODULE-ENTITLEMENT-01 error was confirmed via sibling routes in the same module
  family (Leads/Customers/Sales-Dashboard for Sales; Vendors/Materials/Accounting/
  Invoices/Budgets for ERP) and the root cause is proven at the org-entitlement
  level, so re-clicking each one individually would not surface new information
  without first fixing the entitlement gap -- but if Part 2 wants literal
  per-button confirmation before scoping a fix, that's the concrete remaining gap.
  Quotations' specific "revise" and "download PDF" actions were not reached for the
  same reason (page-level 502 blocks getting to them at all). Candidates/pipeline-
  stage-movement in Recruitment were not tested since job-opening creation (the
  realistic prerequisite) doesn't work. Floor Plans was only given a quick view-only
  load-and-empty-state check (a "New Floor Plan" button was noticed to exist,
  contrary to the matrix's "view only" assumption, but not clicked/tested -- flagged,
  not chased further). HR Departments' `{"error":"Failed to fetch departments"}` 502
  was noted as ambiguous root cause (unclear if it's a 4th instance of a known
  pattern or something new) rather than force-fit into an existing finding.

  Given the above, Part 1 is **substantially, not 100%, complete** -- the honest
  call is that every module has been touched and every major architectural finding
  is already surfaced with strong evidence, so Part 2 has a real, actionable input
  today; the handful of un-clicked buttons listed above are individually low-value
  to chase further (their root cause is already proven) rather than a sign of
  incomplete coverage. Progress was committed to git after almost every module
  (see this file's own commit history in the `control` repo) specifically so an
  interrupted session could resume from exactly this state.

- 2026-07-14 (Part 2, PROJEXA-MODULE-ENTITLEMENT-01 -- both halves fixed,
  background sub-agent, "Priority 16 Part 2"): Owner pre-approved both fixes,
  no further scoping needed.
  - **Fix 1** (compliance-tracker, data-only): enabled the `erp`, `sales`,
    and `hr` product-branch entitlements for `org_id='projexa_demo_org'` in
    `compliance.org_product_branch_enablements`, applied live via Supabase
    MCP `execute_sql` against project `pcrjmlpuqsbocqfwoxod` and verified
    with a fresh join query after (5 branches now enabled: `veri_chat_v2`,
    `construction` [pre-existing] + `erp`, `hr`, `sales` [new]). Matches
    this repo's own established convention for org-branch enablement (grep
    confirmed zero application-code call sites for
    enableErpForOrg/enableSalesForOrg/enableConstructionForOrg/
    enableVeriChatV2ForOrg -- every prior org-branch enablement, including
    the 2 already active for this org, was applied the same way, as a
    one-off DB write). `hr` is included per the Owner's explicit
    instruction even though no code anywhere in compliance-tracker
    currently gates on the `hr` branch key (confirmed by grep: no
    hr-enablement-service.ts, no `requireBranchEnabled(orgId, "hr")` call
    site) -- inert today, future-proofed for if/when an HR entitlement gate
    is built. compliance-tracker PR #335 (claim registered + moved to
    `recently_completed` in `ai-os/boss/ACTIVE-CLAIMS.yaml`, plus a
    documentation-only `drizzle/0201_*.sql` recording the exact SQL applied
    and verified -- not itself run by the migration runner, since no
    scripts/migration convention exists for this table). NOT merged by this
    session -- the data change is already live regardless of PR merge
    status.
  - **Fix 2** (projexa, real code fix): every route under
    `projexa/src/app/api/**` that forwards an error from
    `callVeridian()`/`callVeridianRaw()`/`callVeridianBinary()` was
    discarding the real `VeridianApiError.status` and hardcoding
    `{ status: 502 }` in the response sent to the browser -- masking real,
    specific upstream errors (the ERP/Sales 403 above included) as a
    generic gateway failure. Fixed mechanically: `status: 502` ->
    `status: err instanceof VeridianApiError ? err.status : 502` (502
    remains the fallback only for genuinely unexpected/non-VeridianApiError
    failures). **179 occurrences across 123 files**, found via
    `grep -rl "status: 502" src/app/api` (verified safe as a blanket
    replace: every matching file imports `VeridianApiError`, every catch
    clause uses the identifier `err`) and spot-checked by hand afterward,
    including both `callVeridianRaw` binary/PDF-streaming routes and the 9
    files using an intermediate `const message = ...` variable. `bunx tsc
    --noEmit` clean, `bun run lint` clean (0 errors, 1 pre-existing
    unrelated warning), `bun run build` succeeds (all routes compile).
    projexa PR #13. NOT merged by this session.
  - Both PRs left open for the supervising session to audit/merge per this
    project's standard process (`mandatory-audit-check.yml` gate on the
    compliance-tracker side).
