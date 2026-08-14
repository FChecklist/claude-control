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
Four real, deterministic refusal conditions, checked in this order:

  0. UNTRUSTED VERDICT SOURCE -- a verdict-shaped comment/review exists, but
     its author is disqualified as a verdict source, for either of two real,
     independent reasons:
       (a) SELF-REVIEW -- its author is the exact same login that authored
           the PR (see _is_self_review). Hard invariant, never overridable
           by an association or an allowlist -- matches GitHub's own
           required-review semantics (a PR author's own approval never
           satisfies a required-review branch-protection rule either).
       (b) UNTRUSTED ASSOCIATION -- its author does not have a trusted repo
           association (real, live `authorAssociation` from GitHub itself --
           OWNER/MEMBER/COLLABORATOR by default, see
           TRUSTED_AUTHOR_ASSOCIATIONS) or is not on the explicit
           MERGE_GATE_AUDITOR_LOGINS allowlist when one is configured.
     Together these close the CRITICAL self-certification gap audited live
     on this PR itself (2026-08-14T10:20Z, corrective re-audit confirmed the
     first-pass fix of (b) alone was insufficient because this repo's own
     real PR authors and real audit commenters are today the same OWNER
     -associated login): without both checks, either ANY account with
     comment access, or the PR's own author specifically, could post a
     fabricated "AUDIT: PASS" and force a merge through. Either way the
     untrusted verdict is skipped entirely, not just downgraded -- the scan
     keeps looking for the newest TRUSTED verdict among older events.
  1. NO VERDICT -- no comment or review whose body's first non-blank line is
     a structured "AUDIT: PASS" / "AUDIT: FAIL" line (case-insensitive,
     optional leading markdown `#`/`##`) exists anywhere on the PR from a
     trusted source.
  2. FAILING VERDICT -- the NEWEST such trusted verdict (comments and
     reviews merged into one timeline, sorted by their real timestamps) is
     FAIL.
  3. STALE PASS -- the newest trusted verdict is PASS, but it either cites
     no head SHA at all, or the SHA it cites does not match the PR's live,
     current headRefOid (accepting a short-SHA prefix match either
     direction). This is the real "a later commit dropped previously
     audited content" failure mode the governing SPEC names explicitly -- a
     PASS is only evidence about the commit it was actually run against.

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

Environment variables (all optional; identity/trust config only):
  MERGE_GATE_TRUSTED_ASSOCIATIONS  comma-separated GitHub authorAssociation
                                    values to trust (default:
                                    "OWNER,MEMBER,COLLABORATOR").
  MERGE_GATE_AUDITOR_LOGINS        comma-separated login allowlist; when set,
                                    ONLY these logins' verdicts are trusted
                                    (association check is bypassed, self-
                                    review check is NOT). Unset by default --
                                    no distinct auditor account is
                                    provisioned in this environment yet.
  MERGE_GATE_ALLOW_SELF_REVIEW     "1"/"true"/"yes" to disable the PR-author
                                    -cannot-audit-their-own-PR hard invariant.
                                    Unset (disabled) by default -- this is a
                                    real, deliberate loss of the gate's core
                                    guarantee; only an owner who has
                                    consciously accepted that risk should set
                                    it, and nothing in this module ever sets
                                    it itself.
"""
import argparse
import json
import os
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

# --- Identity/trust gap closed here (real, audited CRITICAL finding posted
# 2026-08-14T10:20Z on claude-control PR #230, the PR that introduced this
# module) --------------------------------------------------------------------
# find_latest_verdict() used to accept an "AUDIT: PASS"/"AUDIT: FAIL" verdict
# from ANY PR comment or review author at all -- no authorAssociation check,
# no bot/service-account allowlist. Because neither claude-control nor
# veridian-scripts has GitHub branch protection configured (confirmed live:
# 404/403 on both repos' branch-protection API, 2026-08-14), this module is
# the SOLE enforcement mechanism for the audit-before-merge control, so
# anyone with repo comment access -- in principle including the PR's own
# author -- could self-approve a merge just by posting a fabricated
# "AUDIT: PASS\nHead SHA audited: <current head>" comment, reproducing the
# exact self-certification failure this gate exists to close.
#
# Real, closable fix, matching the audit's own suggested remedy verbatim
# ("require OWNER/MEMBER or a specific service-account login"): only trust a
# verdict from an account GitHub itself reports (via the real, live
# `authorAssociation` field already present on every `gh pr view --json
# comments,reviews` entry -- no extra API call needed) as having real
# write-level association with the repo. `MERGE_GATE_AUDITOR_LOGINS`, if set,
# narrows this further to an explicit login allowlist -- for the day a
# distinct service/bot account is provisioned to post audits separately from
# PR authors. As of this writing no such separate account exists in this
# environment (every real `gh api user` call in this repo resolves to the
# same single OWNER-association login that also authors every PR) -- same
# honesty as AGENTS.md's own "NOT APPLICABLE YET" notes: a login-based
# self-vs-auditor distinction is not achievable here yet, so the
# authorAssociation check is the real, available layer of defense, and is
# applied uniformly (skips untrusted PASS *and* FAIL alike -- an untrusted
# commenter carries no authority in either direction, so the gate keeps
# scanning older events for the newest TRUSTED verdict instead of trusting
# or being denial-of-serviced by unauthenticated noise).
TRUSTED_AUTHOR_ASSOCIATIONS = frozenset(
    a.strip().upper()
    for a in os.environ.get(
        "MERGE_GATE_TRUSTED_ASSOCIATIONS", "OWNER,MEMBER,COLLABORATOR"
    ).split(",")
    if a.strip()
)

_AUDITOR_LOGIN_ALLOWLIST = frozenset(
    login.strip().lower()
    for login in os.environ.get("MERGE_GATE_AUDITOR_LOGINS", "").split(",")
    if login.strip()
)


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
    """Real, live GitHub state for one PR: current head SHA, state, PR
    author, and every comment + review body with its real timestamp AND
    real `authorAssociation` (both fields `gh pr view --json` already
    returns natively -- no extra API call needed). Raises GhError on any
    real `gh` failure -- callers must treat that as REFUSE, never ALLOW."""
    out = _run_gh(
        ["pr", "view"]
        + _pr_target(repo, pr)
        + ["--json", "number,url,state,headRefOid,author,comments,reviews"]
    )
    data = json.loads(out)
    events = []
    for c in data.get("comments") or []:
        events.append(
            {
                "kind": "comment",
                "author": (c.get("author") or {}).get("login"),
                "author_association": (c.get("authorAssociation") or "").upper(),
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
                "author_association": (r.get("authorAssociation") or "").upper(),
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
        "pr_author": (data.get("author") or {}).get("login"),
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


def _is_self_review(event, pr_author):
    """Real, hard invariant closing the deeper half of the CRITICAL finding
    audited live on PR #230 (2026-08-14T10:20Z, corrective re-audit
    2026-08-14T~11:xxZ): the FIRST fix here only added an
    authorAssociation check, which does NOT actually stop the PR's own
    author from self-certifying in THIS repo, because a real, live check
    (`gh api repos/FChecklist/claude-control/issues/230/comments --jq '.[]
    | .user.login, .author_association'`) confirms every PR author AND
    every audit commenter in this repo today is the exact same OWNER
    -associated login. An authorAssociation allowlist alone cannot
    distinguish "the account with real repo access" from "the account
    that wrote this PR", because right now they are always the same
    account -- so an association-only check leaves the literal attack the
    audit named ("including the PR's own author... posting a fabricated
    AUDIT: PASS") completely open in the one environment this gate
    actually has to defend.

    This is NOT overridable by MERGE_GATE_AUDITOR_LOGINS or
    MERGE_GATE_TRUSTED_ASSOCIATIONS -- a PR's own author must never be
    treated as its own auditor, full stop, matching GitHub's own required
    -review semantics (a PR author's own approval never satisfies a
    required-review branch-protection rule either). The one escape hatch
    is MERGE_GATE_ALLOW_SELF_REVIEW=1 -- unset by default, loud and
    explicit by name, for an owner who has consciously decided to accept
    this risk (e.g. while no distinct auditor identity exists yet);
    nothing in this module ever sets it itself."""
    if os.environ.get("MERGE_GATE_ALLOW_SELF_REVIEW", "").strip().lower() in (
        "1", "true", "yes",
    ):
        return False
    login = (event.get("author") or "").strip().lower()
    author_login = (pr_author or "").strip().lower()
    return bool(login) and bool(author_login) and login == author_login


def _is_trusted_verdict_source(event, pr_author):
    """Real identity check closing the CRITICAL finding audited live on PR
    #230 (2026-08-14T10:20Z): an event only carries verdict authority if
    (a) its author is not the PR's own author (see _is_self_review) AND
    (b) its author has real, GitHub-reported write-level association with
    the repo, or, once a distinct service account exists, is on the
    explicit MERGE_GATE_AUDITOR_LOGINS allowlist. See the
    TRUSTED_AUTHOR_ASSOCIATIONS docstring above for the full incident
    writeup."""
    if _is_self_review(event, pr_author):
        return False
    if _AUDITOR_LOGIN_ALLOWLIST:
        login = (event.get("author") or "").strip().lower()
        return login in _AUDITOR_LOGIN_ALLOWLIST
    return event.get("author_association") in TRUSTED_AUTHOR_ASSOCIATIONS


def find_latest_verdict(events, pr_author):
    """First (= newest, events are pre-sorted) event whose body opens with a
    structured AUDIT: PASS/FAIL line AND whose author is a trusted verdict
    source (see _is_trusted_verdict_source). An untrusted commenter's
    "verdict" carries no authority at all -- it is skipped, not treated as
    the newest, so the scan keeps looking for the newest genuinely-trusted
    verdict among older events (never falls back to trusting it just because
    nothing else was found).

    Returns (verdict_or_None, untrusted_events) -- the second element records
    every untrusted verdict-shaped event that was skipped, purely for
    auditability in the decision object; it never affects allow/refuse."""
    untrusted = []
    for e in events:
        first_line = next(
            (line for line in e["body"].splitlines() if line.strip()), ""
        )
        m = VERDICT_LINE_RE.match(first_line)
        if not m:
            continue
        if not _is_trusted_verdict_source(e, pr_author):
            untrusted.append(
                {
                    "verdict": m.group(1).upper(),
                    "author": e["author"],
                    "author_association": e.get("author_association"),
                    "self_review": _is_self_review(e, pr_author),
                    "ts": e["ts"],
                    "kind": e["kind"],
                }
            )
            continue
        return {
            "verdict": m.group(1).upper(),
            "cited_sha": extract_cited_sha(e["body"]),
            "author": e["author"],
            "author_association": e.get("author_association"),
            "ts": e["ts"],
            "kind": e["kind"],
        }, untrusted
    return None, untrusted


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
    verdict, untrusted = find_latest_verdict(snapshot["events"], snapshot["pr_author"])
    decision = {
        "pr_url": snapshot["url"],
        "pr_number": snapshot["number"],
        "pr_state": snapshot["state"],
        "head_sha": snapshot["head_sha"],
        "pr_author": snapshot["pr_author"],
        "latest_verdict": verdict,
        "untrusted_verdicts_skipped": untrusted,
    }

    if verdict is None:
        decision["allowed"] = False
        if any(u["self_review"] for u in untrusted):
            decision["reason"] = (
                "no TRUSTED audit verdict found: the only verdict(s) posted "
                f"were self-review -- authored by {snapshot['pr_author']!r}, "
                "the same login that authored this PR -- which never carries "
                "authority, regardless of its GitHub association"
            )
        elif untrusted:
            decision["reason"] = (
                "no TRUSTED audit verdict found: "
                f"{len(untrusted)} verdict-shaped comment(s)/review(s) exist "
                "but none of their authors has a trusted repo association "
                f"({sorted(TRUSTED_AUTHOR_ASSOCIATIONS)}) -- an untrusted "
                "verdict carries no authority and cannot allow a merge"
            )
        else:
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
