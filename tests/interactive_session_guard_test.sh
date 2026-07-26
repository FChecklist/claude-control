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
#
# ROUND 4 additions (each proven blocked here, not just asserted in prose):
#   1. Both wrapper scripts used to detect the guarded subcommand by
#      checking ONLY argv[1] literally, so any real global flag before the
#      subcommand (`git -C /tmp push ...`, `git --git-dir=/tmp/.git push
#      ...`, `gh --repo some/repo pr merge ...`) walked straight past
#      detection undetected -- reproduced live, not an adversarial trick.
#      Closed by scanning the full argv and skipping every real global flag
#      documented for the installed git/gh version before looking for the
#      subcommand. Scenarios below cover git's `-C`/`--git-dir=` and gh's
#      `--repo`/`-R` in all its real forms (`--repo value`, `--repo=value`,
#      `-R value`, `-Rvalue` attached), for both the blocked and
#      passes-through cases, and in the systemd-simulated context too (to
#      prove the fix doesn't accidentally start blocking a REAL worker that
#      happens to use a global flag).
#   2. A lower-confidence structural question was investigated live: can an
#      ordinary interactive process run `systemd-run --user
#      --unit=veridian-worker@<fake>.service --scope <command>` to obtain a
#      genuinely kernel-tracked cgroup (and a genuine INVOCATION_ID) that
#      would satisfy round 3's cgroup check without being a real dispatched
#      worker? Live testing on VERIDIAN-DEV found this SPECIFIC attempt is
#      currently rejected by systemd itself (name collision with the real
#      installed veridian-worker@.service/veridian-supervisor@.service
#      template unit files) -- but that is a deployment-specific side
#      effect, not proof the underlying premise is sound in general, and is
#      NOT relied upon as the fix (see the snippet's own KNOWN LIMITATIONS
#      for why). The actual fix, added regardless: the task_id parsed from
#      a matching cgroup unit name must correspond to a REAL, currently
#      in_progress task -- <tasks_dir>/<task_id>/task.yaml must exist with
#      `status: in_progress`. This is testable and IS tested here: a
#      pattern-matching-but-forged cgroup naming a task_id with no
#      corresponding fixture task directory must still be BLOCKED even with
#      a real-looking INVOCATION_ID present, simulating what a successful
#      `systemd-run` impersonation attempt (of the kind investigated above)
#      would actually look like from the guard's point of view. This test
#      does not itself invoke real `systemd-run` (it would mutate real
#      systemd unit state, which an automated regression suite must not
#      do) -- see the interactive-session-guard.bashrc-snippet's ROUND 4
#      section for how the live systemd-run collision test was actually run
#      and what it did and did not prove.
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
# [ROUND 5] `gh alias list` is the guard's own real-alias-resolution lookup
# (see _interactive_guard_gh_resolve_persistent_alias() in _lib.sh) -- an
# informational query, not itself a merge, so like the git fake's
# symbolic-ref handling below it must NOT be logged to CALL_LOG (which means
# "the actual guarded action reached the real binary"), or every BLOCKED
# alias-bypass scenario would wrongly show real_bin_called=1 just because
# the guard asked what the aliases are. $FAKE_GH_ALIASES ("" = none) holds
# the fixture `gh alias list` output for the scenario, one "name: expansion"
# line per alias, exactly the real live-confirmed gh 2.45 format.
if [ "${1:-}" = "alias" ] && [ "${2:-}" = "list" ]; then
  if [ -n "${FAKE_GH_ALIASES:-}" ]; then
    printf '%s\n' "$FAKE_GH_ALIASES"
  fi
  exit 0
fi
echo "REAL_GH_CALLED $*" >> "$CALL_LOG"
exit 0
EOF

cat > "$FAKE_BIN/git" <<'EOF'
#!/bin/bash
# Tolerates an optional leading "-C <path>" prefix before the symbolic-ref
# check, so ROUND 4 scenarios can prove the guard forwards a skipped global
# flag (like -C) through to its internal current-branch lookup, not just to
# the final passthrough exec.
args=("$@")
if [ "${args[0]:-}" = "-C" ]; then
  args=("${args[@]:2}")
fi
if [ "${args[0]:-}" = "symbolic-ref" ] && [ "${args[1]:-}" = "--short" ] && [ "${args[2]:-}" = "HEAD" ]; then
  echo "${FAKE_CURRENT_BRANCH:-master}"
  exit 0
fi
# [ROUND 5] `git config --get-regexp ^alias\.` is the guard's own real
# persistent-alias-resolution lookup (see
# _interactive_guard_git_resolve_persistent_alias() in _lib.sh) --
# informational, not itself a push, so (like symbolic-ref above) it must NOT
# be logged to CALL_LOG. $FAKE_GIT_ALIASES ("" = none configured, real git's
# own exit-1-with-no-output behavior when no alias.* config exists) holds
# the fixture `alias.<name> <value>` lines for the scenario, exactly the
# real live-confirmed git 2.43 `--get-regexp` output format.
if [ "${args[0]:-}" = "config" ] && [ "${args[1]:-}" = "--get-regexp" ]; then
  if [ -n "${FAKE_GIT_ALIASES:-}" ]; then
    printf '%s\n' "$FAKE_GIT_ALIASES"
    exit 0
  fi
  exit 1
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

# [ROUND 4] A fake, matching cgroup whose task_id ("fake-test", chosen to
# mirror the exact `systemd-run --user
# --unit=veridian-worker@fake-test.service` example from the round-4 audit)
# has NO corresponding entry in $FIXTURE_TASKS_DIR below -- this is what a
# successful systemd-run impersonation attempt would look like from the
# guard's point of view: a genuinely pattern-matching cgroup with nothing
# real behind it.
FAKE_WORKER_CGROUP_FORGED="$FIXTURE_ROOT/cgroup.worker-forged"
echo '0::/system.slice/veridian-worker@fake-test.service' > "$FAKE_WORKER_CGROUP_FORGED"

# [ROUND 4] Same shape, but the task_id DOES have a fixture task directory,
# just not with status in_progress -- proves the cross-reference checks the
# status, not merely the directory's existence.
FAKE_WORKER_CGROUP_WRONG_STATUS="$FIXTURE_ROOT/cgroup.worker-wrong-status"
echo '0::/system.slice/veridian-worker@task-done-example.service' > "$FAKE_WORKER_CGROUP_WRONG_STATUS"

# [ROUND 4] Fixture "tasks directory" standing in for the real, hardcoded
# /opt/veridian/ai-os/tasks the shipped guard's _interactive_guard_tasks_dir()
# reads -- built the same sanctioned way as the cgroup fixtures above (a
# source-patched scratch copy, never a runtime override the production code
# reads; see _interactive_guard_tasks_dir()'s own comment in the snippet for
# why it has none). Contains exactly two entries: "task-example" (matches
# $FAKE_WORKER_CGROUP above, real and in_progress -- the positive-path case)
# and "task-done-example" (matches $FAKE_WORKER_CGROUP_WRONG_STATUS, real
# but completed, not in_progress). "fake-test"
# ($FAKE_WORKER_CGROUP_FORGED's task_id) deliberately has no entry at all.
FIXTURE_TASKS_DIR="$FIXTURE_ROOT/tasks_dir"
mkdir -p "$FIXTURE_TASKS_DIR/task-example" "$FIXTURE_TASKS_DIR/task-done-example"
printf 'id: task-example\nstatus: in_progress\n' > "$FIXTURE_TASKS_DIR/task-example/task.yaml"
printf 'id: task-done-example\nstatus: completed\n' > "$FIXTURE_TASKS_DIR/task-done-example/task.yaml"

# --- throwaway, disk-scratch copy of the real snippet, source-patched so its
# hardcoded /proc/self/cgroup AND tasks-dir reads point at fixture paths
# instead. This is the ONLY place this test ever edits the guard's logic, it
# never touches $SNIPPET itself, and it exists solely because a genuinely
# matching /proc/self/cgroup cannot be produced from userspace without root/
# namespace privileges, and because the real, hardcoded tasks dir
# (/opt/veridian/ai-os/tasks) is real production data this test must not
# depend on. See the ROUND 3/4 notes above and the snippet's own KNOWN
# LIMITATIONS section for why this is the sanctioned test-only seam.
# $1=cgroup fixture file $2=output path
_build_patched_snippet() {
  local cgroup_fixture="$1" out="$2"
  sed -e "s#printf '%s' /proc/self/cgroup#printf '%s' '$cgroup_fixture'#" \
      -e "s#printf '%s' /opt/veridian/ai-os/tasks#printf '%s' '$FIXTURE_TASKS_DIR'#" \
      "$SNIPPET" > "$out"
  if ! grep -qF "printf '%s' '$cgroup_fixture'" "$out"; then
    echo "FAIL: could not build the source-patched scratch snippet -- the" \
      "hardcoded /proc/self/cgroup line in the real snippet may have" \
      "changed; update the sed pattern above to match."
    exit 1
  fi
  if ! grep -qF "printf '%s' '$FIXTURE_TASKS_DIR'" "$out"; then
    echo "FAIL: could not build the source-patched scratch snippet -- the" \
      "hardcoded /opt/veridian/ai-os/tasks line in the real snippet may" \
      "have changed; update the sed pattern above to match."
    exit 1
  fi
}

PATCHED_SNIPPET_MATCHING_WORKER="$FIXTURE_ROOT/snippet.patched-matching-worker"
_build_patched_snippet "$FAKE_WORKER_CGROUP" "$PATCHED_SNIPPET_MATCHING_WORKER"

# [ROUND 4] simulates a successful systemd-run-style impersonation attempt:
# cgroup name matches the worker pattern, but no real task backs it.
PATCHED_SNIPPET_FORGED_WORKER="$FIXTURE_ROOT/snippet.patched-forged-worker"
_build_patched_snippet "$FAKE_WORKER_CGROUP_FORGED" "$PATCHED_SNIPPET_FORGED_WORKER"

# [ROUND 4] cgroup name matches a REAL task directory, but that task is not
# in_progress.
PATCHED_SNIPPET_WRONG_STATUS="$FIXTURE_ROOT/snippet.patched-wrong-status"
_build_patched_snippet "$FAKE_WORKER_CGROUP_WRONG_STATUS" "$PATCHED_SNIPPET_WRONG_STATUS"

# Same mechanism, other direction: a throwaway copy simulating a genuine
# real (non-worker) interactive shell's own cgroup -- used for scenarios
# that spoof INVOCATION_ID and must still be BLOCKED because the (simulated)
# real cgroup does not name a veridian-worker/veridian-supervisor unit. Not
# used for any scenario where INVOCATION_ID is unset, since the guard never
# even reaches the cgroup check in that case. The cgroup regex never matches
# here, so the tasks-dir cross-reference is never reached either -- no need
# for a fixture task entry, but the tasks-dir line is still patched for
# consistency with the other scratch copies (it is simply unused).
PATCHED_SNIPPET_NONWORKER="$FIXTURE_ROOT/snippet.patched-nonworker"
_build_patched_snippet "$FAKE_NONWORKER_CGROUP" "$PATCHED_SNIPPET_NONWORKER"

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
# $11=[ROUND 5] fixture `git config --get-regexp ^alias\.` output for the
#     fake "real" git to return (one "alias.<name> <value>" line per alias,
#     "" = none configured) -- simulates a persistent ~/.gitconfig [alias]
#     entry for _interactive_guard_git_resolve_persistent_alias() to resolve
# $12=[ROUND 5] fixture `gh alias list` output for the fake "real" gh to
#     return (one "<name>: <expansion>" line per alias, "" = none
#     configured) -- simulates a persistent `gh alias set` entry for
#     _interactive_guard_gh_resolve_persistent_alias() to resolve
run_case() {
  local label="$1" invocation="$2" cmdline="$3" expected_exit="$4" expect_called="$5" expect_stderr="$6" fake_branch="$7" legacy_attacker_cgroup="${8:-}" env_var_attack_cgroup="${9:-}" snippet_override="${10:-}" fake_git_aliases="${11:-}" fake_gh_aliases="${12:-}"
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
  if [ -n "$fake_git_aliases" ]; then
    env_args+=(FAKE_GIT_ALIASES="$fake_git_aliases")
  fi
  if [ -n "$fake_gh_aliases" ]; then
    env_args+=(FAKE_GH_ALIASES="$fake_gh_aliases")
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
# unset). $5=[ROUND 5] fixture git alias config ("" = none) $6=[ROUND 5]
# fixture gh alias list output ("" = none)
run_case_matching_worker() {
  local label="$1" invocation="$2" cmdline="$3" fake_branch="${4:-}" fake_git_aliases="${5:-}" fake_gh_aliases="${6:-}"
  run_case "$label" "$invocation" "$cmdline" 0 1 "" "$fake_branch" "" "" "$PATCHED_SNIPPET_MATCHING_WORKER" "$fake_git_aliases" "$fake_gh_aliases"
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

# =========================================================================
# ROUND 4: bypass vector 8 -- argv-position bypass via a global flag before
# the subcommand is now closed (git -C / --git-dir=, gh --repo / -R)
# =========================================================================
run_case "BYPASS VECTOR 8: 'git -C /tmp push origin master' is BLOCKED (was a total bypass pre-round-4)" \
  "" "git -C /tmp push origin master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" ""

run_case "BYPASS VECTOR 8: 'git --git-dir=/tmp/.git push origin master' is BLOCKED (was a total bypass pre-round-4)" \
  "" "git --git-dir=/tmp/.git push origin master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" ""

run_case "BYPASS VECTOR 8: 'git --git-dir /tmp/.git push origin master' (space form) is BLOCKED" \
  "" "git --git-dir /tmp/.git push origin master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" ""

run_case "BYPASS VECTOR 8: 'gh --repo some/repo pr merge 1 --merge' is BLOCKED (was a total bypass pre-round-4)" \
  "" "gh --repo some/repo pr merge 1 --merge" 1 0 \
  "BLOCKED: gh pr merge" ""

run_case "BYPASS VECTOR 8: 'gh --repo=some/repo pr merge 1 --merge' (= form) is BLOCKED" \
  "" "gh --repo=some/repo pr merge 1 --merge" 1 0 \
  "BLOCKED: gh pr merge" ""

run_case "BYPASS VECTOR 8: 'gh -R some/repo pr merge 1 --merge' (short-flag space form) is BLOCKED" \
  "" "gh -R some/repo pr merge 1 --merge" 1 0 \
  "BLOCKED: gh pr merge" ""

run_case "BYPASS VECTOR 8: 'gh -Rsome/repo pr merge 1 --merge' (short-flag attached form) is BLOCKED" \
  "" "gh -Rsome/repo pr merge 1 --merge" 1 0 \
  "BLOCKED: gh pr merge" ""

run_case "BYPASS VECTOR 8: 'gh --repo some/repo api -X PUT repos/x/y/pulls/1/merge' is BLOCKED" \
  "" "gh --repo some/repo api -X PUT repos/x/y/pulls/1/merge" 1 0 \
  "BLOCKED: gh pr merge" ""

# sanity: a global flag before a NON-guarded subcommand must still pass
# through unaffected -- proves the fix only changes subcommand DETECTION,
# not which subcommands are guarded.
run_case "BYPASS VECTOR 8 sanity: 'git -C /tmp status' (global flag, non-guarded subcommand) passes through" \
  "" "git -C /tmp status" 0 1 "" ""

run_case "BYPASS VECTOR 8 sanity: 'gh --repo some/repo pr view 1' (global flag, non-guarded subcommand) passes through" \
  "" "gh --repo some/repo pr view 1" 0 1 "" ""

run_case "BYPASS VECTOR 8 sanity: 'git -C /tmp push origin feature-branch' (global flag, non-protected branch) passes through" \
  "" "git -C /tmp push origin feature-branch" 0 1 "" ""

# proves the global-flag prefix is forwarded to the guard's own internal
# current-branch resolution too (bare `git push`, no explicit refspec), not
# just used for detection -- see _interactive_guard_git_push_verdict()'s
# ROUND 4 comment and the fake $FAKE_BIN/git's tolerance for a leading -C.
run_case "BYPASS VECTOR 8: bare 'git -C /tmp push' on protected current branch is BLOCKED (global-flag-aware branch resolution)" \
  "" "git -C /tmp push" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" "master"

run_case "BYPASS VECTOR 8 sanity: bare 'git -C /tmp push' on own feature branch passes through" \
  "" "git -C /tmp push" 0 1 "" "worker/some-task-branch"

run_case_matching_worker "BYPASS VECTOR 8: systemd-simulated 'git -C /tmp push origin master' passes through" \
  "test-unit-123" "git -C /tmp push origin master"

run_case_matching_worker "BYPASS VECTOR 8: systemd-simulated 'gh --repo some/repo pr merge 1 --merge' passes through" \
  "test-unit-123" "gh --repo some/repo pr merge 1 --merge"

# =========================================================================
# ROUND 4: bypass vector 9 -- cgroup-name-pattern match alone is no longer
# trusted; it must cross-reference a REAL, in_progress task (closes the
# systemd-run impersonation concern regardless of how a matching-but-fake
# cgroup name might be produced -- see the ROUND 4 section in
# interactive-session-guard.bashrc-snippet for what was and was not proven
# live about the specific `systemd-run --user
# --unit=veridian-worker@<fake>.service` attempt).
# =========================================================================
run_case "BYPASS VECTOR 9: a cgroup naming a pattern-matching but NON-EXISTENT task (simulating a systemd-run-forged unit) is still BLOCKED -- git push" \
  "real-looking-invocation-id" "git push origin master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" "" "" "" "$PATCHED_SNIPPET_FORGED_WORKER"

run_case "BYPASS VECTOR 9: a cgroup naming a pattern-matching but NON-EXISTENT task (simulating a systemd-run-forged unit) is still BLOCKED -- gh pr merge" \
  "real-looking-invocation-id" "gh pr merge 1 --repo some/repo --merge" 1 0 \
  "BLOCKED: gh pr merge" "" "" "" "$PATCHED_SNIPPET_FORGED_WORKER"

run_case "BYPASS VECTOR 9: a cgroup naming a REAL task that is NOT in_progress (status: completed) is still BLOCKED -- git push" \
  "real-looking-invocation-id" "git push origin master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" "" "" "" "$PATCHED_SNIPPET_WRONG_STATUS"

run_case "BYPASS VECTOR 9: a cgroup naming a REAL task that is NOT in_progress (status: completed) is still BLOCKED -- gh pr merge" \
  "real-looking-invocation-id" "gh pr merge 1 --repo some/repo --merge" 1 0 \
  "BLOCKED: gh pr merge" "" "" "" "$PATCHED_SNIPPET_WRONG_STATUS"

run_case_matching_worker "sanity: a cgroup naming a REAL, in_progress task DOES pass through (both name-pattern AND task cross-reference genuinely satisfied)" \
  "test-unit-123" "git push origin master"

# =========================================================================
# ROUND 5: bypass vector 10 -- native git/gh command ALIASING (both the
# one-shot `-c alias.*=`/`--config-env=alias.*` form and persistent
# ~/.gitconfig `[alias]` / `gh alias set` entries) is now closed. This is
# the real, live-reproduced round-4-review finding:
#   `git -c alias.<name>=push <name> <remote> <branch>` (or a pre-existing
#   `[alias]` entry) let an interactive session push to a protected branch
#   completely undetected -- _interactive_guard_git_find_subcommand()
#   matched on the literal subcommand token with no alias-resolution step,
#   and the wrapper always execs the real git with the untouched argv, which
#   then expands the alias into an actual push. Reproduced live in this
#   round's audit (`git -c alias.wip=push wip origin master` really does
#   push, confirmed against a real git 2.43 install) before this fix landed.
#   Same class for gh: `gh alias set <name> 'pr merge ...'` then
#   `gh <name> ...` -- _interactive_guard_gh_is_merge() only recognized the
#   literal `pr merge`/API forms, no alias-resolution step. Reproduced live
#   (`gh alias list`'s real output format for gh 2.45 confirmed: one
#   "<name>: <expansion>" line per alias) before this fix landed too.
# =========================================================================

# --- one-shot `-c alias.*=` / `--config-env=alias.*` : hard rejected ---
run_case "BYPASS VECTOR 10: 'git -c alias.wip=push wip origin master' (one-shot alias, the exact round-4-review repro) is BLOCKED, real git never called" \
  "" "git -c alias.wip=push wip origin master" 1 0 \
  "BLOCKED: git invocation defines a one-shot alias" ""

run_case "BYPASS VECTOR 10: 'git --config-env=alias.wip=SOME_ENV wip origin master' (--config-env alias form) is BLOCKED" \
  "" "git --config-env=alias.wip=SOME_ENV wip origin master" 1 0 \
  "BLOCKED: git invocation defines a one-shot alias" ""

run_case "BYPASS VECTOR 10: 'git --config-env alias.wip SOME_ENV wip origin master' (space form) is BLOCKED" \
  "" "git --config-env alias.wip SOME_ENV wip origin master" 1 0 \
  "BLOCKED: git invocation defines a one-shot alias" ""

run_case "BYPASS VECTOR 10: one-shot alias is rejected even if the LITERAL subcommand typed is harmless (fail-closed regardless of what the alias maps to)" \
  "" "git -c alias.wip=push status" 1 0 \
  "BLOCKED: git invocation defines a one-shot alias" ""

run_case "BYPASS VECTOR 10 sanity: a non-alias '-c' config override ('-c user.name=x') is NOT hard-rejected -- passes through unaffected" \
  "" "git -c user.name=x push origin feature-branch" 0 1 "" ""

run_case_matching_worker "BYPASS VECTOR 10: systemd-simulated 'git -c alias.wip=push wip origin master' passes through (one-shot-alias reject is gated on interactive context, same as every other check here)" \
  "test-unit-123" "git -c alias.wip=push wip origin master"

# --- persistent git [alias] entries: resolved one level before deciding ---
run_case "BYPASS VECTOR 10: persistent git alias ('alias.wip = push' in ~/.gitconfig) invoked as 'git wip origin master' is BLOCKED" \
  "" "git wip origin master" 1 0 \
  "BLOCKED: git push to protected branch/ref 'master'" "" "" "" "" "alias.wip push"

run_case "BYPASS VECTOR 10 sanity: persistent git alias to a NON-protected branch ('git wip origin feature-branch') still passes through" \
  "" "git wip origin feature-branch" 0 1 "" "" "" "" "" "alias.wip push"

run_case "BYPASS VECTOR 10 sanity: an UNRELATED persistent git alias ('alias.co = checkout') still passes through unaffected" \
  "" "git co master" 0 1 "" "" "" "" "" "alias.co checkout"

run_case_matching_worker "BYPASS VECTOR 10: systemd-simulated persistent git alias push passes through" \
  "test-unit-123" "git wip origin master" "" "alias.wip push"

# --- persistent gh alias entries: resolved one level before deciding ---
run_case "BYPASS VECTOR 10: persistent gh alias ('gh alias set mrg \"pr merge --merge\"') invoked as 'gh mrg 1' is BLOCKED" \
  "" "gh mrg 1 --repo some/repo" 1 0 \
  "BLOCKED: gh pr merge" "" "" "" "" "" "mrg: pr merge --merge"

run_case "BYPASS VECTOR 10 sanity: an UNRELATED persistent gh alias ('co: pr checkout') still passes through unaffected" \
  "" "gh co 1 --repo some/repo" 0 1 "" "" "" "" "" "" "co: pr checkout"

run_case_matching_worker "BYPASS VECTOR 10: systemd-simulated persistent gh alias merge passes through" \
  "test-unit-123" "gh mrg 1 --repo some/repo" "" "" "mrg: pr merge --merge"

# --- residual gaps, disclosed and proven rather than silently omitted ---
run_case "BYPASS VECTOR 10 KNOWN LIMITATION (disclosed, not silently omitted): a NESTED persistent git alias ('alias.a = b', 'alias.b = push') is only resolved ONE level -- 'git a origin master' is NOT detected as push by this guard's own resolution (real git itself would still expand it fully and push)" \
  "" "git a origin master" 0 1 "" "" "" "" "" $'alias.a b\nalias.b push'

run_case "BYPASS VECTOR 10 KNOWN LIMITATION (disclosed, not silently omitted): a gh SHELL alias ('shellmrg: !gh pr merge 1 --merge') is left unresolved by this guard's own alias-resolution logic -- passes through undetected by THIS check specifically (live-verified separately: because real gh's own alias expansion re-invokes an unqualified 'gh', which still resolves through this guard's PATH-prepended wrapper and gets blocked there in the common case -- see KNOWN LIMITATIONS in the installer file)" \
  "" "gh shellmrg 1 --repo some/repo" 0 1 "" "" "" "" "" "" "shellmrg: '!gh pr merge 1 --merge'"

run_case "BYPASS VECTOR 10 KNOWN LIMITATION (new residual found and disclosed honestly while building THIS round's fix, not silently omitted): a persistent git alias whose value uses quote-splicing to spell out 'master' ('alias.evil = push origin \"ma\"\"ster\"') is NOT recognized by this guard's whitespace-only alias-value split -- live-verified separately against a real git 2.43 install that real git's OWN alias expansion still dequotes this to a literal 'master' destination and pushes there; this guard's own resolution logic deliberately does not attempt full quote/escape-aware parsing (see KNOWN LIMITATIONS in the installer file for why: doing so safely without 'eval'-ing attacker-influenced text is out of scope for this round)" \
  "" "git evil" 0 1 "" "" "" "" "" 'alias.evil push origin "ma""ster"'

if [ "$FAILURES" -eq 0 ]; then
  echo "All scenarios passed."
  exit 0
else
  echo "$FAILURES scenario(s) failed."
  exit 1
fi
