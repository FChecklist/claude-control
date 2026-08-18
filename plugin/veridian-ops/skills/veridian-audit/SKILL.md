---
name: veridian-audit
description: Runs a CA/auditor-facing control checklist against the current repo covering RLS coverage, tenant isolation, audit-trail completeness, retention, and PII handling -- invoke explicitly with /veridian-audit when a compliance review is needed.
disable-model-invocation: true
---

# VERIDIAN Compliance Audit

A control checklist for a CA/auditor client. This does not auto-trigger -- it must be invoked
explicitly, because a compliance audit is a deliberate, scoped action, not something to run
opportunistically mid-task.

## Scope

Check the following five control areas against the real source of truth in this repo
(schema/migration files, RLS policy definitions, retention/cron config, PII-handling code) --
never against a doc that merely claims a control exists.

### RLS coverage

For every table holding tenant-scoped data, confirm a Row-Level Security policy exists and is
enabled (not just defined). Check both read and write policies.

### Tenant isolation

Confirm every query path that reads or writes tenant data is scoped by tenant id -- either via
RLS or an explicit `WHERE tenant_id = ...` / equivalent at the application layer. Flag any
raw/unscoped query against a multi-tenant table.

### Audit-trail completeness

Confirm create/update/delete on regulated entities (financial records, user PII, approval
actions) writes an audit-log row with actor, timestamp, and before/after state or an
equivalent diff.

### Retention

Confirm a retention policy (cron job, TTL, scheduled purge, or documented manual process) exists
for each data category that has a stated retention requirement, and that the enforced duration
matches the stated requirement.

### PII handling

Confirm PII fields are identified, and check encryption-at-rest / masking-in-logs /
access-control for each. Flag any PII field logged in plaintext or returned in an API response
without an apparent authorization check.

## Output format

Report results as a **pass/fail table with file references** -- explicitly NOT narrative
prose. One row per control checked:

| Control area | Item checked | Status | File reference |
|---|---|---|---|
| RLS coverage | `orders` table | PASS | `drizzle/0012_orders_rls.sql:14` |
| Tenant isolation | `getInvoices()` | FAIL | `src/lib/services/invoice-service.ts:41` (no tenant_id filter) |

Every row must cite a real file path. A row with no file reference is not a valid finding --
re-check it or mark it "UNABLE TO VERIFY" with the reason, rather than omitting the citation.

## What this skill does not do

It does not fix findings -- it reports them. It does not assume a control exists because a
doc or comment says so. It does not skip a control area for being out of scope of the current
task -- run all five every time it is invoked.
