#!/usr/bin/env python3
"""
Updates the EXISTING knowledge_engine row for XPOST_GITHUB_CATALOG_2026-07-24.yaml
(KE-20260724-062517-e6b1, inserted by register_xpost_github_catalog.py for
batch 1) with batch 2's 19 new repos, via superboss-register.py's own CLI --
per this session's standing rule, registry writes come from a script, never
hand-authored prose/SQL.

register-knowledge is documented insert-only (one row per artifact_path);
re-running it here would create a duplicate row for the same catalog, which
this task's SUCCESS_CRITERIA explicitly rules out ("merged not duplicated").
So this script instead uses the 3 update-in-place primitives the CLI already
exposes for exactly this situation:
  - add-tag           x1 per new repo_path (so query-knowledge's FTS can find
                       this catalog row by any batch-2 repo name too, e.g.
                       "iFixAi" or "OmniRoute" -- same reasoning as batch 1's
                       register script) + x1 per newly-high_relevance repo.
  - add-relationship   x1 per SCOPE-item-3 edge: ifixai-ai/iFixAi -> the real
                       VERIDIAN Testing Engine phase plan AND the real
                       Auditor Engine phase plan; composio-community/
                       awesome-codex-skills -> the real, already-shipped
                       Composio integration file in compliance-tracker.
  - annotate-knowledge x1 dated note summarizing the batch-2 merge (repo_count
                       34 -> 53, checked_no_repo_count 3 -> 7), since there is
                       no "update purpose" primitive in the CLI and the
                       purpose string embeds counts that are now stale.

All --path arguments below use the EXACT registered primary artifact_path
(the frozen batch-1 task workspace snapshot) as the lookup key, since that
is what add-tag/add-relationship/annotate-knowledge match against -- not the
repo-tracked file this task actually edited (that file's own on-disk bytes
are not touched by this script; only the knowledge_engine row's tags/
relationships/metadata are).

Run: python3 ai-os-scripts/register_xpost_github_catalog_batch2.py
"""
import json
import subprocess
import sys

VERIDIAN_ROOT = "/opt/veridian"
SUPERBOSS = f"{VERIDIAN_ROOT}/scripts/superboss-register.py"

# The exact registered primary artifact_path for KE-20260724-062517-e6b1
# (confirmed live via `query-knowledge XPOST-GITHUB-CATALOG-2026-07-24`).
CATALOG_ARTIFACT_PATH = (
    f"{VERIDIAN_ROOT}/ai-os/tasks/task-20260724-060203-xpost-github-catalog-2026-07-24/"
    "workspace/ai-os/XPOST_GITHUB_CATALOG_2026-07-24.yaml"
)

BATCH2_REPO_PATHS = [
    "VectifyAI/PageIndex",
    "supermemoryai/supermemory",
    "diegosouzapw/OmniRoute",
    "asgeirtj/system_prompts_leaks",
    "OpenCut-app/OpenCut",
    "MadsLorentzen/ai-job-search",
    "zaid-maker/meetily",
    "usestrix/strix",
    "superpowerlabs/superpower",
    "mendableai/firecrawl",
    "pathwaycom/pathway",
    "rasbt/LLM-workshop-2024",
    "Unstructured-IO/unstructured",
    "Sanster/IOPaint",
    "ifixai-ai/iFixAi",
    "composio-community/awesome-codex-skills",
    "invoke-ai/InvokeAI",
    "DavidHDev/canvas-ui",
    "lightningpixel/modly",
]
BATCH2_HIGH_RELEVANCE = ["ifixai-ai/iFixAi", "composio-community/awesome-codex-skills"]

RELATIONSHIPS = [
    {
        "related_path": f"{VERIDIAN_ROOT}/ai-os/TESTING_ENGINE_PHASE_PLAN_2026-07-24.yaml",
        "relationship_type": "future_evaluation_candidate_for",
        "evidence": (
            "ifixai-ai/iFixAi catches AI agent mistakes/blind spots before "
            "customers do -- explicitly flagged HIGH RELEVANCE to VERIDIAN's "
            "Testing Engine (this phase plan is the real, already-registered "
            "VERIDIAN Testing Engine / IRVF build plan)."
        ),
    },
    {
        "related_path": f"{VERIDIAN_ROOT}/ai-os/AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml",
        "relationship_type": "future_evaluation_candidate_for",
        "evidence": (
            "ifixai-ai/iFixAi catches AI agent mistakes/blind spots before "
            "customers do -- explicitly flagged HIGH RELEVANCE to VERIDIAN's "
            "Auditor Engine (this phase plan is the real, already-registered "
            "VERIDIAN Auditor Engine build plan)."
        ),
    },
    {
        "related_path": f"{VERIDIAN_ROOT}/repos/compliance-tracker/src/lib/composio-connectors.ts",
        "relationship_type": "future_evaluation_candidate_for",
        "evidence": (
            "composio-community/awesome-codex-skills is a Codex skills "
            "collection -- flagged RELEVANT since VERIDIAN already integrates "
            "Composio via this real file (executeAction()/CONNECTOR_TOOLKITS, "
            "per CONTROLLER.yaml's sync_transport_dispatch_2026_07_16 entry)."
        ),
    },
]

ANNOTATION_NOTE = (
    "Batch-2 merge (instruction INS-20260724-091135-582a, "
    "task-20260724-091206-xpost-github-catalog-batch2-2026-07-24): 19 new "
    "repo rows + 4 new checked_no_repo rows merged into the repo-tracked "
    "copy of this catalog (claude-control/ai-os/XPOST_GITHUB_CATALOG_2026-07-24.yaml, "
    "this row's secondary_path) via ai-os-scripts/merge_xpost_github_catalog_batch2.py. "
    "repo_count 34 -> 53, checked_no_repo_count 3 -> 7. "
    "diegosouzapw/OmniRoute (named 3x in the batch-2 instruction) stored once, "
    "not duplicated. 2 new high_relevance repos: ifixai-ai/iFixAi, "
    "composio-community/awesome-codex-skills (3 new entity_relationships added "
    "separately via add-relationship). No source_tweet_url was itemized "
    "per-repo in the batch-2 instruction (unlike batch 1) -- every batch-2 "
    "catalog row's source_tweet_url is null with an explanatory note, not "
    "fabricated. This row's own artifact_path (the frozen batch-1 task "
    "workspace snapshot) is intentionally left un-rehashed by this merge -- "
    "only secondary_path (the live repo copy) carries the batch-2 content; "
    "this is the same known live-vs-repo split already present in this row "
    "since batch 1's registration."
)


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    return json.loads(result.stdout)


def main():
    tag_results = []
    for repo_path in BATCH2_REPO_PATHS:
        tag_results.append(run(
            [sys.executable, SUPERBOSS, "add-tag",
             "--path", CATALOG_ARTIFACT_PATH, "--tag", repo_path]
        ))
    for repo_path in BATCH2_HIGH_RELEVANCE:
        tag_results.append(run(
            [sys.executable, SUPERBOSS, "add-tag",
             "--path", CATALOG_ARTIFACT_PATH, "--tag", f"high_relevance:{repo_path}"]
        ))

    rel_results = []
    for rel in RELATIONSHIPS:
        rel_results.append(run(
            [sys.executable, SUPERBOSS, "add-relationship",
             "--path", CATALOG_ARTIFACT_PATH,
             "--related-path", rel["related_path"],
             "--relationship-type", rel["relationship_type"],
             "--evidence", rel["evidence"]]
        ))

    annotate_result = run(
        [sys.executable, SUPERBOSS, "annotate-knowledge",
         "--path", CATALOG_ARTIFACT_PATH, "--note", ANNOTATION_NOTE]
    )

    final_tags = tag_results[-1]["tags"] if tag_results else None
    print(json.dumps({
        "artifact_path": CATALOG_ARTIFACT_PATH,
        "artifact_id": tag_results[-1]["artifact_id"] if tag_results else None,
        "tags_added": len(BATCH2_REPO_PATHS) + len(BATCH2_HIGH_RELEVANCE),
        "final_tags_count": len(final_tags) if final_tags else None,
        "relationships_added": len(rel_results),
        "final_entity_relationships_count": len(rel_results[-1]["entity_relationships"]) if rel_results else None,
        "annotated": bool(annotate_result.get("artifact_id")),
    }, indent=2))


if __name__ == "__main__":
    main()
