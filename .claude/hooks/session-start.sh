#!/usr/bin/env bash
# SessionStart hook: prints MEMORY.md + short git summary into Claude's context.
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
MEM="agent-kit/MEMORY.md"
echo "=== TSS MEMORY (auto-loaded) ==="
[[ -f "$MEM" ]] && cat "$MEM" || echo "MEMORY.md missing."
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  head_sha="$(git rev-parse --short HEAD 2>/dev/null || echo none)"
  mem_sha="$(grep -m1 -oP 'commit: \K\S+' "$MEM" 2>/dev/null || echo none)"
  echo; echo "=== GIT === HEAD: $head_sha"
  git log --oneline -3 2>/dev/null
  git status --short 2>/dev/null | head -10
  if [[ "$head_sha" != none && "$mem_sha" != none && "$head_sha" != "$mem_sha" ]]; then
    echo "⚠ DRIFT: commits after last memory update ($mem_sha → $head_sha). Reconcile MEMORY.md first."
  fi
fi
echo "=== END — load doc sections via agent-kit/INDEX.md ==="
exit 0
