#!/bin/bash
# Regression test for the interactive-session write gate (real incident
# 2026-07-26: an interactive session ran `gh pr merge 78 ...` and a direct
# `git push` retrigger commit to compliance-tracker's `main` by hand instead
# of going through the real dispatch pipeline). See
# ai-os/OWNER_DIRECTIVES/interactive-session-guard.bashrc-snippet (the real
# guard, sourced from rajat's ~/.bashrc on VERIDIAN-DEV) and
# ai-os/OWNER_DIRECTIVES/PROTOCOL_OWNER_AI.yaml.
#
# This test sources the REAL shipped snippet (not a re-implementation), so it
# fails the moment the shipped guard drifts from what this test verifies. It
# never touches the real `gh`/`git` binaries or real GitHub -- a fake bin/
# dir is placed first on PATH so `type -P gh`/`type -P git` (called at source
# time by the snippet) resolve to harmless fakes that log whether they were
# invoked.
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

# $1=label $2=INVOCATION_ID value ("" = unset) $3=command line to run
# $4=expected exit code $5=expect real binary called (0/1)
# $6=expected substring in stderr ("" = don't check) $7=FAKE_CURRENT_BRANCH ("" = unset)
run_case() {
  local label="$1" invocation="$2" cmdline="$3" expected_exit="$4" expect_called="$5" expect_stderr="$6" fake_branch="$7"
  local call_log out_file err_file
  call_log="$(mktemp)"; out_file="$(mktemp)"; err_file="$(mktemp)"
  rm -f "$call_log"

  local env_args=()
  if [ -z "$invocation" ]; then
    env_args+=(-u INVOCATION_ID)
  fi
  env_args+=(PATH="$FAKE_BIN:$PATH" CALL_LOG="$call_log")
  if [ -n "$invocation" ]; then
    env_args+=(INVOCATION_ID="$invocation")
  fi
  if [ -n "$fake_branch" ]; then
    env_args+=(FAKE_CURRENT_BRANCH="$fake_branch")
  fi

  env "${env_args[@]}" bash -c "source '$SNIPPET' && $cmdline" >"$out_file" 2>"$err_file"
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
  rm -f "$call_log" "$out_file" "$err_file"
}

# --- gh pr merge ---
run_case "interactive shell: gh pr merge is BLOCKED, real gh never called" \
  "" "gh pr merge 1 --repo some/repo --merge" 1 0 \
  "BLOCKED: gh pr merge must run through the dispatch pipeline" ""

run_case "systemd-simulated (INVOCATION_ID set): gh pr merge passes through to real gh" \
  "test-unit-123" "gh pr merge 1 --repo some/repo --merge" 0 1 "" ""

run_case "systemd-simulated: gh --version passes through (non-merge)" \
  "test-unit-123" "gh --version" 0 1 "" ""

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

# --- git push to protected branch ---
run_case "interactive shell: git push origin master is BLOCKED" \
  "" "git push origin master" 1 0 \
  "BLOCKED: git push to protected branch 'master'" ""

run_case "interactive shell: git push origin main is BLOCKED" \
  "" "git push origin main" 1 0 \
  "BLOCKED: git push to protected branch 'main'" ""

run_case "interactive shell: git push HEAD:master is BLOCKED (refspec colon form)" \
  "" "git push origin HEAD:master" 1 0 \
  "BLOCKED: git push to protected branch 'master'" ""

run_case "interactive shell: bare 'git push' on protected current branch is BLOCKED" \
  "" "git push" 1 0 \
  "BLOCKED: git push to protected branch 'master'" "master"

run_case "systemd-simulated: git push origin master passes through (real dispatched worker)" \
  "test-unit-123" "git push origin master" 0 1 "" ""

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

if [ "$FAILURES" -eq 0 ]; then
  echo "All scenarios passed."
  exit 0
else
  echo "$FAILURES scenario(s) failed."
  exit 1
fi
