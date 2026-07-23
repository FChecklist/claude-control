# PROGRESS -- task-20260723-163003-rca-task-20260723-162833-gap-closing-pha

## Completed
- [x] Read task.yaml/worker.log/systemd.log for task-20260723-162833-gap-closing-phase11-item29-auth-verifica.
- [x] Determined real root cause (not the surface-level "prompt contradiction" text -- see below).
- [x] Applied a real, reusable fix to the shared infra script(s) that caused it (outside this repo, see below).
- [x] Registered the fix in known_fixes (superboss-register.sqlite) for this exact signature.

## Root cause (honest, not a guess)
The watchdog signature `PRE-FLIGHT REJECTED (tight_task_schema_violation, transient)` is
NOT primarily a prompt-authoring bug in the target task. `tight_task_validation.py`'s
`detect_field_contradiction()` did (transiently, 3x in a row) flag a false-positive
contradiction between item 29's CONSTRAINTS and SCOPE sections (both legitimately discuss
the veridian-glm-proxy service -- one scoping the phase, the other asking a judgment
question about removing the unit -- naive keyword-overlap matching mistook that for a
real contradiction). That flakiness is a real, separate, lower-priority issue in the
validator's word-overlap heuristic, but it is NOT what stalled/looped this task, and by
the time this RCA started, prompt.txt had already been edited externally (16:29:53Z) and
attempt #4 passed pre-flight cleanly (checkpoint 16:30:03Z, "pre-flight passed").

The REAL, reusable root cause is in `worker-entrypoint.sh` (and identically in
`doc-worker-entrypoint.sh`), both in `/opt/veridian/scripts/` (live infra, not part of
this git repo -- confirmed no git repo exists at that path or at /opt/veridian):

`tight_task_schema_violation` is a **static, content-based** pre-flight rejection --
`tight_task_validation.py`'s verdict is a pure function of prompt.txt's own text, so a
retry against an unchanged prompt.txt reproduces the IDENTICAL rejection every time. This
is the exact same property that `circuit_breaker_tripped`, `budget_exhausted`,
`openrouter_balance_exhausted`, and `credit_accountant_rejected` were already special-cased
for (worker-entrypoint.sh's own comments: "blind retry produces the identical rejection
until a human intervenes"). But `tight_task_schema_violation` was missing from that
hard-stop allowlist (line ~70), so it fell through to the generic "transient" branch,
which:
  1. checkpoints status=failed and exits 1, letting systemd's Restart=on-failure retry it
     blindly (exactly the loop the watchdog caught -- 3 identical failures in ~90 seconds), and
  2. is WORSE than an ordinary wasted retry: `record_failure_signature()` (which feeds the
     preflight-guard.py circuit breaker via `.failure_signatures.json`) is only called
     after a real `claude -p` invocation runs, further down in the script -- pre-flight
     rejections never reach that code at all. So the circuit breaker that exists
     specifically to stop this class of pathological retry never even saw these failures,
     and the task could have burned all `MAX_LIFETIME_INVOCATIONS` (20) retries on a
     rejection no retry could ever fix -- only a human/agent editing prompt.txt (or fixing
     a validator false-positive) can resolve it.

This is a genuine infra defect, reproducible for ANY task whose prompt.txt fails the
static tight-task-schema check, not specific to item 29's content.

## Fix applied (live infra, outside this repo)
- `/opt/veridian/scripts/worker-entrypoint.sh`: added `tight_task_schema_violation` to the
  pre-flight hard-stop condition (alongside circuit_breaker_tripped/budget_exhausted/
  openrouter_balance_exhausted/credit_accountant_rejected) -- now checkpoints
  status=blocked, disables the unit, and does NOT let systemd retry. `bash -n` verified.
- `/opt/veridian/scripts/doc-worker-entrypoint.sh`: same fix (identical bug present there,
  only `circuit_breaker_tripped` was hard-stopped before). `bash -n` verified.

## known_fixes evidence
```
$ python3 scripts/superboss-register.py log-fix \
    --signature "PRE-FLIGHT REJECTED (tight_task_schema_violation, transient)" \
    --fix-action "hardstop_tight_task_schema_violation"
```
Row confirmed in `/opt/veridian/ai-os/memory/superboss-register.sqlite`:
```json
{"signature": "PRE-FLIGHT REJECTED (tight_task_schema_violation, transient)",
 "fix_action": "hardstop_tight_task_schema_violation",
 "last_applied": "2026-07-23T16:36:54.073701+00:00",
 "success_count": 1}
```
`fix_action` is not in `veridian-task-watchdog.py`'s `FIX_ACTIONS` runtime-remediation
whitelist (by design -- this is a code-level prevention already applied, not a runtime
action for the watchdog to execute), so per that script's own documented behavior it is
recorded/logged only, no automated system action is (or should be) taken for it.

## Secondary note (not fixed this task, out of scope but disclosed)
`detect_field_contradiction()` in `tight_task_validation.py` has a real false-positive
mode on tasks whose CONSTRAINTS and SCOPE/OBJECTIVE legitimately share specific proper
nouns (e.g. a service name) without an actual logical contradiction -- worth a follow-up
if it recurs, but it did not require any fix here since the hard-stop fix makes even a
genuine false-positive here fail safely (blocked + disabled, human-reviewable) instead of
retry-storming.

## Remaining
- [ ] None -- task complete pending review.
