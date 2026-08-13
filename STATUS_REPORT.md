# Status report — reverification of the RCA/quality-gate routing fix (UMR-20260813-115911-df5c)

Governing chain: addendum to P1 UMR-20260806-171945-5767. Same UMR id as the
task that already shipped the real fix (task-20260813-132414, commit
037908b, merged PR #145). This task is a later dispatch of the identical
SPEC; it re-investigates from scratch rather than trusting the prior
conclusion on faith, per standing practice on this repo.

## Verdict

**The real fix was already shipped and is still live. The SPEC's literal
ask (blanket-skip the code quality gate for any `rca--umr-*-killed`-titled
task) is still the wrong fix and was correctly not implemented that way.
The 3 target tasks have not yet cleared `blocked` as of this check, but the
specific bug that was wrongly blocking them is confirmed fixed and active on
all 3 — what remains blocking them now is genuine build capacity, not
quality-gate misrouting.**

## Step 1 — is the fix from the prior identical-UMR run still live?

`grep -n "no active (queued/dispatched/running) umr_tasks row found"
/opt/veridian/scripts/quality-gate.sh` still matches (line 312). The patch
from `ai-os/patches/quality-gate-untracked-task-build-lock-2026-08-13.diff`
(committed at 037908b) is present on the live script the real worker
processes actually execute, not just in this repo's history.

## Step 2 — is the SPEC's blanket-exemption premise correct?

Re-checked independently rather than reusing the prior run's stated
conclusion: all 3 tasks' `task.yaml` files still show real merged PRs
touching `src/app/api/...`, `src/lib/...` (compliance-tracker application
source), not pure diagnosis documentation. A blanket exemption keyed on the
task title (`rca--umr-*-killed`) would let any future task in this class
that also ships real code skip lint/build checking permanently. That is a
real regression risk, not a hypothetical one — the premise does not hold,
same as before.

## Step 3 — current live state of the 3 target tasks

| Task | `task.yaml` status | `quality-gate-0.json` build failure text |
|---|---|---|
| task-20260813-104656-rca--umr-20260808-183732-d3a3-killed | `blocked` | `next build` genuinely TIMED OUT after 900s (exit 124) — real build-performance issue, unrelated to the routing bug |
| task-20260813-105054-rca--umr-20260808-175055-cebd-killed | `blocked` | "build lock not acquired even after an untracked-task long wait — real capacity failure, not a code defect" — **the fixed code path, confirmed running** |
| task-20260813-105503-rca--umr-20260808-150937-43d0-killed | `blocked` | "build lock not acquired even after the 700s starvation-guard fallback wait (4th+ consecutive contention) — real capacity failure, not requeued again" — **the fixed code path, confirmed running** |

For -105054 and -105503 this is direct, live evidence the fix works: before
037908b, this exact situation (no `umr_tasks` row to requeue) was recorded as
a fabricated `build` code-defect failure, which is what fed
credit-accountant.py's correct refusals. Now it is reported honestly as a
capacity condition. -104656's blocker (a real 900s build timeout) is a
separate, real issue the routing fix was never meant to touch.

Checked `/tmp/veridian-quality-gate-build.lock` live: currently uncontended
(`flock -n -w 1 ... ` succeeds immediately), so the lock pressure behind
-105054/-105503 was transient and has already cleared.

## Step 4 — did the 3 tasks actually progress past `blocked`?

**No, not yet, and I'm not claiming otherwise.** None of the 3 has a
`umr_tasks` row (confirmed previously and still true — they were created
directly, never through `resource_governor.submit()`), so they sit outside
`resource_governor.py`'s automatic `--scan-stuck`/`--tick` resume path, and
`systemctl list-units 'veridian-worker@*' --all` currently returns zero
loaded units for any of the 3 — there is no active unit here for this
workspace to restart. Their `.invocation_count` files show 2 of a 20
lifetime cap, so their next invocation (whatever platform mechanism created
their systemd units the first two times) is expected but is a
platform-scheduling event, not something this task can trigger from inside
its own workspace. Reporting them as "progressed past blocked" without a
real observed status transition would be fabricating a result the credit
accountant would be right to reject.

## What changed in this run

Nothing new in code — the real fix was already applied and merged in
task-20260813-132414 / commit 037908b / PR #145. This run's real
contribution is independent reverification: confirming the fix is still
live, confirming the blanket-exemption premise is still wrong, and reading
the actual current `quality-gate-0.json` evidence from all 3 tasks to show
the fix is functioning as designed rather than assuming it from the old
commit message alone.
