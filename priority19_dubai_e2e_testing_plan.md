# Priority 19 -- Dubai 50-User E2E Test + Fix Pass (2nd pipeline run)

STATUS: DRAFT, Part 1 not yet dispatched. This is Priority 16's 2-part
pipeline (E2E test -> analyze/plan/implement) run a SECOND time, with 3
deliberate deltas the Owner asked for 2026-07-15. Read
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

As of 2026-07-15, confirmed via `git log`/`gh pr list` (not assumed):
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

(To be filled in by the dispatched background agent. Follow Priority 16's
own gap-log format: org/persona build log, pre-flight baseline table,
module-by-module results with GAP/Working-no-gap/REGRESSION labels, major
findings called out once and cross-referenced rather than repeated,
Reports & Analysis section, Constitution Cross-Check section. Update this
file in place as testing progresses so an interruption resumes from real
recorded state, same discipline as priority16_e2e_testing_plan.md.)

_Not started yet._

## Part 2 implementation plan

_Not started -- depends on Part 1's gap log. Per the Owner's explicit
"make implementation plan, correct it": write the first draft, then
re-read it against the full gap log a second time before dispatching any
build sub-agent, and record what changed between draft 1 and the corrected
version here (not just the final version) so the correction step is
auditable, not just claimed._
