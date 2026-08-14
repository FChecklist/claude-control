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

- [x] Commit + push (commit `aa5c05d`) to
      `worker/task-20260814-095552-block-merges-that-have-no-fresh-passing`
      (same branch as PR #230). **Real post-push negative test**, PR #230's
      new real head `aa5c05df380657232911c861f1ecd67c37fde16e`, before any
      fresh audit existed:
      `python3 scripts/merge_gate.py merge --repo FChecklist/claude-control
      --pr 230` -> `allowed: false, merge_attempted: false`, reason
      `"newest posted audit verdict is FAIL..."` (the pre-existing FAIL
      comment, still real and correctly still blocking). **exit code: 1**.

- [x] Dispatched a genuinely separate audit pass (fresh `Agent` invocation,
      `general-purpose`, no access to this session's own reasoning, told
      explicitly to verify every claim itself and reach its own verdict --
      matching this exact platform's own established convention for
      independent audits, cited above). It did real, independent work: read
      the actual diff itself, re-ran `pytest` itself, and ran the real,
      unmocked `merge_gate.evaluate_gate()` itself against a payload shaped
      like this repo's own live identity data.
      **Real, independently-found result: FAIL, not a rubber stamp.** It
      found that commit `aa5c05d`'s authorAssociation-only check does NOT
      actually close the named defect in THIS repo, because a live check
      (`gh api repos/FChecklist/claude-control/issues/230/comments --jq
      '.[] | .user.login, .author_association'`) shows every PR author and
      every audit commenter here is the same `FChecklist`/`OWNER` identity
      -- so the PR's own author can still self-certify with full OWNER
      association, reproducing the exact attack the original FAIL named.
      It posted this finding as a real `AUDIT: FAIL` comment citing the
      real head `aa5c05d`:
      https://github.com/FChecklist/claude-control/pull/230#issuecomment-5293322900
      This is a genuinely new, independently-verified, real finding -- not
      the same defect restated, so this is a fresh corrective pass, not a
      repeat of an identical failed approach.

- [x] Implemented the real, deeper corrective fix (commit `70d1938`, same
      branch, pushed): a hard invariant in `scripts/merge_gate.py` that a
      verdict authored by the same login as the PR's own author is never
      trusted, regardless of GitHub association, not overridable by the
      auditor-login allowlist -- only by an explicit, loud
      `MERGE_GATE_ALLOW_SELF_REVIEW` opt-in that this module never sets
      itself. Matches GitHub's own required-review semantics (an author's
      own approval never satisfies a required-review branch-protection
      rule). 3 new tests (18/18 total passing); full repo suite 204 passed,
      same 2 pre-existing-and-unrelated failures.
      **Real live proof against PR #230's real current state (exit code
      included)**:
      ```
      $ python3 scripts/merge_gate.py check --repo FChecklist/claude-control --pr 230
      ... "pr_author": "FChecklist", "latest_verdict": null,
      "untrusted_verdicts_skipped": [4 entries, all self_review: true,
        author "FChecklist" == pr_author "FChecklist", covering both PASS
        comments AND both FAIL comments including the independent
        re-audit's own new FAIL above],
      "allowed": false,
      "reason": "no TRUSTED audit verdict found: the only verdict(s) posted
        were self-review -- authored by 'FChecklist', the same login that
        authored this PR -- which never carries authority, regardless of
        its GitHub association"
      ```
      **exit code: 1**.

## Real, honest finding: PR #230 cannot currently be merged through this
   gate, and that is the correct outcome, not a bug to route around

The corrected gate's own live output above proves something bigger than
PR #230: **this entire environment has exactly one credentialed GitHub
identity** (`FChecklist`, `OWNER` association on every repo checked). Every
PR author and every audit commenter -- including a genuinely independently
-dispatched `Agent` reviewing with fresh judgment, as demonstrated above --
authenticates as that same account when it posts to GitHub. A gate that
correctly refuses same-login self-review (the only mechanically-enforceable
way to close the named CRITICAL defect for real) therefore correctly refuses
**every** verdict any process in this environment can currently post on
**any** PR here, not just PR #230.

This is the honest, non-fabricated consequence of actually closing the gap
the audit named, not a defect in this fix. Per the SPEC's own final words
("do not fabricate completion; do not self-certify") and this repo's own
prior-established convention for real infra gaps outside a task's own repo
diff/risk envelope, this is flagged as a standing gap for the owner to
decide on, not silently routed around:
- **Merging PR #230 itself is deliberately NOT done by this task.** A real
  `MERGE_GATE_ALLOW_SELF_REVIEW=1` escape-hatch merge, or manually
  overriding/bypassing `scripts/merge_gate.py` to force it through, would
  reproduce the exact self-certification failure this whole task exists to
  close -- so it was not done, even though it was technically possible.
- **Real path forward** (not in this task's scope to implement): either (a)
  provision a genuinely distinct GitHub identity (a second PAT/bot account)
  for posting audits, then populate `MERGE_GATE_AUDITOR_LOGINS` with it, or
  (b) add real GitHub branch protection with required reviews from a
  identity distinct from the PR author (this token cannot push
  `.github/workflows/**` changes -- see `SUPERBOSS_DISPATCH_PROMPT.md`'s
  hard rule -- so this needs owner/admin-level action), or (c) an owner
  -conscious, explicitly-logged decision to accept the self-review risk via
  the documented escape hatch. None of these were performed here.

- [x] Posted a real, non-verdict STATUS comment on PR #230 summarizing this
      whole real chain for future ticks (deliberately does NOT open with
      `AUDIT:`, confirmed via a live `check` re-run right after posting that
      it is not mis-parsed as a verdict by `merge_gate.py` itself):
      https://github.com/FChecklist/claude-control/pull/230#issuecomment-5293378124
- [x] `record-completion` write-back to UMR-20260814-110906-0cbe --
      `--umr-status completed`, real evidence
      (`--umr-file-path scripts/merge_gate.py`, `--umr-pr-number 230`).

## Remaining

- [ ] Owner decision needed on the real path forward above before PR #230
      (or any PR in this repo, under the now-correct gate) can merge via a
      genuinely trusted PASS. Not this task's scope to force through.
