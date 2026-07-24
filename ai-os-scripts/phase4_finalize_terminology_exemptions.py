#!/usr/bin/env python3
"""
phase4_finalize_terminology_exemptions.py -- Phase 4 (task-20260724-143013-
phase4-migrate-existing-hardcoded-exampl, ai-os/TERMINOLOGY_STANDARDIZATION_PHASE_PLAN_2026-07-24.yaml
phase_4_existing_hardcoded_example_migration) closeout tool for
compliance-tracker's ai-os/registry/terminology-guardrail-exemptions.yaml.

WHAT THIS DOES: Phase 2's baseline grandfathered every then-existing finding
into this file as a count-ratchet "reason: pending Phase 4 migration"
placeholder. This script gives each finding a REAL Phase 4 disposition --
either (a) why it was fixed in code this phase (removed from
findings_by_category entirely), or (b) why it is a permanent exemption
(never a migration target, with a concrete falsifiable reason), per this
phase's own scope item 2.

TWO MODES:
  --exemptions-file <path>
    In-place mode: rewrites each existing entry's `reason` field using the
    same count already recorded (Phase 2's frozen baseline number). Use this
    to preserve the exact historical baseline count unchanged.
  --from-scan <report.json> [<report.json> ...] --exemptions-file <path>
    Regenerate mode: rebuilds the entire exemptions: list from fresh
    TERMINOLOGY_GUARDRAIL_2026-07-24.py JSON findings reports (current repo
    state), grouping by (file, category). Use this when the current
    repo has drifted from Phase 2's baseline (e.g. new changelog-date
        comments added by unrelated commits since then) -- the CI ratchet's
    recorded max must reflect CURRENT reality or it spuriously fails on
    pre-existing (just not Phase-2-dated) debt in any file a later PR
    happens to touch. Phase 4's migration_completion_pct metric still uses
    Phase 2's frozen 488 as its own denominator regardless of which mode
    produced the file -- see this task's PROGRESS.md for that reconciliation.

Every reason below reflects real investigation performed this phase, not
guesswork -- see this task's own PROGRESS.md for how each category was
verified (grep for non-comment/non-changelog instances, then read each one).

Run:
  python3 ai-os-scripts/phase4_finalize_terminology_exemptions.py --exemptions-file <path>
  python3 ai-os-scripts/phase4_finalize_terminology_exemptions.py --exemptions-file <path> --from-scan <report.json> ...
Rewrites the file in place; prints a per-category disposition summary.
"""
import argparse
import json
import os
import re
import sys

ENTRY_RE = re.compile(
    r"^  - file: (?P<file>.+)\n"
    r"    reason: \"(?P<reason>.*)\"\n"
    r"    findings_by_category:\n"
    r"(?P<categories>(?:      \S+: \d+\n)+)",
    re.MULTILINE,
)
CATEGORY_LINE_RE = re.compile(r"^      (?P<category>\S+): (?P<count>\d+)$", re.MULTILINE)
CLASSIFICATION_RE = re.compile(r"\((?P<slug>src-[a-z-]+) \((?P<classification>[a-z_]+)\)")

SEED_FIXTURE_REASON = (
    "Phase 4 finalized (2026-07-24): permanent exemption per Phase 2's own directory "
    "classification (task-20260724-115921-phase2-directory-scoped-guardrail-rollout) -- "
    "src/db/seed.ts + *.test.ts local-dev/test fixture example data is explicitly out of "
    "scope for placeholder migration (exercises local dev/test flows, not AI prompt/template "
    "authoring). {count} pre-existing finding(s) reviewed and closed as out-of-scope, not "
    "migrated."
)

HARDCODED_DATE_REASON = (
    "Phase 4 finalized (2026-07-24): permanent exemption -- confirmed false positive on "
    "direct read. The hardcoded_iso_date pattern is a bare ISO-date-shape regex with no "
    "comment/string-literal distinction; every non-comment instance in this file was "
    "individually verified this phase (changelog/gap-closure/commit-date comments, external "
    "API/protocol version-literal constants such as Anthropic's 'anthropic-version' header "
    "or MCP's 'protocolVersion', or an Owner-decision-date reference in a log string) -- none "
    "are human example/sample data. {count} pre-existing finding(s) reviewed and closed, not "
    "migrated."
)

# File-specific overrides where the blanket per-category reason above doesn't apply --
# either a distinct false-positive shape, or a real code fix landed this phase.
FILE_OVERRIDES = {
    ("src/lib/guardrail-registrations.ts", "indian_pan_literal"): {
        "action": "exempt",
        "reason": (
            "Phase 4 finalized (2026-07-24): permanent exemption -- confirmed false positive on "
            "direct read. 'AAAAA9999A' is the PAN format shape spelled out inside a validation-"
            "guidance error message (explaining the expected regex shape to whoever reads the "
            "error), not a hand-typed example PAN value. Not a migration target."
        ),
    },
    ("src/lib/orchestra-mock-data.ts", "placeholder_company_name"): {
        "action": "exempt",
        "reason": (
            "Phase 4 finalized (2026-07-24): permanent exemption -- confirmed out of this "
            "guardrail's actual scope on direct read. orchestra-mock-data.ts is static UI "
            "preview/demo content for the AI Orchestra dashboard (see this file's own header "
            "comment: preview data, 'None of this is backed by a real table yet'), not an AI "
            "prompt/template. <Entity.Attribute> placeholder syntax is for prompt-template "
            "substitution and would render literally as on-screen text here (e.g. a user would "
            "see the literal string '<Clients.Name>'), which would be wrong. 'ABC Corp'/'XYZ "
            "Ltd' are demo-only company names for a preview dashboard, not hardcoded examples "
            "in prompt/template authoring, despite matching this category's literal-shape "
            "regex. Not a migration target."
        ),
    },
    ("src/lib/services/communication-drafting-service.ts", "placeholder_company_name"): {
        "action": "fixed",
        "note": (
            "Fixed in code this phase: the JSDoc-style inline comment's illustrative example "
            "('weekly status update for the ABC Corp GST filing') now cites the registered "
            "<Clients.Name> placeholder instead of a hand-typed example company name."
        ),
    },
    ("src/lib/services/crm-accounts-service.ts", "placeholder_company_name"): {
        "action": "fixed",
        "note": (
            "Fixed in code this phase: the JSDoc example (two 'Acme Corp' rows) now cites "
            "the registered <CrmAccounts.Name> placeholder instead of a hand-typed example "
            "company name -- --suggest-fix's own filename-keyword match (CrmAccounts <-> "
            "crm-accounts-service.ts) confirmed this is the right entity."
        ),
    },
}


def classify(reason):
    m = CLASSIFICATION_RE.search(reason)
    if not m:
        return None, None
    return m.group("slug"), m.group("classification")


def classify_by_path(file_path):
    """Same 4-directory Phase 2 classification, derived straight from the
    file path -- used in --from-scan mode where there's no pre-existing
    `reason` string to read the classification back out of."""
    if file_path == "src/db/seed.ts" or file_path.endswith(".test.ts") or file_path.endswith(".test.tsx"):
        return "src-seed-and-test-fixtures", "exemption_candidate"
    if file_path.startswith("src/lib/services/"):
        return "src-lib-services", "required_fix_candidate"
    if file_path.startswith("src/app/api/"):
        return "src-app-api", "required_fix_candidate"
    if file_path.startswith("src/lib/"):
        return "src-lib-toplevel", "required_fix_candidate"
    raise ValueError(f"{file_path!r} doesn't match any of Phase 2's 4 directory patterns -- "
                      f"this scan report includes a file outside this phase's known scope.")


def generate_from_scan(report_paths, repo_root, summary):
    """Aggregate fresh guardrail findings (current repo state) into
    (file, category) -> count, then apply the same disposition rules as
    in-place mode. repo_root strips the report's absolute source paths back
    to repo-relative, matching the exemptions file's own path convention."""
    counts = {}
    for report_path in report_paths:
        with open(report_path) as f:
            report = json.load(f)
        for finding in report["findings"]:
            source = finding["source"]
            rel = os.path.relpath(source, repo_root) if os.path.isabs(source) else source
            key = (rel, finding["category"])
            counts[key] = counts.get(key, 0) + 1

    by_file = {}
    for (file_path, category), count in counts.items():
        by_file.setdefault(file_path, []).append((category, count))

    lines_out = []
    for file_path in sorted(by_file):
        _, classification = classify_by_path(file_path)
        kept_categories = []
        dispositions = []
        for category, count in sorted(by_file[file_path]):
            action, reason_or_note = build_reason(file_path, category, count, classification)
            summary[action] += count
            if action == "fixed":
                dispositions.append(reason_or_note)
                continue
            kept_categories.append((category, count))
            dispositions.append(reason_or_note)
        if not kept_categories:
            continue
        exempt_reasons = [d for d in dispositions if d]
        reason_text = " ".join(dict.fromkeys(exempt_reasons))
        lines_out.append(f"  - file: {file_path}")
        lines_out.append(f"    reason: \"{reason_text}\"")
        lines_out.append("    findings_by_category:")
        for category, count in kept_categories:
            lines_out.append(f"      {category}: {count}")
    return "\n".join(lines_out) + "\n" if lines_out else ""


def build_reason(file_path, category, count, classification):
    override = FILE_OVERRIDES.get((file_path, category))
    if override:
        return override["action"], override.get("reason")
    if classification == "exemption_candidate":
        return "exempt", SEED_FIXTURE_REASON.format(count=count)
    if category == "hardcoded_iso_date":
        return "exempt", HARDCODED_DATE_REASON.format(count=count)
    raise ValueError(f"No Phase 4 disposition rule for {file_path!r} category {category!r} "
                      f"(classification={classification!r}) -- add one to FILE_OVERRIDES or a "
                      f"category rule before re-running; refusing to guess.")


def rewrite_entry(match, summary):
    file_path = match.group("file")
    old_reason = match.group("reason")
    slug, classification = classify(old_reason)
    categories = CATEGORY_LINE_RE.findall(match.group("categories"))

    kept_categories = []
    dispositions = []
    for category, count_str in categories:
        count = int(count_str)
        action, reason_or_note = build_reason(file_path, category, count, classification)
        summary[action] += count
        if action == "fixed":
            dispositions.append(reason_or_note)
            # resolved in code -- drop this category from the grandfathered count entirely
            continue
        kept_categories.append((category, count))
        dispositions.append(reason_or_note)

    if not kept_categories:
        # every category on this file was fixed in code -- no more grandfathered debt at all
        return ""

    # One file can carry at most one exempt-type reason per current file shape (all baseline
    # files so far have a single classification); join distinct reasons if that ever changes.
    exempt_reasons = [d for d in dispositions if d]
    reason_text = " ".join(dict.fromkeys(exempt_reasons))  # de-dup while preserving order
    lines = [f"  - file: {file_path}", f"    reason: \"{reason_text}\"", "    findings_by_category:"]
    for category, count in kept_categories:
        lines.append(f"      {category}: {count}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--exemptions-file", required=True, help="path to terminology-guardrail-exemptions.yaml")
    parser.add_argument("--from-scan", action="append", default=[],
                         help="path to a fresh guardrail JSON findings report (repeatable) -- switches to "
                              "regenerate mode, rebuilding the whole exemptions: list from current repo state")
    parser.add_argument("--repo-root", default=None,
                         help="repo root the scan reports' absolute source paths are relative to "
                              "(required with --from-scan)")
    args = parser.parse_args()

    with open(args.exemptions_file) as f:
        content = f.read()

    summary = {"exempt": 0, "fixed": 0}
    header_end = content.index("\nexemptions:\n") + len("\nexemptions:\n")

    if args.from_scan:
        if not args.repo_root:
            parser.error("--from-scan requires --repo-root")
        new_body = generate_from_scan(args.from_scan, args.repo_root, summary)
    else:
        body = content[header_end:]
        rewritten_entries = [rewrite_entry(m, summary) for m in ENTRY_RE.finditer(body)]
        new_body = "".join(rewritten_entries)

    new_content = content[:header_end] + new_body

    with open(args.exemptions_file, "w") as f:
        f.write(new_content)

    total = summary["exempt"] + summary["fixed"]
    print(f"Phase 4 finalization: {total} findings given a real disposition "
          f"({summary['fixed']} fixed in code, {summary['exempt']} permanent exemption).")
    print(f"Wrote {args.exemptions_file}")


if __name__ == "__main__":
    main()
