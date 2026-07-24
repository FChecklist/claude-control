// VERIDIAN Auditor Engine -- Phase 4, enterprise-architecture domain.
// Standard cited: The Open Group TOGAF 10 Standard. Per
// AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml's own enterprise-architecture row:
// "dependency-cruiser reused for layer-boundary enforcement (same tool as
// clean-architecture ... different ruleset)". Where
// clean-architecture-dependency-rule.config.cjs checks ONE coarse boundary
// (src/app vs src/lib), this file encodes VERIDIAN's real 4-layer TOGAF-style
// stack from ai-os/ARCHITECTURE_BOUNDED_CONTEXT_MAP_2026-07-24.yaml's own
// layer_boundary_map (interface/business -> application -> data ->
// technology) as an ORDERED chain: each layer may depend only on layers to
// its right below; nothing may depend on a layer to its left/above.
//
// Layer order (outer/business -> inner/data), REVISED after this task's own
// live smoke-test found the first draft's ordering backwards: an initial
// interface > application > data > technology chain flagged
// src/lib/openapi/generate.ts (technology) importing src/lib/schemas/*.ts
// (data) as a "violation" -- but a doc generator legitimately needs to read
// domain schemas; the real Clean-Architecture-consistent ring order puts
// data/schemas as the INNERMOST, most-stable ring (importable by everyone,
// imports nothing back out), with technology/infrastructure sitting between
// application and data, not beyond data. Corrected order:
//   interface (src/app)  -->  application (services/engines/...)  -->
//   technology (supabase/webhooks/pdf/openapi/queries)  -->  data (schemas/db)
// data has NO restriction on who may import it (confirmed real, legitimate
// need: openapi/generate.ts, services, and db clients all read schemas) --
// its own single restriction is that it must not import back OUT to
// technology/application/interface. `shared` (errors/prompt-cache/flat
// utility files) is exempt entirely (no folder-specific rule -- leaf
// modules by their own real content).
//
// Shared verbatim across all 3 repos -- absent layer folders in a given repo
// (e.g. veda-advisors has no technology-layer folder, projexa's application
// layer is just src/lib/services/) simply produce zero matches for that
// layer's `from`, not an error; see the map file's per-repo notes for the
// real, honest folder differences. Invoke via
// `npx --yes dependency-cruiser@18.1.0 --config <this file> --output-type json src`
// from within each repo's own root.
const APPLICATION = '^src/lib/(services|engines|ai-router|ai-team|cs|gst|loops|monitors|explainability|ingest|tds)/';
const TECHNOLOGY = '^src/lib/(supabase|webhooks|pdf|openapi|queries)/';
const DATA = '^src/lib/(schemas/|schemas\\.ts$|db/|db\\.ts$)';
const INTERFACE = '^src/app/';

module.exports = {
  forbidden: [
    {
      name: 'ea-application-no-import-interface',
      severity: 'warn',
      comment: "TOGAF layer-order violation: the application layer (business/use-case logic) imports the "
        + "interface layer (src/app -- the outermost, delivery-mechanism ring). Application logic must not "
        + "reach back up into the layer that is supposed to depend on it. severity=warn: this is this "
        + "phase's first real enforcement pass against pre-existing code, so real violations are expected "
        + "findings, not build-breaking errors.",
      from: { path: APPLICATION },
      to: { path: INTERFACE },
    },
    {
      name: 'ea-technology-no-import-interface',
      severity: 'warn',
      comment: "TOGAF layer-order violation: the technology layer (Supabase clients, webhook handlers, "
        + "PDF/OpenAPI plumbing) imports the interface layer (src/app route handlers/pages). Infrastructure "
        + "code depending on delivery-mechanism code is a real layering inversion.",
      from: { path: TECHNOLOGY },
      to: { path: INTERFACE },
    },
    {
      name: 'ea-technology-no-import-application',
      severity: 'warn',
      comment: "TOGAF layer-order violation: the technology layer imports the application layer directly "
        + "(e.g. a Supabase/webhook/PDF helper calling straight into a business service), instead of the "
        + "application layer depending on technology through its own call sites. Confirmed via a live grep "
        + "this task ran before writing this rule that this pattern is real but rare in compliance-tracker "
        + "today (2 real hits: supabase/auth-guard.ts, pdf/quotation-pdf.ts) -- a genuine, actionable "
        + "finding, not rule noise from an overly strict pattern.",
      from: { path: TECHNOLOGY },
      to: { path: APPLICATION },
    },
    {
      name: 'ea-data-no-import-application-interface-or-technology',
      severity: 'warn',
      comment: "TOGAF layer-order violation: the data layer (schemas/persistence models -- the innermost, "
        + "most-stable ring) imports the application, interface, or technology layers above it. A schema/ "
        + "model definition depending on business logic, route handlers, or infrastructure clients is a "
        + "real layering inversion -- data is meant to be importable by everyone and depend on nothing.",
      from: { path: DATA },
      to: { path: `${APPLICATION}|${INTERFACE}|${TECHNOLOGY}` },
    },
  ],
  options: {
    tsConfig: { fileName: 'tsconfig.json' },
    exclude: {
      path: 'node_modules|\\.next|__tests__|\\.test\\.(ts|tsx)$|\\.spec\\.(ts|tsx)$',
    },
    doNotFollow: { path: 'node_modules' },
  },
};
