#!/usr/bin/env python3
"""merge_gate.py -- the real, deterministic merge gate for GitHub pull
requests (task-20260814-095552-block-merges-that-have-no-fresh-passing).

REAL INCIDENTS THIS CLOSES (evidence gathered 2026-08-14T09:50Z via live `gh
pr view` on both issue comments and reviews): eight PRs merged the same day
carrying ZERO audit verdict anywhere -- claude-control #216, #217, #220,
#221, #226 and veridian-scripts #356, #366 -- and one, claude-control #219,
merged with an outstanding `AUDIT: FAIL` comment about metric-state
corruption still posted against it. ROOT CAUSE: nothing MECHANICALLY
prevented any of those merges -- the "post an AUDIT verdict, then merge"
discipline lived only inside scripts/supervisor-entrypoint.sh's own review
call, not as a reusable, independently-enforced gate every real merge call
site (this repo's own status-remediation-tick.py transient-merge-retry path,
or an assistant session running `gh pr merge`/`gh api .../merge` directly
during a cleanup sweep) was forced to go through. "The audit requirement is
policy text only, enforced by convention" (governing SPEC, verbatim).

THIS module is that reusable gate. Given a repo + PR, it decides ALLOW/REFUSE
from the PR's live GitHub state alone (comments + reviews + the PR's real
current headRefOid) -- never from a caller's self-report of its own verdict.
Three real, deterministic refusal conditions, checked in this order:

  1. NO VERDICT -- no comment or review whose body's first non-blank line is
     a structured "AUDIT: PASS" / "AUDIT: FAIL" line (case-insensitive,
     optional leading markdown `#`/`##`) exists anywhere on the PR.
  2. FAILING VERDICT -- the NEWEST such verdict (comments and reviews merged
     into one timeline, sorted by their real timestamps) is FAIL.
  3. STALE PASS -- the newest verdict is PASS, but it either cites no head
     SHA at all, or the SHA it cites does not match the PR's live, current
     headRefOid (accepting a short-SHA prefix match either direction). This
     is the real "a later commit dropped previously audited content"
     failure mode the governing SPEC names explicitly -- a PASS is only
     evidence about the commit it was actually run against.

Only when the newest verdict is PASS *and* its cited SHA matches the PR's
live current head does `merge` go on to actually call `gh pr merge`. `check`
never calls `gh pr merge` (or any other mutating command) at all -- it is
read-only and safe to run speculatively, including by a human or another
script deciding whether to even attempt a merge.

Usage:
  python3 merge_gate.py check --pr-url <url>
  python3 merge_gate.py check --repo OWNER/NAME --pr <number>
  python3 merge_gate.py merge --pr-url <url> [--merge-method merge|squash|rebase] [--delete-branch]
  python3 merge_gate.py merge --repo OWNER/NAME --pr <number> [--merge-method ...] [--delete-branch]

Both subcommands print exactly one JSON decision object to stdout and exit 0
if ALLOWED, 1 if REFUSED (including any real `gh`/API error -- fail closed,
never fail open) -- a caller never needs to parse stdout to decide whether a
merge happened; the exit code alone is authoritative, same convention this
repo's own supervisor_merge_detection_test.sh already established for
merge-outcome detection (trust a fresh API check, never a shell exit code,
for whether the merge itself succeeded -- see `merge_pr_via_gate` below).
"""
import argparse
import json
import re
import subprocess
import sys

# A verdict line is the first non-blank line of a comment/review body,
# optionally markdown-headed ("## AUDIT: PASS"), case-insensitive on both the
# literal word and the verdict itself -- matches every real verdict format
# seen live on this platform (see supervisor-entrypoint.sh's own AUDIT_BODY
# and the "## AUDIT: PASS" / "AUDIT: FAIL" comments observed on real PRs
# #217 and #219 respectively).
VERDICT_LINE_RE = re.compile(r"^\s*#{0,3}\s*AUDIT:\s*(PASS|FAIL)\b", re.IGNORECASE)

# Real head-SHA citation formats already observed in the wild ("Head SHA
# audited: `8737be0...`", "AUDIT_HEAD_SHA=...", "audited sha 4d8f307") plus
# any generic "sha"/"commit"-labeled hex token -- deliberately permissive on
# the LABEL (so any reasonable future phrasing of the same field still
# parses) but strict on the VALUE (a real 7-40 char hex token only).
SHA_LABELED_RE = re.compile(
    r"(?:head[\s_-]*sha(?:\s*audited)?|audited[\s_-]*sha|sha[\s_-]*audited|commit(?:\s*sha)?)"
    # Real audit prose puts markdown noise (bold `**`, backticks, colons) between
    # the label and the value ("**Head SHA audited:** `8737be0...`") -- match any
    # short run of that punctuation/whitespace, not just a bare colon+backtick, or
    # the whole label match fails here and re.search falls through to a LATER,
    # unrelated hex token elsewhere in the body (real bug, caught live against PR
    # #217's own audit comment: without this, it picked up an unrelated `commit
    # 108652d` mentioned three sentences later instead of the real audited SHA).
    r"[\s:=\-*`]{0,8}([0-9a-f]{7,40})\b",
    re.IGNORECASE,
)
# Fallback: a bare full-length (40 hex char) SHA anywhere in the body -- real
# audit prose commonly just states the full commit hash without a label.
SHA_BARE_RE = re.compile(r"\b([0-9a-f]{40})\b")


class GhError(RuntimeError):
    pass


def _run_gh(args, timeout=60):
    """Real subprocess call to the `gh` CLI -- never mocked in the code path
    itself, only in tests (see tests/test_merge_gate.py), so `check`/`merge`
    always reflect this PR's genuine, live GitHub state."""
    try:
        result = subprocess.run(
            ["gh"] + args, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError as e:
        raise GhError(f"gh CLI not found: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise GhError(f"gh {' '.join(args)} timed out after {timeout}s") from e
    if result.returncode != 0:
        raise GhError(
            f"gh {' '.join(args)} exited {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout


def _pr_target(repo, pr):
    """`gh pr view`/`merge` accept either a bare PR number (with --repo) or a
    full URL (no --repo needed) -- this repo's own supervisor-entrypoint.sh
    always has a URL ($PR_URL), so both call shapes are real, not speculative."""
    if repo:
        return [str(pr), "--repo", repo]
    return [str(pr)]


def get_pr_snapshot(repo, pr):
    """Real, live GitHub state for one PR: current head SHA, state, and every
    comment + review body with its real timestamp. Raises GhError on any
    real `gh` failure -- callers must treat that as REFUSE, never ALLOW."""
    out = _run_gh(
        ["pr", "view"]
        + _pr_target(repo, pr)
        + ["--json", "number,url,state,headRefOid,comments,reviews"]
    )
    data = json.loads(out)
    events = []
    for c in data.get("comments") or []:
        events.append(
            {
                "kind": "comment",
                "author": (c.get("author") or {}).get("login"),
                "body": c.get("body") or "",
                "ts": c.get("createdAt") or "",
            }
        )
    for r in data.get("reviews") or []:
        body = r.get("body") or ""
        if not body.strip():
            continue  # a plain APPROVE/REQUEST_CHANGES with no text carries no verdict
        events.append(
            {
                "kind": "review",
                "author": (r.get("author") or {}).get("login"),
                "body": body,
                "ts": r.get("submittedAt") or "",
            }
        )
    # Newest first -- ISO8601 timestamps from GitHub sort correctly as strings.
    events.sort(key=lambda e: e["ts"], reverse=True)
    return {
        "number": data.get("number"),
        "url": data.get("url"),
        "state": data.get("state"),
        "head_sha": data.get("headRefOid"),
        "events": events,
    }


def extract_cited_sha(body):
    m = SHA_LABELED_RE.search(body)
    if m:
        return m.group(1).lower()
    m = SHA_BARE_RE.search(body)
    if m:
        return m.group(1).lower()
    return None


def find_latest_verdict(events):
    """First (= newest, events are pre-sorted) event whose body opens with a
    structured AUDIT: PASS/FAIL line. Returns None if no PR event anywhere
    carries a real structured verdict at all."""
    for e in events:
        first_line = next(
            (line for line in e["body"].splitlines() if line.strip()), ""
        )
        m = VERDICT_LINE_RE.match(first_line)
        if not m:
            continue
        return {
            "verdict": m.group(1).upper(),
            "cited_sha": extract_cited_sha(e["body"]),
            "author": e["author"],
            "ts": e["ts"],
            "kind": e["kind"],
        }
    return None


def _sha_matches(cited_sha, head_sha):
    if not cited_sha or not head_sha:
        return False
    cited_sha, head_sha = cited_sha.lower(), head_sha.lower()
    if len(cited_sha) < 7 or len(head_sha) < 7:
        return False
    return head_sha.startswith(cited_sha) or cited_sha.startswith(head_sha)


def evaluate_gate(repo, pr):
    """The real deterministic decision. Never raises for an ordinary
    refuse case -- returns {"allowed": False, "reason": ...}. A real `gh`/API
    failure IS re-raised as GhError (fail closed: callers must treat any
    inability to confirm ALLOW as REFUSE, never default to allowing)."""
    snapshot = get_pr_snapshot(repo, pr)
    verdict = find_latest_verdict(snapshot["events"])
    decision = {
        "pr_url": snapshot["url"],
        "pr_number": snapshot["number"],
        "pr_state": snapshot["state"],
        "head_sha": snapshot["head_sha"],
        "latest_verdict": verdict,
    }

    if verdict is None:
        decision["allowed"] = False
        decision["reason"] = (
            "no audit verdict found: no PR comment or review body opens with "
            "a structured 'AUDIT: PASS'/'AUDIT: FAIL' line"
        )
        return decision

    if verdict["verdict"] == "FAIL":
        decision["allowed"] = False
        decision["reason"] = (
            f"newest posted audit verdict is FAIL (by {verdict['author']} at "
            f"{verdict['ts']})"
        )
        return decision

    # verdict["verdict"] == "PASS" from here on.
    if not verdict["cited_sha"]:
        decision["allowed"] = False
        decision["reason"] = (
            "newest audit verdict is PASS but cites no head SHA -- cannot "
            "confirm it was run against this PR's current content"
        )
        return decision

    if not _sha_matches(verdict["cited_sha"], snapshot["head_sha"]):
        decision["allowed"] = False
        decision["reason"] = (
            f"stale pass: newest PASS verdict cites SHA {verdict['cited_sha']} "
            f"but the PR's current head is {snapshot['head_sha']} -- a later "
            f"commit landed after this verdict was audited"
        )
        return decision

    decision["allowed"] = True
    decision["reason"] = (
        f"fresh PASS verdict by {verdict['author']} at {verdict['ts']} cites "
        f"head SHA {verdict['cited_sha']}, matching the PR's current head "
        f"{snapshot['head_sha']}"
    )
    return decision


def merge_pr_via_gate(repo, pr, merge_method="merge", delete_branch=False):
    """Only real caller of `gh pr merge` this module exposes. Evaluates the
    gate first; on REFUSE, returns the refusal decision and calls `gh pr
    merge` NOT AT ALL. On ALLOW, calls it, then judges success solely via a
    fresh `gh pr view --json state,mergedAt` call -- never the merge
    command's own exit code (same real-incident-driven rule
    tests/supervisor_merge_detection_test.sh already enforces for
    supervisor-entrypoint.sh's own merge call: a `gh pr merge` can genuinely
    succeed server-side and still exit non-zero for an unrelated local
    reason)."""
    decision = evaluate_gate(repo, pr)
    if not decision["allowed"]:
        decision["merged"] = False
        decision["merge_attempted"] = False
        return decision

    merge_args = ["pr", "merge"] + _pr_target(repo, pr) + [f"--{merge_method}"]
    if delete_branch:
        merge_args.append("--delete-branch")
    decision["merge_attempted"] = True
    try:
        _run_gh(merge_args)
    except GhError as e:
        decision["merge_command_error"] = str(e)

    # Trust only a fresh live check, never the command's own exit code.
    verify_out = _run_gh(
        ["pr", "view"] + _pr_target(repo, pr) + ["--json", "state,mergedAt"]
    )
    verify = json.loads(verify_out)
    decision["merged"] = verify.get("state") == "MERGED" and bool(
        verify.get("mergedAt")
    )
    decision["post_merge_state"] = verify.get("state")
    decision["post_merge_merged_at"] = verify.get("mergedAt")
    return decision


def _add_common_args(p):
    p.add_argument("--pr-url", default=None, help="full PR URL (no --repo needed)")
    p.add_argument("--repo", default=None, help="OWNER/NAME, used with --pr")
    p.add_argument("--pr", default=None, help="PR number, used with --repo")


def _resolve_target(args):
    if args.pr_url:
        return None, args.pr_url
    if args.repo and args.pr:
        return args.repo, args.pr
    raise SystemExit("error: supply either --pr-url or both --repo and --pr")


def cmd_check(args):
    repo, pr = _resolve_target(args)
    try:
        decision = evaluate_gate(repo, pr)
    except GhError as e:
        print(json.dumps({"allowed": False, "reason": f"gh error: {e}"}, indent=2))
        sys.exit(1)
    print(json.dumps(decision, indent=2))
    sys.exit(0 if decision["allowed"] else 1)


def cmd_merge(args):
    repo, pr = _resolve_target(args)
    try:
        decision = merge_pr_via_gate(
            repo, pr, merge_method=args.merge_method, delete_branch=args.delete_branch
        )
    except GhError as e:
        print(json.dumps({"allowed": False, "reason": f"gh error: {e}"}, indent=2))
        sys.exit(1)
    print(json.dumps(decision, indent=2))
    sys.exit(0 if decision["allowed"] and decision.get("merged") else 1)


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="read-only: report ALLOW/REFUSE, never calls gh pr merge")
    _add_common_args(p_check)
    p_check.set_defaults(func=cmd_check)

    p_merge = sub.add_parser("merge", help="evaluate the gate, and only on ALLOW actually call gh pr merge")
    _add_common_args(p_merge)
    p_merge.add_argument("--merge-method", default="merge", choices=["merge", "squash", "rebase"])
    p_merge.add_argument("--delete-branch", action="store_true")
    p_merge.set_defaults(func=cmd_merge)

    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
