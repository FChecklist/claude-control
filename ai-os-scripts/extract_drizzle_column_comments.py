#!/usr/bin/env python3
"""Live extraction of real drizzle column definitions + their inline `//`
comments from compliance-tracker/src/lib/db/schema.ts, for the metadata
domain's DRIZZLE_COLUMN_COMMENT_CONVENTION_2026-07-24.schema.json.

Bounded to the same 3 veri-meetings tables (veriMeetings,
veriMeetingActionItems, veriMeetingShareLinks) this phase's
compliance-tracker.openapi.yaml already documents -- same
representative-subset discipline as the api-contract domain's own OpenAPI
docs, not a full-schema.ts extraction (schema.ts is 5000+ lines covering
hundreds of tables).

This is a real regex-based line parser over the actual file, not invented
data -- re-running it against a changed schema.ts produces different real
output. Multi-line column definitions (rare in this file) are not split
across lines by this parser; each column here is confirmed one-line.

Usage:
    python3 extract_drizzle_column_comments.py [--schema-file PATH] [--table NAME]...
    Prints a JSON array matching DRIZZLE_COLUMN_COMMENT_CONVENTION_2026-07-24.schema.json to stdout.
"""
import argparse
import json
import re
import sys

DEFAULT_SCHEMA_FILE = "/opt/veridian/repos/compliance-tracker/src/lib/db/schema.ts"
DEFAULT_TABLES = ["veriMeetings", "veriMeetingActionItems", "veriMeetingShareLinks"]

_TABLE_START_RE = re.compile(r"^export const (\w+) = \w+\.table\(")
_COLUMN_LINE_RE = re.compile(r"^\s*(\w+):\s*.+?,\s*(?://\s*(.*))?$")


def extract_table_block(lines, table_name):
    start_idx = None
    for i, line in enumerate(lines):
        m = _TABLE_START_RE.match(line)
        if m and m.group(1) == table_name:
            start_idx = i
            break
    if start_idx is None:
        raise ValueError(f"table '{table_name}' not found (no 'export const {table_name} = X.table(' line)")

    depth = 0
    block = []
    for line in lines[start_idx:]:
        depth += line.count("{") - line.count("}")
        block.append(line)
        if depth <= 0 and len(block) > 1:
            break
    return block[1:-1]  # drop the `export const X = table('...', {` and closing `})` lines


def extract_columns(block_lines):
    records = []
    for line in block_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        m = _COLUMN_LINE_RE.match(line)
        if not m:
            continue
        column, comment = m.group(1), m.group(2)
        comment = comment.strip() if comment else None
        records.append({
            "column": column,
            "has_comment": comment is not None and len(comment) > 0,
            "raw_comment": comment if comment else None,
        })
    return records


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--schema-file", default=DEFAULT_SCHEMA_FILE)
    ap.add_argument("--table", dest="tables", action="append", default=None)
    args = ap.parse_args()
    tables = args.tables or DEFAULT_TABLES

    with open(args.schema_file) as f:
        lines = f.readlines()

    out = []
    errors = []
    for table in tables:
        try:
            block = extract_table_block(lines, table)
            for rec in extract_columns(block):
                out.append({"table": table, **rec})
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        print(json.dumps({"error": "; ".join(errors)}), file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
