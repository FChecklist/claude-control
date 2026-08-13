# Status report — target-identifier dedup check for the server-native PM front door

UMR chain: addendum to UMR-20260813-102459-10c3 (itself addendum to
UMR-20260813-084321-2962 / P1 UMR-20260806-171945-5767)

## Verdict

**Real remaining scope, not already done.** UMR-20260813-102459-10c3 has not
landed anywhere yet — confirmed live: zero commits/PRs across
`FChecklist/veridian-scripts` or `FChecklist/claude-control` reference
`UMR-20260813-102459-10c3` or `102459-10c3` (checked via `gh search prs`,
`gh api search/commits`, and a full `git log --all --oneline` grep of a
fresh clone). So this addendum's requirement — the exact target-identifier
check, not `--search` alone — was folded in directly as new real scope, not
skipped as already-covered.

**The real fix lands in `FChecklist/veridian-scripts`, not this repo.**
`claude-control/scripts/` has been retired since 2026-08-01
(`scripts/README-RETIRED.md`, this repo's own file: *"Do not add or edit
files here for anything meant to run on the server. Use
`FChecklist/veridian-scripts` instead."*) — the same repo-boundary mistake
already documented as PR #131's root cause in this chain's own history.
`dispatch-owner-task.sh` (the real single front door every dispatcher —
server-native PM sentinel, Desktop sentinel, Desktop session — already goes
through) and `superboss-register.py` both live only in `veridian-scripts`,
on `main`; neither exists in `claude-control` at all.

## Step 1 — real incident data, cross-checked against this repo's own git history

The SPEC's incident text names four UMR-suffix IDs (`-a248`, `-1489`,
`-bd10`, `-9a69`) targeting PR #131 and PR #135. Both PRs are real and
concrete in this repo:

- `claude-control#131` — "feat: server-native hourly PM sentinel
  (pm-sentinel-tick.sh)" — still **OPEN** (`gh pr list --repo
  FChecklist/claude-control`).
- `claude-control#135` — the financial-escalation-policy amendment —
  already **MERGED** (`78e4ee1`, see the prior status report below this
  one in git history, `95c5ce0`, UMR-...-9a69 — the exact suffix this
  addendum's incident text names for PR #135).

This confirms the incident is describing real, already-observed duplicate
dispatch pressure against this exact repo's own open work, not a
hypothetical.

## Step 2 — real code added (in `veridian-scripts`, PR #297)

<https://github.com/FChecklist/veridian-scripts/pull/297> — branch
`worker/task-20260813-115828-add-target-identifier-dedup-check-to-ser` off
`main` (`41c3d02`), head `c3ee2b2`.

In `superboss-register.py`:
- `extract_target_identifiers(text, default_repo=None)` — real,
  deterministic (regex, no fuzziness) extraction of PR number+repo, exact
  file paths, and exact script names from free text.
- `find_target_identifier_duplicate(conn, title, prompt, repo=None,
  window_hours=4, limit=30)` — pulls `query_umr_tasks(limit=30)` with **no
  status filter, newest first** (exactly the shape this addendum's own fix
  requirement specifies), and returns the first still-`queued`/`running`
  row within `window_hours` whose own real prompt/title shares an exact
  target identifier with the dispatch about to happen.
- `check-target-identifier-duplicate` CLI subcommand, same convention as
  the existing `check-content-duplicate`.

In `dispatch-owner-task.sh`: a new step 1b, right alongside the existing
content-duplicate check. A real target-identifier duplicate now **refuses
the dispatch** (exit 1, citing the live `duplicate_umr_id`) before any UMR
row is even created — closing the gap for every caller of the shared front
door, not just one script.

This is a third, independent dedup layer — orthogonal to
`check-content-duplicate` (exact hash) and `--search` (fuzzy FTS5), not a
widening of either; both of those remain unchanged.

## Step 3 — real test proving it catches this exact incident pattern

`tests/test_target_identifier_dedup.py` (9 tests, real subprocess + real
isolated sqlite3 scratch DB, same convention as this repo's existing
`tests/test_dispatch_owner_task_status_write.py`). The key test,
`test_wrapper_refuses_second_differently_worded_pr131_dispatch`, reproduces
the incident directly:

1. Dispatches a real task via `dispatch-owner-task.sh` titled "Desktop
   sentinel: RCA for PR #131" — succeeds, records `umr_id`.
2. Independently confirms `check-content-duplicate` (the pre-existing
   exact-hash layer) does **not** flag the second prompt — proving the
   wording is genuinely different, matching the real incident's
   "resource_governor.py --search ... returned nothing" observation.
3. Dispatches a second, differently-worded task ("Desktop session: land fix
   for PR #131") within the same run (well inside the 4h window) — **this
   is refused** (`REFUSED: a queued/running dispatch within the last 4h
   already targets the exact same PR/file/script`), citing the first real
   `umr_id`.
4. Queries the real scratch `umr_tasks` table directly and confirms exactly
   one live (`queued`/`running`) row exists for PR #131, not two — the real
   proof the incident (two concurrent workers against the same PR branch)
   cannot recur.

Also covered: the pure `extract_target_identifiers` function (PR+repo /
bare PR needs a repo / file path / script name), 4h window + `queued`/
`running`-only status scoping, the CLI subcommand round-trip, and a
not-over-broad check (the same PR *number* in a genuinely different repo is
correctly allowed, not refused).

```
$ python3 -m pytest tests/test_target_identifier_dedup.py \
  tests/test_dispatch_owner_task_status_write.py \
  tests/test_dispatch_owner_task_tmux_relay_lock.py \
  test_resource_governor_owner_priority_advance.py -v
============================== 26 passed ==============================
```
No regressions in the pre-existing dispatch-owner-task.sh / resource_governor.py
test coverage this change touches.

## What was NOT done (explicitly out of scope / not this task's authority)

- Did not merge `veridian-scripts#297` — workers never merge/push-main;
  left for real review, same standing rule the prior status report in this
  chain (`UMR-...-9a69`) already documented for `veridian-scripts#292`.
- Did not touch `claude-control#131` or `claude-control/scripts/` — that
  directory is retired (`scripts/README-RETIRED.md`); adding real
  server-side logic there would repeat the exact wrong-repo mistake already
  root-caused in this chain's own history.
- Did not modify `check-content-duplicate` or `--search`/FTS5 — both stay
  as independent, complementary layers; this addendum adds a third, it does
  not widen or replace either existing one.
