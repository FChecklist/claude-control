// VERIDIAN Auditor Engine -- Phase 4, ddd domain.
// Standard cited: Eric Evans, Domain-Driven Design (2003) + Vaughn Vernon,
// Implementing Domain-Driven Design (2013) -- bounded-context module boundary
// enforcement, per AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml's own ddd row
// ("dependency-cruiser ... CAN deterministically enforce bounded-context
// module-boundary rules once those boundaries are named").
//
// Bounded contexts are named in ai-os/ARCHITECTURE_BOUNDED_CONTEXT_MAP_2026-07-24.yaml
// (business_capability_map / bounded_contexts blocks per repo). This rule
// file does NOT hand-enumerate every real context folder -- it uses
// dependency-cruiser's own from-path-capture-group + to-path `$1`
// backreference feature (documented rules-reference.md recipe for "modules
// may not depend on each other's internals") so the boundary is enforced
// GENERICALLY between every real context-folder pair automatically, in all
// 3 repos, without needing per-repo hand maintenance as folders are added.
//
// Shared verbatim across compliance-tracker, projexa, veda-advisors: invoke
// via `npx --yes dependency-cruiser@18.1.0 --config <this file> --output-type json src`
// from within each repo's own root (so `src/...`-relative paths match, and
// `options.tsConfig` resolves that repo's own tsconfig.json for its @/* alias).
//
// The UI-context pattern tolerates an OPTIONAL '(app)/' route-group segment
// specifically because compliance-tracker/projexa nest contexts under
// src/app/(app)/<context>/ while veda-advisors' real page sections sit
// directly under src/app/<context>/ (no (app) group) -- confirmed via live
// directory reads, not assumed identical across repos. `(?!api/)` excludes
// the API tree from this rule so it is governed only by the dedicated
// api-context rule below (avoids double-flagging the same import twice
// under two different rule names).
module.exports = {
  forbidden: [
    {
      name: 'ddd-no-cross-context-ui',
      severity: 'warn',
      comment: "DDD bounded-context violation: a UI route-group module imports directly from a DIFFERENT "
        + "bounded context's UI route-group tree. Real cross-context coupling at the presentation layer is "
        + "exactly what a bounded-context boundary exists to prevent -- shared UI primitives belong in a "
        + "shared/common location, not borrowed directly from a sibling context. severity=warn (not error): "
        + "this is this phase's FIRST real enforcement pass against code that predates the boundary being "
        + "named at all, so real, pre-existing violations are expected findings, not build-breaking errors.",
      from: { path: '^src/app/(?!api/)(?:\\(app\\)/)?([^/]+)/' },
      to: {
        path: '^src/app/(?!api/)(?:\\(app\\)/)?([^/]+)/',
        pathNot: [
          '^src/app/(?:\\(app\\)/)?$1/',
        ],
      },
    },
    {
      name: 'ddd-no-cross-context-api',
      severity: 'warn',
      comment: "DDD bounded-context violation: an API route handler in one bounded context imports directly "
        + "from another bounded context's API route tree (route.ts files), instead of going through that "
        + "context's own service/engine layer or a shared contract. src/app/api/v1/<sub>/ is treated as ONE "
        + "context ('v1') by this first-pass rule -- not decomposed into its own real sub-boundaries yet, "
        + "documented as a known simplification in ARCHITECTURE_BOUNDED_CONTEXT_MAP_2026-07-24.yaml.",
      from: { path: '^src/app/api/([^/]+)/' },
      to: {
        path: '^src/app/api/([^/]+)/',
        pathNot: [
          '^src/app/api/$1/',
        ],
      },
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
