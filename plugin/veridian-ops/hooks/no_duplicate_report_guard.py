#!/usr/bin/env python3
"""PreToolUse hook (matcher: Write) -- blocks recreating the RCA.md / STATUS_REPORT.md
shared-scratch anti-pattern that caused repeated PR collisions in claude-control (see
reports/incidents/RCA_20260813_UMR-20260813-060311-6eea.md and
reports/audits/STATUS_REPORT_20260814_part1-4-status.md for the history). Ships generically
to all VERIDIAN repos via the veridian-ops-plugin -- must not hardcode any repo-specific path.

Reads the PreToolUse JSON payload from stdin, extracts tool_input.file_path, and:
  - blocks (exit 2) if the basename is one of a fixed set of banned generic report names
  - blocks (exit 2) if the basename matches the dated TYPE_YYYYMMDD_ID[.md] convention with
    no suffix, and a file for the same TYPE+ID is already tracked in git (a second report for
    the same id requires an explicit _second_pass / _addendum / ... suffix)
  - otherwise exits 0
"""
import json
import os
import re
import subprocess
import sys

BANNED_GENERIC_NAMES = {
    "RCA.md",
    "STATUS_REPORT.md",
    "PROGRESS.md",
    "report.md",
    "summary.md",
    "notes.md",
    "output.md",
    "result.md",
}

# <TYPE>_<YYYYMMDD>_<STABLE-ID>[_<suffix>].md
NAME_RE = re.compile(
    r"^(?P<type>RCA|MERGE_REPORT|AUDIT|STATUS_REPORT)_(?P<date>\d{8})_(?P<id>[A-Za-z0-9\-]+)"
    r"(?P<suffix>_.+)?\.md$"
)


def resolve_start_dir(file_path):
    """Walk up from file_path's directory to the nearest directory that actually exists on
    disk, so this works even for a hypothetical/not-yet-created target path. Falls back to
    the hook process's own cwd (the repo containing the current session) if nothing along
    the way exists."""
    d = os.path.dirname(os.path.abspath(file_path))
    while d and not os.path.isdir(d):
        parent = os.path.dirname(d)
        if parent == d:
            d = ""
            break
        d = parent
    return d if d and os.path.isdir(d) else os.getcwd()


def find_repo_root(start_dir):
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


def existing_files_for_id(repo_root, file_type, stable_id):
    """Return tracked files (relative to repo_root) that already cover this TYPE+ID."""
    try:
        out = subprocess.run(
            ["git", "ls-files", f"*{file_type}_*{stable_id}*.md"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return []
    matches = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        base = os.path.basename(line)
        m = NAME_RE.match(base)
        if m and m.group("type") == file_type and m.group("id") == stable_id:
            matches.append(line)
    return matches


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # Unparseable input isn't this hook's problem to block on.
        return 0

    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        return 0

    basename = os.path.basename(file_path)

    if basename in BANNED_GENERIC_NAMES:
        sys.stderr.write(
            f"Blocked: '{basename}' is a banned generic report filename. It caused repeated "
            "PR collisions in this repo's history (shared-scratch filenames rewritten many "
            "times over -- RCA.md 7x, STATUS_REPORT.md 18x). Use "
            "reports/{incidents,merges,audits}/<TYPE>_<YYYYMMDD>_<id>.md instead -- see "
            "AGENTS.md 'Report filing rules'.\n"
        )
        return 2

    m = NAME_RE.match(basename)
    if not m:
        return 0

    if m.group("suffix"):
        # Explicit suffix (e.g. _second_pass, _addendum) is exactly how a second report for
        # an already-covered id is permitted -- nothing to block.
        return 0

    file_type = m.group("type")
    stable_id = m.group("id")

    start_dir = resolve_start_dir(file_path)
    repo_root = find_repo_root(start_dir)
    if not repo_root:
        # Can't determine a repo root (not inside a git repo) -- nothing to check against.
        return 0

    try:
        rel_new_path = os.path.relpath(os.path.abspath(file_path), repo_root)
    except ValueError:
        rel_new_path = None

    existing = [e for e in existing_files_for_id(repo_root, file_type, stable_id) if e != rel_new_path]

    if existing:
        sys.stderr.write(
            f"Blocked: a {file_type} report for id '{stable_id}' already exists at "
            f"{existing[0]} (tracked in git). A second report for the same id requires an "
            "explicit suffix, e.g. "
            f"{file_type}_{m.group('date')}_{stable_id}_second_pass.md or _addendum.md -- "
            f"update {existing[0]} directly, or add a suffix if this is genuinely a distinct "
            "follow-up pass.\n"
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
