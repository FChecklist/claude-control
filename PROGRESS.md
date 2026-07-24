# PROGRESS -- task-20260724-083902-phase1-testing-engine-route-tests

## Completed
- [x] Read TESTING_ENGINE_PHASE_PLAN_2026-07-24.yaml phase_1_route_test_autogeneration and
      ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml's 5 populated_routes in full.
- [x] Confirmed real environment facts before building: compliance-tracker has zero E2E tests / empty
      `e2e/` testDir (playwright.config.ts's own comment), no `bun` binary but `bunx bun test` works and
      resolves the real tsconfig `@/` alias; DATABASE_URL is a real remote Supabase project (not locally
      reachable, and not safe to write-test against without a fixture org).
- [x] Built `ai-os-scripts/generate_route_tests.py`: derives each route's real dispatch target by
      grepping+brace-matching compliance-tracker's live `task-execution-engine.ts` `dispatchEngine()` switch
      for the route's `capability_name` (no invented paths), generates a real `bun:test` file, runs it for
      real via `bunx bun test` against compliance-tracker's actual checkout, writes generated source + raw
      run output to `ai-os/testing_engine_evidence/phase1/<route_id>/`, and updates
      `ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml`'s `test_status`/`notes` fields in place (regex-scoped, existing
      comments/formatting untouched). Cleans up its transient test file from compliance-tracker's own working
      tree after each run (that repo is not part of this task's PR).
- [x] Fixed a tuple-order bug in `derive_dispatch_target()`'s no-match branch (reason landed in the wrong
      return slot) caught by a dry-run before the full batch -- one fix, verified, moved on (no repeat
      failures).
- [x] Ran the generator for real against all 5 registry routes:
      - RT-gratuity_calculator-001 -> **passing** (real `calculateGratuity()` checked against the Payment of
        Gratuity Act 15/26 formula)
      - RT-commission_calculator-001 -> **passing** (real `calculatePayrollCommission()`)
      - RT-gst_calculation_engine-001 -> **passing** (real `calculateGst()`, inter-state IGST split)
      - RT-trend_analysis_engine-001 -> **passing** (real `analyzeTrendExplained()`, matches this engine's
        own pre-existing production test file's expectations)
      - RT-capability_registry_dedup-001 -> **quarantined**, honest documented blocker: no
        `dispatchEngine()` case exists for it (matches `capability_record_schema.workflow=null`); its real
        destination (`auditDuplicateCapabilities()`) needs a live Postgres+pgvector connection this task does
        not safely exercise against a real remote DB with no test-fixture org. Not a fabricated pass.
- [x] Verified `ROUTE_REGISTRY_SCHEMA_2026-07-24.yaml` still parses as valid YAML after the script's writes,
      and that compliance-tracker's own git working tree is unmodified/clean after the run.
- [x] Marked `phase_1_route_test_autogeneration` `status: done` in `TESTING_ENGINE_PHASE_PLAN_2026-07-24.yaml`
      with a full `status_detail` covering what shipped vs what's honestly deferred (Playwright browser E2E,
      the on-create trigger, full dispatchEngine/buildCapabilityTree exhaustive enumeration -- captured one
      real data point, 186 `case` entries in `dispatchEngine()`, left the rest for Phase 4).

## Remaining
- [ ] None for Phase 1's own scope. Deferred to later phases per this task's own CONSTRAINTS (do not attempt
      in this task): Phase 2 trace verification wiring, Phase 3 route replay storage+diff, Phase 4 dependency
      graph validation / exhaustive dispatchEngine+buildCapabilityTree enumeration.
- [ ] Commit + push + open PR on claude-control (in progress).
