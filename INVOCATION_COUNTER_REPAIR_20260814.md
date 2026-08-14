# Lifetime invocation counter repair -- 2026-08-14

Repairs the 11 real tasks whose `.invocation_count` (lifetime cap
`MAX_LIFETIME_INVOCATIONS=20`, `veridian-worker@.service`) was inflated by
preflight rejections that never invoked a model -- the same bug fixed in
`worker-entrypoint.sh` by
`FChecklist/veridian-scripts#fix/lifetime-invocation-counter-preflight-rejection`.

Script: `scripts/repair_invocation_counters.py` (this workspace). Run with no
args for a dry-run report, `--apply` to write the corrected values.

## Method

For each task, the corrected value is derived ONLY from that task's own
`task.yaml` checkpoint history (never from the live `.invocation_count` value
itself, which is exactly the number under dispute):

```
corrected = (# checkpoints that started a distinct script invocation)
          - (# of those whose note contains "no model call made, no cost incurred")
```

A checkpoint is recognized as starting a distinct invocation by note prefix:
`worker started` / `doc-worker started` (real invocation, preflight passed),
`PRE-FLIGHT REJECTED` (transient preflight rejection), `PRE-FLIGHT HARD STOP`
(deterministic preflight rejection), `PREVENTION CAP HIT` (cap already
exceeded). Only the `PRE-FLIGHT REJECTED ... transient` checkpoints carry the
literal `-- no model call made, no cost incurred` text (the exact signal named
in this task's SPEC), so only those are discounted. `PRE-FLIGHT HARD STOP` /
`PREVENTION CAP HIT` checkpoints are deliberately NOT discounted here even
though they also never called the model -- that mechanical text match is the
scope this repair was asked to close; broadening it to hard-stop reasons too
would be a separate, explicit decision.

10 of the 11 tasks were rejected by the 2026-08-14 host-level disk_low event
(guard reason `disk_low`, confirmed via `grep -rl disk_low */task.yaml` under
`/opt/veridian/ai-os/tasks`). The 11th
(`task-20260718-171007-commercial--subscription---pricing-model`) carries an
older instance of the identical bug shape: 12 `credit_accountant_rejected`
preflight rejections from 2026-07-20, BEFORE that reason was added to
`worker-entrypoint.sh`'s hard-stop list later the same day -- while it fell
through to the transient branch it charged the lifetime counter 12 times for
zero model calls, exactly like the disk_low cases.

## Before / after

| task_id | before | checkpoints (starts) | discounted (no-model-call) | after (corrected) |
|---|---:|---:|---:|---:|
| task-20260718-171007-commercial--subscription---pricing-model | 13 | 16 | 12 | **4** |
| task-20260807-062740-cleanup-closed-6-stale-awaiting-approval | 7 | 7 | 3 | **4** |
| task-20260807-064722-retry-ai-documentation-lifecycle | 6 | 6 | 3 | **3** |
| task-20260807-064727-retry-ai-documentation-ai-readable-techn | 6 | 6 | 3 | **3** |
| task-20260807-071557-retry-ai-cost-governance-finops-cost-vis | 6 | 6 | 3 | **3** |
| task-20260814-023018-live-deploy-drift-p0--the-live-veridian | 4 | 4 | 3 | **1** |
| task-20260814-030259-live-deploy-drift-p0--the-live-veridian | 3 | 3 | 3 | **0** |
| task-20260814-031827-rca--umr-20260807-153242-ee23-killed | 3 | 3 | 3 | **0** |
| task-20260814-031834-rca--umr-20260807-151622-15cd-killed | 3 | 3 | 3 | **0** |
| task-20260814-031840-rca--umr-20260807-063851-df5e-killed | 3 | 3 | 3 | **0** |
| task-20260814-031847-rca--umr-20260807-063839-3e0e-killed | 3 | 3 | 3 | **0** |

For 10 of the 11 tasks, `before` exactly equals the checkpoint-derived
`checkpoints (starts)` count -- the live file and the checkpoint history agree
on total invocations, and the repair is a clean subtraction of the discounted
rejections.

**Note on the SPEC's cited "18 of 20"**: the task SPEC that dispatched this
repair cited this task's live count as 18/20 at ~03:40 UTC. The real value
read directly from `.invocation_count` at repair time (this run) was 13, not
18 -- and this task's own `task.yaml` top-level `status` is `blocked` with its
LAST checkpoint dated 2026-07-20 (`PRE-FLIGHT HARD STOP`, which also disables
the systemd unit) -- i.e. this task has not run since 2026-07-20 and could not
have taken any NEW hits from an 2026-08-14 disk_low event. The 18 figure in
the SPEC is not reproducible against this task's actual on-disk state at
repair time; flagging rather than silently assuming either number is right.
Either way, the checkpoint-history-derived corrected value (4) is the real,
auditable number this repair writes back, independent of which of 13/18 was
the true "before".

**Known discrepancy, task-20260718-171007**: `before` (13) is 3 LOWER than the
checkpoint-history-derived total (16: 3 real `worker started` + 12
`PRE-FLIGHT REJECTED` + 1 `PRE-FLIGHT HARD STOP`). This task's 12 rejections
all landed within a ~40-minute window on 2026-07-20 (15:32-16:11 UTC), several
only 30-90 seconds apart -- plausibly 3 of those `.invocation_count` writes
lost a race under systemd's fast restart cadence (`RestartSec=30` between
attempts, but this bug predates that specific reason being on the hard-stop
list, so retries were tighter). Per this task's SPEC, the checkpoint-history
value is treated as ground truth (never the live counter, which is exactly the
value alleged to be wrong) -- so the corrected value here (4) is
`16 checkpoint-derived starts - 12 discounted = 4`, not `13 - 12 = 1`. This is
called out explicitly rather than silently reconciled, since the drift's exact
cause 3.5 weeks later is not independently verifiable.

## Real values written (verified post-write)

```
task-20260718-171007-commercial--subscription---pricing-model -> 4
task-20260807-062740-cleanup-closed-6-stale-awaiting-approval -> 4
task-20260807-064722-retry-ai-documentation-lifecycle -> 3
task-20260807-064727-retry-ai-documentation-ai-readable-techn -> 3
task-20260807-071557-retry-ai-cost-governance-finops-cost-vis -> 3
task-20260814-023018-live-deploy-drift-p0--the-live-veridian -> 1
task-20260814-030259-live-deploy-drift-p0--the-live-veridian -> 0
task-20260814-031827-rca--umr-20260807-153242-ee23-killed -> 0
task-20260814-031834-rca--umr-20260807-151622-15cd-killed -> 0
task-20260814-031840-rca--umr-20260807-063851-df5e-killed -> 0
task-20260814-031847-rca--umr-20260807-063839-3e0e-killed -> 0
```

All 11 tasks moved well clear of `MAX_LIFETIME_INVOCATIONS=20`.
`task-20260718-171007` in particular went from 13/20 (with the live host still
having an active disk_low condition, one more of which would previously have
pushed it further toward permanent unrunnability) to a real 4/20 -- 3 real
attempts plus 1 hard-stop.
