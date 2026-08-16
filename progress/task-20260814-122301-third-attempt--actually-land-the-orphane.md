# Task: actually land the orphaned server-native PM sentinel (3rd attempt, verify-everything-yourself)

## Completed
- [x] Verified the governing ancestry claim myself, fresh, after `git fetch origin` in `/opt/veridian/repos/claude-control`:
  - `git rev-parse origin/main` -> **fails** (`fatal: ambiguous argument 'origin/main'`) -- confirms there is no `main`, only `master`.
  - `git rev-parse origin/master` -> `e1edd4e481b9fb8ea25ae435bc4866f0c7b51e4d`.
  - `git merge-base --is-ancestor 6a78798 origin/master` -> **exit 1** (not an ancestor). Matches the SPEC's claim exactly.
  - `git branch -r --contains 6a78798` -> only `origin/pr/131`, `origin/worker/task-20260813-084351-...`. Matches SPEC.
- [x] Searched all 8 known repos (compliance-tracker, claude-control, veridian-scripts, projexa, veda-advisors, global-revenue-engine, veridian-brain, sumeet-spec) via `find_code.sh` and `git log --all --grep` for `pm-sentinel`/`server-native`. No matches in compliance-tracker, projexa, veda-advisors, global-revenue-engine, veridian-brain, sumeet-spec. Real matches in **claude-control** and **veridian-scripts**.
- [x] **Key finding: the literal SHA `6a78798` is orphaned (true), but its real content is NOT unlanded.** A prior task in this same lineage (`task-20260814-095513-land-the-orphaned-audited-server-native`) already:
  - cherry-picked `6a78798` onto fresh `origin/master` (commit `dda3deb9`, content byte-identical),
  - opened real PR **#227** (`worker/task-20260814-095513-land-6a78798-pm-sentinel` -> `master`),
  - and it was genuinely **squash-merged** -> new master head `0cb827d8de31be7e943136d70f5b2d40cb56a3a2`.
  - Squash merges always mint a new SHA, so `6a78798` itself can never become an ancestor -- that's *expected*, not evidence of non-landing. The correct check is content-equivalence + ancestry of the *merge* commit, both of which I re-ran independently:
    - `git merge-base --is-ancestor 0cb827d origin/master` -> **exit 0**.
    - `git diff --quiet 6a78798 0cb827d -- scripts/pm-sentinel-tick.sh scripts/systemd/veridian-pm-sentinel-tick.service scripts/systemd/veridian-pm-sentinel-tick.timer scripts/test_pm_sentinel_tick.py` -> **exit 0, zero output** (byte-identical).
    - `git cat-file -e origin/master:scripts/pm-sentinel-tick.sh` -> **exists**.
    - `gh pr view 227 --json state,mergedAt,mergeCommit` -> real GitHub state: **MERGED**, `mergeCommit.oid = 0cb827d8de31be7e943136d70f5b2d40cb56a3a2`.
  - So requirement (3) ("open ONE real PR ... merge on PASS") was already genuinely satisfied by PR #227 -- opening a second, duplicate PR for the same already-landed content would itself be the kind of self-duplicating busywork this task's protocol warns against (wiring_registry already flagged one matching row for this scope).
- [x] **Gap I actually found and fixed:** PR #227's only "audit" comment was posted by the *same* task/account that authored and merged it -- a self-audit, not an independent one. I performed a genuinely independent re-verification (fresh task, re-ran every command from scratch, did not trust the prior progress note) and posted it as a real PR comment: https://github.com/FChecklist/claude-control/pull/227#issuecomment-5293285967 -- **Verdict: PASS**.
- [x] Requirement (4), re-proven fresh just now: ancestor check against `origin/master` for the literal orphan SHA still correctly returns non-ancestor (exit 1, expected post-squash); the merge-commit SHA `0cb827d` returns ancestor (exit 0); `scripts/pm-sentinel-tick.sh` confirmed present on `origin/master`.
- [x] Requirement (5), which SHA is actually RUNNING on this server right now:
  - `/opt/veridian/scripts` is itself a live git checkout, but of a **different** repo: `veridian-scripts`, not `claude-control`.
  - `git rev-parse HEAD` there = `origin/main` HEAD = `3173e09ec13b250cd34dbd4e49576635ee646c1b` (fully in sync, `git fetch` shows no new changes).
  - `git diff --quiet -- pm-sentinel-tick.sh` in that checkout -> **exit 0** (clean, no live-deploy drift).
  - The file was last content-modified there by commit `f9b4101` ("fix(pm-sentinel-tick): stop re-dispatching RCA for already-closed killed rows (#341)"), a real further evolution of the same original feature (through real merged PRs #299, #318, #323, #341, etc. in `veridian-scripts`).
  - So: the *audited historical record* of `6a78798` lives correctly on `claude-control`'s `origin/master` (via PR #227 / `0cb827d`); the *actual running* sentinel on this box today executes a newer, further-developed copy of the same script from `veridian-scripts`'s `origin/main` @ `3173e09`. Both are real, both are git-verified, neither is drifted or fabricated.
- [x] Note on tooling: `git show <ref>:<path> | sha256sum` was silently truncated by a sandbox-level output limiter for this ~65KB file (repeatably returned a truncated 1981-byte prefix ending in a literal `"... more files changed"` marker, NOT real file content) -- caught this by cross-checking against `git cat-file -s` (real blob size 64905, matching the deployed file's real `stat` size) and `git diff --quiet` (authoritative, zero-output-on-match, immune to output truncation). Relied on `git diff --quiet`/`merge-base --is-ancestor`/`cat-file -e` exit codes throughout, not on piped-hash comparisons, for anything load-bearing.

- [x] Ran `progress_completion_gate.py check-completion` against this branch myself to be transparent about it, rather than let it surprise a reviewer: it correctly extracts `pm-sentinel-tick.sh` as a named objective file from `prompt.txt`, and since this branch's diff (relative to `origin/master`, which already contains the file byte-identical via PR #227) legitimately touches no code, it returns `ok=False` / exit 1 ("diff touches no code"). This is a real, known limitation of that gate for this specific case class -- "objective file already present, unchanged, in the merge-base because a prior task already landed it" -- not covered by its existing `_BOILERPLATE_TOOL_NAME_EXCLUDED`/evidence-list exceptions. I deliberately did **not** make a cosmetic/no-op edit to the live, hourly-running production script just to force a green diff through the gate -- that would be gaming the check, not real work, and adds real risk to a script that already executes on this server every hour. Recording this explicitly so it is not mistaken for an unnoticed failure.

## Remaining
- [x] Call `agent_work_briefing.py record-completion` with the real summary.

## Evidence
- Original orphaned commit: `6a78798ebd7280c28727879167201591e019fb14` (claude-control)
- Already-landed via: PR https://github.com/FChecklist/claude-control/pull/227 (MERGED, squash commit `0cb827d8de31be7e943136d70f5b2d40cb56a3a2`, ancestor of current `origin/master` `e1edd4e4`)
- My independent audit comment: https://github.com/FChecklist/claude-control/pull/227#issuecomment-5293285967
- Live-running copy: `veridian-scripts` `origin/main` @ `3173e09ec13b250cd34dbd4e49576635ee646c1b`, deployed clean (no drift) at `/opt/veridian/scripts/pm-sentinel-tick.sh` on this server.
