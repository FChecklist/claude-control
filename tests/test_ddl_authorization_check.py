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

PRE-APPROVED-LIVE-DDL: OWNER_DECISIONS_NEEDED_2026-07-23.yaml#auth-log-group-permission
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is True, result
    assert result["pre_approved_reference"] == "OWNER_DECISIONS_NEEDED_2026-07-23.yaml#auth-log-group-permission"


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


def test_bare_yes_pre_approval_marker_does_not_count():
    """A non-empty, non-placeholder-listed word is still not a real citation --
    it references nothing that can be checked."""
    text = """
## SCOPE
Call apply_migration to run:
DROP TABLE stale_leads;

PRE-APPROVED-LIVE-DDL: yes
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result


def test_freeform_rephrasing_is_not_a_citation():
    text = """
## SCOPE
Run: DROP TABLE stale_leads;

PRE-APPROVED-LIVE-DDL: the Owner said this was fine
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result


def test_ke_style_decision_log_id_passes():
    """KE-20260725-061008-8423 is a real ID, present verbatim in
    ai-os/OWNER_ENGINE_MANDATORY_GATE_IMPLEMENTATION_2026-07-25.yaml -- the
    existence check must find it there."""
    text = """
## SCOPE
Run: DROP TABLE stale_leads;

PRE-APPROVED-LIVE-DDL: KE-20260725-061008-8423
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is True, result


def test_fabricated_ke_id_that_does_not_exist_anywhere_is_rejected():
    """Round-3 live-verified gap: a well-formed but never-recorded KE id
    must not pass on shape alone."""
    text = """
## SCOPE
Run: DROP TABLE stale_leads;

PRE-APPROVED-LIVE-DDL: KE-20260726-999999-dead
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result


def test_fabricated_owner_decisions_file_that_does_not_exist_is_rejected():
    text = """
## SCOPE
Run: DROP TABLE stale_leads;

PRE-APPROVED-LIVE-DDL: OWNER_DECISIONS_NEEDED_2026-01-01.yaml#not-a-real-entry
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result


def test_real_owner_decisions_file_reference_passes():
    """The exact scenario the reviewer live-tested: a fabricated citation
    string matching the right shape must fail, and a real, on-disk decision
    file reference must pass."""
    text = """
## SCOPE
Run: DROP TABLE stale_leads;

PRE-APPROVED-LIVE-DDL: OWNER_DECISIONS_NEEDED_2026-07-23.yaml#auth-log-group-permission
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is True, result


def test_dated_note_of_meaningful_length_passes():
    text = """
## SCOPE
Run: DROP TABLE stale_leads;

PRE-APPROVED-LIVE-DDL: Owner approved via Slack DM on 2026-07-25, see #ops-approvals thread
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is True, result


def test_short_dated_stub_is_rejected():
    """A date alone isn't a citation -- it needs to actually say something."""
    text = """
## SCOPE
Run: DROP TABLE stale_leads;

PRE-APPROVED-LIVE-DDL: ok 2026-07-25
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result


def test_create_unique_index_is_detected():
    text = """
## SCOPE
Run: CREATE UNIQUE INDEX idx_leads_email ON leads (email);
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result
    assert "CREATE UNIQUE INDEX" in result["ddl_references_found"]


def test_lowercase_and_mixed_case_ddl_keywords_are_detected():
    text = """
## SCOPE
run this migration:
drop table stale_leads;
Create Table stale_leads_v2 (id uuid primary key);
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result
    assert "DROP TABLE" in result["ddl_references_found"]
    assert "CREATE TABLE" in result["ddl_references_found"]


def test_multiline_multi_statement_sql_block_is_detected():
    text = """
## SCOPE
Apply this migration:

CREATE TABLE leads_v2 (
    id uuid primary key,
    email text not null
);

CREATE POLICY leads_v2_select ON leads_v2
    FOR SELECT USING (true);

ALTER TABLE leads_v2
    ADD CONSTRAINT leads_v2_email_unique UNIQUE (email);
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result
    for label in ("CREATE TABLE", "CREATE POLICY", "ALTER TABLE", "ADD CONSTRAINT"):
        assert label in result["ddl_references_found"], result


def test_additional_real_ddl_keywords_are_detected():
    cases = {
        "DROP INDEX": "DROP INDEX idx_leads_email;",
        "CREATE POLICY": "CREATE POLICY leads_select ON leads FOR SELECT USING (true);",
        "DROP POLICY": "DROP POLICY leads_select ON leads;",
        "CREATE TRIGGER": "CREATE TRIGGER set_updated_at BEFORE UPDATE ON leads EXECUTE FUNCTION touch();",
        "DROP TRIGGER": "DROP TRIGGER set_updated_at ON leads;",
        "ADD COLUMN": "ALTER TABLE leads ADD COLUMN region text;",
        "DROP COLUMN": "ALTER TABLE leads DROP COLUMN region;",
        "ADD CONSTRAINT": "ALTER TABLE leads ADD CONSTRAINT leads_pk PRIMARY KEY (id);",
        "CREATE TYPE": "CREATE TYPE lead_status AS ENUM ('new', 'won');",
        "DROP TYPE": "DROP TYPE lead_status;",
        "CREATE SCHEMA": "CREATE SCHEMA reporting;",
        "CREATE EXTENSION": 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";',
        "CREATE SEQUENCE": "CREATE SEQUENCE lead_seq;",
    }
    for label, sql in cases.items():
        text = f"## SCOPE\nRun:\n{sql}\n"
        result = check_ddl_authorization(text)
        assert result["valid"] is False, (label, result)
        assert label in result["ddl_references_found"], (label, result)


def test_execute_sql_tool_name_is_detected():
    text = """
## SCOPE
Call Supabase MCP's execute_sql tool directly against production to run:
DROP TABLE stale_leads;
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result
    assert "execute_sql" in result["ddl_references_found"]


def test_merge_branch_tool_name_is_detected():
    text = """
## SCOPE
Merge the dev branch's migrations to production via Supabase MCP's
merge_branch tool -- this includes:
DROP TABLE stale_leads;
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result
    assert "merge_branch" in result["ddl_references_found"]


def test_fully_qualified_mcp_tool_name_is_detected():
    text = """
## SCOPE
Call mcp__claude_ai_Supabase__apply_migration directly against production to run:
DROP TABLE stale_leads;
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result
    assert "apply_migration" in result["ddl_references_found"]


def test_grant_is_detected():
    text = """
## SCOPE
Run: GRANT ALL ON compliance.users TO anon;
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result
    assert "GRANT" in result["ddl_references_found"]


def test_revoke_is_detected():
    text = """
## SCOPE
Run: REVOKE ALL ON compliance.users FROM anon;
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result
    assert "REVOKE" in result["ddl_references_found"]


def test_security_definer_function_is_detected():
    text = """
## SCOPE
Run:
CREATE OR REPLACE FUNCTION public.escalate() RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  UPDATE compliance.users SET role = 'admin' WHERE id = auth.uid();
END;
$$;
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result
    assert "CREATE FUNCTION" in result["ddl_references_found"]
    assert "SECURITY DEFINER" in result["ddl_references_found"]


def test_alter_role_superuser_is_detected():
    text = """
## SCOPE
Run: ALTER ROLE anon SUPERUSER;
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result
    assert "ALTER ROLE" in result["ddl_references_found"]


def test_create_and_drop_role_are_detected():
    text = """
## SCOPE
Run:
CREATE ROLE backdoor LOGIN SUPERUSER;
DROP ROLE old_service_account;
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result
    assert "CREATE ROLE" in result["ddl_references_found"]
    assert "DROP ROLE" in result["ddl_references_found"]


def test_create_and_drop_view_are_detected():
    text = """
## SCOPE
Run:
CREATE VIEW leads_public AS SELECT id, email FROM leads;
DROP VIEW leads_public;
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result
    assert "CREATE VIEW" in result["ddl_references_found"]
    assert "DROP VIEW" in result["ddl_references_found"]


def test_grant_without_citation_is_rejected_end_to_end():
    """The exact scenario the reviewer live-tested: GRANT with no citation
    must fail closed."""
    text = "GRANT ALL ON compliance.users TO anon;"
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result


def test_drop_table_with_fabricated_citation_is_rejected_end_to_end():
    """The exact scenario the reviewer live-tested: a DROP TABLE statement
    paired with a fabricated, non-existent citation must fail closed."""
    text = """
DROP TABLE compliance.audit_log;

PRE-APPROVED-LIVE-DDL: KE-20260726-999999-dead
"""
    result = check_ddl_authorization(text)
    assert result["valid"] is False, result
