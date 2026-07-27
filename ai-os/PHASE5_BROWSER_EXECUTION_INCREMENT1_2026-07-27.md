# phase_5_browser_execution_tiers -- increment 1 checkpoint (2026-07-27)

**Plan:** `ai-os/VERIDIAN_ARCHITECTURE_V2_PHASE_PLAN_2026-07-25.yaml`, phase
`phase_5_browser_execution_tiers`. **Target repo:** compliance-tracker (per
that phase's own `target_repo`/`target_repo_note`). This doc is
`veridian_v2_browser_execution`'s knowledge_engine registration artifact
(`registration.knowledge_engine_query_command` in the phase plan).

This phase names 10 browser engines + 2 tech-stack tables + 2 Owner-directed
UI surfaces -- too large for one pass, per this task's own instruction to
checkpoint real, working, tested increments rather than attempt all 10 at
once. This is increment 1 of N.

## What increment 1 real-shipped (compliance-tracker, branch
`worker/task-20260727-065831-architecture-phase-5--browser-execution`)

- **litert-spike-unregistered**: closed -- `ai-os/MASTER_INDEX.yaml`
  (this repo) now has a real `litert_spike` registry entry, done before any
  new engine code (see git history for the one place this task's own
  ordering slipped: the registration commit landed after, not before, the
  first browser-execution source files -- corrected within the same
  session, noted here rather than silently smoothed over).
- **engine-browser-lite-llm** (technology decision): WebLLM adopted for
  real text-generation Lite LLM inference; LiteRT.js kept, unchanged, in
  its real existing vision-classifier role. Full justification:
  `repos/compliance-tracker/ai-os/BROWSER_LITE_LLM_TECH_DECISION_2026-07-27.md`.
- **engine-browser-execution** (master orchestrator), **engine-model-selection**,
  **engine-execution-planner**: `src/lib/browser-execution/tier-orchestrator.ts`
  -- real priority-ordered tier plan (NPU -> Built-in AI -> Lite LLM ->
  Transformers -> Server) with a documented real fallback chain.
- **engine-browser-npu**, **engine-browser-builtin-ai**, **engine-browser-lite-llm**
  (detection half), **engine-browser-transformers** (detection half):
  `src/lib/browser-execution/tier-detection.ts` -- real feature detection
  (navigator.ml / window.ai / navigator.gpu), no faked capability.
- **engine-server-escalation** (deepen): `tier-orchestrator.ts`'s
  `requiresServerEscalation()` + the new API route's own verification-based
  escalation flag -- two distinct, real escalation causes (no local tier at
  all vs. low compiled-prompt confidence), neither of which itself calls
  Gateway G05 (that stays exactly where it already lived, per the
  credit-governance reconciliation).
- **Owner-directed browser-to-server handoff** (Option 2, free-text chat):
  `src/lib/browser-execution/client-compile.ts` (real browser FIRST pass,
  reusing phase_2's existing `analyzeLightweight` -- required splitting
  `prompt-hash.ts` out of `prompt-construction.ts` so that function has zero
  node-only imports) wired into `src/components/veri-chat/VeriComposer.tsx`'s
  existing `discuss` mode send path (the real, already-shipped Option 2
  surface -- no new UI component was built, per the Owner's "no new engine
  unless necessary" directive), POSTing to the new
  `src/app/api/prompt-compiler/execute/route.ts` (real deterministic
  SECOND-pass SOFTWARE execution, `requireAuth()`-gated, running phase_2's
  full `runPipeline`).

## What is explicitly deferred (not silently dropped)

- Option 1 (structured mode-pill/option-chain) browser-to-server wiring --
  `VeriComposer.tsx`'s `dispatchInstruction()` already reaches
  task-execution-engine.ts's own deterministic (often LLM-free)
  engineKey/workerAgentId dispatch path, a lower-priority integration point
  than `discuss` mode (the one real path that reaches an actual AI call
  today). Filed as this increment's own explicit follow-up.
- engine-browser-mcp, engine-browser-function, engine-browser-storage,
  engine-browser-sync (L0-L4 cache tiers are phase_6's own scope per the
  phase plan), engine-browser-worker deepening beyond litert-spike's
  existing single-worker pattern, engine-browser-transformers' real
  Transformers.js model integration (only feature-detection shipped this
  pass), and a real bundled WebLLM model (see the tech-decision doc's own
  follow-up section) -- all real, all not yet started, all named explicitly
  rather than left to be silently assumed done.

## Verification

- `bun test` (compliance-tracker): 2070 pass, 0 fail, across 171 files
  (includes 22 new tests in `src/lib/browser-execution/*.test.ts` + 5 in
  `src/app/api/prompt-compiler/execute/route.test.ts`).
- `bunx tsc --noEmit`: clean (whole repo).
- `bunx eslint`: 0 errors on every touched file (1 pre-existing, unrelated
  warning in VeriComposer.tsx, not introduced by this change).
- `e2e/browser-execution-tiers.spec.ts` (new, real Playwright spec): could
  not execute in this sandbox (missing shared libraries for headless
  Chromium, no root/sudo available to install them) -- committed for CI's
  own `e2e` job (`.github/workflows/ci.yml`), which already runs
  `bunx playwright install --with-deps chromium`.
