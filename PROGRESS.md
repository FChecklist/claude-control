# PROGRESS -- task-20260724-083420-phase1-capability-registry-live-wiring

## Completed
- [x] Read `ai-os/20_ENGINES_10_GATEWAYS_PHASE_PLAN_2026-07-24.yaml`'s `phase_1_capability_registry_live_wiring`
      objective/real_mechanism_reused and `ai-os/CAPABILITY_REGISTRY_SCHEMA_2026-07-24.yaml`'s
      `capability_record_schema`/`lookup_contract`/`populated_capabilities` in full before building anything.
- [x] Merged `origin/master` into this branch first (it was several PRs behind after other parallel worker
      tasks merged) -- only conflict was `PROGRESS.md` (expected, per-branch stub), resolved by keeping this
      task's own stub.
- [x] Extended `scripts/superboss-register.py` with a real 8th tree, `capability_registry`: table +
      FTS5 index + AFTER INSERT/UPDATE/DELETE sync triggers, same convention as the existing `knowledge_engine`
      table (not a new pattern). Columns match `capability_record_schema` field-for-field. Added
      `register-capability` (upsert ON CONFLICT(capability_name), same living-catalog convention as
      `index_add`), `lookup-capability` (implements `lookup_contract.function_signature`'s first two
      `resolution_order` stages: exact name match, then domain-scoped FTS keyword match -- the third stage,
      embedding similarity via `capability-registry-service.ts`'s `findSimilar()`, is honestly reported as
      `embedding_fallback_available: false` since that function lives in compliance-tracker's own TypeScript
      runtime, not reachable from this Python CLI), and `list-capabilities` CLI subcommands. Unit-tested
      against a scratch DB (insert, idempotent re-register/upsert, exact lookup, keyword lookup, empty lookup,
      list) before touching anything live.
- [x] Wrote `ai-os-scripts/populate_capability_registry.py`: reads
      `CAPABILITY_REGISTRY_SCHEMA_2026-07-24.yaml`'s 5 real, already-verified `populated_capabilities` rows
      (verified once already by `generate_capability_registry_candidates.py` against the live filesystem --
      not re-invented) and registers each via `register-capability`. Tested against a scratch DB (5/5
      registered) before running for real.
- [x] Wired `scripts/task-gateway.py`'s `cmd_submit` -- the real entrypoint every task hits before AI-worker
      dispatch -- to call `lookup-capability` alongside its existing `check-duplicate`/`search`/
      `query-knowledge` calls, surfacing `capability_matches` + `capability_deterministic_path_available` in
      its output. This is the literal mechanism the Owner's "most engines already exist, don't duplicate with
      AI" instruction needed to become structurally enforced rather than merely documented (the
      `lookup_contract`'s own `call_site_requirement`). Live-verified end to end: `submit --text "need to
      calculate GST rate split for an interstate invoice"` returns
      `capability_deterministic_path_available: true`, `capability_matches: [gst_calculation_engine]`.
      Confirmed `scripts/task-gateway.py`'s live copy already had an unrelated newer fix
      (`_changed_files_for_task`, from a merged PR not yet in this branch) -- applied this task's specific
      edit directly to the live file via the same targeted string match rather than overwriting it wholesale,
      so that fix was not regressed.
- [x] Ran the real live wiring against `/opt/veridian/ai-os/memory/superboss-register.sqlite` (after a
      timestamped backup copy): `init` (additive only -- pre-existing table row counts unchanged:
      instructions=269, work_items=80, actions=1482, knowledge_engine=46), then
      `populate_capability_registry.py` (`{"schema_rows_found": 5, "registered_count": 5, "failed_count": 0,
      "live_row_count_after_run": 5}`). Confirmed queryable: `lookup-capability --capability-name
      gst_calculation_engine` -> `exact_capability_name_match`; `lookup-capability --intent-text "sales
      commission percent rate"` -> `domain_scoped_keyword_match`, matched `commission_calculator`;
      `list-capabilities` -> all 5 rows, `ai_required=false`/`confidence=1.0` each.
- [x] Marked `phase_1_capability_registry_live_wiring` `status: done` in
      `20_ENGINES_10_GATEWAYS_PHASE_PLAN_2026-07-24.yaml` with a full `status_detail` (what_shipped /
      real_evidence / what_remains_for_later_phases). Updated `MASTER_INDEX.yaml`'s
      `registries.engines_gateways_architecture` entry (status + new
      `phase_1_capability_registry_live_wiring` evidence field, `next_phase` now points at Phase 2).
- [x] Registered the live wiring in `knowledge_engine`: new canonical rows for
      `ai-os-scripts/populate_capability_registry.py`, `scripts/superboss-register.py`, and
      `scripts/task-gateway.py` (with real `entity_relationships` edges to each other and to
      `CAPABILITY_REGISTRY_SCHEMA_2026-07-24.yaml`), plus `verify-knowledge` + `annotate-knowledge` on the two
      pre-existing rows this task's edits changed (`20_ENGINES_10_GATEWAYS_PHASE_PLAN_2026-07-24.yaml`,
      `MASTER_INDEX.yaml`) so their `HASH_DRIFTED` status is explained, not a silent surprise for a future
      audit. `knowledge_engine` row count: 46 -> 49.
- [x] Synced every changed/new file to its live path (`/opt/veridian/scripts/`, `/opt/veridian/ai-os/`,
      `/opt/veridian/ai-os-scripts/`) per this session's standing drift-avoidance instruction, and verified
      each synced copy is byte-identical to the git-tracked copy (except `task-gateway.py`, which correctly
      retains its pre-existing live-only fix on top of this task's edit).
- [x] No crontab changes in this phase (population is a one-time run, not a recurring job; lookup happens
      synchronously inside `task-gateway.py submit`) -- the Owner-approval-citation pattern from
      `KNOWN_CONTEXT` does not apply here.

## Remaining
- [ ] None for Phase 1's own scope, per this task's own CONSTRAINTS (do not attempt Phase 2+ in this task).
      Honestly deferred (see the phase plan's own `what_remains_for_later_phases`): a bridge into
      `capability-registry-service.ts`'s `findSimilar()` for the embedding-similarity lookup stage; broader
      auto-discovery across the ~100 real capability-tree leaves beyond the 5 already-verified rows (Phase 2's
      `false_negative_policy` self-registration mechanism); Phase 2
      (`policy_rule_decision_unification`) itself.
- [ ] Commit + push + open PR on claude-control (in progress).
