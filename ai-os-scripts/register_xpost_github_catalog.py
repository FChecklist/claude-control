#!/usr/bin/env python3
"""
Registers ai-os/XPOST_GITHUB_CATALOG_2026-07-24.yaml (built by
generate_xpost_github_catalog.py) into the live knowledge_engine table via
superboss-register.py's own CLI -- per this session's standing rule,
registry writes come from a script, never hand-authored prose/SQL.

Idempotent: checks query-knowledge for an existing row at this artifact_path
first and skips register-knowledge (only adds the 3 entity_relationships
edges) if one is already there, rather than inserting a duplicate row (this
table is otherwise insert-only per register_knowledge's own docstring).

Tags carry every repo_path from the catalog (not just the 4 flagged
high_relevance) so query-knowledge (FTS over artifact_path/purpose/tags/
entity_relationships) can find this catalog row by any repo name, e.g.
"claudexor" or "code-review-graph" -- both are required to return a hit
per this task's SUCCESS_CRITERIA.
"""
import json
import os
import subprocess
import sys
import yaml

VERIDIAN_ROOT = "/opt/veridian"
SUPERBOSS = f"{VERIDIAN_ROOT}/scripts/superboss-register.py"
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(WORKSPACE_ROOT, "ai-os", "XPOST_GITHUB_CATALOG_2026-07-24.yaml")

# Post-merge, this same file is expected to also land at the claude-control
# repo mirror synced from master (same dual-location precedent as
# MASTER_INDEX.yaml/CONTROLLER.yaml elsewhere in knowledge_engine) -- recorded
# here, not registered as a live row until it is real and hashable there.
SECONDARY_PATH = f"{VERIDIAN_ROOT}/repos/claude-control/ai-os/XPOST_GITHUB_CATALOG_2026-07-24.yaml"

# entity_relationships for the 4 high_relevance repos -> the closest real
# VERIDIAN artifacts, per this task's SCOPE item 3. Neither target below is
# itself yet registered in knowledge_engine, so related_artifact_id will
# resolve to null (register-knowledge's own documented, non-fabricating
# behavior) while the real path + evidence are still recorded.
RELATIONSHIPS = [
    {
        "path": f"{VERIDIAN_ROOT}/scripts/anthropic_openrouter_proxy_v2.py",
        "relationship_type": "future_evaluation_candidate_for",
        "evidence": (
            "razzant/claudexor and stablyai/orca both orchestrate multiple coding "
            "CLIs (Claude Code/Codex/Cursor/OpenCode) to cut token cost. VERIDIAN's "
            "closest existing real artifact in this space is this proxy's hard "
            "budget-ceiling + exact-match cache chokepoint (single-provider, not "
            "multi-CLI) -- no multi-CLI orchestrator exists in VERIDIAN yet."
        ),
    },
    {
        "path": f"{VERIDIAN_ROOT}/scripts/superboss-register.py",
        "relationship_type": "future_evaluation_candidate_for",
        "evidence": (
            "tirth8205/code-review-graph builds a codebase-to-dependency knowledge "
            "graph for AI code review -- conceptually adjacent to this file's own "
            "knowledge_engine entity_relationships layer (register_knowledge/"
            "add_relationship)."
        ),
    },
    {
        "path": "ai-os/UX_AUDIT_ENGINE (not yet built as of 2026-07-24)",
        "relationship_type": "future_evaluation_candidate_for",
        "evidence": (
            "Nutlope/hallmark removes the AI-generated look from websites via 57 "
            "design checks -- flagged as relevant to a future VERIDIAN UX Audit "
            "Engine, which does not exist yet (forward reference, not a real path)."
        ),
    },
]


def already_registered():
    out = subprocess.run(
        [sys.executable, SUPERBOSS, "query-knowledge", "XPOST-GITHUB-CATALOG-2026-07-24"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    for row in data.get("matches", []):
        if row["artifact_path"] == CATALOG_PATH:
            return row["artifact_id"]
    return None


def main():
    with open(CATALOG_PATH) as f:
        catalog = yaml.safe_load(f)

    repo_tags = sorted({r["repo_path"] for r in catalog["repos"]})
    high_relevance_tags = sorted(
        r["repo_path"] for r in catalog["repos"] if r["high_relevance"]
    )
    tags = ["xpost-github-catalog", "archive-only", "reference-only",
            "source:x-post", "domain:knowledge_engine"] + repo_tags
    for hr in high_relevance_tags:
        tags.append(f"high_relevance:{hr}")

    purpose = (
        f"Reference-only catalog of {catalog['meta']['repo_count']} GitHub repos "
        f"({catalog['meta']['checked_no_repo_count']} checked-no-repo entries recorded "
        f"separately) surfaced via X/Twitter posts, from instruction "
        f"{catalog['meta']['source_instruction']['instruction_id']}. ARCHIVE ONLY -- "
        f"no cloning/installing/integration performed. High-relevance repos flagged for "
        f"future VERIDIAN work: {', '.join(high_relevance_tags)}."
    )

    existing_id = already_registered()
    if existing_id:
        print(json.dumps({"skipped_insert": True, "artifact_id": existing_id,
                           "reason": "row already exists for this artifact_path"}))
        artifact_id = existing_id
    else:
        relationships_json = json.dumps([
            {"path": r["path"], "relationship_type": r["relationship_type"], "evidence": r["evidence"]}
            for r in RELATIONSHIPS
        ])
        result = subprocess.run(
            [sys.executable, SUPERBOSS, "register-knowledge",
             "--path", CATALOG_PATH,
             "--artifact-type", "canonical",
             "--purpose", purpose,
             "--tags", ",".join(tags),
             "--relationships", relationships_json,
             "--secondary-path", SECONDARY_PATH,
             "--metadata", json.dumps({
                 "instruction_id": catalog["meta"]["source_instruction"]["instruction_id"],
                 "prior_batch_search": catalog["meta"]["prior_batch_search"],
             })],
            capture_output=True, text=True,
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            sys.exit(result.returncode)
        artifact_id = json.loads(result.stdout)["artifact_id"]

    print(json.dumps({"artifact_id": artifact_id, "tags_count": len(tags),
                       "relationships_count": len(RELATIONSHIPS)}, indent=2))


if __name__ == "__main__":
    main()
