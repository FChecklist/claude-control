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
import json
import os
import sys

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
