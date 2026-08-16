#!/usr/bin/env python3
"""Real, mechanical completion gate for claude-control's own worker-entrypoint.sh.

REAL DEFECT (task-20260814-054242, governing chain UMR-20260813-195922-f548):
a prior task on this repo (commit 1d97759, "RCA + real fix for
UMR-20260813-195922-f548") diagnosed exactly this problem -- a task whose
objective names a source file but whose diff touches no code still got
routed to pending_review/completed as if it were real work -- and shipped a
REAL fix for it, but only in a DIFFERENT repository (FChecklist/veridian-
scripts#322, /opt/veridian/scripts/progress_completion_gate.py). The commit
merged into THIS repo (claude-control) was the RCA markdown document alone;
no gate code was ever added to claude-control's own scripts/ or wired into
claude-control's own worker-entrypoint.sh. Since claude-control dispatches
its own tasks (including this one) through its own worker-entrypoint.sh, the
exact bug the prior task described -- and claimed to have fixed -- was still
fully live here. This module is the real fix, in the repo that actually
needed it.

Two pieces of real (mechanical, not prompt-instruction) enforcement:

  1. `check-completion` -- if a task's own prompt.txt names a specific
     source/script file as its objective, that file must appear in the
     task's real git diff (committed-since-merge-base + staged + unstaged).
     A diff that only touches progress/doc artifacts for a code-named
     objective is REJECTED with an explicit reason and a non-zero exit code
     -- never silently accepted as complete. Wired into worker-entrypoint.sh
     between the COMPLETION-GATE-BLOCK markers, run after the main
     invocation returns and before the quality-gate/pending_review path.
  2. `rollup` -- deterministically regenerates a single rolled-up view from
     every progress/<task_id>.md file, sorted by filename. Generated output
     only -- no worker branch ever writes to it, so it can never become the
     shared-file collision progress/<task_id>.md (per task_identity) itself
     exists to avoid.
"""
import argparse
import os
import re
import subprocess
import sys

# Extensions that count as "a specific source file or script" for the
# completion gate. Deliberately excludes .md/.txt/.json/.yaml doc/config
# extensions -- the gate exists to catch "objective named a CODE file, diff
# has no code", not to force every task to touch a file of some kind.
CODE_EXTENSIONS = (
    "py", "sh", "js", "jsx", "ts", "tsx", "go", "rb",
    "java", "c", "h", "cpp", "hpp", "rs", "sql", "mjs", "yaml", "yml",
)

FILENAME_RE = re.compile(
    r"[A-Za-z0-9_\-./]+\.(?:" + "|".join(CODE_EXTENSIONS) + r")\b"
)

# Progress/doc artifacts the gate must never itself treat as "the named
# objective file", even when they appear in prose right next to a real code
# filename -- these are exactly the artifacts this whole fix exists to stop
# conflating with real code.
_PROGRESS_ARTIFACT_RES = (
    re.compile(r"^PROGRESS\.md$", re.IGNORECASE),
    re.compile(r"^progress/.*\.md$", re.IGNORECASE),
    re.compile(r"^RCA.*\.md$", re.IGNORECASE),
)


def is_progress_artifact(path):
    base = path.rsplit("/", 1)[-1]
    return any(p.match(path) or p.match(base) for p in _PROGRESS_ARTIFACT_RES)


def extract_named_code_files(text):
    """Real source/script filenames referenced in a task's own spec text
    (prompt.txt). Order-preserving de-dup; progress/doc artifacts excluded
    even though their extension (.md) is not in CODE_EXTENSIONS anyway --
    kept explicit so the exclusion is provable, not incidental."""
    text = text or ""
    seen = []
    for m in FILENAME_RE.finditer(text):
        candidate = m.group(0)
        if is_progress_artifact(candidate):
            continue
        if candidate not in seen:
            seen.append(candidate)
    return seen


def _git(workspace, *args):
    return subprocess.run(
        ["git", "-C", workspace, *args], capture_output=True, text=True
    )


def git_diff_files(workspace, default_branch):
    """Real changed-file set for this branch: committed-since-merge-base,
    PLUS staged, PLUS unstaged. This gate runs from worker-entrypoint.sh's
    own COMPLETION-GATE-BLOCK before the final `git add -A && git commit`,
    so committed-only would miss real in-progress work; it must also see
    fully-committed branches when invoked standalone (e.g. from a test or a
    resume), so committed history is not skipped either."""
    out = set()
    mb = _git(workspace, "merge-base", f"origin/{default_branch}", "HEAD")
    merge_base = mb.stdout.strip() if mb.returncode == 0 else f"origin/{default_branch}"
    for args in (
        ("diff", "--name-only", merge_base, "HEAD"),
        ("diff", "--name-only", "HEAD"),
        ("diff", "--name-only", "--cached"),
    ):
        res = _git(workspace, *args)
        if res.returncode == 0:
            out.update(f for f in res.stdout.splitlines() if f)
    return out


def check_completion(task_dir, workspace, default_branch):
    """Returns (ok, reason).

    ok=True whenever there is nothing real to gate on (objective names no
    code file) OR at least one named file is really present in the diff.

    ok=False -- a REAL rejection, never downgraded to a success status --
    only when the objective names >=1 code file, the diff is non-empty, and
    NONE of the named files are in it (i.e. a doc/progress-only diff for a
    code-named objective).
    """
    prompt_path = os.path.join(task_dir, "prompt.txt")
    try:
        with open(prompt_path) as f:
            spec_text = f.read()
    except FileNotFoundError:
        return True, "no prompt.txt found -- nothing to gate on"

    named = extract_named_code_files(spec_text)
    if not named:
        return True, "objective names no specific source/script file -- gate does not apply"

    diff_files = git_diff_files(workspace, default_branch)
    if not diff_files:
        return True, "empty diff -- handled by the separate no-op path, not this gate"

    diff_basenames = {f.rsplit("/", 1)[-1] for f in diff_files}
    matched = [
        n for n in named
        if n in diff_files or n.rsplit("/", 1)[-1] in diff_basenames
    ]
    if matched:
        return True, f"objective-named file(s) present in diff: {matched}"

    non_progress = sorted(f for f in diff_files if not is_progress_artifact(f))
    reason = (
        f"objective named {named} but the diff touches no code -- "
        f"diff only contains: {sorted(diff_files)}"
    )
    if non_progress:
        reason += f" (non-progress files present but none of them match: {non_progress})"
    return False, reason


def cmd_check_completion(args):
    ok, reason = check_completion(args.task_dir, args.workspace, args.default_branch)
    print(reason)
    return 0 if ok else 1


def cmd_rollup(args):
    """Deterministic, generated-only rollup -- never a merge target. Reads
    every progress/*.md file in the workspace, in filename-sorted order, and
    concatenates them under an explicit generated-file banner. Safe to run
    from any number of concurrent branches: it only READS progress/*.md
    (each worker's own file) and WRITES a single output path that no worker
    branch itself commits to as part of its own progress protocol."""
    progress_dir = os.path.join(args.workspace, "progress")
    lines = [
        "<!-- GENERATED by progress_completion_gate.py rollup -- do not hand-edit. -->",
        "<!-- Source of truth is progress/<task_id>.md, one file per task. -->",
        "",
        "# Progress rollup",
        "",
    ]
    if os.path.isdir(progress_dir):
        for name in sorted(os.listdir(progress_dir)):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(progress_dir, name)) as f:
                body = f.read().rstrip()
            lines.append(f"## {name}")
            lines.append("")
            lines.append(body)
            lines.append("")
    output = "\n".join(lines) + "\n"
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
    else:
        sys.stdout.write(output)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser(
        "check-completion",
        help="reject a doc/progress-only diff for a code-named objective",
    )
    p_check.add_argument("--task-dir", required=True)
    p_check.add_argument("--workspace", required=True)
    p_check.add_argument("--default-branch", required=True)
    p_check.set_defaults(func=cmd_check_completion)

    p_roll = sub.add_parser(
        "rollup", help="regenerate the deterministic progress rollup view"
    )
    p_roll.add_argument("--workspace", required=True)
    p_roll.add_argument("--output", help="write here instead of stdout")
    p_roll.set_defaults(func=cmd_rollup)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
