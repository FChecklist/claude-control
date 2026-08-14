#!/usr/bin/env python3
"""Unit tests for scripts/merge_gate.py -- the real deterministic merge gate
(task-20260814-095552-block-merges-that-have-no-fresh-passing).

Every scenario mocks only `merge_gate._run_gh` (the one real subprocess call
site) with canned `gh pr view --json ...` output shaped exactly like GitHub's
real response, so `evaluate_gate`/`merge_pr_via_gate` themselves run
unmodified, real code -- these tests prove the gate's own decision logic, not
a re-implementation of it. Live, unmocked end-to-end proof against real PRs
is documented separately in this task's progress file (real `gh` output
against claude-control PR #217/#219/#223 etc.).
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import merge_gate  # noqa: E402


def _pr_view_json(head_sha, comments=None, reviews=None, state="OPEN"):
    return json.dumps({
        "number": 999,
        "url": "https://github.com/ORG/REPO/pull/999",
        "state": state,
        "headRefOid": head_sha,
        "comments": comments or [],
        "reviews": reviews or [],
    })


def _comment(body, ts):
    return {"author": {"login": "bot"}, "body": body, "createdAt": ts}


def test_refuses_when_no_verdict_posted_at_all(monkeypatch):
    """Real incident shape: claude-control PR #216/#217/#220/#221/#226,
    veridian-scripts #356/#366 -- merged with ZERO audit verdict anywhere."""
    calls = []

    def fake_run_gh(args, timeout=60):
        calls.append(args)
        return _pr_view_json("deadbeef" * 5, comments=[
            _comment("Looks good to me, nice work!", "2026-08-14T01:00:00Z"),
        ])

    monkeypatch.setattr(merge_gate, "_run_gh", fake_run_gh)
    decision = merge_gate.evaluate_gate("ORG/REPO", 999)
    assert decision["allowed"] is False
    assert "no audit verdict found" in decision["reason"]


def test_refuses_when_newest_verdict_is_fail(monkeypatch):
    """Real incident shape: claude-control PR #219 -- an AUDIT: FAIL comment
    outstanding at merge time must refuse, even if an OLDER comment happened
    to say PASS (newest verdict wins, not just any verdict)."""
    head = "1234567" + "0" * 33

    def fake_run_gh(args, timeout=60):
        return _pr_view_json(head, comments=[
            _comment(f"AUDIT: PASS\nHead SHA audited: `{head}`", "2026-08-14T08:00:00Z"),
            _comment("AUDIT: FAIL\nmetric-state corruption found.", "2026-08-14T09:00:00Z"),
        ])

    monkeypatch.setattr(merge_gate, "_run_gh", fake_run_gh)
    decision = merge_gate.evaluate_gate("ORG/REPO", 999)
    assert decision["allowed"] is False
    assert "FAIL" in decision["reason"]
    assert decision["latest_verdict"]["ts"] == "2026-08-14T09:00:00Z"


def test_refuses_stale_pass_when_cited_sha_not_current_head(monkeypatch):
    """The exact bug this task's SPEC calls out by name: "a stale pass,
    meaning a pass whose cited SHA is not the current head - this stale case
    is real and already burned us when a later commit dropped previously
    audited content." A later commit landed after the PASS was posted."""
    old_sha = "aaaaaaa" + "0" * 33
    new_sha = "bbbbbbb" + "0" * 33

    def fake_run_gh(args, timeout=60):
        return _pr_view_json(new_sha, comments=[
            _comment(f"AUDIT: PASS\nHead SHA audited: `{old_sha}`", "2026-08-14T08:00:00Z"),
        ])

    monkeypatch.setattr(merge_gate, "_run_gh", fake_run_gh)
    decision = merge_gate.evaluate_gate("ORG/REPO", 999)
    assert decision["allowed"] is False
    assert "stale pass" in decision["reason"]
    assert old_sha in decision["reason"] and new_sha in decision["reason"]


def test_refuses_pass_with_no_sha_citation(monkeypatch):
    """Real incident shape: claude-control PR #219's own final AUDIT: PASS
    comment (posted by supervisor-entrypoint.sh's own current AUDIT_BODY
    format) never cited a head SHA at all -- must refuse, not trust it."""
    head = "cccccc7" + "0" * 33

    def fake_run_gh(args, timeout=60):
        return _pr_view_json(head, comments=[
            _comment("AUDIT: PASS\nNo issues found.", "2026-08-14T08:00:00Z"),
        ])

    monkeypatch.setattr(merge_gate, "_run_gh", fake_run_gh)
    decision = merge_gate.evaluate_gate("ORG/REPO", 999)
    assert decision["allowed"] is False
    assert "cites no head SHA" in decision["reason"]


def test_allows_fresh_pass_citing_current_head(monkeypatch):
    head = "dddddd7" + "0" * 33

    def fake_run_gh(args, timeout=60):
        return _pr_view_json(head, comments=[
            _comment("AUDIT: FAIL\nold finding, since fixed.", "2026-08-14T07:00:00Z"),
            _comment(f"AUDIT: PASS\nHead SHA audited: `{head}`", "2026-08-14T09:00:00Z"),
        ])

    monkeypatch.setattr(merge_gate, "_run_gh", fake_run_gh)
    decision = merge_gate.evaluate_gate("ORG/REPO", 999)
    assert decision["allowed"] is True


def test_review_body_with_verdict_is_considered(monkeypatch):
    """Verdicts can arrive as a real PR review, not only an issue comment --
    the gate must merge both timelines, not just scan comments."""
    head = "eeeeee7" + "0" * 33

    def fake_run_gh(args, timeout=60):
        return _pr_view_json(head, reviews=[
            {"author": {"login": "auditor"}, "body": f"AUDIT: PASS\nHead SHA audited: `{head}`",
             "state": "APPROVED", "submittedAt": "2026-08-14T09:00:00Z"},
        ])

    monkeypatch.setattr(merge_gate, "_run_gh", fake_run_gh)
    decision = merge_gate.evaluate_gate("ORG/REPO", 999)
    assert decision["allowed"] is True
    assert decision["latest_verdict"]["kind"] == "review"


def test_merge_pr_via_gate_never_calls_gh_pr_merge_on_refuse(monkeypatch):
    """The core "cannot be bypassed" contract: on REFUSE, `gh pr merge` must
    never be invoked at all -- not attempted-then-undone, never called."""
    merge_calls = []

    def fake_run_gh(args, timeout=60):
        if args[:2] == ["pr", "merge"]:
            merge_calls.append(args)
            return ""
        return _pr_view_json("f" * 40, comments=[])  # no verdict -> refuse

    monkeypatch.setattr(merge_gate, "_run_gh", fake_run_gh)
    decision = merge_gate.merge_pr_via_gate("ORG/REPO", 999)
    assert decision["allowed"] is False
    assert decision["merge_attempted"] is False
    assert merge_calls == []


def test_merge_pr_via_gate_calls_gh_pr_merge_on_allow_and_verifies_via_fresh_view(monkeypatch):
    """On ALLOW, `gh pr merge` IS called, and success is judged only via a
    fresh `gh pr view --json state,mergedAt` call afterward -- the same
    real-incident-driven rule tests/supervisor_merge_detection_test.sh
    already established for supervisor-entrypoint.sh's own merge call (a
    `gh pr merge` can succeed server-side and still exit non-zero locally)."""
    head = "a1a1a1a" + "0" * 33
    calls = []

    def fake_run_gh(args, timeout=60):
        calls.append(args)
        if args[:2] == ["pr", "merge"]:
            return ""
        if args[:2] == ["pr", "view"] and "state,mergedAt" in args:
            return json.dumps({"state": "MERGED", "mergedAt": "2026-08-14T10:00:00Z"})
        return _pr_view_json(head, comments=[
            _comment(f"AUDIT: PASS\nHead SHA audited: `{head}`", "2026-08-14T09:00:00Z"),
        ])

    monkeypatch.setattr(merge_gate, "_run_gh", fake_run_gh)
    decision = merge_gate.merge_pr_via_gate("ORG/REPO", 999, merge_method="squash", delete_branch=True)
    assert decision["allowed"] is True
    assert decision["merge_attempted"] is True
    assert decision["merged"] is True
    merge_call = next(c for c in calls if c[:2] == ["pr", "merge"])
    assert "--squash" in merge_call
    assert "--delete-branch" in merge_call


def test_short_sha_prefix_match_is_accepted(monkeypatch):
    """A real audit citing a short SHA prefix (e.g. `4d8f307`) against a full
    40-char headRefOid must still match -- both this repo's own convention
    and GitHub's own short-SHA display use prefixes, not just full hashes."""
    full_head = "4d8f3071234567890abcdef1234567890abcdef"

    def fake_run_gh(args, timeout=60):
        return _pr_view_json(full_head, comments=[
            _comment("AUDIT: PASS\nHead SHA audited: `4d8f307`", "2026-08-14T09:00:00Z"),
        ])

    monkeypatch.setattr(merge_gate, "_run_gh", fake_run_gh)
    decision = merge_gate.evaluate_gate("ORG/REPO", 999)
    assert decision["allowed"] is True


def test_gh_error_is_never_silently_treated_as_allow(monkeypatch):
    """Fail closed: if `gh` itself errors (auth/network/rate-limit), the CLI
    entrypoints must exit non-zero, never default to permitting a merge."""
    def fake_run_gh(args, timeout=60):
        raise merge_gate.GhError("simulated network failure")

    monkeypatch.setattr(merge_gate, "_run_gh", fake_run_gh)
    with pytest.raises(merge_gate.GhError):
        merge_gate.evaluate_gate("ORG/REPO", 999)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
