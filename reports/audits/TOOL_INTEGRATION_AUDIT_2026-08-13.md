# Real tool-integration audit — 2026-08-13

**Governing chain:** addendum to P1 `UMR-20260806-171945-5767`, parent `UMR-20260813-042145-7cc0`
(itself an addendum to P1, see its `STATUS_REPORT.md`). This dispatch: `UMR-20260813-050029-ecba`.

Every claim below is from a live command run today (2026-08-13, ~05:05-05:20 UTC) against the
real host — `systemctl`, `which`, `pip show`, `npm ls`, `docker ps`, `psql`, `curl`. Nothing is
carried forward from the 2026-08-08 findings without re-verification, per the dispatch SPEC.
No certification without the boolean evidence shown.

## (a) Boolean install-state table

| # | Item | Verdict | Real evidence |
|---|---|---|---|
| 1 | **earlyoom** | **INSTALLED-WORKING** | `dpkg -l`: `ii earlyoom 1.7-2 amd64`. `systemctl is-active earlyoom` → `active`; `is-enabled` → `enabled`. |
| 2 | **Cockpit** | **INSTALLED-WORKING** | `dpkg -l`: `cockpit 314-1` + 6 `cockpit-*` sub-packages (bridge/networkmanager/packagekit/storaged/system/ws). `cockpit.socket` is `active (listening)` on `[::]:9091` (not the 9090 default — confirmed via `systemctl --no-pager status`). Live `curl -sk https://localhost:9091` → HTTP **200**. |
| 3 | **Grafana** | **INSTALLED-WORKING** | Not an apt/systemd install — deployed via `/opt/veridian/monitoring/docker-compose.yml`. `docker ps`: `veridian_grafana` (`grafana/grafana:latest`) `Up 2 hours`, port `127.0.0.1:3000`. `curl http://127.0.0.1:3000/api/health` → `{"database":"ok","version":"13.1.3"}`. `GET /api/datasources` confirms a real configured **Prometheus** datasource (id=1). Directly contradicts the 2026-08-08 "Grafana down" finding — it is up now. |
| 4 | **Prometheus** | **INSTALLED-WORKING** | Same compose file, `veridian_prometheus` `Up 2 hours`. `curl http://127.0.0.1:9090/-/healthy` → **200**. `GET /api/v1/targets` shows real active scrape targets (`cadvisor`, `node`) with `"health":"up"`. |
| 5 | **node_exporter** | **INSTALLED-WORKING** | Same compose file, `veridian_node_exporter` `Up 2 hours`, host network mode. `curl http://127.0.0.1:9100/metrics` → **200**. Confirmed scraped by Prometheus as job `node`, health `up`. |
| 6 | **pgvector** | **INSTALLED-WORKING** | The app's real `DATABASE_URL` (compliance-tracker `.env.local`) points at the managed Supabase Postgres project `pcrjmlpuqsbocqfwoxod.supabase.co`, not a local container. Live `psql "$DATABASE_URL" -c "SELECT extname, extversion FROM pg_extension WHERE extname='vector'"` → **`vector 0.8.0`**, reachable. 15 real `vector`-typed columns in production schemas (`compliance.embeddings`, `compliance.embedding_cache`, `compliance.compliance_items`, `compliance.tasks.task_embedding`, `platform.worker_agents.{capability_embedding,knowledge_embedding}`, etc.). Live row counts: `compliance.embeddings` = **143 rows**, `compliance.embedding_cache` = **27 rows** — real data, not just an empty schema. Directly contradicts the 2026-08-08 "pgvector unreachable" finding. *(Side note, not the load-bearing DB: 2 local Docker Supabase dev stacks also exist — `supabase_db_projexa` has **no** vector extension; `supabase_db_verdian-ai` has `vector 0.8.2` installed but 0 vector columns in use. Neither is what the app actually talks to.)* |
| 7 | **Zoekt** | **INSTALLED-WORKING** | `~/go/bin/{zoekt,zoekt-index,zoekt-webserver}` present (built 2026-08-08). `systemctl --user status veridian-zoekt-webserver.service` → `active (running)`, `enabled`, PID 1218, listening `127.0.0.1:6070`; companion `veridian-cron-zoekt-reindex.{service,timer}` also `enabled`. Real index: 9 shards under `/opt/veridian/.zoekt-index` covering `compliance-tracker`, `scripts`, `veridian-scripts`, `claude-control`, freshly reindexed **today** (04:00-04:01 UTC). Live query `curl http://127.0.0.1:6070/search?q=VERIDIAN` returns real HTML search results. Already wired into `scripts/task-gateway.py`'s `run_zoekt_search()`, with a real, fail-open test suite (`scripts/tests/test_task_gateway_zoekt_search.py`, includes a live-service test). Directly contradicts the 2026-08-08 "Zoekt never installed" finding. |
| 8 | **aider-chat** | **INSTALLED-WORKING (but currently unwired)** | `pip show aider-chat` → `Version: 0.86.2`, binary at `~/.local/bin/aider`. Live `aider --version` → `aider 0.86.2`. **Caveat**: `find_code.sh "aider"` across `/opt/veridian/scripts` and `/opt/veridian/ai-os` finds **zero** real callers — it is installed and functional but not invoked by any dispatch/orchestration path today. Distinct from "broken"; it's dormant. |
| 9 | **claude-orchestra (MIT, GitHub)** | **NOT-INSTALLED** | No `/opt/veridian/repos/*orchestra*` clone (full repo listing checked). No global/local npm package (`npm ls -g --depth=0` — only `@anthropic-ai/claude-code`, `corepack`, `npm`, `vercel`). No pip package. No citation in `MASTER_INDEX.yaml`, `wiring_registry`, or `capability_registry` (`check-duplicate` fuzzy search returned 230 unrelated hits, none naming this tool). The name is also ambiguous — multiple unrelated GitHub projects could match "claude-orchestra"; no canonical repo URL has been confirmed anywhere in this system's records. |
| 10 | **graft** | **NOT-INSTALLED** | No `which graft`. No pip/npm/cargo package (cargo not installed at all; `pip3 list`/`npm ls -g` both empty for this name). No `/opt/veridian/repos/graft*` clone. No registry citation (`check-duplicate` returned 41 unrelated fuzzy hits — mostly false positives on unrelated filenames — none naming a "graft" tool). Same ambiguity risk as above: multiple real OSS projects share this name (a schema-migration tool, a distributed SQLite replication engine, etc.) — no canonical URL on record. |

## 20 engines + metadata — cited from the real registry, not hand-enumerated

Per `MASTER_INDEX.yaml` `registries.engines_gateways_architecture` (path:
`ai-os/20_ENGINES_10_GATEWAYS_PHASE_PLAN_2026-07-24.yaml` +
`ai-os/CAPABILITY_REGISTRY_SCHEMA_2026-07-24.yaml`): **19/20 partial coverage, 1/20 full
(Knowledge Engine)**, zero engines at NONE, `phase_0_through_phase_5_complete`.

Live cross-check against the actual DB tables it describes (not re-deriving, just confirming the
citation is still true):

```sql
SELECT entity_id, verification_status FROM wiring_registry WHERE entity_type='engine';
-- 20 rows, engine-01 .. engine-20, ALL verification_status = VERIFIED_MATCH
```

`capability_registry` (Engine 3, `phase_1_capability_registry_live_wiring`, marked `DONE`
2026-07-24 in the registry) currently holds **26 live rows** — confirmed via
`SELECT count(*) FROM capability_registry`. `wiring_registry` overall holds **24,441 rows**.
Query commands (already documented, reused as-is, not rebuilt):
`python3 scripts/superboss-register.py query-knowledge "engines_gateways_architecture" --tag domain:engines_gateways_architecture`
and `python3 scripts/superboss-register.py list-capabilities`.

## (b) Realistic prioritized 24h plan, by real token-reduction impact

**Honest framing first:** 6 of the 10 audited items are already INSTALLED-WORKING today, and a
7th (aider-chat) is installed and functional but unwired. The only genuine "build" work left is
claude-orchestra + graft — and per `UMR-20260813-042145-7cc0`'s own findings (this UMR's parent),
**every other open task under the P1 chain is currently blocked by the same
`credit-accountant.py` human-review gate** ("no further metered spend without human review").
Any new dispatch this plan proposes will likely hit that identical gate. **Not all of this is
credibly completable in 24h without a human clearing that gate first** — said plainly, not
hedged.

1. **(0-1h, blocking, no token-reduction yet — a prerequisite) Resolve name ambiguity for
   claude-orchestra and graft.** Both names collide with multiple unrelated real OSS projects.
   Installing the wrong one wastes credits and produces a false "done." Needs one human-confirmed
   canonical repo URL for each before any install dispatch — this is a proposal, not an
   assumption, and is the actual reason these two show NOT-INSTALLED rather than
   INSTALLED-BROKEN.

2. **(0-4h, highest real token-reduction lever available today, zero new install needed) Widen
   Zoekt adoption.** Zoekt is fully live and already proven inside `task-gateway.py`'s
   `run_zoekt_search()`, but that's one call site. Every place an agent currently does an
   LLM-mediated file sweep (broad `grep`/`find`/`Explore`-agent fan-out) to locate a symbol or
   string is a candidate to hit the already-running `127.0.0.1:6070` service first — that's a
   real, measurable token cut with the infrastructure already paid for and running. Scoping which
   call sites to convert is same-day feasible; this is the one item on this list that is both
   high-impact and not blocked by the credit-accountant gate (it is code reuse of a live service,
   not new spend).

3. **(0-2h, real but smaller impact) Wire aider-chat in or document why not.** It is installed
   and functional (`aider --version` proves it) but has zero real callers. Aider's local
   diff-based editing is cheaper than full-file LLM rewrites for small, mechanical edits — a
   genuine token-reduction candidate — but wiring it into the dispatch pipeline is new
   integration work, which means it likely also hits the credit-accountant gate. Realistic 24h
   outcome: a scoped recommendation + owner decision request, not a merged integration.

4. **(0-2h, verification only, no new work) pgvector / embedding cache.** Already
   INSTALLED-WORKING with real production data (143 embeddings, 27 cache rows). No action needed
   for install state. The only realistic 24h add: a Grafana dashboard panel (Grafana+Prometheus
   are already live) tracking `embedding_cache` hit-rate, since that number is a direct
   token-reduction signal and the observability stack to show it already exists — cheap,
   additive, not blocked by the credit gate since no app code changes.

5. **(Deprioritized for this 24h window) earlyoom / Cockpit / Grafana / Prometheus /
   node_exporter.** All confirmed INSTALLED-WORKING today. These are system-stability/observability
   tools, not token-reduction levers — no further action is credible or necessary against this
   SPEC's own stated impact metric.

6. **(Not credible in 24h) claude-orchestra + graft actual install/integration.** Blocked on item
   1's clarification AND the standing credit-accountant human-review gate that is already
   stopping every other sibling task in this P1 chain. Stating plainly: even with the name
   resolved today, install + smoke-test + registry-registration + real-caller-wiring for two new
   tools inside 24h, on top of an active spend-approval gate, is not a credible commitment.

## (c) Zero-duplication check vs. other open UMRs under this P1 chain

Checked live against `ai_agent_registry` (each UMR = exactly one agent memory row, per the
`UMR-20260806-121332-6ba4` correction already standing in this system) and the parent's own
`STATUS_REPORT.md` deliverable table:

| Sibling UMR under P1 | Real current state (re-confirmed, not assumed) | Overlap with this audit? |
|---|---|---|
| P1 root, `UMR-20260806-171945-5767` | `status=completed`; its closeout task (`task-20260809-004606-priority-1-final-point--close-umr171945`) is `status: blocked` on the credit-accountant gate | None — that task is a generic close-out, not a tool audit |
| Parent, `UMR-20260813-042145-7cc0` | `--umr-id` bug fix (PR #289, unmerged) + supervisor-audit diagnosis + 4-chain resume investigation | None — different scope entirely; this dispatch is its own addendum, not a re-run of it |
| P2/3, `UMR-20260808-175055-cebd` → `UMR-20260808-185252-afba` | `status: blocked`, same credit-accountant gate, worker unit inactive | None — OCID020/021-COMBINED item closure, unrelated tool set |
| P4, `UMR-20260808-183732-d3a3` | `status: blocked`, same gate; prior real work was OCID consolidation (PRs #796-#801, #1068, #870, #884) | None — OCID consolidation, no tool-install content |
| Parallel mandate, `UMR-20260808-183926-70b6` | `status: blocked`, same gate; prior work was PR merge-conflict/branch-protection coordination across P1-P4 | None — coordination role, no tool-install content |
| `UMR-20260813-034121-45c0` | Superboss verdict `reject` (missing audit trail — no branch/PR) | None — external-memory-scaffolding topic |
| `UMR-20260813-035737-1d97` | Superboss verdict `approve`, stuck unmerged (no PR) | None — boss/worker model-tier topic |

Also checked the one prior doc that names some of the *same category* of tooling decisions,
`docs/infra/TOOL_INTEGRATION_PLAN.md` (compliance-tracker, cited via `check-duplicate` against
this UMR's own scope terms) — it governs a **disjoint** 6-tool set (PaddleOCR, Docling,
Meilisearch, Whisper.cpp, LibreOffice Headless, Temporal) plus a 46-tool sweep evaluation that
explicitly lists Supabase pgvector as "already integrated" (consistent with finding #6 above) but
does not name earlyoom/Cockpit/Grafana/Prometheus/node_exporter/Zoekt/aider-chat/claude-orchestra/graft
as a group — **no overlapping in-flight work found, nothing duplicated by this audit.**

**Conclusion: zero duplication.** No other open UMR under this P1 chain is auditing or building
this specific 8-tool set (earlyoom/Cockpit/Grafana+Prometheus+node_exporter/pgvector/Zoekt/
aider-chat/claude-orchestra/graft) or the 20-engine registry citation. This audit is genuinely new
ground, not a re-run.
