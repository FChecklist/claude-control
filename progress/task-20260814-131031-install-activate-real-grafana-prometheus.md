# PROGRESS -- task-20260814-131031-install-activate-real-grafana-prometheus

Governing UMR: UMR-20260813-084321-2962 (addendum). Deterministic briefing UMR: UMR-20260814-130922-557f.

## Real gap re-check (before building anything)

SPEC's "not installed at all" was confirmed true for native binaries/dpkg/systemd
unit files (all empty), but that check never looked at `docker ps` / `ss -tlnp`.
Found: the actual 2026-08-07 stack (referenced as
`veridian_grafana_monitoring_stack_2026-08-07`) was alive the entire time as 4
docker containers (`veridian_node_exporter`, `veridian_prometheus`,
`veridian_grafana`, `veridian_cadvisor`), up 34h, bound to the exact standard
ports (9100/9090/3000/8085), Grafana healthy at v13.1.3, real config recoverable
at `/opt/veridian/monitoring/{docker-compose.yml,prometheus/prometheus.yml,prometheus/alert_rules.yml}`.
It was never removed -- SPEC's speculation about a disk-cleanup removal was wrong.

Task explicitly requires `systemctl --user is-active` = active for 3 named
systemd --user units (not docker containers), so the docker trio for
node_exporter/prometheus/grafana was stopped (not deleted -- containers +
images left in place as a rollback fallback) and superseded by real native
systemd --user-managed binaries, reusing the recovered prometheus.yml/
alert_rules.yml content and the grafana admin-user/port convention unchanged.
cadvisor container left running untouched (out of scope, harmless, still
scraped as a bonus Prometheus target).

## Completed

- [x] Re-checked live gap: confirmed no native/dpkg/systemd install, found + reused prior 2026-08-07 docker-based config instead of rebuilding from scratch
- [x] Stopped (not removed) the 3 relevant docker containers to free ports 9100/9090/3000; left cadvisor running
- [x] Downloaded + sha256-verified real binaries: node_exporter v1.12.1, Prometheus v3.13.2, Grafana 13.1.3 (linux/amd64) to /opt/veridian/monitoring/{bin,grafana/install}
- [x] Reused prior prometheus.yml + alert_rules.yml (only fixed docker-internal paths -> real local paths); kept node_exporter + cadvisor scrape targets
- [x] node_exporter systemd --user unit: 127.0.0.1:9100, --collector.textfile.directory enabled
- [x] Prometheus systemd --user unit: 127.0.0.1:9090, scrapes node_exporter + cadvisor
- [x] Grafana systemd --user unit: 127.0.0.1:3000, admin user/port convention reused from prior docker-compose.yml (real password kept only in the untracked live grafana.ini on host, redacted in the committed repo copy -- public repo)
- [x] New read-only observability sidecar (veridian-metrics-textfile.service + .timer, every 30s) writes real `veridian_concurrent_worker_count` (systemctl --user list-units veridian-worker@*/veridian-supervisor@* --state=running, same definition as dispatch_core.py's running_worker_count(), shelled out to directly -- no import of dispatch_core.py or any dispatch-decision code) and `veridian_dispatch_queue_depth` (superboss-register.sqlite work_items status IN ('open','pending'), opened strictly `mode=ro`) to node_exporter's textfile collector. Not part of the 20-unit veridian-cron-* closed set (documented in the unit file + ~/.config/systemd/user/README.md's governance) -- new category, same precedent pattern as veridian-task-watchdog/veridian-webhook-receiver.
- [x] Installed frser-sqlite-datasource Grafana plugin, provisioned as a second (unused-by-default-panels, available for ad-hoc SQL) read-only datasource pointed at superboss-register.sqlite via a `mode=ro`-equivalent path config
- [x] Provisioned dashboard `veridian-observability.json`: Memory & Swap Used %, Load Average % (normalized by CPU count), Real Concurrent Worker Count (stat), Dispatch Queue Depth (stat) -- all 4 panels confirmed returning real live data through Grafana's own datasource proxy
- [x] Enabled + started all 3 required units + the timer; confirmed `systemctl --user is-active` = active for all 3 (node-exporter/prometheus/grafana), confirmed localhost-only binding (127.0.0.1) via `ss -tlnp` for all 3 ports
- [x] DONE CRITERIA proof: `curl localhost:3000/api/health` -> `{"database":"ok","version":"13.1.3",...}`; `curl localhost:9090/-/healthy` -> `Prometheus Server is Healthy.`; `curl localhost:9100/metrics` shows real `veridian_concurrent_worker_count`/`veridian_dispatch_queue_depth`
- [x] Did not touch pm-sentinel-tick.sh or any dispatch-decision logic -- verified: only read-only `systemctl --user list-units` shell-outs and a `mode=ro` sqlite connection
- [x] Committed real unit files (systemd/) + real config/dashboard/script (monitoring/) to this task's branch

## Remaining

- [ ] Push branch + open PR
- [ ] Call agent_work_briefing.py record-completion for UMR-20260814-130922-557f
