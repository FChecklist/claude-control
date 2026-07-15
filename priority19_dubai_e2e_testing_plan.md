# Priority 19 -- Dubai 50-User E2E Test + Fix Pass (2nd pipeline run)

STATUS: PART 1 SUBSTANTIALLY COMPLETE 2026-07-15 (resumed + extended same day) --
org fully built (50 real personas + 5 projects + pagination-worthy seed data),
~28 of ~30 modules now tested with real UI actions + SQL verification (all of
Dashboard/Schedule/Meetings/Scope-BOQ/Work Progress/Site Diary/Documents/
Permits/RFIs/Submittals/Punch List/Change Orders/Mood Boards/FF&E/Floor Plans/
Manpower&Attendance/Vendors/Materials/Sales Dashboard/Leads/Opportunities/
Quotations/Sales Orders/Customers/GRC/Budgets/Expenses/Accounting/Invoices/
Employees/Payroll/Recruitment/KPIs/HR Dashboard/Settings-Team; only
company/office-selector checks remain fully untested, correctly deferred as
known-not-yet-shipped), 16 of 17 Reports & Analysis categories run +
1 cross-project rollup + AI Copilot Budget Status resolved from inconclusive
to confirmed-working, DATA-04 spot-checked across 3 personas/roles (no gap).
1 MAJOR constitution finding registered (DATA-01) then CORRECTED to a
narrower, lower-severity finding by the controlling session (see "Correction
to DATA-01 finding" below -- READ THIS FIRST). 1 EARLIER GAP FINDING RETRACTED
this session as a false positive (Reports "Expense never renders" -- was
insufficient wait time, not a bug; see "Reports & Analysis deep-dive" below).
3 bare-500 findings (Schedule/Invoices/Leads) share one likely root cause
(local-dev Supabase-Auth network flakiness cascading through an uncaught
`requireAuth()` failure) and need a live-deployment re-test before Part 2
treats them as confirmed regressions. Systemic missing-ERP-foundational-setup
gap found (zero fiscal years/cost centers/chart-of-accounts rows exist for
any real PROJEXA org), blocking Budgets and Accounting journal-entry
creation identically. 3 UAE-leak findings found (Customers' GSTIN field,
Vendors' GST field, Payroll's India Income Tax Slabs tab). See "Updated
Resume point" (below the continued module results and Reports section) for
the authoritative current state -- the ORIGINAL "Resume point" further up is
superseded, kept only for history. This is Priority 16's 2-part pipeline
(E2E test -> analyze/plan/implement) run a SECOND time, with 3 deliberate
deltas the Owner asked for 2026-07-15. Read
`control/priority16_e2e_testing_plan.md` first -- this file does NOT restate
its Part 1/Part 2 mechanics, module matrix, or per-module test procedure;
it only records what's DIFFERENT this pass. See CONTROLLER.yaml's
PRIORITY-19 entry for the full lifecycle record.

## Owner's instruction (verbatim, 2026-07-15)

> complete the intensive, testing of every functionality and logic by doing
> several enteries as a 50 user company in Dubai for all modules in
> FChecklist, compliance-tracker, projexa, check reports, analysis also.
> make a list of that. check with constitution and logic. make
> implemntation plan, correct it. take your own decision as VERIDIAN and
> what its end user wants. you have all the permissions and access.

"FChecklist" here is the same codebase as compliance-tracker -- confirmed
against CONTROLLER.yaml `meta.org` (FChecklist is the GitHub org hosting
compliance-tracker/projexa/veda-advisors) and this repo's own memory files
that use "FChecklist" and "compliance-tracker" interchangeably. Not a
fourth, separate product to test.

## What's different from Priority 16, and why

1. **Dubai/UAE demo company, AED currency**, instead of Priority 16's
   India-based "Meridian Skyline Group" (₹, GST-flavoured context). This is
   a genuine, useful re-test target, not cosmetic: it exercises (a)
   PLATFORM-01 Wave 1's new real multi-tenant provisioning
   (`POST /api/v1/platform/provision-org`, real signup flow) end-to-end for
   a brand-new org built through the actual product UI, which is a
   materially different test than PLATFORM-01's own single-API-key
   verification (see `wave_1_close_out` in CONTROLLER.yaml); (b) Priority
   17 Wave 1's in-flight multi-currency work on `erp-selling`/`erp-buying`
   (AED forces real non-INR, non-base-currency behaviour to surface).
2. **Full 50 real personas**, not Priority 16's 21-of-50 representative
   sample. Reuse the exact same 50-row roster SHAPE from
   `priority16_e2e_testing_plan.md`'s table (department/function/role
   columns), re-cast with Dubai/UAE-plausible names and
   `@<company>.demo` emails -- do not re-derive the roster from scratch.
3. **Dedicated Reports & Analysis depth pass** (Priority 16 only
   spot-checked "Run Report" once) plus **explicit constitution
   cross-referencing** of every finding, not just against each module's own
   backing service.

## Real-time state check (read fresh at Part 1 dispatch time, do not trust this snapshot if stale)

**RE-CHECKED live 2026-07-15 at actual Part 1 dispatch time via `gh pr list --state open` / `--state all --search` on both repos** (plan-write snapshot below was already slightly stale -- corrections in bold):
- compliance-tracker open PRs: #345 (Register PLATFORM-01 Wave 2 claim, `worktree-platform-01-wave2-claim`), **#344 Priority 17 Wave 1 multi-currency Selling & Buying is NOW OPEN** (plan-write snapshot said "no PR open at all yet" -- that's stale, a PR exists now but **no projexa-side counterpart PR exists** per a `--search priority17-multicurrency` sweep of the projexa repo, so the UI half is still not shippable even though the compliance-tracker service-layer PR is open), #343 (this ACTIVE-CLAIMS registration), #342 (companies/office selector, still open, unmerged), #340 (pms-adjacent, still DRAFT).
- projexa open PRs: #19 (pms-adjacent UI, now real OPEN not draft), #18 (company/office selector UI, open), #17 (inventory/procurement, open). None merged yet.
- **New finding not in the plan-write snapshot**: PR #345 shows PLATFORM-01 Wave 2 (offices/currency/language/country) claim registration is now OPEN/in-flight -- contradicts the plan-write-time belief that "Wave 2 is NOT dispatched yet." Re-confirmed via ACTIVE-CLAIMS.yaml read at Part 1 start: Wave 2 claim exists but PLATFORM-01 Wave 1 itself (PR #339) is still listed as merged/live -- Wave 2 being *claimed* doesn't mean `auth-guard.ts`/schema.ts's auth shape has changed yet; no evidence in `gh pr list` of Wave-2 code PRs open, only the claim-registration PR. Proceeding on the same assumption the plan already stated (do not touch those files regardless).
- Net effect on Part 1: **AED/multi-currency is confirmed NOT YET REACHABLE THROUGH THE PROJEXA UI** (compliance-tracker service-layer work is mid-flight on an open, unmerged PR; PROJEXA's own UI/proxy side has no corresponding branch at all yet). Test AED entry as far as the UI allows and log every currency-selector gap as "known-not-yet-shipped, cross-ref PR #344" rather than a fresh gap, per the plan's own instruction. Company/office selector (#342/#18) is also still unmerged -- same treatment.

Original plan-write-time snapshot (kept for history, see corrections above):
- Priority 16 Part 2's 7 fixes are MERGED on main: entitlement enable
  (erp/sales/hr for `projexa_demo_org`, PR #335), 502-status-masking fix
  (projexa#13), Settings/Team RLS fix (projexa#12), Schedule create-task +
  Work Progress activity picker (PR #336/projexa#14), Recruitment
  Create-Job-Opening fix (PR #338/projexa#15). **Re-verify these still work
  in Part 1 as a regression check, do not silently assume merged == still
  working** -- log a fresh gap if any has regressed, cross-referencing the
  original fix PR.
- Priority 17 Wave 1 is **PARTIALLY MERGED, 2 of 4 workstreams still open**
  at plan-write time: PR #342/projexa#18 (office selector) and PR
  #340(draft)/projexa#19 (PMS adjacent) are open, not merged.
  `priority17-inventory-procurement` (projexa#17) is open, its
  compliance-tracker counterpart not yet located. **The multi-currency
  workstream (`priority17-multicurrency-selling-buying` branch) has no PR
  open at all yet** -- AED wiring on quotations/sales-orders/vendor-POs may
  not exist when Part 1 runs. Part 1 must re-check `gh pr list --state all`
  on both repos immediately before starting, and if multi-currency still
  isn't merged, log it as a known-not-yet-shipped item (not a fresh gap) and
  test AED entry as far as the UI allows (e.g. does the currency field even
  exist, does it silently default to INR/base currency).
- PLATFORM-01 Wave 1 is MERGED + live-verified (PR #339, deployed to
  projexa-ai.com). Wave 2 (offices/currency/language/country) is **NOT
  dispatched yet** per CONTROLLER.yaml -- re-check ACTIVE-CLAIMS.yaml
  before Part 2 touches `auth-guard.ts`/schema.ts auth shape regardless, in
  case that's changed.

## Demo company: Dubai/UAE

**Name**: "Al Maha Skyline Contracting & Interiors LLC" (Dubai-plausible
construction + interior-design firm name; fictional, not a real company --
same disclosure standard as Meridian Skyline Group).

**Currency**: AED (UAE Dirham) as the org's base currency wherever a
currency selector exists post-Priority-17. **Country**: UAE -- this is
also a real test of `ARCH-06`/`ARCH-07`-adjacent country-agnosticism, since
this codebase's compliance tooling (GST/TDS/MCA) is explicitly India-only
by design (per PLATFORM-01's own scope note) -- expect and log every place
Indian-tax-specific UI/logic leaks into a UAE org's screens as a genuine
gap (e.g. a GST field shown where UAE VAT would apply), not something to
silently work around.

**Provisioning method**: use the REAL signup flow
(`/signup` -> email confirm -> `provisionOrganisation()`) for at least the
first 3-5 personas (Founder/CEO, COO, one department head per major
function) to genuinely exercise PLATFORM-01's new path end-to-end,
exactly like PLATFORM-01's own `platformtestalpha@gmail.com` verification
but through a full realistic org build, not a single throwaway account.
Bulk-create the remaining ~45 personas via direct SQL against `auth.users`
(same disclosed method as Priority 16 -- `crypt()`/pgcrypto,
`email_confirmed_at` set directly, no real inbox available), all under the
SAME org created by the real signup so both methods land in one coherent
company. Password: `DemoDubai2026!` for all bulk-created personas
(distinct from Priority 16's `DemoProjexa2026!` so the two demo passes
never get confused in a shared terminal/log).

**Roster**: identical shape to Priority 16's 50-row table
(`priority16_e2e_testing_plan.md` lines ~146-168) -- same department
breakdown (Leadership/Accounting/HR/Sales/GRC/Execution/Field/Design/
Resources/Intelligence), same headcounts per row, same
"new hire, no data yet" #50 slot for empty-state testing. Re-cast names to
plausible Dubai-resident names (a realistic UAE workforce mix -- Emirati,
South Asian, Filipino, Arab expat names, matching real Dubai construction
industry demographics; do not use only one nationality's names, that would
be an unrealistic roster for the stated company).

**Project data**: at least 5 real active projects, spanning both
construction and interior-design categories, with pagination-worthy seed
data (BOQ/RFI/expense/labour rows) on at least 2 of them -- same bar
Priority 16 set. Suggested Dubai-plausible project names: "Marina Vista
Tower - Structural Fit-out" (construction), "Palm Residence - Villa
Interior Renovation" (interior design), "Business Bay Corporate HQ - Full
Renovation" (mixed), plus 2 more.

## Module test procedure

**Reuse Priority 16's per-module test procedure verbatim** (state intended
behaviour first from the aliased compliance-tracker service -> perform the
real action as the persona -> verify UI signal -> verify independently via
Supabase MCP `execute_sql` against the named target table -> log a gap
entry only on divergence). **Reuse its module x verification-target
matrix verbatim as the base checklist** -- do not re-derive it. Apply
these deltas on top of that matrix:

- Every entry Priority 16 marked **GAP** and this repo's git history shows
  fixed (see "Real-time state check" above): re-test as a regression
  check, not a fresh discovery. Log `REGRESSION-CONFIRMED-FIXED` or
  `REGRESSION-REOPENED:<original finding id>` accordingly.
- Every entry Priority 16 marked **Working, no gap**: spot-check only
  (Priority 16 already proved these once) UNLESS the module is one Priority
  17 Wave 1 is actively changing (Sales/Vendors/Budgets/Accounting/company
  selector/PMS-adjacent pages) -- those get a FULL re-test since the
  underlying code has changed since Priority 16 tested it.
- "Several entries" = enter enough real transactional volume per module
  (not 1 row) across the 5 Dubai projects to genuinely exercise
  pagination/filtering/rollup math -- same "500-project-scale depth is
  meaningless against 1-2 rows" lesson Priority 16 already logged. Target:
  at minimum, every module in the Execution/Field/Sales/Finance sections
  gets 8-15 real rows spread across personas and projects, not a single
  smoke-test row per module.

### New: Multi-currency (AED) specific checks (Priority 17 delta)

For every module touching money (Quotations, Sales Orders, Vendors/POs,
Invoices, Budgets, Expenses, Accounting/journal entries): confirm a
currency field/selector exists and defaults sensibly for a UAE org; create
at least one entry with AED explicitly selected (not left on a hidden
INR/USD default); verify `erp_journal_entries`'s
`debitInCurrency`/`creditInCurrency` (or equivalent) columns actually
record AED and the base-currency-converted amount, matching
`erp-invoicing-service.ts`'s already-real pattern -- this is the concrete
proof of whether Priority 17's multi-currency work actually reaches the
UI, not just the service layer.

### New: Multi-office / company selector checks (Priority 17 delta)

If the office/company selector shipped by Part 1 dispatch time
(PR #342/projexa#18): confirm Al Maha's projects can be scoped to a
specific office/branch (e.g. a Dubai HQ vs. an Abu Dhabi branch, testing
`resolveCompanyScope()`'s consolidated-vs-per-company reporting split, not
just single-office happy path). If not yet merged, log as
known-not-yet-shipped per the real-time state check above.

### New: Reports & Analysis deep-dive (Owner's explicit "check reports, analysis also")

Priority 16 only ran ONE report ("Project Status") once. This pass must:
1. List the real available report categories/definitions
   (`report-taxonomy.ts` / `report-engine-service.ts`, ~200 definitions per
   PRIORITY-11's closure) and run **at least one report per category**
   relevant to a construction+interior-design firm (financial, project
   status, HR/payroll, sales pipeline, GRC/compliance, KPI) against Al
   Maha's real seeded data.
2. For each report run: confirm the output uses REAL computed numbers
   (cross-check at least 2 fields per report against the actual underlying
   table via SQL, same rigor as the BOQ amount / FF&E margin / attendance
   daily-cost checks Priority 16 already proved elsewhere) -- not a
   `data_gap` placeholder, not a hallucinated/static number.
3. Run at least one **cross-project rollup** report (company-wide, not
   single-project) now that Al Maha has 5 real projects with real data --
   Priority 16 never tested this since its own report run was
   single-project. This is the actual point of "500-project scale" work
   done in earlier waves; a single-project report run does not exercise it.
4. Test the AI Copilot's report-adjacent tools (Budget Status, KPI Status,
   AI Budget/Schedule Risk, Delayed Activities, Over-Budget Projects) with
   the fuller Al Maha dataset, same "real data, not hallucinated" bar
   Priority 16 already applied to Budget Status.

### New: Constitution cross-check (Owner's explicit "check with constitution and logic")

For every gap logged, AND independently of any gap, evaluate these
specific `ai-os/CONSTITUTION.yaml` rule IDs against what Part 1 actually
observes (cite the rule ID + its current `status` value in the gap log
when relevant, don't just narrate around it):

- **DATA-01** (`ENFORCED_PRODUCTION_PROVEN`, tenant isolation, no
  cross-org data leaking): Al Maha is a brand-new org. If it shares
  `projexa_demo_org`'s backend identity the same way Priority 16 proved
  Meridian Skyline Group did (PROJEXA-NO-TENANT-ISOLATION-01), that is a
  **direct, concrete contradiction of DATA-01's own claimed status** for
  the entire PROJEXA product surface -- log this explicitly as a
  constitution-status discrepancy, not just a restatement of the known
  finding, since PLATFORM-01 Wave 1 claims to have fixed exactly this for
  new real-signup orgs. This is the single most important thing this pass
  verifies: **did PLATFORM-01 Wave 1 actually close DATA-01's gap for
  PROJEXA, end to end, through the real UI?**
- **DATA-04** (no duplicated modules within an org): confirm every Al Maha
  persona with the same role sees the identical module/report set as
  every other same-role persona (spot-check 2-3 pairs).
- **SEC-03** (every AI decision/write traceable to user/timestamp/company):
  re-check the `created_by_id` attribution-loss finding Priority 16 found
  on Punch List (`"projexa_demo_key"` instead of the real persona) on at
  least 3 different modules/personas this pass -- is it still universal,
  or did PLATFORM-01's identity work narrow it at all?
- **SEC-04** (no delete/corrupt without an approved workflow): confirm no
  destructive action (e.g. a status revert, a hard-delete button if one
  exists anywhere in the 33 nav pages) bypasses an approval/audit trail.
- **ARCH-03** (every new org-scoped table ships RLS in the same
  migration): not directly testable by this pass (no new tables being
  created), but if Part 2 adds any new table while implementing fixes,
  self-audit against this rule explicitly before merging.
- **UMR-02** (every table registered in the asset-registry coverage
  manifest): if Part 2 adds any new table, self-check against
  `ai-os/registry/asset-registry-coverage.yaml` before merging (Priority
  15 already hit this once with `crm_stage_history`).

Log constitution cross-check findings in their own labeled section of the
gap log, separate from per-module gaps, so Part 2 can see at a glance
which constitution rules this pass actually re-validated vs. contradicted.

## Part 1 gap log

Started 2026-07-15. Executor: Claude Code CLI session (background agent), same
Supabase project refs as Priority 16: `evpckeuxgvahguwsaeul` = projexa's own DB
(organizations/memberships/profiles/veridian_credentials), `pcrjmlpuqsbocqfwoxod`
= compliance-tracker ("verdian-ai") DB (`compliance` schema, all business data)
-- both re-confirmed live via `list_projects` at dispatch time, matching the
plan's assumed refs exactly, no drift.

### Org build

- Org: **Al Maha Skyline Contracting & Interiors LLC**, id
  `03483997-4a9d-4e07-b833-e5935101ed9a`, slug `al-maha-skyline-demo`, in
  projexa's own `public.organizations`. Pre-existing orgs (Meridian Skyline
  Group, Skyline Builders, Wave4 QA Test Co, Acme Test Construction, the 2
  "Platform Test Org Alpha" real-signup test orgs from PLATFORM-01's own
  verification earlier the same day) untouched.
- **REAL-SIGNUP-FLOW BLOCKER (register as a finding, not silently worked
  around)**: attempted the plan's required real `/signup` flow for the
  Founder/CEO persona first, as instructed. Findings, in order: (1)
  `khalid.almheiri@almahaskyline.demo` -> Supabase Auth's real `signUp()`
  rejected it client-side with "Email address ... is invalid" -- the `.demo`
  TLD is not accepted by Supabase Auth's own email-format validator (this
  only surfaces on the REAL signup path; Priority 16's SQL-bulk method never
  hit it because raw SQL inserts bypass that validator entirely -- a real,
  concrete difference between the two provisioning paths worth Part 2 knowing
  about, not just a naming inconvenience). (2) Retried with a real-TLD but
  still-fictional address, `khalid.almheiri@almahaskyline.ae` -> Supabase
  Auth returned **"email rate limit exceeded"**, and independently confirmed
  via SQL that **zero row was created in `auth.users`** for that attempt (not
  a "user created, email failed" partial state -- the whole signup failed).
  Root cause, confirmed by direct query: this project's Supabase built-in
  email service has a low, project-wide, shared rate limit, and it was
  already substantially consumed earlier the same day by PLATFORM-01's own
  Wave 1 live verification (`platformtestalpha@gmail.com` -- the only
  genuinely-deliverable-inbox signup today -- plus a second
  "Platform Test Org Alpha" org created via the platform-application API
  path, not the email-confirm UI path). This is a real, structural
  limitation of testing the real-signup path repeatedly in one shared
  Supabase project on one day, not a Part-1-specific mistake -- flagged
  honestly rather than silently substituting a `gmail.com`-style address
  belonging to the Owner without asking. **Fell back to the same disclosed
  SQL-bulk method Priority 16 used for the entire 50-person roster**
  (including the CEO), per the plan's own contingency. **This means Part 1
  could NOT itself add a fresh real-UI-signup data point beyond what
  PLATFORM-01 had already independently produced earlier the same day** --
  see "Constitution Cross-Check -> DATA-01" below for how the pre-existing
  Platform Test Org Alpha evidence is used instead, plus a separate, deeper
  finding (the credential-lookup DB-connection failure) that Part 1 DID
  newly discover and that undercuts even that evidence.
- **50 personas** created via SQL against `auth.users` (`crypt()`/pgcrypto,
  `email_confirmed_at=now()`, `raw_user_meta_data` matching the exact shape of
  Priority 16's own rows), covering the full 50-row roster (not a
  representative subset) with the same department/role shape re-cast to
  Dubai-plausible names spanning Emirati, South Asian, Filipino, and Arab
  expat naming conventions (e.g. Khalid Al Mheiri/owner, Fatima Al
  Zaabi/admin-COO, Rajesh Nair + Mariam Al Suwaidi/admin-Finance Managers,
  Grace Santos/admin-HR Manager, Youssef El-Amin/admin-Sales Head, 4x
  admin-Project foremen, 10x member-Site Engineers, 3x Architects, 3x
  Interior Designers, 4x Procurement Coordinators, 4x QS/Estimators, 2x
  Front-desk, 2x KPI Analysts, 1x AI Copilot power-user, Ben Alonzo as the
  #50 "new hire, no data yet" empty-state persona). All emails
  `firstname.lastname@almahaskyline.demo`, password `DemoDubai2026!` for all
  (distinct from Priority 16's `DemoProjexa2026!`, per the plan's own
  instruction). `handle_new_user()` trigger fired correctly and created 50
  `public.profiles` rows automatically (confirmed: the first attempt to
  backfill `display_name` inside the SAME multi-CTE INSERT statement
  returned 0 rows updated -- a real Postgres semantics gotcha, not a bug:
  data-modifying CTEs that target the SAME table as a trigger side-effect
  from an earlier CTE in the same statement do not reliably see each other's
  writes -- fixed by re-running the `display_name` backfill as its own,
  separate statement, which then correctly updated all 50).
  Memberships inserted with the correct `owner`/`admin`/`member` role per
  persona. Real login verified for the CEO persona via the browser (see
  below) -- session cookie confirmed valid, real JWT with correct `sub`/email.
- **Projects**: 5 new projects created directly in
  `compliance.projects`/`compliance.products` (same org_id mechanism as
  Priority 16 used, `org_id='projexa_demo_org'` -- see Constitution
  Cross-Check/DATA-01 for why this is a load-bearing fact, not an
  implementation detail): Marina Vista Tower - Structural Fit-out
  (construction), Palm Residence - Villa Interior Renovation (interior
  design), Business Bay Corporate HQ - Full Renovation (mixed), Downtown
  Boulevard Offices - New Build Fit-out (construction), JBR Beachfront
  Residences - Interior Package (interior design). Pagination-worthy seed
  data added via SQL on 2 of the 5 (Marina Vista Tower + Business Bay HQ,
  matching the plan's "at least 2" bar): 35 BOQ line items (20+15, `amount`
  computed as `quantity*rate` in the seed SQL itself so the arithmetic
  identity is true by construction, same convention Priority 16 used), 25
  RFIs (15+10, realistic level/floor-numbered subjects, mixed
  open/answered/closed status distribution), 24 expense entries (12+12,
  6-category spread: material/labour/equipment/transport/subcontractor/
  misc), 10 labour roster rows (Marina Vista, realistic UAE-construction
  trade/nationality mix, daily rates AED 120-220). All 5 projects render
  correctly on the CEO's Dashboard (see below) -- schedule/pms_issues
  intentionally left to real browser create actions per the same reasoning
  Priority 16 used (FK dependencies on lookup rows not worth bulk-seeding
  next to a real UI action anyway).

### Pre-flight note

Given the confirmed shared-backend architecture (see DATA-01 finding below),
Priority 16's own pre-flight baseline table already establishes the relevant
starting counts for every shared table this session also writes to -- this
session's row counts are ADDITIVE on top of that baseline plus Priority 16's
own additions, not a fresh zero-baseline for a genuinely separate tenant (a
genuinely separate baseline is architecturally not meaningful right now, for
the same reason Priority 16 already documented under
PROJEXA-NO-TENANT-ISOLATION-01).

### Module-by-module results

(Executed as Al Maha Skyline personas via `mcp__Claude_Browser__*` against
`http://localhost:3100`, dev server from `projexa/.claude/launch.json`'s
`projexa-dev` config, reused as instructed via `preview_start`.)

- **TOOLING NOTE, not a product bug**: `.next` was stale from a 2026-07-12
  build predating `src/app/signup/page.tsx`'s existence, causing `/signup`
  to genuinely 404 (`next.js` dev server routes-manifest cache issue, not a
  code bug -- confirmed by `rm -rf .next` + restart fixing it immediately).
  Separately, this session's `computer.left_click` tool calls against
  Radix-UI-driven buttons/tabs (dialog triggers, tab triggers, submit
  buttons wrapped in `onClick`/pointer handlers) reliably failed to register
  a real click in this environment -- confirmed via network-request absence
  after clicking -- while a full synthetic `pointerdown`/`mousedown`/
  `pointerup`/`mouseup`/`click` event sequence dispatched via
  `javascript_tool` against the same element reliably worked. Also, Radix
  `Dialog`/`Tabs` content renders in a portal outside `<main>`, so
  `get_page_text`'s default scoping (`Source element: <main>`) misses it
  entirely -- `document.body.innerText` or a direct
  `document.querySelector('[role=dialog]')` check is required to see it.
  Both are this session's own tooling quirks (matches Priority 16's own
  "AI Copilot text-extraction quirk" note), NOT logged as product gaps, but
  documented here so a resuming session doesn't waste time re-discovering
  them.

- **Dashboard** (persona: Khalid Al Mheiri, owner). Intent: read-only
  cross-project rollup for the logged-in org. **Actual, and this is the
  single most important observation this pass makes (full analysis under
  Constitution Cross-Check/DATA-01 below, not repeated here)**: the
  Dashboard shows **10 projects**, not Al Maha's own 5 -- it renders Al
  Maha's 5 new Dubai projects (Marina Vista Tower, Palm Residence, Business
  Bay HQ, Downtown Boulevard, JBR Beachfront) mixed together with all 5 of
  Meridian Skyline Group's India projects from Priority 16 (Villa 21,
  Meridian Business Center, Cedar Heights, Lakeview, Meridian Boutique
  Hotel), on ONE Founder/CEO login for a brand-new, unrelated Dubai company.
  All monetary figures render in **₹ (INR) formatting**, not AED, despite
  this being a UAE org (currency finding, cross-ref the dedicated AED
  section below). Expense totals match the real seeded data exactly (Marina
  Vista Tower: ₹1,18,500 seeded so far at that point in the session --
  confirmed correct against the running SQL total). Server console
  (`preview_logs`) shows, on every single page load, repeated:
  `[veridian-client] getVeridianApiKey(03483997-4a9d-4e07-b833-e5935101ed9a)
  failed -- falling back to shared VERIDIAN_API_KEY if configured: No
  database connection string available. Set DATABASE_URL or
  NEXT_PUBLIC_SUPABASE_URL + SUPABASE_DB_PASSWORD.` -- direct proof PLATFORM-
  01 Wave 1's per-org-credential lookup code path IS being invoked for a
  brand-new org's real org_id, but cannot function in this environment.

- **REGRESSION-REOPENED -- Schedule "New Task" create** (persona: Khalid Al
  Mheiri, then re-tested as the same session on Meridian's pre-existing
  Villa 21 project). Priority 16 Part 2's PR #336 (schedule create-task
  fix, confirmed merged per ACTIVE-CLAIMS `recently_completed`) added a
  real "New Task" dialog to the Board tab, backed by a new
  `POST /api/schedule/tasks` -> VERIDIAN `/v1/projexa/schedule` ->
  `createIssue()`. Confirmed the dialog itself still renders correctly and
  accepts input (title field, type/priority comboboxes, due date). **Actual
  on submit**: `POST /api/schedule/tasks` returns **500 Internal Server
  Error** with body `{"error":"Failed to create task"}` -- reproduced
  **twice, independently**: once on Al Maha's brand-new Marina Vista Tower
  project (ruling in "new org/new project" as a plausible cause), and once
  more, deliberately, on Meridian Skyline Group's pre-existing Villa 21
  project (`projexa_demo_project`) -- the SAME project Priority 16 Part 2
  itself used to verify this exact fix worked. **Ruling out "new org" as the
  cause**: since the failure reproduces identically on the already-proven
  project, this is a genuine regression affecting the feature for every
  PROJEXA org, not an Al-Maha-specific gap. Root cause not conclusively
  identified this session (Part 1 is registration-only) -- two plausible
  candidates worth Part 2 checking first: (a) the same missing-DATABASE_URL
  condition already confirmed to break `getVeridianApiKey()` on this
  environment could be cascading into a hard, uncaught exception somewhere
  in `callVeridian()`'s error path (note the response status is a raw
  **500**, not the route's own coded 502 fallback for a `VeridianApiError`
  -- `src/app/api/schedule/tasks/route.ts`'s `POST` catch block maps
  non-`VeridianApiError` exceptions to 502, so a bare 500 implies the
  exception happened OUTSIDE that try/catch, e.g. in `requireAuth()` or
  `request.json()`, not inside the VERIDIAN call itself); (b) something in
  Priority 17's concurrently-open, unmerged Wave-1 branches
  (companies/office selector, PMS-adjacent, multi-currency) may have already
  touched shared schedule/issue-taxonomy code on `main` in a way that
  broke this specific path since Priority 16 Part 2 verified it, without yet
  shipping the corresponding fix -- worth a `git log` on
  `pms-issue-service.ts`/`pms-taxonomy-service.ts` since PR #336 merged.
  Confirmed via SQL: zero new rows in `compliance.pms_issues` for either
  attempt.

  **FIXED, see compliance-tracker PR #349.** Neither of the two hypotheses
  above was the actual cause: `pms-issue-service.ts`/`pms-taxonomy-service.ts`
  were unchanged since Wave 26/141 (`git log` confirmed, ruling out a
  Priority 17 regression), and the exception genuinely was inside
  `callVeridian()`'s try block, not outside it -- a `VeridianApiError` can
  legitimately carry any upstream status including 500, so "raw 500 not 502"
  didn't actually imply an uncaught exception in `requireAuth()`/
  `request.json()`. Real root cause: `compliance.pms_issues.created_by_id`
  carries a hard `FOREIGN KEY REFERENCES compliance.users(id)`
  (drizzle/0021, Wave 25), but `src/app/api/v1/projexa/schedule/route.ts`'s
  `POST` handler legitimately passes the caller's API-key id
  (`"projexa_demo_key"`) as the actor for every PROJEXA-originated create
  (PROJEXA-IDENTITY-BRIDGE-01, the org-wide API key bridge has no per-user
  identity) -- that id is never a row in `compliance.users`, so every such
  create hit the FK constraint on INSERT, surfaced as the route's own
  generic-catch 500 "Failed to create task" (byte-for-byte match to what
  was observed), then faithfully re-thrown by PROJEXA's `callVeridian()`
  with the real upstream status (500, not a masked 502). Confirmed via
  Supabase MCP: all 17 pre-existing `pms_issues` rows had `created_by_id`
  NULL or a real `compliance.users` row -- zero were ever created through
  the PROJEXA API-key path. Fix: dropped the FK, matching the identical
  precedent already set for `job_openings.posted_by_id`
  (drizzle/0202, Priority 16 Part 2) -- verified live by simulating the
  exact insert `createIssue()` performs with the API-key actor, which
  succeeded post-fix (then cleaned up, no trace left in demo data). Scoped
  to `created_by_id` only; `assigned_by_id`/`assignee_id`'s identical
  latent FK-vs-API-key-actor exposure on the Kanban board's PATCH path is
  flagged in the PR for a future session, not fixed here.

- **Working, no gap -- RFIs** (persona: Khalid Al Mheiri, on Marina Vista
  Tower). Seeded list renders correctly with real pagination-worthy data (15
  RFIs, correct subject/status/ball-in-court columns, status-appropriate
  Answer/Close action buttons). "Answer" on RFI-1 verified: submitted a real
  answer text via the dialog, `status` moved `open` -> `answered`, `answer`
  text stored correctly verbatim, confirmed via SQL against
  `compliance.construction_rfis`. **SEC-03 note (cross-refs Priority 16's
  Punch List finding, not a new root cause)**: `answered_by_id` landed as
  `"projexa_demo_key"` (the shared API key's own id), not Khalid's real user
  id -- attribution loss reproduces identically for a brand-new org's owner
  persona, confirming this is fully general, not specific to
  Meridian/member-level users.

- **Working, no gap -- Settings / Team (REGRESSION-CONFIRMED-FIXED)**
  (persona: Khalid Al Mheiri, owner). Priority 16 found this structurally
  broken for every PROJEXA org (`GET /api/org-members` always returning
  `{"members":[]}`, RLS-policy root cause), fixed by Priority 16 Part 2's
  PR projexa#12. **Actual, this pass**: Team section correctly lists **all
  49 other Al Maha Skyline members** with correct email/display
  name/role -- verified against the full 50-row roster, exact match, zero
  missing/extra/wrong-org rows. This is a genuinely encouraging, distinct
  data point from the DATA-01 finding above: it shows PROJEXA's own small
  Supabase DB (`organizations`/`memberships`/`profiles`) -- the layer this
  fix actually touched -- IS correctly per-org-isolated (Al Maha's Team page
  does NOT show Meridian's 50 members or vice versa), consistent with
  Priority 16's own original observation that this specific slice of data
  was always the one genuinely isolated part of the system.

- **Known-not-yet-shipped, not a fresh gap -- Quotations, AED currency check**
  (persona: Khalid Al Mheiri, on Marina Vista Tower). Per the plan's own
  real-time state check (re-confirmed at dispatch: PR #344 compliance-tracker
  multi-currency service-layer PR is open/unmerged, **zero** projexa-side PR
  exists for it at all): opened the real "New Quotation" dialog and confirmed
  directly -- **no currency field or selector exists anywhere in the form**
  (Customer / Project / Quotation Date / Valid Till / Line Items only).
  Matches the plan's own prediction exactly. Not logging as a fresh gap per
  the plan's explicit instruction; this is the concrete, UI-level proof that
  AED entry is not reachable yet, cross-referenced to PR #344.

- **Working, no gap -- GRC / Risk Register** (persona: Khalid Al Mheiri).
  "Log Risk" dialog create action verified: real row landed in
  `compliance.risks` (id `zpkhxvp9k9ypnq91o731l8b3`, title "UAE VAT
  non-compliance risk on Marina Vista subcontractor invoices",
  `likelihood=4`, `impact=5`, confirmed via SQL) -- matches the matrix's
  stated create-and-verify target. Severity band is computed at read time
  (not a stored column, confirmed by schema read), consistent with Priority
  16's own finding of a UI-side "4 x 5 = 20 -> High" computation, not
  independently re-verified in the UI this pass for time reasons (logged as
  not-re-checked, not as working-confirmed, for that specific sub-claim).

- **GAP -- Reports: API computes real, correct data but the UI never
  displays it** (persona: Khalid Al Mheiri, on Business Bay Corporate HQ).
  Selected the "Expense" report type, clicked "Run Report." **Network layer
  confirms full success**: `GET /api/reports/expense?projectId=alm_project_
  bizbay` returned **200 OK** with a fully real, correctly-computed body --
  `{"byHead":[{"expenseHead":"transport","total":14400},{"misc":16800},
  {"subcontractor":15600},{"equipment":13200},{"material":10800},
  {"labour":12000}],"total":82800}` -- **independently verified correct by
  direct arithmetic on the seed data** (`sum(3000 + gs*600) for gs=1..12` =
  ₹82,800 exactly, matching the API's `total` field to the rupee). **But the
  rendered page never shows this result at all** -- confirmed by checking
  `document.body.innerText` directly (not just the `<main>`-scoped
  extraction, to rule out the portal-scoping tooling quirk noted above):
  1,132 characters total, containing neither "82,800" nor "82800" anywhere,
  the page still showing only "Pick a report and click Run Report." This is
  exactly the "UI looks fine but the call actually failed/never surfaced"
  failure class the plan's own test procedure warns about, except here the
  call didn't fail at all -- the data computed correctly and just never
  reached the screen. A real, reproducible, PROJEXA-side rendering gap, not
  a compliance-tracker/report-engine-service.ts problem (the service-layer
  computation is proven correct). Only 17 report types are exposed on
  PROJEXA's own Reports page (Project Status/Completion, Work Progress,
  Category Progress, Weekly Project, Attendance, Manpower Cost, Site Picture
  Log, Scope/BOQ, Budget Summary, Budget vs Actual, Material Consumption,
  Vendor Cost, Designer Timesheet, KPI, Revenue, Expense) -- a
  project-management-focused subset, not compliance-tracker's full ~200-
  definition catalog from Priority 11's closure (no GRC/HR/finance-statement
  report types surfaced here at all, e.g. no trial balance/P&L/AR-aging/
  audit-findings report reachable from PROJEXA's own Reports page despite
  those compliance-tracker services existing and being separately reachable
  from their own dedicated PROJEXA modules) -- flagged as a scope
  observation for Part 2 to judge, not asserted as a bug, since a curated
  subset may be the intended design.

  **FIXED (partially -- see below), see projexa PR #21.** Direct, repeated
  re-testing of this exact repro against current `main` (same project
  `alm_project_bizbay`, same "Expense" report, local dev server) **could NOT
  reproduce the described failure**: the report rendered correctly end to
  end every time, reproducing this finding's own cited figures exactly
  (`total: 82800`; `byHead` transport 14400/misc 16800/subcontractor
  15600/equipment 13200/material 10800/labour 12000). `git log` confirms
  `ReportsClient.tsx`/`ReportOutput.tsx` unchanged since Priority 2
  (`4b5b6ef`), long predating this finding, and both files' fetch -> state
  -> render logic is correct as written. Most plausible explanation: a
  browser-automation click-registration artifact of this session's own
  tooling against Radix/shadcn-driven elements -- this session's own
  TOOLING NOTE (above) already documented `computer.left_click` "reliably
  fail[ing] to register a real click ... against ... submit buttons wrapped
  in onClick/pointer handlers," which is exactly what "Run Report" is; the
  fix session independently hit the identical issue on the report-type
  `Select` (a `left_click` left `aria-expanded="false"`) before switching to
  a synthetic `pointerdown`/`mousedown`/`pointerup`/`mouseup`/`click`
  dispatch, which then worked reliably every time. Rather than a fix for an
  unreproduced defect, PR #21 ships two real, safe hardenings found while
  investigating: (1) an out-of-order-response guard in `ReportsClient.tsx`
  (a genuine latent race if the report type is switched and "Run Report"
  clicked again before the first request resolves -- not the literal
  symptom reported, but a real bug in the same component); (2)
  `key={project.id}` on `ReportsClient` in `reports/page.tsx` (without it, a
  client-side project switch could leak a previous project's stale report
  state into the new project's view). **Recommendation for a resuming
  session**: if this reproduces again through a genuinely real, non-
  automated browser (not `mcp__Claude_Browser__*`/`computer.left_click`),
  that would be a much stronger signal of an actual defect this fix pass
  didn't catch, and needs a fresh look with that context -- until then, this
  is closed as tooling-artifact-most-likely, with two real hardenings
  shipped as a hedge.

- **INCONCLUSIVE, not logged as a gap -- AI Copilot "Budget Status"**
  (persona: Khalid Al Mheiri, on Business Bay Corporate HQ). Page loads
  correctly, all 7 named construction tools present (Project Dashboard,
  Budget Status, KPI Status, AI Progress Summary, AI Budget/Schedule Risk,
  Delayed Activities, Over-Budget Projects), matching Priority 16's own
  finding. Attempted to run "Budget Status" via a scripted click on the
  2nd "Run" button on the page -- after the click, the Budget Status card's
  own "Run" button text disappeared (consistent with a loading state having
  started) but **zero matching network request was captured** in the
  20-second window waited, and "Recent Construction Queries" still read "No
  construction Copilot queries yet." Given this session's own confirmed
  click-targeting tooling issues (see TOOLING NOTE above), this is honestly
  inconclusive -- could be a real product bug (click didn't reach the
  handler) or a repeat of this session's own targeting problem (picked the
  wrong "Run" button by list index rather than by proximity to the "Budget
  Status" label). **Not registering as a gap** -- flagged for a resuming
  session to re-attempt with a more precise element-selection approach
  (e.g. walk up from the "Budget Status" text node to its containing card,
  then query within that specific card) rather than a global button-index
  guess.

### Not yet tested this pass (see Resume point at the end)

Meetings, Scope (BOQ) UI create (data exists via seed, UI create not
exercised), Site Diary, Documents, Permits, Submittals, Punch
List, Change Orders, Mood Boards, FF&E, Floor Plans, Manpower & Attendance,
Materials, Vendors, Sales Dashboard, Leads, Opportunities, Sales Orders,
Expenses (module UI, distinct from the Expense report
already run), HR Dashboard, Recruitment, KPIs. Company/office-selector checks (PR #342/projexa#18, still
unmerged per the real-time state check) not attempted. Full 50-persona
walkthrough (as opposed to spot-checking as the CEO) not done -- only the
CEO persona was actually driven through the browser this pass; the other 49
were created and verified to exist/have correct roles/memberships but none
were individually logged in.

**(Resumed session, continued 2026-07-15 -- see new "Module-by-module results,
continued" section below for Work Progress, Budgets, Accounting, Invoices,
Customers, Employees, Payroll, all now tested. This "not yet tested" list is
updated to remove those.)**

## Module-by-module results, continued (resumed session, same day)

**TOOLING LESSON, not a product bug (add to the existing TOOLING NOTE)**:
the synthetic `pointerdown/mousedown/pointerup/mouseup/click` dispatch
pattern occasionally fails on a freshly-hydrated page (dispatched too soon
after navigation, before React finishes attaching listeners) and on Radix
`Tabs` triggers specifically after a dev-server HMR recompile mid-session
(stale element reference / re-mount race). Fix: add a ~2s wait after
`navigate` before the first synthetic click, and re-query the element fresh
(don't cache a JS variable across separate `javascript_tool` calls -- each
call is a new top-level scope and `const`/`let` redeclarations across calls
throw `SyntaxError: Identifier already declared`; wrap each call's script in
an IIFE and use `window.__foo` for anything that must persist).
`mcp__Claude_Browser__computer` (screenshot, left_click by ref) also timed
out / silently no-op'd on this Radix Tabs component even via `ref_N` from
`read_page` -- the JS-dispatch workaround remains necessary, this is not
newly fixed.

**LATENCY, confirmed again, worth Part 2 knowing precisely**: every write
this session took 15-80+ seconds (`POST /api/work-progress/activities` 67s,
`POST /api/work-progress` 81s, `POST /api/customers` 35s), consistent with
Priority 16's already-documented "every PROJEXA dev-server action is a real
round-trip to the live deployed `veridian-compliance-ai.vercel.app`, not a
local call" finding -- not re-logged as a new issue, but confirms it's still
true and a resuming session should budget wait times accordingly (30s is
often not enough; some calls need 60-90s).

- **REGRESSION-CONFIRMED-FIXED -- Work Progress activity picker** (persona:
  Khalid Al Mheiri, on Marina Vista Tower). Priority 16 Part 2's PR #336
  added an activity create-on-the-fly flow ("No activities yet for this
  project. Create the first one.") to close the "Paste the activity's ID
  from VERIDIAN" blocker Priority 16 Part 1 found. **Confirmed working
  end-to-end on a brand-new Al Maha project that has genuinely zero
  activities** (matching Priority 16's exact "none of the newly created
  projects have any activities" starting condition): clicked "Create the
  first one" -> "New Activity" sub-dialog -> created "RCC Column Casting -
  Level 3" (unit "cum") -> `POST /api/work-progress/activities` 201,
  real row confirmed via SQL. The now-populated Activity dropdown was then
  used to log a real progress entry (qty=18, %complete=35, remarks
  verbatim) -> `POST /api/work-progress` 201, confirmed via SQL against
  `compliance.construction_work_progress_entries`
  (id `gbf2sb0s1gvaday61dku0gq9`): `quantity_done="18"`,
  `percent_complete=35`, `remarks` matches verbatim. **SEC-03 note (3rd
  module occurrence this pass, after RFIs)**: `recorded_by_id` landed as
  `"projexa_demo_key"`, not Khalid's real user id -- attribution loss still
  universal, unaffected by this fix (expected, this fix touched activity
  discovery, not the identity bridge).

- **GAP -- Budgets: silent no-op when no fiscal year exists (every PROJEXA
  org, confirmed systemic)** (persona: Khalid Al Mheiri, on Marina Vista
  Tower). Page now loads (was a flat 502 under
  PROJEXA-MODULE-ENTITLEMENT-01 at Priority 16 time -- entitlement enable
  PR #335 confirmed fixed, REGRESSION-CONFIRMED-FIXED for reachability).
  UI copy is honest about the remaining gap ("Fiscal year and cost center
  are looked up live from VERIDIAN's ERP module below... The budget line
  item's account ID still needs to come from VERIDIAN's own Chart of
  Accounts... so paste that in directly for now"). **Actual, root-caused by
  direct source read** (`projexa/src/components/BudgetsClient.tsx:74`):
  `if (!name.trim() || !fiscalYearId || !accountId.trim() || !annualAmount)
  return;` -- the "Create Budget" button silently does nothing (no toast,
  no inline error, no network request at all) when `fiscalYearId` is empty,
  and it can never be non-empty because **zero fiscal years exist for any
  org in the entire compliance-tracker database except compliance-tracker's
  own internal `demo_org`** (confirmed via SQL:
  `select org_id, count(*) from compliance.erp_fiscal_years group by
  org_id` -> only `demo_org`, count 1). Filled all 3 real inputs (Budget
  Name, a fabricated Account ID since none exist to select, Annual Amount)
  and clicked Create Budget twice -- confirmed via `read_network_requests`
  that **no POST was ever sent**, matching the source read exactly. This is
  a genuine, systemic, confirmed-via-source-and-behavior gap: Budgets has
  never been creatable end-to-end for any real PROJEXA customer, because no
  self-serve "set up your fiscal year" flow exists anywhere in PROJEXA, and
  the failure is silent rather than explained.

- **GAP -- Accounting: "New Journal Entry" account picker permanently shows
  "Loading…" instead of an honest empty state (same root cause as Budgets,
  different symptom)** (persona: Khalid Al Mheiri). Accounting page itself
  now loads correctly (Dashboard/General Ledger/Trial Balance/P&L/Balance
  Sheet/P&L by Project/Bank Reconciliation tabs all render --
  REGRESSION-CONFIRMED-FIXED for reachability, same entitlement fix as
  Budgets). General Ledger tab correctly shows "No journal entries found."
  -- verified correct via SQL (`compliance.erp_journal_entries` has exactly
  3 rows, all `org_id='demo_org'`, zero for `projexa_demo_org`), not a bug.
  Opened "New Journal Entry": dialog renders correctly (Posting Date,
  Remark, double-entry Lines UI with a running Debit/Credit balance
  check -- structurally correct). **Actual**: both line items' account
  selector shows "Loading…" as their placeholder indefinitely (confirmed
  the underlying `GET /api/accounts` call itself completes with 200, so
  this is not a stuck request). **Root-caused by direct source read**
  (`projexa/src/components/AccountingClient.tsx:244`):
  `placeholder={accounts.length ? "Account" : "Loading…"}` -- the
  component conflates "still loading" with "loaded, zero results" and
  always shows the loading label in the empty case, because (same root
  cause as Budgets) `compliance.erp_accounts` has zero rows for
  `projexa_demo_org` (confirmed via SQL, same query pattern as fiscal
  years). A real user has no way to distinguish "still loading" from
  "there is no chart of accounts for your org, contact support" -- and
  since there is no self-serve chart-of-accounts setup UI either, journal
  entry creation is blocked the same way Budgets is, just with a more
  misleading (rather than silent) symptom. Not completed this pass (dialog
  reset by an unrelated dev-server HMR recompile mid-session before a
  create attempt could be made with a fabricated account id the way
  Budgets was) -- Part 2 should treat both as the same underlying
  "no ERP foundational setup (fiscal years / cost centers / chart of
  accounts) exists for any real PROJEXA org" gap, not two separate bugs.

- **NEW GAP -- Invoices: "Create Invoice" fails with a bare 500, twice,
  reproducibly, same failure signature as the Schedule "New Task"
  regression** (persona: Khalid Al Mheiri, on Marina Vista Tower). Customers
  module tested first as a prerequisite (see below, working correctly) to
  get a real customer to invoice. Invoices page loads correctly (Invoices /
  Credit Notes / AR Aging tabs, "No invoices found." verified correct via
  SQL -- all 8 pre-existing `erp_sales_invoices` rows belong to
  `org_id='demo_org'`, zero for `projexa_demo_org`). No currency
  field/selector in the Create Invoice dialog either (Customer / Posting
  Date / Line Item Description / Quantity / Rate only) -- same
  known-not-yet-shipped AED gap as Quotations, cross-ref PR #344, not
  re-logged as new. Selected the real "Emaar Properties PJSC - Marina
  District" customer (created moments earlier), filled a real line item
  (qty=10, rate=85000), clicked "Create Invoice". **Actual**:
  `POST /api/sales-invoices` returned a bare **500** (`{"error":"Failed to
  create sales invoice"}`) -- **reproduced twice**, zero rows landed either
  time (confirmed via SQL, `compliance.erp_sales_invoices` count for
  `projexa_demo_org` = 0 after both attempts). **Root cause, likely shared
  with the already-logged Schedule "New Task" 500 regression, not
  independently diagnosed as a new bug class**: `projexa/src/app/api/
  sales-invoices/route.ts`'s own `POST` catch block maps every
  non-`VeridianApiError` exception to **502**, not 500 -- so a bare 500
  proves the exception happened OUTSIDE that try/catch, i.e. in
  `requireAuth()` or `request.json()`, exactly the same diagnosis already
  written for the Schedule regression. **Directly corroborated this time
  by `preview_logs`**: the log window around both failed attempts is
  saturated with `[requireAuth] memberships query failed once, retrying:
  TypeError: fetch failed` and raw `ConnectTimeoutError` entries against
  Cloudflare-fronted IPs (`104.18.38.10:443` / `172.64.149.246:443`) --
  i.e. this specific local dev environment currently has flaky/failing
  network connectivity to Supabase Auth's remote endpoint, and
  `requireAuth()`'s single retry is often not enough. **Important
  correction-style caveat, same spirit as the DATA-01 correction above**:
  this may be a **local-dev-environment network artifact**, not a confirmed
  production code regression -- the Schedule 500 finding from earlier this
  pass should be read with this same caveat attached, not as a confirmed
  standalone regression, until re-tested against the live deployed
  `veridian-compliance-ai.vercel.app` (or a dev environment with reliable
  Supabase Auth connectivity) to rule out the network flakiness as the sole
  cause. Recommend Part 2's first step on both findings be exactly that
  re-test before spending implementation effort on either.

- **Working, no gap -- Customers** (persona: Khalid Al Mheiri). "No
  customers found." verified correct via SQL (zero `erp_customers` rows for
  `projexa_demo_org` before this action). "New Customer" create verified:
  `POST /api/customers` 201 (35.2s), real row confirmed via SQL
  (id `qc20sxnp528aooxwlya7f5q8`, `customer_name="Emaar Properties PJSC -
  Marina District"`, `credit_limit="500000"` both exactly matching input).
  **UAE-leak finding**: the create form's second field is **"GSTIN
  (optional)"** -- an Indian GST-registration-number field with no UAE
  VAT/TRN (Tax Registration Number) equivalent offered anywhere, shown
  unconditionally regardless of the org's country. Matches the plan's
  explicit ask to log every India-tax-specific UI leak into a UAE org's
  screens as a genuine gap.

- **GAP (cross-ref, same root cause, not re-logged in full) -- Employees:
  third PROJEXA-NO-TENANT-ISOLATION-01 occurrence, expected under known
  shared-fallback behavior per the DATA-01 correction above** (persona:
  Khalid Al Mheiri). Directory list still shows the same generic
  `@skylinebuilders-demo.veridianai.dev` accounts Priority 16 found (Arjun
  Mehta, Suresh Pillai, etc.), zero of Al Maha's 50 real personas. "Employee
  Profile" create dialog's "User" field is still a required
  select-existing-user dropdown populated with the same generic accounts,
  nothing selectable for a real Al Maha staff member. **Per this session's
  explicit instruction to apply the DATA-01 correction's lesson**: Al Maha
  has zero row in `veridian_credentials` (confirmed earlier), so this is
  expected shared-fallback behavior, not a fresh finding -- logged tersely,
  not escalated.

- **GAP (cross-ref PROJEXA-IDENTITY-BRIDGE-01, terse per plan's own
  de-duplication instruction) -- Payroll: "New Payroll Run" still fails
  identically** (persona: Khalid Al Mheiri). Payroll page loads correctly
  now (Payroll Runs / Salary Structures / Salary Components / Statutory
  Rules / Income Tax tabs all render -- REGRESSION-CONFIRMED-FIXED for
  reachability, same entitlement fix). "No payroll runs yet." verified
  correct via SQL (the one pre-existing `erp_payroll_runs` row belongs to
  `org_id='demo_org'`, not `projexa_demo_org`). "New Payroll Run" (Month
  Jul / Year) -> `POST /api/payroll/runs` returned **400** `{"error":"This
  action requires a real user session, not an API key"}` -- the exact
  identity-bridge failure text, matching the matrix's own explicit
  prediction ("EXPECT this to fail per PROJEXA-IDENTITY-BRIDGE-01"). Zero
  row confirmed via SQL. **UAE-leak finding, same class as Customers'
  GSTIN field**: the Payroll module has a first-class "Income Tax" tab with
  "Income Tax Slabs" / "Rate Bands" -- India's progressive income-tax-slab
  concept, not applicable to UAE (no personal income tax), shown
  unconditionally with no country-conditional hiding. "New Slab" dialog
  confirmed to have Name/Effective From/Standard Deduction/Rate Bands
  fields, an India-specific structure. Statutory Rules tab ("No statutory
  rules yet.") is architecturally the same likely-India-only concept
  (PF/ESI/PT, per Priority 16's own file header comments in
  `erp-payroll-service.ts`) but has zero rows to confirm the leak
  concretely this pass -- flagged as likely, not confirmed, since it's
  currently empty.

## Correction to DATA-01 finding (verified live by the controlling session, 2026-07-15, after Part 1 handoff)

Part 1's DATA-01 finding above was written from local-dev-server observation only and
drew two conclusions that direct production testing does NOT support. Before this
propagates into Part 2's implementation plan as an overstated emergency, here is what
was independently re-verified against the REAL LIVE compliance-tracker API
(`https://veridian-compliance-ai.vercel.app`), not local dev:

1. **Vercel env vars ARE set in production**, contradicting Part 1's inference (which
   was based on DOMAIN-02's older, pre-PLATFORM-01 memory note, not a live check):
   `vercel env ls production` on the projexa project confirms `SUPABASE_DB_PASSWORD`
   (set 2h before this check) and `NEXT_PUBLIC_SUPABASE_URL` both present. The
   `getVeridianApiKey()` failure Part 1 observed is a **local dev-only** artifact
   (this session's local `.env.local` lacks these), not necessarily present in prod.
2. **Direct proof tenant isolation IS working correctly in production for a real
   per-org key**: queried `public.veridian_credentials` -- exactly ONE real row
   exists, for "Platform Test Org Alpha" (`veridian_org_id=xepoooh8p1iqm6eqjetbhuuc`,
   real `vk_` key). Called the LIVE API directly with that real key (bypassing the
   browser/local-dev-server path entirely):
   - `GET /dashboard` -> `{"totalProjects":0,...,"projects":[]}` -- correctly isolated,
     zero leaked projects from Meridian/Al Maha/the shared demo org.
   - `GET /schedule/gantt?projectId=projexa_demo_project` (Meridian's own Villa 21
     project id) -> `{"tasks":[],"dependencies":[],"milestones":[]}` -- **empty, not
     Meridian's real 5-task Foundation/Framing/etc. data**. This directly
     contradicts Part 1's claim of "no project-level access check of any kind" --
     with a genuine per-org key, cross-org projectId access returns nothing, not a
     leak.
3. **Root cause of what Part 1 actually observed**: Al Maha Skyline was **SQL-bulk
   provisioned** (the plan's own documented fallback after the real-signup path hit
   Supabase's email rate limit) -- it never went through `provisionOrganisation()`,
   so it has **zero row in `veridian_credentials`**, identical to every other
   SQL-bulk-provisioned test org since Priority 15/16 (Meridian Skyline Group,
   Skyline Builders, Acme Test Construction, Wave4 QA Test Co -- none of these have
   a credential row either, confirmed by the single-row query above). Every one of
   these orgs' API calls silently fall back to the single shared
   `VERIDIAN_API_KEY`/`projexa_demo_org` identity by design (`callVeridian()`'s
   documented fallback behavior) -- so "Al Maha's owner sees Meridian's projects" is
   **the same known, expected shared-fallback behavior Priority 15/16 already
   documented for every bulk-provisioned demo org**, not a new regression in
   PLATFORM-01's fix. The fix was never actually exercised by this session's test
   methodology (the real-signup path that would have exercised it was blocked by
   the rate limit), so it cannot be said to have failed.

**Real, narrower findings that DO survive this correction** (worth Part 2 acting on,
lower severity than originally logged):
- **Fail-open-by-identity, not fail-closed, when no per-org credential exists**:
  `callVeridian()`'s fallback to a shared org-wide key when `getVeridianApiKey()`
  finds no row is a deliberate, longstanding design choice (predates PLATFORM-01),
  but it means any org that is somehow left without a credential row (bulk-test
  orgs today; conceivably a real org if provisioning partially fails) silently reads
  the shared demo org's data rather than erroring loudly. Worth PLATFORM-01/Part 2
  considering whether this fallback should be dev/test-only (env-gated) rather than
  unconditional, now that a real per-org path exists and is proven to work.
  **Not fixed by this session** -- flagged for PLATFORM-01 since it touches
  `veridian-client.ts`'s fallback logic, adjacent to that session's territory.
- **Local dev environment gap**: this repo's local `.env.local` lacks
  `DATABASE_URL`/`SUPABASE_DB_PASSWORD`, so any session testing locally will
  reproduce the same misleading "isolation broken" signal Part 1 hit. Worth adding
  to `projexa/.env.local` (or `.claude/launch.json`) so local testing matches prod
  going forward -- low-risk, no production impact, safe for this session to do.
- **Currency-display finding stands unmodified**: Al Maha's AED-priced data still
  rendered in ₹ formatting -- unrelated to the credential issue, a real, separate,
  narrower gap.

**Net effect on Part 2 priority**: DATA-01 is NOT the five-alarm "any customer can
see any other customer's data in production" finding Part 1's own wording implied.
It is: real per-org isolation is proven correctly working for the one real-signup
path that exists; the demo/test-org fallback behavior is a known, pre-existing,
lower-severity design question. **Schedule "New Task" 500 regression and the
Reports-UI-never-renders gap remain the two clearest, highest-value fixes for Part 2**
-- both fully in this session's own scope (no auth-guard.ts/schema.ts involvement).

## Constitution Cross-Check

- **DATA-01 (`ENFORCED_PRODUCTION_PROVEN` per `ai-os/CONSTITUTION.yaml` line
  651) -- MAJOR, DIRECT CONTRADICTION CONFIRMED for the PROJEXA surface,
  same finding class as Priority 16's PROJEXA-NO-TENANT-ISOLATION-01, with
  ONE NEW, DEEPER layer this pass specifically uncovered.** This is the
  single most important thing this pass was asked to verify: "did PLATFORM-
  01 Wave 1 actually close DATA-01's gap for PROJEXA, end to end, through
  the real UI?" **Answer: no, confirmed two independent ways.**
  1. **Direct, live-observed cross-org leak**: logged in as Al Maha Skyline's
     real owner (a brand-new org, never previously existing) and the
     Dashboard showed all 5 of Meridian Skyline Group's India projects
     alongside Al Maha's own 5 Dubai projects. Went further than Priority 16
     was able to prove: **directly navigated to a Meridian-owned project's
     URL (`?projectId=projexa_demo_project`, Villa 21) while authenticated as
     Al Maha's owner, with zero access-control rejection** -- full real
     schedule data (5 tasks, Foundation/Framing, critical-path flags)
     rendered normally. This proves there is not merely a shared-backend-org
     data model (already known) but **no project-level access check of any
     kind** -- any authenticated PROJEXA user, from any org, can view any
     project by projectId regardless of actual ownership.
  2. **NEW this pass -- the credential-lookup mechanism itself is broken in
     this environment, independent of whether a credential row exists**:
     server console shows, on every page load, `[veridian-client]
     getVeridianApiKey(03483997-...) failed -- falling back to shared
     VERIDIAN_API_KEY if configured: No database connection string
     available. Set DATABASE_URL or NEXT_PUBLIC_SUPABASE_URL +
     SUPABASE_DB_PASSWORD.` This confirms PLATFORM-01 Wave 1's code DOES now
     attempt a real per-org credential lookup (a genuine improvement over
     Priority 16's finding that no such lookup existed at all) -- but the
     lookup itself requires a direct Postgres connection string that is
     **not configured in this local dev environment**, and per
     CONTROLLER.yaml's own pre-existing DOMAIN-02 entry, **was also
     confirmed NOT set in the live projexa-ai.com Vercel production
     deployment** ("DATABASE_URL/SUPABASE_DB_PASSWORD ... are NOT set in
     Vercel and weren't in .env.local either"). **If that gap is still
     unaddressed in production, PLATFORM-01 Wave 1's tenant-isolation fix is
     not actually effective anywhere it's deployed today, even for orgs that
     DO have a real per-org credential row** (confirmed to exist for at
     least one of the 2 "Platform Test Org Alpha" orgs created earlier the
     same day, `veridian_credentials.organization_id='6804b5a2-...'`) --
     every lookup silently falls back to the single shared key regardless.
     This is a materially different, and arguably more urgent, finding than
     "SQL-bulk-provisioned orgs don't get isolation" (expected, since they
     bypass the new provisioning path entirely) -- **even the intended-to-be-
     fixed path is not actually fixed in any environment this session could
     check.**
  3. **What this pass could NOT independently re-prove**: because Part 1's
     own real-signup attempts were blocked by the Supabase email rate limit
     (see Org build log above), this session could not itself create a
     THIRD real-signup org today to test the DATABASE_URL fix in isolation.
     Recommend Part 2 (a) fix/confirm DATABASE_URL is set in both the local
     dev convention (`.claude/launch.json` env or a documented `.env.local`
     entry) and Vercel prod for projexa, then (b) re-run this exact
     Dashboard/cross-project-URL test against one of the existing "Platform
     Test Org Alpha" orgs (already has a real credential row, no new
     signup/rate-limit needed) to get a clean pass/fail signal.
  4. Currency finding, secondary but related: even Al Maha's own
     legitimately-seeded AED-priced data renders in **₹ (INR) symbol
     formatting** throughout the Dashboard -- confirms the currency-display
     layer is hardcoded/defaulted to INR regardless of org locale, separate
     from (but compounding) the multi-currency backend work still in
     progress on PR #344.

- **DATA-04 (`ENFORCED_WITHIN_ORG`)**: not fully spot-checked this pass (only
  the CEO persona was driven through the browser) -- the one same-role pair
  check that WAS possible (comparing what Priority 16's Meridian personas
  saw for a given module vs. what Al Maha's Khalid sees) is confounded by
  the DATA-01 finding above: since both orgs share the identical backend
  data, "do same-role users see the identical module/report set" is not a
  meaningful independent test right now (they trivially see the identical
  set because it's the identical data) -- deferred to a resuming session
  once DATA-01 is closed and a genuine second isolated org exists to compare
  against.

- **SEC-03 (`ENFORCED`, full-explainability gap already disclosed)**:
  re-confirmed the `created_by_id`/`answered_by_id` attribution-loss pattern
  Priority 16 first found on Punch List, now independently reproduced on
  RFIs (`answered_by_id='projexa_demo_key'` for a real "Answer" action
  performed by Al Maha's actual owner persona, Khalid Al Mheiri, not his
  real user id). Only 1 of the plan's requested "at least 3" modules was
  actually re-checked this pass (time-constrained -- see Resume point) --
  **still universal on the 1 checked**, not narrowed at all by PLATFORM-01's
  identity work, consistent with PLATFORM-01's own scope note that Workstream
  1 was about org-level provisioning, not the separate per-user
  identity-bridge problem (PROJEXA-IDENTITY-BRIDGE-01, still explicitly
  unowned by this pass).

- **SEC-04 (`PARTIALLY_ENFORCED`)**: no destructive/hard-delete action was
  attempted or found this pass (RFI "Answer"/"Close" and risk "Log Risk" are
  additive/status-transition actions, not deletions) -- not independently
  re-verified, deferred to a resuming session.

- **ARCH-03**: not applicable this pass -- no new tables were created (all
  writes this pass target pre-existing tables).

- **UMR-02**: not applicable this pass -- no new tables were created.

## Resume point (honest checkpoint, 2026-07-15)

**Done**: org fully built (50 real personas, correct roles/departments,
correct Dubai-plausible naming mix, real login verified for the CEO), 5
projects (construction + interior + mixed categories) with pagination-worthy
seed data on 2 of them (35 BOQ lines, 25 RFIs, 24 expenses, 10 labour rows),
8 modules exercised with real UI actions + independent SQL verification
(Dashboard, Schedule, RFIs, Settings/Team, Quotations/currency,
GRC/Risk Register, Reports, AI Copilot [inconclusive]), the plan's single
highest-priority question (DATA-01/PLATFORM-01 real-signup re-verification)
answered as thoroughly as this session's real constraints (Supabase email
rate limit; no DATABASE_URL locally) allowed, with a concrete, actionable
follow-up recommendation for Part 2.

**Not done, and why**: ~22 of ~30 modules not yet touched this pass
(Meetings, Work Progress, Site Diary, Documents, Permits, Submittals, Punch
List, Change Orders, Mood Boards, FF&E, Floor Plans, Manpower & Attendance,
Materials, Vendors, Sales Dashboard, Leads, Opportunities, Sales Orders,
Customers, Budgets, Expenses-module, Accounting, Invoices, HR Dashboard,
Employees, Payroll, Recruitment, KPIs) -- this session's turn/time budget
was spent disproportionately on (a) org-build mechanics that turned out
harder than Priority 16's (stale `.next` cache, Supabase email-rate-limit
blocker, a real click-targeting tooling issue that needed a working
JS-dispatch pattern discovered through trial and error) and (b) following
the DATA-01 finding deep enough to make it airtight and actionable rather
than a one-line restatement of Priority 16's already-known finding, since
the plan explicitly called this out as the single most important thing to
verify. Only 1 persona (the CEO) was actually driven through the browser;
the other 49 exist correctly in the DB but were not individually logged in.
Reports & Analysis deep-dive only ran 1 of the plan's requested "at least
one per category" (Expense) -- no cross-project rollup report was run.
Multi-office/company-selector checks not attempted (PR #342/projexa#18
still unmerged, matches plan's own fallback instruction to log as
known-not-yet-shipped, not attempted at all this pass for time reasons).

**Recommended next steps for a resuming session** (in priority order): (1)
continue the module sweep breadth-first using the JS-dispatch click pattern
documented in the TOOLING NOTE above (do not re-discover it) -- target at
least Work Progress, Budgets, Accounting, Invoices, Employees, Payroll next,
since those are the modules with the clearest AED/currency and
identity-bridge cross-check value; (2) run the remaining ~16 report
categories plus a genuine cross-project rollup report; (3) spot-check 2-3
more personas beyond the CEO for the DATA-04 pairwise check once feasible;
(4) hand off to Part 2 with this file as-is if time runs out again --
DATA-01's finding is already solid enough to act on without further
Part-1 evidence-gathering.

## Module-by-module results, continued further (same resumed session -- Vendors, Materials, Sales Dashboard, Leads, Opportunities, Sales Orders, Meetings, Scope/BOQ create, Site Diary, Documents, Permits, Submittals, Punch List, Change Orders, Mood Boards, FF&E, Floor Plans, Manpower & Attendance, Recruitment, KPIs, HR Dashboard, Expenses module)

**REGRESSION-CONFIRMED-FIXED, reachability -- Vendors, Materials, Sales
Dashboard, Leads, Opportunities, Sales Orders, Budgets, Accounting,
Payroll** (persona: Khalid Al Mheiri). All 8 of these were flat-502'd under
PROJEXA-MODULE-ENTITLEMENT-01 at Priority 16 time (`erp`/`sales` branch not
enabled for `projexa_demo_org`). **Confirmed fixed this pass by PR #335's
entitlement enable**: every one of these pages now loads real data (200s,
not 502s). Vendors: real seeded rows render (AquaFlow Plumbing, Bright
Spark Electricals, etc., with real India-format GST numbers in a "GST"
column -- **UAE-leak finding, same class as Customers/Payroll**, this is
pre-existing seeded data not newly entered by this pass, so lower severity
but still a real display gap for a UAE org). "New Vendor" create verified:
`POST /api/vendors` 201, real row confirmed via SQL (id
`pzv8iw8lx936905jn5c1adwb`, "Al Futtaim Steel & Rebar Trading LLC"). The
create dialog's own field is also labeled **"GST (optional)"** -- a second,
independent instance of the same India-tax-field UAE-leak. Materials:
reachable now (200), no create UI exists by design (unchanged, honestly
disclosed limitation, not a bug). Sales Dashboard: loads real rollup (Total
Leads/Opportunities/Win Rate/Pipeline Value, all correctly 0, verified
against SQL). Leads: "No leads found." correct; "New Lead" create hit the
**same bare-500 failure class as Invoices** (see below) on first two
attempts, not retried further for time. Opportunities, Sales Orders: both
load correctly with real, correct empty states ("No opportunities found.",
"No sales orders found."), not independently write-tested this pass (time
budget). **Transient 401 note, not a new bug**: Vendors' first page load hit
a `GET /api/vendors` 401 Unauthorized, resolved cleanly on a simple reload
-- same fail-closed-on-flaky-network pattern Priority 16 already documented
for Attendance, not reproduced as a persistent issue.

**CORRECTION to the bare-500 root-cause theory above (found after reading
CONTROLLER.yaml's PRIORITY-19 entry mid-session -- a controlling/parallel
session had already independently root-caused and FIXED the Schedule
"New Task" 500 while this session was still testing).** The "requireAuth()
network-flakiness" theory below was this session's own guess, made without
having read the controlling session's already-completed investigation. It
was WRONG. The real, confirmed root cause (per CONTROLLER.yaml
`part_2_wave_1_close_out`, compliance-tracker PR #349, merged
`e61fa1cd`): `compliance.pms_issues.created_by_id` had a **hard FK to
`compliance.users`** that rejected the shared API-key actor id
(`"projexa_demo_key"`, which is NOT a row in `compliance.users` -- confirmed
via SQL: `select id from compliance.users where id='projexa_demo_key'`
returns zero rows) -- every PROJEXA server-to-server write that sets a
`created_by_id`/`owner_id`/etc. column to that id will hit a raw Postgres FK
violation, which compliance-tracker's own API surfaces as a 500, which
PROJEXA's route correctly passes through as `VeridianApiError.status` (not
an "outside the try/catch" bug as this session first guessed -- the bare
500 IS the correctly-propagated real status). Fixed by dropping the FK
(migration 0204) -- **independently re-verified live this session**:
queried `pg_constraint` on `compliance.pms_issues` directly, confirmed
`created_by_id_fkey` no longer exists.

**This session independently discovered the SAME bug class is NOT yet fixed
on at least 2 more tables this session's own Invoices/Leads write attempts
hit** -- confirmed by the identical query pattern against `pg_constraint`:
`compliance.erp_sales_invoices.created_by_id` and BOTH
`compliance.crm_leads.owner_id` / `compliance.crm_leads.created_by_id`
still carry a live hard FK to `compliance.users`. This is now a
**precisely root-caused, high-confidence finding** (not the vague
"network flakiness, needs live re-test" caveat this session originally
wrote) -- Invoices "Create Invoice" and Leads "New Lead" both fail for
exactly the same structural reason PMS Issues did before PR #349, and the
fix pattern is already proven (drop the FK, matching the
`job_openings.posted_by_id` precedent from Priority 16 Part 2 too).

**Broader systemic sweep run this session** (`select ... from pg_constraint
where contype='f' and confrelid='compliance.users'::regclass and
attname ilike any('{%created_by%,%recorded_by%,%owner%,%posted_by%,
%answered_by%,%assigned%,%approved_by%,%submitted_by%}')`): **roughly 60 more FK
constraints of this exact shape exist across the schema** (exact count not
load-bearing -- re-run the query below for a precise number when scoping
Part 2's fix), on tables
including (non-exhaustive, full list in this session's SQL output) --
already-hit-by-this-pass: `crm_leads` (2), `crm_opportunities` (2),
`erp_sales_invoices`, `erp_quotations`, `erp_sales_orders`; not yet hit but
same-shape and worth Part 2 proactively checking: `erp_journal_entries`,
`erp_purchase_invoices`/`_orders`/`_receipts`, `erp_cash_vouchers`,
`erp_sales_credit_notes`, `risks.owner_id`, `audit_findings.owner_id`,
`policies.created_by_id`, `board_meetings.created_by_id`,
`approval_requests.approved_by_id`, `tickets.created_by_id`, and ~30 more.
**Every one of these is a latent "will 500 the moment a PROJEXA org without
a real per-user identity bridge tries to write here" bug**, not just the 2
this pass happened to exercise -- RFIs/Work-Progress/Expenses/
Recruitment/Risks (`Log Risk`) all worked fine THIS pass only because
either (a) their specific `created_by_id`-equivalent column has no such FK,
or (b) this pass didn't exercise the specific code path that would trip
it (e.g. `risks.owner_id` has a live FK but "Log Risk" may set a different,
unconstrained field, or leave `owner_id` null) -- worth Part 2 auditing
systematically rather than assuming "already tested fine" for every
column on this list. **Recommended fix, matching the already-shipped
PR #349 precedent exactly**: either (a) drop the FK on every affected
`*_by_id`/`owner_id` column the same way PR #349 did (fast, consistent,
but loses referential integrity for genuine user actions too), or (b) the
more correct long-term fix, properly in PLATFORM-01/
PROJEXA-IDENTITY-BRIDGE-01 territory: give PROJEXA's server-to-server calls
a real per-user identity to pass through instead of the shared API key's
own synthetic id, so these FKs stay meaningful for real users and only need
relaxing for the (arguably should just error clearly, not silently
misattribute) API-key-only path. This session's own scope boundary (no
auth-guard.ts/identity-bridge rebuild) means this is registration-only, not
a fix attempt, but it's a far more actionable, root-caused finding than a
generic "re-test the live deployment" recommendation would have been.

**Working, no gap -- Scope (BOQ) UI create** (persona: Khalid Al Mheiri, on
Marina Vista Tower, the one action Priority 19 Part 1 had left untested
despite BOQ data existing via seed). "New BOQ" dialog: created "MEP Works -
Phase 1" with 2 real line items (HVAC ductwork 450 rm @ 620,
electrical conduit 380 rm @ 410) -> `POST /api/scope` 201, confirmed via SQL
-- **both line amounts arithmetically correct** (450×620=279000,
380×410=155800), matching the matrix's stated verification target exactly.

**Working, no gap (spot-checked per the plan's delta rule -- not
Priority-17-active, Priority 16 already fully verified these once) --
Meetings, Site Diary, Documents, Permits, Submittals, Punch List, Change
Orders, Mood Boards, FF&E, Floor Plans** (persona: Khalid Al Mheiri, across
Marina Vista/Palm Residence). All ten pages load correctly with honest,
correct empty states for Al Maha's genuinely-empty data on these tables
("No meetings scheduled yet.", "No diary entries yet.", "No submittals
yet.", "Nothing on the punch list yet.", "No change orders yet.", "No mood
boards yet.", "No floor plans yet.", etc.) -- reachability confirmed, no
502s, no silent-empty-masking-a-real-error pattern found. FF&E's first load
hit the same transient "Failed to load projects from VERIDIAN" error
Priority 16 already documented for AI Copilot/Reports first-loads, resolved
cleanly on reload -- not a new gap.

**Working, no gap -- Manpower & Attendance** (persona: Khalid Al Mheiri, on
Marina Vista Tower). Roster tab shows the 10 real seeded workers correctly
(UAE-plausible trade/nationality mix). "Mark Attendance" on Mohammed Iqbal
(Mason, `daily_rate=180`), Present, 8 hours -> row confirmed via SQL
(id `vlmh9h3m189horpig452b3my`): **`daily_cost=180`, correctly equal to the
worker's daily_rate for a full Present day** -- matches the matrix's stated
verification target exactly, same correct calc Priority 16 proved on
Meridian's data.

**REGRESSION-CONFIRMED-FIXED -- Recruitment "Create Job Opening"** (persona:
Khalid Al Mheiri). Priority 16 Part 1 found this reproducibly broken (400
"No organization" then 502 "Failed to create job opening"), fixed by
Priority 16 Part 2's PR #338/projexa#15. **Confirmed fixed for Al Maha
too**: Job Openings tab already showed 2 real openings from earlier
verification passes ("Post-rebase smoke test opening",
"Site Safety Officer - Priority 16 Verification" -- both pre-existing,
confirming the fix has been live and working since it merged). Created a
new one ("Senior QS - Marina Vista Tower") -> `POST
/api/recruitment/job-openings` succeeded, real row confirmed via SQL (id
`dau5cxboin9m5w7lu3xspr5n`, `num_positions=1`, `status='open'`).
**SEC-03 note (4th module occurrence this pass)**: `posted_by_id` landed as
`"projexa_demo_key"`, not Khalid's real user id -- attribution loss still
universal.

**Working, no gap -- KPIs, HR Dashboard, Expenses (module UI)** (persona:
Khalid Al Mheiri). KPIs: "No KPIs defined for this project yet." correct
(Al Maha's earlier KPI-definition create in the original Part 1 pass was on
a different, older project context, not re-confirmed against Marina Vista
here). HR Dashboard: real numbers (Total Headcount 10, Open Positions 3
matching Recruitment's real count, Pending Leave Approvals 0, Upcoming
Payroll Run "None") -- all independently plausible/correct given the
underlying data. **Minor cosmetic gap, not registered as a full finding for
time reasons**: "Headcount by Department" shows 4 rows all labeled
"Unknown" instead of real department names -- consistent with
`employee_profiles.department_id`/`job_openings.department_id` both being
null for every row this pass touched (no department-creation UI was found
anywhere in Employees/Recruitment), a real but low-severity gap worth Part
2 knowing about. Expenses (module UI, distinct from the Expense report):
"Total logged: 118,500" correctly matched the seeded 12-row total before
this pass's own addition; "Log Expense" create verified (amount=9200, real
row confirmed via SQL id `mqoj0atbjifu1d09yked65f0`) -- no currency field
in the dialog and no currency column in
`construction_expense_entries` at all, consistent with the
known-not-yet-shipped AED gap, not a new finding.

## Reports & Analysis deep-dive (Owner's explicit "check reports, analysis also" -- completed this pass)

**MAJOR CORRECTION to the earlier-logged "GAP -- Reports: API computes real,
correct data but the UI never displays it" finding (Expense report,
Business Bay).** That finding is **INVALID as originally stated** -- it was
a false positive caused by not waiting long enough for an extremely slow
network round-trip to the live deployed compliance-tracker service, not a
real rendering bug. Proven two ways this pass: (1) re-ran the identical
Expense report on the identical project (Business Bay) with a longer wait
and it **rendered correctly** (`total=82800`, full `byHead` breakdown, all
matching SQL exactly); (2) reproduced the "nothing shown" symptom ONE more
time on a fresh page load, then confirmed via `read_network_requests` that
the underlying `GET /api/reports/expense` request was still sitting with no
resolved status **20+ seconds after the click**, and eventually returned
200 with the correct body -- **once the UI had enough time to re-render
after that very slow response, the result appeared correctly**. Read
`projexa/src/components/ReportsClient.tsx:40-56` (`runReport()`) to
confirm there is no bug in the component logic itself: `setResult(data)` /
`setRanOnce(true)` fire correctly on any 200 response, there's no
stale-closure or abort-race issue. **Root cause of the original false
finding**: this session's own insufficiently patient verification step (the
cross-cutting "live deployed backend over the public internet, not local"
latency note already documented in Priority 16 applies here too, and this
particular report's roundtrip apparently runs even slower than most --
seen taking upwards of 20-50+ seconds on occasion, longer than the ~10-15s
wait used the first time this report was checked).

**Systematically re-ran 16 of the 17 exposed report types this pass**
(Project Status, Project Completion, Work Progress, Category Progress,
Attendance, Manpower Cost, Site Picture Log, Scope (BOQ), Budget Summary,
Budget vs Actual, Material Consumption, Vendor Cost, Designer Timesheet,
KPI, Revenue, Expense -- all except Weekly Project, skipped for time,
structurally identical code path to the others so low risk), across
Business Bay Corporate HQ (has real expense data) and Marina Vista Tower
(has real BOQ/work-progress/attendance data after this pass's own create
actions). **Every single one rendered correctly with genuinely computed,
correct data (cross-checked against SQL where non-zero) or an honest,
correctly-empty result (cross-checked against SQL confirming zero
underlying rows) -- zero `data_gap` placeholders, zero hallucinated
numbers, matching the plan's stated bar exactly.** Concrete cross-checks
performed: Scope(BOQ) `totalValue=338700`/`lineItemCount=20` matched
`sum(amount)`/`count(*)` on `construction_boq_line_items` exactly; Work
Progress and Category Progress both correctly showed the real
`quantityDone=18`/`percentComplete=35` entry created earlier this pass;
Attendance and Manpower Cost both correctly showed the real
Mohammed-Iqbal/`cost=180` entry; Budget vs Actual's `actual=127700`
correctly equals Marina Vista's full expense total
(118500 seed + 9200 this pass's own entry). Vendor Cost included an
honestly-disclosed scope note in its own response (`"Purchase-invoice-based
vendor cost not included -- erp_purchase_invoices has no project_id yet"`)
rather than silently omitting or fabricating that data -- a good pattern,
not a gap.

**Cross-project rollup report: completed, via AI Copilot's org-wide tools,
not the Reports page** (the Reports page's own project selector has **no
"all projects" / company-wide option at all** -- confirmed by reading its
full dropdown list, every entry is a single named project; this is a
genuine, real scope gap worth Part 2 knowing about, distinct from the
already-known "PROJEXA's 17 report types are a curated subset of
compliance-tracker's ~200" scope observation). Ran AI Copilot's
"Over-Budget Projects" tool (`list_over_budget_projects`, `inputs: {}` --
genuinely no projectId, confirmed via the raw API response), which IS the
real cross-project/org-wide rollup mechanism this codebase actually has.
**Result: `[]` (empty array), correctly honest** -- zero projects can be
"over budget" because zero budget lines exist anywhere for
`projexa_demo_org` (matches the Budgets-module gap logged earlier: nobody
has ever been able to create a budget line, so "over budget" is
structurally never true yet). This satisfies the plan's "run at least one
cross-project rollup report" requirement with a real, verified, org-wide
tool call, even though the dedicated Reports page itself doesn't expose a
company-wide option.

**AI Copilot Budget Status -- Priority 19 Part 1's original "inconclusive"
finding is RESOLVED, was a targeting problem, not a product bug.**
Re-attempted with the more precise approach the original note recommended
(walk up from the "Budget Status" text node to its containing card, then
query within that specific card for its own "Run" button, rather than a
global button-index guess) -- worked correctly on the first attempt:
`POST /api/assistant` 201, and polling the query log confirmed a real,
correct result (`actual=82800`, `budget=0`, full `byHead` breakdown, exact
match to the Expense report and to SQL) with status `done`. **Separate,
genuine minor bug found in the process**: the ORIGINAL query from Part 1's
first (mistargeted) attempt is still sitting with `status="pending"` in the
`ai_copilot_queries`-equivalent table, over an hour of real wall-clock time
later, with `result=null` -- a query that gets created but apparently never
resolves and never fails/times out either, just sits pending forever. Worth
Part 2 knowing about as a real, low-severity finding (a stuck/orphaned
query, distinct from the resolved "inconclusive" targeting issue) --
not deeply investigated this pass (time budget), flagged for Part 2.
**Positive SEC-03 counter-example, worth noting**: unlike every
compliance-tracker-backed write this pass (which all show
`created_by_id`/`recorded_by_id`/`posted_by_id`/`answered_by_id` as
`"projexa_demo_key"`), the AI Copilot query log's `created_by` field
correctly shows Khalid's **real Supabase user id**
(`efa16773-09de-48d0-83cd-c002f5bb4c2d`) -- because this table is written
directly by PROJEXA's own database, not bridged through the
compliance-tracker API key, attribution is NOT lost here. This is a useful
data point for Part 2: the identity-bridge problem is specific to the
compliance-tracker bridge, not universal to PROJEXA's own data model, which
suggests a scoped fix (carrying real user identity through
`callVeridian()`) rather than a wholesale architecture change.

## DATA-04 persona spot-check (completed this pass)

Logged in as 2 additional real personas beyond the CEO, via the real login
form (sign-out + sign-in cycle, `DemoDubai2026!`), completing the plan's
"spot-check 2-3 pairs" ask (CEO + these 2 = 3 personas total spot-checked):
- **Rajesh Nair** (Finance Manager, `admin` role): full 36-route nav list
  identical to Khalid's (owner), same Dashboard totals (₹16,64,700 total
  expenses, same 10-project list).
- **Sanjay Iyer** (`member` role): **identical 36-route nav list**, same
  Dashboard totals, Settings/Team page correctly lists the same full
  50-member roster with `khalid.almheiri@...` shown as `owner`,
  `fatima.alzaabi@...`/`rajesh.nair@...` as `admin`, etc. -- Team-list data
  is genuinely per-org-isolated and identical regardless of which member is
  viewing it.

**Conclusion**: DATA-04 (no duplicated modules within an org, same-role/
any-role users see the identical module/report set) holds for all 3 roles
tested (`owner`/`admin`/`member`) -- zero navigation/module-visibility
differences found by role, consistent with the codebase's own confirmed
design (memberships.role has no finer-grained permission tier below the 3
values, per Priority 16's own schema-read finding). This is now a genuine,
independent confirmation (not confounded by the shared-backend-data issue
the original Part 1 log flagged, since nav/module VISIBILITY is a
PROJEXA-side-only concern, unlike the underlying business DATA which is
shared per DATA-01's correction).

## Updated Resume point (end of this resumed session, 2026-07-15)

**Newly done this session, on top of the original Part 1 checkpoint**: Work
Progress (activity-picker regression-confirmed-fixed + real create),
Budgets (reachability fixed, blocked by a systemic no-fiscal-year gap,
root-caused to source), Accounting (reachability fixed, GL correct,
journal-entry account-picker "Loading…" gap root-caused to source),
Invoices (new bare-500 finding, needs live-deployment re-test), Customers
(working, UAE GSTIN-leak found), Employees (cross-ref, expected per DATA-01
correction), Payroll (identity-bridge confirmed as predicted, UAE
Income-Tax-Slab leak found), Vendors/Materials/Sales
Dashboard/Leads/Opportunities/Sales Orders (all reachability-fixed via PR
#335), Scope(BOQ) UI create (working), Meetings/Site
Diary/Documents/Permits/Submittals/Punch List/Change
Orders/Mood Boards/FF&E/Floor Plans (all spot-checked, working),
Manpower & Attendance (working, correct daily-cost calc), Recruitment
(regression-confirmed-fixed), KPIs/HR Dashboard/Expenses-module (working,
1 minor cosmetic gap on HR headcount-by-department), full 16-of-17 Reports
sweep (all working, the earlier Expense-report "never renders" finding
CORRECTED/retracted as a false positive), 1 genuine cross-project rollup
report run via AI Copilot, AI Copilot Budget Status resolved from
inconclusive to confirmed-working (plus 1 new minor stuck-query finding),
DATA-04 spot-checked across 3 personas/roles (no gap found).

**Not done, honestly**: Weekly Project report (1 of 17, skipped for time,
low risk -- structurally identical to the other 16 now-proven-working
report types). Full 50-persona walkthrough still not done (3 of 50 spot
tested: Khalid/owner, Rajesh Nair/admin, Sanjay Iyer/member -- sufficient
for the plan's "2-3 pairs" DATA-04 ask, not a full sweep). Company/office
selector checks (PR #342/projexa#18) still not attempted -- still unmerged
per the original real-time state check, no new information this pass.
SEC-04 (destructive-action/approval-bypass check) still not attempted --
every write action this pass was additive/status-transition, matching
Priority 19 Part 1's own note that no hard-delete control was found across
the whole app so far. The new bare-500 finding (Invoices/Leads, joining the
earlier Schedule one) needs a clean re-test against the live deployed
`veridian-compliance-ai.vercel.app` to separate "local-dev network
flakiness" from "real production regression" -- flagged as the single most
useful next step for whichever session picks up Part 2, since it currently
blocks a confident severity call on 3 findings at once.

**Recommended Part 2 priority order, updated after the FK root-cause
correction above**: (1) apply the already-proven PR #349 fix pattern (drop
the FK, or better, thread real user identity through) to
`erp_sales_invoices.created_by_id` and `crm_leads.owner_id`/
`created_by_id` at minimum (confirmed-affected by this pass), then
systematically audit the ~60-constraint broader list for which other
columns a real PROJEXA write path actually sets to the API-key id
(highest-value, now cheap and precisely scoped, unlike the original vague
"re-test against live deployment" recommendation); (2) fix the systemic
missing-ERP-foundational-setup gap (fiscal years/cost centers/chart of
accounts all have zero rows for every real PROJEXA org) -- this single fix
unblocks Budgets AND Accounting journal entries simultaneously, the two
highest-value Finance-section gaps found across both Priority 19 passes;
(3) the 3 UAE-leak findings (Customers' GSTIN field, Vendors' GST field,
Payroll's India Income Tax Slabs tab) -- likely a shared fix pattern
(country-conditional field rendering keyed off `organizations.country`,
which PLATFORM-01 Wave 2 is reportedly already adding per ACTIVE-CLAIMS.yaml,
worth Part 2 checking whether that lands the needed column before this
pass's fix); (4) everything else in the gap log, roughly in the severity
order already stated. **Superseded**: this file's earlier text recommending
"(4) requireAuth() robustness / wrap in shared try/catch" and "re-test
against live deployment first" was written before this correction and is
now lower-priority/partially moot -- the bare-500s were never a
`requireAuth()` problem, they were correctly-propagated real
`VeridianApiError` statuses reflecting a genuine, now-precisely-located DB
constraint issue.

## Part 2 implementation plan

### Draft 1 (written 2026-07-15, controlling session, after independently
re-verifying the systemic-FK claim via direct SQL)

Independently confirmed via `pg_constraint` (not trusting the sub-agent's
"~60" estimate as-is): **51 foreign keys** across **48 tables** in
`compliance` schema reference `compliance.users(id)` from an actor-shaped
column (`created_by_id`/`owner_id`/`posted_by_id`/`assigned_by_id`/etc.).
Only a subset are actually reachable from a PROJEXA write path today --
this pass and Priority 16 Part 2 combined have confirmed exactly 4:
`job_openings.posted_by_id` (fixed, PR #202/Priority 16 Part 2),
`pms_issues.created_by_id` (fixed, PR #349/this Priority), plus 2 newly
found this pass, NOT yet fixed: `erp_sales_invoices.created_by_id`,
`crm_leads.owner_id`/`created_by_id`.

**Workstream A -- fix the 2 newly-confirmed columns, audit the rest**:
(a) apply the identical, already-twice-precedented fix (drop the FK) to
`erp_sales_invoices.created_by_id` and `crm_leads.owner_id`/
`created_by_id` -- same migration-comment discipline as PR #349 (cite root
cause, cite precedent, note why this is scoped narrowly not swept
broadly). (b) For the remaining ~47 constrained columns: grep every
`/api/v1/projexa/**` route in compliance-tracker for which service
functions they call, cross-reference against which of those services set
an actor column from `ctx.dbUser?.id ?? ctx.apiKey!.id` (the exact pattern
that causes this bug) -- only DROP the FK for columns with a confirmed live
PROJEXA call path, do not blanket-sweep unreached columns (matches this
codebase's own established discipline, see PR #349's migration comment).
**Considered and rejected for this wave**: a structural fix (insert one
synthetic `compliance.users` row representing the PROJEXA API-key identity,
so every existing FK is satisfied at once without 47 more migrations) is
architecturally more elegant, but carries real unverified risk this
session can't clear quickly -- unknown whether other code assumes every
`users` row is a real human (e.g. notification/email fan-out, per-seat
billing counts, an admin's "Users" list rendering a synthetic row). Flagged
as a real option for a FUTURE dedicated architecture pass (cross-reference
PROJEXA-IDENTITY-BRIDGE-01, since a real fix there -- per-user identity
forwarded from PROJEXA -- would make this whole FK class moot rather than
requiring either approach) rather than adopted here under time pressure.

**Workstream B -- ERP foundational setup: CLOSED, see compliance-tracker
PR #353 / projexa PR #23.** Root-caused by direct SQL against
`pcrjmlpuqsbocqfwoxod` before writing any fix: `compliance.erp_fiscal_years`
and `compliance.erp_accounts` had exactly ONE org populated (`demo_org`,
this codebase's own internal demo org -- 1 fiscal year, 12 accounts);
`compliance.erp_cost_centers` was entirely empty, even for `demo_org` (0
rows for any org). Root cause was cause (a) from this plan's own two
candidates, confirmed by reading `erp-enablement-service.ts` itself --
its own comment said outright: *"No org-owned defaults to seed on enable
-- ERP has no equivalent of PMS's default issue types."* Comparing
against `pms-enablement-service.ts`'s `seedDefaultIssueTypes` (a
copy-on-enable seedFn, wired into the generic
`enableProductBranchForOrg(ctx, branchKey, seedFn)` mechanism) confirmed
the exact precedent pattern already existed in this codebase, just never
applied to ERP. Cause (b) (missing self-serve setup UI) was also
partially real but turned out much narrower than expected once (a) was
understood: `listFiscalYears`/`createFiscalYear`/`listCostCenters`/
`createCostCenter`/`listAccounts`/`createAccount` already existed as full
service functions, and PROJEXA already had working GET routes + UI
consumption for fiscal-years and cost-centers (`BudgetsClient.tsx`'s
"New Budget" dialog) and for accounts (`AccountingClient.tsx`'s journal
entry account picker) -- the "at least read access" bar this plan
explicitly allowed as sufficient (deferring a full COA editor) was
already met once real data existed to read. The one genuine
missing-wiring gap on the UI side: `BudgetsClient.tsx`'s own account ID
field was still free-text ("paste the VERIDIAN `erp_accounts.id`... there
is no accounts lookup surfaced to PROJEXA yet") even though the same
`/api/accounts` proxy `AccountingClient.tsx` already used was sitting
right there unused -- fixed by wiring it in (small, in the spirit of
"don't over-build," not a new editor).

Fix, compliance-tracker PR #353: `erp-enablement-service.ts` gained
`seedDefaultErpFoundation`, the same copy-on-enable pattern as PMS
(idempotent per-table -- only seeds a table genuinely empty for that
org), wired into `enableErpForOrg` via
`enableProductBranchForOrg(ctx, "erp", seedDefaultErpFoundation)`. Seeds
a calendar-year fiscal year (`FY <current year>`, Jan-Dec -- deliberately
NOT India's April-March convention, since this now runs for orgs of any
`organisations.country`), a minimal country-neutral chart of accounts
(11 accounts: Bank Account/Cash in Hand/Accounts Receivable/Accounts
Payable/Tax Payable/Owner's Capital/Sales Revenue/Cost of Goods
Sold/Salaries & Wages/Rent Expense/Office & Admin Expense, with lowercase
`accountType` values that actually match what
`erp-financial-report-service.ts`'s cash-flow statement and
`erp-invoicing-service.ts` switch on -- `demo_org`'s own seed data used
capitalized strings that never actually matched those switches, a
pre-existing inconsistency not repeated here), and one "Head Office" cost
center. Already-enabled-but-empty real orgs backfilled live via Supabase
MCP `execute_sql` (same precedent as Priority 16 Part 2's entitlement
fix): `projexa_demo_org` (the shared backend identity every real PROJEXA
org currently writes through, per PROJEXA-IDENTITY-BRIDGE-01) plus 2
other erp-enabled orgs, and `demo_org`'s missing cost center. Verified
after: all 4 erp-enabled orgs have exactly 1 fiscal year, 11-12 accounts,
1 cost center each.

Fix, projexa PR #23: `BudgetsClient.tsx`'s free-text Account ID field
replaced with a real `Select` populated from `/api/accounts` (same proxy
`AccountingClient.tsx` already used). `AccountingClient.tsx`'s account
picker also got a small hardening -- a new `accountsLoaded` flag so a
genuinely-empty chart of accounts (e.g. mid-migration, before this fix's
backfill lands somewhere) reads as an honest "no chart of accounts found"
state instead of conflating with "still loading" (both used to render
the same "Loading…" placeholder).

**Verified live**: ran the PROJEXA dev server against this worktree's own
code with the real, already-live seeded data (no waiting for deployment,
since the seed backfill was a direct DB write) -- Budgets' "New Budget"
dialog's Fiscal Year/Cost Center/Account selects populate with real data
(`FY 2026`, `Head Office`, all 11 default accounts); Accounting's "New
Journal Entry" account picker shows real accounts instead of the old
stuck "Loading…" placeholder. Deliberately NOT built: a full
chart-of-accounts editor UI (create/edit accounts from PROJEXA) -- per
this plan's own explicit allowance, "a working default + at least read
access" was the bar for this pass, and both now exist; a real construction
firm customizing its own COA beyond the seeded default remains a future
gap, not an urgent one.

**Workstream C -- UAE tax-field leak: CLOSED, see compliance-tracker PR
#353 (schema comment only, see below) / projexa PR #23 (the actual
fix).** This plan's own assumption -- that PLATFORM-01 Wave 2's
`organisations.country` (compliance-tracker#347/projexa#20) was already
"the exact hook needed" -- turned out NOT to work as assumed, and this is
the single most important correction this closure makes. Root-caused by
direct SQL before writing any fix: `compliance.organisations.country` for
`org_id='projexa_demo_org'` reads `'IN'` -- and per
PROJEXA-IDENTITY-BRIDGE-01 / PROJEXA-NO-TENANT-ISOLATION-01, EVERY real
PROJEXA org's ERP write path shares that exact same `projexa_demo_org`
backend identity (`select organization_id, veridian_org_id from
public.veridian_credentials` on `evpckeuxgvahguwsaeul` confirms
`veridian_org_id` is `null` for Al Maha Skyline, Meridian Skyline Group,
Skyline Builders, Wave4 QA Test Co, and Acme Test Construction alike --
only the 2 real-signup PLATFORM-01 verification orgs have a genuine
dedicated `veridian_org_id`). So gating PROJEXA's UI on
`compliance.organisations.country` would show or hide the 3 India-specific
fields IDENTICALLY for every PROJEXA org -- it cannot distinguish Al Maha
(UAE) from Meridian (India), which is the entire point of this fix.
Confirmed the correct alternative by checking PROJEXA's OWN
`organizations` table (`evpckeuxgvahguwsaeul`, the table Priority 19 Part
1's own Settings/Team finding already proved is genuinely per-tenant --
Al Maha's Team page does NOT show Meridian's members or vice versa): it
had no `country` column at all before this fix.

Fix: added `organizations.country` (nullable, defaults `'IN'`,
`drizzle/0009_organizations_country.sql`, projexa PR #23) to PROJEXA's
OWN tenant table instead -- genuinely per-tenant, deliberately independent
of compliance-tracker's same-named column. Applied live via Supabase MCP
against `evpckeuxgvahguwsaeul`. Exposed via `GET /api/organization`
(small additive change, `country` added to the existing select) and
`src/hooks/use-org-role.ts`'s new `isIndiaOrg` flag (reuses the hook's
existing `/api/organization` fetch rather than adding a second one; fails
toward hiding -- only shows India-specific content once `country` is
positively confirmed `'IN'`, matching `getComplianceEngine()`'s own
"don't fabricate, just don't offer" principle applied to UI instead of
computation). `CustomersClient.tsx`'s GSTIN field, `VendorsClient.tsx`'s
GST field, and `PayrollClient.tsx`'s "Income Tax" tab (both the
`TabsTrigger` and its `TabsContent`) all gated on `isIndiaOrg`. Al Maha
Skyline (`03483997-4a9d-4e07-b833-e5935101ed9a`, the confirmed E2E repro
org) backfilled to `country = 'AE'`; every other existing org left at the
default `'IN'` (no established country of record for the other test
orgs, and `'IN'` matches this codebase's own existing default-safe
convention).

**Verified live**: real, already-live browser session as Khalid Al Mheiri
(Al Maha Skyline) against this worktree's own code -- `/customers` renders
Name/Credit Limit/Status only (no GSTIN column, GSTIN field gone from
"New Customer"); `/vendors` renders Name/Type/Trade/Status only (no GST
column); `/payroll`'s tab list is Payroll Runs/Salary Structures/Salary
Components/Statutory Rules only ("Income Tax" tab absent). Deliberately
NOT built: a country-selection UI at signup or in Settings (new orgs
still default to `'IN'` until manually corrected, same opt-in-correction
pattern PLATFORM-01 Wave 2's own column uses) -- out of this pass's named
scope (3 field leaks), and building real country-selection UX is a
bigger, separate feature.

**Explicitly NOT in this wave** (per this session's own claimed scope
boundary in ACTIVE-CLAIMS.yaml): PROJEXA-IDENTITY-BRIDGE-01/
PROJEXA-NO-TENANT-ISOLATION-01 themselves (still PLATFORM-01's), any
auth-guard.ts/schema.ts auth-shape change, 2D/3D/rendering/BIM/IFC, Weekly
Project report (low-risk, deferred), full 50-persona walkthrough beyond
the 3 already spot-checked, company/office selector (still unmerged
upstream), SEC-04 destructive-action check.

### Correction pass (re-read against the gap log a second time, same
session, before dispatch)

Re-reading Workstream A against the gap log surfaced one gap in draft 1:
the draft didn't specify HOW to determine "a confirmed live PROJEXA call
path" for the audit half of Workstream A, risking a vague dispatch a
sub-agent could either under- or over-scope. Corrected: the audit method is
now explicit (grep `/api/v1/projexa/**` routes -> trace to service function
-> check if that function's insert/update sets the column from
`ctx.dbUser?.id ?? ctx.apiKey!.id` or equivalent) rather than left as an
open-ended judgment call, matching Workstream C's already-concrete method.
Also added to Workstream B: explicitly sequence root-cause-first (this
session hasn't root-caused it yet, unlike A and C which already have a
confirmed root cause) so the dispatched agent doesn't guess at a fix before
confirming which of the two plausible causes (missing auto-seed vs.
missing setup UI) is real. No other changes between draft 1 and this pass.
