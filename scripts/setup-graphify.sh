#!/usr/bin/env bash
# setup-graphify.sh — host-side one-shot to wire up the graphify skill.
#
# What it does (run on the host where graphify CLI is installed):
#   1. Confirms `graphify` is on PATH (installs via `uv tool install graphifyy` if not).
#   2. Runs `graphify update .` to refresh the stale graph.json (3 commits behind).
#   3. Runs `graphify hook install` to wire a post-commit hook that auto-rebuilds
#      the graph on every commit (incremental, AST-only, no LLM cost).
#
# After running, verify with:
#   stat -f "%Sm" graphify-out/graph.json        # mtime = today
#   graphify query "what calls MongoDBHandler"  # returns scoped subgraph
#   graphify hook status                        # reports post-commit installed
#
# Run from the repo root:
#   bash scripts/setup-graphify.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

step() { printf "\n\033[1;36m▸ %s\033[0m\n" "$*"; }
ok()   { printf "  \033[32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$*" >&2; }
die()  { printf "  \033[31m✗\033[0m %s\n" "$*" >&2; exit 1; }

step "1/4  check graphify CLI"
if ! command -v graphify >/dev/null 2>&1; then
  warn "graphify not on PATH — installing via uv tool"
  if ! command -v uv >/dev/null 2>&1; then
    die "uv not found. Install uv first: https://docs.astral.sh/uv/"
  fi
  uv tool install --upgrade graphifyy -q
  ok "installed graphifyy via uv"
else
  ok "graphify found: $(command -v graphify)"
fi
graphify --version
ok "version: $(graphify --version 2>&1 | head -1)"

step "2/4  confirm skill files are restored"
[[ -f .claude/skills/graphify/SKILL.md ]] || die "SKILL.md missing — run /graphify or restore from relentless/graphify-first-rule"
[[ -f .claude/skills/graphify/.graphify_version ]] || die ".graphify_version missing"
ok "SKILL.md: $(wc -l < .claude/skills/graphify/SKILL.md) lines, version: $(cat .claude/skills/graphify/.graphify_version)"

step "3/4  rebuild graph (replaces stale 2026-06-12 build)"
if [[ -f graphify-out/graph.json ]]; then
  GRAPH_MTIME=$(stat -f "%Sm" graphify-out/graph.json 2>/dev/null || stat -c "%y" graphify-out/graph.json)
  warn "existing graph.json mtime: $GRAPH_MTIME — will be replaced"
fi
graphify update . || {
  warn "incremental update failed — falling back to full rebuild"
  graphify .
}
ok "graph rebuilt: $(stat -f "%Sm" graphify-out/graph.json 2>/dev/null || stat -c "%y" graphify-out/graph.json)"

step "4/4  install post-commit hook (auto-update forever)"
if [[ -f .git/hooks/post-commit ]] && ! grep -q "graphify" .git/hooks/post-commit; then
  warn "existing post-commit hook without graphify — graphify hook install will append, not replace"
fi
graphify hook install
graphify hook status
ok "post-commit hook active — every commit now triggers graphify update"

step "verify"
printf "  graph.json mtime: %s\n" "$(stat -f '%Sm' graphify-out/graph.json 2>/dev/null || stat -c '%y' graphify-out/graph.json)"
printf "  test query:       graphify query \"what calls MongoDBHandler\"\n"
printf "  auto-update test: touch Project/Application/main.py && git add -A && git commit -m 'test' && stat -f '%%Sm' graphify-out/graph.json\n"
printf "  cleanup:          git reset --soft HEAD~1  # undo the test commit\n"
ok "done. graphify is now wired up and self-maintaining."
