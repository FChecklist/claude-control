#!/usr/bin/env python3
"""
generate_chatgpt_promptbatch_request.py -- manual-bridge request generator
for the VERIDIAN ChatGPT Prompt Library (INS-20260724-214122-f0ed,
task-20260724-214215-chatgpt-manual-bridge-workflow).

Owner decision this task implements: no OPENAI_API_KEY will be supplied (see
ai-os/CHATGPT_PROMPTLIB_BLOCKER_2026-07-24.yaml's prior awaiting_owner_decision
state). Instead of an API call, this script produces ONE real, complete,
ready-to-copy text file covering N real, currently-uncovered capabilities
from the live capability_registry (via scripts/generate_prompt_coverage_report.py's
own loaders -- never a second, divergent reader of that data), the exact
ai-os/CHATGPT_PROMPT_SCHEMA_2026-07-24.yaml 15-column contract, and the
<Entity.Attribute> placeholder rule (reused from
ai-os/VARIABLE_DICTIONARY_2026-07-24.yaml, never reinvented) with an explicit
instruction to never use a hardcoded company/person name.

The Owner copies this into a free ChatGPT web session by hand, then saves the
reply for scripts/ingest_chatgpt_promptbatch_response.py to parse, validate,
and write into CSV/.

Nothing here calls any LLM API. The only write this script performs is the
request .txt file itself, under
/opt/veridian/chatgpt-prompt-library/_pending_requests/, still routed through
scripts/chatgpt_promptlib_guard.py's guarded_write.

Run:
  python3 scripts/generate_chatgpt_promptbatch_request.py --count 10
  python3 scripts/generate_chatgpt_promptbatch_request.py --count 3 --prompts-per-capability 8
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from chatgpt_promptlib_guard import SANDBOX_ROOT, guarded_write  # noqa: E402
from generate_prompt_coverage_report import (  # noqa: E402
    load_real_capabilities, load_real_prompts, compute_coverage, DEFAULT_CSV_DIR,
)

import yaml  # noqa: E402

REPO_ROOT = os.path.dirname(SCRIPT_DIR)
SCHEMA_PATH = os.path.join(REPO_ROOT, "ai-os", "CHATGPT_PROMPT_SCHEMA_2026-07-24.yaml")
VARIABLE_DICTIONARY_PATH = os.path.join(REPO_ROOT, "ai-os", "VARIABLE_DICTIONARY_2026-07-24.yaml")
PENDING_REQUESTS_DIR = os.path.join(SANDBOX_ROOT, "_pending_requests")

DEFAULT_PROMPTS_PER_CAPABILITY = 5
DEFAULT_PLACEHOLDER_ENTITIES_PER_CAPABILITY = 3
DEFAULT_ATTRS_PER_ENTITY = 6


def _now_compact():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_variable_dictionary():
    with open(VARIABLE_DICTIONARY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def group_placeholders_by_entity(var_dict):
    by_entity = {}
    for entry in var_dict.get("entries", []):
        by_entity.setdefault(entry["entity"], []).append(entry["placeholder"])
    return by_entity


def pick_relevant_entities(capability, by_entity, max_entities):
    """Real, non-fabricated matching: an entity is 'relevant' to a capability
    if its lowercase name appears as a substring of the capability's own
    owner/workflow/capability_name text, or (fallback) it's one of the two
    highest-reference-count entities (Clients, Users) that appear in nearly
    every business prompt. No semantic guessing beyond substring matching."""
    haystack = " ".join(str(capability.get(k) or "") for k in ("owner", "workflow", "capability_name")).lower()
    matched = [entity for entity in by_entity if entity.lower() in haystack]
    for fallback in ("Users", "Clients"):
        if fallback in by_entity and fallback not in matched:
            matched.append(fallback)
    return matched[:max_entities]


def render_placeholder_appendix(capabilities, by_entity, max_entities, max_attrs):
    lines = []
    seen_entities = set()
    for cap in capabilities:
        entities = pick_relevant_entities(cap, by_entity, max_entities)
        lines.append(f"  {cap['capability_name']}: relevant entities -> {entities or '(none matched, use Users/Clients generically)'}")
        for entity in entities:
            if entity in seen_entities:
                continue
            seen_entities.add(entity)
            tokens = by_entity.get(entity, [])[:max_attrs]
            lines.append(f"    <{entity}.*> registered placeholders (sample): {', '.join(tokens)}")
    return "\n".join(lines)


def render_schema_columns(schema):
    lines = []
    for col in schema["csv_schema"]["columns"]:
        lines.append(f"  - {col['name']} ({col['type']}, required={col['required']}): {col['description']}")
    return "\n".join(lines)


def build_request_text(selected_capabilities, all_capabilities_by_name, prompts_per_capability,
                        schema, var_dict, requested_count, missing_count):
    by_entity = group_placeholders_by_entity(var_dict)
    columns_text = render_schema_columns(schema)
    placeholder_rule = schema["placeholder_variable_convention"]["rule"]
    placeholder_example = schema["placeholder_variable_convention"]["example"]
    placeholder_appendix = render_placeholder_appendix(
        selected_capabilities, by_entity, DEFAULT_PLACEHOLDER_ENTITIES_PER_CAPABILITY, DEFAULT_ATTRS_PER_ENTITY
    )

    shortfall_note = ""
    if requested_count > missing_count:
        shortfall_note = (
            f"\nNOTE: {requested_count} capabilities were requested but only {missing_count} real "
            f"capabilities are currently uncovered (0 real prompt rows) -- this batch covers all "
            f"{missing_count} of them, not {requested_count}. No capability is fabricated to make up "
            f"the count.\n"
        )

    capability_blocks = []
    for cap in selected_capabilities:
        capability_blocks.append(
            f"### Capability: {cap['capability_name']}\n"
            f"  owner: {cap.get('owner')}\n"
            f"  ai_required: {cap.get('ai_required')}\n"
            f"  confidence: {cap.get('confidence')}\n"
            f"  workflow: {cap.get('workflow')}\n"
            f"  inputs: {json.dumps(cap.get('inputs'), default=str)}\n"
            f"  business_rules: {json.dumps(cap.get('business_rules'), default=str)}\n"
        )

    parts = [
        "SYSTEM: You are generating real prompts for the VERIDIAN ChatGPT Prompt Library. Each prompt "
        "is a realistic, natural-language request a VERIDIAN user would type, that the named capability "
        "should be able to answer.",
        "",
        f"Output EXACTLY {prompts_per_capability} prompt rows per capability listed below, as CSV with "
        "this exact header row (15 columns, in this order):",
        ",".join(c["name"] for c in schema["csv_schema"]["columns"]),
        "",
        "Column contract:",
        columns_text,
        "",
        "PLACEHOLDER RULE (mandatory, reused from ai-os/VARIABLE_DICTIONARY_2026-07-24.yaml -- do not "
        "invent a different placeholder syntax):",
        f"  {placeholder_rule}",
        f"  Example: {placeholder_example}",
        "",
        "HARD REJECTION RULE: Any example data inside a Prompt (company name, person name, email, "
        "date, ID number) MUST use one of the registered <Entity.Attribute> placeholder tokens listed "
        "below -- NEVER a literal/hardcoded company name (e.g. 'Acme Corp', 'ABC Pvt Ltd'), person name "
        "(e.g. 'John Doe', 'Jane Smith'), or any other invented literal. A row using a hardcoded name "
        "instead of a placeholder will be automatically rejected at ingestion, not silently accepted.",
        "",
        "Registered placeholder tokens relevant to each capability below (sample -- the full dictionary "
        "has 894 entries across 60 entities in ai-os/VARIABLE_DICTIONARY_2026-07-24.yaml; if you need an "
        "entity/attribute not listed here, prefer Users/Clients/Tasks generic attributes over inventing one):",
        placeholder_appendix,
        shortfall_note,
        "CAPABILITIES FOR THIS BATCH (real, live capability_registry rows -- Capability column MUST "
        "exactly match one of these capability_name values):",
        "\n".join(capability_blocks),
        "",
        "Respond with ONLY the CSV -- header row first, then the prompt rows, no prose before or after, "
        "no markdown code fence.",
    ]
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=10, help="number of currently-uncovered capabilities to include")
    parser.add_argument("--prompts-per-capability", type=int, default=DEFAULT_PROMPTS_PER_CAPABILITY)
    parser.add_argument("--csv-dir", default=DEFAULT_CSV_DIR)
    args = parser.parse_args()

    try:
        capabilities = load_real_capabilities()
    except (RuntimeError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "error": "capability_registry_unreachable", "detail": str(e)}, indent=2))
        sys.exit(1)

    prompts, _ = load_real_prompts(args.csv_dir)
    coverage = compute_coverage(capabilities, prompts)
    missing_names = coverage["missing_capabilities"]

    if not missing_names:
        print(json.dumps({
            "ok": False,
            "error": "no_uncovered_capabilities",
            "detail": "every real capability already has >=1 real prompt row -- nothing to batch. "
                      "Consider a targeted --count against a specific gap instead.",
        }, indent=2))
        sys.exit(1)

    selected_names = missing_names[:args.count]
    by_name = {c["capability_name"]: c for c in capabilities}
    selected_capabilities = [by_name[name] for name in selected_names]

    schema = load_schema()
    var_dict = load_variable_dictionary()

    request_text = build_request_text(
        selected_capabilities, by_name, args.prompts_per_capability, schema, var_dict,
        requested_count=args.count, missing_count=len(missing_names),
    )

    ts = _now_compact()
    batch_id = f"BATCH-{ts}"
    request_filename = f"{batch_id}-request-{ts}.txt"
    request_path = os.path.join(PENDING_REQUESTS_DIR, request_filename)

    header = (
        "=== VERIDIAN ChatGPT Prompt Library Batch Request (manual-bridge) ===\n"
        f"Batch: {batch_id}\n"
        f"Generated: {datetime.now(timezone.utc).isoformat()}\n"
        "Generated by: scripts/generate_chatgpt_promptbatch_request.py "
        "(INS-20260724-214122-f0ed, task-20260724-214215-chatgpt-manual-bridge-workflow)\n"
        f"Capabilities in this batch: {selected_names}\n"
        "\n"
        "INSTRUCTIONS FOR THE OWNER:\n"
        "  1. Copy everything below the '===== COPY BELOW THIS LINE =====' marker into a new,\n"
        "     free ChatGPT web session (no API key needed).\n"
        "  2. Save ChatGPT's full CSV response to a file.\n"
        "  3. Run: python3 scripts/ingest_chatgpt_promptbatch_response.py --file <response-file>\n"
        "\n"
        "===== COPY BELOW THIS LINE =====\n"
    )
    full_text = header + request_text

    guarded_write(request_path, full_text)

    print(json.dumps({
        "ok": True,
        "request_path": request_path,
        "batch_id": batch_id,
        "capabilities_selected": selected_names,
        "requested_count": args.count,
        "available_uncovered_count": len(missing_names),
        "prompts_per_capability": args.prompts_per_capability,
        "next_step": "python3 scripts/ingest_chatgpt_promptbatch_response.py --file <response-file>",
    }, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
