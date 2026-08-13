#!/usr/bin/env python3
"""Real tests for UMR-20260813-042708-e592 (governing chain
UMR-20260806-171945-5767, sibling UMR-20260813-042145-7cc0): the real,
confirmed gap this closes -- task-gateway.py's cmd_start spawned a real
systemd unit synchronously with ZERO reference anywhere in this file to
resource_governor.py/dispatch_one/stop_work, while dispatch-owner-task.sh's
OTHER real channel (resource_governor.py's submit()/dispatch_one()) already
got the real standing-stop-work-order + resource-threshold gate. Wired via
run_task_start_gate(), which calls resource_governor.py --check-task-start-
gate as a real subprocess (RESOURCE_GOVERNOR = f"{SCRIPTS}/resource_governor.py",
SCRIPTS derived from task-gateway.py's own hardcoded VERIDIAN_ROOT =
"/opt/veridian" -- the same real, live, already-deployed resource_governor.py
every other real production caller of this file resolves to, not a repo-local
copy), so there is exactly one enforced stop-work check regardless of which
entrypoint started the work.

test_cmd_start_is_blocked_while_a_real_stop_work_order_is_active is the load-
bearing test here: it calls task-gateway.py's real cmd_start() (not a stub of
it) with a real, isolated OWNER_DECISIONS_NEEDED yaml (a real `git init` repo,
same "real, not mocked" convention as /opt/veridian/scripts/tests/
test_stop_work_order_gate.py and test_task_start_gate.py, which this file
otherwise mirrors) that has NO real, committed, approved lift/exemption entry
for the standing order -- proving a real cmd_start call is genuinely blocked
before it ever reaches veridian-task.py create (which would spend a real
worktree/branch/systemd unit), the same real protection
resource_governor.py's own dispatch_one()/submit() path already gets.
"""
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
TASK_GATEWAY_PATH = os.path.join(SCRIPTS_DIR, "task-gateway.py")
# The real, live, already-deployed resource_governor.py -- the exact one
# task-gateway.py's own RESOURCE_GOVERNOR constant resolves to at runtime
# (VERIDIAN_ROOT is hardcoded "/opt/veridian" in task-gateway.py, not env-
# overridable), so this is what actually enforces the gate in production.
LIVE_RESOURCE_GOVERNOR = "/opt/veridian/scripts/resource_governor.py"

pytestmark = pytest.mark.skipif(
    not os.path.isfile(LIVE_RESOURCE_GOVERNOR),
    reason="live resource_governor.py not present on this host -- cannot prove "
           "the real gate without it (a stub would only prove this file's own "
           "plumbing, not that the standing stop-work order actually blocks)",
)


def _load_tg(name):
    spec = importlib.util.spec_from_file_location(name, TASK_GATEWAY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(repo_dir, *args):
    return subprocess.run(["git", "-C", repo_dir, *args], capture_output=True, text=True, check=True)


def _init_owner_decisions_repo(tmp_dir, entries_yaml_text):
    """A real, isolated `git init` repo standing in for OWNER_DECISIONS_PATH
    -- same convention as /opt/veridian/scripts/tests/test_task_start_gate.py,
    so a real, git-committed check runs against a real repo, never the live
    production one."""
    repo_dir = os.path.join(tmp_dir, "owner_decisions_repo")
    os.makedirs(repo_dir, exist_ok=True)
    subprocess.run(["git", "init", repo_dir], capture_output=True, text=True, check=True)
    _git(repo_dir, "config", "user.email", "test@example.com")
    _git(repo_dir, "config", "user.name", "Test")
    path = os.path.join(repo_dir, "OWNER_DECISIONS_NEEDED_2026-07-23.yaml")
    with open(path, "w") as f:
        f.write(entries_yaml_text)
    _git(repo_dir, "add", "OWNER_DECISIONS_NEEDED_2026-07-23.yaml")
    _git(repo_dir, "commit", "-m", "real committed owner-decisions entry")
    return path


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
Never produced -- the stop-work-order gate must block cmd_start first.
## CONSTRAINTS
None.
## COMPLEXITY_TIER
mechanical
"""


def _build_cmd_start_env(tmp_path, tg, monkeypatch):
    """Stubs every wrapped script cmd_start calls BEFORE the new gate
    (SUPERBOSS claim-task-key, tight_task_validation.py, ddl_authorization_
    check.py) so a real cmd_start() call reaches run_task_start_gate() for
    real, and stubs veridian-task.py (the real spawn, past the gate) so a
    test that expects to pass the gate never performs a real dispatch
    either. Deliberately does NOT touch tg.RESOURCE_GOVERNOR -- that stays
    pointed at the real, live resource_governor.py."""
    stub_superboss = tmp_path / "stub_superboss.py"
    _write_executable(stub_superboss, "#!/usr/bin/env python3\n"
                       "import json\nprint(json.dumps({'claimed': True, 'instruction_id': 'INS-TEST-1'}))\n")
    stub_tight = tmp_path / "stub_tight_validation.py"
    _write_executable(stub_tight, "#!/usr/bin/env python3\n"
                       "import json\nprint(json.dumps({'valid': True, 'holdForOwnerSignoff': False}))\n")
    stub_ddl = tmp_path / "stub_ddl_check.py"
    _write_executable(stub_ddl, "#!/usr/bin/env python3\n"
                       "import json\nprint(json.dumps({'valid': True}))\n")
    veridian_task_calls = tmp_path / "veridian_task_calls.log"
    stub_veridian_task = tmp_path / "stub_veridian_task.py"
    _write_executable(stub_veridian_task, f"""#!/usr/bin/env python3
import sys
with open({str(veridian_task_calls)!r}, "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\\n")
print("CREATED: task-mock-0001")
""")
    monkeypatch.setattr(tg, "SUPERBOSS", str(stub_superboss))
    monkeypatch.setattr(tg, "TIGHT_VALIDATION", str(stub_tight))
    monkeypatch.setattr(tg, "DDL_AUTHORIZATION_CHECK", str(stub_ddl))
    monkeypatch.setattr(tg, "VERIDIAN_TASK", str(stub_veridian_task))
    return veridian_task_calls


def _isolated_stop_work_env(monkeypatch, owner_decisions_path):
    """Isolates the real live resource_governor.py's stop-work-order check
    from this host's real, current production state -- same env-var
    convention that module's own tests already use (VERIDIAN_OWNER_
    DECISIONS_PATH, VERIDIAN_GOVERNOR_STOP_WORK_TRUNK_REF=HEAD so the check
    reads the just-created local repo's own HEAD, never a real origin
    fetch). Metric threshold and emergency-stop are pushed out of the way so
    only the stop-work-order check can possibly block -- this test proves
    THAT check specifically, not an incidental host-load false positive."""
    monkeypatch.setenv("VERIDIAN_OWNER_DECISIONS_PATH", owner_decisions_path)
    monkeypatch.setenv("VERIDIAN_GOVERNOR_STOP_WORK_TRUNK_REF", "HEAD")
    monkeypatch.setenv("VERIDIAN_GOVERNOR_EMERGENCY_STOP", "/nonexistent/EMERGENCY_STOP_never_created")
    monkeypatch.setenv("VERIDIAN_GOVERNOR_METRIC_THRESHOLD", "100000")


def test_cmd_start_currently_has_zero_stop_work_references_would_have_been_caught(monkeypatch):
    """Documents the real, confirmed gap this closes, verified fresh (not
    from stale memory) against source: before this fix, grepping cmd_start's
    own source for resource_governor/dispatch_one/stop_work found nothing.
    Guards against a future regression silently removing the wiring this
    test suite otherwise only exercises behaviorally."""
    import inspect
    tg = _load_tg("tg_source_check")
    src = inspect.getsource(tg.cmd_start)
    assert "run_task_start_gate" in src, (
        "cmd_start no longer calls the shared stop-work-order gate -- this is "
        "exactly the UMR-20260813-042708-e592 bypass reappearing"
    )


def test_cmd_start_is_blocked_while_a_real_stop_work_order_is_active(tmp_path, monkeypatch, capsys):
    """The load-bearing test: a real cmd_start() call, with a real, isolated
    OWNER_DECISIONS_PATH containing no lift/exemption entry for the standing
    order, must be blocked by the real live resource_governor.py -- same
    real protection resource_governor.py's own submit()/dispatch_one() path
    already gets -- and must NEVER reach veridian-task.py create (no real
    worktree/branch/systemd unit spent)."""
    owner_decisions_path = _init_owner_decisions_repo(str(tmp_path), "[]\n")
    _isolated_stop_work_env(monkeypatch, owner_decisions_path)

    tg = _load_tg("tg_blocked")
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
    assert out["check"] == "stop_work_order"
    assert "BLOCKED by standing stop-work order" in out["detail"]
    assert "stop-work-order" in out["error"]

    assert not veridian_task_calls.exists(), (
        "veridian-task.py create was invoked despite the stop-work-order block -- "
        "a real worktree/branch/systemd unit would have been spent"
    )


def test_cmd_start_proceeds_past_the_gate_once_a_real_lift_entry_is_committed(tmp_path, monkeypatch):
    """Symmetry check: the same real live resource_governor.py, given a real,
    committed, approved 'owner-absolute-stop-work-order-lifted' entry naming
    the standing order (same real exemption channel _stop_work_order_
    block_reason() itself documents), must let cmd_start proceed to the real
    spawn step -- proving the gate is a real pass/fail check, not something
    that blocks unconditionally."""
    # The real standing order id resource_governor.py ships as its own
    # default (VERIDIAN_GOVERNOR_STOP_WORK_ORDER_TASK_IDS unset).
    order_id = "task-20260806-165921-owner-absolute-stop-work-order--complete"
    lift_yaml = (
        "- id: owner-absolute-stop-work-order-lifted-test\n"
        "  status: approved\n"
        f"  what: \"{order_id} lifted for this real test\"\n"
    )
    owner_decisions_path = _init_owner_decisions_repo(str(tmp_path), lift_yaml)
    _isolated_stop_work_env(monkeypatch, owner_decisions_path)

    tg = _load_tg("tg_clear")
    veridian_task_calls = _build_cmd_start_env(tmp_path, tg, monkeypatch)

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text(FULL_SPEC_TEXT)

    args = argparse_namespace(
        prompt_file=str(prompt_file), title="stop work gate real test task clear",
        repo="claude-control", instruction_id="INS-TEST-1",
    )

    tg.cmd_start(args)  # must NOT raise SystemExit

    assert veridian_task_calls.exists(), (
        "veridian-task.py create was never invoked even though the stop-work "
        "order was really lifted -- the gate must not block unconditionally"
    )


def argparse_namespace(**kwargs):
    import argparse
    return argparse.Namespace(**kwargs)


# ---------------------------------------------------------------------------
# run_task_start_gate() -- unit tests against a stub resource_governor.py,
# isolated from the real one's own checks (those are covered for real above).
# ---------------------------------------------------------------------------

_STUB_GOVERNOR_TEMPLATE = """
import json
print(json.dumps(%r))
"""


def test_run_task_start_gate_returns_parsed_result_when_clear(tmp_path, monkeypatch):
    stub = tmp_path / "stub_rg_clear.py"
    _write_executable(stub, _STUB_GOVERNOR_TEMPLATE % {"blocked": False, "check": None, "detail": None})
    tg = _load_tg("tg_gate_unit_1")
    monkeypatch.setattr(tg, "RESOURCE_GOVERNOR", str(stub))
    result = tg.run_task_start_gate("task-key-1", "some title")
    assert result == {"blocked": False, "check": None, "detail": None}


def test_run_task_start_gate_returns_parsed_result_when_blocked(tmp_path, monkeypatch):
    stub = tmp_path / "stub_rg_blocked.py"
    _write_executable(stub, _STUB_GOVERNOR_TEMPLATE % {
        "blocked": True, "check": "stop_work_order", "detail": "real block reason text",
    })
    tg = _load_tg("tg_gate_unit_2")
    monkeypatch.setattr(tg, "RESOURCE_GOVERNOR", str(stub))
    result = tg.run_task_start_gate("task-key-2", "some title")
    assert result["blocked"] is True
    assert result["check"] == "stop_work_order"
    assert result["detail"] == "real block reason text"


def test_run_task_start_gate_passes_task_kind_veridian_task_create(tmp_path, monkeypatch):
    """cmd_start's only real task_kind -- confirms run_task_start_gate() never
    silently omits --task-kind (which would make _stop_work_order_block_reason()
    skip the check entirely, since it only applies to 'veridian_task_create')."""
    stub = tmp_path / "stub_rg_argv.py"
    _write_executable(stub, "#!/usr/bin/env python3\n"
                       "import json, sys\nprint(json.dumps({'blocked': False, 'check': None, "
                       "'detail': None, 'argv': sys.argv[1:]}))\n")
    tg = _load_tg("tg_gate_unit_3")
    monkeypatch.setattr(tg, "RESOURCE_GOVERNOR", str(stub))
    result = tg.run_task_start_gate("task-key-3", "some title")
    assert "--task-kind" in result["argv"]
    assert "veridian_task_create" in result["argv"]
