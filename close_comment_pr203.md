Closing as superseded.

This PR contains only a progress markdown file (no code) documenting a
duplicate-guard over-blocking fix that was already shipped and merged
upstream as veridian-scripts PR #345, commit
`1f16c1159b6474869c90de712d09a640a8191874` ("fix(resource_governor):
duplicate guards over-blocking brand-new work (UMR-20260814-015201)"), which
is present on `main` in the live `/opt/veridian/scripts` checkout.

This also matches the real posted audit verdict on this PR
(2026-08-14T02:12:56Z):

> AUDIT: FAIL
> ...
> Verdict: fail
> Corrective Action Owner: Worker to address the findings listed above and
> resubmit.

Separately, the sibling code PR for this same work (veridian-scripts #342)
was diffed against the actual merged commit before being closed: two of its
two real bug fixes were functionally identical to what #345 shipped, and the
one piece of unique value it carried (a helper excluding a parenthetical
PR-number citation from Stage 6 matching) was salvaged into a small
follow-up, veridian-scripts #356, rather than discarded. Closing this PR
without merging -- it carries no code of its own.
