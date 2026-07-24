#!/usr/bin/env python3
"""
Merges the 2nd X-post GitHub batch (instruction INS-20260724-091135-582a,
task-20260724-091206-xpost-github-catalog-batch2-2026-07-24) into
ai-os/XPOST_GITHUB_CATALOG_2026-07-24.yaml, in place, alongside the 34
repos already written by generate_xpost_github_catalog.py (batch 1,
INS-20260724-060111-0975).

ARCHIVE ONLY per Owner directive -- no cloning, installing, evaluating fit,
or integrating any of these repos as part of this task.

Scope-item-1 prior-catalog search (per this task's SCOPE): both the live
knowledge_engine table (superboss-register.sqlite, `search`/`query-knowledge`
for "xpost"/"github catalog") and the filesystem (ai-os/tasks tree +
/opt/veridian/repos/claude-control) were checked. Found: exactly one
existing artifact, this file, already registered as KE-20260724-062517-e6b1
with a KNOWN live-vs-repo split -- artifact_path (the "primary", hashed,
registered copy) is a snapshot inside the now-closed batch-1 task's own
workspace (ai-os/tasks/task-20260724-060203-xpost-github-catalog-2026-07-24/
workspace/ai-os/XPOST_GITHUB_CATALOG_2026-07-24.yaml), while secondary_path
is the live repo-tracked copy this script edits
(claude-control/ai-os/XPOST_GITHUB_CATALOG_2026-07-24.yaml, identical to
this task's own workspace copy of the same file since this task's workspace
is itself a fresh claude-control clone). This script deliberately edits only
the repo-tracked copy (the one that reaches origin/master via a real PR,
per this task's EXPECTED_OUTPUT) and leaves the closed batch-1 task's frozen
workspace snapshot untouched -- register_xpost_github_catalog_batch2.py
updates the EXISTING knowledge_engine row (add-tag/add-relationship/
annotate-knowledge, keyed by the original primary artifact_path) rather
than re-hashing that frozen snapshot or inserting a duplicate row.

Per the SPEC's KNOWN_CONTEXT: instruction INS-20260724-091135-582a's
raw_text (read live from superboss-register.sqlite, confirmed by direct
`search` query) gives repo_path + one-line description per repo, same as
batch 1 -- but, UNLIKE batch 1's raw_text (which bracketed an explicit
x.com status id per repo), batch 2's raw_text names an aggregate count
("19 new distinct repos from 18 X post URLs") without itemizing which URL
maps to which repo. No source_tweet_url is fabricated to fill that gap --
every batch-2 row's source_tweet_url is left null with a note explaining
why, consistent with this codebase's stated never-fabricate discipline
(see register_knowledge()'s own docstring: "falls back to null, never
fabricated, if it doesn't yet").

diegosouzapw/OmniRoute is named 3x within instruction INS-20260724-091135-582a's
own raw_text ("seen 3x across these posts") -- stored once here, with the
repeat count recorded on that one row (seen_count_in_source_posts), per this
task's KNOWN_CONTEXT instruction not to duplicate it.

Run: python3 ai-os-scripts/merge_xpost_github_catalog_batch2.py
"""
import os
import yaml

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(WORKSPACE_ROOT, "ai-os", "XPOST_GITHUB_CATALOG_2026-07-24.yaml")

BATCH2_INSTRUCTION_ID = "INS-20260724-091135-582a"
BATCH2_INSTRUCTION_TS = "2026-07-24T09:11:35.861673+00:00"
BATCH2_SESSION_ID = "x-post-github-catalog-batch2-2026-07-24"

# 19 new distinct repos from INS-20260724-091135-582a's raw_text, in the
# order the Owner's instruction lists them. No per-repo tweet URL was given
# in this instruction (unlike batch 1) -- source_tweet_url is intentionally
# left absent (None) rather than guessed.
BATCH2_REPOS = [
    {"repo_path": "VectifyAI/PageIndex",
     "one_line_purpose": "Vectorless reasoning RAG."},
    {"repo_path": "supermemoryai/supermemory",
     "one_line_purpose": "AI memory/context engine."},
    {"repo_path": "diegosouzapw/OmniRoute",
     "one_line_purpose": "231+ AI providers behind one endpoint.",
     "seen_count_in_source_posts": 3},
    {"repo_path": "asgeirtj/system_prompts_leaks",
     "one_line_purpose": "Leaked system prompts (Claude/GPT/Gemini/Grok/Cursor/Copilot)."},
    {"repo_path": "OpenCut-app/OpenCut",
     "one_line_purpose": "Open-source CapCut alternative, browser-based."},
    {"repo_path": "MadsLorentzen/ai-job-search",
     "one_line_purpose": "Claude-Code-powered job application agent."},
    {"repo_path": "zaid-maker/meetily",
     "one_line_purpose": "Local meeting transcription (Whisper+Ollama)."},
    {"repo_path": "usestrix/strix",
     "one_line_purpose": "AI-powered open-source vulnerability scanner."},
    {"repo_path": "superpowerlabs/superpower",
     "one_line_purpose": "Self-hosted AI workspace, 250k+ stars claimed."},
    {"repo_path": "mendableai/firecrawl",
     "one_line_purpose": "Website-to-LLM-ready-data, RAG standard."},
    {"repo_path": "pathwaycom/pathway",
     "one_line_purpose": "Python ETL for stream processing + RAG."},
    {"repo_path": "rasbt/LLM-workshop-2024",
     "one_line_purpose": "Hands-on PyTorch LLM-internals workshop."},
    {"repo_path": "Unstructured-IO/unstructured",
     "one_line_purpose": "PDF/email/scan to structured data for LLM pipelines."},
    {"repo_path": "Sanster/IOPaint",
     "one_line_purpose": "Self-hosted AI image inpainting/outpainting."},
    {"repo_path": "ifixai-ai/iFixAi",
     "one_line_purpose": "Catches AI agent mistakes/blind spots before customers do.",
     "high_relevance": True,
     "high_relevance_reason": "Explicitly flagged in the instruction as HIGH RELEVANCE to VERIDIAN's Testing Engine / Auditor Engine."},
    {"repo_path": "composio-community/awesome-codex-skills",
     "one_line_purpose": "Codex skills collection.",
     "high_relevance": True,
     "high_relevance_reason": "Explicitly flagged in the instruction as RELEVANT -- VERIDIAN already integrates Composio (compliance-tracker/src/lib/composio-connectors.ts)."},
    {"repo_path": "invoke-ai/InvokeAI",
     "one_line_purpose": "Locally-hosted Stable Diffusion creative environment."},
    {"repo_path": "DavidHDev/canvas-ui",
     "one_line_purpose": "React canvas UI components, WebGL."},
    {"repo_path": "lightningpixel/modly",
     "one_line_purpose": "Desktop image-to-3D-model app, local GPU."},
]

# The 4 entries in instruction INS-20260724-091135-582a that resolved to NO
# real GitHub repo -- kept as a record so a future re-check doesn't repeat
# the same lookup (same pattern as batch 1's CHECKED_NO_REPO).
BATCH2_CHECKED_NO_REPO = [
    {"checked_reference": "fdtn-ai/antares-350m",
     "reason": "Hugging Face model (code-vuln-detection), not GitHub."},
    {"checked_reference": "DavidAU Fable-Fusion",
     "reason": "Reddit discussion of a Hugging Face model merge -- no repo."},
    {"checked_reference": "untitled dev-log about a Gekai coding agent",
     "reason": "No repo link in the post."},
    {"checked_reference": "osp.fyi \"148 scientific skills for AI agents\" landing page",
     "reason": "No direct github.com link surfaced."},
]


def build_row(r, from_batch):
    row = {
        "repo_path": r["repo_path"],
        "one_line_purpose": r["one_line_purpose"],
    }
    if "tweet_id" in r:
        row["source_tweet_url"] = f"https://x.com/i/status/{r['tweet_id']}"
    else:
        row["source_tweet_url"] = None
        row["source_tweet_url_note"] = (
            "Not itemized per-repo in instruction " + BATCH2_INSTRUCTION_ID +
            "'s raw_text (aggregate: \"19 new distinct repos from 18 X post "
            "URLs\", no per-repo id given, unlike batch 1) -- left null rather "
            "than guessed."
        )
    row["high_relevance"] = bool(r.get("high_relevance", False))
    if r.get("high_relevance_reason"):
        row["high_relevance_reason"] = r["high_relevance_reason"]
    if r.get("also_seen_in_2026-07-23_batch"):
        row["also_seen_in_2026-07-23_batch"] = True
    if r.get("seen_count_in_source_posts"):
        row["seen_count_in_source_posts"] = r["seen_count_in_source_posts"]
        row["dedup_note"] = (
            f"Named {r['seen_count_in_source_posts']}x in instruction "
            f"{BATCH2_INSTRUCTION_ID}'s raw_text -- stored once here per "
            "this task's KNOWN_CONTEXT (not duplicated)."
        )
    row["batch"] = from_batch
    return row


def main():
    with open(CATALOG_PATH) as f:
        catalog = yaml.safe_load(f)

    existing_paths = {r["repo_path"] for r in catalog["repos"]}
    dupes = existing_paths & {r["repo_path"] for r in BATCH2_REPOS}
    if dupes:
        raise SystemExit(f"refusing to merge -- repo_path already present from batch 1: {dupes}")

    # Tag every pre-existing row with batch=1 for provenance, without
    # otherwise touching batch 1's rows.
    for row in catalog["repos"]:
        row.setdefault("batch", 1)
    for row in catalog.get("checked_no_repo", []):
        row.setdefault("batch", 1)

    new_rows = [build_row(r, 2) for r in BATCH2_REPOS]
    catalog["repos"].extend(new_rows)

    new_checked_no_repo = [
        {**c, "source_tweet_url": None, "batch": 2} for c in BATCH2_CHECKED_NO_REPO
    ]
    catalog.setdefault("checked_no_repo", []).extend(new_checked_no_repo)

    catalog["meta"]["repo_count"] = len(catalog["repos"])
    catalog["meta"]["checked_no_repo_count"] = len(catalog["checked_no_repo"])
    catalog["meta"]["total_source_tweet_urls"] = (
        catalog["meta"].get("total_source_tweet_urls", 19) + 18
    )
    catalog["meta"]["source_instructions"] = [
        catalog["meta"]["source_instruction"],
        {
            "instruction_id": BATCH2_INSTRUCTION_ID,
            "ts": BATCH2_INSTRUCTION_TS,
            "session_id": BATCH2_SESSION_ID,
            "utm_source": "owner",
            "utm_medium": "task_gateway",
        },
    ]
    catalog["meta"]["batch2_merge"] = {
        "task": "task-20260724-091206-xpost-github-catalog-batch2-2026-07-24",
        "prior_catalog_search": (
            "knowledge_engine (query-knowledge/search for xpost/github catalog) "
            "+ filesystem (ai-os/tasks tree, /opt/veridian/repos/claude-control) "
            "-- found exactly 1 existing catalog artifact (this file, "
            "KE-20260724-062517-e6b1), merged into in place, not duplicated."
        ),
        "repos_added": len(new_rows),
        "checked_no_repo_added": len(new_checked_no_repo),
        "dedup": "diegosouzapw/OmniRoute named 3x in the batch-2 instruction, stored once (see its row's seen_count_in_source_posts).",
        "source_tweet_url_availability": (
            "Batch-2 instruction did not itemize a source_tweet_url per repo "
            "(unlike batch 1) -- every batch-2 row's source_tweet_url is null "
            "with an explanatory note, not fabricated."
        ),
    }

    os.makedirs(os.path.dirname(CATALOG_PATH), exist_ok=True)
    with open(CATALOG_PATH, "w") as f:
        f.write("# Generated by ai-os-scripts/generate_xpost_github_catalog.py "
                "(batch 1) + ai-os-scripts/merge_xpost_github_catalog_batch2.py "
                "(batch 2) -- do not hand-edit.\n")
        yaml.dump(catalog, f, sort_keys=False, default_flow_style=False, width=100)

    print(f"merged {len(new_rows)} batch-2 repo rows + {len(new_checked_no_repo)} "
          f"batch-2 checked_no_repo rows into {CATALOG_PATH} "
          f"(total now: {catalog['meta']['repo_count']} repos, "
          f"{catalog['meta']['checked_no_repo_count']} checked_no_repo)")


if __name__ == "__main__":
    main()
