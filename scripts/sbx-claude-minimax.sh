#!/usr/bin/env bash
# Setup script: configure `sbx run claude` for the MiniMax (api.minimax.io) proxy.
# Idempotent — safe to re-run.
#
# What it does:
#   1. Allow egress to api.minimax.io in the sbx proxy policy
#   2. Read the API key from immo-scouter/.claude/settings.local.json
#   3. Store it as an sbx secret for the claude service
#   4. Print the one-liner the user runs to launch

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SETTINGS="$PROJECT_DIR/.claude/settings.local.json"

if [ ! -f "$SETTINGS" ]; then
    echo "ERROR: $SETTINGS not found. Run from immo-scouter project root." >&2
    exit 1
fi

API_BASE=$(python3 -c "import json; d=json.load(open('$SETTINGS')); print(d['env']['ANTHROPIC_BASE_URL'])")
API_TOKEN=$(python3 -c "import json; d=json.load(open('$SETTINGS')); print(d['env']['ANTHROPIC_AUTH_TOKEN'])")
API_HOST=$(echo "$API_BASE" | sed -E 's|https?://||; s|/.*||')

echo "→ Allowing sbx proxy egress to $API_HOST"
sbx policy allow network "$API_HOST" 2>&1 | tail -1

echo "→ Storing MiniMax API key as sbx secret (service: anthropic, scope: global)"
echo "$API_TOKEN" | sbx secret set -g anthropic 2>&1 | tail -2

echo ""
echo "✅ Setup complete."
echo ""
echo "Now run:"
echo "  cd $PROJECT_DIR"
echo "  sbx run claude -- -p \"Reply with exactly one word: OK\""
echo ""
echo "Or interactively:"
echo "  sbx run claude"
echo "  (then type a message)"
echo ""
echo "Note: inside the container, ANTHROPIC_BASE_URL is set to a placeholder"
echo "via the proxy. The proxy rewrites the URL + auth header on outbound"
echo "to https://$API_HOST."
