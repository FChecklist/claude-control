#!/usr/bin/env python3
"""
Updates the EXISTING knowledge_engine row for XPOST_GITHUB_CATALOG_2026-07-24.yaml
(KE-20260724-062517-e6b1, inserted by register_xpost_github_catalog.py for
batch 1, updated by register_xpost_github_catalog_batch2.py for batch 2)
with batch 3's 8 new repos, via superboss-register.py's own CLI -- per this
session's standing rule, registry writes come from a script, never
hand-authored prose/SQL.

register-knowledge is documented insert-only (one row per artifact_path);
re-running it here would create a duplicate row for the same catalog, which
this task's SUCCESS_CRITERIA explicitly rules out ("merged not duplicated").
So this script instead uses the same 3 update-in-place primitives batch 2
used:
  - add-tag           x1 per new repo_path (so query-knowledge's FTS can find
                       this catalog row by any batch-3 repo name too, e.g.
                       "ponytail" or "openworker") + x1 for the newly
                       high_relevance repo.
  - add-relationship   x1 per SCOPE-item-3 edge: DietrichGebert/ponytail ->
                       this session's known token-cost-control work (the
                       real, already-registered multi-CLI cost-control proxy
                       that batch 1's claudexor/orca relationship also points
                       at).
  - annotate-knowledge x1 dated note summarizing the batch-3 merge (repo_count
                       53 -> 61, checked_no_repo_count 7 -> 12).

All --path arguments below use the EXACT registered primary artifact_path
(the frozen batch-1 task workspace snapshot) as the lookup key, since that
is what add-tag/add-relationship/annotate-knowledge match against -- not the
repo-tracked file this task actually edited (that file's own on-disk bytes
are not touched by this script; only the knowledge_engine row's tags/
relationships/metadata are).

Run: python3 ai-os-scripts/register_xpost_github_catalog_batch3.py
"""
import json
import subprocess
import sys

VERIDIAN_ROOT = "/opt/veridian"
SUPERBOSS = f"{VERIDIAN_ROOT}/scripts/superboss-register.py"

# The exact registered primary artifact_path for KE-20260724-062517-e6b1
# (confirmed live via `query-knowledge "xpost github catalog"`).
CATALOG_ARTIFACT_PATH = (
    f"{VERIDIAN_ROOT}/ai-os/tasks/task-20260724-060203-xpost-github-catalog-2026-07-24/"
    "workspace/ai-os/XPOST_GITHUB_CATALOG_2026-07-24.yaml"
)

BATCH3_REPO_PATHS = [
    "Timeverse/My-TW-Coverage",
    "TabularisDB/tabularis",
    "comfyanonymous/ComfyUI",
    "teambit/bit",
    "DietrichGebert/ponytail",
    "danny-avila/LibreChat",
    "andrewyng/openworker",
    "davidondrej/skills",
]
BATCH3_HIGH_RELEVANCE = ["DietrichGebert/ponytail"]

RELATIONSHIPS = [
    {
        "related_path": f"{VERIDIAN_ROOT}/scripts/anthropic_openrouter_proxy_v2.py",
        "relationship_type": "future_evaluation_candidate_for",
        "evidence": (
            "DietrichGebert/ponytail reduces unnecessary AI-agent code output "
            "(claimed up to 94% less code) -- explicitly flagged relevant to "
            "VERIDIAN's own token-cost concerns. This proxy is this session's "
            "known token-cost-control work (hard budget-ceiling + exact-match "
            "cache chokepoint), the same real artifact batch 1's claudexor/orca "
            "relationship already points at for the same class of concern."
        ),
    },
]

ANNOTATION_NOTE = (
    "Batch-3 merge (instruction INS-20260724-095812-0523, "
    "task-20260724-095857-xpost-github-catalog-batch3-2026-07-24): 8 new "
    "repo rows + 5 new checked_no_repo rows merged into the repo-tracked "
    "copy of this catalog (claude-control/ai-os/XPOST_GITHUB_CATALOG_2026-07-24.yaml, "
    "this row's secondary_path) via ai-os-scripts/merge_xpost_github_catalog_batch3.py. "
    "repo_count 53 -> 61, checked_no_repo_count 7 -> 12. "
    "Zipstack/unstract reposted in the batch-3 source posts; already catalogued "
    "in batch 1, not re-added -- recorded once in checked_no_repo as a dedup note. "
    "1 new high_relevance repo: DietrichGebert/ponytail (1 new entity_relationship "
    "added separately via add-relationship, to this session's known token-cost-control "
    "work). The instruction's claim of a free-forever Claude Code router via free-tier "
    "providers surfaced no repo link -- recorded in checked_no_repo as UNVERIFIED / "
    "ToS-adjacent, not a recommended tool. No source_tweet_url was itemized per-repo "
    "in the batch-3 instruction (aggregate count only, same as batch 2) -- every "
    "batch-3 catalog row's source_tweet_url is null with an explanatory note, not "
    "fabricated. This row's own artifact_path (the frozen batch-1 task workspace "
    "snapshot) is intentionally left un-rehashed by this merge -- only secondary_path "
    "(the live repo copy) carries the batch-3 content; this is the same known "
    "live-vs-repo split already present in this row since batch 1's registration."
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
    for repo_path in BATCH3_REPO_PATHS:
        tag_results.append(run(
            [sys.executable, SUPERBOSS, "add-tag",
             "--path", CATALOG_ARTIFACT_PATH, "--tag", repo_path]
        ))
    for repo_path in BATCH3_HIGH_RELEVANCE:
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
        "tags_added": len(BATCH3_REPO_PATHS) + len(BATCH3_HIGH_RELEVANCE),
        "final_tags_count": len(final_tags) if final_tags else None,
        "relationships_added": len(rel_results),
        "final_entity_relationships_count": len(rel_results[-1]["entity_relationships"]) if rel_results else None,
        "annotated": bool(annotate_result.get("artifact_id")),
    }, indent=2))


if __name__ == "__main__":
    main()
