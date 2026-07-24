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

Run:
  python3 ai-os/TERMINOLOGY_GUARDRAIL_2026-07-24.py --file <path> [--file <path> ...] [--output <json_path>]
  python3 ai-os/TERMINOLOGY_GUARDRAIL_2026-07-24.py --string "some prompt text"
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


def load_registered_placeholders(dictionary_path):
    if yaml is None:
        print(f"WARNING: pyyaml not available, cannot load {dictionary_path} -- "
              f"unregistered-placeholder-token check disabled", file=sys.stderr)
        return set()
    if not os.path.isfile(dictionary_path):
        print(f"WARNING: dictionary not found at {dictionary_path} -- "
              f"unregistered-placeholder-token check disabled", file=sys.stderr)
        return set()
    with open(dictionary_path) as f:
        doc = yaml.safe_load(f)
    return {e["placeholder"] for e in doc.get("entries", [])}


def scan_text(text, registered_placeholders, source_label="<inline>"):
    findings = []
    lines = text.splitlines()
    for lineno, line in enumerate(lines, start=1):
        for category, pattern, note in PATTERN_FAMILIES:
            for m in pattern.finditer(line):
                findings.append({
                    "source": source_label,
                    "line": lineno,
                    "column": m.start() + 1,
                    "category": category,
                    "matched_text": m.group(0),
                    "note": note,
                    "line_excerpt": line.strip()[:160],
                })
        for m in PLACEHOLDER_TOKEN_RE.finditer(line):
            token = m.group(0)
            if token not in registered_placeholders:
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
                })
    return findings


def scan_file(path, registered_placeholders):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    return scan_text(text, registered_placeholders, source_label=path)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", action="append", default=[], help="file to scan (repeatable)")
    parser.add_argument("--string", default=None, help="inline prompt string to scan")
    parser.add_argument("--dictionary", default=DEFAULT_DICTIONARY_PATH, help="path to VARIABLE_DICTIONARY yaml")
    parser.add_argument("--output", default=None, help="write JSON findings report to this path")
    args = parser.parse_args()

    if not args.file and not args.string:
        parser.error("provide at least one --file or --string")

    registered_placeholders = load_registered_placeholders(args.dictionary)

    all_findings = []
    files_scanned = []
    if args.string is not None:
        all_findings.extend(scan_text(args.string, registered_placeholders))
    for path in args.file:
        if not os.path.isfile(path):
            print(f"WARNING: file not found, skipping: {path}", file=sys.stderr)
            continue
        files_scanned.append(path)
        all_findings.extend(scan_file(path, registered_placeholders))

    by_category = {}
    for f in all_findings:
        by_category[f["category"]] = by_category.get(f["category"], 0) + 1

    report = {
        "meta": {
            "script": "ai-os/TERMINOLOGY_GUARDRAIL_2026-07-24.py",
            "status": "designed_and_smoke_tested_not_yet_rolled_out_or_ci_wired",
            "dictionary_used": args.dictionary,
            "registered_placeholder_count": len(registered_placeholders),
            "files_scanned": files_scanned,
            "inline_string_scanned": args.string is not None,
        },
        "summary": {
            "total_findings": len(all_findings),
            "findings_by_category": by_category,
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
