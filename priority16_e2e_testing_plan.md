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

Not written yet -- blocked on PRIORITY-15 reaching status: done (module list
must be final first). Write the literal per-module/per-role test script here
before Part 1 starts; this is the "tightened instructions" Part 1 (Low
effort) needs to actually perform, not a re-paste of the Owner's original
prose.

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
