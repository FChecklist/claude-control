# Status report — real dedup finding for claude-control PR #126 (task-gateway.py stop-work bypass)

UMR: UMR-20260813-085642-56b3 (this task's own governing UMR)
Governing chain: UMR-20260813-042708-e592 ("Close task-gateway.py stop-work
bypass gap"), which produced PR #126 and its own real, posted AUDIT:FAIL
(2026-08-13T04:40:12Z).

## Verdict
**PR #126 is a true duplicate of already-shipped-and-live code, opened
against a retired directory. Closed without merging (not re-audited for
merge — see "Do not merge" below).** The original AUDIT:FAIL verdict was
correct; this report documents the real evidence and closes the loop.

## Step 1 — stop-work exemption, confirmed in writing
`ai-os/OWNER_DECISIONS_NEEDED_2026-07-23.yaml`, entry
`stop-work-order-lifted-2026-08-08` (status: approved, decided_at
2026-08-08T09:55:38Z, decided_by "rajat (real, on-server, own git identity —
not the PM relay)"):

> Owner directly lifts the standing stop-work order
> (task-20260806-165921-owner-absolute-stop-work-order--complete) for all
> PR/push work on resource_governor.py, superboss-register.py,
> **task-gateway.py**, and resource_governor_tick_loop.sh, effective
> immediately.

task-gateway.py is named explicitly. This task's own work (reading source,
running tests, posting a PR comment, closing a PR, writing docs) is
authorized under this exemption.

## Step 2 — is the live gate genuinely wired into cmd_start? Yes.
`/opt/veridian/scripts/task-gateway.py` (the real file the running
`veridian-worker@*.service` units execute — confirmed via `readlink -f` and
`stat`, mtime 2026-08-08 23:54, 1611 lines) is a clean git working copy of
**`FChecklist/veridian-scripts`** (`git remote -v` → `veridian-scripts.git`,
not `claude-control.git`; `git diff HEAD -- task-gateway.py` → 0 files
changed, i.e. working tree exactly matches committed HEAD `347d89e`).

Quoted directly from that live file:

```
130: def run_task_start_gate(task_identity, title, umr_id=None):
131:     """UMR-20260808-121334-e122 (Owner-decided Option B, PM decision cycle
...
155:     cmd = [
156:         "python3", RESOURCE_GOVERNOR, "--check-task-start-gate",
157:         "--task-identity", task_identity, "--title", title,
158:     ]
...
161:     return run_json(cmd, "resource_governor.py --check-task-start-gate")
```

and, inside `cmd_start` itself:

```
617:     # Real gate (UMR-20260808-121334-e122, Option B) -- see
618:     # run_task_start_gate()'s own docstring. Runs immediately after the
619:     # duplicate-task-key claim (cheap, no real resources spent yet) and
620:     # before veridian-task.py create below (the real spawn -- worktree/
621:     # branch/systemd unit), so a blocked start never reaches that point.
622:     gate_result = run_task_start_gate(task_key, args.title, umr_id=args.umr_id)
623:     if gate_result.get("blocked"):
624:         fail(
625:             "blocked by resource_governor.py's real stop-work-order/resource-threshold gate "
626:             "-- the same real protection dispatch_one() applies to every queued task",
```

This is exactly the gap PR #126 claims to close, already present and live.

**Provenance, timeline (the real, load-bearing fact):** this wiring shipped
as `veridian-scripts` PR #278 ("fix: e122 Option B — shared stop-work-order
+ resource-threshold gate for task-gateway.py cmd_start"), commit `bc14a21`
(2026-08-08T14:32:44Z), merged via `5537b6d` at **2026-08-08T14:42:58Z**.
UMR-20260813-042708-e592 was minted **2026-08-13T04:27**, and PR #126's head
`efa7dc9` was pushed **2026-08-13T04:32** — **5 days after** the real fix was
already live. The auditor's FAIL comment ("this diff re-implements a gate
that was already shipped live at /opt/veridian/scripts/task-gateway.py") is
factually correct.

## Step 3 — why did a worker duplicate already-live code? Root cause found.
PR #126 was opened against **`claude-control`**'s `scripts/task-gateway.py`
— not `veridian-scripts`. `claude-control/scripts/README-RETIRED.md`
(merged 2026-08-01, PR #120) states, in this repo, right now:

> As of 2026-08-01 this is retired... `sync-repos.sh` now pulls
> `/opt/veridian/scripts` directly from `veridian-scripts` instead. This
> directory is no longer read by anything.
>
> **Do not add or edit files here for anything meant to run on the
> server.** Use `FChecklist/veridian-scripts` instead.

PR #126 edited a directory that has been formally dead for 12 days before it
was opened. Its diff (`c49518a..ebaf413`, +348/-0 across
`scripts/task-gateway.py` and a new `tests/test_task_gateway_stop_work_gate.py`)
never had any chance of reaching production regardless of the duplication
question — `claude-control/scripts/` is not deployed. Whatever dispatched
UMR-20260813-042708-e592 with `repo: claude-control` pointed the work at the
wrong repo.

## Step 4 — real test run proving cmd_start cannot bypass the gate (exit 0)
Two independent real runs, both against the live module, no mocks of the
gate itself:

```
$ cd /opt/veridian/scripts && python3 -m pytest tests/test_task_start_gate.py -v
...
tests/test_task_start_gate.py::test_cli_check_task_start_gate_blocked_by_stop_work_order PASSED
tests/test_task_start_gate.py::test_run_task_start_gate_returns_parsed_result_when_blocked PASSED
...
10 passed in 2.95s
```

Plus an ad hoc direct end-to-end check of `cmd_start()` itself (not just
`run_task_start_gate()`) loaded straight from
`/opt/veridian/scripts/task-gateway.py`, with a real isolated
`OWNER_DECISIONS_PATH` git repo containing no lift/exemption entry:

```
$ cd /tmp && python3 -m pytest verify_live_cmd_start_gate.py -v
verify_live_cmd_start_gate.py::test_live_cmd_start_is_blocked_by_real_stop_work_order PASSED
1 passed in 0.25s
```

The test asserts `cmd_start()` exits with code 1, the JSON error names
`check == "stop_work_order"`, and — critically — the stubbed
`veridian-task.py create` (the real spawn step) is **never invoked**. This is
real evidence the live cmd_start path cannot bypass the stop-work gate. (Note:
the pre-existing, unrelated `tests/test_stop_work_order_gate.py::
test_dispatch_one_defense_in_depth_blocks_preexisting_queued_row` failure
seen in the same run is a real-host-load flake — 5/5 worker slots are
genuinely occupied right now, so `dispatch_one()`'s cap-exhaustion check
fires before its stop-work check in that one test; unrelated to cmd_start
and to this UMR's scope.)

## Decision taken
- Posted a dedup finding comment on `claude-control` PR #126 quoting the
  above live lines and the retirement notice.
- **Closed PR #126 without merging.** Not re-audited for merge-worthiness —
  there is nothing to merge; merging would reintroduce dead code into an
  already-retired directory.
- No corrective push was made to PR #126's branch — a "fix" here would mean
  editing `claude-control/scripts/task-gateway.py`, which the repo's own
  2026-08-01 decision says not to do.
- Did not touch `task-20260813-042729`'s own `task.yaml` (owned by the
  task-lifecycle system, not hand-edited by this task).

## Owner-decision check
No open product decision is required here — this hinges entirely on real,
checkable evidence (file mtimes, git history, a named commit, a
git-committed retirement notice, passing tests), not a judgment call. Not
escalated.
