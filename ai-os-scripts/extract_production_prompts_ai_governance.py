#!/usr/bin/env python3
"""VERIDIAN Auditor Engine -- Phase 6, ai-governance domain: extracts the
real, currently-in-production system prompt text for a named, bounded set
of compliance-tracker LLM call sites, directly from the real drizzle
migration SQL that seeds `compliance.prompt_versions` -- the actual source
of truth `resolvePromptTemplate()` reads at runtime (confirmed via a live
read of src/lib/services/crm-service.ts/construction-ai-service.ts, which
all call `await resolvePromptTemplate("<template_key>")` rather than
inlining prompt text in TypeScript).

Same "extract from the real source, don't hand-copy" discipline as Phase 2's
extract_drizzle_column_comments.py. Every real prompt-version migration this
task found uses one of two real SQL shapes:
  (a) a plain `INSERT ... SELECT id, <version>, $tpl$...$tpl$, 'production'
      FROM compliance.prompt_templates WHERE template_key = '<key>'` (e.g.
      0065_wave75_crm_intelligence.sql, 0100_gst_reconciliation_engine.sql,
      0105_wave123_construction_ai_prompts.sql)
  (b) a PL/pgSQL DO block that first demotes the prior 'production'-labeled
      row (`UPDATE ... SET label = NULL WHERE label = 'production'`) then
      inserts a new version labeled 'production' (e.g.
      0238_ai_explainability_gap_closure.sql, real prompt version BUMPS).
Both shapes place the dollar-quoted content block adjacent to (before or
after) a `template_key = '<key>'` literal -- this script finds every
dollar-quoted block in every drizzle/*.sql file, resolves the nearest
template_key reference (search window each direction), and the label that
immediately follows the block's own closing delimiter. Files are scanned in
filename-sorted (== migration-chronological, VERIDIAN's own numeric-prefix
convention) order, so a later file's demote-then-insert naturally overrides
an earlier file's 'production' row for the same template_key, exactly
matching what a live `SELECT ... WHERE label = 'production'` query against
the real Postgres table would return -- this script has no DB connection,
so this ordering rule is how it reproduces that result deterministically
from the SQL alone.

Bounded scope (named explicitly, not silently narrowed): the 5 template_keys
below are VERIDIAN's real LLM-scoring/report/risk-assessment surfaces named
in ai-os/AI_GOVERNANCE_REVIEW_2026-07-24.yaml's own findings (GOV-AI-001/002/003)
-- construction.estimate_progress_from_photo (vision/image input) and
construction.discuss / crm chat-style prompts are out of this bounded set,
same "representative sub-tree, not exhaustive" discipline Phase 2 used for
its OpenAPI docs.

Usage:
    python3 extract_production_prompts_ai_governance.py [--dry-run]
"""
import argparse
import glob
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(_HERE, "..")
DRIZZLE_DIR = "/opt/veridian/repos/compliance-tracker/drizzle"
OUT_DIR = os.path.join(REPO_ROOT, "ai-os", "promptfoo", "prompts")

TARGET_TEMPLATE_KEYS = [
    "crm_intelligence.score_lead",
    "crm_intelligence.analyze_opportunity",
    "gst.ai_review_report",
    "construction.detect_budget_schedule_risk",
    "construction.generate_progress_summary",
]

_BLOCK_RE = re.compile(r"\$(tpl|PROMPT)\$(.*?)\$\1\$", re.S)
_LABEL_AFTER_RE = re.compile(r"^\s*,\s*'([a-zA-Z_]+)'")
_TEMPLATE_KEY_RE = re.compile(r"template_key\s*=\s*'([\w.]+)'")
_SEARCH_WINDOW = 1200


def _nearest_template_key(text, block_start, block_end):
    """A `template_key = '<key>'` literal BEFORE the block always wins over
    one found after, even if physically closer -- real SQL-shape reason,
    not an arbitrary tie-break: shape (b)'s PL/pgSQL DO block scopes each
    INSERT by a `SELECT id INTO tpl_id ... WHERE template_key = '<key>'`
    line that precedes it (the actual owning WHERE clause), while a
    template_key appearing shortly AFTER a block in that same shape belongs
    to the NEXT, unrelated tpl_id-reassignment statement -- despite
    sometimes being nearer in raw character distance. Shape (a)'s plain
    `SELECT id, <v>, $tpl$...$tpl$ FROM ... WHERE template_key = '<key>'`
    has no real 'before' match in range (the only earlier template_key-like
    text is a `('<key>', ...)` VALUES tuple, which this regex deliberately
    does not match), so it correctly falls through to 'after' unaffected."""
    before = text[max(0, block_start - _SEARCH_WINDOW):block_start]
    after = text[block_end:block_end + _SEARCH_WINDOW]
    # A 'before' match only counts if its own owning statement/scope hasn't
    # already closed before this block starts. Real markers of "this
    # reference's scope is done, it belongs to an earlier block": shape
    # (a)'s plain `INSERT ... SELECT ... FROM ... WHERE template_key = 'X'
    # ON CONFLICT (...) DO NOTHING;` closes with the literal `ON CONFLICT`
    # idiom; shape (b)'s PL/pgSQL `IF tpl_id IS NOT NULL THEN ... END IF;`
    # closes each template_key's own reassignment scope with `END IF`.
    # Neither idiom appears between a genuinely-owning template_key
    # reference and its own block (both statements are internally ';'
    # separated -- shape (b)'s own `SELECT id INTO tpl_id ...;` line ends
    # in ';' before its sibling UPDATE/INSERT statements in the SAME scope,
    # so ';' alone is not a valid discriminator, unlike ON CONFLICT/END IF).
    for cand in reversed(list(_TEMPLATE_KEY_RE.finditer(before))):
        gap = before[cand.end():]
        if "ON CONFLICT" not in gap and "END IF" not in gap:
            return cand.group(1)
    m_after = _TEMPLATE_KEY_RE.search(after)
    if m_after:
        return m_after.group(1)
    return None


def extract_all():
    """Returns {template_key: {"content": str, "label": str|None, "source_file": str, "source_line": int}}
    keeping only the LAST occurrence per template_key in filename-sorted order
    (see module docstring for why last-wins reproduces the real 'production' row)."""
    found = {}
    files = sorted(glob.glob(os.path.join(DRIZZLE_DIR, "*.sql")))
    for path in files:
        with open(path, "r") as f:
            text = f.read()
        for m in _BLOCK_RE.finditer(text):
            content = m.group(2)
            tail = text[m.end():m.end() + 200]
            label_m = _LABEL_AFTER_RE.match(tail)
            label = label_m.group(1) if label_m else None
            tkey = _nearest_template_key(text, m.start(), m.end())
            if tkey not in TARGET_TEMPLATE_KEYS:
                continue
            line_no = text.count("\n", 0, m.start()) + 1
            found[tkey] = {
                "content": content.strip(),
                "label": label,
                "source_file": os.path.relpath(path, "/opt/veridian/repos/compliance-tracker"),
                "source_line": line_no,
            }
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    found = extract_all()
    missing = [k for k in TARGET_TEMPLATE_KEYS if k not in found]
    not_production = {k: v["label"] for k, v in found.items() if v["label"] != "production"}
    if missing:
        print(json.dumps({"ok": False, "error": f"template_key(s) not found in any drizzle migration: {missing}"}, indent=2))
        return 2
    if not_production:
        print(json.dumps({"ok": False, "error": f"resolved content is not label='production' for: {not_production} "
                                                  f"(real drift -- re-check TARGET_TEMPLATE_KEYS / migration ordering)"}, indent=2))
        return 2

    manifest = {}
    if not args.dry_run:
        os.makedirs(OUT_DIR, exist_ok=True)
    for tkey, row in found.items():
        fname = tkey.replace(".", "_") + ".txt"
        out_path = os.path.join(OUT_DIR, fname)
        if not args.dry_run:
            with open(out_path, "w") as f:
                f.write(row["content"] + "\n")
        manifest[tkey] = {
            "prompt_file": f"ai-os/promptfoo/prompts/{fname}",
            "source": f"compliance-tracker/{row['source_file']}:{row['source_line']}",
            "label": row["label"],
            "content_chars": len(row["content"]),
        }

    manifest_path = os.path.join(OUT_DIR, "MANIFEST.json")
    if not args.dry_run:
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

    print(json.dumps({"ok": True, "extracted": manifest, "dry_run": args.dry_run}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
