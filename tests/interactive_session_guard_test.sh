#!/bin/bash
# Regression test for the interactive-session write gate (real incident
# 2026-07-26: an interactive session ran `gh pr merge 78 ...` and a direct
# `git push` retrigger commit to compliance-tracker's `main` by hand instead
# of going through the real dispatch pipeline). See
# ai-os/OWNER_DIRECTIVES/interactive-session-guard.bashrc-snippet (the real
# guard, sourced from rajat's ~/.bashrc/~/.profile on VERIDIAN-DEV) and
# ai-os/OWNER_DIRECTIVES/PROTOCOL_OWNER_AI.yaml article A15.
#
# This test sources the REAL shipped snippet (not a re-implementation), so it
# fails the moment the shipped guard drifts from what this test verifies. It
# never touches the real `gh`/`git` binaries or real GitHub -- a fake bin/
# dir is placed first on PATH so the guard's own PATH search for the "real"
# binary (with its own directory excluded) resolves to harmless fakes that
# log whether they were invoked. INTERACTIVE_GUARD_DIR points the guard's
# installation directory at a throwaway fixture dir for every case, so this
# test never writes into the real $HOME.
#
# ROUND 2 additions (each proven blocked here, not just asserted in prose):
#   1. `export INVOCATION_ID=<anything>` alone no longer passes the gate --
#      a second, kernel-tracked cgroup signal is now required too.
#   2. `command git ...` / `command gh ...` no longer bypasses the guard --
#      the guard is now PATH-resolved wrapper scripts, not shell functions,
#      so `command` (which only skips functions/aliases, never PATH search)
#      still finds them.
#   3. `gh api -X PUT|PATCH .../pulls/<n>/merge` is now detected as a merge,
#      same as `gh pr merge`.
#   4. `git push --all` / `git push --mirror` are now blocked unconditionally
#      (they reach every ref, protected branches included, regardless of the
#      branch currently checked out).
#
# ROUND 3 additions (each proven blocked here, not just asserted in prose):
#   1. Round 2's cgroup check read a path out of a plain, user-writable
#      config file ($guard_dir/_cgroup_path) that the installer wrote into
#      its own install directory -- any interactive session could overwrite
#      it to point at a fake cgroup and bypass the "kernel-verified" check
#      entirely. An early round-3 draft replaced that file with an
#      INTERACTIVE_GUARD_TEST_CGROUP_FILE environment-variable override --
#      the identical bug class in different clothing (a runtime signal an
#      ordinary shell can set that the production code path trusts) -- and
#      was caught and removed before landing. The shipped guard now hardcodes
#      /proc/self/cgroup with NO override of any kind: no config file, no
#      environment variable, nothing external the production code path reads.
#      Two scenarios below prove this: writing a fake worker cgroup into the
#      old $guard_dir/_cgroup_path file has zero effect, and setting
#      INTERACTIVE_GUARD_TEST_CGROUP_FILE (in case anyone reintroduces that
#      variable name by accident in a future edit) also has zero effect --
#      both run against the real, unmodified, shipped snippet.
#
#      Real /proc/self/cgroup can't be faked from userspace without root/
#      namespace privileges (unavailable in this sandbox), and its actual
#      content is environment-dependent -- e.g. this test, when it runs as
#      part of a dispatched task itself, sees ITS OWN real cgroup naming a
#      veridian-worker@*.service unit, the opposite of what a real
#      interactive login shell would see. So this test never relies on the
#      test runner's own ambient /proc/self/cgroup for any cgroup-sensitive
#      scenario. Instead, wherever INVOCATION_ID is set (the only case where
#      _interactive_guard_is_real_worker_context() ever reaches the cgroup
#      check at all -- it short-circuits on a missing INVOCATION_ID before
#      touching the cgroup), the test sources one of two throwaway,
#      disk-scratch COPIES of the real snippet's source text, each with the
#      single hardcoded `/proc/self/cgroup` line in
#      _interactive_guard_cgroup_path() replaced by a fixture file path --
#      $PATCHED_SNIPPET_MATCHING_WORKER for scenarios that must simulate a
#      genuine matching worker, $PATCHED_SNIPPET_NONWORKER for scenarios
#      that must simulate a genuine real (non-worker) interactive shell.
#      This is editing a copy of the guard's OWN SOURCE, exactly as
#      ai-os/OWNER_DIRECTIVES/interactive-session-guard.bashrc-snippet's
#      KNOWN LIMITATIONS section describes as the sanctioned seam. Neither
#      copy ever touches the real committed/deployed file, and the
#      production code path itself never reads any file or env var to make
#      this decision -- a real interactive shell can never reach this seam
#      because it only ever sources the genuine, unmodified, committed
#      snippet. Scenarios where INVOCATION_ID is unset don't need any of
#      this -- the cgroup check is never reached, so they safely run
#      against the real, unmodified $SNIPPET.
#   2. `git push origin +master` (force-push shorthand) is now blocked -- the
#      leading `+` force marker is stripped before comparing the destination
#      ref against the protected-branch pattern.
#   3. `git push origin feature-branch master` (a real, valid multi-refspec
#      single push) is now blocked because of `master` specifically, even
#      though it's the second refspec, not the first -- every positional
#      refspec is checked, not just the first one.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SNIPPET="${1:-$REPO_ROOT/ai-os/OWNER_DIRECTIVES/interactive-session-guard.bashrc-snippet}"
FAILURES=0

if [ ! -f "$SNIPPET" ]; then
  echo "FAIL: guard snippet not found at $SNIPPET"
  exit 1
fi

FIXTURE_ROOT="$(mktemp -d)"
trap 'rm -rf "$FIXTURE_ROOT"' EXIT

FAKE_BIN="$FIXTURE_ROOT/fake_bin"
mkdir -p "$FAKE_BIN"

cat > "$FAKE_BIN/gh" <<'EOF'
#!/bin/bash
echo "REAL_GH_CALLED $*" >> "$CALL_LOG"
exit 0
EOF

cat > "$FAKE_BIN/git" <<'EOF'
#!/bin/bash
if [ "$1" = "symbolic-ref" ] && [ "$2" = "--short" ] && [ "$3" = "HEAD" ]; then
  echo "${FAKE_CURRENT_BRANCH:-master}"
  exit 0
fi
echo "REAL_GIT_CALLED $*" >> "$CALL_LOG"
exit 0
EOF
chmod +x "$FAKE_BIN/gh" "$FAKE_BIN/git"

# A fake, non-matching cgroup -- what a real interactive SSH/login shell's
# own /proc/self/cgroup actually looks like (a login session scope, never a
# veridian-worker@/veridian-supervisor@ unit). Only used to populate the
# legacy attacker-controlled config-file location in the bypass-closed
# scenarios below -- the real /proc/self/cgroup (this sandbox's genuine,
# non-worker cgroup) is what the guard actually reads in every case here.
FAKE_NONWORKER_CGROUP="$FIXTURE_ROOT/cgroup.nonworker"
echo '0::/user.slice/user-1000.slice/session-3.scope' > "$FAKE_NONWORKER_CGROUP"

# A fake, matching cgroup -- what a real dispatched veridian-worker unit's
# /proc/self/cgroup looks like. Used both to simulate an attacker's
# old-config-file bypass attempt, and (via the source-patched snippet copy
# below) to simulate a genuine matching worker for positive-path scenarios.
FAKE_WORKER_CGROUP="$FIXTURE_ROOT/cgroup.worker"
echo '0::/system.slice/veridian-worker@task-example.service' > "$FAKE_WORKER_CGROUP"

# --- throwaway, disk-scratch copy of the real snippet, source-patched so its
# hardcoded /proc/self/cgroup read points at $FAKE_WORKER_CGROUP instead.
# This is the ONLY place this test ever edits the guard's logic, it never
# touches $SNIPPET itself, and it exists solely because a genuinely matching
# /proc/self/cgroup cannot be produced from userspace without root/namespace
# privileges. See the ROUND 3 note above and the snippet's own KNOWN
# LIMITATIONS section for why this is the sanctioned test-only seam.
PATCHED_SNIPPET_MATCHING_WORKER="$FIXTURE_ROOT/snippet.patched-matching-worker"
sed "s#printf '%s' /proc/self/cgroup#printf '%s' '$FAKE_WORKER_CGROUP'#" \
  "$SNIPPET" > "$PATCHED_SNIPPET_MATCHING_WORKER"
if ! grep -qF "printf '%s' '$FAKE_WORKER_CGROUP'" "$PATCHED_SNIPPET_MATCHING_WORKER"; then
  echo "FAIL: could not build the source-patched scratch snippet used for" \
    "positive-path ('passes through') scenarios -- the hardcoded" \
    "/proc/self/cgroup line in the real snippet may have changed; update" \
    "the sed pattern above to match."
  exit 1
fi

# Same mechanism, other direction: a throwaway copy simulating a genuine
# real (non-worker) interactive shell's own cgroup -- used for scenarios
# that spoof INVOCATION_ID and must still be BLOCKED because the (simulated)
# real cgroup does not name a veridian-worker/veridian-supervisor unit. Not
# used for any scenario where INVOCATION_ID is unset, since the guard never
# even reaches the cgroup check in that case.
PATCHED_SNIPPET_NONWORKER="$FIXTURE_ROOT/snippet.patched-nonworker"
sed "s#printf '%s' /proc/self/cgroup#printf '%s' '$FAKE_NONWORKER_CGROUP'#" \
  "$SNIPPET" > "$PATCHED_SNIPPET_NONWORKER"
if ! grep -qF "printf '%s' '$FAKE_NONWORKER_CGROUP'" "$PATCHED_SNIPPET_NONWORKER"; then
  echo "FAIL: could not build the source-patched scratch snippet used to" \
    "simulate a real non-worker interactive shell -- the hardcoded" \
    "/proc/self/cgroup line in the real snippet may have changed; update" \
    "the sed pattern above to match."
  exit 1
fi

# $1=label $2=INVOCATION_ID value ("" = unset) $3=command line to run
# $4=expected exit code $5=expect real binary called (0/1)
# $6=expected substring in stderr ("" = don't check) $7=FAKE_CURRENT_BRANCH ("" = unset)
# $8=fake cgroup file to write into the OLD, now-inert
#    "$guard_dir/_cgroup_path" location, simulating an attacker attempting
#    the round-2 config-file bypass ("" = don't attempt it)
# $9=fake cgroup file to set INTERACTIVE_GUARD_TEST_CGROUP_FILE to,
#    simulating an attacker attempting the (now removed) round-3-draft
#    env-var bypass ("" = don't attempt it)
# $10=alternate snippet path to source instead of the real $SNIPPET ("" =
#     use the real, unmodified, shipped snippet -- every scenario except the
#     source-patched positive-path ones must leave this unset)
run_case() {
  local label="$1" invocation="$2" cmdline="$3" expected_exit="$4" expect_called="$5" expect_stderr="$6" fake_branch="$7" legacy_attacker_cgroup="${8:-}" env_var_attack_cgroup="${9:-}" snippet_override="${10:-}"
  local call_log out_file err_file guard_dir snippet_to_source
  call_log="$(mktemp)"; out_file="$(mktemp)"; err_file="$(mktemp)"
  rm -f "$call_log"
  guard_dir="$(mktemp -d)"
  snippet_to_source="${snippet_override:-$SNIPPET}"

  local env_args=()
  if [ -z "$invocation" ]; then
    env_args+=(-u INVOCATION_ID)
  fi
  env_args+=(-u INTERACTIVE_GUARD_TEST_CGROUP_FILE)
  env_args+=(PATH="$FAKE_BIN:$PATH" CALL_LOG="$call_log" INTERACTIVE_GUARD_DIR="$guard_dir")
  if [ -n "$invocation" ]; then
    env_args+=(INVOCATION_ID="$invocation")
  fi
  if [ -n "$fake_branch" ]; then
    env_args+=(FAKE_CURRENT_BRANCH="$fake_branch")
  fi
  if [ -n "$env_var_attack_cgroup" ]; then
    env_args+=(INTERACTIVE_GUARD_TEST_CGROUP_FILE="$env_var_attack_cgroup")
  fi

  local legacy_attack=""
  if [ -n "$legacy_attacker_cgroup" ]; then
    legacy_attack="cat '$legacy_attacker_cgroup' > '$guard_dir/_cgroup_path';"
  fi

  env "${env_args[@]}" bash -c "source '$snippet_to_source' && $legacy_attack $cmdline" >"$out_file" 2>"$err_file"
  local actual_exit=$?

  local called=0
  [ -s "$call_log" ] && called=1

  local ok=1
  if [ "$actual_exit" != "$expected_exit" ]; then ok=0; fi
  if [ "$called" != "$expect_called" ]; then ok=0; fi
  if [ -n "$expect_stderr" ] && ! grep -qF "$expect_stderr" "$err_file"; then ok=0; fi

  if [ "$ok" = "1" ]; then
    echo "PASS: $label"
  else
    echo "FAIL: $label (exit=$actual_exit expected=$expected_exit, real_bin_called=$called expected=$expect_called)"
    echo "  --- stderr ---"; sed 's/^/  /' "$err_file"
    echo "  --- stdout ---"; sed 's/^/  /' "$out_file"
    FAILURES=$((FAILURES + 1))
  fi
  rm -rf "$call_log" "$out_file" "$err_file" "$guard_dir"
}

# Positive-path helper: sources the source-patched scratch snippet copy (see
# PATCHED_SNIPPET_MATCHING_WORKER above) so the guard's hardcoded cgroup read
# resolves to a genuine matching worker cgroup, simulating "both signals
# really present" without touching the real $SNIPPET or any runtime
# override. $1=label $2=INVOCATION_ID value $3=cmdline $4=fake_branch ("" =
# unset)
run_case_matching_worker() {
  local label="$1" invocation="$2" cmdline="$3" fake_branch="${4:-}"
  run_case "$label" "$invocation" "$cmdline" 0 1 "" "$fake_branch" "" "" "$PATCHED_SNIPPET_MATCHING_WORKER"
}

# --- gh pr merge ---
run_case "interactive shell: gh pr merge is BLOCKED, real gh never called" \
  "" "gh pr merge 1 --repo some/repo --merge" 1 0 \
  "BLOCKED: gh pr merge" ""

run_case_matching_worker "systemd-simulated (INVOCATION_ID + matching real-worker cgroup): gh pr merge passes through to real gh" \
  "test-unit-123" "gh pr merge 1 --repo some/repo --merge"

run_case_matching_worker "systemd-simulated: gh --version passes through (non-merge)" \
  "test-unit-123" "gh --version"

# --- gh read-only passthrough (must NEVER be blocked, interactive or not) ---
run_case "interactive shell: gh pr view passes through unaffected" \
  "" "gh pr view 1 --repo FChecklist/claude-control" 0 1 "" ""

run_case "interactive shell: gh pr list passes through unaffected" \
  "" "gh pr list --repo FChecklist/claude-control" 0 1 "" ""

run_case "interactive shell: gh pr comment passes through unaffected" \
  "" "gh pr comment 1 --repo some/repo --body hi" 0 1 "" ""

run_case "interactive shell: gh run rerun passes through unaffected" \
  "" "gh run rerun 123 --repo some/repo --failed" 0 1 "" ""

run_case "interactive shell: gh checks passes through unaffected" \
  "" "gh pr checks 1 --repo some/repo" 0 1 "" ""

run_case "interactive shell: gh api GET (non-merge) passes through unaffected" \
  "" "gh api repos/FChecklist/claude-control/pulls/1" 0 1 "" ""

# --- git push to protected branch ---
run_case "interactive shell: git push origin master is BLOCKED" \
  "" "git push origin master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" ""

run_case "interactive shell: git push origin main is BLOCKED" \
  "" "git push origin main" 1 0 \
  "BLOCKED: git push to protected branch/ref 'main'" ""

run_case "interactive shell: git push HEAD:master is BLOCKED (refspec colon form)" \
  "" "git push origin HEAD:master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" ""

run_case "interactive shell: bare 'git push' on protected current branch is BLOCKED" \
  "" "git push" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" "master"

run_case_matching_worker "systemd-simulated (INVOCATION_ID + matching real-worker cgroup): git push origin master passes through" \
  "test-unit-123" "git push origin master"

# --- git push to a non-protected branch: must never be blocked ---
run_case "interactive shell: git push to own feature/task branch passes through" \
  "" "git push origin worker/task-20260726-083833-build-interactive-session-write-gate--re" 0 1 "" ""

run_case "interactive shell: bare 'git push' on own feature branch passes through" \
  "" "git push" 0 1 "" "worker/some-task-branch"

# --- other git subcommands: must never be blocked ---
run_case "interactive shell: git status passes through unaffected" \
  "" "git status" 0 1 "" ""

run_case "interactive shell: git log passes through unaffected" \
  "" "git log -1" 0 1 "" ""

run_case "interactive shell: git diff passes through unaffected" \
  "" "git diff" 0 1 "" ""

# =========================================================================
# ROUND 2: bypass vector 1 -- spoofed INVOCATION_ID alone is not enough
# =========================================================================
run_case "BYPASS VECTOR 1: spoofed INVOCATION_ID with a real (non-worker) cgroup is still BLOCKED -- git push" \
  "fake123" "git push origin master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" "" "" "" "$PATCHED_SNIPPET_NONWORKER"

run_case "BYPASS VECTOR 1: spoofed INVOCATION_ID with a real (non-worker) cgroup is still BLOCKED -- gh pr merge" \
  "fake123" "gh pr merge 1 --repo some/repo --merge" 1 0 \
  "BLOCKED: gh pr merge" "" "" "" "$PATCHED_SNIPPET_NONWORKER"

run_case_matching_worker "sanity: spoofed INVOCATION_ID + a genuinely matching worker cgroup DOES pass through (both signals really present)" \
  "fake123" "git push origin master"

# =========================================================================
# ROUND 2: bypass vector 2 -- `command` prefix no longer skips the guard
# =========================================================================
run_case "BYPASS VECTOR 2: 'command git push origin master' is still BLOCKED (was a total bypass in round 1)" \
  "" "command git push origin master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" ""

run_case "BYPASS VECTOR 2: 'command gh pr merge' is still BLOCKED (was a total bypass in round 1)" \
  "" "command gh pr merge 1 --repo some/repo --merge" 1 0 \
  "BLOCKED: gh pr merge" ""

run_case "BYPASS VECTOR 2: 'command git status' (non-guarded subcommand) still passes through" \
  "" "command git status" 0 1 "" ""

# =========================================================================
# ROUND 2: bypass vector 3 -- gh api merge path is now detected
# =========================================================================
run_case "BYPASS VECTOR 3: 'gh api -X PUT .../pulls/N/merge' is BLOCKED" \
  "" "gh api -X PUT repos/FChecklist/claude-control/pulls/1/merge" 1 0 \
  "BLOCKED: gh pr merge" ""

run_case "BYPASS VECTOR 3: 'gh api --method PATCH .../pulls/N/merge' is BLOCKED" \
  "" "gh api --method PATCH repos/FChecklist/claude-control/pulls/1/merge" 1 0 \
  "BLOCKED: gh pr merge" ""

run_case "BYPASS VECTOR 3: 'gh api -XPUT .../pulls/N/merge' (attached flag form) is BLOCKED" \
  "" "gh api -XPUT repos/FChecklist/claude-control/pulls/1/merge" 1 0 \
  "BLOCKED: gh pr merge" ""

run_case "BYPASS VECTOR 3: 'gh api -X PUT' on a non-merge path still passes through" \
  "" "gh api -X PUT repos/FChecklist/claude-control/issues/1/labels" 0 1 "" ""

run_case_matching_worker "BYPASS VECTOR 3: systemd-simulated 'gh api -X PUT .../pulls/N/merge' passes through" \
  "test-unit-123" "gh api -X PUT repos/FChecklist/claude-control/pulls/1/merge"

# =========================================================================
# ROUND 2: bypass vector 4 -- git push --all / --mirror now blocked
# =========================================================================
run_case "BYPASS VECTOR 4: 'git push --all' is BLOCKED even from a non-protected current branch" \
  "" "git push --all" 1 0 \
  "BLOCKED: git push to protected branch/ref 'all refs" "worker/some-feature-branch"

run_case "BYPASS VECTOR 4: 'git push --mirror' is BLOCKED even from a non-protected current branch" \
  "" "git push --mirror" 1 0 \
  "BLOCKED: git push to protected branch/ref 'all refs" "worker/some-feature-branch"

run_case_matching_worker "BYPASS VECTOR 4: systemd-simulated 'git push --all' passes through" \
  "test-unit-123" "git push --all"

# =========================================================================
# ROUND 3: bypass vector 5 -- the round-2 config-file cgroup bypass is closed
# =========================================================================
# This reproduces the exact round-2 reviewer's live bypass sequence: spoof
# INVOCATION_ID, then write a fake worker cgroup into the
# "$guard_dir/_cgroup_path" file the round-2 installer used to read, while
# the guard's ACTUAL (simulated-real) cgroup signal is deterministically a
# genuine non-worker cgroup (via PATCHED_SNIPPET_NONWORKER -- see the note
# above on why this test never relies on this process's own ambient
# /proc/self/cgroup). Proves the old config file has zero effect: the push
# is still blocked even though the attacker successfully wrote a fake
# matching-worker cgroup into the exact path round 2 used to trust.
run_case "ROUND 3 BYPASS CLOSED: writing a fake worker cgroup into the old _cgroup_path config file no longer bypasses the guard -- git push" \
  "fake123" "git push origin master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" "" "$FAKE_WORKER_CGROUP" "" "$PATCHED_SNIPPET_NONWORKER"

run_case "ROUND 3 BYPASS CLOSED: writing a fake worker cgroup into the old _cgroup_path config file no longer bypasses the guard -- gh pr merge" \
  "fake123" "gh pr merge 1 --repo some/repo --merge" 1 0 \
  "BLOCKED: gh pr merge" "" "$FAKE_WORKER_CGROUP" "" "$PATCHED_SNIPPET_NONWORKER"

# This reproduces the (never-shipped, caught-before-landing) round-3-draft
# env-var bypass attempt: spoof INVOCATION_ID and set
# INTERACTIVE_GUARD_TEST_CGROUP_FILE to a fake matching worker cgroup, again
# against a deterministically real-non-worker simulated cgroup signal. The
# shipped _interactive_guard_cgroup_path() no longer reads this (or any)
# environment variable at all, so this proves the variable is completely
# inert against the actual shipped code, not merely undocumented.
run_case "BYPASS VECTOR 5b: setting INTERACTIVE_GUARD_TEST_CGROUP_FILE to a fake worker cgroup has ZERO effect on the real shipped guard -- git push" \
  "fake123" "git push origin master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" "" "" "$FAKE_WORKER_CGROUP" "$PATCHED_SNIPPET_NONWORKER"

run_case "BYPASS VECTOR 5b: setting INTERACTIVE_GUARD_TEST_CGROUP_FILE to a fake worker cgroup has ZERO effect on the real shipped guard -- gh pr merge" \
  "fake123" "gh pr merge 1 --repo some/repo --merge" 1 0 \
  "BLOCKED: gh pr merge" "" "" "$FAKE_WORKER_CGROUP" "$PATCHED_SNIPPET_NONWORKER"

run_case_matching_worker "sanity: a GENUINELY matching worker cgroup (via the source-patched scratch snippet, not any runtime override) DOES pass through" \
  "test-unit-123" "git push origin master"

# =========================================================================
# ROUND 3: bypass vector 6 -- leading '+' force-push marker now stripped
# =========================================================================
run_case "BYPASS VECTOR 6: 'git push origin +master' (force-push shorthand) is BLOCKED" \
  "" "git push origin +master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" ""

run_case "BYPASS VECTOR 6: 'git push origin +HEAD:master' (force-push colon refspec) is BLOCKED" \
  "" "git push origin +HEAD:master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" ""

run_case "BYPASS VECTOR 6: 'git push origin +feature-branch' (force-push, non-protected) still passes through" \
  "" "git push origin +feature-branch" 0 1 "" ""

run_case_matching_worker "BYPASS VECTOR 6: systemd-simulated 'git push origin +master' passes through" \
  "test-unit-123" "git push origin +master"

# =========================================================================
# ROUND 3: bypass vector 7 -- every positional refspec is now checked
# =========================================================================
run_case "BYPASS VECTOR 7: 'git push origin feature-branch master' (multi-refspec) is BLOCKED because of 'master' as the second refspec" \
  "" "git push origin feature-branch master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" ""

run_case "BYPASS VECTOR 7: 'git push origin master feature-branch' (multi-refspec, protected branch listed first) is BLOCKED" \
  "" "git push origin master feature-branch" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" ""

run_case "sanity: 'git push origin feature-branch other-feature' (multi-refspec, neither protected) passes through" \
  "" "git push origin feature-branch other-feature" 0 1 "" ""

run_case_matching_worker "BYPASS VECTOR 7: systemd-simulated 'git push origin feature-branch master' passes through" \
  "test-unit-123" "git push origin feature-branch master"

if [ "$FAILURES" -eq 0 ]; then
  echo "All scenarios passed."
  exit 0
else
  echo "$FAILURES scenario(s) failed."
  exit 1
fi
