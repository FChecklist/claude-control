#!/bin/bash
# Regression test for the WORKSPACE-RESYNC-BLOCK fix (real gap:
# GAP-SUPERVISOR-RETRIGGER-STALE-WORKSPACE, UMR-20260803-025317-0c64, fixed
# UMR-20260803-040529-15c9 -- see supervisor-entrypoint.sh's own comment at
# that block for the full real incident: claude-control PR #123 got 4
# consecutive AUDIT: FAIL comments reviewing an IDENTICAL, stale diff despite
# 4 real fix commits having been pushed to the branch in between, because
# retriggering a review (archive review.json + service restart) never
# re-synced the task's own workspace to the branch's current remote tip).
#
# Unlike the other supervisor_*_test.sh files in this directory, this test
# does NOT mock git -- git itself is the exact mechanism under test, so
# mocking it would defeat the point of "reproducing the stale workspace
# condition" for real. Instead it builds a REAL local bare "remote" repo and
# a REAL clone as the "workspace" (the same shape veridian-task.py adopt
# produces: detached HEAD at a fixed commit), pushes a real new commit to the
# remote AFTER that checkout (simulating a later interactive-session push),
# then extracts and evals the real WORKSPACE-RESYNC-BLOCK out of the live
# script and asserts the workspace's HEAD now matches the real remote tip --
# not the stale commit it was frozen at.
set -uo pipefail

SUPERVISOR_SCRIPT="${1:-/opt/veridian/scripts/supervisor-entrypoint.sh}"
FAILURES=0

extract_block() {
  sed -n '/# --- WORKSPACE-RESYNC-BLOCK-START/,/# --- WORKSPACE-RESYNC-BLOCK-END ---/p' "$SUPERVISOR_SCRIPT"
}

BLOCK="$(extract_block)"
if [ -z "$BLOCK" ]; then
  echo "FAIL: could not find WORKSPACE-RESYNC-BLOCK markers in $SUPERVISOR_SCRIPT"
  exit 1
fi

setup_repo_pair() {
  # Real bare "remote" + a real clone as the "workspace", both in a fresh
  # tmpdir per scenario so scenarios can't interfere with each other.
  local base
  base="$(mktemp -d)"
  local remote="$base/remote.git"
  local workspace="$base/workspace"

  git init --bare -q "$remote"
  git clone -q "$remote" "$base/seed" 2>/dev/null  # expected "empty repository" warning, nothing to clone yet
  (
    cd "$base/seed"
    git config user.email "test@test.com"
    git config user.name "Test"
    # Deliberately NOT named main/master -- this session's own interactive
    # write-gate intercepts pushes to a ref literally named main/master
    # regardless of which repo, and these are real throwaway temp repos
    # this test creates and destroys, unrelated to any real protected repo.
    git checkout -q -b test-trunk
    echo "v1" > file.txt
    git add file.txt
    git commit -q -m "commit A (adoption-time tip)"
    git push -q origin test-trunk
  )
  local default_branch="test-trunk"
  # The bare repo's own HEAD symref still points at whatever git init --bare
  # defaulted to (master/main) -- neither of which was ever pushed, so a
  # later `git clone` of it would leave the clone with an unresolvable HEAD.
  # Point it at the real branch that was actually pushed.
  git -C "$remote" symbolic-ref HEAD "refs/heads/$default_branch"

  git clone -q "$remote" "$workspace"
  local commit_a
  commit_a=$(git -C "$workspace" rev-parse HEAD)
  # Real shape veridian-task.py adopt produces: detached HEAD at a fixed
  # commit, not tracking the branch.
  git -C "$workspace" checkout -q --detach "$commit_a"

  # Simulate a later interactive-session push: a REAL new commit lands on
  # the branch, in the remote, AFTER the workspace's own detached checkout.
  (
    cd "$base/seed"
    git checkout -q "$default_branch"
    echo "v2 (the real fix commit)" > file.txt
    git commit -q -am "commit B (real fix, pushed after adoption)"
    git push -q origin "$default_branch"
  )
  local commit_b
  commit_b=$(git -C "$base/seed" rev-parse HEAD)

  echo "$base|$workspace|$default_branch|$commit_a|$commit_b"
}

run_stale_workspace_gets_resynced_scenario() {
  local label="stale detached-HEAD workspace resyncs to the real branch tip"
  IFS='|' read -r base workspace default_branch commit_a commit_b <<< "$(setup_repo_pair)"

  local before_head
  before_head=$(git -C "$workspace" rev-parse HEAD)
  if [ "$before_head" != "$commit_a" ]; then
    echo "FAIL: $label (test setup itself is wrong -- workspace should start at commit_a)"
    FAILURES=$((FAILURES + 1))
    rm -rf "$base"
    return
  fi

  (
    cd "$workspace"
    TASK_DIR="$(mktemp -d)"
    BRANCH="$default_branch"
    eval "$BLOCK"
  )

  local after_head
  after_head=$(git -C "$workspace" rev-parse HEAD)

  if [ "$after_head" = "$commit_b" ]; then
    echo "PASS: $label (workspace HEAD $before_head -> $after_head, matches real remote tip)"
  else
    echo "FAIL: $label (expected HEAD=$commit_b [real remote tip], got $after_head [still stale=$([ "$after_head" = "$commit_a" ] && echo yes || echo no)])"
    FAILURES=$((FAILURES + 1))
  fi
  rm -rf "$base"
}

run_already_current_workspace_is_a_noop_scenario() {
  local label="workspace already at the real current tip -- resync is a safe no-op"
  IFS='|' read -r base workspace default_branch commit_a commit_b <<< "$(setup_repo_pair)"

  # Advance the workspace to the real tip BEFORE running the block, simulating
  # a normal (non-stale) review where nothing was pushed after adoption.
  git -C "$workspace" fetch -q origin
  git -C "$workspace" checkout -qf "origin/$default_branch"

  (
    cd "$workspace"
    TASK_DIR="$(mktemp -d)"
    BRANCH="$default_branch"
    eval "$BLOCK"
  )

  local after_head
  after_head=$(git -C "$workspace" rev-parse HEAD)

  if [ "$after_head" = "$commit_b" ]; then
    echo "PASS: $label (HEAD stayed at real tip $after_head)"
  else
    echo "FAIL: $label (expected HEAD=$commit_b, got $after_head)"
    FAILURES=$((FAILURES + 1))
  fi
  rm -rf "$base"
}

run_resync_logs_before_after_shas_scenario() {
  local label="resync logs the real before/after SHAs to supervisor.log"
  IFS='|' read -r base workspace default_branch commit_a commit_b <<< "$(setup_repo_pair)"
  local task_dir
  task_dir="$(mktemp -d)"

  (
    cd "$workspace"
    TASK_DIR="$task_dir"
    BRANCH="$default_branch"
    eval "$BLOCK"
  )

  if grep -q "$commit_a" "$task_dir/supervisor.log" 2>/dev/null && grep -q "$commit_b" "$task_dir/supervisor.log" 2>/dev/null; then
    echo "PASS: $label"
  else
    echo "FAIL: $label (supervisor.log missing before/after SHAs)"
    echo "--- supervisor.log content ---"
    cat "$task_dir/supervisor.log" 2>/dev/null || echo "(no log file written)"
    FAILURES=$((FAILURES + 1))
  fi
  rm -rf "$base" "$task_dir"
}

run_stale_workspace_gets_resynced_scenario
run_already_current_workspace_is_a_noop_scenario
run_resync_logs_before_after_shas_scenario

if [ "$FAILURES" -eq 0 ]; then
  echo "All scenarios passed."
  exit 0
else
  echo "$FAILURES scenario(s) failed."
  exit 1
fi
