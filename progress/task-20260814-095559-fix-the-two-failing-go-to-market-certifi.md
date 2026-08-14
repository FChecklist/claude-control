# Fix the two failing GTM certification categories (OCID-020 cat 17 + cat 23)

## Completed
- [x] Read both real check scripts and independently queried
      superboss-register.sqlite (python3 + sqlite3 module, read-only URI)
      for both categories' live evidence_json.
- [x] Category 17 root-caused and independently re-verified as a genuine,
      root-only host OS dependency gap (Playwright webkit `browserType.launch`
      fails on missing `libgles2`/`gstreamer1.0-libav`), NOT a front-end
      defect -- there is no product code path reachable before launch fails.
      Re-confirmed this session: `sudo` genuinely requires a password
      (`timeout 5 sudo whoami < /dev/null` -> "a password is required"), and
      the root-free `unshare --map-root-user --mount` workaround is blocked
      by `apparmor_restrict_unprivileged_userns=1`. Docker-group host-root
      escalation is technically available on this shared host but is a
      high-blast-radius action outside a front-end-fix task's scope --
      deliberately not used. **No product code change is possible for
      category 17; documented honestly rather than gamed.**
- [x] Category 23 root-caused in compliance-tracker: OCID-038
      GAP-OCID038-PROJEXA-DOMAIN-BRAND-MISMATCH Stage 1
      (`resolvePreAuthBrandByHost`) was applied only to /login; /signup,
      /pricing, /contact still hardcoded "VERIDIAN AI"/"VERIDIAN COGNITIVE
      AI OS" (H2/H4 severity-3). /help redirected every unauthenticated
      visitor straight to /login with zero content (H10 severity-3) --
      root-caused to `src/proxy.ts` + `scripts/generate-protected-routes.mjs`
      treating "/help" as a protected `(app)` route prefix.
- [x] Real product fix implemented in a clean worktree off origin/main
      (local checkout had unrelated uncommitted WIP from other tasks):
      brand resolution extended to /signup, /pricing, /contact; /contact
      nav "On cost" -> real "Pricing" link + added footer link parity;
      `/help` carved out as the one documented public exception in the
      route-protection generator, and `(app)/help/page.tsx` now renders
      real pre-auth FAQ content for anonymous visitors (full authenticated
      help center unchanged, moved to help-center-content.tsx);
      `(app)/layout.tsx` skips the authenticated-only AppShell chrome for
      anonymous visitors.
- [x] Registered ACTIVE-CLAIMS entry (AGENTS.md Rule 11) before starting
      real edits; sanity-checked all edited files with `bunx tsc --noEmit`
      (module-resolution-only errors from bypassing tsconfig path aliases;
      no genuine syntax/type errors from these edits -- full-repo `tsc`
      OOMs in this environment regardless of these changes).
- [x] Committed + pushed compliance-tracker branch
      `worker/task-20260814-095559-fix-the-two-failing-go-to-market-certifi`
      at commit `101704a31ba3147a9c09086e9811e417b81d3334`, opened real PR:
      https://github.com/FChecklist/compliance-tracker/pull/1145
- [x] Committed + pushed this task's own progress file in claude-control
      (commit `4f29fb00fa936ab6d02e4ba85181a25f5bd9a8ca`).

## Remaining (honest, not yet done -- budget exhausted this session)
- [ ] PR #1145 has NOT yet been reviewed/merged by CI (Rule 6 branch
      protection: no direct push to main). Until it merges and Vercel
      redeploys projexa-ai.com from the merged commit, the LIVE site still
      serves the pre-fix code -- re-running
      `gtm_check_ux_audit.py` right now would still show the same
      severity-3 findings, not because the fix is wrong but because it
      is not live yet. **Do not report category 23 as passing until
      after merge + redeploy + a fresh, real, unmodified run of
      gtm_check_ux_audit.py actually shows pass.**
- [ ] Once merged and redeployed: re-run
      `python3 /opt/veridian/scripts/gtm_check_ux_audit.py` unmodified and
      confirm a genuine pass; if any residual finding remains (e.g. nav
      link-set differences between the marketing site and the product app
      were only partially addressed -- brand name and Pricing link were
      unified, but /login+/signup's minimal-by-design nav vs /pricing's
      product nav vs /contact's marketing nav are still structurally
      different navs), iterate on the real fix, don't loosen the check.
- [ ] Category 17: no further action possible without root or an
      explicitly-authorized, high-blast-radius infra action on this shared
      host (this session deliberately did not take that action). Flag to
      the user/PM for an explicit decision rather than silently leaving it
      failing forever.
- [ ] Call `agent_work_briefing.py record-completion` with
      `--gtm-category-index 23` once the live re-check genuinely passes
      (not yet done this session -- see above).

## Key evidence for anyone continuing this
- Category 17 real evidence: `/tmp/cat17_evidence.json` (this session's
  sqlite read) -- webkit `browserType.launch` error names exactly
  `libgles2`, `gstreamer1.0-libav`.
- Category 23 real evidence: `/tmp/cat23_evidence.json` -- H2/H4/H10
  findings and rationale.
- compliance-tracker PR: https://github.com/FChecklist/compliance-tracker/pull/1145
  (head commit `101704a31ba3147a9c09086e9811e417b81d3334`).
