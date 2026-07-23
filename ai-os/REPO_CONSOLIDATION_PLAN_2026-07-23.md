# Repo Consolidation + Gap Closure Plan — 2026-07-23

Companion to `ai-os/MASTER_GAP_AUDIT_2026-07-23.yaml`. Zero customers today (pre-launch), so
breaking changes are lower-risk than with live users, but still done carefully. This plan is sized
honestly: **this is genuinely large, multi-week work**, not a quick pass.

## Real current state (evidence-based, from this task's own repo-readiness agent)

- **compliance-tracker**: 2,382 tracked files, ~194,900 LOC, 51 DB tables (Drizzle, `compliance`+`platform` pg schemas), own git remote. The merge target.
- **projexa**: 441 files, ~31,600 LOC, 11 DB tables (default schema). No table-name collisions with compliance-tracker.
- **veridian-ui-kit**: 32 files, ~1,940 LOC, peer-deps only. Both products already consume it via `github:FChecklist/veridian-ui-kit#v0.2.2`; current HEAD is v0.3.0, purely additive since v0.2.2.
- **claude-control**: docs/orchestration only, no app code (this repo).
- **veda-advisors**: 214 files, ~7,022 LOC — real app, **not actually isolated today** (see Phase 2).
- **infisuite-reverse-engineering** / **odoo-reverse-engineering**: docs-only stubs, genuinely isolated already, minimal content (odoo especially — barely started).

## Phase 1 — veridian-ui-kit → compliance-tracker merge (low risk, ~2-4 days)

Real blockers found, both reconcilable:
1. `lucide-react`: compliance-tracker `^1.24.0` vs projexa `^0.525.0` (major-version split).
2. `react-resizable-panels`: compliance-tracker `^4.12.2` vs projexa `^3.0.3` (major-version split).
3. ui-kit itself is pinned at v0.2.2 in both consumers; HEAD (v0.3.0) is a purely additive diff (new `prompt-patterns` module) — safe to bump first.

Steps:
1. Bump both products' ui-kit dependency to v0.3.0 (or latest tag), verify build/lint/test green — no breaking changes expected per the additive diff.
2. Since compliance-tracker is the merge target and projexa is NOT merging, the lucide-react/react-resizable-panels split only matters if projexa is later expected to consume the *same* merged kit instance — if not, no reconciliation needed yet; flag as a future blocker only if/when projexa formally adopts the merged kit.
3. Physically fold veridian-ui-kit's source into compliance-tracker (e.g. `src/lib/ui-kit/` or a workspace package), replacing the `github:` dependency with a local path — this is the actual "merge," not just a version bump. No component-name collisions found, so this is mechanical, not a redesign.
4. Retire the standalone veridian-ui-kit repo (or keep it as a read-only historical mirror) once compliance-tracker's copy is the source of truth — Owner decision, not assumed here.

## Phase 2 — veda-advisors: real isolation cutover (medium risk, ~1 week, has a security-adjacent element — do NOT treat as low-risk)

Contrary to the "already isolated/offline" framing, this task found veda-advisors is **actively entangled** with compliance-tracker right now:
1. **Same live Supabase project**: veda-advisors' `.env.local` `NEXT_PUBLIC_SUPABASE_URL` is byte-identical to compliance-tracker's — both point at project ref `pcrjmlpuqsbocqfwoxod`.
2. **Active cross-write**: `veda-advisors/src/app/stage0/page.tsx` hardcodes that Supabase URL + anon key client-side and POSTs lead-capture form data directly into `stage0_submissions` on that shared instance, right now, in production code (not a stub).
3. **Governance entanglement**: `compliance-tracker/ai-os/sentinel/SENTINEL.yaml` lists veda-advisors in `scope.repositories` with `authority: FULL_ACCESS` for both Z.ai and Claude Code agents — meaning today's AI agents already have write authority spanning both repos.
4. **Stale documentation risk**: `claude-control/CONTROLLER.yaml` (lines 134-138) claims veda-advisors' app code lives in `veda-advisors/code-by-zai/` — that path does not exist; the real app is at repo root. Anyone planning off CONTROLLER.yaml alone will misjudge this repo's shape.

Steps (in order — do not skip or reorder, each depends on the last):
1. Provision a **separate** Supabase project for veda-advisors (new project ref, new credentials).
2. Migrate `stage0_submissions` (and any other veda-advisors-only tables/data) to the new project; verify row counts match before cutover.
3. Update `veda-advisors/.env.local` and any deployment env (Vercel) to the new project's URL/keys; redeploy; smoke-test the `stage0` lead-capture flow end-to-end against the new project.
4. Remove veda-advisors from `compliance-tracker/ai-os/sentinel/SENTINEL.yaml`'s `scope.repositories` — this is the step that actually makes "isolated" true at the governance layer, not just the code layer.
5. Correct the `code-by-zai/` stale path claim in `claude-control/CONTROLLER.yaml`.
6. Only after 1-5: confirm zero remaining references to the old shared Supabase project ref anywhere in veda-advisors (`grep -r pcrjmlpuqsbocqfwoxod veda-advisors/`) and close this phase.

## Phase 3 — infisuite-reverse-engineering / odoo-reverse-engineering: keep isolated (no action needed)

Both are genuinely isolated today — no shared env vars, no cross-imports, no CI coupling, no frontend. No blockers found. The only real note: odoo-reverse-engineering is very early (6 files, scoping not yet done per its own README) — "isolated" is true but "ready for anything" is not; don't schedule downstream work against it yet.

## Phase 4 — gap closure, sequenced by real blocking dependency (large, multi-week)

Do NOT attempt to close all ~187-259 open items (see MASTER_GAP_AUDIT) in one pass. Sequence:

1. **Immediate (before any other dispatch)**: repair `superboss-register.sqlite`'s active re-corruption (MASTER_GAP_AUDIT source_3 critical finding) — everything else that touches check-duplicate/system_index/execution_log is degraded until this is fixed a second time, and a real root cause for the *recurrence* (not just the symptom) should be found this time, since the same DB broke twice in one day.
2. **gap_queue's 13 genuinely-still-open items** (v2-4, v2-7, v2-11 through v2-22 excluding v2-19): these already have a structured task template each (full_prompt in gap_queue.yaml) and were never actually blocked by anything except the now-fixed OpenRouter credit exhaustion — dispatch_paused must be explicitly released by the Owner first (Phase 0 of this queue's own governance gate), then these can redispatch largely as-is, with the 7 newly-discovered-done items (v2-1/5/6/9/19/23/24) marked closed first so they aren't wastefully re-run.
3. **execution-rules' 5 MISSING parts** (33/34/35: Owner/Organization/End-User conversation memory stores; already flagged in that audit's own roadmap as "substantial new subsystem, deferred, needs its own future task" — treat as its own multi-task initiative, not a quick fix.
4. **198-checklist's 15 NOT_YET_BUILT + 9 NEEDS_HUMAN_JUDGMENT items**: NEEDS_HUMAN_JUDGMENT items are explicitly not machine-decidable (SOLID_ENGINEERING_DISCIPLINE category, 5 of the 9) — these need an actual Owner/senior-engineer review pass, not more AI dispatch.
5. **audit198 tool repair** (path-drift bug + missing CONSTITUTION.yaml): small, mechanical, should be done early since it blocks trustworthy future re-audits of the 198-item checklist.

## Honest sizing

- Phase 1 (ui-kit merge): days, low risk.
- Phase 2 (veda-advisors real isolation): about a week, has a real data-migration/credential-rotation step — treat with the same care as a production cutover even though there are no customers yet, because it involves real (if pre-launch) lead-capture data.
- Phase 3: no work needed.
- Phase 4: multi-week to multi-month, ~187-259 real open items across 4 sources, several of which (conversation memory stores, SUPERBOSS execution core, NEEDS_HUMAN_JUDGMENT items) are substantial subsystems in their own right, not quick fixes. Do not compress this estimate to sound smaller — the audit's own honest total says otherwise.
