# Prompt Translation/Localization/Marketplace/Export/Import engines: scoping-only pass

**Phase:** `phase_8_dspy_learning_distribution_engines` increment 1
(`ai-os/VERIDIAN_ARCHITECTURE_V2_PHASE_PLAN_2026-07-25.yaml`).
**Date:** 2026-07-27.
**Status: PLANNED, NOT BUILT.** Per this increment's own hard scope
boundary, this document is architecture/scoping only -- schema design and a
rough build estimate per engine, so a future increment has a concrete
starting point instead of re-deriving scope from scratch. No migration, no
service code, no API route for any of the 5 engines below was written this
pass.

## Real, confirmed prior art these engines build on top of

All 5 have **zero prior art** in this system (re-confirmed this session by
re-reading `ai-os/VERIDIAN_ARCHITECTURE_V2_GAP_ANALYSIS_2026-07-25.yaml`
lines 828-861, same verdict the phase plan's own `integration_point` note
already stated: `none -- standalone`). What *does* already exist, and every
schema below reuses rather than duplicates:

- `compliance.prompt_templates` / `compliance.prompt_versions`
  (`src/lib/db/schema.ts:2119-2184`, phase_1) -- the real, live prompt
  registry every engine below hangs a `promptVersionId` foreign key off of,
  the same pattern `prompt_eval_cases`/`prompt_eval_runs`
  (`schema.ts:2194+`) already establish for "one more table keyed off an
  existing prompt version" rather than each new concern inventing its own
  parallel prompt-storage.
- `organisations.country` (already read by `BusinessContext.country` in
  `src/lib/prompt-compiler/types.ts:76`) -- the real, existing per-org
  country signal `engine-prompt-localization` keys off, not a new
  country-config table (a separate, already-real multi-country abstraction
  exists per this session's own memory of V2-1/PR #492 -- reuse that
  registry rather than a third country enum).

## 1. engine-prompt-translation

**Requirement:** "Multi-language prompt translation with cultural
adaptation and model-specific optimization."

**Schema (new table, additive):**
```
promptTranslations
  id                text PK
  promptVersionId   text NOT NULL  -- FK compliance.prompt_versions.id
  targetLanguage    text NOT NULL  -- ISO 639-1, e.g. 'hi', 'ar'
  translatedContent text NOT NULL
  modelUsed         text           -- which LLM/provider produced this translation, nullable (a human-authored translation has none)
  culturalNotes     jsonb NOT NULL DEFAULT '{}'  -- free-form adaptation notes (idiom substitutions, tone shifts), not a fixed schema -- varies too much per language pair to over-structure this pass
  status            text NOT NULL DEFAULT 'draft'  -- draft | reviewed | approved, mirrors prompt_versions.lifecycleState's own vocabulary rather than inventing a parallel one
  createdById       text
  createdAt         timestamp NOT NULL DEFAULT now()
  UNIQUE(promptVersionId, targetLanguage)  -- one translation per (version, language) pair; a new language edit creates a new row via prompt_versions' own versioning, not an in-place overwrite
```

**Build estimate:** ~3 days (migration + service CRUD + one API route +
tests). Translation quality itself is an LLM call through the existing
Gateway G05 (`llm-client.ts`) -- no new model-call infrastructure needed,
only a new prompt template asking for translation + cultural-adaptation
output.

## 2. engine-prompt-localization

**Requirement:** "Country/region-specific prompt adaptation including
regulatory and cultural compliance."

**Real distinction from translation (not a duplicate of #1):**
translation is language-driven; localization is jurisdiction-driven and
can apply even with no language change (e.g. an India-GST-phrased prompt
adapted for UAE-VAT terminology, both in English). Confirmed no existing
table already covers this: `organisations.country` is read, never written
by a prompt-adaptation mechanism today.

**Schema (new table, additive):**
```
promptLocalizations
  id                    text PK
  promptVersionId       text NOT NULL  -- FK compliance.prompt_versions.id
  countryCode           text NOT NULL  -- ISO 3166-1 alpha-2, e.g. 'IN', 'AE' -- same vocabulary the existing country-config registry already uses (reuse, not a 3rd enum)
  localizedContent      text NOT NULL
  regulatoryAdaptations jsonb NOT NULL DEFAULT '{}'  -- e.g. {"GST": "VAT", "PAN": "TRN"} term substitutions, real and inspectable, not a black-box rewrite
  status                text NOT NULL DEFAULT 'draft'
  createdById           text
  createdAt             timestamp NOT NULL DEFAULT now()
  UNIQUE(promptVersionId, countryCode)
```

**Build estimate:** ~3 days, same shape as translation. Real dependency:
should read from the existing multi-country compliance-engine registry
(V2-1, PR #492) for its known term-substitution pairs per country rather
than hand-authoring them here a second time -- that registry currently has
zero production callers per this session's own memory note, so this would
be its first real consumer.

## 3. engine-prompt-marketplace

**Requirement:** "Internal prompt package discovery, sharing, versioning,
dependency management."

**Schema (2 new tables, additive):**
```
promptMarketplaceListings
  id                text PK
  promptTemplateId  text NOT NULL  -- FK compliance.prompt_templates.id
  publishedVersionId text NOT NULL -- FK compliance.prompt_versions.id -- the specific version this listing publishes, not "whatever is current"
  title             text NOT NULL
  description       text
  tags              jsonb NOT NULL DEFAULT '[]'  -- string[]
  visibility        text NOT NULL DEFAULT 'org'  -- 'org' | 'global' -- org-scoped by default per this codebase's RLS-first posture, must be explicitly published global
  dependsOnListingIds jsonb NOT NULL DEFAULT '[]'  -- string[] of other promptMarketplaceListings.id -- dependency graph, resolved at install time
  installCount      integer NOT NULL DEFAULT 0
  publishedById     text
  publishedAt       timestamp NOT NULL DEFAULT now()

promptMarketplaceInstalls
  id                text PK
  listingId         text NOT NULL  -- FK promptMarketplaceListings.id
  orgId             text NOT NULL  -- the installing org (RLS-scoped, unlike the listing itself which may be global)
  installedVersionId text NOT NULL -- FK compliance.prompt_versions.id -- pinned at install time, does not silently follow future listing updates
  installedAt       timestamp NOT NULL DEFAULT now()
  UNIQUE(listingId, orgId)
```

**Build estimate:** ~5-6 days -- the largest of the 5. Real complexity:
dependency-graph resolution at install time (topological walk over
`dependsOnListingIds`, cycle detection) and org-scoped RLS on
`promptMarketplaceInstalls` while `promptMarketplaceListings` itself is
mixed-tier (org + global rows in one table, same posture
`platform_assets`/`task_capabilities` already establish elsewhere in this
schema for cross-org-visible rows -- reuse that precedent, don't invent a
new mixed-tier RLS pattern).

## 4. engine-prompt-export

**Requirement:** "Export to JSON, YAML, TOML, and proprietary formats with
schema validation."

**No new primary table.** This is a pure serialization concern over data
that already exists (`prompt_templates` + `prompt_versions` +, optionally,
`prompt_eval_cases`). Real design: a service function
`exportPromptVersion(versionId, format: "json" | "yaml" | "toml")` that
reads the existing rows and serializes with schema validation against a
new `PROMPT_EXPORT_SCHEMA_2026-XX-XX.schema.json` (same convention as this
repo's existing `PROMPT_METADATA_SCHEMA_2026-07-25.schema.json`, already
referenced by `prompt_versions.metadata`). The export *event* itself
(who/when/what format) should log through whatever this codebase's
existing audit-log mechanism is (do not build a dedicated
`promptExportJobs` table -- that would duplicate an existing audit
concern for what is fundamentally a read-only operation).

**Build estimate:** ~1.5 days -- smallest of the 5, since it reuses
existing rows and an existing audit mechanism; only the 3 real serializers
+ schema validation + 1 API route are new.

## 5. engine-prompt-import

**Requirement:** "Import from external libraries with conflict detection,
dependency analysis, sandboxing."

**Schema (new table, additive):**
```
promptImportJobs
  id                    text PK
  sourceType            text NOT NULL  -- 'file_upload' | 'url' | 'marketplace_listing'
  rawContent            text NOT NULL  -- the as-received content before any transformation, kept for audit/replay
  detectedConflicts     jsonb NOT NULL DEFAULT '[]'  -- e.g. templateKey collisions against existing prompt_templates
  dependencyAnalysis    jsonb NOT NULL DEFAULT '{}'  -- resolved against promptMarketplaceListings.dependsOnListingIds when sourceType='marketplace_listing'
  sandboxValidationResult jsonb  -- nullable until the sandbox step runs -- schema-validates against PROMPT_EXPORT_SCHEMA (shared with #4, an import is structurally "export, reversed") before any DB write
  status                text NOT NULL DEFAULT 'pending'  -- pending | validated | conflict | imported | rejected
  importedVersionId     text  -- FK compliance.prompt_versions.id, nullable until status='imported'
  createdById           text
  createdAt             timestamp NOT NULL DEFAULT now()
```

**Build estimate:** ~4-5 days. Real complexity is the "sandboxing" clause:
imported content must be schema-validated and conflict-checked
*before* any write to `prompt_templates`/`prompt_versions`, using the
same `PROMPT_EXPORT_SCHEMA` #4 defines (shared schema between export and
import closes the loop -- what this system exports, it can re-import and
validate against the identical contract).

## Rough total estimate

~17-19.5 real build-days across all 5 if built sequentially by one
implementer; genuinely parallelizable across translation/localization
(near-identical shape) and export/import (shared schema) pairs, with
marketplace as the one engine large enough to warrant its own increment.

## What this pass does NOT do (explicit, not silently skipped)

No migration was generated, no `src/lib/services/prompt-*-service.ts` file
was created, no API route was added, for any of the 5 engines above. This
document plus each engine's `MASTER_INDEX.yaml` entry (status: `planned`)
is the complete deliverable for this increment's item 3.
