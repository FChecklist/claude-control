#!/usr/bin/env python3
"""Real tests for UMR-20260813-042708-e592 (governing chain
UMR-20260806-171945-5767): the real, confirmed gap this closes --
task-gateway.py's cmd_start spawned a real systemd unit synchronously with
ZERO reference anywhere in this file to resource_governor.py/dispatch_one,
while resource_governor.py's own dispatch_one() already gates every queued
row behind its real EMERGENCY_STOP-sentinel + 4-metric-threshold "stop work"
check. Wired via run_task_start_gate(), which calls the real
resource_governor.py --check-task-start-gate subprocess (same absolute-path
composition convention this file already uses for SUPERBOSS/TIGHT_VALIDATION/
DDL_AUTHORIZATION_CHECK/CREDIT_ACCOUNTANT), so there is exactly one enforced
stop-work check regardless of whether a task is queued through
resource_governor.py's own submit()/dispatch_one() or started directly via
this file's cmd_start.

test_cmd_start_is_blocked_while_the_real_stop_work_gate_is_active is the
load-bearing test: it calls task-gateway.py's real cmd_start() (not a stub of
it) against the REAL resource_governor.py (only its own downstream I/O --
/proc reads, dispatch_core's superboss-register.py DB -- is redirected into a
throwaway fixture tree, never resource_threshold_block_reason() itself),
with a real EMERGENCY_STOP sentinel file present, and proves cmd_start is
genuinely blocked before it ever reaches veridian-task.py create (which would
spend a real worktree/branch/systemd unit) -- the same real protection
resource_governor.py's own dispatch_one() already applies to every queued
row.
"""
import importlib.util
import json
import os
import stat
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
TASK_GATEWAY_PATH = os.path.join(SCRIPTS_DIR, "task-gateway.py")
RESOURCE_GOVERNOR_PATH = os.path.join(SCRIPTS_DIR, "resource_governor.py")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _resource_governor_fixtures import build_governor_fixture_tree  # noqa: E402


def _load_tg(name):
    spec = importlib.util.spec_from_file_location(name, TASK_GATEWAY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_executable(path, content):
    with open(path, "w") as f:
        f.write(content)
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


FULL_SPEC_TEXT = """## OBJECTIVE
Real test task -- never actually dispatched, the gate must block first.
## SCOPE
Only this test's own throwaway files.
## KNOWN_CONTEXT
Test fixture for UMR-20260813-042708-e592.
## SUCCESS_CRITERIA
n/a -- this task is never expected to reach veridian-task.py create.
## EXPECTED_OUTPUT
Never produced -- the stop-work gate must block cmd_start first.
## CONSTRAINTS
None.
## COMPLEXITY_TIER
mechanical
"""


def _build_cmd_start_env(tmp_path, tg, monkeypatch):
    """Stubs every wrapped script cmd_start calls BEFORE the new gate
    (SUPERBOSS claim-task-key, tight_task_validation.py,
    ddl_authorization_check.py) so a real cmd_start() call reaches
    run_task_start_gate() for real, and stubs everything AFTER the gate
    (veridian-task.py create, credit-accountant.py propose, SUPERBOSS
    log-work) so a test that expects to pass the gate never performs a real
    dispatch either. Deliberately does NOT touch tg.RESOURCE_GOVERNOR -- the
    real resource_governor.py stays wired, only its own downstream
    dependencies get redirected via env (see _isolated_governor_env)."""
    stub_superboss = tmp_path / "stub_superboss.py"
    _write_executable(stub_superboss, """#!/usr/bin/env python3
import json, sys
if "claim-task-key" in sys.argv:
    print(json.dumps({"claimed": True}))
elif "log-work" in sys.argv:
    print(json.dumps({"work_item_id": "WI-TEST-1"}))
else:
    print(json.dumps({}))
""")
    stub_tight = tmp_path / "stub_tight_validation.py"
    _write_executable(stub_tight, "#!/usr/bin/env python3\n"
                       "import json\nprint(json.dumps({'valid': True, 'holdForOwnerSignoff': False}))\n")
    stub_ddl = tmp_path / "stub_ddl_check.py"
    _write_executable(stub_ddl, "#!/usr/bin/env python3\n"
                       "import json\nprint(json.dumps({'valid': True}))\n")
    stub_credit_accountant = tmp_path / "stub_credit_accountant.py"
    _write_executable(stub_credit_accountant, "#!/usr/bin/env python3\n"
                       "import json\nprint(json.dumps({'approved': True, 'reason': 'stub'}))\n")
    veridian_task_calls = tmp_path / "veridian_task_calls.log"
    stub_veridian_task = tmp_path / "stub_veridian_task.py"
    _write_executable(stub_veridian_task, f"""#!/usr/bin/env python3
import sys
with open({str(veridian_task_calls)!r}, "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\\n")
print("CREATED: task-mock-0001")
""")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    _write_executable(bin_dir / "systemctl", "#!/bin/bash\n"
                       "if [[ \"$*\" == *is-active* ]]; then echo inactive; exit 3; fi\n"
                       "exit 0\n")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    monkeypatch.setattr(tg, "SUPERBOSS", str(stub_superboss))
    monkeypatch.setattr(tg, "TIGHT_VALIDATION", str(stub_tight))
    monkeypatch.setattr(tg, "DDL_AUTHORIZATION_CHECK", str(stub_ddl))
    monkeypatch.setattr(tg, "VERIDIAN_TASK", str(stub_veridian_task))
    monkeypatch.setattr(tg, "CREDIT_ACCOUNTANT", str(stub_credit_accountant))
    return veridian_task_calls


def _isolated_governor_env(monkeypatch, tmp_path):
    """Isolates the real resource_governor.py's OWN downstream I/O (the
    EMERGENCY_STOP sentinel path, /proc reads it would otherwise need to
    parse for real) into a throwaway fixture tree -- resource_threshold_
    block_reason() itself (the real gate logic under test) is never
    stubbed."""
    work, env = build_governor_fixture_tree(tmp_path / "governor_fixture")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    # sample_metrics() must never spuriously block this test on real host
    # load -- only the EMERGENCY_STOP sentinel is under test here.
    monkeypatch.setenv("VERIDIAN_GOVERNOR_METRIC_THRESHOLD", "1000000")
    return work, env


def argparse_namespace(**kwargs):
    import argparse
    return argparse.Namespace(**kwargs)


def test_cmd_start_currently_calls_the_shared_stop_work_gate():
    """Documents the real, confirmed gap this closes, verified fresh (not
    from stale memory) against source. Guards against a future regression
    silently removing the wiring this test suite otherwise only exercises
    behaviorally."""
    import inspect
    tg = _load_tg("tg_source_check")
    src = inspect.getsource(tg.cmd_start)
    assert "run_task_start_gate" in src, (
        "cmd_start no longer calls the shared stop-work gate -- this is "
        "exactly the UMR-20260813-042708-e592 bypass reappearing"
    )


def test_cmd_start_is_blocked_while_the_real_stop_work_gate_is_active(tmp_path, monkeypatch, capsys):
    """The load-bearing test: a real cmd_start() call, with a real
    EMERGENCY_STOP sentinel present (resource_governor.py's own real "stop
    work" mechanism -- see resource_threshold_block_reason()'s docstring),
    must be blocked by the real resource_governor.py subprocess -- same real
    protection resource_governor.py's own dispatch_one() path already gets
    -- and must NEVER reach veridian-task.py create (no real
    worktree/branch/systemd unit spent)."""
    work, env = _isolated_governor_env(monkeypatch, tmp_path)
    spec = importlib.util.spec_from_file_location(
        "rg_for_sentinel", str(work / "scripts" / "resource_governor.py"))
    rg = importlib.util.module_from_spec(spec)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    spec.loader.exec_module(rg)
    rg._save_json(rg.EMERGENCY_STOP_PATH, {"ts": "test", "state": {}})

    tg = _load_tg("tg_blocked")
    monkeypatch.setattr(tg, "RESOURCE_GOVERNOR", str(work / "scripts" / "resource_governor.py"))
    veridian_task_calls = _build_cmd_start_env(tmp_path, tg, monkeypatch)

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text(FULL_SPEC_TEXT)

    args = argparse_namespace(
        prompt_file=str(prompt_file), title="stop work gate real test task",
        repo="claude-control", instruction_id="INS-TEST-1",
    )

    with pytest.raises(SystemExit) as exc_info:
        tg.cmd_start(args)
    assert exc_info.value.code == 1

    out = json.loads(capsys.readouterr().out)
    assert "EMERGENCY_STOP" in out["detail"]
    assert "stop-work" in out["error"] or "stop_work" in out["error"]

    assert not veridian_task_calls.exists(), (
        "veridian-task.py create was invoked despite the real stop-work gate blocking -- "
        "a real worktree/branch/systemd unit would have been spent"
    )


def test_cmd_start_proceeds_past_the_gate_when_the_real_gate_is_clear(tmp_path, monkeypatch):
    """Symmetry check: the same real resource_governor.py subprocess, with no
    EMERGENCY_STOP sentinel and metrics under threshold, must let cmd_start
    proceed to the real spawn step -- proving the gate is a real pass/fail
    check, not something that blocks unconditionally."""
    _isolated_governor_env(monkeypatch, tmp_path)

    tg = _load_tg("tg_clear")
    monkeypatch.setattr(tg, "RESOURCE_GOVERNOR", RESOURCE_GOVERNOR_PATH)
    veridian_task_calls = _build_cmd_start_env(tmp_path, tg, monkeypatch)

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text(FULL_SPEC_TEXT)

    args = argparse_namespace(
        prompt_file=str(prompt_file), title="stop work gate real test task clear",
        repo="claude-control", instruction_id="INS-TEST-1",
    )

    tg.cmd_start(args)  # must NOT raise SystemExit

    assert veridian_task_calls.exists(), (
        "veridian-task.py create was never invoked even though the real gate was clear -- "
        "the gate must not block unconditionally"
    )


# ---------------------------------------------------------------------------
# run_task_start_gate() -- unit tests against a stub resource_governor.py,
# isolated from the real one's own checks (those are covered for real above).
# ---------------------------------------------------------------------------

_STUB_GOVERNOR_TEMPLATE = """#!/usr/bin/env python3
import json
print(json.dumps(%r))
"""


def test_run_task_start_gate_returns_parsed_result_when_clear(tmp_path, monkeypatch):
    stub = tmp_path / "stub_rg_clear.py"
    _write_executable(stub, _STUB_GOVERNOR_TEMPLATE % {"blocked": False, "detail": None, "metrics": {}})
    tg = _load_tg("tg_gate_unit_1")
    monkeypatch.setattr(tg, "RESOURCE_GOVERNOR", str(stub))
    result = tg.run_task_start_gate("task-key-1", "some title")
    assert result == {"blocked": False, "detail": None, "metrics": {}}


def test_run_task_start_gate_returns_parsed_result_when_blocked(tmp_path, monkeypatch):
    stub = tmp_path / "stub_rg_blocked.py"
    _write_executable(stub, _STUB_GOVERNOR_TEMPLATE % {
        "blocked": True, "detail": "real block reason text", "metrics": None,
    })
    tg = _load_tg("tg_gate_unit_2")
    monkeypatch.setattr(tg, "RESOURCE_GOVERNOR", str(stub))
    result = tg.run_task_start_gate("task-key-2", "some title")
    assert result["blocked"] is True
    assert result["detail"] == "real block reason text"


def test_run_task_start_gate_passes_task_identity_and_title(tmp_path, monkeypatch):
    """Confirms run_task_start_gate() forwards the real task_key/title argv,
    not silently omitted or swapped."""
    stub = tmp_path / "stub_rg_argv.py"
    _write_executable(stub, "#!/usr/bin/env python3\n"
                       "import json, sys\nprint(json.dumps({'blocked': False, 'detail': None, "
                       "'metrics': None, 'argv': sys.argv[1:]}))\n")
    tg = _load_tg("tg_gate_unit_3")
    monkeypatch.setattr(tg, "RESOURCE_GOVERNOR", str(stub))
    result = tg.run_task_start_gate("task-key-3", "some title")
    assert "--task-identity" in result["argv"]
    assert "task-key-3" in result["argv"]
    assert "--title" in result["argv"]
    assert "some title" in result["argv"]


def test_run_task_start_gate_fails_loudly_on_a_broken_governor(tmp_path, monkeypatch):
    """A broken/unavailable resource_governor.py must be a real wrapper-level
    failure (via fail() -> sys.exit(1)), never silently skipped -- matching
    every other real wrapper call in this file (run_json's own docstring)."""
    stub = tmp_path / "stub_rg_broken.py"
    _write_executable(stub, "#!/usr/bin/env python3\nimport sys\nsys.exit(1)\n")
    tg = _load_tg("tg_gate_unit_4")
    monkeypatch.setattr(tg, "RESOURCE_GOVERNOR", str(stub))
    with pytest.raises(SystemExit) as exc_info:
        tg.run_task_start_gate("task-key-4", "some title")
    assert exc_info.value.code == 1
