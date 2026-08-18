#!/usr/bin/env python3
"""
Real, additive-only migration: creates gtm_certification_categories in
superboss-register.sqlite and seeds one real row per each of the 25 real
GTM certification categories (Owner directive, UMR-20260805-131542-121f,
escalated as standalone highest-priority under UMR-20260805-145042-e536).
Scope note (why this is safe to run directly, not gated by
ddl_authorization_check.py): that gate covers Supabase/production-app DDL
(CREATE/ALTER/DROP against the live product database via the Supabase MCP).
This is a local, ops-layer sqlite table on the same server-side database
every other script in this repo already reads/writes (umr_tasks,
ocid_canonical_registry, ocid_master_standard_audit_log, ...) -- CREATE TABLE
IF NOT EXISTS only, never touches or alters any existing table, and reuses
superboss-register.py's own _connect()/_write_lock() so it is bound by the
exact same corruption-safety discipline as every other write path in this
codebase (see that file's _write_lock() docstring for the 2026-07-23
incident this pattern exists to prevent).
Idempotent: safe to re-run. CREATE TABLE IF NOT EXISTS + per-category
INSERT OR IGNORE keyed on category_index, so a second run changes nothing.
Booleans are never AI-narrated: `passed` starts NULL (pending) for every
category except the one this session has real, deterministic evidence for
(governance testing, category 14 -- see evidence_json on that row, which
cites the real ocid_master_standard_audit_log row id=3 recorded earlier this
session). Every other category stays NULL until real tool output backs a
real boolean -- this script does not fabricate results for categories that
have not actually been run.
"""
import importlib.util
import json
from datetime import datetime, timezone
... more files changed
