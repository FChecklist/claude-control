# task-20260814-121853-fix-the-audited-fail-merge-gate-so-unaud

Governing chain: PM-sentinel tick. Real evidence gathered 2026-08-14T11:00Z:
claude-control PR #230 ("Real deterministic merge gate wired into both real
merge call sites") had head `f41abcdf` and its newest comment (10:20Z) was a
real `AUDIT: FAIL`, superseding two earlier `AUDIT: PASS` comments that cited
now-stale heads (`a05492fe`, `536050a9`). This task reads that FAIL comment
for real, fixes the exact named defect on the same PR branch, proves the fix
with a real negative test, and gets a fresh independent audit before merging.

## Completed

- [x] Read the real `AUDIT: FAIL` comment body on PR #230 in full (not
      truncated) via `gh api repos/FChecklist/claude-control/issues/230/comments`.
      Named defect, extracted verbatim, not guessed: `scripts/merge_gate.py`'s
      `find_latest_verdict()` accepted an `AUDIT: PASS`/`AUDIT: FAIL` verdict
      from **any** PR commenter/reviewer with **zero identity check** -- no
      `authorAssociation` filter, no bot/service-account allowlist. Combined
      with the real, confirmed absence of GitHub branch protection on both
      claude-control and veridian-scripts (404/403 on the branch-protection
      API), `merge_gate.py` is the sole enforcement mechanism, so anyone with
      repo comment access -- including the PR's own author -- could
      self-approve a merge by posting a fabricated `AUDIT: PASS` citing the
      current head. Suggested remedy, quoted verbatim from the audit: "Needs
      an author allowlist or authorAssociation check (e.g. require
      OWNER/MEMBER or a specific service-account login) before this can be
      trusted as a real merge gate."
      Minor/unverified note in the same comment (deployment path
      `/opt/veridian/scripts/merge_gate.py`) independently confirmed as
      **expected, not a bug**: `/opt/veridian/repos/claude-control` (the live
      checkout `/opt/veridian/scripts` is synced from) is still at `master`
      HEAD `e1edd4e`, i.e. PR #230 genuinely has not merged into master yet --
      so `/opt/veridian/scripts/merge_gate.py` correctly does not exist there
      yet; it will land once PR #230 merges and the existing auto-sync
      mechanism (PR #229) runs, same as every other real script deployed from
      this repo's `scripts/` directory.

- [x] Checked out the SAME branch as PR #230
      (`worker/task-20260814-095552-block-merges-that-have-no-fresh-passing`,
      real head `f41abcdfaf55037ee68b3fbbcf945995529b0383` at start) and
      implemented the real corrected fix for the named defect in
      `scripts/merge_gate.py`:
      - `get_pr_snapshot()` now also fetches the PR's real `author` and each
        comment/review's real, live `authorAssociation` field from `gh pr
        view --json` (both already returned natively -- no extra API call).
      - New `TRUSTED_AUTHOR_ASSOCIATIONS` (default `OWNER,MEMBER,COLLABORATOR`,
        overridable via `MERGE_GATE_TRUSTED_ASSOCIATIONS`) and an explicit
        `MERGE_GATE_AUDITOR_LOGINS` allowlist (unset by default -- honestly
        documented as "not yet populated": this environment has exactly one
        credentialed GitHub identity, `FChecklist`/OWNER, used for every PR
        author and every audit comment alike, confirmed live via `gh api
        repos/.../issues/230/comments --jq '.[] | .user.login,
        .author_association'` on PR #230's own real comments -- so a
        login-based self-vs-auditor distinction is not achievable here yet;
        this is the real, available layer of defense, matching the audit's
        own suggested remedy verbatim).
      - `find_latest_verdict()` now skips (not just downgrades) any
        verdict-shaped comment/review whose author fails the trust check --
        for PASS *and* FAIL alike, so an untrusted commenter can neither
        force an allow nor deny-of-service a real trusted PASS -- and keeps
        scanning older events for the newest genuinely-trusted verdict.
      - `evaluate_gate()` reports a new, distinct refusal reason ("no TRUSTED
        audit verdict found...") plus a new `untrusted_verdicts_skipped` list
        in the decision object for auditability, whenever every verdict-shaped
        event found was untrusted.
      - Module docstring's "real deterministic refusal conditions" list
        updated to document condition 0 (UNTRUSTED VERDICT SOURCE) ahead of
        the existing NO VERDICT / FAILING VERDICT / STALE PASS conditions.

- [x] Extended `tests/test_merge_gate.py` for real (not rebuilt as a
      self-report): updated the `_comment`/`_pr_view_json` test helpers to
      carry a real `authorAssociation` (default `OWNER`, so all 10
      pre-existing scenarios keep exercising verdict/staleness logic
      unaffected), and added 6 new tests exercising the identity gate
      directly: untrusted PASS is ignored (not trusted) even citing the
      correct head SHA; the PR's own author posting a self-cert PASS with no
      real association is still refused (the exact attack the audit named);
      an untrusted newer PASS/FAIL cannot shadow or sabotage a real trusted
      older verdict (skip, don't stop-and-trust, don't stop-and-block); and
      the `MERGE_GATE_AUDITOR_LOGINS` allowlist, when set, overrides the
      association check in both directions (an OWNER-associated non-allowlisted
      login is refused; a no-association allowlisted login is trusted).
      **Real run, this exact head, all passing**:
      `python3 -m pytest tests/test_merge_gate.py -v` -> **15/15 passed**.
      Full repo suite: `python3 -m pytest tests/ -q` -> **201 passed, 2
      failed** -- both pre-existing and unrelated to this change, confirmed
      by re-running the identical 2 tests against the pre-fix commit
      (`git stash` back to `f41abcd`): same 2 failures
      (`hold_for_signoff_test.py::test_hold_for_signoff_blocks_tier1_automerge`,
      `test_merge_execution.py::test_merge_execution_runs_when_approved_tier1_and_pr_url_resolved`,
      both a real `HOLD_FOR_OWNER_SIGNOFF: unbound variable` bug in
      `tests/supervisor_merge_detection_test.sh` unrelated to merge_gate.py),
      already documented as pre-existing by the prior task's own progress
      file. `tests/supervisor_merge_gate_test.sh` (invoked with this repo's
      own `scripts/supervisor-entrypoint.sh` since `/opt/veridian/scripts/`
      doesn't have PR #230's not-yet-merged content, same expected-gap noted
      above) -> **4/4 scenarios passed**.

- [x] **Real negative test, exit code and output included** (SPEC step 3):
      `python3 scripts/merge_gate.py check --repo FChecklist/claude-control
      --pr 230` against the real, live, unmerged PR #230, BEFORE this fix's
      commits existed on the branch:
      ```
      {
        "pr_url": "https://github.com/FChecklist/claude-control/pull/230",
        "head_sha": "f41abcdfaf55037ee68b3fbbcf945995529b0383",
        "latest_verdict": {"verdict": "FAIL", "cited_sha": null,
          "author": "FChecklist", "author_association": "OWNER",
          "ts": "2026-08-14T10:20:08Z", "kind": "comment"},
        "untrusted_verdicts_skipped": [],
        "allowed": false,
        "reason": "newest posted audit verdict is FAIL (by FChecklist at 2026-08-14T10:20:08Z)"
      }
      ```
      **exit code: 1**. (Second, post-push negative-test run against the new
      head -- now demonstrating the classic *stale-SHA* refusal path by
      construction, since pushing this fix moves the head again and makes
      both earlier PASS comments' cited SHAs stale relative to it -- appended
      below once pushed, so the exact head cited is real and final.)

## Remaining

- [ ] Commit + push this fix to
      `worker/task-20260814-095552-block-merges-that-have-no-fresh-passing`
      (same branch as PR #230).
- [ ] Real post-push negative test against the new head (stale-SHA scenario,
      exit code + output).
- [ ] Per this platform's own established convention (already documented on
      this exact PR by the prior task's own progress file: "independent
      audits are their own separately-dispatched worker tasks, not something
      the fixing worker can force/self-issue") -- dispatch a genuinely
      separate audit pass (fresh Agent context, no access to this session's
      own reasoning about whether the fix is correct) to independently
      review the new head and, only if it is real and passes, post a real
      `AUDIT: PASS` citing that exact head SHA.
- [ ] Only merge via `scripts/merge_gate.py merge` once that fresh, trusted,
      SHA-matching PASS exists -- gated by the tool itself, not by this
      task's own self-report.
- [ ] `record-completion` write-back to UMR-20260814-110906-0cbe.
