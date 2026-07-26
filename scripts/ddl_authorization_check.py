#!/usr/bin/env python3
"""
Dispatch-time pre-flight gate closing a real gap found 2026-07-26: the
standing rule "Supabase schema changes are tier2-by-definition, always held
for human sign-off, never auto-merged" was only enforced at the PR-merge
step (task_lifecycle_state_machine.S9_AUDITED / S10b_HELD_FOR_SIGNOFF in
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

Fails closed: any reference to Supabase MCP's apply_migration tool, or any
SQL DDL/write-DDL keyword (DROP TABLE, CREATE TABLE, ALTER TABLE, CREATE
INDEX, TRUNCATE) anywhere in the prompt-file's text is rejected UNLESS the
text also contains a line literally matching `PRE-APPROVED-LIVE-DDL:`
followed by a real, non-placeholder reference (an Owner approval note, a
decision-log entry ID, etc.) -- a citation, not a rephrasing, the same
approval-citation pattern already used elsewhere in this pipeline (see
PROTOCOL_OWNER_AI.yaml's OWNER_DECISIONS_NEEDED approved_via convention).
Plain SELECT-style read-only SQL never matches any of the DDL keywords below
and so never triggers this gate.
"""
import json
import re
import sys

DDL_KEYWORD_PATTERNS = {
    "DROP TABLE": re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE),
    "CREATE TABLE": re.compile(r"\bCREATE\s+TABLE\b", re.IGNORECASE),
    "ALTER TABLE": re.compile(r"\bALTER\s+TABLE\b", re.IGNORECASE),
    "CREATE INDEX": re.compile(r"\bCREATE\s+INDEX\b", re.IGNORECASE),
    "TRUNCATE": re.compile(r"\bTRUNCATE\b", re.IGNORECASE),
}

APPLY_MIGRATION_PATTERN = re.compile(r"apply_migration", re.IGNORECASE)

APPROVAL_LINE_RE = re.compile(r"^\s*PRE-APPROVED-LIVE-DDL:\s*(.*)$", re.MULTILINE)

PLACEHOLDER_REFERENCE_RE = re.compile(
    r"^(tbd|todo|n/?a|none|null|undefined|xxx+|\.\.\.|fill.?in|pending|<.*>)$",
    re.IGNORECASE,
)


def find_ddl_references(text):
    """Real hits, in DDL_KEYWORD_PATTERNS order, plus 'apply_migration' last
    if present. Empty list means no DDL-executing language was found."""
    hits = [label for label, pattern in DDL_KEYWORD_PATTERNS.items() if pattern.search(text)]
    if APPLY_MIGRATION_PATTERN.search(text):
        hits.append("apply_migration")
    return hits


def find_pre_approval(text):
    """Returns the first non-empty, non-placeholder PRE-APPROVED-LIVE-DDL:
    reference found, or None if no line matches or every match is a
    placeholder."""
    for m in APPROVAL_LINE_RE.finditer(text):
        reference = m.group(1).strip()
        if reference and not PLACEHOLDER_REFERENCE_RE.match(reference):
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
            "band, add a line `PRE-APPROVED-LIVE-DDL: <real citation>` (an Owner approval "
            "note or a decision-log entry ID, not a placeholder) to this prompt-file. "
            "Otherwise, remove the apply_migration / DDL instruction from SCOPE and have the "
            "worker open a migration PR for human review instead, the same as every other "
            "Supabase schema change."
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
