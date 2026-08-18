#!/bin/bash
REPO="FChecklist/veridian-scripts"
MSG="Closing as **obsolete**: this PR's entire diff is a single edit to the shared root \`PROGRESS.md\` (no code file touched). Commit \`1c363b6\` on \`origin/main\` (\"fix(worker-entrypoint): per-task progress files + real completion gate, kill the shared-PROGRESS.md conflict/empty-fix hole\") structurally moved every worker off that shared file onto \`progress/\${TASK_ID}.md\`, and added \`progress_completion_gate.py\`, which explicitly refuses to treat a PROGRESS.md-only diff as real completion evidence. \`origin/main\`'s root \`PROGRESS.md\` today holds an unrelated, much later task's checkpoint -- it has been overwritten dozens of times since this PR opened, so this PR's premise (that this text belongs in the shared file) is false and merging it would just regress the current placeholder. Triaged under task-20260814-060159."

NUMS="24 28 74 75 80 89 94 101 113 182 183 203 209 215 219 220 222 223 225 226 229 236 239 240 243 267"
for n in $NUMS; do
  echo "=== closing #$n ==="
  gh pr close "$n" --repo "$REPO" --comment "$MSG" 2>&1
done
echo "=== done ==="
