# Fix the two failing GTM certification categories (OCID-020 cat 17 + cat 23)

## Investigation summary
- category_index=17 "browser compatibility": webkit fails at `browserType.launch`
  (before any page load) with Playwright's own "Host system is missing
  dependencies" error naming `libgles2` and `gstreamer1.0-libav` (needs
  `sudo apt-get install ...`). Independently re-verified: `sudo` genuinely
  requires a password (`timeout 5 sudo whoami < /dev/null` -> "a password is
  required"), and the root-free mount-namespace workaround
  (`unshare --map-root-user --mount`) is blocked by
  `apparmor_restrict_unprivileged_userns=1`. This is a real host/test-runner
  infra gap, NOT a front-end/product defect -- there is no product code path
  reachable before browser launch fails. Docker-group-based host root
  escalation is technically available (user is in `docker` group, docker
  works) but that is a high-blast-radius privileged action on a live shared
  host (other production containers running) -- out of scope for a
  front-end fix and not attempted without explicit authorization.
- category_index=23 "UX audit": live evidence_json shows H2/H4/H10 at
  severity 3. Root cause found in compliance-tracker: OCID-038
  GAP-OCID038-PROJEXA-DOMAIN-BRAND-MISMATCH Stage 1
  (`resolvePreAuthBrandByHost` in org-branding-service.ts) already resolves
  the real per-host brand ("PROJEXA" for projexa-ai.com) correctly on
  /login, but /signup, /pricing, /contact still hardcode "VERIDIAN AI" /
  "VERIDIAN COGNITIVE AI OS" literally in JSX (prior fix commits claiming
  this was done for signup/pricing do not match current origin/main file
  content -- regressed or superseded). /help has no real pre-auth content,
  just a redirect to /login.

## Completed
- [x] Read both real check scripts (gtm_check_browser_compatibility.py,
      gtm_check_ux_audit.py) to learn exact pass criteria.
- [x] Queried superboss-register.sqlite directly (python3 + sqlite3 module,
      read-only URI) for both categories' evidence_json.
- [x] Independently re-verified category 17 is a genuine root-only OS
      dependency gap (not front-end): sudo blocked, unprivileged userns
      blocked.
- [x] Root-caused category 23: found the real per-host brand resolution
      mechanism and confirmed which pre-auth pages don't use it yet.
- [x] Set up clean git worktree off origin/main for compliance-tracker
      (local checkout had unrelated uncommitted WIP from other tasks).

## Remaining
- [ ] Apply `resolvePreAuthBrandByHost` (title + visible brand text) to
      /signup, /pricing, /contact, matching /login's existing pattern.
- [ ] Add a real pre-auth /help page (no redirect-to-login) with genuine
      content, using the resolved brand.
- [ ] Nav/footer consistency pass across pricing/contact (Pricing link
      naming, footer link parity) -- best-effort within scope.
- [ ] Run `bun run build` / lint in the worktree to confirm no breakage.
- [ ] Commit + push branch, open real PR against compliance-tracker.
- [ ] Re-run gtm_check_ux_audit.py unmodified against the deployed fix and
      confirm a genuine pass (requires live projexa-ai.com to be running
      the merged/deployed code -- verify deployment path).
- [ ] For category 17: document honestly that this is a real, confirmed
      infra-only blocker outside front-end code, not fabricate a pass.
- [ ] Write final audit citing real head SHA; call
      agent_work_briefing.py record-completion.
