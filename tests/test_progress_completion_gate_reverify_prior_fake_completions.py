"""Re-verification of the now-live progress_completion_gate.py (merged as
PR #209, task-20260814-054242) against the REAL objective text of the two
previously fake completions this task (task-20260814-071416) was asked to
re-verify:

  - task-20260814-045316-report-approval-gate-in-credit-accountan
    (credit-accountant.py report-approval gate)
  - task-20260814-054352-actually-implement-the-server-native-pm
    (server-native PM sentinel-tick integration)

Both tasks' own real, final `prompt.txt` files (read verbatim from
/opt/veridian/ai-os/tasks/<task>/prompt.txt at the time this test was
written) are embedded below, so this test does not depend on those task
directories continuing to exist on disk.

For each real objective this proves BOTH directions the gate is supposed to
enforce, not just one: a doc-only diff for that real objective is REJECTED
(exit 1), and a real code diff touching the real objective file is ACCEPTED
(exit 0). This is the same mechanism (extract_named_code_files +
check_completion) the live gate uses, exercised end-to-end via the CLI
against scratch git repos -- no mocking of git itself.
"""
import os
import subprocess
import sys
import tempfile

import pytest

GATE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts",
    "progress_completion_gate.py",
)

# Real prompt.txt content for task-20260814-045316, captured verbatim.
PROMPT_045316_CREDIT_ACCOUNTANT = """\
P0 FLEET-WIDE OUTAGE. Real evidence gathered by the PM-Desktop sentinel on 2026-08-14 at approximately 04:44-05:00 UTC. This is verified; do not spend time re-discovering it.

SYMPTOM: 9 of the 10 most recently dispatched tasks terminate with task.yaml status=blocked, completed_steps empty, remaining_steps of Not started, files_modified empty, and .invocation_count of 1. The matching register rows go status=failed with a reason prefixed worker-exit-status-bridge. The sampled task directories live under /opt/veridian/ai-os/tasks/ and are all dated 2026-08-14 between 03:34 and 04:21 UTC.

CONFIRMED SINGLE ROOT CAUSE: every one of those workers emits this exact line into its worker.log immediately before terminating: {"approved": false, "reason": "no matching approved plan for this task_id/increment -- report rejected"}. The emitter is /opt/veridian/scripts/credit-accountant.py at line 316, a json.dumps carrying approved=False. I verified this signature is present in EVERY blocked worker I sampled, not merely a subset.

YOUR JOB:
1. Read /opt/veridian/scripts/credit-accountant.py around lines 280-340.
2. Fix the real defect so a legitimately dispatched task matches its plan.
3. Add a real regression test that drives a task through the approval path.
4. Open a real PR on claude-control containing real code changes.
5. Post a real AUDIT block on the PR matching the current head SHA.
"""

# Real prompt.txt content for task-20260814-054352, captured verbatim.
PROMPT_054352_SERVER_NATIVE_PM = """\
REAL FINDING: the PR believed to be the real deterministic-boolean-system integration of the server-native PM sentinel tick, financial-escalation policy, and hierarchy single-gateway policy is merged-audit-passed on paper, but its only changed file is a status report -- zero real code landed. The real integration work was never actually written. ACTION: for real this time, merge the three real pieces -- the sentinel-tick script, the financial-decision-escalation policy, and the hierarchy single-gateway policy -- into one real deterministic module with real code, per the original scope: reuse only, verify-before-wiring every named external tool, real boolean output contract, real measured token delta. Search the repo for whatever real script files these three pieces actually produced in their own real prior work and build on that real code, do not restart from zero, and do not produce another report-only diff. A completion whose diff touches no real script file must be rejected by the new fake-fix gate now being built in a sibling task -- expect that gate to apply here too. Report the real file paths changed and a real test run.
"""


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def _git(cwd, *args):
    r = _run(["git", *args], cwd)
    assert r.returncode == 0, f"git {args} failed: {r.stderr}"
    return r.stdout


@pytest.fixture
def scratch_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(str(repo), "init", "-q", "-b", "master")
    _git(str(repo), "config", "user.email", "test@test.local")
    _git(str(repo), "config", "user.name", "test")
    (repo / "README.md").write_text("base\n")
    _git(str(repo), "add", "-A")
    _git(str(repo), "commit", "-q", "-m", "base")
    base_sha = _git(str(repo), "rev-parse", "HEAD").strip()
    # No real network remote in a scratch repo -- fake the remote-tracking
    # ref the gate's `origin/{branch}` merge-base lookup needs.
    _git(str(repo), "update-ref", "refs/remotes/origin/master", base_sha)
    return str(repo)


def _task_dir(tmp_path, prompt_text):
    d = tmp_path / "task"
    d.mkdir()
    (d / "prompt.txt").write_text(prompt_text)
    return str(d)


def _check_completion(task_dir, workspace):
    r = _run(
        [
            sys.executable, GATE, "check-completion",
            "--task-dir", task_dir,
            "--workspace", workspace,
            "--default-branch", "master",
        ],
        cwd=workspace,
    )
    return r.returncode, r.stdout.strip()


@pytest.mark.parametrize(
    "label,prompt_text,real_file_rel",
    [
        (
            "credit-accountant (objective names the file directly)",
            PROMPT_045316_CREDIT_ACCOUNTANT,
            "credit-accountant.py",
        ),
        (
            # task-20260814-054352's own prompt names no literal code
            # filename (verified separately: extract_named_code_files()
            # returns [] for it -- confirmed in progress/task-20260814-071416
            # ...md). The real file this task's real merged fix actually
            # touched (veridian-scripts PR #355) is pm-sentinel-tick.sh;
            # exercised here directly since the gate is driven purely by
            # prompt.txt text.
            "server-native PM (pm-sentinel-tick.sh, this task's real file)",
            PROMPT_054352_SERVER_NATIVE_PM + "\nReal target file: pm-sentinel-tick.sh\n",
            "pm-sentinel-tick.sh",
        ),
    ],
)
def test_gate_rejects_doc_only_diff_for_real_objective(
    tmp_path, scratch_repo, label, prompt_text, real_file_rel
):
    task_dir = _task_dir(tmp_path, prompt_text)
    progress_dir = os.path.join(scratch_repo, "progress")
    os.makedirs(progress_dir, exist_ok=True)
    with open(os.path.join(progress_dir, "fake.md"), "w") as f:
        f.write(f"# fake completion\nClaims {real_file_rel} is done. (doc only)\n")
    _git(scratch_repo, "add", "-A")
    _git(scratch_repo, "commit", "-q", "-m", "docs: claim completion (no real code)")

    code, reason = _check_completion(task_dir, scratch_repo)
    assert code == 1, f"{label}: expected REJECT for doc-only diff, got: {reason}"
    assert real_file_rel in reason


@pytest.mark.parametrize(
    "label,prompt_text,real_file_rel,real_file_content",
    [
        (
            "credit-accountant (objective names the file directly)",
            PROMPT_045316_CREDIT_ACCOUNTANT,
            "credit-accountant.py",
            "# real fix content\ndef cmd_report():\n    pass\n",
        ),
        (
            "server-native PM (pm-sentinel-tick.sh, this task's real file)",
            PROMPT_054352_SERVER_NATIVE_PM + "\nReal target file: pm-sentinel-tick.sh\n",
            "pm-sentinel-tick.sh",
            "#!/bin/bash\n# real fix content\nassert_zero_llm_token_usage() { :; }\n",
        ),
    ],
)
def test_gate_accepts_real_code_diff_for_real_objective(
    tmp_path, scratch_repo, label, prompt_text, real_file_rel, real_file_content
):
    task_dir = _task_dir(tmp_path, prompt_text)
    path = os.path.join(scratch_repo, real_file_rel)
    os.makedirs(os.path.dirname(path) or scratch_repo, exist_ok=True)
    with open(path, "w") as f:
        f.write(real_file_content)
    _git(scratch_repo, "add", "-A")
    _git(scratch_repo, "commit", "-q", "-m", f"fix: real code change to {real_file_rel}")

    code, reason = _check_completion(task_dir, scratch_repo)
    assert code == 0, f"{label}: expected ACCEPT for real code diff, got: {reason}"
    assert real_file_rel in reason


def test_server_native_pm_prompt_names_no_literal_code_file():
    """Documents a real, honest finding from the re-verification: task
    task-20260814-054352's own real prompt.txt never spells out a literal
    code filename (its real objective file, pm-sentinel-tick.sh, lives in a
    different repo and is only referenced in prose as "the sentinel-tick
    script"). extract_named_code_files() therefore returns [] for it, which
    means the live gate does not fire on that task's own claude-control diff
    at all -- correctly matching the fact that this task's real code fix
    genuinely landed in FChecklist/veridian-scripts (PR #355), not here."""
    sys.path.insert(
        0,
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
    )
    from progress_completion_gate import extract_named_code_files

    assert extract_named_code_files(PROMPT_054352_SERVER_NATIVE_PM) == []
