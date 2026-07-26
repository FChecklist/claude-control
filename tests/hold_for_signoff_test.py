#!/usr/bin/env python3
"""
Regression test for the HOLD_FOR_OWNER_SIGNOFF fix (2026-07-26, root-caused
against the PR563 incident): a dispatch prompt's prose instruction "must be
held for Owner sign-off, do not merge under any circumstance" had zero
effect on the actual merge decision, which is made purely by risk-tier.py's
deterministic tier classification plus the Superboss's AI verdict -- the
task auto-merged anyway.

Two things are tested, both against the REAL shipped code (no
reimplementation):

1. tight_task_validation.py's extract_hold_for_owner_signoff() -- the real
   parser -- correctly extracts the marker from EXPECTED_OUTPUT/CONSTRAINTS,
   and defaults to False when absent.
2. supervisor-entrypoint.sh's real HOLD-FOR-OWNER-SIGNOFF-BLOCK (extracted
   from the live script text and eval'd under mocked `gh`/`python3`, the
   same technique tests/supervisor_merge_detection_test.sh already uses) --
   given a tier1-eligible approve verdict AND HOLD_FOR_OWNER_SIGNOFF=True,
   it must NOT auto-merge.
"""
import importlib.util
import os
import subprocess
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIGHT_VALIDATION_PATH = os.path.join(REPO_ROOT, "scripts", "tight_task_validation.py")
SUPERVISOR_SCRIPT = os.path.join(REPO_ROOT, "scripts", "supervisor-entrypoint.sh")


def _load_tight_validation():
    spec = importlib.util.spec_from_file_location("tight_task_validation_under_test", TIGHT_VALIDATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_hold_for_signoff_parsed_true_from_expected_output():
    mod = _load_tight_validation()
    prompt = """## OBJECTIVE
Fix the thing.

## EXPECTED_OUTPUT
A real PR against claude-control.
HOLD_FOR_OWNER_SIGNOFF: true
"""
    fields = mod.parse_labeled_fields(prompt)
    assert mod.extract_hold_for_owner_signoff(fields) is True


def test_hold_for_signoff_parsed_true_from_constraints():
    mod = _load_tight_validation()
    prompt = """## OBJECTIVE
Fix the thing.

## CONSTRAINTS
Must be held for Owner sign-off, do not merge under any circumstance.
HOLD_FOR_OWNER_SIGNOFF: true
"""
    fields = mod.parse_labeled_fields(prompt)
    assert mod.extract_hold_for_owner_signoff(fields) is True


def test_hold_for_signoff_defaults_false_when_absent():
    mod = _load_tight_validation()
    prompt = """## OBJECTIVE
Fix the thing.

## EXPECTED_OUTPUT
A real PR against claude-control.
"""
    fields = mod.parse_labeled_fields(prompt)
    assert mod.extract_hold_for_owner_signoff(fields) is False


def _extract_hold_block():
    with open(SUPERVISOR_SCRIPT) as f:
        text = f.read()
    start = text.index("# --- HOLD-FOR-OWNER-SIGNOFF-BLOCK-START")
    end = text.index("# --- HOLD-FOR-OWNER-SIGNOFF-BLOCK-END ---") + len("# --- HOLD-FOR-OWNER-SIGNOFF-BLOCK-END ---")
    return text[start:end]


def _run_scenario(hold_value, verdict="approve", tier="tier1", scope_ok="1"):
    block = _extract_hold_block()
    assert block, f"could not find HOLD-FOR-OWNER-SIGNOFF-BLOCK markers in {SUPERVISOR_SCRIPT}"

    with tempfile.TemporaryDirectory() as tmp:
        gh_log = os.path.join(tmp, "gh.log")
        checkpoint_log = os.path.join(tmp, "checkpoint.log")

        script = f"""
set -uo pipefail
gh() {{
  echo "$*" >> "{gh_log}"
  if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
    echo "OPEN"
  fi
  return 0
}}
python3() {{
  if echo "$*" | grep -q "veridian-task.py checkpoint"; then
    echo "$*" >> "{checkpoint_log}"
  fi
  if echo "$*" | grep -q "notify-owner.py"; then
    echo "$*" >> "{checkpoint_log}"
  fi
  return 0
}}
export -f gh python3

PR_URL="https://github.com/FChecklist/fake-repo/pull/563"
TASK_DIR="{tmp}"
TASK_ID="fake-task-563"
REPO="fake-repo"
BRANCH="worker/fake-task-563"
VERDICT="{verdict}"
TIER="{tier}"
SCOPE_OK="{scope_ok}"
HOLD_FOR_OWNER_SIGNOFF="{hold_value}"

{block}
"""
        proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        assert proc.returncode == 0, f"scenario script failed: {proc.stderr}"

        gh_calls = open(gh_log).read() if os.path.isfile(gh_log) else ""
        checkpoint_calls = open(checkpoint_log).read() if os.path.isfile(checkpoint_log) else ""
        return gh_calls, checkpoint_calls


def test_hold_for_signoff_blocks_tier1_automerge():
    """The exact PR563 scenario: tier1, Superboss-approved, but
    HOLD_FOR_OWNER_SIGNOFF: true -- must NOT auto-merge."""
    gh_calls, checkpoint_calls = _run_scenario(hold_value="True", verdict="approve", tier="tier1", scope_ok="1")

    assert "pr merge" not in gh_calls, f"auto-merge was attempted despite HOLD_FOR_OWNER_SIGNOFF=true: {gh_calls}"
    assert "--status awaiting_human_approval" in checkpoint_calls, (
        f"expected an awaiting_human_approval checkpoint, got: {checkpoint_calls}"
    )
    assert "notify-owner.py" in checkpoint_calls


def test_hold_for_signoff_false_allows_normal_tier1_automerge_path():
    """Control: with HOLD_FOR_OWNER_SIGNOFF=false, the normal tier1 path
    (not this fix's concern) still runs -- proves the new check is not
    swallowing the pre-existing behavior."""
    gh_calls, checkpoint_calls = _run_scenario(hold_value="False", verdict="approve", tier="tier1", scope_ok="1")

    assert "--status awaiting_human_approval" not in checkpoint_calls
    assert "notify-owner.py" not in checkpoint_calls


if __name__ == "__main__":
    test_hold_for_signoff_parsed_true_from_expected_output()
    test_hold_for_signoff_parsed_true_from_constraints()
    test_hold_for_signoff_defaults_false_when_absent()
    test_hold_for_signoff_blocks_tier1_automerge()
    test_hold_for_signoff_false_allows_normal_tier1_automerge_path()
    print("All hold_for_signoff scenarios passed.")
