#!/usr/bin/env python3
"""Stop hook -- runs the current repo's verify-config (typecheck/test commands) before
letting the agent stop, and blocks the stop if either command fails.

Ships generically to all VERIDIAN repos via the veridian-ops-plugin. Populating any repo's
.claude/verify-config.json is an explicit follow-up, NOT part of this hook -- no
typecheck/test command has been confirmed to actually work in any of the six VERIDIAN repos
as of 2026-08-18, so this hook must degrade to a no-op when the config is absent rather than
inventing or guessing a command.

Reads the Stop hook JSON payload from stdin. Looks for .claude/verify-config.json at the repo
root (found via `git rev-parse --show-toplevel` from the payload's `cwd`), schema:
    {"typecheck": "<cmd-or-null>", "test": "<cmd-or-null>"}

- Config missing -> print an informational note to stderr, exit 0 (never blocks with no
  config).
- Any present (non-null) command that fails -> if the payload's stop_hook_active is already
  true, exit 0 without blocking again (avoids an infinite retry loop); otherwise print
  {"decision": "block", "reason": "<last ~50 lines of the failing command's combined
  output>"} as JSON to stdout and exit 0, per the documented Stop-hook JSON decision
  mechanism.
- All present commands pass -> exit 0, no output.
"""
import json
import os
import subprocess
import sys

TAIL_LINES = 50


def find_repo_root(cwd):
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd or os.getcwd(),
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


def tail(text, n=TAIL_LINES):
    lines = text.splitlines()
    return "\n".join(lines[-n:])


def run_command(cmd, cwd):
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except Exception as e:
        return 1, f"failed to run command '{cmd}': {e}"
    if proc.returncode == 0:
        return 0, ""
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return proc.returncode, tail(combined)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    repo_root = find_repo_root(cwd)
    if not repo_root:
        sys.stderr.write("verify_gate: not inside a git repo, skipping gate.\n")
        return 0

    config_path = os.path.join(repo_root, ".claude", "verify-config.json")
    if not os.path.isfile(config_path):
        sys.stderr.write(
            f"verify_gate: no verify-config found for this repo ({config_path}), skipping gate.\n"
        )
        return 0

    try:
        with open(config_path) as f:
            config = json.load(f)
    except Exception as e:
        sys.stderr.write(f"verify_gate: could not parse {config_path} ({e}), skipping gate.\n")
        return 0

    failures = []
    for step in ("typecheck", "test"):
        cmd = config.get(step)
        if not cmd:
            continue
        rc, output = run_command(cmd, repo_root)
        if rc != 0:
            failures.append((step, cmd, output))

    if not failures:
        return 0

    if payload.get("stop_hook_active"):
        # Already retried once for this stop -- don't loop forever.
        sys.stderr.write(
            "verify_gate: verification still failing after a retry; not blocking again "
            "(stop_hook_active).\n"
        )
        return 0

    reason_parts = [
        f"[{step}] `{cmd}` failed:\n{output}" for step, cmd, output in failures
    ]
    reason = "\n\n".join(reason_parts)
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
