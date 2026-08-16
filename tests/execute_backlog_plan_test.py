#!/usr/bin/env python3
"""
Tests for execute_backlog_plan.py's OWN orchestration logic (2026-07-27,
independent review of PR #102 flagged this file -- the one that performs
real duplicate-collapse task.yaml writes, git pushes, PR creation, and
systemd service starts once live -- as having zero automated test coverage
of its own wiring, distinct from the already-well-tested classify()/
apply_verified_collapses()/apply_representative_completion() functions in
plan_backlog_completion.py that it delegates to).

These tests never call classify()/build_groups() themselves (already covered
by plan_backlog_completion_dedup_test.py) and never touch real
ai-os/tasks/*/task.yaml, real git remotes, or real systemd units -- every
phase function under test here is exercised against synthetic in-memory plan
fixtures and tmp_path task directories, with dispatch_core, subprocess, and
the delegated plan_backlog_completion module all monkeypatched/stubbed.

Two things are tested:

1. phase1and2_collapse_verified() -- this script's own for-loop that decides
   which representative/duplicate task ids to record as
   marked_completed/duplicates_marked and to emit a dispatch_event for --
   only ever touches issues classified ALREADY_DONE_STALE_STATUS with a
   success_criteria_verification that actually passed. This is the same
   safety invariant plan_backlog_completion.py's own apply_verified_collapses
   enforces, but exercised here at THIS script's own bookkeeping layer,
   which apply_verified_collapses() is stubbed out for so the loop's own
   filtering (not the delegated function's) is what is under test.
2. main()'s phase dispatch/wave-sequencing wiring: given one small synthetic
   plan with one issue per category, main() must route each issue through
   the correct phase (collapse / supervisor routing / wave-sequenced
   redispatch) and must process lower-numbered waves before higher-numbered
   ones in phase4, regardless of the issues' order in the input plan.
"""
import contextlib
import importlib.util
import json
import os

import pytest
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(REPO_ROOT, "scripts", "execute_backlog_plan.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("execute_backlog_plan_under_test", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@contextlib.contextmanager
def _noop_lock():
    yield


class _StubFixedModule:
    """Stands in for the real plan_backlog_completion module load_fixed_module()
    returns -- apply_verified_collapses() itself is already covered by
    plan_backlog_completion_dedup_test.py, so it is stubbed here to isolate
    THIS script's own dispatch/bookkeeping loop as the thing under test."""

    def __init__(self):
        self.calls = []

    def apply_verified_collapses(self, issues, dry_run=True):
        self.calls.append((issues, dry_run))
        return sum(len(i["all_attempt_ids"]) for i in issues)


def test_phase1and2_only_touches_verified_already_done_issues(monkeypatch):
    """The safety invariant already proven for apply_verified_collapses() in
    plan_backlog_completion_dedup_test.py: an unverified ALREADY_DONE_STALE_STATUS
    issue and a differently-categorized issue must never be credited as
    collapsed/completed. Proven here at this script's OWN bookkeeping loop
    (results dict + dispatch_event emission), independent of the delegated
    apply_verified_collapses() call, which is stubbed out."""
    mod = _load_module()
    recorded_events = []
    monkeypatch.setattr(mod.dispatch_core, "record_dispatch_event",
                         lambda task_id, **kw: recorded_events.append((task_id, kw)))

    plan = {
        "issues": [
            {
                "issue_key": "1:verified-dup",
                "representative_task_id": "task-verified-rep",
                "all_attempt_ids": ["task-verified-rep", "task-verified-dup1", "task-verified-dup2"],
                "classification": {
                    "category": "ALREADY_DONE_STALE_STATUS",
                    "pr_number": 55,
                    "success_criteria_verification": {"verified": True},
                },
            },
            {
                "issue_key": "2:unverified",
                "representative_task_id": "task-unverified-rep",
                "all_attempt_ids": ["task-unverified-rep", "task-unverified-dup1"],
                "classification": {
                    "category": "ALREADY_DONE_STALE_STATUS",
                    "pr_number": 56,
                    "success_criteria_verification": {"verified": False},
                },
            },
            {
                "issue_key": "3:other-category",
                "representative_task_id": "task-pr-pending-rep",
                "all_attempt_ids": ["task-pr-pending-rep"],
                "classification": {"category": "PR_PENDING_MERGE", "pr_number": 57},
            },
        ],
    }
    results = {"marked_completed": [], "duplicates_marked": []}
    stub_fixed = _StubFixedModule()

    mod.phase1and2_collapse_verified(plan, results, stub_fixed)

    assert results["marked_completed"] == ["task-verified-rep"]
    assert sorted(results["duplicates_marked"]) == ["task-verified-dup1", "task-verified-dup2"]

    assert [tid for tid, _ in recorded_events] == ["task-verified-rep"]
    _, kw = recorded_events[0]
    assert kw["extra"]["action"] == "status_corrected_to_completed_verified"
    assert kw["extra"]["pr"] == 55

    # the delegated (already-tested) function was still forwarded the FULL
    # issue list unfiltered -- filtering for its own write decision is its job
    assert stub_fixed.calls == [(plan["issues"], False)]


def test_main_dispatches_phases_and_sequences_waves(monkeypatch, tmp_path):
    """Exercises main()'s own wiring: correct phase per issue category, and
    phase4's wave-sequencing (lower wave numbers dispatched before higher
    ones, regardless of input order) -- against a small synthetic plan and
    isolated tmp_path task directories. No real ai-os/tasks, git remote, or
    systemd unit is touched; subprocess/dispatch_core/GATEWAY-shaped calls
    are all faked."""
    mod = _load_module()

    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    ai_os_dir = tmp_path / "ai-os"
    ai_os_dir.mkdir()
    mod.TASKS_DIR = str(tasks_dir)
    mod.AI_OS = str(ai_os_dir)

    pr_rep_dir = tasks_dir / "task-pr-rep"
    pr_rep_dir.mkdir()
    (pr_rep_dir / "task.yaml").write_text("id: task-pr-rep\nstatus: blocked\ntitle: pr issue\n")

    for rep in ("task-wave1", "task-wave2"):
        d = tasks_dir / rep
        d.mkdir()
        (d / "prompt.txt").write_text(f"do the thing for {rep}\n")

    plan = {
        "issues": [
            {
                "issue_key": "1:dup",
                "representative_task_id": "task-dup-rep",
                "all_attempt_ids": ["task-dup-rep", "task-dup-a"],
                "repo": "claude-control",
                "title": "dup issue",
                "classification": {
                    "category": "ALREADY_DONE_STALE_STATUS",
                    "pr_number": 55,
                    "success_criteria_verification": {"verified": True},
                },
            },
            {
                "issue_key": "2:pr",
                "representative_task_id": "task-pr-rep",
                "all_attempt_ids": ["task-pr-rep"],
                "repo": "claude-control",
                "title": "pr issue",
                "classification": {
                    "category": "PR_PENDING_MERGE",
                    "pr_number": 77,
                    "pr_state": {"url": "https://github.com/FChecklist/claude-control/pull/77"},
                },
            },
            # wave 2 listed BEFORE wave 1 on purpose -- proves wave-sequencing
            # sorts by wave number, not input order.
            {
                "issue_key": "3:wave2",
                "representative_task_id": "task-wave2",
                "all_attempt_ids": ["task-wave2"],
                "repo": "claude-control",
                "title": "wave2 issue",
                "wave": 2,
                "classification": {"category": "NEEDS_FRESH_REDISPATCH"},
            },
            {
                "issue_key": "4:wave1",
                "representative_task_id": "task-wave1",
                "all_attempt_ids": ["task-wave1"],
                "repo": "claude-control",
                "title": "wave1 issue",
                "wave": 1,
                "classification": {"category": "PR_CLOSED_NEEDS_REDISPATCH"},
            },
        ],
    }

    monkeypatch.setattr(mod, "load_fixed_module", lambda: _StubFixedModule())
    monkeypatch.setattr(mod, "regenerate_fresh_plan", lambda: (plan, str(tmp_path / "fresh.json")))

    monkeypatch.setattr(mod.dispatch_core, "acquire_dispatch_lock", _noop_lock)
    monkeypatch.setattr(mod.dispatch_core, "has_free_slot", lambda: True)
    monkeypatch.setattr(mod.dispatch_core, "running_worker_count", lambda: 0)
    recorded_events = []
    monkeypatch.setattr(mod.dispatch_core, "record_dispatch_event",
                         lambda task_id, **kw: recorded_events.append((task_id, kw)))

    def fake_run(cmd, **kwargs):
        class FakeResult:
            def __init__(self, returncode=0, stdout="", stderr=""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        if cmd[0] == "systemctl":
            return FakeResult(returncode=0)
        if cmd[:3] == ["python3", mod.GATEWAY, "submit"]:
            return FakeResult(returncode=0, stdout=json.dumps({"instruction_id": "instr-1"}))
        if cmd[:3] == ["python3", mod.GATEWAY, "start"]:
            return FakeResult(returncode=0, stdout=json.dumps({"task_id": "new-task-1", "work_item_id": "wi-1"}))
        raise AssertionError(f"unexpected real subprocess call in test: {cmd}")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)

    mod.main()

    out_files = list(ai_os_dir.glob("BACKLOG_PLAN_EXECUTION_RESULT_*.json"))
    assert len(out_files) == 1
    results = json.loads(out_files[0].read_text())

    # phase1+2: only the ALREADY_DONE_STALE_STATUS+verified issue was collapsed
    assert results["marked_completed"] == ["task-dup-rep"]
    assert results["duplicates_marked"] == ["task-dup-a"]

    # phase3: the PR_PENDING_MERGE issue was routed to supervisor, and its
    # task.yaml was actually flipped to pending_review
    assert results["routed_to_supervisor"] == ["task-pr-rep"]
    pr_doc = yaml.safe_load((pr_rep_dir / "task.yaml").read_text())
    assert pr_doc["status"] == "pending_review"

    # phase4: both redispatch-category issues were dispatched, wave 1 before wave 2
    assert [r["original"] for r in results["redispatched"]] == ["task-wave1", "task-wave2"]

    # every phase's real action emitted its own dispatch_event, in phase order
    # (phase4's events key on the NEW redispatched task id, not the original)
    assert [tid for tid, _ in recorded_events] == [
        "task-dup-rep", "task-pr-rep", "new-task-1", "new-task-1",
    ]
    assert [kw["extra"]["original_task_id"] for _, kw in recorded_events[2:]] == ["task-wave1", "task-wave2"]
