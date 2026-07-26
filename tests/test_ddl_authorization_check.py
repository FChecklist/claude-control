#!/usr/bin/env python3
"""
Regression tests for scripts/ddl_authorization_check.py -- the dispatch-time
gate closing the real 2026-07-26 gap where a dispatch prompt's own SCOPE
section authorized a worker to run live DDL against production Supabase via
apply_migration, before any PR/CI/human review happened. Run with:
python3 -m pytest tests/ -k ddl_authorization
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from ddl_authorization_check import check_ddl_authorization  # noqa: E402


def test_no_ddl_language_passes():
    text = """
## OBJECTIVE
Add a new read-only status endpoint.

## SCOPE
Read task rows from the database and return them as JSON. No schema changes.
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is True, result


def test_apply_migration_and_drop_table_without_approval_is_rejected():
    text = """
## OBJECTIVE
Reconcile migration drift.

## SCOPE
Call Supabase MCP's apply_migration tool directly against production to run:
DROP TABLE stale_leads;
CREATE TABLE stale_leads_v2 (id uuid primary key);
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result
    assert "reason" in result and "guidance" in result
    assert "DROP TABLE" in result["ddl_references_found"]
    assert "apply_migration" in result["ddl_references_found"]


def test_same_prompt_with_valid_pre_approval_marker_passes():
    text = """
## OBJECTIVE
Reconcile migration drift.

## SCOPE
Call Supabase MCP's apply_migration tool directly against production to run:
DROP TABLE stale_leads;
CREATE TABLE stale_leads_v2 (id uuid primary key);

PRE-APPROVED-LIVE-DDL: OWNER_DECISIONS_NEEDED_2026-07-26.yaml#KE-20260726-090000-aaaa
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is True, result
    assert result["pre_approved_reference"] == "OWNER_DECISIONS_NEEDED_2026-07-26.yaml#KE-20260726-090000-aaaa"


def test_select_only_sql_is_not_falsely_rejected():
    text = """
## OBJECTIVE
Audit lead counts per tenant.

## SCOPE
Run this read-only query against Supabase and report the results:
SELECT tenant_id, COUNT(*) FROM leads GROUP BY tenant_id;
SELECT * FROM stale_leads WHERE created_at < now() - interval '90 days';
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is True, result


def test_placeholder_pre_approval_marker_does_not_count():
    text = """
## SCOPE
Call apply_migration to run:
TRUNCATE audit_log;

PRE-APPROVED-LIVE-DDL: TBD
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result
