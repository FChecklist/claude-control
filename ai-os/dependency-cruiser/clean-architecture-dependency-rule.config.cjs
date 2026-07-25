// VERIDIAN Auditor Engine -- Phase 4, clean-architecture domain.
// Standard cited: Robert C. Martin, Clean Architecture: A Craftsman's Guide
// to Software Structure and Design (2017) -- The Dependency Rule: "source
// code dependencies can only point inwards", per
// AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml's own clean-architecture row.
//
// VERIDIAN's real layer names (see ai-os/ARCHITECTURE_BOUNDED_CONTEXT_MAP_2026-07-24.yaml
// layer_boundary_map per repo): src/app (interface -- outermost ring, Next.js
// framework/delivery mechanism) vs src/lib (application/domain/infrastructure
// -- everything inward of it). This is deliberately a SINGLE coarse boundary
// check (one rule), distinct from enterprise-architecture-layers.config.cjs's
// finer TOGAF 4-layer ordered chain -- same tool, different ruleset, exactly
// as the phase plan's own enterprise-architecture row describes ("same tool
// as clean-architecture ... different ruleset").
//
// Shared verbatim across all 3 repos (same src/app vs src/lib split
// confirmed live in all 3). Invoke via
// `npx --yes dependency-cruiser@18.1.0 --config <this file> --output-type json src`
// from within each repo's own root.
module.exports = {
  forbidden: [
    {
      name: 'clean-arch-no-inner-imports-outer',
      severity: 'error',
      comment: "Robert C. Martin's Dependency Rule: source code dependencies must point only inward. "
        + "src/lib (VERIDIAN's application/domain/infrastructure code -- everything the plan's own "
        + "custom_work_required note calls 'inner layers') must never import from src/app (the Next.js "
        + "interface/delivery-mechanism layer -- the outermost ring). src/app may freely import src/lib; "
        + "the reverse is a real Dependency Rule violation, not a style preference -- severity=error.",
      from: { path: '^src/lib/' },
      to: { path: '^src/app/' },
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
