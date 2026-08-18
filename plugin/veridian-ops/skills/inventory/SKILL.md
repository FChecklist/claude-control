---
name: inventory
description: Generates a compact repo map (routes, tables, shared components, shared utils) for the current repo -- use this before exploring a repo by hand, so search-reuse discipline is followed instead of re-discovering the same structure every session.
---

# Repo Inventory

Produce a compact map of the current repository so an agent can orient itself without a
fresh exploratory search.

## What to collect

1. **Routes** -- for a web app, list the route tree (file-based router paths, or an
   `express`/`fastify`/similar route table). Note which are auth-gated.
2. **Tables** -- for a repo with a database, list tables/models from the schema/migration
   source of truth (not a stale doc), with a one-line purpose each.
3. **Shared components** -- UI components imported from more than one feature area. Name the
   file path, not just the component name.
4. **Shared utils** -- utility modules imported from more than one feature area (date
   formatting, API clients, validation helpers, etc.).

Ground every entry in a real file path. Do not infer structure from naming conventions alone
-- open the actual source of truth (schema file, router config, import graph) for each
category.

## Output format

A compact markdown map, one section per category above, each entry as
`` `path/to/file` -- one-line description ``. Keep it scannable -- this is meant to replace a
fresh grep/glob sweep, not to be a narrative document.

## When to skip a category

If a category doesn't apply to this repo (e.g. no database in a pure CLI tool), say so in
one line and omit the section -- do not pad with "N/A" filler.
