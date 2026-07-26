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
#      a second, kernel-tracked cgroup signal is now required too. Real
#      /proc/self/cgroup can't be fabricated from userspace without root/
#      namespace privileges (verified unavailable in this sandbox), so this
#      test drives the guard's cgroup check through the small
#      "$guard_dir/_cgroup_path" config file the installer itself writes
#      (reset to the real /proc/self/cgroup path every time the snippet is
#      sourced) -- exactly the seam the snippet documents as being for this
#      purpose, not a generic env-var override.
#   2. `command git ...` / `command gh ...` no longer bypasses the guard --
#      the guard is now PATH-resolved wrapper scripts, not shell functions,
#      so `command` (which only skips functions/aliases, never PATH search)
#      still finds them.
#   3. `gh api -X PUT|PATCH .../pulls/<n>/merge` is now detected as a merge,
#      same as `gh pr merge`.
#   4. `git push --all` / `git push --mirror` are now blocked unconditionally
#      (they reach every ref, protected branches included, regardless of the
#      branch currently checked out).
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
# veridian-worker@/veridian-supervisor@ unit).
FAKE_NONWORKER_CGROUP="$FIXTURE_ROOT/cgroup.nonworker"
echo '0::/user.slice/user-1000.slice/session-3.scope' > "$FAKE_NONWORKER_CGROUP"

# A fake, matching cgroup -- what a real dispatched veridian-worker unit's
# /proc/self/cgroup looks like.
FAKE_WORKER_CGROUP="$FIXTURE_ROOT/cgroup.worker"
echo '0::/system.slice/veridian-worker@task-example.service' > "$FAKE_WORKER_CGROUP"

# $1=label $2=INVOCATION_ID value ("" = unset) $3=command line to run
# $4=expected exit code $5=expect real binary called (0/1)
# $6=expected substring in stderr ("" = don't check) $7=FAKE_CURRENT_BRANCH ("" = unset)
# $8=fake cgroup file to point the guard's check at ("" = leave the
#    installer's real-/proc/self/cgroup default in place)
run_case() {
  local label="$1" invocation="$2" cmdline="$3" expected_exit="$4" expect_called="$5" expect_stderr="$6" fake_branch="$7" fake_cgroup="${8:-}"
  local call_log out_file err_file guard_dir
  call_log="$(mktemp)"; out_file="$(mktemp)"; err_file="$(mktemp)"
  rm -f "$call_log"
  guard_dir="$(mktemp -d)"

  local env_args=()
  if [ -z "$invocation" ]; then
    env_args+=(-u INVOCATION_ID)
  fi
  env_args+=(PATH="$FAKE_BIN:$PATH" CALL_LOG="$call_log" INTERACTIVE_GUARD_DIR="$guard_dir")
  if [ -n "$invocation" ]; then
    env_args+=(INVOCATION_ID="$invocation")
  fi
  if [ -n "$fake_branch" ]; then
    env_args+=(FAKE_CURRENT_BRANCH="$fake_branch")
  fi

  local cgroup_override=""
  if [ -n "$fake_cgroup" ]; then
    cgroup_override="echo '$fake_cgroup' > '$guard_dir/_cgroup_path';"
  fi

  env "${env_args[@]}" bash -c "source '$SNIPPET' && $cgroup_override $cmdline" >"$out_file" 2>"$err_file"
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

# --- gh pr merge ---
run_case "interactive shell: gh pr merge is BLOCKED, real gh never called" \
  "" "gh pr merge 1 --repo some/repo --merge" 1 0 \
  "BLOCKED: gh pr merge" "" ""

run_case "systemd-simulated (INVOCATION_ID + matching real-worker cgroup): gh pr merge passes through to real gh" \
  "test-unit-123" "gh pr merge 1 --repo some/repo --merge" 0 1 "" "" "$FAKE_WORKER_CGROUP"

run_case "systemd-simulated: gh --version passes through (non-merge)" \
  "test-unit-123" "gh --version" 0 1 "" "" "$FAKE_WORKER_CGROUP"

# --- gh read-only passthrough (must NEVER be blocked, interactive or not) ---
run_case "interactive shell: gh pr view passes through unaffected" \
  "" "gh pr view 1 --repo FChecklist/claude-control" 0 1 "" "" ""

run_case "interactive shell: gh pr list passes through unaffected" \
  "" "gh pr list --repo FChecklist/claude-control" 0 1 "" "" ""

run_case "interactive shell: gh pr comment passes through unaffected" \
  "" "gh pr comment 1 --repo some/repo --body hi" 0 1 "" "" ""

run_case "interactive shell: gh run rerun passes through unaffected" \
  "" "gh run rerun 123 --repo some/repo --failed" 0 1 "" "" ""

run_case "interactive shell: gh checks passes through unaffected" \
  "" "gh pr checks 1 --repo some/repo" 0 1 "" "" ""

run_case "interactive shell: gh api GET (non-merge) passes through unaffected" \
  "" "gh api repos/FChecklist/claude-control/pulls/1" 0 1 "" "" ""

# --- git push to protected branch ---
run_case "interactive shell: git push origin master is BLOCKED" \
  "" "git push origin master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" "" ""

run_case "interactive shell: git push origin main is BLOCKED" \
  "" "git push origin main" 1 0 \
  "BLOCKED: git push to protected branch/ref 'main'" "" ""

run_case "interactive shell: git push HEAD:master is BLOCKED (refspec colon form)" \
  "" "git push origin HEAD:master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" "" ""

run_case "interactive shell: bare 'git push' on protected current branch is BLOCKED" \
  "" "git push" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" "master" ""

run_case "systemd-simulated (INVOCATION_ID + matching real-worker cgroup): git push origin master passes through" \
  "test-unit-123" "git push origin master" 0 1 "" "" "$FAKE_WORKER_CGROUP"

# --- git push to a non-protected branch: must never be blocked ---
run_case "interactive shell: git push to own feature/task branch passes through" \
  "" "git push origin worker/task-20260726-083833-build-interactive-session-write-gate--re" 0 1 "" "" ""

run_case "interactive shell: bare 'git push' on own feature branch passes through" \
  "" "git push" 0 1 "" "worker/some-task-branch" ""

# --- other git subcommands: must never be blocked ---
run_case "interactive shell: git status passes through unaffected" \
  "" "git status" 0 1 "" "" ""

run_case "interactive shell: git log passes through unaffected" \
  "" "git log -1" 0 1 "" "" ""

run_case "interactive shell: git diff passes through unaffected" \
  "" "git diff" 0 1 "" "" ""

# =========================================================================
# ROUND 2: bypass vector 1 -- spoofed INVOCATION_ID alone is not enough
# =========================================================================
run_case "BYPASS VECTOR 1: spoofed INVOCATION_ID with a real (non-worker) cgroup is still BLOCKED -- git push" \
  "fake123" "git push origin master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" "" "$FAKE_NONWORKER_CGROUP"

run_case "BYPASS VECTOR 1: spoofed INVOCATION_ID with a real (non-worker) cgroup is still BLOCKED -- gh pr merge" \
  "fake123" "gh pr merge 1 --repo some/repo --merge" 1 0 \
  "BLOCKED: gh pr merge" "" "$FAKE_NONWORKER_CGROUP"

run_case "sanity: spoofed INVOCATION_ID + a genuinely matching worker cgroup DOES pass through (both signals really present)" \
  "fake123" "git push origin master" 0 1 "" "" "$FAKE_WORKER_CGROUP"

# =========================================================================
# ROUND 2: bypass vector 2 -- `command` prefix no longer skips the guard
# =========================================================================
run_case "BYPASS VECTOR 2: 'command git push origin master' is still BLOCKED (was a total bypass in round 1)" \
  "" "command git push origin master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" "" ""

run_case "BYPASS VECTOR 2: 'command gh pr merge' is still BLOCKED (was a total bypass in round 1)" \
  "" "command gh pr merge 1 --repo some/repo --merge" 1 0 \
  "BLOCKED: gh pr merge" "" ""

run_case "BYPASS VECTOR 2: 'command git status' (non-guarded subcommand) still passes through" \
  "" "command git status" 0 1 "" "" ""

# =========================================================================
# ROUND 2: bypass vector 3 -- gh api merge path is now detected
# =========================================================================
run_case "BYPASS VECTOR 3: 'gh api -X PUT .../pulls/N/merge' is BLOCKED" \
  "" "gh api -X PUT repos/FChecklist/claude-control/pulls/1/merge" 1 0 \
  "BLOCKED: gh pr merge" "" ""

run_case "BYPASS VECTOR 3: 'gh api --method PATCH .../pulls/N/merge' is BLOCKED" \
  "" "gh api --method PATCH repos/FChecklist/claude-control/pulls/1/merge" 1 0 \
  "BLOCKED: gh pr merge" "" ""

run_case "BYPASS VECTOR 3: 'gh api -XPUT .../pulls/N/merge' (attached flag form) is BLOCKED" \
  "" "gh api -XPUT repos/FChecklist/claude-control/pulls/1/merge" 1 0 \
  "BLOCKED: gh pr merge" "" ""

run_case "BYPASS VECTOR 3: 'gh api -X PUT' on a non-merge path still passes through" \
  "" "gh api -X PUT repos/FChecklist/claude-control/issues/1/labels" 0 1 "" "" ""

run_case "BYPASS VECTOR 3: systemd-simulated 'gh api -X PUT .../pulls/N/merge' passes through" \
  "test-unit-123" "gh api -X PUT repos/FChecklist/claude-control/pulls/1/merge" 0 1 "" "" "$FAKE_WORKER_CGROUP"

# =========================================================================
# ROUND 2: bypass vector 4 -- git push --all / --mirror now blocked
# =========================================================================
run_case "BYPASS VECTOR 4: 'git push --all' is BLOCKED even from a non-protected current branch" \
  "" "git push --all" 1 0 \
  "BLOCKED: git push to protected branch/ref 'all refs" "worker/some-feature-branch" ""

run_case "BYPASS VECTOR 4: 'git push --mirror' is BLOCKED even from a non-protected current branch" \
  "" "git push --mirror" 1 0 \
  "BLOCKED: git push to protected branch/ref 'all refs" "worker/some-feature-branch" ""

run_case "BYPASS VECTOR 4: systemd-simulated 'git push --all' passes through" \
  "test-unit-123" "git push --all" 0 1 "" "" "$FAKE_WORKER_CGROUP"

if [ "$FAILURES" -eq 0 ]; then
  echo "All scenarios passed."
  exit 0
else
  echo "$FAILURES scenario(s) failed."
  exit 1
fi
