#!/usr/bin/env python3
"""
End-to-end integration test for task-20260726-092433: a raw Owner-style chat
message gets classified by OWNER_ENGINE (scripts/prompt_gateway/gateway.py)
and routed through the new single entrypoint (TaskGateway.route_and_dispatch /
--mode owner-dispatch) directly into a real task-gateway.py invocation --
closing the manual "AI reads OWNER_ENGINE's output, hand-constructs a
task-gateway.py command" gap SCOPE item 1 describes.

Test-mode/dry-run per EXPECTED_OUTPUT: a fake runner is injected in place of
dispatch_to_task_lifecycle()'s real subprocess.run() wrapper, so every
assertion here is against the REAL argv task-gateway.py would have received --
without ever performing a live production dispatch (no real systemd start, no
real gh/claude calls, no real credit spend).

Run with: python3 -m pytest tests/ -k "gateway_task_integration or owner_engine_task"
"""
import importlib.util
import json
import os
import sqlite3
import sys
import types

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "prompt_gateway"))

import gateway  # noqa: E402


def _make_gateway(tmp_path):
    return gateway.TaskGateway(base_dir=str(tmp_path))


def _fake_runner(calls):
    """Records every constructed task-gateway.py invocation instead of
    executing it -- the "dry-run, not a live production dispatch" test mode.
    Returns a runner closure that appends each argv to `calls`."""
    def runner(cmd, input_text=None):
        calls.append(cmd)
        if len(cmd) > 2 and cmd[2] == "submit":
            return {
                "command": cmd, "returncode": 0,
                "stdout": json.dumps({"instruction_id": "INS-FAKE-TEST-1"}),
                "stderr": "", "parsed": {"instruction_id": "INS-FAKE-TEST-1"},
            }
        return {"command": cmd, "returncode": 0, "stdout": "{}", "stderr": "", "parsed": {}}
    return runner


FULL_SPEC_TEXT = """## OBJECTIVE
Wire the gratuity calculator's rounding fix into the live route.
## SCOPE
Only scripts/gratuity_calculator.py, no other module.
## KNOWN_CONTEXT
Read scripts/gratuity_calculator.py before changing it.
## SUCCESS_CRITERIA
`python3 -m pytest tests/test_gratuity_calculator.py -q`
## EXPECTED_OUTPUT
A merged PR against claude-control.
## CONSTRAINTS
Do not change any other route.
## COMPLEXITY_TIER
mechanical
"""


def test_owner_engine_task_dispatch_routes_new_task_to_submit(tmp_path):
    gw = _make_gateway(tmp_path)
    calls = []
    result = gw.route_and_dispatch(
        "Create a task to review the deployment PR before Friday",
        session_id="test-session-1", runner=_fake_runner(calls),
    )
    dispatch = result["lifecycle_dispatch"]
    assert dispatch["action"] == "submit"
    assert len(calls) == 1
    cmd = calls[0]
    assert os.path.basename(cmd[1]) == "task-gateway.py"
    assert cmd[2] == "submit"
    assert cmd[cmd.index("--source") + 1] == "ai_agent"
    # The text passed to task-gateway.py is the ALREADY-gated machine prompt,
    # never the raw Owner text verbatim -- OWNER_ENGINE's own gate contract
    # (task-gateway.py's own run_owner_engine_gate must never re-run on this).
    assert cmd[cmd.index("--text") + 1] == result["final_output"]


def test_gateway_task_integration_routes_status_query_to_status(tmp_path):
    gw = _make_gateway(tmp_path)
    calls = []
    task_id = "task-20260726-092433-wire-owner-engine---task-lifecycle-into"
    result = gw.route_and_dispatch(
        f"what is the status of {task_id}", session_id="test-session-2",
        runner=_fake_runner(calls),
    )
    dispatch = result["lifecycle_dispatch"]
    assert dispatch["action"] == "status"
    assert dispatch["task_id"] == task_id
    assert len(calls) == 1
    cmd = calls[0]
    assert cmd[2] == "status"
    assert cmd[cmd.index("--task-id") + 1] == task_id


def test_gateway_task_integration_routes_full_spec_to_submit_then_start(tmp_path):
    gw = _make_gateway(tmp_path)
    calls = []
    result = gw.route_and_dispatch(
        FULL_SPEC_TEXT, session_id="test-session-3", runner=_fake_runner(calls),
    )
    dispatch = result["lifecycle_dispatch"]
    assert dispatch["action"] == "start"
    assert len(calls) == 2, calls
    submit_cmd, start_cmd = calls
    assert submit_cmd[2] == "submit"
    assert start_cmd[2] == "start"
    assert start_cmd[start_cmd.index("--instruction-id") + 1] == "INS-FAKE-TEST-1"
    assert start_cmd[start_cmd.index("--repo") + 1] == "claude-control"
    title = start_cmd[start_cmd.index("--title") + 1]
    assert "gratuity" in title.lower()
    # The staged prompt-file is real (task-gateway.py's cmd_start requires a
    # readable --prompt-file path) but transient -- removed once the
    # (fake, in this test) start invocation has run.
    prompt_file = start_cmd[start_cmd.index("--prompt-file") + 1]
    assert not os.path.exists(prompt_file)


def test_gateway_task_integration_non_lifecycle_message_is_not_dispatched(tmp_path):
    gw = _make_gateway(tmp_path)
    calls = []
    result = gw.route_and_dispatch(
        "Hello, thanks for your help!", session_id="test-session-4",
        runner=_fake_runner(calls),
    )
    assert result["lifecycle_dispatch"]["action"] == "none"
    assert calls == []


def test_owner_engine_task_dispatch_route_decision_prefers_status_over_task_category():
    # "check the status of task-..." also scores real TASK-category keywords
    # ("check", "status") -- must still route to status, not submit, for an
    # EXISTING task_id (never misroute a lookup as a new dispatch).
    entities = [{"type": "TASK_ID", "value": "task-20260101-000000-example"}]
    route = gateway.determine_lifecycle_route(
        "TASK", entities, "check the status of task-20260101-000000-example",
    )
    assert route == {"action": "status", "task_id": "task-20260101-000000-example"}


# =============================================================================
# task-20260726-101257 SCOPE item 1: the mandatory clarification gate
# (query.py's NEEDS_OWNER_CLARIFICATION) must actually block dispatch for an
# ambiguous Owner message, not just exist unused.
# =============================================================================
def test_gateway_task_integration_ambiguous_message_triggers_clarification_not_dispatch(tmp_path):
    gw = _make_gateway(tmp_path)
    calls = []
    # Classifies TASK (weak keyword match) with confidence well below
    # query.py's LOW_CONFIDENCE_THRESHOLD (0.15) and UNKNOWN intent (no verb
    # matches any intent pattern) -- both step_3 "software could not tell"
    # signals at once. Absent the gate this would have routed straight to
    # submit (category TASK, no existing task_id).
    result = gw.route_and_dispatch(
        "deadline priority", session_id="test-session-ambiguous",
        runner=_fake_runner(calls),
    )
    dispatch = result["lifecycle_dispatch"]
    assert dispatch["action"] == "clarification_needed"
    answer = dispatch["clarification"]["answer"]
    assert answer["needs_owner_clarification"] is True
    assert "LOW_CLASSIFICATION_CONFIDENCE" in answer["reasons"]
    assert "INTENT_UNKNOWN" in answer["reasons"]
    # task-gateway.py must never be invoked at all when clarification is needed.
    assert calls == []


def test_gateway_task_integration_confident_task_message_still_dispatches(tmp_path):
    # Regression guard for the gate itself: a message clear enough that
    # NEEDS_OWNER_CLARIFICATION says false must still reach dispatch exactly
    # as before -- the gate must not become a blanket block.
    gw = _make_gateway(tmp_path)
    calls = []
    result = gw.route_and_dispatch(
        "Create a task to review the deployment PR before Friday",
        session_id="test-session-confident", runner=_fake_runner(calls),
    )
    assert result["lifecycle_dispatch"]["action"] == "submit"
    assert len(calls) == 1


def test_gateway_task_integration_document_mode_spec_not_forced_into_clarification(tmp_path):
    # Document-mode chat records (any full literal_template spec, like
    # FULL_SPEC_TEXT below, triggers gateway.py's _process_document_chat)
    # save classification.confidence=None, not a float -- query.py must
    # treat that as "not applicable", never as "low confidence", or every
    # real full-spec `start` dispatch would be wrongly blocked (and, before
    # the None-guard fix, `None < 0.15` would raise TypeError outright).
    gw = _make_gateway(tmp_path)
    calls = []
    result = gw.route_and_dispatch(
        FULL_SPEC_TEXT, session_id="test-session-doc-mode", runner=_fake_runner(calls),
    )
    assert result["classification"]["confidence"] is None
    assert result["lifecycle_dispatch"]["action"] == "start"


# =============================================================================
# task-20260726-101257 SCOPE item 2: `start` must never auto-fire when
# submit's own response already reports duplicate_found: true.
# =============================================================================
def _fake_runner_with_duplicate(calls):
    def runner(cmd, input_text=None):
        calls.append(cmd)
        if len(cmd) > 2 and cmd[2] == "submit":
            parsed = {
                "instruction_id": "INS-FAKE-DUP-1",
                "duplicate_found": True,
                "duplicate_evidence": [{"task_id": "task-existing-duplicate", "score": 0.9}],
            }
            return {
                "command": cmd, "returncode": 0,
                "stdout": json.dumps(parsed), "stderr": "", "parsed": parsed,
            }
        return {"command": cmd, "returncode": 0, "stdout": "{}", "stderr": "", "parsed": {}}
    return runner


def test_gateway_task_integration_duplicate_found_blocks_auto_start(tmp_path):
    gw = _make_gateway(tmp_path)
    calls = []
    result = gw.route_and_dispatch(
        FULL_SPEC_TEXT, session_id="test-session-dup",
        runner=_fake_runner_with_duplicate(calls),
    )
    dispatch = result["lifecycle_dispatch"]
    assert dispatch["action"] == "start"
    assert dispatch["result"] is None
    assert dispatch["start_skipped_reason"] == (
        "submit reported duplicate_found=true -- surfacing for human/AI review "
        "instead of auto-starting a possibly-duplicate task"
    )
    assert dispatch["duplicate_evidence"] == [{"task_id": "task-existing-duplicate", "score": 0.9}]
    # Exactly one call -- submit. `start` must NEVER be invoked when
    # duplicate_found is true.
    assert len(calls) == 1
    assert calls[0][2] == "submit"


# =============================================================================
# task-20260726-101257 SCOPE item 3: repo_override is the real checkpoint --
# it must actually take precedence over _derive_repo_from_spec()'s guess.
# =============================================================================
def test_gateway_task_integration_repo_override_takes_precedence_over_guess(tmp_path):
    gw = _make_gateway(tmp_path)
    calls = []
    result = gw.route_and_dispatch(
        FULL_SPEC_TEXT, session_id="test-session-repo-override",
        runner=_fake_runner(calls), repo_override="compliance-tracker",
    )
    assert result["lifecycle_dispatch"]["action"] == "start"
    assert result["lifecycle_dispatch"]["derived_repo"] == "compliance-tracker"
    start_cmd = calls[1]
    assert start_cmd[start_cmd.index("--repo") + 1] == "compliance-tracker"


# =============================================================================
# task-20260726-101257 SCOPE item 4: credit-accountant.py's real, live
# argument parser and cmd_propose behavior -- not assumed, not mocked at the
# subprocess-argv level like the tests above. credit-accountant.py is a
# genuinely live-deployed-only file (deliberately excluded from this git
# repo, same convention as veridian-task.py -- see
# ai-os/OWNER_ENGINE_MANDATORY_GATE... sibling commits), so these tests skip
# cleanly wherever that live file isn't present (e.g. a fresh clone off this
# server) rather than failing.
# =============================================================================
CREDIT_ACCOUNTANT_PATH = "/opt/veridian/scripts/credit-accountant.py"


def _load_credit_accountant_module():
    spec = importlib.util.spec_from_file_location("credit_accountant_live", CREDIT_ACCOUNTANT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not os.path.exists(CREDIT_ACCOUNTANT_PATH),
                     reason="credit-accountant.py is live-deployed only, not present in this checkout")
def test_gateway_task_integration_credit_accountant_help_confirms_repo_flag():
    import subprocess
    proc = subprocess.run(
        ["python3", CREDIT_ACCOUNTANT_PATH, "propose", "--help"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "--repo" in proc.stdout


@pytest.mark.skipif(not os.path.exists(CREDIT_ACCOUNTANT_PATH),
                     reason="credit-accountant.py is live-deployed only, not present in this checkout")
def test_gateway_task_integration_credit_accountant_propose_registers_real_plan_with_repo(tmp_path, monkeypatch):
    ca = _load_credit_accountant_module()
    ledger_path = str(tmp_path / "test-credit-ledger.sqlite")
    monkeypatch.setattr(ca, "LEDGER_PATH", ledger_path)
    # Deterministic, zero-cost, zero-network stand-ins for the two checks
    # that would otherwise hit a real OpenRouter balance call and a real
    # (subscription) `claude -p` call -- this test verifies task-gateway.py's
    # own argv construction and cmd_propose's real DB-write/--repo-plumbing
    # behavior, not credit-accountant.py's judgment-call network path.
    monkeypatch.setattr(ca, "get_openrouter_remaining", lambda: None)
    monkeypatch.setattr(ca, "check_existing_capability", lambda terms: (False, None))
    captured = {}

    def fake_judgment_call(prompt_body):
        captured["prompt_body"] = prompt_body
        return "PASS", "test-approved, real progress"

    monkeypatch.setattr(ca, "claude_judgment_call", fake_judgment_call)

    args = types.SimpleNamespace(
        task_id="task-TEST-credit-accountant-verification-zzz",
        plan="Verify propose() genuinely registers a real ledger row.",
        search_terms="credit_accountant_test_zzz_unlikely_to_match",
        repo="claude-control",
    )
    with pytest.raises(SystemExit) as exc_info:
        ca.cmd_propose(args)
    assert exc_info.value.code == 0

    # --repo genuinely reaches cmd_propose's judgment-call prompt -- proves
    # the flag is not a silent no-op.
    assert "Repo: claude-control" in captured["prompt_body"]

    # cmd_propose's real state, not just its exit code: a row was actually
    # inserted into the (temp) ledger with the real plan/search_terms/verdict.
    conn = sqlite3.connect(ledger_path)
    row = conn.execute(
        "SELECT increment_number, plan_text, search_terms, plan_verdict "
        "FROM credit_increments WHERE task_id = ?",
        (args.task_id,),
    ).fetchone()
    conn.close()
    assert row == (1, args.plan, args.search_terms, "approved")
