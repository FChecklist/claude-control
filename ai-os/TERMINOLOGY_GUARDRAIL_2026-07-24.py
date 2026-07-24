#!/usr/bin/env python3
"""
TERMINOLOGY_GUARDRAIL_2026-07-24.py -- Phase 0 DESIGN of the VERIDIAN
Terminology Standardization guardrail (task-20260724-070131,
instruction INS-20260724-070047-3a2d).

STATUS: designed + smoke-tested this phase, NOT wired into CI and NOT run
repo-wide yet -- see ai-os/TERMINOLOGY_STANDARDIZATION_PHASE_PLAN_2026-07-24.yaml
for when/how that happens. This phase's own CONSTRAINTS explicitly scope this
task to "guardrail design + smoke-test," not rollout.

WHAT IT DOES: scans a given file (or an inline prompt string) for hardcoded
literal values that match common "human example" shapes -- placeholder
company names (ABC/XYZ/Acme + Corp/Ltd/Pvt/LLP/Inc), placeholder person
names (John/Jane Doe/Smith), fake example email domains, bare ISO dates,
and India-specific compliance-domain literals (PAN, GSTIN patterns) that a
prompt/template author typed by hand instead of citing a real
<Entity.Attribute> placeholder from ai-os/VARIABLE_DICTIONARY_2026-07-24.yaml.
It also flags any <Entity.Attribute>-shaped token already in the text that is
NOT a placeholder registered in that dictionary (drift/typo detection).

WHAT IT DOES NOT DO (by design, this phase): auto-fix anything, suggest a
single "correct" replacement placeholder with confidence, or run outside the
files it is explicitly pointed at. Those are rollout-phase concerns.

PHASE 1 ADDITION (task-20260724-084040-phase1-terminology-dictionary-expansion),
per the phase plan's phase_1_dictionary_coverage_expansion scope: every finding
now carries a dictionary_gap_candidate boolean. If the finding's own line
mentions a real DATABASE_CATALOG.json table name that is NOT yet covered by
the dictionary this run loaded (i.e. outside its current TOP_N tier), the
finding is tagged dictionary_gap_candidate=true and
dictionary_gap_candidate_table/_entity name the uncovered table, instead of
silently offering no lead on which table to prioritize next. This is a plain
word-boundary substring match against real table names (not NLP/semantic), so
it is a coarse heuristic -- Phase 2's per-directory findings reports use its
frequency counts to prioritize which dictionary tier to grow next, not as a
precise auto-fix suggestion (that's Phase 4's --suggest-fix scope).

PHASE 4 ADDITION (task-20260724-143013-phase4-migrate-existing-hardcoded-exampl),
per the phase plan's phase_4_existing_hardcoded_example_migration scope item 1:
--suggest-fix. For each finding, this mode searches the loaded
VARIABLE_DICTIONARY_2026-07-24.yaml for a placeholder whose entity/attribute
plausibly matches the finding's surrounding code context (nearby identifiers,
file name, the matched category's expected attribute family -- e.g. a
placeholder_company_name finding looks for a "*.Name"-family attribute on an
entity whose name appears near the finding), and attaches a "suggested_fix"
object to the finding: the candidate placeholder token, its dictionary
example_value, a plain suggested_diff (old line -> new line with the literal
substring replaced by the placeholder token), and how the entity was matched
(context keyword vs. category-only fallback vs. no match at all). This is
intentionally a suggestion engine, not an autofix: --suggest-fix never writes
to any file, it only enriches the JSON findings report (and, in human-
readable mode, prints the suggested diff) for a human to review and apply
(or reject in favor of a permanent exemption-file entry) themselves. Matching
is a coarse keyword heuristic (same honesty class as the dictionary_gap_candidate
check above), not NLP/semantic -- a finding with no plausible entity match in
its surrounding context gets suggested_fix: null and a stated reason, rather
than a confident-looking wrong guess.

Run:
  python3 ai-os/TERMINOLOGY_GUARDRAIL_2026-07-24.py --file <path> [--file <path> ...] [--output <json_path>]
  python3 ai-os/TERMINOLOGY_GUARDRAIL_2026-07-24.py --string "some prompt text"
  python3 ai-os/TERMINOLOGY_GUARDRAIL_2026-07-24.py --file <path> --suggest-fix
Exit code: 0 if no findings, 1 if any findings (so it can gate CI once wired
in a later phase -- see the phase plan's ci_enforcement design note).
"""
import argparse
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    yaml = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DICTIONARY_PATH = os.path.join(SCRIPT_DIR, "VARIABLE_DICTIONARY_2026-07-24.yaml")
DEFAULT_CATALOG_PATH = "/opt/veridian/ai-os/DATABASE_CATALOG.json"

PLACEHOLDER_TOKEN_RE = re.compile(r"<[A-Z][A-Za-z0-9]*\.[A-Z][A-Za-z0-9]*>")

# Each pattern targets a concrete literal shape, never placeholder syntax
# itself (placeholders use <Entity.Attribute>, these patterns match plain
# text) -- so by construction any match here is a hardcoded literal, not a
# registered placeholder.
PATTERN_FAMILIES = [
    (
        "placeholder_company_name",
        re.compile(r"\b(ABC|XYZ|Acme|Foo|Bar)\s+(Corp\.?|Corporation|Pvt\.?\s*Ltd\.?|Private Limited|Ltd\.?|LLP|Inc\.?|Company)\b"),
        "Hardcoded placeholder-style company name -- replace with a registered <Entity.Attribute> "
        "placeholder (e.g. <Clients.Name>) instead of a literal example company.",
    ),
    (
        "placeholder_person_name",
        re.compile(r"\b(John|Jane)\s+(Doe|Smith)\b"),
        "Hardcoded placeholder-style person name -- replace with a registered <Entity.Attribute> "
        "placeholder (e.g. <Users.Name>) instead of a literal example person.",
    ),
    (
        "placeholder_email_domain",
        re.compile(r"\b[a-zA-Z0-9_.+-]+@(example|acme|test|foo|sample)\.(com|org|net)\b", re.IGNORECASE),
        "Hardcoded placeholder-style email address -- replace with a registered <Entity.Attribute> "
        "placeholder (e.g. <Users.Email>) instead of a literal example address.",
    ),
    (
        "hardcoded_iso_date",
        re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
        "Bare ISO date literal -- if this is example/sample data (not a real changelog/version/task-id "
        "date), replace with a registered date-typed <Entity.Attribute> placeholder.",
    ),
    (
        "indian_pan_literal",
        re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
        "Literal shaped like an Indian PAN number -- replace with a registered <Entity.Attribute> "
        "placeholder rather than a hand-typed example PAN.",
    ),
    (
        "indian_gstin_literal",
        re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b"),
        "Literal shaped like an Indian GSTIN -- replace with a registered <Entity.Attribute> placeholder "
        "rather than a hand-typed example GSTIN.",
    ),
]

# PHASE 4 ADDITION -- --suggest-fix support. Each finding category maps to the
# family of dictionary attribute names that would plausibly replace it (e.g. a
# placeholder_company_name literal wants a "*Name" attribute, not a "*Email"
# one). Order matters: earlier substrings are tried first.
CATEGORY_ATTRIBUTE_FAMILIES = {
    "placeholder_company_name": ["name"],
    "placeholder_person_name": ["name"],
    "placeholder_email_domain": ["email"],
    "indian_pan_literal": ["pan"],
    "indian_gstin_literal": ["gstin", "gst"],
    "hardcoded_iso_date": ["createdat", "updatedat", "duedate", "deadline", "date", "at"],
}

_CAMEL_SPLIT_RE = re.compile(r"[A-Z][a-z0-9]*|[a-z0-9]+")
_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def _entity_keywords(entity_name):
    """Split an entity name like 'CrmAccounts' into lowercase context
    keywords ('crm', 'accounts') a human would plausibly write near code that
    deals with that entity. Words shorter than 3 chars are dropped as too
    generic to match on (e.g. 'Id')."""
    return [w.lower() for w in _CAMEL_SPLIT_RE.findall(entity_name) if len(w) >= 3]


def load_dictionary_entries(dictionary_path):
    """Full entry list (placeholder/entity/attribute/example_value/etc.) from
    VARIABLE_DICTIONARY_2026-07-24.yaml, for --suggest-fix's entity/attribute
    matching. Returns [] if the dictionary can't be loaded (same soft-fail
    posture as load_registered_placeholders)."""
    if yaml is None or not os.path.isfile(dictionary_path):
        return []
    with open(dictionary_path) as f:
        doc = yaml.safe_load(f)
    return doc.get("entries", [])


def build_context_words(source_label):
    """Context keyword source for entity matching: the scanned file's own
    basename only (e.g. crm-accounts-service.ts -> {"crm", "accounts",
    "service", "ts"}), deliberately NOT surrounding prose lines. This
    codebase names service/route files after the entity they own
    (crm-accounts-service.ts, esignature-service.ts, ...), which is a
    precise signal -- prose in nearby comments is not: this repo's own
    compliance-domain vocabulary (audit/risk/vendor/client/task) overlaps so
    heavily with real entity-name components that a prose window matched
    confidently-wrong entities in testing (e.g. an unrelated "Risk
    assessment" comment line matching VendorRiskProfiles). Filename-only
    trades recall for precision, matching this script's own "no plausible
    match beats a confident wrong one" design note."""
    return set(w.lower() for w in _WORD_RE.findall(os.path.basename(source_label)))


def suggest_fix_for_finding(finding, dictionary_entries, context_words):
    """Best-effort <Entity.Attribute> suggestion for one finding. Returns a
    dict always (never None) so every finding gets an explicit disposition
    lead in --suggest-fix output, even when no match is found."""
    category = finding["category"]
    attr_families = CATEGORY_ATTRIBUTE_FAMILIES.get(category)
    if not attr_families or category == "unregistered_placeholder_token":
        return {
            "placeholder": None,
            "example_value": None,
            "suggested_diff": None,
            "match_basis": "none",
            "reason": f"category '{category}' has no defined attribute-family mapping for suggest-fix.",
        }

    candidates_by_family = {}
    for entry in dictionary_entries:
        attr_lower = entry["attribute"].lower()
        for rank, family in enumerate(attr_families):
            if family in attr_lower:
                candidates_by_family.setdefault(rank, []).append(entry)
                break

    best = None
    best_score = -1
    for family_rank in sorted(candidates_by_family):
        for entry in candidates_by_family[family_rank]:
            keywords = _entity_keywords(entry["entity"])
            if not keywords or not all(kw in context_words for kw in keywords):
                continue  # require EVERY keyword part of a multi-word entity to match -- a
                          # partial hit (e.g. just "risk" out of "vendor"+"risk"+"profiles")
                          # is exactly the noisy false-positive class this heuristic must avoid.
            score = len(keywords) * 100 - family_rank  # more/longer entity name -> more specific match
            if score > best_score:
                best_score = score
                best = entry
        if best is not None:
            break  # a filename-matched entity in this family rank beats trying looser families

    if best is None:
        return {
            "placeholder": None,
            "example_value": None,
            "suggested_diff": None,
            "match_basis": "none",
            "reason": "no dictionary entity's full name matched this file's own name -- needs a "
                      "human to pick the right entity, or this may not be migratable example "
                      "data at all (e.g. a changelog date, a protocol-version literal, a "
                      "format-shape description, or static UI/demo content rather than "
                      "AI-prompt/template text).",
        }

    old_text = finding["matched_text"]
    new_line = finding["line_excerpt"].replace(old_text, best["placeholder"], 1)
    return {
        "placeholder": best["placeholder"],
        "example_value": best["example_value"],
        "suggested_diff": {
            "old_line": finding["line_excerpt"],
            "new_line": new_line,
        },
        "match_basis": "filename_keyword",
        "reason": f"entity '{best['entity']}' name fully matched this file's own name; "
                  f"attribute '{best['attribute']}' matched category '{category}''s expected "
                  f"attribute family.",
    }


def load_registered_placeholders(dictionary_path):
    if yaml is None:
        print(f"WARNING: pyyaml not available, cannot load {dictionary_path} -- "
              f"unregistered-placeholder-token check disabled", file=sys.stderr)
        return set(), set()
    if not os.path.isfile(dictionary_path):
        print(f"WARNING: dictionary not found at {dictionary_path} -- "
              f"unregistered-placeholder-token check disabled", file=sys.stderr)
        return set(), set()
    with open(dictionary_path) as f:
        doc = yaml.safe_load(f)
    entries = doc.get("entries", [])
    registered_placeholders = {e["placeholder"] for e in entries}
    covered_tables = {e["source_table"].split(".")[-1] for e in entries}
    return registered_placeholders, covered_tables


def build_gap_candidate_regex(catalog_path, covered_tables):
    """Real DATABASE_CATALOG.json table names not yet covered by the dictionary
    this run loaded, compiled into one word-boundary alternation regex so
    scan_text can flag findings whose line mentions one of them -- see this
    script's own PHASE 1 ADDITION module-docstring note for the heuristic's
    scope and limits."""
    if not os.path.isfile(catalog_path):
        print(f"WARNING: DATABASE_CATALOG.json not found at {catalog_path} -- "
              f"dictionary_gap_candidate check disabled", file=sys.stderr)
        return None, {}
    with open(catalog_path) as f:
        catalog = json.load(f)
    entity_by_table = {}
    for t in catalog.get("tables", []):
        tn = t["table_name"]
        entity_by_table[tn] = "".join(part[:1].upper() + part[1:] for part in tn.split("_") if part)
    uncovered = [tn for tn in entity_by_table if tn not in covered_tables]
    if not uncovered:
        return None, entity_by_table
    uncovered_sorted = sorted(uncovered, key=len, reverse=True)
    pattern = r"\b(" + "|".join(re.escape(tn) for tn in uncovered_sorted) + r")\b"
    return re.compile(pattern, re.IGNORECASE), entity_by_table


def find_gap_candidate(line, gap_regex, entity_by_table):
    if gap_regex is None:
        return None
    m = gap_regex.search(line)
    if not m:
        return None
    table_name = m.group(1).lower()
    return table_name, entity_by_table.get(table_name)


def scan_text(text, registered_placeholders, source_label="<inline>", gap_regex=None, entity_by_table=None):
    entity_by_table = entity_by_table or {}
    findings = []
    lines = text.splitlines()
    for lineno, line in enumerate(lines, start=1):
        for category, pattern, note in PATTERN_FAMILIES:
            for m in pattern.finditer(line):
                gap = find_gap_candidate(line, gap_regex, entity_by_table)
                findings.append({
                    "source": source_label,
                    "line": lineno,
                    "column": m.start() + 1,
                    "category": category,
                    "matched_text": m.group(0),
                    "note": note,
                    "line_excerpt": line.strip()[:160],
                    "dictionary_gap_candidate": gap is not None,
                    "dictionary_gap_candidate_table": gap[0] if gap else None,
                    "dictionary_gap_candidate_entity": gap[1] if gap else None,
                })
        for m in PLACEHOLDER_TOKEN_RE.finditer(line):
            token = m.group(0)
            if token not in registered_placeholders:
                gap = find_gap_candidate(line, gap_regex, entity_by_table)
                findings.append({
                    "source": source_label,
                    "line": lineno,
                    "column": m.start() + 1,
                    "category": "unregistered_placeholder_token",
                    "matched_text": token,
                    "note": f"'{token}' looks like an <Entity.Attribute> placeholder but is not registered "
                            f"in ai-os/VARIABLE_DICTIONARY_2026-07-24.yaml -- typo, or the dictionary needs "
                            f"a new entry.",
                    "line_excerpt": line.strip()[:160],
                    "dictionary_gap_candidate": gap is not None,
                    "dictionary_gap_candidate_table": gap[0] if gap else None,
                    "dictionary_gap_candidate_entity": gap[1] if gap else None,
                })
    return findings


def scan_file(path, registered_placeholders, gap_regex=None, entity_by_table=None):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    return scan_text(text, registered_placeholders, source_label=path, gap_regex=gap_regex, entity_by_table=entity_by_table)


def apply_suggest_fix(findings, dictionary_entries):
    """Mutates `findings` in place, attaching a "suggested_fix" object to
    each one, keyed off each finding's own "source" file name (see
    build_context_words's docstring for why filename, not surrounding
    prose)."""
    context_words_cache = {}
    for finding in findings:
        source = finding["source"]
        if source not in context_words_cache:
            context_words_cache[source] = build_context_words(source)
        finding["suggested_fix"] = suggest_fix_for_finding(
            finding, dictionary_entries, context_words_cache[source]
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", action="append", default=[], help="file to scan (repeatable)")
    parser.add_argument("--file-list", default=None,
                         help="path to a text file with one file-to-scan path per line (blank lines and "
                              "#-comments ignored) -- for wide directory sweeps without a --file per file")
    parser.add_argument("--string", default=None, help="inline prompt string to scan")
    parser.add_argument("--dictionary", default=DEFAULT_DICTIONARY_PATH, help="path to VARIABLE_DICTIONARY yaml")
    parser.add_argument("--catalog", default=DEFAULT_CATALOG_PATH,
                         help="path to DATABASE_CATALOG.json, for the dictionary_gap_candidate check")
    parser.add_argument("--output", default=None, help="write JSON findings report to this path")
    parser.add_argument("--suggest-fix", action="store_true",
                         help="attach a suggested <Entity.Attribute> replacement + diff to each finding "
                              "(never writes to any file -- for human review only, see this script's own "
                              "PHASE 4 ADDITION module-docstring note)")
    args = parser.parse_args()

    files = list(args.file)
    if args.file_list:
        with open(args.file_list) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    files.append(line)

    if not files and not args.string:
        parser.error("provide at least one --file, --file-list, or --string")

    registered_placeholders, covered_tables = load_registered_placeholders(args.dictionary)
    gap_regex, entity_by_table = build_gap_candidate_regex(args.catalog, covered_tables)

    all_findings = []
    files_scanned = []
    if args.string is not None:
        all_findings.extend(scan_text(args.string, registered_placeholders, gap_regex=gap_regex, entity_by_table=entity_by_table))
    for path in files:
        if not os.path.isfile(path):
            print(f"WARNING: file not found, skipping: {path}", file=sys.stderr)
            continue
        files_scanned.append(path)
        all_findings.extend(scan_file(path, registered_placeholders, gap_regex=gap_regex, entity_by_table=entity_by_table))

    if args.suggest_fix:
        dictionary_entries = load_dictionary_entries(args.dictionary)
        apply_suggest_fix(all_findings, dictionary_entries)

    by_category = {}
    for f in all_findings:
        by_category[f["category"]] = by_category.get(f["category"], 0) + 1
    gap_candidate_count = sum(1 for f in all_findings if f["dictionary_gap_candidate"])
    gap_candidate_tables = {}
    for f in all_findings:
        if f["dictionary_gap_candidate"]:
            t = f["dictionary_gap_candidate_table"]
            gap_candidate_tables[t] = gap_candidate_tables.get(t, 0) + 1

    report = {
        "meta": {
            "script": "ai-os/TERMINOLOGY_GUARDRAIL_2026-07-24.py",
            "status": "phase_1_wider_rollout_run_not_yet_ci_wired",
            "dictionary_used": args.dictionary,
            "registered_placeholder_count": len(registered_placeholders),
            "dictionary_covered_table_count": len(covered_tables),
            "catalog_used": args.catalog,
            "gap_candidate_check_enabled": gap_regex is not None,
            "files_scanned": files_scanned,
            "files_scanned_count": len(files_scanned),
            "inline_string_scanned": args.string is not None,
            "suggest_fix_enabled": args.suggest_fix,
        },
        "summary": {
            "total_findings": len(all_findings),
            "findings_by_category": by_category,
            "dictionary_gap_candidate_findings": gap_candidate_count,
            "dictionary_gap_candidate_tables": gap_candidate_tables,
        },
        "findings": all_findings,
    }

    print(json.dumps(report, indent=2))
    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Wrote {args.output}", file=sys.stderr)

    sys.exit(1 if all_findings else 0)


if __name__ == "__main__":
    main()
