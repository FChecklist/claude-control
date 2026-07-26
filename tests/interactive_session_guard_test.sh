#!/bin/bash
# Regression test for ai-os/OWNER_DIRECTIVES/interactive-session-guard.bashrc-snippet
# (the 4th real policy gate this session added -- see
# ai-os/POLICY_GATE_REGISTRY_2026-07-26.yaml). The snippet itself references this
# exact file path in its own header comment ("Verified directly ... in
# tests/interactive_session_guard_test.sh's 'command git' / 'command gh'
# scenarios") but it was never actually committed anywhere -- this closes that
# real gap with a genuine end-to-end test, not a re-implementation of the
# guard's own logic (it sources the real snippet and exercises the real
# generated wrapper scripts, same "extract the real block, don't re-implement
# it" discipline as tests/supervisor_merge_detection_test.sh).
#
# Does NOT touch the live ~/.bashrc, ~/.claude-interactive-session-guard.bashrc-snippet,
# or ~/.claude-interactive-session-guard.d/ -- everything below runs inside a
# throwaway TMPDIR with INTERACTIVE_GUARD_DIR and a fake cgroup file pointed at
# it via the snippet's own testing override, per its documented design.
set -uo pipefail

SNIPPET="${1:-ai-os/OWNER_DIRECTIVES/interactive-session-guard.bashrc-snippet}"
FAILURES=0

if [ ! -f "$SNIPPET" ]; then
  echo "FAIL: snippet not found at $SNIPPET"
  exit 1
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

# Fake "real" git/gh binaries this test controls, placed on PATH *after* the
# guard dir so the guard's own PATH-search-with-self-removed logic finds
# these, never itself -- same mechanism a real interactive shell uses to find
# the real /usr/bin/git.
FAKE_BIN="$WORKDIR/fakebin"
mkdir -p "$FAKE_BIN"
cat > "$FAKE_BIN/git" <<'EOF'
#!/bin/bash
if [ "$1" = "symbolic-ref" ]; then
  echo "${FAKE_CURRENT_BRANCH:-refs/heads/master}"
  exit 0
fi
echo "REAL_GIT_CALLED: $*"
exit 0
EOF
chmod +x "$FAKE_BIN/git"
cat > "$FAKE_BIN/gh" <<'EOF'
#!/bin/bash
echo "REAL_GH_CALLED: $*"
exit 0
EOF
chmod +x "$FAKE_BIN/gh"

run_scenario() {
  # $1=label $2=cmd(git|gh) $3.. = args (invocation_id/cgroup context set via env before calling)
  local label="$1"; shift
  local cmd="$1"; shift
  local out rc
  out="$("$GUARD_DIR/$cmd" "$@" 2>&1)"
  rc=$?
  printf '%s\n' "$out" > "$WORKDIR/last_output"
  echo "$rc" > "$WORKDIR/last_rc"
}

assert_blocked() {
  local label="$1"
  local rc out
  rc="$(cat "$WORKDIR/last_rc")"
  out="$(cat "$WORKDIR/last_output")"
  if [ "$rc" -eq 0 ] || ! printf '%s' "$out" | grep -q "BLOCKED"; then
    echo "FAIL ($label): expected BLOCKED/non-zero, got rc=$rc out=$out"
    FAILURES=$((FAILURES + 1))
  else
    echo "PASS ($label): blocked as expected"
  fi
}

assert_allowed() {
  local label="$1"
  local rc out
  rc="$(cat "$WORKDIR/last_rc")"
  out="$(cat "$WORKDIR/last_output")"
  if [ "$rc" -ne 0 ] || ! printf '%s' "$out" | grep -q "REAL_GIT_CALLED\|REAL_GH_CALLED"; then
    echo "FAIL ($label): expected the real binary to run, got rc=$rc out=$out"
    FAILURES=$((FAILURES + 1))
  else
    echo "PASS ($label): passed through to the real binary as expected"
  fi
}

# --- source the real snippet with an isolated guard dir --------------------
GUARD_DIR="$WORKDIR/guard.d"
export INTERACTIVE_GUARD_DIR="$GUARD_DIR"
unset INVOCATION_ID
export PATH="$FAKE_BIN:$PATH"
# shellcheck disable=SC1090
source "$SNIPPET"

if [ ! -x "$GUARD_DIR/git" ] || [ ! -x "$GUARD_DIR/gh" ]; then
  echo "FAIL: sourcing the snippet did not produce executable git/gh wrapper scripts in $GUARD_DIR"
  exit 1
fi
echo "PASS: sourcing the snippet produces git/gh wrapper scripts"

# --- scenario 1: interactive (no worker context), push to master: blocked --
FAKE_CURRENT_BRANCH="refs/heads/master" run_scenario "push-master-interactive" git push origin master
assert_blocked "git push origin master, no worker context"

# --- scenario 2: interactive, push to a feature branch: allowed ------------
run_scenario "push-feature-interactive" git push origin my-feature-branch
assert_allowed "git push origin my-feature-branch, no worker context"

# --- scenario 3: interactive, push --all: blocked (reaches every ref) ------
run_scenario "push-all-interactive" git push --all origin
assert_blocked "git push --all, no worker context"

# --- scenario 4: interactive, gh pr merge: blocked -------------------------
run_scenario "gh-merge-interactive" gh pr merge 123 --merge
assert_blocked "gh pr merge 123, no worker context"

# --- scenario 5: interactive, gh pr view (read-only): allowed --------------
run_scenario "gh-view-interactive" gh pr view 123
assert_allowed "gh pr view 123 (read-only, never gated)"

# --- scenario 6: gh api PUT .../pulls/N/merge: blocked ---------------------
run_scenario "gh-api-merge-interactive" gh api -X PUT repos/o/r/pulls/123/merge
assert_blocked "gh api -X PUT .../pulls/123/merge, no worker context"

# --- scenario 7: real dispatched worker context: push to master allowed ---
FAKE_CGROUP="$WORKDIR/fake_cgroup"
printf '0::/system.slice/veridian-worker@task-123.service\n' > "$FAKE_CGROUP"
printf '%s' "$FAKE_CGROUP" > "$GUARD_DIR/_cgroup_path"
export INVOCATION_ID="fake-systemd-invocation-id"
FAKE_CURRENT_BRANCH="refs/heads/master" run_scenario "push-master-worker-context" git push origin master
assert_allowed "git push origin master, real worker context (INVOCATION_ID + veridian-worker cgroup)"
unset INVOCATION_ID

# --- scenario 8: INVOCATION_ID alone (no matching cgroup) is NOT enough ----
printf '0::/user.slice/user-1000.slice/session-5.scope\n' > "$FAKE_CGROUP"
export INVOCATION_ID="spoofed-invocation-id"
FAKE_CURRENT_BRANCH="refs/heads/master" run_scenario "push-master-spoofed-invocation-id" git push origin master
assert_blocked "git push origin master, spoofed INVOCATION_ID but real cgroup is a login session, not a worker unit"
unset INVOCATION_ID

echo "---"
if [ "$FAILURES" -gt 0 ]; then
  echo "$FAILURES scenario(s) FAILED"
  exit 1
fi
echo "All scenarios passed"
