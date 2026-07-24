#!/usr/bin/env python3
"""
generate_variable_dictionary.py -- Phase 0 of VERIDIAN Terminology
Standardization (task-20260724-070131, instruction INS-20260724-070047-3a2d),
Variable Dictionary deliverable (ai-os/VARIABLE_DICTIONARY_2026-07-24.yaml).

Owner standing rule: "all registry/catalog data must be produced by scripts,
not hand-authored AI prose." This script reads the real, mechanically
generated schema catalog (ai-os/DATABASE_CATALOG.json -- 444 tables, extracted
by extract-db-schema-catalog.mjs via drizzle-orm getTableConfig introspection,
NOT AI-written) and derives one <Entity.Attribute> placeholder per real column
of the top-N most-referenced tables. It does not invent entity or attribute
names -- every placeholder is a direct PascalCase transform of a real
table_name/column.name pair that exists in the catalog today.

RANKING METHODOLOGY ("most-referenced" tables):
  Most tables in this schema are Drizzle-defined without a formal SQL FOREIGN
  KEY constraint (only 7 of 444 tables have any non-empty foreign_keys[] in
  the catalog -- confirmed by inspection), so declared FKs alone are too
  sparse a signal. This script instead combines two real, mechanically
  computable signals:
    1. declared_fk_ref_count: how many times a table appears as
       foreign_keys[].foreign_table across the whole catalog (schema-enforced).
    2. naming_convention_ref_count: how many columns *anywhere* in the catalog
       are named exactly "<singularized table_name>_id" (application-enforced
       reference, the dominant pattern in this codebase). Singularization is
       a plain suffix rule (ies->y, ses->s-strip, s->strip), applied only
       when the singularized form matches a real table name in the catalog.
  combined_reference_score = declared_fk_ref_count + naming_convention_ref_count.
  Tables are ranked by (-combined_reference_score, -column_count, table_name)
  and the top TOP_N are selected. This is a real, re-runnable heuristic, not
  a hand-picked list -- rerunning this script against a future catalog
  snapshot will select whichever tables are actually most-referenced then.

EXAMPLE VALUES:
  ai-os/VARIABLE_DICTIONARY_SOURCE_ROWS_2026-07-24.json holds one real row
  (SELECT * ... LIMIT 1) per selected table, fetched live via the Supabase
  MCP tool against the verdian-ai project (pcrjmlpuqsbocqfwoxod) that backs
  compliance-tracker's schema.ts (the same source_file DATABASE_CATALOG.json
  itself cites) -- confirmed dev/seed data (org_001 = "Acme Corp", demo_org),
  not production customer PII. Any column whose name matches
  SENSITIVE_COLUMN_RE (password/passcode/secret/credential/*_hash/token) is
  NEVER sourced from that file even if present -- it always gets a synthetic
  example. Columns with no real row available (empty table, or the row's
  value was null) fall back to a synthetic example clearly marked as such.

Run: python3 ai-os-scripts/generate_variable_dictionary.py
Writes: ai-os/VARIABLE_DICTIONARY_2026-07-24.yaml
Exits non-zero if DATABASE_CATALOG.json or the source-rows file is missing,
or if fewer than TOP_N real tables are found (drift/regression signal).
PHASE 1 UPDATE (task-20260724-084040-phase1-terminology-dictionary-expansion):
  TOP_N raised 20 -> 60 (the phase plan's second tier -- 20 -> 60 -> 150 -> all
  444). VARIABLE_DICTIONARY_SOURCE_ROWS_2026-07-24.json was extended
  append-only with real Supabase-fetched rows for the 39 newly-in-scope
  tables (rank 21-60) that exist in the live DB (24 real rows, 15 confirmed
  live-but-empty at fetch time -- both handled by the existing synthetic
  fallback below), plus one table (ticket_intelligence_items) present in
  DATABASE_CATALOG.json but absent from the live DB (real catalog/DB drift,
  same synthetic-fallback path). Tier 1's original 20 tables were not
  refetched. --top-n lets a future phase re-run for the next tier without
  editing this file.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

import yaml

VERIDIAN_ROOT = "/opt/veridian"
DATABASE_CATALOG_PATH = f"{VERIDIAN_ROOT}/ai-os/DATABASE_CATALOG.json"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_AI_OS_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "ai-os"))
SOURCE_ROWS_PATH = os.path.join(REPO_AI_OS_DIR, "VARIABLE_DICTIONARY_SOURCE_ROWS_2026-07-24.json")
OUTPUT_PATH = os.path.join(REPO_AI_OS_DIR, "VARIABLE_DICTIONARY_2026-07-24.yaml")

TOP_N = 60

SENSITIVE_COLUMN_RE = re.compile(r"password|passcode|secret|credential|_hash$|^hash$|token", re.IGNORECASE)

SYNTHETIC_BY_SQL_TYPE = {
    "boolean": True,
    "date": "2026-07-24",
    "timestamp": "2026-07-24T00:00:00+00:00",
    "integer": 1,
    "numeric": 100.0,
    "jsonb": {},
    "json": {},
    "text": None,  # filled per-column below
}


def singularize(name):
    if name.endswith("ies"):
        return name[:-3] + "y"
    if name.endswith("ses"):
        return name[:-2]
    if name.endswith("s") and not name.endswith("ss"):
        return name[:-1]
    return name


def to_pascal_case(snake_str):
    return "".join(part[:1].upper() + part[1:] for part in snake_str.split("_") if part)


def load_catalog():
    if not os.path.isfile(DATABASE_CATALOG_PATH):
        print(f"FATAL: DATABASE_CATALOG.json not found at {DATABASE_CATALOG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(DATABASE_CATALOG_PATH) as f:
        return json.load(f)


def load_source_rows():
    if not os.path.isfile(SOURCE_ROWS_PATH):
        print(f"FATAL: source rows file not found at {SOURCE_ROWS_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(SOURCE_ROWS_PATH) as f:
        doc = json.load(f)
    by_table = {}
    for entry in doc.get("rows", []):
        by_table[entry["table_name"]] = entry.get("row")
    return by_table


def compute_reference_scores(tables):
    table_names = {t["table_name"] for t in tables}
    singular_map = {}
    for tn in table_names:
        singular_map.setdefault(singularize(tn), []).append(tn)

    declared_fk = {}
    conv_ref = {}
    for t in tables:
        for fk in t.get("foreign_keys", []):
            ft = fk.get("foreign_table")
            if ft:
                declared_fk[ft] = declared_fk.get(ft, 0) + 1
        for c in t["columns"]:
            m = re.match(r"^(.*)_id$", c["name"])
            if not m:
                continue
            base = m.group(1)
            for tn in singular_map.get(base, []):
                if tn != t["table_name"]:
                    conv_ref[tn] = conv_ref.get(tn, 0) + 1

    return declared_fk, conv_ref


def rank_tables(tables, declared_fk, conv_ref):
    def score(t):
        tn = t["table_name"]
        return declared_fk.get(tn, 0) + conv_ref.get(tn, 0)

    ranked = sorted(tables, key=lambda t: (-score(t), -t["column_count"], t["table_name"]))
    return ranked, score


def synthetic_example(entity, attribute, column):
    sql_type = column["sql_type"]
    if column.get("enum_values"):
        return column["enum_values"][0], "synthetic_from_declared_enum"
    if sql_type in ("boolean",):
        return True, "synthetic_placeholder_example"
    if sql_type == "date":
        return "2026-07-24", "synthetic_placeholder_example"
    if sql_type == "timestamp":
        return "2026-07-24T00:00:00+00:00", "synthetic_placeholder_example"
    if sql_type == "integer":
        return 1, "synthetic_placeholder_example"
    if sql_type.startswith("numeric"):
        return 100.0, "synthetic_placeholder_example"
    if sql_type in ("jsonb", "json"):
        return {}, "synthetic_placeholder_example"
    if column["name"] == "id":
        return f"SYNTHETIC_{entity.upper()}_ID_001", "synthetic_placeholder_example"
    return f"SYNTHETIC_EXAMPLE_{entity}_{attribute}", "synthetic_placeholder_example"


def resolve_example(entity, table_name, column, source_row):
    attribute = to_pascal_case(column["name"])
    if SENSITIVE_COLUMN_RE.search(column["name"]):
        value, source = synthetic_example(entity, attribute, column)
        return value, source, True

    if source_row is not None and column["name"] in source_row:
        real_value = source_row[column["name"]]
        if real_value is not None and real_value != "REDACTED_SENSITIVE_FIELD_NOT_USED_AS_EXAMPLE":
            return real_value, "real_row_supabase_2026-07-24", False

    value, source = synthetic_example(entity, attribute, column)
    return value, source, True


def build_dictionary(top_n=TOP_N):
    catalog = load_catalog()
    source_rows = load_source_rows()
    tables = catalog["tables"]

    declared_fk, conv_ref = compute_reference_scores(tables)
    ranked, score_fn = rank_tables(tables, declared_fk, conv_ref)
    selected = ranked[:top_n]

    if len(selected) < top_n:
        print(f"FATAL: only {len(selected)} tables found in catalog, need >= {top_n}", file=sys.stderr)
        sys.exit(1)

    table_summaries = []
    entries = []
    for t in selected:
        table_name = t["table_name"]
        entity = to_pascal_case(table_name)
        table_summaries.append({
            "table_name": table_name,
            "schema": t["schema"],
            "entity": entity,
            "declared_fk_ref_count": declared_fk.get(table_name, 0),
            "naming_convention_ref_count": conv_ref.get(table_name, 0),
            "combined_reference_score": score_fn(t),
            "column_count": t["column_count"],
        })

        source_row = source_rows.get(table_name)
        for c in t["columns"]:
            attribute = to_pascal_case(c["name"])
            example_value, example_source, is_synthetic = resolve_example(entity, table_name, c, source_row)
            entries.append({
                "placeholder": f"<{entity}.{attribute}>",
                "entity": entity,
                "attribute": attribute,
                "source_table": f"{t['schema']}.{table_name}",
                "source_column": c["name"],
                "data_type": c["data_type"],
                "sql_type": c["sql_type"],
                "required": bool(c["not_null"]),
                "has_default": bool(c["has_default"]),
                "primary_key": bool(c["primary_key"]),
                "enum_values": c.get("enum_values"),
                "example_value": example_value,
                "example_source": example_source,
                "example_is_synthetic": is_synthetic,
            })

    doc = {
        "meta": {
            "title": "VERIDIAN Variable Dictionary -- real <Entity.Attribute> placeholders derived from DATABASE_CATALOG.json",
            "generated_by": "ai-os-scripts/generate_variable_dictionary.py",
            "generated_at": "2026-07-24 (task-20260724-070131-veridian-terminology-standardization-pha, INS-20260724-070047-3a2d)",
            "source_catalog": DATABASE_CATALOG_PATH,
            "source_catalog_table_count": catalog["table_count"],
            "source_catalog_generated_by": catalog["generated_by"],
            "source_rows_file": "ai-os/VARIABLE_DICTIONARY_SOURCE_ROWS_2026-07-24.json",
            "ranking_methodology": "combined_reference_score = declared_fk_ref_count (foreign_keys[].foreign_table) "
                                    "+ naming_convention_ref_count (columns named '<singularized table>_id' anywhere "
                                    "in the catalog), sorted desc, tie-broken by column_count desc then table_name. "
                                    "See this script's own module docstring for full rationale (only 7/444 tables "
                                    "have a declared SQL foreign key, so naming-convention is the dominant signal).",
            "top_n": top_n,
            "tables_selected": len(selected),
            "total_placeholder_entries": len(entries),
            "sensitive_column_pattern": SENSITIVE_COLUMN_RE.pattern,
            "sensitive_column_note": "Columns matching this pattern always get a synthetic example, never a real "
                                      "row value, regardless of what VARIABLE_DICTIONARY_SOURCE_ROWS_2026-07-24.json contains.",
        },
        "tables": table_summaries,
        "entries": entries,
    }
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--top-n", type=int, default=TOP_N,
                         help=f"how many most-referenced tables to include (default {TOP_N}, the current phase tier)")
    args = parser.parse_args()

    doc = build_dictionary(top_n=args.top_n)
    with open(OUTPUT_PATH, "w") as f:
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, width=120)
    real_count = sum(1 for e in doc["entries"] if not e["example_is_synthetic"])
    synthetic_count = len(doc["entries"]) - real_count
    print(f"Wrote {OUTPUT_PATH}")
    print(f"  tables_selected={len(doc['tables'])} entries={len(doc['entries'])} "
          f"real_row_examples={real_count} synthetic_examples={synthetic_count}")


if __name__ == "__main__":
    main()
