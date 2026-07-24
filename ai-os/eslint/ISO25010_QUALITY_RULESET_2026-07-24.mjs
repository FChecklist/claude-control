// VERIDIAN Auditor Engine -- Phase 3, product-quality domain.
//
// Standard cited: ISO/IEC 25010:2023 (SQuaRE product quality model). The
// phase plan's own product-quality row names sonar-scanner as the real
// industry tool but excludes it from this phase (needs a running SonarQube
// server -- infra work, not a standalone binary). ESLint is already a
// devDependency in all 3 repos (compliance-tracker, projexa, veda-advisors --
// confirmed via package.json read 2026-07-24) and is the named substitute:
// zero new install required. This file is the "VERIDIAN-specific quality
// profile" the phase plan's custom_work_required calls for -- a ruleset
// mapped explicitly to ISO 25010's maintainability and reliability
// sub-characteristics, not a generic style guide.
//
// Real, confirmed divergence this file deliberately overrides rather than
// inherits: all 3 repos' own eslint.config.mjs (read directly 2026-07-24)
// turns OFF nearly every reliability-relevant core rule below (no-empty,
// no-fallthrough, no-unreachable, no-redeclare, no-case-declarations, etc.)
// -- reasonable for that repo's own day-to-day dev-velocity tradeoff, but
// exactly the signal ISO 25010 reliability asks a quality audit to surface.
// This ruleset is applied by ai-os-scripts/audit_pipeline_product_quality.py
// via `eslint --config <this file>`, which replaces (does not merge with)
// each repo's own eslint.config.mjs for the audit run only -- the repos'
// own configs are untouched.
//
// Resolution note: this file lives under ai-os/eslint/, outside all 3 repos'
// own node_modules trees, so a bare `import "eslint-config-next/typescript"`
// would fail to resolve from here. createRequire(process.cwd()) instead
// walks the *invoking* process's cwd (set by the pipeline to the repo root
// being linted) to find that repo's own installed eslint-config-next /
// typescript-eslint -- the same packages each repo's own config already
// depends on, so no new dependency is introduced by this file.
import { createRequire } from "node:module";

const require = createRequire(process.cwd() + "/package.json");
// eslint-config-next's own typescript.js: typescript-eslint's `recommended`
// config array (parser + plugin registration + baseline rules) plus two
// `warn`-level unused-vars/unused-expressions rules. Confirmed by direct
// read of node_modules/eslint-config-next/dist/typescript.js 2026-07-24.
const nextTypescript = require("eslint-config-next/typescript");

const ISO25010_RULES = {
  // --- Maintainability / analysability (ISO 25010 SS 4.2.6, degree to which
  // the impact of an intended change on a component can be assessed) ---
  // cyclomatic complexity and nesting depth are the standard static proxies
  // for "how hard is this to reason about before changing it."
  complexity: ["warn", 15],
  "max-depth": ["warn", 4],
  "max-nested-callbacks": ["warn", 4],
  "max-params": ["warn", 5],

  // --- Maintainability / modularity (degree of composition from discrete
  // components such that a change to one has minimal impact on others) ---
  "max-lines-per-function": ["warn", { max: 150, skipBlankLines: true, skipComments: true }],
  "max-classes-per-file": ["warn", 1],

  // --- Maintainability / reusability & modifiability (dead code and
  // shadowed/redeclared bindings both increase the risk of a future change
  // silently doing the wrong thing) ---
  "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
  "no-shadow": "off",
  "@typescript-eslint/no-shadow": "warn",
  "no-var": "warn",
  "prefer-const": "warn",
  "no-redeclare": "error",

  // --- Reliability / maturity & fault tolerance (ISO 25010 SS 4.2.3, degree
  // to which the system avoids failure states arising from faults). Every
  // rule below is a real core-ESLint rule that all 3 repos' own
  // eslint.config.mjs explicitly sets to "off" (confirmed by direct read
  // 2026-07-24) -- this ruleset restores them as the actual reliability
  // signal ISO 25010 asks a quality audit to surface, deliberately
  // overriding that repo-local suppression rather than inheriting it.
  "no-empty": ["error", { allowEmptyCatch: false }],
  "no-fallthrough": "error",
  "no-unreachable": "error",
  "no-case-declarations": "error",
  "no-unsafe-optional-chaining": "error",
  "no-async-promise-executor": "error",
  "no-compare-neg-zero": "error",
  "no-cond-assign": "error",
  "no-constant-condition": "error",
  "no-dupe-keys": "error",
  "no-dupe-args": "error",
  "no-duplicate-case": "error",
  "no-func-assign": "error",
  "no-import-assign": "error",
  "no-self-compare": "error",
  "no-unmodified-loop-condition": "warn",

  // --- Reliability / recoverability (ability to recover data/state directly
  // affected by a failure) -- an exception reassigned or swallowed before it
  // can be observed is the concrete way a real failure becomes unrecoverable.
  "no-ex-assign": "error",
};

const config = [
  ...nextTypescript,
  {
    rules: ISO25010_RULES,
  },
];

export default config;
