#!/usr/bin/env python3
"""
Regression tests for the plan_backlog_completion.py dedup fix (2026-07-27,
root-caused against the mass-mislabeling incident where 32 real task.yaml
files were hand-edited to status=superseded, falsely citing this tool for a
collapse decision it never made and had no code path to make).

Two things are tested, both against the REAL shipped module (no
reimplementation), using synthetic fixture data under tests/fixtures/ --
never the real production ai-os/tasks/ tree:

1. classify() no longer trusts "a PR referenced somewhere in the chain's
   checkpoints happens to be merged" as proof an issue is done. It must
   independently re-run the ORIGINAL task's own SUCCESS_CRITERIA and only
   conclude ALREADY_DONE_STALE_STATUS when that verification actually
   passes. This reproduces the real historical fixture: task-20260726-083946
   (original), its rca-chain retries, PR #81 (closed without merging), and
   PR #104 (real, merged -- but its actual diff only fixes an unrelated
   crontab preflight hard-stop, not branch resolution or hold-for-signoff).
2. apply_collapse() -- the one real, auditable code path allowed to write
   status=superseded/duplicate_of/superseded_reason -- refuses to write
   anything for a non-verified category, and cites real evidence when it
   does write.
"""
import importlib.util
import os

import pytest
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(REPO_ROOT, "scripts", "plan_backlog_completion.py")
FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
INCIDENT_FIXTURE = os.path.join(FIXTURES_DIR, "dedup_083946_incident")
PROSE_ONLY_FIXTURE = os.path.join(FIXTURES_DIR, "dedup_prose_only_criteria")


def _load_module():
    spec = importlib.util.spec_from_file_location("plan_backlog_completion_under_test", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _single_group(mod, tasks_dir):
    """Point the module at a fixture tasks dir and return its one dedup'd group."""
    mod.TASKS_DIR = tasks_dir
    tasks = mod.load_all_tasks()
    groups = mod.build_groups(tasks)
    assert len(groups) == 1, f"fixture must collapse to exactly one issue group, got {list(groups.keys())}"
    ((_, group),) = groups.items()
    return sorted(group, key=lambda t: (t.get("created_at") or "", t.get("last_checkpoint_at") or ""))


def test_success_criteria_extraction_from_real_fixture_prompt():
    mod = _load_module()
    prompt_path = os.path.join(
        INCIDENT_FIXTURE,
        "task-20260726-083946-fix-task-lifecycle--real-branch-resoluti",
        "prompt.txt",
    )
    with open(prompt_path) as f:
        text = f.read()
    fields = mod.parse_labeled_fields(text)
    commands = mod.extract_verifiable_commands(fields["successCriteria"])
    assert any("pytest" in c and "branch_resolution or hold_for_signoff" in c for c in commands)
    assert sum(c.startswith("grep") for c in commands) == 2


def test_find_group_original_picks_the_real_original_not_an_rca_retry():
    mod = _load_module()
    group_sorted = _single_group(mod, INCIDENT_FIXTURE)
    original = mod.find_group_original(group_sorted)
    assert original["id"] == "task-20260726-083946-fix-task-lifecycle--real-branch-resoluti"


def test_classify_does_not_credit_unrelated_merged_pr_in_rca_chain(monkeypatch):
    """The naive max-PR-number-mentioned + mergedAt check used to label this
    ALREADY_DONE_STALE_STATUS purely because PR #104 (mentioned in the round-3
    rca attempt's checkpoint) merged. The fixed classify() must independently
    re-run the ORIGINAL task's own SUCCESS_CRITERIA and, when that
    verification fails (simulating reality: PR #104 never touched branch
    resolution or hold-for-signoff), must NOT credit PR #104 or collapse."""
    mod = _load_module()
    group_sorted = _single_group(mod, INCIDENT_FIXTURE)
    rep = group_sorted[-1]

    def fake_gh_pr_state(repo, pr_number):
        assert pr_number == 104  # highest PR# mentioned across this fixture's checkpoints
        return {
            "state": "CLOSED", "mergedAt": "2026-07-27T04:20:00Z", "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED", "title": "Fix RCA: route crontab_unauthorized_change to hard-stop",
            "url": "https://github.com/FChecklist/claude-control/pull/104",
        }
    monkeypatch.setattr(mod, "gh_pr_state", fake_gh_pr_state)

    def fake_verify_fn(repo, commands):
        # Simulates independently re-running the ORIGINAL task's SUCCESS_CRITERIA
        # against the real default branch and finding it does NOT pass -- PR #104's
        # real diff never touched branch resolution / hold-for-signoff.
        return False, [{"command": c, "passed": False, "checked_commit": "deadbeef"} for c in commands]

    result = mod.classify(rep, group_sorted, db_cur=None, effective_repo="claude-control", verify_fn=fake_verify_fn)

    assert result["pr_number"] == 104
    assert result["category"] != "ALREADY_DONE_STALE_STATUS"
    assert result["category"] == "PR_MERGED_BUT_SUCCESS_CRITERIA_UNVERIFIED"
    verification = result.get("success_criteria_verification")
    assert verification is not None
    assert verification["verified"] is False
    assert verification["original_task_id"] == "task-20260726-083946-fix-task-lifecycle--real-branch-resoluti"


def test_classify_collapses_only_when_success_criteria_verification_actually_passes(monkeypatch):
    mod = _load_module()
    group_sorted = _single_group(mod, INCIDENT_FIXTURE)
    rep = group_sorted[-1]

    def fake_gh_pr_state(repo, pr_number):
        return {"state": "CLOSED", "mergedAt": "2026-07-27T04:20:00Z"}
    monkeypatch.setattr(mod, "gh_pr_state", fake_gh_pr_state)

    def fake_verify_fn(repo, commands):
        return True, [{"command": c, "passed": True, "checked_commit": "cafef00d"} for c in commands]

    result = mod.classify(rep, group_sorted, db_cur=None, effective_repo="claude-control", verify_fn=fake_verify_fn)

    assert result["category"] == "ALREADY_DONE_STALE_STATUS"
    assert "cafef00d" in result["action"]
    assert result["success_criteria_verification"]["verified"] is True


def test_prose_only_success_criteria_is_never_silently_treated_as_verified(monkeypatch):
    mod = _load_module()
    group_sorted = _single_group(mod, PROSE_ONLY_FIXTURE)
    rep = group_sorted[-1]

    def fake_gh_pr_state(repo, pr_number):
        return {"state": "CLOSED", "mergedAt": "2026-01-02T00:00:00Z"}
    monkeypatch.setattr(mod, "gh_pr_state", fake_gh_pr_state)

    def fail_if_called(repo, commands):
        raise AssertionError("verify_fn must not be invoked when there are no runnable commands")

    # No runnable commands exist in this fixture's SUCCESS_CRITERIA (prose-only) --
    # classify() must short-circuit to CANNOT_AUTO_VERIFY_NEEDS_HUMAN_READ without
    # ever calling verify_fn (proven by passing one that raises if invoked).
    result = mod.classify(rep, group_sorted, db_cur=None, effective_repo="claude-control", verify_fn=fail_if_called)

    assert result["category"] == "CANNOT_AUTO_VERIFY_NEEDS_HUMAN_READ"
    assert result["category"] != "ALREADY_DONE_STALE_STATUS"
    assert result["success_criteria_verification"]["verified"] is False


def test_apply_collapse_refuses_non_verified_category(tmp_path):
    mod = _load_module()
    mod.TASKS_DIR = str(tmp_path)
    task_dir = tmp_path / "task-x"
    task_dir.mkdir()
    (task_dir / "task.yaml").write_text("id: task-x\nstatus: failed\n")

    with pytest.raises(ValueError):
        mod.apply_collapse("task-x", "task-y", "PR_PENDING_MERGE", "some evidence", dry_run=False)

    # refused -- file must be untouched
    assert yaml.safe_load((task_dir / "task.yaml").read_text())["status"] == "failed"


def test_apply_collapse_refuses_missing_evidence(tmp_path):
    mod = _load_module()
    mod.TASKS_DIR = str(tmp_path)
    task_dir = tmp_path / "task-x"
    task_dir.mkdir()
    (task_dir / "task.yaml").write_text("id: task-x\nstatus: failed\n")

    with pytest.raises(ValueError):
        mod.apply_collapse("task-x", "task-y", "ALREADY_DONE_STALE_STATUS", "  ", dry_run=False)


def test_apply_collapse_writes_real_task_yaml_with_cited_evidence(tmp_path):
    mod = _load_module()
    mod.TASKS_DIR = str(tmp_path)
    task_dir = tmp_path / "task-x"
    task_dir.mkdir()
    (task_dir / "task.yaml").write_text("id: task-x\nstatus: failed\ntitle: thing\n")

    mod.apply_collapse(
        "task-x", "task-y", "ALREADY_DONE_STALE_STATUS",
        "PR #999 merged; original task `task-x`'s SUCCESS_CRITERIA (1 command(s)) independently "
        "re-run and passing at commit abc123.",
        dry_run=False,
    )

    written = yaml.safe_load((task_dir / "task.yaml").read_text())
    assert written["status"] == "superseded"
    assert written["duplicate_of"] == "task-y"
    assert "abc123" in written["superseded_reason"]
    assert "plan_backlog_completion.py --apply" in written["superseded_reason"]


def test_apply_collapse_dry_run_does_not_write(tmp_path):
    mod = _load_module()
    mod.TASKS_DIR = str(tmp_path)
    task_dir = tmp_path / "task-x"
    task_dir.mkdir()
    (task_dir / "task.yaml").write_text("id: task-x\nstatus: failed\n")

    mod.apply_collapse("task-x", "task-y", "ALREADY_DONE_STALE_STATUS", "evidence here", dry_run=True)

    assert yaml.safe_load((task_dir / "task.yaml").read_text())["status"] == "failed"
