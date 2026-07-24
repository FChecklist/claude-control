#!/usr/bin/env python3
"""
Merges the 3rd X-post GitHub batch (instruction INS-20260724-095812-0523,
task-20260724-095857-xpost-github-catalog-batch3-2026-07-24) into
ai-os/XPOST_GITHUB_CATALOG_2026-07-24.yaml, in place, alongside the 53
repos already written by generate_xpost_github_catalog.py (batch 1,
INS-20260724-060111-0975) and merge_xpost_github_catalog_batch2.py
(batch 2, INS-20260724-091135-582a).

ARCHIVE ONLY per Owner directive -- no cloning, installing, evaluating fit,
or integrating any of these repos as part of this task.

Scope-item-1 prior-catalog search (per this task's SCOPE): both the live
knowledge_engine table (superboss-register.sqlite, query-knowledge for
"xpost github catalog") and the filesystem (ai-os/tasks tree +
/opt/veridian/repos/claude-control) were checked. Found: exactly one
existing artifact, this file, already registered as KE-20260724-062517-e6b1
with the same known live-vs-repo split batch 2 documented -- artifact_path
(the primary, registered lookup key) is the frozen batch-1 task workspace
snapshot (ai-os/tasks/task-20260724-060203-xpost-github-catalog-2026-07-24/
workspace/ai-os/XPOST_GITHUB_CATALOG_2026-07-24.yaml), while secondary_path
is the live repo-tracked copy this script edits
(claude-control/ai-os/XPOST_GITHUB_CATALOG_2026-07-24.yaml, identical to
this task's own workspace copy of the same file since this task's workspace
is itself a fresh claude-control clone). This script edits only the
repo-tracked copy (the one that reaches origin/master via a real PR, per
this task's EXPECTED_OUTPUT) and leaves the closed batch-1 task's frozen
workspace snapshot untouched.

Per the SPEC's KNOWN_CONTEXT: instruction INS-20260724-095812-0523's
raw_text (read live from superboss-register.sqlite, confirmed by direct
query) gives repo_path + one-line description per repo, but -- like batch 2,
unlike batch 1 -- names an aggregate count ("8 new distinct repos from 13 X
post URLs") without itemizing which URL maps to which repo. No
source_tweet_url is fabricated to fill that gap -- every batch-3 row's
source_tweet_url is left null with a note explaining why.

Zipstack/unstract is named in the batch-3 instruction as "one duplicate of
Zipstack/unstract already catalogued in batch1 (a repost of the same
original tweet)" -- per this task's KNOWN_CONTEXT it is NOT re-added as a
repo row; it is recorded once in checked_no_repo as a dedup note instead.

Run: python3 ai-os-scripts/merge_xpost_github_catalog_batch3.py
"""
import os
import yaml

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(WORKSPACE_ROOT, "ai-os", "XPOST_GITHUB_CATALOG_2026-07-24.yaml")

BATCH3_INSTRUCTION_ID = "INS-20260724-095812-0523"
BATCH3_INSTRUCTION_TS = "2026-07-24T09:58:12.797465+00:00"
BATCH3_SESSION_ID = "x-post-github-catalog-batch3-2026-07-24"

# 8 new distinct repos from INS-20260724-095812-0523's raw_text, in the
# order the Owner's instruction lists them. No per-repo tweet URL was given
# in this instruction (aggregate "8 new distinct repos from 13 X post URLs",
# same as batch 2) -- source_tweet_url is intentionally left absent (None)
# rather than guessed.
BATCH3_REPOS = [
    {"repo_path": "Timeverse/My-TW-Coverage",
     "one_line_purpose": "Taiwan-listed companies knowledge graph (1,735 companies / 99 industries)."},
    {"repo_path": "TabularisDB/tabularis",
     "one_line_purpose": "Open-source desktop SQL workspace (Postgres/MySQL/MariaDB)."},
    {"repo_path": "comfyanonymous/ComfyUI",
     "one_line_purpose": "Node-based visual AI workflow engine (well-known)."},
    {"repo_path": "teambit/bit",
     "one_line_purpose": "AI-powered dev workspaces; reusable components for humans + agents."},
    {"repo_path": "DietrichGebert/ponytail",
     "one_line_purpose": "Reduces unnecessary AI-agent code output (claimed up to 94% less code).",
     "high_relevance": True,
     "high_relevance_reason": "Explicitly flagged in the instruction as RELEVANT to VERIDIAN's own token-cost concerns."},
    {"repo_path": "danny-avila/LibreChat",
     "one_line_purpose": "Self-hosted multi-provider AI chat platform."},
    {"repo_path": "andrewyng/openworker",
     "one_line_purpose": "Andrew Ng project: agent that delivers finished work, not just chat (notable)."},
    {"repo_path": "davidondrej/skills",
     "one_line_purpose": "Personal Claude Code skills collection."},
]

# The 5 no-repo-found/flagged entries in instruction INS-20260724-095812-0523
# -- kept as a record so a future re-check doesn't repeat the same lookup
# (same pattern as batch 1/2's CHECKED_NO_REPO). Includes the explicit
# Zipstack/unstract dedup (already catalogued in batch 1, not re-added) and
# the unverified "free-forever Claude Code router" claim, recorded rather
# than silently omitted per this task's SCOPE item 2.
BATCH3_CHECKED_NO_REPO = [
    {"checked_reference": "hugging-apps/wordvoice-tts + XXH333/WordVoice-base-0.5B",
     "reason": "Hugging Face TTS models, not GitHub repos."},
    {"checked_reference": "Claimed free-forever Claude Code router via free-tier providers",
     "reason": "No repo link surfaced in the thread. Flagged as UNVERIFIED and ToS-adjacent -- "
               "explicitly NOT to be treated as a recommended tool without further verification."},
    {"checked_reference": "GitHub-repo-visualization tool demo",
     "reason": "Name unconfirmed, no link surfaced."},
    {"checked_reference": "Screen-sharing app demo",
     "reason": "No name/link surfaced."},
    {"checked_reference": "Zipstack/unstract (reposted)",
     "reason": "Repost of the same original tweet already catalogued as Zipstack/unstract in "
               "batch 1 -- not re-added, per this task's KNOWN_CONTEXT. This is a dedup record only."},
]


def build_row(r, from_batch):
    row = {
        "repo_path": r["repo_path"],
        "one_line_purpose": r["one_line_purpose"],
        "source_tweet_url": None,
        "source_tweet_url_note": (
            "Not itemized per-repo in instruction " + BATCH3_INSTRUCTION_ID +
            "'s raw_text (aggregate: \"8 new distinct repos from 13 X post "
            "URLs\", no per-repo id given, same as batch 2) -- left null "
            "rather than guessed."
        ),
    }
    row["high_relevance"] = bool(r.get("high_relevance", False))
    if r.get("high_relevance_reason"):
        row["high_relevance_reason"] = r["high_relevance_reason"]
    row["batch"] = from_batch
    return row


def main():
    with open(CATALOG_PATH) as f:
        catalog = yaml.safe_load(f)

    existing_paths = {r["repo_path"] for r in catalog["repos"]}
    dupes = existing_paths & {r["repo_path"] for r in BATCH3_REPOS}
    if dupes:
        raise SystemExit(f"refusing to merge -- repo_path already present from a prior batch: {dupes}")

    new_rows = [build_row(r, 3) for r in BATCH3_REPOS]
    catalog["repos"].extend(new_rows)

    new_checked_no_repo = [
        {**c, "source_tweet_url": None, "batch": 3} for c in BATCH3_CHECKED_NO_REPO
    ]
    catalog.setdefault("checked_no_repo", []).extend(new_checked_no_repo)

    catalog["meta"]["repo_count"] = len(catalog["repos"])
    catalog["meta"]["checked_no_repo_count"] = len(catalog["checked_no_repo"])
    catalog["meta"]["total_source_tweet_urls"] = (
        catalog["meta"].get("total_source_tweet_urls", 37) + 13
    )
    catalog["meta"]["source_instructions"] = catalog["meta"].get("source_instructions", []) + [
        {
            "instruction_id": BATCH3_INSTRUCTION_ID,
            "ts": BATCH3_INSTRUCTION_TS,
            "session_id": BATCH3_SESSION_ID,
            "utm_source": "owner",
            "utm_medium": "task_gateway",
        },
    ]
    catalog["meta"]["batch3_merge"] = {
        "task": "task-20260724-095857-xpost-github-catalog-batch3-2026-07-24",
        "prior_catalog_search": (
            "knowledge_engine (query-knowledge for \"xpost github catalog\") + filesystem "
            "(ai-os/tasks tree, /opt/veridian/repos/claude-control) -- found exactly 1 "
            "existing catalog artifact (this file, KE-20260724-062517-e6b1), merged into "
            "in place, not duplicated."
        ),
        "repos_added": len(new_rows),
        "checked_no_repo_added": len(new_checked_no_repo),
        "dedup": "Zipstack/unstract reposted in the batch-3 source posts; already catalogued in "
                 "batch 1, not re-added -- recorded once in checked_no_repo as a dedup note.",
        "source_tweet_url_availability": (
            "Batch-3 instruction did not itemize a source_tweet_url per repo (aggregate count "
            "only, same as batch 2) -- every batch-3 row's source_tweet_url is null with an "
            "explanatory note, not fabricated."
        ),
        "unverified_claim_note": (
            "The instruction's claim of a 'free-forever Claude Code router via free-tier "
            "providers' surfaced no repo link -- recorded in checked_no_repo as UNVERIFIED / "
            "ToS-adjacent rather than silently omitted, and explicitly not to be treated as a "
            "recommended tool."
        ),
    }

    os.makedirs(os.path.dirname(CATALOG_PATH), exist_ok=True)
    with open(CATALOG_PATH, "w") as f:
        f.write("# Generated by ai-os-scripts/generate_xpost_github_catalog.py "
                "(batch 1) + ai-os-scripts/merge_xpost_github_catalog_batch2.py "
                "(batch 2) + ai-os-scripts/merge_xpost_github_catalog_batch3.py "
                "(batch 3) -- do not hand-edit.\n")
        yaml.dump(catalog, f, sort_keys=False, default_flow_style=False, width=100)

    print(f"merged {len(new_rows)} batch-3 repo rows + {len(new_checked_no_repo)} "
          f"batch-3 checked_no_repo rows into {CATALOG_PATH} "
          f"(total now: {catalog['meta']['repo_count']} repos, "
          f"{catalog['meta']['checked_no_repo_count']} checked_no_repo)")


if __name__ == "__main__":
    main()
