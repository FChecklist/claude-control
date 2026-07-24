-- VERIDIAN Auditor Engine -- Phase 7, pgAudit enablement migration.
--
-- Resolves the open question Phase 0/6 left unanswered: does the Owner's
-- Supabase plan tier support the pgaudit extension? REAL, LIVE CHECK this
-- phase via the Supabase MCP connector (list_extensions), not assumed:
--   - Org "MeetTrack" (gycrthstsbvkojggzkjk) plan = free.
--   - compliance-tracker's real project ("verdian-ai", pcrjmlpuqsbocqfwoxod,
--     ACTIVE_HEALTHY) lists pgaudit (default_version 17.1, installed_version
--     null) in its extension catalog.
--   - projexa's real project (evpckeuxgvahguwsaeul, ACTIVE_HEALTHY) lists
--     the same. Both are the actual cloud projects backing the deployed
--     apps -- confirmed distinct from the separate local `supabase start`
--     CLI dev-stack containers also running in Docker on this box
--     (supabase_db_projexa / supabase_db_verdian-ai, com.supabase.cli.project
--     labelled -- not the same thing).
-- ANSWER: yes, the free plan tier supports enabling pgaudit.
--
-- NOT YET RUN against either live production project by this phase. Per
-- this session's own risk-confirmation rule (modifying shared production
-- infrastructure needs explicit sign-off) and the exact precedent already
-- set in this same plan's OWNER_DECISIONS_NEEDED_2026-07-23.yaml file
-- (e.g. webhook-receiver-network-exposure), this migration is authored and
-- ready but gated on an Owner decision -- see the
-- pgaudit-enable-on-production-supabase entry added to that file this
-- phase. Apply via the Supabase MCP connector's apply_migration tool (or
-- the SQL editor) against project_id pcrjmlpuqsbocqfwoxod and
-- evpckeuxgvahguwsaeul once approved.

CREATE EXTENSION IF NOT EXISTS pgaudit;

-- pgaudit.log determines which statement classes are logged. 'write' logs
-- INSERT/UPDATE/DELETE/TRUNCATE (Phase 7's own event schema cross-references
-- these via audit_events.pgaudit_statement_id for DB-write events like
-- remediation_applied); 'ddl' logs schema changes (CREATE/ALTER/DROP), the
-- highest-value class for VERIDIAN's RLS-policy-heavy schemas per Phase 3's
-- own data-model domain findings. Deliberately NOT including 'role' or
-- 'misc' -- both are noisy for Supabase's own internal role-management
-- traffic and would drown the real signal.
ALTER DATABASE postgres SET pgaudit.log = 'write, ddl';
