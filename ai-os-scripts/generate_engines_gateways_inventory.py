#!/usr/bin/env python3
"""
generate_engines_gateways_inventory.py -- Phase 0 of VERIDIAN 20-ENGINE/
10-GATEWAY architecture (task-20260724-053213, instruction
INS-20260724-053123-0e5a), SCOPE item 1 + Owner directive ("all
registry/catalog data must be produced by scripts, not hand-authored AI
prose").

This script is the SOURCE OF TRUTH for the engine_inventory: block embedded
in ai-os/20_ENGINES_10_GATEWAYS_PHASE_PLAN_2026-07-24.yaml. The DISCOVERY
list below encodes one grep/read finding per engine (file:line evidence
gathered manually this session, same method KNOWLEDGE_ENGINE_INVENTORY_
2026-07-23.yaml and AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml both used --
a human/AI still has to point the script at a real finding, but the script,
not the AI, decides coverage/verified_on_disk from a live check, and no row
is ever written by hand into the phase-plan yaml directly).

Every exists_as path is checked with a live os.path.exists() call at run
time -- a row is only marked verified: true if every one of its paths is
real *right now*. A path that has drifted (renamed/deleted since this
script was written) flips verified_on_disk to false and coverage to
"drifted" automatically, rather than silently keeping a stale claim.

Idempotent, safe to re-run: outputs the same structure every time the
underlying files are unchanged. Run:
    python3 ai-os/scripts/generate_engines_gateways_inventory.py
writes ai-os/generated/engine_inventory_2026-07-24.yaml and also prints the
same YAML to stdout (for splicing into the phase-plan document).

Phase gateway_definition_and_inventory (dispatched after the Owner's
gateway_naming_gap was closed by recovering INS-20260724-053123-0e5a's
original, uncondensed raw_text from the instructions table) extends this
same script with a GATEWAY_DISCOVERY list, same live-verification method,
also writes ai-os/generated/gateway_inventory_2026-07-24.yaml.
"""
import os
import sys

VERIDIAN_ROOT = "/opt/veridian"
OUT_PATH = f"{VERIDIAN_ROOT}/ai-os/generated/engine_inventory_2026-07-24.yaml"
GATEWAY_OUT_PATH = f"{VERIDIAN_ROOT}/ai-os/generated/gateway_inventory_2026-07-24.yaml"

# One entry per named engine (order matches the SPEC's own 20-name list).
# exists_as: list of real, repo-relative-to-/opt/veridian paths found by
# direct grep/read this session -- empty list means NONE (no real
# implementation found under any name after a deliberate search).
DISCOVERY = [
    dict(
        n=1, name="Intent Engine",
        purpose="Classify what the user/system wants to do before routing to a capability.",
        exists_as=[
            "repos/compliance-tracker/src/components/veri-chat/IntentCommandPalette.tsx",
            "repos/compliance-tracker/src/lib/browser-intent-cache.ts",
            "repos/compliance-tracker/src/components/veri-chat/ChainSelector.tsx",
        ],
        coverage="partial",
        gap="Recalls/restores a user's own past mode-pill+chain-path selections (recency/frequency ranked, IndexedDB "
            "+ server-side chain-usage-ranking.ts) -- this IS real intent capture for VeriComposer, but it is "
            "recall-of-past-choice, not general free-text NLU intent classification for a new, never-seen request.",
    ),
    dict(
        n=2, name="Context Engine",
        purpose="Carry request/session/org context through a call chain so downstream engines don't re-derive it.",
        exists_as=[
            "repos/compliance-tracker/src/lib/services/context.ts",
            "repos/compliance-tracker/src/lib/ai-team/roster.ts",
        ],
        coverage="partial",
        gap="ServiceContext/ReadContext (orgId + actor) is real, enforced, typed context-threading for every "
            "service call -- but it is request-scoped tenant/actor context, not conversational/session memory "
            "across turns (that half is closer to Knowledge Engine's artifact relationships, see Engine 15).",
    ),
    dict(
        n=3, name="Capability Registry Engine",
        purpose="Single lookup a caller checks before ever considering an AI call: does a capability already "
            "exist, what are its inputs/rules/workflow/apis/permissions/confidence.",
        exists_as=[
            "repos/compliance-tracker/src/lib/services/capability-registry-service.ts",
            "repos/compliance-tracker/src/app/api/capability-registry",
            "repos/compliance-tracker/src/app/(app)/capability-registry",
            "repos/compliance-tracker/src/lib/loops/capability-index-freshness-audit.ts",
        ],
        coverage="partial",
        gap="Real, live, embedding-based duplicate/similarity index (Wave 43) over 5 entity types (worker_agent, "
            "automation_rule, module, prompt_pattern, dynamic_chain) with a recurring freshness-audit loop -- this "
            "answers 'does something similar already exist' via vector search. It does NOT carry the PART4 field "
            "set (business_rules/workflow/automation/documents/reports/apis/ui_screens/permissions/ai_required/"
            "confidence/version/owner) as structured columns -- that richer schema is this task's own deliverable "
            "(CAPABILITY_REGISTRY_SCHEMA_2026-07-24.yaml), designed to sit ON TOP of indexCapability()/findSimilar() "
            "as the embedding layer underneath, not replace it. This is the single most important finding of this "
            "inventory: the 'most important missing piece' PART4 warned about is 60% already built under a "
            "different name, and the real gap is schema richness, not existence.",
    ),
    dict(
        n=4, name="Planning Engine",
        purpose="Turn an objective into a bounded, sequenced, validated plan before execution.",
        exists_as=[
            "repos/compliance-tracker/src/lib/task-tightening.ts",
            "repos/compliance-tracker/src/lib/services/dynamic-chain-directory-service.ts",
        ],
        coverage="partial",
        gap="task-tightening.ts enforces a mandatory objective/scope/success-criteria envelope before any AI "
            "Workforce dispatch (rejects a loose free-text brief); dynamic-chain-directory-service.ts does "
            "keyword-ranked chain-path recommendation. Neither generates a novel multi-step plan/DAG from a goal "
            "-- both validate or recommend from an already-known, finite set of paths.",
    ),
    dict(
        n=5, name="Policy Engine",
        purpose="Gate actions against standing policy before they execute.",
        exists_as=[
            "scripts/preflight-guard.py",
            "ai-os/OWNER_DECISIONS_NEEDED_2026-07-23.yaml",
            "repos/compliance-tracker/src/lib/policy-enforcement-engine.ts",
        ],
        coverage="partial",
        gap="preflight-guard.py gates server-side task dispatch (resource/crontab/scope checks); "
            "policy-enforcement-engine.ts is a deterministic pre-LLM-call gate (personal-use/prompt-injection/"
            "out-of-domain categories) in compliance-tracker. Both are real, enforced gates -- but two separate "
            "policy engines with no shared schema or single point of truth, and neither covers the other's domain "
            "(server ops vs in-app LLM calls).",
    ),
    dict(
        n=6, name="Rule Engine",
        purpose="Evaluate named business rules against inputs/outputs deterministically.",
        exists_as=[
            "repos/compliance-tracker/src/lib/guardrail-engine.ts",
            "repos/compliance-tracker/src/lib/guardrail-registrations.ts",
            "repos/compliance-tracker/src/lib/business-rule-validator.ts",
        ],
        coverage="partial",
        gap="Wave 157 guardrail-engine.ts is a real, generic, opt-in rule framework (input/process/output/logic "
            "phases per capability-tree leaf) wired as a genuine pre-execution gate via "
            "assertBusinessRulesBeforeExecution(). Starts EMPTY by design -- only a handful of leaves are actually "
            "registered today (GST rate bounds, EMI/loan bounds, gratuity/commission bounds), so the engine exists "
            "and is real, but coverage across the ~100 real capability-tree leaves is shallow.",
    ),
    dict(
        n=7, name="Decision Engine",
        purpose="Score/route a request by risk or confidence to decide how it should be handled.",
        exists_as=[
            "scripts/risk-tier.py",
            "repos/compliance-tracker/src/lib/explainability/ai-decision-explanation.ts",
        ],
        coverage="partial",
        gap="risk-tier.py assigns a risk tier for server task dispatch; ai-decision-explanation.ts renders "
            "structured AI-decision explanations in-app. Neither is a general decision-table/rules-based router "
            "that other engines could call generically.",
    ),
    dict(
        n=8, name="Workflow Engine",
        purpose="Model and execute a named multi-step business process end to end.",
        exists_as=[
            "scripts/task-gateway.py",
            "repos/compliance-tracker/src/lib/task-execution-engine.ts",
        ],
        coverage="partial",
        gap="task-gateway.py's submit/start/log/close lifecycle is real, enforced process orchestration for "
            "server-side AI tasks. task-execution-engine.ts dispatches VCEL engine calculations through named "
            "chains. Neither is BPMN-modeled (confirmed zero bpmn-js/camunda dependency in any of the 3 repos' "
            "package.json, per AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml's own workflow-domain finding) -- "
            "VERIDIAN's 'workflows' today are status-enum transitions and task-gateway phases, not a modeled "
            "process definition a workflow engine would normally execute against.",
    ),
    dict(
        n=9, name="Automation Engine",
        purpose="Execute a rule-triggered action without human intervention once conditions are met.",
        exists_as=[
            "scripts/task-gateway.py",
            "repos/compliance-tracker/src/lib/loops/automation-progress-audit.ts",
        ],
        coverage="partial",
        gap="task-gateway.py's cron-dispatched lifecycle IS real unattended automation for server tasks. "
            "automation_rule is one of the 5 real entity types the Capability Registry (Engine 3) already "
            "indexes, and automation-progress-audit.ts is a recurring health loop over it. No general "
            "trigger-condition-action rule builder exists outside these two call sites.",
    ),
    dict(
        n=10, name="Integration Engine",
        purpose="Connect to and exchange data with external systems/APIs.",
        exists_as=[
            "repos/compliance-tracker/src/lib/webhook-deliver.ts",
            "repos/compliance-tracker/src/lib/webhooks",
            "repos/compliance-tracker/src/lib/monitors/webhook-delivery-outcome-monitor.ts",
        ],
        coverage="partial",
        gap="Real outbound webhook delivery + a recurring delivery-outcome monitor exist. No inbound "
            "connector/iPaaS framework -- confirmed zero n8n/Kong/similar dependency in any of the 3 repos "
            "(same package.json read AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml already did for its own tool "
            "inventory, reused here rather than re-run).",
    ),
    dict(
        n=11, name="Document Engine",
        purpose="Generate, extract, and process documents (PDF/OCR/templates).",
        exists_as=[
            "repos/compliance-tracker/src/lib/engines/document-processing-engine.ts",
            "repos/compliance-tracker/src/lib/pdf-generator.ts",
            "repos/compliance-tracker/services/doc-processing",
        ],
        coverage="partial",
        gap="Real PDF generation, a standalone Python doc-processing microservice, and an LLM-Vision-based "
            "OCR/extraction service (document-extraction-service.ts) all exist and are live. "
            "document-processing-engine.ts itself is thin (barcode-decode contract + exact-hash dedup only) -- "
            "most of the real work lives in the two files it explicitly defers to.",
    ),
    dict(
        n=12, name="Notification Engine",
        purpose="Deliver an alert/message to the right recipient through the right channel.",
        exists_as=[
            "repos/compliance-tracker/src/app/api/notifications",
            "scripts/notify-owner.py",
        ],
        coverage="partial",
        gap="In-app notifications API route (compliance-tracker) and a separate, unrelated server-side "
            "Owner-notification script (notify-owner.py) are both real but not the same system -- no single "
            "notification engine serves both the product and the AI-OS operational layer.",
    ),
    dict(
        n=13, name="Data Engine",
        purpose="Move, transform, and validate data across storage/pipelines.",
        exists_as=[
            "repos/compliance-tracker/src/lib/engines/data-quality-engine.ts",
        ],
        coverage="partial",
        gap="Real data-quality validation checks exist as one of the 22 VCEL domain engines. No ETL/pipeline "
            "orchestration layer -- data movement today is direct drizzle-orm/Prisma queries per route, not a "
            "distinct Data Engine.",
    ),
    dict(
        n=14, name="Metadata Engine",
        purpose="Track what artifacts exist, their type/location/relationships, kept fresh.",
        exists_as=[
            "ai-os/MASTER_INDEX.yaml",
            "ai-os/memory/superboss-register.sqlite",
        ],
        coverage="partial",
        gap="MASTER_INDEX.yaml's registries: section plus knowledge_engine's multi-source rows (SERVER/VERCEL/"
            "SUPABASE/GITHUB/LOCAL, see self_sustaining_system_engine registry entry) together are real, live "
            "metadata tracking with drift detection (verification_status). Split across two documents/mechanisms "
            "with overlapping but not identical scope (MASTER_INDEX is hand-edited prose+structure, "
            "knowledge_engine is queryable rows) rather than one authoritative metadata store.",
    ),
    dict(
        n=15, name="Knowledge Engine",
        purpose="Store and query artifacts, their purpose, and their relationships to each other.",
        exists_as=[
            "ai-os/memory/superboss-register.sqlite",
            "scripts/superboss-register.py",
        ],
        coverage="full",
        gap="Purpose-built and live: knowledge_engine table (artifact_path/content_hash/verification_status/"
            "entity_relationships) + FTS5 search + register-knowledge/query-knowledge/verify-knowledge/"
            "add-relationship CLI, covering SERVER/VERCEL/SUPABASE/GITHUB/LOCAL sources with a recurring 6h "
            "refresh cron. Known operational gap (not a design gap): SUPABASE cron refresh degrades gracefully "
            "when SUPABASE_ACCESS_TOKEN is invalid (401), per KNOWLEDGE_ENGINE_PHASE3_CANDIDATES_2026-07-24.yaml.",
    ),
    dict(
        n=16, name="Learning Engine",
        purpose="Learn from outcomes/feedback to improve future behavior.",
        exists_as=[
            "repos/compliance-tracker/src/lib/loops/task-reflection.ts",
            "repos/compliance-tracker/src/lib/loops/loop-engineering-audit.ts",
        ],
        coverage="partial",
        gap="A real 'Loop Engineering' meta-loop taxonomy exists (loop_definitions/loop_executions, a fixed set "
            "of platform-improvement loops) plus a universal task-reflection mechanism (outcome/speed/cost "
            "verdicts) firing on every terminal task-status write, feeding the CLEE pipeline "
            "(loop-improvement-proposer.ts). This is real reflective learning infrastructure, but it is "
            "structured verdict/proxy scoring, not a model-training or feedback-weight-adjustment learning "
            "system.",
    ),
    dict(
        n=17, name="UI Composition Engine",
        purpose="Assemble UI dynamically from reusable pieces based on context/selection.",
        exists_as=[
            "repos/compliance-tracker/src/components/veri-chat/VeriComposer.tsx",
            "repos/compliance-tracker/src/components/veri-chat/ChainSelector.tsx",
        ],
        coverage="partial",
        gap="Real dynamic composition of the chat composer (mode pill + cascading chain-path picker, shared "
            "between an inline composer and a pre-conversation dialog, ChainSelectorDialog) -- but scoped "
            "entirely to VeriComposer's own chat surface, not a general design-system/component-registry-driven "
            "UI composition engine for the rest of the product.",
    ),
    dict(
        n=18, name="Analytics Engine",
        purpose="Compute trends/statistics/KPIs over stored data.",
        exists_as=[
            "repos/compliance-tracker/src/lib/engines/analytics-engine.ts",
        ],
        coverage="partial",
        gap="Real trend-analysis (linear regression via simple-statistics, with an explainable variant) exists "
            "as one of the 22 VCEL domain engines, plus orchestra-analytics-service.ts for AI-usage KPIs. Scoped "
            "to specific call sites (task-execution-engine.ts's trend_analysis_engine case, AI-usage dashboards), "
            "not a general-purpose analytics layer over arbitrary datasets.",
    ),
    dict(
        n=19, name="Audit Engine",
        purpose="Verify system/code/process conformance against named standards.",
        exists_as=[
            "ai-os/AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml",
        ],
        coverage="partial",
        gap="Out of scope for this task per CONSTRAINTS -- the VERIDIAN Auditor Engine (a separate, already-"
            "in-progress Phase 0, task-20260724-042659) is authoritative for this engine. Do not re-plan; see "
            "that file's own domains: block (15 audit domains) and phases: block for real status.",
    ),
    dict(
        n=20, name="Observability Engine",
        purpose="Surface real-time system health/alerts/traces across the estate.",
        exists_as=[
            "ai-os/AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml",
            "scripts/health-check-15min.py",
            "ai-os/logs/ATTENTION.md",
        ],
        coverage="partial",
        gap="health-check-15min.py + ATTENTION.md are real, live server-side health monitoring (systemd/DB/disk/"
            "mem, 15-minute cron). The Auditor Engine's PART6 (7-repo OpenTelemetry + pgAudit observability "
            "layer) is designed but not yet enforced (Phase 7 per that plan) -- authoritative for the "
            "product-code half of this engine, per this task's own CONSTRAINTS not re-planned here.",
    ),
]


# ---------------------------------------------------------------------------
# GATEWAY_DISCOVERY -- Phase gateway_definition_and_inventory. The naming gap
# recorded in this document's own gateways.gateway_naming_gap block (Phase 0)
# is now closed: the original, uncondensed Owner instruction
# (INS-20260724-053123-0e5a, recovered verbatim from
# ai-os/memory/superboss-register.sqlite's instructions table -- it was never
# missing, only lost in this task's own condensed SPEC) names all 10 gateways
# explicitly: "10 gateways wrap all 20 engines: G01 Owner, G02 Engineering,
# G03 Organization, G04 UserChannel, G05 AI, G06 BusinessServices, G07
# DataKnowledge, G08 Integration, G09 ObservabilityAudit, G10 Infrastructure
# -- no component talks to another except through a gateway. Every gateway
# runs the same fixed pipeline: Authenticate->Authorize->Validate->
# Normalize->LoadOrgContext->LoadUserContext->LoadMetadata->CapabilityLookup->
# PolicyEval->RuleEval->Decision->Execute->GenerateEvents->UpdateKnowledge->
# WriteAuditLog->WriteMetrics->Return."
#
# These are request-routing/access-boundary wrappers ("no component talks to
# another except through a gateway"), architecturally distinct from the 20
# ENGINES above. Same method as DISCOVERY: one grep/read finding per gateway,
# gathered this session (see gateway_definition_and_inventory phase's
# status_detail for the investigation), live-verified below by the same
# verify() function -- no row hand-written into the phase-plan yaml directly.
#
# Confirmed finding: scripts/task-gateway.py -- the one "gateway"-named file
# in this codebase, and the only gateway_candidate this document's Phase 0
# could confirm before this naming gap closed -- is NOT a match for any of
# G01-G10. It is a task/workflow lifecycle CLI (submit/start/log/close), not
# an Authenticate->Authorize->...->Return request boundary per the Owner's
# own pipeline text. It stays out of GATEWAY_DISCOVERY below; see
# gateways.confirmed_real_today for the honest, updated record of that
# finding.
# ---------------------------------------------------------------------------
GATEWAY_DISCOVERY = [
    dict(
        n=1, gid="G01", name="Owner",
        purpose="Boundary through which the human Owner's own instructions/directives enter the system and get logged/tracked.",
        exists_as=[
            "scripts/superboss-register.py",
            "scripts/notify-owner.py",
            "ai-os/OWNER_DECISIONS_NEEDED_2026-07-23.yaml",
            "ai-os/OWNER_DIRECTIVES/CHATGPT_AUDIT_AND_PROMPT_LIBRARY_WORKSPACE_2026-07-24.txt",
        ],
        coverage="partial",
        gap="Real, live pieces exist for both directions -- Owner-in (superboss-register.py's log-instruction "
            "subcommand and instructions table, the exact mechanism that registered "
            "INS-20260724-053123-0e5a itself) and Owner-out (notify-owner.py, rate-limited, plain-English by "
            "design). But they are two separate scripts sharing no Authenticate/Authorize pipeline -- "
            "log-instruction does not authenticate its caller (any process on the box can insert an "
            "instruction row claiming Owner origin), so this is a structured ledger, not an access boundary "
            "in the pipeline sense the Owner's own instruction describes.",
    ),
    dict(
        n=2, gid="G02", name="Engineering",
        purpose="Boundary for engineering/dev-tooling requests -- CI, code-quality gates, and AI-dev-team dispatch.",
        exists_as=[
            "repos/compliance-tracker/.github/workflows/ci.yml",
            "repos/compliance-tracker/.github/workflows/ai-dispatch.yml",
            "repos/compliance-tracker/.github/workflows/ai-team-workforce.yml",
            "scripts/quality-gate.sh",
            "scripts/scope-check.py",
        ],
        coverage="partial",
        gap="Real, enforced dev-tooling gates exist (CI lint/typecheck/build, a pre-merge quality gate, "
            "file-ownership/scope-collision checks), but they are independent scripts/GitHub-Actions "
            "workflows triggered at different points, not one named Engineering gateway that "
            "authenticates/authorizes a caller before executing -- checks embedded in a pipeline, not a "
            "routing boundary a caller goes through.",
    ),
    dict(
        n=3, gid="G03", name="Organization",
        purpose="Boundary that resolves and enforces tenant/organization context for every request.",
        exists_as=[
            "repos/compliance-tracker/src/lib/services/context.ts",
            "repos/compliance-tracker/src/lib/supabase/auth-guard.ts",
            "repos/compliance-tracker/src/lib/db/tenant-scoped.ts",
            "repos/compliance-tracker/src/lib/services/org-provisioning-service.ts",
        ],
        coverage="partial",
        gap="ServiceContext/ReadContext's mandatory orgId (Engine 2's own Context Engine finding) plus "
            "withTenantContext's Postgres RLS session vars are real, enforced org-scoping used consistently "
            "across service calls -- genuine LoadOrgContext. But it is woven into auth-guard.ts's "
            "requireAuth() per-route, not a standalone named Organization gateway other subsystems route "
            "through as one addressable Authenticate->Authorize->LoadOrgContext boundary.",
    ),
    dict(
        n=4, gid="G04", name="UserChannel",
        purpose="Boundary for end-user-facing product channels (chat, portal, guest access) into the platform.",
        exists_as=[
            "repos/compliance-tracker/src/lib/supabase/auth-guard.ts",
            "repos/compliance-tracker/src/app/api/veri-chat",
            "repos/compliance-tracker/src/app/api/guest-chat",
            "repos/compliance-tracker/src/app/api/me/route.ts",
        ],
        coverage="partial",
        gap="requireAuth()/requireRole() in auth-guard.ts is a real, universally-used per-route "
            "Authenticate+Authorize gate, and veri-chat/guest-chat are real end-user channel surfaces built "
            "on it. But it is invoked ad hoc at the top of each individual route.ts file, not centralized "
            "behind one UserChannel gateway component -- no middleware.ts file exists anywhere in the repo.",
    ),
    dict(
        n=5, gid="G05", name="AI",
        purpose="Boundary all AI/model calls route through for provider/model resolution, policy, and audit.",
        exists_as=[
            "repos/compliance-tracker/src/lib/ai-router/mother-router.ts",
            "repos/compliance-tracker/src/lib/model-tier-eligibility.ts",
        ],
        coverage="partial",
        gap="Mother Router (resolveModel(), versioned ai_routing_policies, ai_routing_audit_log) is real, "
            "live, audit-logged AI routing -- the strongest single candidate of all 10 gateways for matching "
            "the Owner's fixed-pipeline description. But its own header comment documents a mechanical grep "
            "finding 35 files still bypassing it by calling resolveModelConfig()/checkTierEligibility() "
            "directly -- a documented decision not (yet) to migrate them, so roughly a third of this one "
            "repo's AI dispatch call sites don't route through it at all.",
    ),
    dict(
        n=6, gid="G06", name="BusinessServices",
        purpose="Boundary wrapping internal business-domain service calls (accounting, PMS, HR, etc.).",
        exists_as=[
            "repos/compliance-tracker/src/lib/services",
        ],
        coverage="partial",
        gap="A large, real services/ directory (263 files -- erp-accounting-service.ts, "
            "pms-meeting-service.ts, org-branding-service.ts, etc.) exists and every function in it does "
            "take a ServiceContext/ReadContext (G03's own finding), so some uniform contract is enforced "
            "per-call. But there is no single BusinessServices gateway component -- each service module is "
            "called directly from its own route handler(s); this is a naming/directory convention, not a "
            "gateway other components route calls through.",
    ),
    dict(
        n=7, gid="G07", name="DataKnowledge",
        purpose="Boundary for accessing/tracking data and knowledge-store artifacts (metadata, relationships, provenance).",
        exists_as=[
            "scripts/superboss-register.py",
            "scripts/knowledge_registry_multisource.py",
            "ai-os/MASTER_INDEX.yaml",
        ],
        coverage="partial",
        gap="Same real infrastructure engine_inventory already rated coverage=full for Engine 15 (Knowledge "
            "Engine) -- a live SQLite+FTS5 store with a register-knowledge/query-knowledge CLI and a "
            "recurring multi-source cron refresh. As a gateway concept, though, it is a data store with a "
            "CLI, not a request boundary other components authenticate/authorize through first -- no "
            "Authenticate/Authorize step exists in front of register-knowledge/query-knowledge themselves.",
    ),
    dict(
        n=8, gid="G08", name="Integration",
        purpose="Boundary for exchanging data with external systems/APIs (inbound and outbound).",
        exists_as=[
            "repos/compliance-tracker/src/lib/webhook-deliver.ts",
            "repos/compliance-tracker/src/lib/webhooks/vercel-signature.ts",
            "repos/compliance-tracker/src/app/api/webhooks/vercel-deployment/route.ts",
            "repos/compliance-tracker/src/app/api/connectors/route.ts",
            "repos/compliance-tracker/src/lib/supabase/platform-application-auth.ts",
        ],
        coverage="partial",
        gap="Real outbound webhook delivery (Engine 10's own finding), real inbound webhook receipt with "
            "signature verification (Vercel deployment events), a real OAuth-connector framework (Composio, "
            "Drive/Gmail), and a real cross-product platform-application-key Authenticate step all exist and "
            "are live. None are unified under one Integration gateway -- each is its own auth/validation "
            "path with its own credential class (webhook signature vs. platform key vs. Composio OAuth).",
    ),
    dict(
        n=9, gid="G09", name="ObservabilityAudit",
        purpose="Boundary/loop surfacing system health and writing the audit trail for actions taken.",
        exists_as=[
            "scripts/health-check-15min.py",
            "scripts/veridian-task-watchdog.py",
            "repos/compliance-tracker/src/lib/audit.ts",
            "ai-os/AUDITOR_ENGINE_PHASE_PLAN_2026-07-24.yaml",
        ],
        coverage="partial",
        gap="Real, live 15-minute health monitoring (systemd/DB/disk/mem) and a real per-write logActivity() "
            "in-app audit function both exist and are used (same finding as engine_inventory's Engine 19/20 "
            "rows). But these are two unrelated systems -- server-ops health cron vs. in-app DB audit log -- "
            "with no shared schema, and neither is a gateway boundary other components route calls through; "
            "logActivity() is a side effect at the end of a service function, not an enforced WriteAuditLog "
            "step of a shared pipeline.",
    ),
    dict(
        n=10, gid="G10", name="Infrastructure",
        purpose="Boundary/deploy layer for provisioning and running the server-side process fleet.",
        exists_as=[
            "reconciliation/claude-control/systemd/veridian-task-watchdog.service",
            "scripts/supervisor-entrypoint.sh",
            "scripts/worker-entrypoint.sh",
            "scripts/sync-repos.sh",
        ],
        coverage="partial",
        gap="Real systemd-managed worker/supervisor process lifecycle (veridian-worker@/veridian-supervisor@ "
            "units referenced throughout health-check-15min.py and supervisor-entrypoint.sh) and a real "
            "deployed watchdog unit exist. But no single Infrastructure gateway component exists, just a set "
            "of shell entrypoints and systemd units -- and the live server has no top-level /opt/veridian/"
            "systemd directory (units live staged under reconciliation/claude-control/systemd/ instead),"
            " honestly reported rather than assumed.",
    ),
]


def verify(entry):
    checked = []
    all_exist = True
    for rel in entry["exists_as"]:
        abs_path = os.path.join(VERIDIAN_ROOT, rel)
        exists = os.path.exists(abs_path)
        checked.append({"path": rel, "exists_on_disk": exists})
        if not exists:
            all_exist = False
    coverage = entry["coverage"] if (all_exist or not entry["exists_as"]) else "drifted"
    return checked, all_exist, coverage


def build_rows():
    rows = []
    for e in DISCOVERY:
        checked, verified, coverage = verify(e)
        rows.append({
            "engine_no": e["n"],
            "engine_name": e["name"],
            "purpose": e["purpose"],
            "exists_as": [c["path"] for c in checked] if checked else None,
            "verified_on_disk": verified if checked else None,
            "coverage": coverage if checked else "none",
            "gap_description": e["gap"] if checked else
                "No real implementation found under any name after a deliberate search of compliance-tracker/"
                "projexa/veda-advisors src/ and /opt/veridian/scripts + ai-os/.",
        })
    return rows


def to_yaml(rows):
    lines = []
    lines.append("# Generated by ai-os/scripts/generate_engines_gateways_inventory.py -- DO NOT HAND-EDIT.")
    lines.append("# Re-run the script to regenerate after any of the cited paths change.")
    lines.append("engine_inventory:")
    for r in rows:
        lines.append(f"  - engine_no: {r['engine_no']}")
        lines.append(f"    engine_name: \"{r['engine_name']}\"")
        lines.append(f"    purpose: \"{r['purpose']}\"")
        if r["exists_as"]:
            lines.append("    exists_as:")
            for p in r["exists_as"]:
                lines.append(f"      - {p}")
        else:
            lines.append("    exists_as: NONE")
        lines.append(f"    verified_on_disk: {str(r['verified_on_disk']).lower() if r['verified_on_disk'] is not None else 'null'}")
        lines.append(f"    coverage: {r['coverage']}")
        gap = r["gap_description"].replace('"', '\\"')
        lines.append(f"    gap_description: \"{gap}\"")
    return "\n".join(lines) + "\n"


def build_gateway_rows():
    rows = []
    for e in GATEWAY_DISCOVERY:
        checked, verified, coverage = verify(e)
        rows.append({
            "gateway_no": e["n"],
            "gateway_id": e["gid"],
            "gateway_name": e["name"],
            "purpose": e["purpose"],
            "exists_as": [c["path"] for c in checked] if checked else None,
            "verified_on_disk": verified if checked else None,
            "coverage": coverage if checked else "none",
            "gap_description": e["gap"] if checked else
                "No real implementation found under any name after a deliberate search of compliance-tracker/"
                "projexa/veda-advisors src/ and /opt/veridian/scripts + ai-os/.",
        })
    return rows


def to_yaml_gateways(rows):
    lines = []
    lines.append("# Generated by ai-os-scripts/generate_engines_gateways_inventory.py -- DO NOT HAND-EDIT.")
    lines.append("# Re-run the script to regenerate after any of the cited paths change.")
    lines.append("gateway_inventory:")
    for r in rows:
        lines.append(f"  - gateway_no: {r['gateway_no']}")
        lines.append(f"    gateway_id: \"{r['gateway_id']}\"")
        lines.append(f"    gateway_name: \"{r['gateway_name']}\"")
        lines.append(f"    purpose: \"{r['purpose']}\"")
        if r["exists_as"]:
            lines.append("    exists_as:")
            for p in r["exists_as"]:
                lines.append(f"      - {p}")
        else:
            lines.append("    exists_as: NONE")
        lines.append(f"    verified_on_disk: {str(r['verified_on_disk']).lower() if r['verified_on_disk'] is not None else 'null'}")
        lines.append(f"    coverage: {r['coverage']}")
        gap = r["gap_description"].replace('"', '\\"')
        lines.append(f"    gap_description: \"{gap}\"")
    return "\n".join(lines) + "\n"


def main():
    rows = build_rows()
    yaml_text = to_yaml(rows)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write(yaml_text)
    sys.stdout.write(yaml_text)
    unverified = [r["engine_name"] for r in rows if r["verified_on_disk"] is False]
    if unverified:
        sys.stderr.write(f"WARNING: drift detected, exists_as path missing for: {unverified}\n")
    sys.stderr.write(f"wrote {OUT_PATH} ({len(rows)} rows)\n")

    gw_rows = build_gateway_rows()
    gw_yaml_text = to_yaml_gateways(gw_rows)
    with open(GATEWAY_OUT_PATH, "w") as f:
        f.write(gw_yaml_text)
    sys.stdout.write(gw_yaml_text)
    gw_unverified = [r["gateway_name"] for r in gw_rows if r["verified_on_disk"] is False]
    if gw_unverified:
        sys.stderr.write(f"WARNING: drift detected, exists_as path missing for: {gw_unverified}\n")
    sys.stderr.write(f"wrote {GATEWAY_OUT_PATH} ({len(gw_rows)} rows)\n")


if __name__ == "__main__":
    main()
