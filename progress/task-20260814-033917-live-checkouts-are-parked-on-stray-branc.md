# Live checkouts parked on stray branches -- drift fix

## Scope correction (real, independently verified -- see evidence below)

The SPEC calls both `/opt/veridian/repos/veridian-scripts` and `/opt/veridian/ai-os`
"live checkouts". Independent verification shows this is only half true:

- `/opt/veridian/ai-os` **is** genuinely live: 3 systemd --user oneshot units
  (`veridian-cron-veridian-self-check.service`, `veridian-cron-file-inventory.service`,
  `veridian-cron-audit-pipeline-security.service`) execute Python files directly out of
  `/opt/veridian/ai-os/scripts/*.py` on a recurring timer. This checkout's branch/HEAD
  genuinely determines what code those units run.
- `/opt/veridian/repos/veridian-scripts` is **not** live. `grep -rl "repos/veridian-scripts"`
  across every `~/.config/systemd/user/*.service` and every `/opt/veridian/scripts/*.py`
  finds exactly one hit: a comment in `veridian-cron-zoekt-reindex.service` documenting
  that this exact checkout was deliberately dropped from indexing on 2026-08-13
  (task-20260813-103224, UMR-20260813-101142-5d24) as "an orphaned second checkout of
  the same repo /opt/veridian/scripts already indexes, 200 commits behind and
  unmaintained since 2026-08-06 (nothing pulls it)". The real live veridian-scripts
  deploy target is a separate, third checkout: `/opt/veridian/scripts`, confirmed
  independently at HEAD `badf5a4` == `origin/main` (0 ahead, 0 behind) -- already healthy,
  not part of this defect. Every `ExecStart=` line in every systemd --user unit that runs
  veridian-scripts code points at `/opt/veridian/scripts`, never at
  `/opt/veridian/repos/veridian-scripts`.

Consequence: I still do the full preserve/verify/PR/fast-forward sequence on
`/opt/veridian/repos/veridian-scripts` (asked for explicitly, and cheap/safe to do), but
step 5 (restart services, prove live code) has nothing to restart for that path --
stated plainly below, not glossed over.

## Completed
- [x] Step 1: Preserved ahead-commits by pushing both stray branches to origin
      **before** any reset/checkout/discard.
  - `veridian-scripts`: pushed `worker/task-20260814-010457-recurrence-doc-only-fake-fix-cleanup`
    (new branch on origin) -- `git push origin worker/task-20260814-010457-recurrence-doc-only-fake-fix-cleanup`
    -> `* [new branch] worker/task-20260814-010457-recurrence-doc-only-fake-fix-cleanup -> ...`
    Verified via `git ls-remote origin refs/heads/worker/task-20260814-010457-recurrence-doc-only-fake-fix-cleanup`
    -> `b10afec21bdd1bef9f58619b56b4b7f7a71b8311` (matches local HEAD exactly).
  - `ai-os`: pushed `docs/hard-rule3-correction-find-root-and-umr-grep-guidance-umr20260806103641-2a1f`
    (fast-forward of an already-partially-pushed branch) --
    `git push origin docs/hard-rule3-correction-find-root-and-umr-grep-guidance-umr20260806103641-2a1f`
    -> `523f49e..ca513ca  docs/hard-rule3-correction-...`
    Verified via `git ls-remote` -> `ca513ca2a85dd77894b1a627b2a957262e94d191` (matches local HEAD exactly).

## Remaining
- [ ] Step 2: `git cherry -v` per-commit verdict for both repos' ahead-commits
- [ ] Step 3: Open PR(s) for genuinely unmerged work
- [ ] Step 4: Fast-forward both live checkouts to origin/main, show before/after
      `git rev-parse HEAD` + `git status`
- [ ] Step 5: Restart/reload real services reading these trees; prove with a real
      functional check (ai-os only -- veridian-scripts/repos has no reader, see above)
- [ ] Step 6: Add a recurring drift guard (reuse `check_live_scripts_drift.py`,
      wire into the existing `veridian-cron-veridian-self-check` unit rather than
      creating a new systemd unit -- the closed-set-of-18/20 policy documented in
      `~/.config/systemd/user/README.md` and every unit file forbids adding a new
      unit without explicit Owner sign-off)
- [ ] record-completion write-back to UMR-20260814-033856-9db0
