#!/usr/bin/env python3
"""
Generates ai-os/XPOST_GITHUB_CATALOG_2026-07-24.yaml -- Knowledge Engine
reference-only catalog of the 34 GitHub repos in instruction
INS-20260724-060111-0975's repos_by_source_url list (task-20260724-060203).

ARCHIVE ONLY per Owner directive ("we will work on these after all existing
works is done") -- no cloning, no installing, no fit evaluation. Every
repo_path/one_line_purpose/source_tweet_url/high_relevance value below is a
mechanical transcription of the instruction's raw_text (read live from
superboss-register.sqlite's instructions table, instruction_id
INS-20260724-060111-0975), not re-derived or guessed.

Prior-batch search (per SCOPE item 1): the knowledge_engine table was
queried directly (see task PROGRESS.md) for any existing X-post-to-GitHub
catalog -- zero rows matched. A related but structurally different artifact
was found: ai-os/tasks/task-20260723-133902-x-post-ai-tool-analysis-2026-07-23-lowpr/
workspace/ai-os/X_POST_AI_ANALYSIS_2026-07-23.md (2026-07-23, 79 URLs / 80
repos, columns post_url/accessible/linked_github_repo/what_it_does). It was
never registered into knowledge_engine (confirmed by direct query) and uses
a different schema, so it is not merged in place; instead this file is the
first instance of the reference-only catalog schema this instruction asks
for, and cross-references that prior batch per-row via
also_seen_in_2026-07-23_batch for the 2 repos whose source tweet ID is an
EXACT match to a row in that prior batch (lharries/whatsapp-mcp,
themabhiram/WhatsApp-Message-Scheduler -- same x.com status ID in both
instructions), so a future re-check does not re-analyze those two tweets.

Run: python3 ai-os-scripts/generate_xpost_github_catalog.py
"""
import os
import yaml
from datetime import timezone

VERIDIAN_ROOT = "/opt/veridian"
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(WORKSPACE_ROOT, "ai-os", "XPOST_GITHUB_CATALOG_2026-07-24.yaml")

INSTRUCTION_ID = "INS-20260724-060111-0975"
INSTRUCTION_TS = "2026-07-24T06:01:11.216746+00:00"
SESSION_ID = "x-post-github-catalog-2026-07-24"

PRIOR_BATCH_PATH = (
    "ai-os/tasks/task-20260723-133902-x-post-ai-tool-analysis-2026-07-23-lowpr/"
    "workspace/ai-os/X_POST_AI_ANALYSIS_2026-07-23.md"
)

# One row per real repo in repos_by_source_url, in the order the Owner's
# instruction lists them. tweet_id is the bare x.com status id; the full
# source_tweet_url is derived from it (https://x.com/i/status/<id>).
REPOS = [
    {"repo_path": "lharries/whatsapp-mcp", "tweet_id": "1927339121120272553",
     "one_line_purpose": "WhatsApp MCP server (Go whatsmeow, SQLite, LLM tool access).",
     "high_relevance": False,
     "also_seen_in_2026-07-23_batch": True},
    {"repo_path": "themabhiram/WhatsApp-Message-Scheduler", "tweet_id": "2079760572279873817",
     "one_line_purpose": "Python CLI app that schedules WhatsApp messages for automatic sending.",
     "high_relevance": False,
     "also_seen_in_2026-07-23_batch": True},
    {"repo_path": "Zipstack/unstract", "tweet_id": "2080298505785217152",
     "one_line_purpose": "LLM-based document extraction to structured JSON.",
     "high_relevance": False},
    {"repo_path": "trimstray/the-practical-linux-hardening-guide", "tweet_id": "2080414148182032618",
     "one_line_purpose": "Practical Linux hardening guide.",
     "high_relevance": False},
    {"repo_path": "EdoStra/Marketing-for-Founders", "tweet_id": "2080361898554384384",
     "one_line_purpose": "Marketing guidance/resources for founders.",
     "high_relevance": False},
    {"repo_path": "LadybugDB/ladybug", "tweet_id": "2080288334434164945",
     "one_line_purpose": "Embeddable graph database, positioned as a Kuzu successor.",
     "high_relevance": False},
    {"repo_path": "headroomlabs-ai/headroom", "tweet_id": "2080251851673387488",
     "one_line_purpose": "AI agent cost reduction tool, ex-Netflix eng, 61k stars claimed.",
     "high_relevance": False},
    {"repo_path": "Nutlope/logocreator", "tweet_id": "2080209098356695301",
     "one_line_purpose": "AI logo creator.",
     "high_relevance": False},
    {"repo_path": "antonreshetov/mysigmail", "tweet_id": "2080433648038232434",
     "one_line_purpose": "Email signature generator.",
     "high_relevance": False},
    {"repo_path": "karam-ajaj/atlas", "tweet_id": "2080316104207999037",
     "one_line_purpose": "Network infrastructure visual mapping tool.",
     "high_relevance": False},
    {"repo_path": "razzant/claudexor", "tweet_id": "2080237028264857802",
     "one_line_purpose": "Orchestrates Claude Code + Codex + Cursor to cut token cost.",
     "high_relevance": True,
     "high_relevance_reason": "Explicitly flagged in the instruction as relevant to VERIDIAN's own multi-CLI cost control architecture."},
    {"repo_path": "victordibia/designing-multiagent-systems", "tweet_id": "2080497659706515845",
     "one_line_purpose": "PicoAgents framework for designing multi-agent systems.",
     "high_relevance": False},
    {"repo_path": "firezone/firezone", "tweet_id": "2080378559961448651",
     "one_line_purpose": "Zero-trust WireGuard-based VPN.",
     "high_relevance": False},
    {"repo_path": "RVC-Project/Retrieval-based-Voice-Conversion-WebUI", "tweet_id": "2080342417933312000",
     "one_line_purpose": "Retrieval-based voice conversion WebUI.",
     "high_relevance": False},
    # [2080232697365176510] = "TEN repos" tweet
    {"repo_path": "webadderallorg/recordly", "tweet_id": "2080232697365176510",
     "one_line_purpose": "Screen recorder app.",
     "high_relevance": False},
    {"repo_path": "Stirling-Tools/Stirling-PDF", "tweet_id": "2080232697365176510",
     "one_line_purpose": "Self-hosted PDF toolkit.",
     "high_relevance": False},
    {"repo_path": "Diolinux/PhotoGIMP", "tweet_id": "2080232697365176510",
     "one_line_purpose": "GIMP patch for a Photoshop-like layout.",
     "high_relevance": False},
    {"repo_path": "lfnovo/open-notebook", "tweet_id": "2080232697365176510",
     "one_line_purpose": "Self-hosted NotebookLM alternative.",
     "high_relevance": False},
    {"repo_path": "pewdiepie-archive/odysseus", "tweet_id": "2080232697365176510",
     "one_line_purpose": "Self-hosted AI workspace: chat + agents + research + docs + email + memory.",
     "high_relevance": False},
    {"repo_path": "DigitalPlatDev/FreeDomain", "tweet_id": "2080232697365176510",
     "one_line_purpose": "Free domain name registration service.",
     "high_relevance": False},
    {"repo_path": "heygen-com/hyperframes", "tweet_id": "2080232697365176510",
     "one_line_purpose": "HTML-to-video render engine, built for agents.",
     "high_relevance": False},
    {"repo_path": "shiaho777/web-to-app", "tweet_id": "2080232697365176510",
     "one_line_purpose": "Web-to-app converter.",
     "high_relevance": False},
    {"repo_path": "averygan/reclip", "tweet_id": "2080232697365176510",
     "one_line_purpose": "Video/audio downloader.",
     "high_relevance": False},
    {"repo_path": "excalidraw/excalidraw", "tweet_id": "2080232697365176510",
     "one_line_purpose": "Virtual whiteboard for hand-drawn-style diagrams.",
     "high_relevance": False},
    # [2080409368915501465] = "TEN repos" tweet
    {"repo_path": "mattpocock/skills", "tweet_id": "2080409368915501465",
     "one_line_purpose": "Package engine (skills).",
     "high_relevance": False},
    {"repo_path": "Nutlope/hallmark", "tweet_id": "2080409368915501465",
     "one_line_purpose": "Removes the AI-generated look from websites via 57 design checks.",
     "high_relevance": True,
     "high_relevance_reason": "Explicitly flagged in the instruction as relevant to a future VERIDIAN UX Audit Engine."},
    {"repo_path": "stablyai/orca", "tweet_id": "2080409368915501465",
     "one_line_purpose": "Orchestrates Claude Code + Codex + OpenCode.",
     "high_relevance": True,
     "high_relevance_reason": "Explicitly flagged in the instruction as relevant to VERIDIAN's own multi-CLI cost control architecture (same class as claudexor)."},
    {"repo_path": "Shubhamsaboo/awesome-llm-apps", "tweet_id": "2080409368915501465",
     "one_line_purpose": "100+ production AI app examples.",
     "high_relevance": False},
    {"repo_path": "tirth8205/code-review-graph", "tweet_id": "2080409368915501465",
     "one_line_purpose": "Codebase-to-dependency knowledge graph for AI-assisted code review.",
     "high_relevance": True,
     "high_relevance_reason": "Explicitly flagged in the instruction as relevant to VERIDIAN's Knowledge Engine entity-relationship work."},
    {"repo_path": "iOfficeAI/OfficeCLI", "tweet_id": "2080409368915501465",
     "one_line_purpose": "AI agents read/write Word/Excel/PowerPoint.",
     "high_relevance": False},
    {"repo_path": "HKUDS/Vibe-Trading", "tweet_id": "2080409368915501465",
     "one_line_purpose": "AI trading agent (Python/FastAPI backend, React frontend).",
     "high_relevance": False},
    {"repo_path": "earendil-works/pi", "tweet_id": "2080409368915501465",
     "one_line_purpose": "Lightweight multi-model AI agent toolkit.",
     "high_relevance": False},
    {"repo_path": "HKUDS/DeepTutor", "tweet_id": "2080409368915501465",
     "one_line_purpose": "Self-hosted AI tutor built from documents.",
     "high_relevance": False},
    {"repo_path": "openai/codex", "tweet_id": "2080409368915501465",
     "one_line_purpose": "Lightweight coding agent CLI from OpenAI.",
     "high_relevance": False},
]

# The 3 entries in repos_by_source_url that resolved to NONE (checked, no
# real GitHub repo) -- kept as a record so a future re-check of this X post
# thread doesn't repeat the same lookup.
CHECKED_NO_REPO = [
    {"tweet_id": "2080291430736744680",
     "reason": "TopviewAI MCP marketing product, paid/sponsored post -- no OSS repo."},
    {"tweet_id": "2080215848334332406",
     "reason": "huggingface.co AyaanAhmed123/Spark_one, Qwen2.5-Coder-3B finetune -- hosted on Hugging Face, not GitHub."},
    {"tweet_id": "2080412142243856718",
     "reason": "huggingface.co PaddlePaddle/HPD-Parsing doc-parsing VLM -- hosted on Hugging Face, not GitHub."},
]


def tweet_url(tweet_id):
    return f"https://x.com/i/status/{tweet_id}"


def build_catalog():
    repos_out = []
    for r in REPOS:
        row = {
            "repo_path": r["repo_path"],
            "one_line_purpose": r["one_line_purpose"],
            "source_tweet_url": tweet_url(r["tweet_id"]),
            "high_relevance": r["high_relevance"],
        }
        if r.get("high_relevance_reason"):
            row["high_relevance_reason"] = r["high_relevance_reason"]
        if r.get("also_seen_in_2026-07-23_batch"):
            row["also_seen_in_2026-07-23_batch"] = True
            row["note"] = (
                "Source tweet ID is an exact match to a row already analyzed in the "
                "2026-07-23 prior batch (" + PRIOR_BATCH_PATH + ") -- not re-fetched here."
            )
        repos_out.append(row)

    checked_no_repo_out = [
        {"source_tweet_url": tweet_url(c["tweet_id"]), "reason": c["reason"]}
        for c in CHECKED_NO_REPO
    ]

    return {
        "meta": {
            "id": "XPOST-GITHUB-CATALOG-2026-07-24",
            "generated_by": "ai-os-scripts/generate_xpost_github_catalog.py (re-run to refresh -- do not hand-edit)",
            "purpose": (
                "Reference-only archive of GitHub repos surfaced via X/Twitter posts, for "
                "future evaluation only. ARCHIVE ONLY per Owner directive -- no cloning, "
                "installing, evaluating fit, or integrating any of these repos as part of "
                "this task."
            ),
            "source_instruction": {
                "instruction_id": INSTRUCTION_ID,
                "ts": INSTRUCTION_TS,
                "session_id": SESSION_ID,
                "utm_source": "owner",
                "utm_medium": "task_gateway",
            },
            "repo_count": len(repos_out),
            "checked_no_repo_count": len(checked_no_repo_out),
            "total_source_tweet_urls": 19,
            "prior_batch_search": {
                "searched": "knowledge_engine table (superboss-register.sqlite) + ai-os/tasks tree",
                "found": True,
                "found_path": PRIOR_BATCH_PATH,
                "found_summary": (
                    "2026-07-23 X-post-to-GitHub analysis batch (79 URLs / 80 repos), "
                    "columns post_url/accessible/linked_github_repo/what_it_does -- a "
                    "different, narrative-analysis structure, not this reference-only "
                    "repo_path/one_line_purpose/source_tweet_url/high_relevance schema."
                ),
                "registered_in_knowledge_engine": False,
                "action_taken": (
                    "Not merged in place (different schema, never itself registered into "
                    "knowledge_engine -- confirmed via direct query, zero matching rows). "
                    "This file is the first instance of the reference-only catalog schema. "
                    "The 2 repos whose source tweet ID exactly matches a row in that prior "
                    "batch are cross-referenced per-row via also_seen_in_2026-07-23_batch "
                    "instead of being re-analyzed."
                ),
            },
        },
        "repos": repos_out,
        "checked_no_repo": checked_no_repo_out,
    }


def main():
    catalog = build_catalog()
    os.makedirs(os.path.dirname(CATALOG_PATH), exist_ok=True)
    with open(CATALOG_PATH, "w") as f:
        f.write("# Generated by ai-os-scripts/generate_xpost_github_catalog.py -- do not hand-edit.\n")
        yaml.dump(catalog, f, sort_keys=False, default_flow_style=False, width=100)
    print(f"wrote {len(catalog['repos'])} repo rows + {len(catalog['checked_no_repo'])} "
          f"checked_no_repo rows to {CATALOG_PATH}")


if __name__ == "__main__":
    main()
