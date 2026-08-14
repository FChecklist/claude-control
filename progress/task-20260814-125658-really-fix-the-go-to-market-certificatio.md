# Really fix the go-to-market certification gate

UMR-20260814-125428-4385. This is the 4th attempt at this SPEC. Attempts 1-3
are documented in the SPEC itself as producing ZERO real change (files_touched=[]
or PR containing only progress/*.md). This file tracks a genuinely different
approach: instead of re-investigating the SPEC's stale "2 hard-FAIL categories"
premise a 4th time, this task independently re-measured the live registry,
found the REAL current state (7 FAIL, 2 blocked, 16 pass, 0 stale -- not "2
hard-FAIL / 18 stale"), and is landing real product-code fixes in the repos
that actually own the fixable defects (compliance-tracker's dependencies,
veridian-ui-kit, veridian-scripts), not just in claude-control (which is a
docs/index repo by its own README -- "not a product").

## Completed
- [x] Independently re-measured `gtm_certification_categories` (25 rows) via
      read-only `sqlite3.connect('file:...?mode=ro', uri=True)` (never
      opened read-write by hand). Real current state as of this task's
      start: **PASS 16, FAIL 7 (2,3,17,19,20,23,25), BLOCKED 2 (10,11,
      real safety-gate refusals -- low swap), stale(>7d) 0**. This
      supersedes the SPEC's "2 hard-FAIL / 18 stale" premise, which was
      true when the SPEC was written but was already refreshed for real
      (registry writes, not git-tracked) by the immediately-prior attempt.
- [x] Confirmed root/sudo is genuinely, freshly unavailable this session
      (`sudo whoami` -> "a password is required"), consistent with 3 prior
      independent investigations.
- [x] Re-confirmed category 17 (browser compatibility) is a genuine,
      real, root-only blocker with NO possible product-code fix: read
      `gtm_check_browser_compatibility.py`'s full docstring (root-caused to
      source level: Playwright's `missingDLOPENLibraries()` reads the
      system-wide `/sbin/ldconfig -p` cache directly, no LD_LIBRARY_PATH
      override possible) -- independently verified this is not fabricated,
      it is real and current. No 4th re-investigation attempted; this
      would repeat an already-exhausted approach.
- [x] Found and fixed the REAL underlying defects for category 3 (security
      audit), which is a genuine current hard-FAIL not named by the SPEC's
      stale premise but real right now:
  - Ran the actual `gtm_check_security_audit.py` fresh (fresh clone, HEAD
    `21dda46336905c00d5c13d8b3c476f9eab0b6e3c`): gitleaks 1 finding, trivy
    1 HIGH (both real, confirmed by hand below).
  - **gitleaks finding**: `ai-os/OCID-056-CREDENTIAL-EXPOSURE-REPORT.md:36`
    quotes the same known-safe test-fixture literal
    (`whsec_test_secret_1234567890`) already cleared under this repo's
    existing Group-B gitleaks exemptions. Fixed in
    `FChecklist/veridian-scripts` PR #372 (branch
    `fix/ocid-020-cat3-gitleaks-ocid056-doc-fingerprint`, commit `851693f`):
    added the 1 new fingerprint to `gtm_security_audit_gitleaksignore.txt`.
    Verified: `gitleaks detect --source . --no-git --gitleaks-ignore-path
    <patched file>` against the same fresh clone -> "no leaks found".
  - **trivy HIGH finding**: `CVE-2026-67213` (nanoid DoS), nanoid 3.3.17
    resolving transitively via `@fchecklist/veridian-ui-kit`'s own bundled
    `bun.lock` (postcss -> nanoid). Root-caused: not actually installed
    anywhere in compliance-tracker's real `node_modules` (verified via
    `find node_modules -iname nanoid -type d`), but trivy correctly flags
    it as a real vulnerable version pinned in a shipped lockfile. Fixed in
    `FChecklist/veridian-ui-kit` PR #7 (branch
    `fix/ocid-020-nanoid-cve-2026-67213`, commit `ce6a4d0`): added
    `"nanoid": "^3.3.18"` to `package.json` `overrides` (same pattern as
    the existing `postcss` override from this repo's own prior CVE-fix
    commit `625583e`). Verified: `bun install` resolves nanoid to 3.3.18,
    `bun run typecheck` passes clean, `trivy fs .` now reports 0
    vulnerabilities (was 1 HIGH).
  - Both fixes pushed as open PRs, NOT self-merged (this repo's established
    precedent: a fixing worker cannot force/self-issue its own re-audit --
    same reasoning applied by the immediately-prior attempt to PR #231/#1145).
    Registry row 3 updated via the canonical `gtm_write_category_result.py`
    writer with `--result fail` (honest -- unmerged fixes do not change the
    live main-branch check result) but with full fix evidence
    (`fix_pr_number=372`, both PR URLs/commits/verification detail in
    `evidence_json`).

## Remaining
- [ ] Category 23 (UX audit): PR #1145 (compliance-tracker) already has a
      real, prior-session product fix. Re-check its current mergeable/CI
      state and push a real rebase if conflicting (in progress).
- [ ] Category 2 (static code analysis): `tsc --noEmit` OOMs on this host
      (heap exhaustion, not a real type error) -- investigate a real,
      non-fabricated fix (e.g. raising Node's heap limit for the tsc
      invocation) vs. confirming it is a genuine host-resource blocker.
- [ ] Categories 19 (backup recency) and 20 (monitoring units): both look
      root-cause-linked to disabled `systemctl --user` timers/services --
      investigate whether enabling them is within this task's authority
      and safe (many other cron timers on this host are also currently
      disabled; avoid an unscoped mass-enable).
- [ ] Close FChecklist/claude-control PR #231 (the doc-only PR from prior
      attempt 2) as superseded by this task.
- [ ] Re-run every category's real check fresh at the end and report the
      honest final tally (pass/fail/blocked out of 25).
- [ ] Post real evidence, commit real progress, open this task's own PR
      with real changed files (this progress doc plus, if applicable,
      claude-control-scoped changes) -- or, if claude-control genuinely has
      no code of its own to change, document explicitly why the real fixes
      live in compliance-tracker/veridian-ui-kit/veridian-scripts instead
      and link those PRs as the real artifacts of this task.
