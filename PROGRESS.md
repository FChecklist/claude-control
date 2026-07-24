# PROGRESS -- task-20260724-070131-veridian-terminology-standardization-pha

## Completed
- [x] Investigated real DATABASE_CATALOG.json (444 tables, /opt/veridian/ai-os/DATABASE_CATALOG.json) and its
      column/foreign_keys shape.
- [x] Confirmed live Supabase project pcrjmlpuqsbocqfwoxod (verdian-ai) backs the same schema (abac_policies,
      organisations, users all present) and holds dev/seed data (org_001="Acme Corp", demo_org), not production PII.
- [x] Derived a real "most-referenced" ranking methodology (declared FK count + naming-convention `_id` column
      count, since only 7/444 tables have a declared SQL FK) and computed the real top-20 tables.
- [x] Fetched one real row (LIMIT 1) per top-20 table via Supabase MCP, redacted sensitive columns
      (password/passcode/*_hash/token), saved as ai-os/VARIABLE_DICTIONARY_SOURCE_ROWS_2026-07-24.json.
- [x] Wrote ai-os-scripts/generate_variable_dictionary.py and ran it: produced
      ai-os/VARIABLE_DICTIONARY_2026-07-24.yaml -- 320 real column entries across 20 real tables, 182 sourced from
      actual DB rows, 138 clearly-marked synthetic (sensitive columns + 2 empty tables).

- [x] Designed + wrote ai-os/TERMINOLOGY_GUARDRAIL_2026-07-24.py (lint script: flags hardcoded human-example
      literals -- placeholder company names, person names, fake email domains, ISO dates, PAN/GSTIN shapes --
      plus any unregistered <Entity.Attribute> token). Not CI-wired yet, by design (this phase = design + smoke-test only).
- [x] Smoke-tested against 3 real compliance-tracker files (communication-drafting-service.ts,
      orchestra-mock-data.ts, db/seed.ts): 36 real findings (29 placeholder_company_name "ABC Corp"/"XYZ Ltd",
      7 placeholder_email_domain "*@acme.com"), exit code 1, saved to
      ai-os/TERMINOLOGY_GUARDRAIL_SMOKE_TEST_FINDINGS_2026-07-24.json.

## Remaining
- [ ] Write ai-os/TERMINOLOGY_STANDARDIZATION_PHASE_PLAN_2026-07-24.yaml with real dependency table.
- [ ] Register all 3 artifacts in knowledge_engine (superboss-register.py register-knowledge) and
      MASTER_INDEX.yaml (registries.terminology_standardization) + live file sync.
- [ ] Commit + push, open PR, final checkpoint summary.
