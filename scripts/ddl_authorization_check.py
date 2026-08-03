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
execute_sql, merge_branch -- see DDL_CAPABLE_TOOL_NAMES below), or any SQL
DDL/DCL keyword -- schema forms (CREATE/DROP TABLE, CREATE INDEX/CREATE
UNIQUE INDEX/DROP INDEX, ALTER TABLE, TRUNCATE, CREATE/DROP POLICY,
CREATE/DROP TRIGGER, ADD/DROP COLUMN, ADD CONSTRAINT, CREATE/DROP TYPE,
CREATE SCHEMA, CREATE EXTENSION, CREATE SEQUENCE, CREATE/DROP VIEW,
CREATE/DROP/ALTER FUNCTION, COMMENT ON) and privilege-escalation forms
(GRANT, REVOKE, CREATE/ALTER/DROP ROLE, CREATE/ALTER/DROP USER, SECURITY
DEFINER, REASSIGN OWNED -- see DDL_KEYWORD_PATTERNS below) anywhere in the
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

A KE-<date>-<time>-<hex> or OWNER_DECISIONS_NEEDED_<date>.yaml citation is
verified for real EXISTENCE, not just shape: a KE-style ID must appear
literally somewhere under ai-os/ (checked via a full-text scan of that
directory at validation time -- see _ke_id_exists_on_disk below), and an
OWNER_DECISIONS_NEEDED_<date>.yaml reference must name a file that actually
exists on disk at ai-os/<that filename> (see _owner_decisions_file_exists
below). A citation matching the right shape but naming an ID/file that does
not exist anywhere -- e.g. a fabricated `KE-20260726-999999-dead` nobody ever
recorded -- is rejected, not accepted on format alone. This closes the round-2
gap where the check validated only the citation's STRING SHAPE via regex and
a fabricated-but-well-formed reference passed; a round-3 live test confirmed
that gap was real. The dated-free-text-note path (below MIN_DATED_NOTE_LENGTH
check) has NO equivalent existence check -- there is nothing on disk to look
up for free text like "Owner approved via Slack DM on 2026-07-25, see
#ops-approvals thread" -- so that path remains format-only and, honestly, a
worker could still fabricate a plausible-sounding dated note. Prefer a
KE-id/decision-file citation over a free-text note when authoring a real
approval for exactly this reason.

Known limitations (accepted, not solved by this gate):

1. This is a DISPATCH-TIME scan of the prompt-file's TEXT, not a RUNTIME
   interceptor of the actual tool call. It catches a dispatch prompt that
   tells a worker to run live DDL. It does NOT catch a worker whose prompt
   says nothing about DDL but which decides, mid-task, to call
   apply_migration/execute_sql/merge_branch anyway -- this session's agent
   framework has no mechanism to intercept a live MCP tool call while a
   worker is running, only to vet the prompt before the worker is dispatched.
   Closing that gap would require a runtime tool-call interceptor (e.g. an
   MCP-proxy-level policy check), which is a materially different and larger
   piece of infrastructure than a prompt-text scan and is explicitly out of
   scope here.
2. The existence check above proves the cited ID/file is a real record that
   exists somewhere under ai-os/ -- it does NOT prove that record is a
   genuine Owner approval OF THIS SPECIFIC DDL ACTION. A worker could in
   principle cite a real KE-id or decision file that exists for an unrelated
   reason. Fully closing that would require the check to parse and semantically
   match the cited record's content against the specific DDL statements found,
   which is out of scope here; treat the existence check as raising the bar
   from "any well-formed string" to "a real, findable record", not as a
   content/intent audit.

Treat this gate as a real but partial control: it stops a prompt from
authorizing live DDL up front with a fabricated or free-floating citation, it
does not guarantee no live DDL happens after dispatch, and it does not
semantically verify a cited real record actually approves this action.

PHASE 2 UNIFICATION (2026-07-26): this gate was a genuine 3rd disconnected
policy gate -- it shipped after
ai-os/20_ENGINES_10_GATEWAYS_PHASE_PLAN_2026-07-24.yaml's phase_2_policy_rule_decision_unification
closed with exactly 2 gates unified (preflight-guard.py, policy-enforcement-engine.ts),
and it emitted its own ad hoc {valid,reason,guidance} shape instead of
scripts/policy_decision.py's shared PolicyDecision envelope -- flagged by
ai-os/MASTER_INDEX.yaml's own registries.engines_gateways_architecture.phase_2_scope_judgment_2026_07_26
entry as the one real follow-up Phase 2 owed. Closed here: check_ddl_authorization()'s
return dict now carries an additive "policy_decision" key (a full
policy_decision_schema envelope, source_gate="ddl_authorization_check.py:check_ddl_authorization")
alongside the original valid/reason/guidance/ddl_references_found/pre_approved_reference
keys, unchanged -- same additive, non-breaking discipline Phase 2 used on
preflight-guard.py/risk-tier.py. See ai-os/POLICY_GATE_REGISTRY_2026-07-26.yaml for
the full gate registry this is now a member of.

CATEGORY A / CATEGORY B SPLIT (2026-08-03, Owner directive UMR-20260803-025317-0c64,
amended UMR-20260803-025414-8274): the incident this split responds to is real --
task-20260802-210700 ran a live, unreviewed-at-dispatch-time production migration
apply (see ai-os/boss/COMPLETED.yaml's MIGRATION-DRIFT-0264-EMAIL-INTEL-500-FIX) with
no PR and no prior tier2 sign-off. It was already-reviewed, already-merged, idempotent
SQL fixing a real Sev1 outage -- but there was no deterministic way to say so at
dispatch time, and the eventual authorization was a real, one-off Owner/PM judgment
call (UMR-20260803-012711-18b4), not a repeatable, non-human-gated policy. The Owner's
explicit decision: neither the non-technical Owner, nor the PM, nor AI judgment should
be the standing approval mechanism for this class of action -- the Kernel itself,
evaluating deterministic evidence, should be.

This splits what used to be a single PRE-APPROVED-LIVE-DDL citation requirement into
two real categories, evaluated as independent alternative acceptance paths (Category B
does not replace Category A -- either passing is sufficient):

- Category A (new schema change: new migration, new table, new column, new constraint,
  any schema redesign) -- UNCHANGED. Still requires a real PRE-APPROVED-LIVE-DDL
  citation (see above), held for explicit human sign-off exactly as it works today.
- Category B (deterministic recovery: reapplying previously-approved/merged SQL,
  idempotent reapplication, correcting production drift, reconciling metadata) -- NEW.
  A dispatch prompt-file may instead include a `CATEGORY-B-DETERMINISTIC-RECOVERY:`
  evidence block (see CATEGORY_B_BLOCK_RE / parse_category_b_block below) naming real,
  checkable evidence for all 10 of the Owner's conditions. check_category_b_recovery()
  verifies each condition against real repo/task-record state -- file existence, git
  merge history, a real idempotency-guard scan of the actual SQL text, and citation-
  existence checks structurally identical in rigor to Category A's KE-id/decision-file
  checks above (a real, findable record, not a semantic content audit -- same honest
  limitation as the rest of this module). If and only if all 10 pass, Category B
  authorizes execution without a human/PM/AI judgment call in the loop. Any single
  failed condition blocks execution and reports plainly which one failed and why --
  same fail-closed, specific-reason discipline Category A already uses.

Retroactive test (2026-08-03): MIGRATION-DRIFT-0264-EMAIL-INTEL-500-FIX was
reclassified under this new rule and checked against these same 10 conditions using
the real evidence the independent auditor already gathered -- see
ai-os/boss/COMPLETED.yaml's `category_b_retroactive_test` field on that entry for the
real, non-hypothetical result (spoiler, documented honestly there, not here: it does
NOT pass all 10 as originally executed -- no rollback path was ever documented for
this migration, condition 9. The new deterministic gate is measurably stricter than
the ad hoc human authorization that actually approved this action.).
"""
import json
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI_OS_DIR = os.path.join(REPO_ROOT, "ai-os")

# Sibling checkouts on this server share this convention (this session's own
# established layout, e.g. supervisor-entrypoint.sh's live-vs-repo reconciliation
# pattern) -- Category B evidence can name a DIFFERENT repo than the one this
# script itself lives in (ddl_authorization_check.py lives in claude-control;
# the SQL/canonical-artifact evidence it's asked to verify usually lives in
# compliance-tracker or another sibling repo).
REPOS_BASE_DIR = os.path.dirname(REPO_ROOT)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from policy_decision import emit_allow, emit_deny, make_explanation  # noqa: E402

SOURCE_GATE = "ddl_authorization_check.py:check_ddl_authorization"

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
    "CREATE VIEW": re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:MATERIALIZED\s+)?VIEW\b", re.IGNORECASE),
    "DROP VIEW": re.compile(r"\bDROP\s+(?:MATERIALIZED\s+)?VIEW\b", re.IGNORECASE),
    "CREATE FUNCTION": re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\b", re.IGNORECASE),
    "ALTER FUNCTION": re.compile(r"\bALTER\s+FUNCTION\b", re.IGNORECASE),
    "DROP FUNCTION": re.compile(r"\bDROP\s+FUNCTION\b", re.IGNORECASE),
    "COMMENT ON": re.compile(r"\bCOMMENT\s+ON\b", re.IGNORECASE),
    # Privilege-escalation DCL/DDL primitives -- arguably more dangerous than
    # the schema-shape statements above since they change WHO can do what,
    # not just the shape of the data. Real gap found 2026-07-26 round 3: all
    # of these previously passed through undetected.
    "GRANT": re.compile(r"\bGRANT\b", re.IGNORECASE),
    "REVOKE": re.compile(r"\bREVOKE\b", re.IGNORECASE),
    "CREATE ROLE": re.compile(r"\bCREATE\s+ROLE\b", re.IGNORECASE),
    "ALTER ROLE": re.compile(r"\bALTER\s+ROLE\b", re.IGNORECASE),
    "DROP ROLE": re.compile(r"\bDROP\s+ROLE\b", re.IGNORECASE),
    "CREATE USER": re.compile(r"\bCREATE\s+USER\b", re.IGNORECASE),
    "ALTER USER": re.compile(r"\bALTER\s+USER\b", re.IGNORECASE),
    "DROP USER": re.compile(r"\bDROP\s+USER\b", re.IGNORECASE),
    # SECURITY DEFINER makes a function run with its OWNER's privileges
    # rather than the caller's -- the classic Postgres privilege-escalation
    # primitive, matched standalone (not just adjacent to CREATE FUNCTION)
    # since it can equally appear in an ALTER FUNCTION statement and the
    # clause itself, wherever it appears, is the escalation vector.
    "SECURITY DEFINER": re.compile(r"\bSECURITY\s+DEFINER\b", re.IGNORECASE),
    "REASSIGN OWNED": re.compile(r"\bREASSIGN\s+OWNED\b", re.IGNORECASE),
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
# pipeline (see PROTOCOL_OWNER_AI.yaml's approved_via/decision-log convention).
# Matching this SHAPE is necessary but not sufficient -- see
# _ke_id_exists_on_disk / _owner_decisions_file_exists below, which check the
# cited ID/file is a real record, not just a well-formed string.
KE_ID_RE = re.compile(r"KE-\d{8}-\d{6}-[0-9a-f]{4}", re.IGNORECASE)
OWNER_DECISIONS_FILE_RE = re.compile(r"OWNER_DECISIONS_NEEDED_\d{4}-\d{2}-\d{2}\.ya?ml", re.IGNORECASE)

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


def _ke_id_exists_on_disk(ke_id):
    """True if the literal KE-<date>-<time>-<hex> string appears anywhere in
    a file under ai-os/ -- i.e. it's a real recorded ID, not just a
    well-formed one. A full-text scan (ai-os/ is ~11MB across ~50 files, cheap
    to re-scan per check) rather than an index, since there's no existing
    index of KE IDs to consult."""
    if not os.path.isdir(AI_OS_DIR):
        return False
    for root, _dirs, files in os.walk(AI_OS_DIR):
        for name in files:
            path = os.path.join(root, name)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    if ke_id in f.read():
                        return True
            except OSError:
                continue
    return False


def _owner_decisions_file_exists(filename):
    """True if ai-os/<filename> actually exists on disk. Only the file's
    existence is checked, not that any #<id> fragment on the citation matches
    a specific entry inside it -- see the module docstring's residual-gap
    note."""
    return os.path.isfile(os.path.join(AI_OS_DIR, filename))


def is_real_reference(reference):
    """A citation, not a rephrasing: either a decision-log entry ID/file
    reference in one of this pipeline's real record formats THAT ACTUALLY
    EXISTS on disk under ai-os/, or a dated free-text note long enough to
    actually say something. A bare word like "yes" or "approved" is neither,
    and a well-formed but fabricated KE-id/decision-file citation is rejected
    too -- shape alone is not enough."""
    if not reference or PLACEHOLDER_REFERENCE_RE.match(reference):
        return False
    ke_match = KE_ID_RE.search(reference)
    if ke_match:
        return _ke_id_exists_on_disk(ke_match.group(0))
    file_match = OWNER_DECISIONS_FILE_RE.search(reference)
    if file_match:
        return _owner_decisions_file_exists(file_match.group(0))
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


# =====================================================================
# CATEGORY B: deterministic recovery (2026-08-03, UMR-20260803-025317-0c64 /
# UMR-20260803-025414-8274). See module docstring for the real incident and
# Owner decision this responds to.
# =====================================================================

CATEGORY_B_BLOCK_RE = re.compile(
    r"^\s*CATEGORY-B-DETERMINISTIC-RECOVERY:\s*\n((?:^[ \t]+\S.*\n?)+)",
    re.MULTILINE,
)
CATEGORY_B_FIELD_RE = re.compile(r"^[ \t]+([a-z_]+):\s*(.*)$")

CATEGORY_B_REQUIRED_FIELDS = (
    "repo", "sql_file", "governing_umr", "outage_evidence", "root_cause_evidence",
    "audit_match_evidence", "before_after_evidence", "rollback_path", "canonical_artifact",
)

UMR_ID_RE = re.compile(r"UMR-\d{8}-\d{6}-[0-9a-f]{4}", re.IGNORECASE)

# A real DDL statement opener that, unguarded, is not obviously safe to
# re-run: CREATE without IF NOT EXISTS, ALTER/DROP without IF EXISTS, ADD
# COLUMN without IF NOT EXISTS, etc. Deliberately mirrors the shape-classes
# already listed in DDL_KEYWORD_PATTERNS above rather than inventing new
# ones.
RISKY_DDL_OPENER_RE = re.compile(
    r"^\s*(CREATE\s+(?:UNIQUE\s+)?(?:OR\s+REPLACE\s+)?(?:MATERIALIZED\s+)?"
    r"(?:TABLE|INDEX|POLICY|TRIGGER|TYPE|SCHEMA|SEQUENCE|VIEW|FUNCTION)|"
    r"ALTER\s+(?:TABLE|FUNCTION)|"
    r"DROP\s+(?:TABLE|INDEX|POLICY|TRIGGER|TYPE|VIEW|FUNCTION)|"
    r"ADD\s+COLUMN|DROP\s+COLUMN|ADD\s+CONSTRAINT)\b",
    re.IGNORECASE | re.MULTILINE,
)

IDEMPOTENCY_GUARD_RE = re.compile(
    r"IF\s+NOT\s+EXISTS|IF\s+EXISTS|OR\s+REPLACE|ON\s+CONFLICT|DUPLICATE_OBJECT",
    re.IGNORECASE,
)

DO_BLOCK_RE = re.compile(r"DO\s+\$\$.*?END\s+\$\$\s*;", re.IGNORECASE | re.DOTALL)


def parse_category_b_block(text):
    """Extracts a `CATEGORY-B-DETERMINISTIC-RECOVERY:` evidence block from a
    dispatch prompt-file (or any text with the same shape). Returns a dict of
    whatever fields were present (not necessarily all of
    CATEGORY_B_REQUIRED_FIELDS -- that's checked separately, as its own
    condition, so a missing field is a real reported failure rather than a
    silent no-op), or None if no such block exists at all."""
    m = CATEGORY_B_BLOCK_RE.search(text)
    if not m:
        return None
    fields = {}
    for line in m.group(1).splitlines():
        fm = CATEGORY_B_FIELD_RE.match(line)
        if fm:
            fields[fm.group(1)] = fm.group(2).strip()
    return fields


def _resolve_repo_root(repo_name):
    """Real sibling-checkout resolution (REPOS_BASE_DIR/<repo_name>) -- returns
    None (not an exception) if the named repo isn't a real directory on this
    server, so callers can report a normal condition failure rather than
    crash."""
    if not repo_name or "/" in repo_name or repo_name in (".", ".."):
        return None
    candidate = os.path.join(REPOS_BASE_DIR, repo_name)
    return candidate if os.path.isdir(candidate) else None


def _git(repo_root, *args):
    """Runs git in repo_root, returns (returncode, stdout). Never raises --
    a git failure is real evidence a condition doesn't hold, not a crash."""
    try:
        proc = subprocess.run(
            ["git", *args], cwd=repo_root, capture_output=True, text=True, timeout=30,
        )
        return proc.returncode, proc.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def _read_repo_file(repo_root, rel_path, ref="origin/main"):
    """Real content of rel_path as it exists in ref's history (falls back to
    origin/master, then the working tree, since sibling repos on this server
    use both default-branch names -- see claude-control's own master vs
    compliance-tracker's main). Returns None if not found anywhere."""
    for candidate_ref in (ref, "origin/master", "origin/main"):
        rc, out = _git(repo_root, "cat-file", "-p", f"{candidate_ref}:{rel_path}")
        if rc == 0:
            return out
    working_path = os.path.join(repo_root, rel_path)
    if os.path.isfile(working_path):
        try:
            with open(working_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except OSError:
            return None
    return None


def _sql_file_previously_merged(repo_root, rel_path):
    """Condition 2 -- 'previously reviewed and merged, not new or unreviewed':
    real check is that this exact path has real commit history on the repo's
    own default branch (git log returns at least one commit reachable from
    origin/main or origin/master), not merely present in a working tree or on
    an unmerged branch."""
    for branch in ("origin/main", "origin/master"):
        rc, out = _git(repo_root, "log", branch, "--oneline", "--", rel_path)
        if rc == 0 and out.strip():
            return True, f"git log {branch} -- {rel_path}: {out.strip().splitlines()[0]!r}"
    return False, f"no commit history for {rel_path} on origin/main or origin/master"


def _is_idempotent_sql(sql_text):
    """Condition 3 -- 'genuinely idempotent, safe to run again without harm':
    a real, honest heuristic (documented limitation, same class as this
    module's other checks -- not a full SQL parser). DO $$ ... END $$; blocks
    are stripped first (Postgres's own idiom for wrapping a CREATE POLICY/etc.
    in an exception handler that swallows duplicate_object -- see this
    module's docstring for the real migration this pattern is drawn from);
    every remaining risky DDL opener must have an idempotency guard
    (IF NOT EXISTS / IF EXISTS / OR REPLACE / ON CONFLICT) within its own
    statement (naive but conservative semicolon-bounded split -- fails closed
    on anything ambiguous rather than assuming safety)."""
    guarded_blocks = DO_BLOCK_RE.findall(sql_text)
    remainder = DO_BLOCK_RE.sub("", sql_text)
    unguarded = []
    for statement in remainder.split(";"):
        if RISKY_DDL_OPENER_RE.search(statement) and not IDEMPOTENCY_GUARD_RE.search(statement):
            unguarded.append(statement.strip().splitlines()[0][:80])
    if unguarded:
        return False, f"{len(unguarded)} unguarded DDL statement(s) outside any DO $$ exception block: {unguarded}"
    return True, f"all risky DDL statements guarded (IF NOT EXISTS/IF EXISTS/OR REPLACE/ON CONFLICT), {len(guarded_blocks)} DO $$ exception block(s) also present"


def _citation_exists(repo_root, citation):
    """Generalizes is_real_reference()/_ke_id_exists_on_disk() to Category B's
    evidence fields, which may cite: a UMR id (existence-scanned the same way
    a KE id is), a `path#anchor` or bare `path` reference into the named
    repo's own ai-os/ tree (path must exist; anchor, if given, must appear
    literally inside it), or fall back to the same dated-free-text-note floor
    Category A uses. Same honest limitation as the rest of this module: this
    proves the citation is a real, findable record, not that its content
    actually substantiates the specific claim."""
    if not citation or PLACEHOLDER_REFERENCE_RE.match(citation.strip()):
        return False, "empty or placeholder citation"
    citation = citation.strip()
    umr_match = UMR_ID_RE.search(citation)
    if umr_match:
        repo_ai_os = os.path.join(repo_root, "ai-os")
        if os.path.isdir(repo_ai_os):
            for root, _dirs, files in os.walk(repo_ai_os):
                for name in files:
                    path = os.path.join(root, name)
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            if umr_match.group(0) in f.read():
                                return True, f"{umr_match.group(0)} found under {os.path.relpath(repo_ai_os, repo_root)}/"
                    except OSError:
                        continue
        return False, f"{umr_match.group(0)} not found anywhere under ai-os/"
    if "#" in citation:
        rel_path, anchor = citation.split("#", 1)
    else:
        rel_path, anchor = citation, None
    rel_path = rel_path.strip()
    full_path = os.path.join(repo_root, rel_path)
    if os.path.isfile(full_path):
        if not anchor:
            return True, f"{rel_path} exists"
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            return False, f"{rel_path} exists but could not be read"
        if anchor in content:
            return True, f"{rel_path} exists and contains anchor {anchor!r}"
        return False, f"{rel_path} exists but does not contain anchor {anchor!r}"
    ke_match = KE_ID_RE.search(citation)
    if ke_match:
        return _ke_id_exists_on_disk(ke_match.group(0)), f"KE-id existence check for {ke_match.group(0)}"
    if DATED_NOTE_RE.search(citation) and len(citation) >= MIN_DATED_NOTE_LENGTH:
        return True, "dated free-text note, format-only check (no record to look up)"
    return False, f"{rel_path!r} is not a real file/UMR-id/KE-id citation and not a sufficiently detailed dated note"


def check_category_b_recovery(evidence):
    """Evaluates the Owner's 10 real conditions (UMR-20260803-025317-0c64)
    against real, verifiable evidence -- never a narrated claim. `evidence` is
    the dict parse_category_b_block() returns (or an equivalent dict supplied
    directly for the retroactive/CLI --category-b-evidence path). Returns
    {"category_b_valid": bool, "conditions": [{"id", "description", "passed",
    "detail"}, ...]} -- every condition is reported, not just the first
    failure, so a rejection is fully specific about what's still missing.
    Fails closed: any condition this function cannot check (missing field,
    unresolvable repo, unreadable file) is reported as failed, never skipped
    or assumed true."""
    conditions = []

    def record(cid, description, passed, detail):
        conditions.append({"id": cid, "description": description, "passed": bool(passed), "detail": detail})

    missing = [f for f in CATEGORY_B_REQUIRED_FIELDS if not evidence.get(f)]
    if missing:
        record("0_evidence_complete", "All required evidence fields present",
                False, f"missing field(s): {missing}")
        return {"category_b_valid": False, "conditions": conditions}
    record("0_evidence_complete", "All required evidence fields present", True, "all fields present")

    repo_root = _resolve_repo_root(evidence["repo"])
    if not repo_root:
        record("0_repo_resolved", "Named repo is a real sibling checkout", False,
               f"repo={evidence['repo']!r} not found under {REPOS_BASE_DIR}")
        return {"category_b_valid": False, "conditions": conditions}
    record("0_repo_resolved", "Named repo is a real sibling checkout", True, repo_root)

    # 1. The SQL already exists in the repository.
    sql_text = _read_repo_file(repo_root, evidence["sql_file"])
    record("1_sql_exists", "SQL already exists in the repository", sql_text is not None,
           f"{evidence['sql_file']} {'found' if sql_text is not None else 'not found'} in {evidence['repo']}")

    # 2. The SQL was previously reviewed and merged, not new or unreviewed.
    merged_ok, merged_detail = (_sql_file_previously_merged(repo_root, evidence["sql_file"])
                                 if sql_text is not None else (False, "skipped, file not found (condition 1 failed)"))
    record("2_previously_merged", "SQL was previously reviewed and merged", merged_ok, merged_detail)

    # 3. The SQL is genuinely idempotent, safe to run again without harm.
    idem_ok, idem_detail = (_is_idempotent_sql(sql_text) if sql_text is not None
                             else (False, "skipped, file not found (condition 1 failed)"))
    record("3_idempotent", "SQL is genuinely idempotent, safe to rerun", idem_ok, idem_detail)

    # 4. The production issue is a verified real outage or Sev1 incident, not routine maintenance.
    outage_ok, outage_detail = _citation_exists(repo_root, evidence["outage_evidence"])
    record("4_real_outage", "Production issue is a verified real outage/Sev1, not routine maintenance",
           outage_ok, outage_detail)

    # 5. Root cause has been independently verified, not assumed.
    root_cause_ok, root_cause_detail = _citation_exists(repo_root, evidence["root_cause_evidence"])
    record("5_root_cause_verified", "Root cause independently verified, not assumed",
           root_cause_ok, root_cause_detail)

    # 6. An independent audit confirms the proposed live action matches the already-reviewed migration exactly.
    audit_ok, audit_detail = _citation_exists(repo_root, evidence["audit_match_evidence"])
    record("6_independent_audit_match", "Independent audit confirms exact match to the reviewed migration",
           audit_ok, audit_detail)

    # 7. The execution is fully logged under the real governing UMR.
    umr = evidence["governing_umr"]
    umr_format_ok = bool(UMR_ID_RE.fullmatch(umr.strip()))
    umr_exists_ok, umr_exists_detail = _citation_exists(repo_root, umr) if umr_format_ok else (False, "not a well-formed UMR id")
    record("7_umr_traceability", "Execution is fully logged under the real governing UMR",
           umr_format_ok and umr_exists_ok, umr_exists_detail if umr_format_ok else f"{umr!r} is not a well-formed UMR-YYYYMMDD-HHMMSS-xxxx id")

    # 8. Real before-and-after evidence is captured, not narrated.
    before_after_ok, before_after_detail = _citation_exists(repo_root, evidence["before_after_evidence"])
    record("8_before_after_evidence", "Real before/after evidence captured, not narrated",
           before_after_ok, before_after_detail)

    # 9. A real rollback path is documented.
    rollback_ok, rollback_detail = _citation_exists(repo_root, evidence["rollback_path"])
    record("9_rollback_documented", "A real rollback path is documented", rollback_ok, rollback_detail)

    # 10. A real canonical artifact is updated after execution completes.
    canonical_ok, canonical_detail = _citation_exists(repo_root, evidence["canonical_artifact"])
    record("10_canonical_artifact_updated", "Real canonical artifact is updated after execution completes",
           canonical_ok, canonical_detail)

    all_passed = all(c["passed"] for c in conditions)
    return {"category_b_valid": all_passed, "conditions": conditions}


def check_ddl_authorization(text):
    hits = find_ddl_references(text)
    if not hits:
        decision = emit_allow(
            source_gate=SOURCE_GATE, reason_code="no_ddl_language_found",
            detail="No DDL/DCL keyword or DDL-capable Supabase MCP tool name found in this prompt-file.",
        )
        return {"valid": True, "policy_decision": decision.to_dict()}

    reference = find_pre_approval(text)
    if reference:
        explanation = make_explanation(
            summary="Live DDL pre-approved by a real, verified citation.",
            reasoning=f"Matched DDL language ({', '.join(hits)}) but a valid PRE-APPROVED-LIVE-DDL citation ({reference}) was found and verified to exist.",
        )
        decision = emit_allow(
            source_gate=SOURCE_GATE, reason_code="ddl_pre_approved",
            detail=f"pre_approved_reference={reference}",
            explanation=explanation, evidence=hits,
        )
        return {
            "valid": True, "ddl_references_found": hits, "pre_approved_reference": reference,
            "policy_decision": decision.to_dict(),
        }

    # Category B: deterministic recovery, an ALTERNATIVE acceptance path to
    # Category A's PRE-APPROVED-LIVE-DDL citation above, not a replacement --
    # see module docstring. Only consulted once the Category A citation path
    # above has already failed to find a valid reference.
    category_b_evidence = parse_category_b_block(text)
    category_b_result = None
    if category_b_evidence is not None:
        category_b_result = check_category_b_recovery(category_b_evidence)
        if category_b_result["category_b_valid"]:
            explanation = make_explanation(
                summary="Live DDL authorized as a deterministic Category B recovery.",
                reasoning=(
                    f"Matched DDL language ({', '.join(hits)}); no Category A PRE-APPROVED-LIVE-DDL "
                    "citation was present, but a CATEGORY-B-DETERMINISTIC-RECOVERY evidence block was, "
                    "and all 10 of the Owner's deterministic conditions (UMR-20260803-025317-0c64) "
                    "verified true against real repo/task-record evidence -- no human/PM/AI judgment "
                    "call required for this class of action."
                ),
            )
            decision = emit_allow(
                source_gate=SOURCE_GATE, reason_code="category_b_deterministic_recovery",
                detail=json.dumps(category_b_result["conditions"], default=str),
                explanation=explanation, evidence=hits,
            )
            return {
                "valid": True, "ddl_references_found": hits, "category": "B",
                "category_b_conditions": category_b_result["conditions"],
                "policy_decision": decision.to_dict(),
            }

    explanation = make_explanation(
        summary="Live DDL language found with no valid pre-approval citation.",
        reasoning=(
            f"Matched DDL/DCL language ({', '.join(hits)}) and no PRE-APPROVED-LIVE-DDL: line cited a "
            "real, existing decision-log record or a sufficiently detailed dated note"
            + (", and the CATEGORY-B-DETERMINISTIC-RECOVERY evidence block present did not satisfy "
               "all 10 required conditions" if category_b_result is not None else "")
            + "."
        ),
        recommended_action=(
            "Remove the DDL instruction from SCOPE and open a migration PR for human review instead, "
            "or fix the specific failed Category B condition(s) reported below."
        ),
    )
    decision = emit_deny(
        source_gate=SOURCE_GATE, reason_code="ddl_authorization_required",
        detail=f"ddl_references_found={hits}", explanation=explanation, evidence=hits,
    )
    result = {
        "valid": False,
        "reason": (
            "ddl_authorization_required: this prompt-file references live-DDL-executing "
            f"language ({', '.join(hits)}) with no PRE-APPROVED-LIVE-DDL: citation" +
            (" and no CATEGORY-B-DETERMINISTIC-RECOVERY block that satisfies all 10 required "
             "conditions" if category_b_result is not None else "") + ". "
            "Supabase schema changes (Category A) are tier2-by-definition and must be held for "
            "human sign-off before a worker is ever dispatched to run them. Deterministic recovery "
            "of already-reviewed, already-merged, idempotent SQL (Category B) may instead be "
            "auto-authorized by this gate if all 10 of the Owner's conditions verify true -- this "
            "gate enforces both rules at dispatch time, not only at PR-merge time."
        ),
        "guidance": (
            "Category A: if the Owner has genuinely pre-approved this specific live DDL action out "
            "of band, add a line `PRE-APPROVED-LIVE-DDL: <real citation>` to this prompt-file -- a "
            "decision-log entry ID (KE-<date>-<time>-<hex>, or an "
            "OWNER_DECISIONS_NEEDED_<date>.yaml#<id> reference), or a dated approval note of "
            "meaningful length. A bare word like `yes` is not a citation and will not pass.\n"
            "Category B: if this is a deterministic recovery of already-reviewed/merged/idempotent "
            "SQL, add a `CATEGORY-B-DETERMINISTIC-RECOVERY:` block naming real, checkable evidence "
            "for all 10 conditions (repo, sql_file, governing_umr, outage_evidence, "
            "root_cause_evidence, audit_match_evidence, before_after_evidence, rollback_path, "
            "canonical_artifact) -- see the conditions breakdown below if a block was already "
            "present but failed.\n"
            "Otherwise, remove the DDL instruction from SCOPE and have the worker open a migration "
            "PR for human review instead, the same as every other Supabase schema change."
        ),
        "ddl_references_found": hits,
        "policy_decision": decision.to_dict(),
    }
    if category_b_result is not None:
        result["category_b_conditions"] = category_b_result["conditions"]
    return result


if __name__ == "__main__":
    # Standalone/retroactive Category B check: evaluates a real evidence JSON
    # file against the 10 conditions directly, independent of any prompt-file
    # dispatch flow -- used to test the policy against a past incident (see
    # module docstring's "Retroactive test" section) or to spot-check a
    # proposed evidence block before wiring it into a real prompt-file.
    if len(sys.argv) >= 3 and sys.argv[1] == "--category-b-evidence":
        with open(sys.argv[2]) as f:
            evidence = json.load(f)
        result = check_category_b_recovery(evidence)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if result.get("category_b_valid") else 1)

    if len(sys.argv) < 2:
        print(json.dumps({"valid": True, "note": "usage: ddl_authorization_check.py <prompt_file> | ddl_authorization_check.py --category-b-evidence <evidence.json>"}))
        sys.exit(0)
    with open(sys.argv[1]) as f:
        prompt_text = f.read()
    result = check_ddl_authorization(prompt_text)
    print(json.dumps(result))
    sys.exit(0 if result.get("valid") else 1)
