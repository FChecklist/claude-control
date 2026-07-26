#!/usr/bin/env python3
"""
Dispatch-time pre-flight gate closing a real gap found 2026-07-26: the
standing rule "Supabase schema changes are tier2-by-definition, always held
for human sign-off, never auto-merged" was only enforced at the PR-merge
step (task_lifecycle_state_machine.S9_AUDITED/S10b_HELD_FOR_SIGNOFF in
PROTOCOL_OWNER_AI.yaml), not before a headless worker takes a live action.
task-20260726-071400-migration-drift-audit-and-reconciliation executed live
DROP TABLE/CREATE TABLE/ALTER TABLE/CREATE INDEX statements against the
production Supabase project (pcrjmlpuqsbocqfwoxod) via the Supabase MCP
apply_migration tool, entirely before any PR/CI/human review happened --
because its own dispatch prompt's SCOPE section told it to, and nothing in
the dispatch pipeline stopped that prompt from authorizing it. The worker did
exactly what its prompt said; the gap was a missing check on what a dispatch
prompt is allowed to authorize, not a misbehaving worker.

Same CLI contract as tight_task_validation.py, the check task-gateway.py's
cmd_start() already chains at this exact insertion point: invoked as
`python3 ddl_authorization_check.py <prompt-file>`, prints one JSON blob with
a "valid" boolean (plus "reason"/"guidance" on rejection) on stdout, exits 0
if valid else 1.

Fails closed: any reference to a DDL-capable Supabase MCP tool (apply_migration,
execute_sql, merge_branch -- see DDL_CAPABLE_TOOL_NAMES below), or any SQL DDL
keyword (CREATE/DROP TABLE, CREATE INDEX/CREATE UNIQUE INDEX/DROP INDEX,
ALTER TABLE, TRUNCATE, CREATE/DROP POLICY, CREATE/DROP TRIGGER, ADD/DROP
COLUMN, ADD CONSTRAINT, CREATE/DROP TYPE, CREATE SCHEMA, CREATE EXTENSION,
CREATE SEQUENCE -- see DDL_KEYWORD_PATTERNS below) anywhere in the
prompt-file's text is rejected UNLESS the text also contains a line literally
matching `PRE-APPROVED-LIVE-DDL:` followed by a real reference: a decision-log
entry ID (the `KE-<date>-<time>-<hex>` knowledge_engine ID format, or an
`OWNER_DECISIONS_NEEDED_<date>.yaml#<id>` citation -- the same
approved_via/decision-log convention already used elsewhere in this pipeline,
see PROTOCOL_OWNER_AI.yaml's OWNER_DECISIONS_NEEDED_2026-07-23.yaml
description), or a dated free-text note of meaningful length (e.g. "Owner
approved via Slack DM on 2026-07-25, see #ops-approvals thread"). A bare
non-empty string like `PRE-APPROVED-LIVE-DDL: yes` is NOT a citation and does
not pass -- it references nothing that can be checked. Matching is
case-insensitive and scans the whole prompt-file text (not line-by-line), so
multi-line/multi-statement SQL blocks and lowercase/mixed-case SQL are all
covered the same as single-line uppercase SQL. Plain SELECT-style read-only
SQL never matches any of the DDL keywords below and so never triggers this
gate.

Known limitation (accepted, not solved by this gate): this is a DISPATCH-TIME
scan of the prompt-file's TEXT, not a RUNTIME interceptor of the actual tool
call. It catches a dispatch prompt that tells a worker to run live DDL. It
does NOT catch a worker whose prompt says nothing about DDL but which
decides, mid-task, to call apply_migration/execute_sql/merge_branch anyway --
this session's agent framework has no mechanism to intercept a live MCP tool
call while a worker is running, only to vet the prompt before the worker is
dispatched. Closing that gap would require a runtime tool-call interceptor
(e.g. an MCP-proxy-level policy check), which is a materially different and
larger piece of infrastructure than a prompt-text scan and is explicitly out
of scope here. Treat this gate as a real but partial control: it stops a
prompt from authorizing live DDL up front, it does not guarantee no live DDL
happens after dispatch.
"""
import json
import re
import sys

DDL_KEYWORD_PATTERNS = {
    "CREATE TABLE": re.compile(r"\bCREATE\s+TABLE\b", re.IGNORECASE),
    "ALTER TABLE": re.compile(r"\bALTER\s+TABLE\b", re.IGNORECASE),
    "DROP TABLE": re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE),
    "CREATE UNIQUE INDEX": re.compile(r"\bCREATE\s+UNIQUE\s+INDEX\b", re.IGNORECASE),
    "CREATE INDEX": re.compile(r"\bCREATE\s+INDEX\b", re.IGNORECASE),
    "DROP INDEX": re.compile(r"\bDROP\s+INDEX\b", re.IGNORECASE),
    "TRUNCATE": re.compile(r"\bTRUNCATE\b", re.IGNORECASE),
    "CREATE POLICY": re.compile(r"\bCREATE\s+POLICY\b", re.IGNORECASE),
    "DROP POLICY": re.compile(r"\bDROP\s+POLICY\b", re.IGNORECASE),
    "CREATE TRIGGER": re.compile(r"\bCREATE\s+TRIGGER\b", re.IGNORECASE),
    "DROP TRIGGER": re.compile(r"\bDROP\s+TRIGGER\b", re.IGNORECASE),
    "ADD COLUMN": re.compile(r"\bADD\s+COLUMN\b", re.IGNORECASE),
    "DROP COLUMN": re.compile(r"\bDROP\s+COLUMN\b", re.IGNORECASE),
    "ADD CONSTRAINT": re.compile(r"\bADD\s+CONSTRAINT\b", re.IGNORECASE),
    "CREATE TYPE": re.compile(r"\bCREATE\s+TYPE\b", re.IGNORECASE),
    "DROP TYPE": re.compile(r"\bDROP\s+TYPE\b", re.IGNORECASE),
    "CREATE SCHEMA": re.compile(r"\bCREATE\s+SCHEMA\b", re.IGNORECASE),
    "CREATE EXTENSION": re.compile(r"\bCREATE\s+EXTENSION\b", re.IGNORECASE),
    "CREATE SEQUENCE": re.compile(r"\bCREATE\s+SEQUENCE\b", re.IGNORECASE),
}

# Every Supabase MCP tool name available to this session whose invocation can
# run or push live DDL against a database: apply_migration and execute_sql
# both take a caller-authored "query" string executed directly against
# Postgres (apply_migration's own tool description: "Use this when executing
# DDL operations"; execute_sql's: "Executes raw SQL in the Postgres
# database"), and merge_branch pushes a dev branch's accumulated migrations
# live to production ("Merges migrations and edge functions from a
# development branch to production"). Branch-lifecycle tools that don't take
# caller-authored SQL/DDL text (create_branch, reset_branch, rebase_branch,
# delete_branch) are deliberately excluded -- they manage branches, they
# don't execute arbitrary DDL a prompt-file could smuggle through.
DDL_CAPABLE_TOOL_NAMES = ["apply_migration", "execute_sql", "merge_branch"]

DDL_TOOL_PATTERN = re.compile(
    r"\b(?:mcp__[\w]*Supabase[\w]*__)?(?:" + "|".join(DDL_CAPABLE_TOOL_NAMES) + r")\b",
    re.IGNORECASE,
)

APPROVAL_LINE_RE = re.compile(r"^\s*PRE-APPROVED-LIVE-DDL:\s*(.*)$", re.MULTILINE)

PLACEHOLDER_REFERENCE_RE = re.compile(
    r"^(tbd|todo|n/?a|none|null|undefined|yes|approved|xxx+|\.\.\.|fill.?in|pending|<.*>)$",
    re.IGNORECASE,
)

# A real decision-log citation: either the knowledge_engine KE-<date>-<time>-<hex>
# ID format, or a direct OWNER_DECISIONS_NEEDED_<date>.yaml[#<id>] file reference
# -- both are real, grep-able record formats already in use elsewhere in this
# pipeline (see PROTOCOL_OWNER_AI.yaml's approved_via/decision-log convention),
# not something a worker can fabricate by just writing a plausible-looking word.
DECISION_LOG_REFERENCE_RE = re.compile(
    r"KE-\d{8}-\d{6}-[0-9a-f]{4}|OWNER_DECISIONS_NEEDED_\d{4}-\d{2}-\d{2}\.ya?ml",
    re.IGNORECASE,
)

DATED_NOTE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

# A dated free-text approval note has to actually say something -- "ok
# 2026-07-25" has a date but isn't a citation of anything. This is a floor,
# not a guarantee of truthfulness; it's here to reject one-word/one-date
# non-answers, not to verify the note's contents.
MIN_DATED_NOTE_LENGTH = 25


def find_ddl_references(text):
    """Real hits, in DDL_KEYWORD_PATTERNS order, plus any DDL-capable Supabase
    MCP tool name found last. Empty list means no DDL-executing language was
    found."""
    hits = [label for label, pattern in DDL_KEYWORD_PATTERNS.items() if pattern.search(text)]
    tool_hit = DDL_TOOL_PATTERN.search(text)
    if tool_hit:
        hits.append(tool_hit.group(0).rsplit("__", 1)[-1].lower())
    return hits


def is_real_reference(reference):
    """A citation, not a rephrasing: either a decision-log entry ID/file
    reference in one of this pipeline's real record formats, or a dated
    free-text note long enough to actually say something. A bare word like
    "yes" or "approved" is neither."""
    if not reference or PLACEHOLDER_REFERENCE_RE.match(reference):
        return False
    if DECISION_LOG_REFERENCE_RE.search(reference):
        return True
    if DATED_NOTE_RE.search(reference) and len(reference) >= MIN_DATED_NOTE_LENGTH:
        return True
    return False


def find_pre_approval(text):
    """Returns the first PRE-APPROVED-LIVE-DDL: reference that passes
    is_real_reference(), or None if no line matches or every match fails."""
    for m in APPROVAL_LINE_RE.finditer(text):
        reference = m.group(1).strip()
        if is_real_reference(reference):
            return reference
    return None


def check_ddl_authorization(text):
    hits = find_ddl_references(text)
    if not hits:
        return {"valid": True}

    reference = find_pre_approval(text)
    if reference:
        return {"valid": True, "ddl_references_found": hits, "pre_approved_reference": reference}

    return {
        "valid": False,
        "reason": (
            "ddl_authorization_required: this prompt-file references live-DDL-executing "
            f"language ({', '.join(hits)}) with no PRE-APPROVED-LIVE-DDL: citation. "
            "Supabase schema changes (and any other live DDL) are tier2-by-definition and "
            "must be held for human sign-off before a worker is ever dispatched to run them "
            "-- this gate enforces that rule at dispatch time, not only at PR-merge time."
        ),
        "guidance": (
            "If the Owner has genuinely pre-approved this specific live DDL action out of "
            "band, add a line `PRE-APPROVED-LIVE-DDL: <real citation>` to this prompt-file -- "
            "a decision-log entry ID (KE-<date>-<time>-<hex>, or an "
            "OWNER_DECISIONS_NEEDED_<date>.yaml#<id> reference), or a dated approval note of "
            "meaningful length. A bare word like `yes` is not a citation and will not pass. "
            "Otherwise, remove the DDL instruction from SCOPE and have the worker open a "
            "migration PR for human review instead, the same as every other Supabase schema "
            "change."
        ),
        "ddl_references_found": hits,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"valid": True, "note": "usage: ddl_authorization_check.py <prompt_file>"}))
        sys.exit(0)
    with open(sys.argv[1]) as f:
        prompt_text = f.read()
    result = check_ddl_authorization(prompt_text)
    print(json.dumps(result))
    sys.exit(0 if result.get("valid") else 1)
