# Status report — RCA + resume for killed task-20260813-035740 (Boss/Worker model-tier orchestration)

UMR: UMR-20260813-090004-8f18 (this task's own governing UMR)
Governing chain: Priority 1 UMR-20260806-171945-5767, real addendum
UMR-20260813-035737-1d97 (Boss/Worker model-tier orchestration)

## Verdict
**The killed task's reasoning was real, correct, and complete — it just
never got durably committed.** No code implementation was needed (the
dispatch spec's premise about existing model-cost tiering was false, and
the worker correctly proved that rather than building unneeded framework
code). The gap was pure process: the real finding sat as uncommitted files
in a shared directory with a mistaken assumption that an "Auto-sync"
process would land it in git. It didn't exist for that directory. Fixed by
landing the recovered finding as a real, merged PR.

## Step 0 — stop-work-order gate, run for real, not assumed
```
$ python3 /opt/veridian/scripts/resource_governor.py --check-task-start-gate \
    --task-kind veridian_task_create --title "RCA resume killed P1 addendum UMR-1d97" \
    --umr-id UMR-20260813-090004-8f18
{"blocked": false, "check": null, "detail": null}
```
Not blocked. Also independently confirmed via `ai-os` git log: Owner lifted
the standing stop-work order directly, 2026-08-08 (commit `ca513ca`,
`OWNER_DECISIONS_NEEDED_2026-07-23.yaml` entry
`stop-work-order-lifted-2026-08-08`). No exemption fabricated — this is the
real gate's own real output.

## Step 1 — what actually happened to task-20260813-035740
Read directly from its `task.yaml` checkpoint history, `prompt.txt`,
`result.json`, and `supervisor.log` (never re-derived from scratch):

- Prompt (real scope, 3 items): (1) document the existing real
  BOSS=sonnet-high/WORKER=haiku-low tiering already used by the dispatch
  pipeline, or correct the premise if false; (2) a short prompt-caching-
  order note if not already covered by a sibling task; (3) explicitly do
  **not** create `boss.py`/`worker.py`/`orchestrator.py`/a new systemd
  service.
- The worker's own final `result.json` summary: *"the dispatch spec's
  premise — 'BOSS=sonnet-high/WORKER=haiku-low tiering already used by
  this dispatch pipeline' — is **not true**."* It verified this against
  `/opt/veridian/scripts/` and wrote up the finding plus grep evidence to
  `/opt/veridian/ai-os/memory/BOSS_WORKER_DISPATCH_TIER_NOTE.md` and
  `memory/sources/2026-08-13_boss-worker-model-tier-verification.md`,
  explicitly did *not* create any new framework files, and noted item (2)
  was already covered by sibling `UMR-20260813-034121-45c0`'s output.
- `task.yaml`'s last checkpoint (`2026-08-13T04:03:53Z`, `status: blocked`):
  *"supervisor could not resolve a real PR for branch
  'worker/task-20260813-035740-boss-worker-model-tier-orchestration--ad'
  (gh pr create failed, no existing open PR found for it) — refusing to
  proceed rather than risk operating on an unrelated PR via gh's
  empty-argument fallback."*
- `supervisor.log` shows the real underlying `gh` failure: *"pull request
  create failed: GraphQL: Head sha can't be blank, Base sha can't be
  blank, No commits between master and worker/...(branch) (createPullRequest)"*
  — because the task's own `claude-control` branch genuinely had zero
  commits (correct: no code change was warranted) — followed by an
  explicit refusal to fall back to gh's ambiguous default-PR resolution,
  citing a real prior incident (PR #84, 2026-07-26).
- The task then went `status=killed` some time later: real systemd state
  `inactive`, no live process, no PR ever opened.

## Step 2 — independently re-verified the recovered finding (not just trusted it)
Before landing anything, re-ran the load-bearing checks myself against the
live `/opt/veridian/scripts/`:
```
$ grep -n "^TIER_MIN\|^DEFAULT_TIER" resource_governor.py
68:TIER_MIN, TIER_MAX = 0, 4
69:DEFAULT_TIER = 2
```
— confirmed a scheduling-priority value for the `umr_tasks` queue (docstring
above it: anti-starvation aging, `max(0, tier - age_seconds // interval)`),
unrelated to model choice.
```
$ grep -n -- "--model" worker-entrypoint.sh supervisor-entrypoint.sh doc-worker-entrypoint.sh
worker-entrypoint.sh:260:      --model sonnet --effort high ...
worker-entrypoint.sh:680:      --model sonnet --effort high ...
supervisor-entrypoint.sh:117:  --model sonnet --effort high ...
doc-worker-entrypoint.sh:139:  --model sonnet --effort high ...
$ grep -n -- "--model" master-decompose.py
105: ["claude", "-p", prompt, "--model", "sonnet", "--effort", "high", ...]
$ grep -rli haiku *.py *.sh /opt/veridian/systemd
credit-accountant.py   # docstring example prompt text only, not a model invocation
```
Confirmed: every real Claude Code invocation site uses `sonnet`/`high`
uniformly for both the boss/supervisor role and the worker role. No
cost-tiering between them exists live. The killed worker's finding was
correct.

## Step 3 — real root cause of the block (both candidate readings tested)
- **Candidate (a) — genuinely no code change needed**: TRUE, independently
  confirmed above. Not the actual blocker by itself; the finding existing
  and being correct isn't in question.
- **Candidate (b) — a real blocker it couldn't clear**: also TRUE, but it's
  a process/tooling gap, not a content gap:
  1. The worker wrote its finding into `/opt/veridian/ai-os/memory/` — the
     correct, established location per this UMR chain's own convention
     (the governing prompt itself says sibling `UMR-20260813-034121-45c0`'s
     equivalent output is "now live" there) — but never committed it, citing
     a belief that an existing "Auto-sync ... to master controller" process
     would land it. That process is real but is **not** this: `git log` on
     `/opt/veridian/ai-os` has zero "Auto-sync" commits at all (that message
     pattern belongs to a *different* repo's task-state sync, not this
     memory directory). Confirmed via `git status --short` that
     `BOSS_WORKER_DISPATCH_TIER_NOTE.md`, its sources file, `state.json`,
     `dead_ends.json`, and `CLAUDE_MEMORY_INDEX.md` were all still `??`
     (untracked) hours later, and `git show origin/main:memory/<file>`
     confirmed none of them have ever been on `origin/main`, for this task
     or the sibling one.
  2. Separately, the worker's own `claude-control` task branch had zero
     commits (correctly — no code change was warranted there), so when the
     supervisor's finalization required a PR, `gh pr create` failed
     outright ("No commits between master and worker branch") and
     `gh pr list --head` found nothing open either. The supervisor's refusal
     to fall back to an unrelated PR was itself correct and not the bug —
     see the real PR #84 incident it cites.
  - Net: the worker's reasoning was never lost or wrong. It was simply
    never durably committed anywhere, which made it indistinguishable from
    lost work once the unit went inactive.
- **Not a genuine Owner-decision item**: there is no live model-tier choice
  to make (no tiering exists to choose between), so this is not escalated
  as NEEDS OWNER DECISION — that would be inventing a decision that doesn't
  need making.

## Step 4 — real committed artifact landed
PR opened and pushed (not left as lost reasoning):
**https://github.com/FChecklist/veridian-ai-os/pull/13** — branch
`docs/land-boss-worker-tier-note-umr-1d97` off `origin/main` (via a
throwaway `git worktree`, to avoid the shared `/opt/veridian/ai-os`
checkout's large pre-existing unrelated dirty state and stale local
branch). Adds, verbatim-recovered from the killed worker's uncommitted
working tree and independently re-verified before landing (Step 2 above):
- `memory/BOSS_WORKER_DISPATCH_TIER_NOTE.md`
- `memory/sources/2026-08-13_boss-worker-model-tier-verification.md`

Deliberately did **not** sweep in `state.json`/`dead_ends.json`/
`CLAUDE_MEMORY_INDEX.md`/`open_questions.json` — those mix in sibling
tasks' uncommitted edits too, and landing them is a separate, broader
decision (see Remaining below), not this task's scope.

## Remaining / real follow-up (out of this task's scope, not done here)
1. **Systemic gap**: `/opt/veridian/ai-os/memory/`'s knowledge-base files
   are described across multiple UMRs as durable/"now live" but have zero
   git history and no real sync mechanism. Confirmed this is not a one-off:
   sibling `task-20260813-034138-token-efficiency-external-memory-system`
   (UMR-20260813-034121-45c0's task) hit the **identical** shape — genuine
   no-op, zero commits, supervisor can't resolve a PR — and is also still
   `status: blocked`. Worth a dedicated follow-up task to either add a real
   periodic committer for that directory, or teach the supervisor's
   finalization path to accept a non-`claude-control` PR (like #13 above)
   as satisfying a task whose real deliverable lives elsewhere. Not done
   here — it means changing `resource_governor.py`/`supervisor-entrypoint.sh`,
   a materially bigger and riskier change than this addendum's real scope
   (boss/worker model-tier documentation) asked for.
2. `task-20260813-035740`'s own `task.yaml` still literally reads
   `status: blocked`. That status predates this RCA; its evidence gap is
   now closed by PR #13. Not hand-editing that file directly (supervisor-
   managed state); recording this task's real completion via
   `agent_work_briefing.py record-completion` instead, with a pointer to
   this report and PR #13.
