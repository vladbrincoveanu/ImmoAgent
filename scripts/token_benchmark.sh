#!/bin/bash
# Token Speed Benchmark — curl-based, model-agnostic
# Usage: ./token_benchmark.sh [PROVIDER] [MODEL] [API_KEY]
#
# Providers: fireworks (default), minimax
#
# Examples:
#   ./token_benchmark.sh fireworks "accounts/fireworks/routers/kimi-k2p5-turbo" "fw_YOUR_KEY"
#   ./token_benchmark.sh minimax "MiniMax-Text-01" "YOUR_MINIMAX_KEY"
#   ./token_benchmark.sh  # uses defaults: fireworks + kimi-k2p5-turbo

set -e

PROVIDER="${1:-fireworks}"
MODEL="${2:-accounts/fireworks/routers/kimi-k2p5-turbo}"
API_KEY="${3:-fw_Lv7Z5vCrqqWAyBvtsdQCtd}"
MAX_TOKENS=500
PROMPT="Write exactly 400 words about distributed systems architecture. Be detailed and technical."

case "$PROVIDER" in
  fireworks)
    BASE_URL="https://api.fireworks.ai/inference"
    ;;
  minimax)
    BASE_URL="https://api.minimax.io/anthropic"
    ;;
  *)
    echo "Unknown provider: $PROVIDER"
    echo "Supported: fireworks, minimax"
    exit 1
    ;;
esac

echo "=========================================="
echo "Token Speed Benchmark"
echo "=========================================="
echo "Provider:   $PROVIDER"
echo "Model:      $MODEL"
echo "Base URL:   $BASE_URL"
echo "Max Tokens: $MAX_TOKENS"
echo "=========================================="

# Non-streaming test — measures total throughput
echo ""
echo "[Test 1/2] Non-streaming (total throughput)"

JSON_PAYLOAD=$(cat <<JSON
{
  "model": "$MODEL",
  "messages": [{"role": "user", "content": "$PROMPT"}],
  "max_tokens": $MAX_TOKENS,
  "stream": false
}
JSON
)

START=$(date +%s.%N)

RESPONSE=$(curl -s -w "\nTTFB:%{time_starttransfer}s\nTOTAL:%{time_total}s" \
  -X POST "$BASE_URL/v1/chat/completions" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "$JSON_PAYLOAD")

END=$(date +%s.%N)
DURATION=$(echo "$END - $START" | bc)

# Extract timing (curl -w outputs "TTFB:Ns" format)
TTFB=$(echo "$RESPONSE" | grep "TTFB:" | sed 's/TTFB://' | sed 's/s//')
TOTAL=$(echo "$RESPONSE" | grep "TOTAL:" | sed 's/TOTAL://' | sed 's/s//')

# Extract JSON part (everything before TTFB line)
JSON_RESPONSE=$(echo "$RESPONSE" | sed '/TTFB:/q' | sed '$ d')

echo "Wall clock:   ${DURATION}s"
echo "TTFB:         ${TTFB}s"
echo "Total time:   ${TOTAL}s"

COMPLETION_TOKENS=$(echo "$JSON_RESPONSE" | jq -r '.usage.completion_tokens // empty')
if [ -n "$COMPLETION_TOKENS" ] && [ "$TOTAL" != "0" ]; then
    TPS=$(echo "scale=2; $COMPLETION_TOKENS / $TOTAL" | bc)
    echo "Completion:   ${COMPLETION_TOKENS} tokens"
    echo "Throughput:   ~${TPS} tokens/sec"
fi

# Streaming test — measures time to first token
echo ""
echo "[Test 2/2] Streaming (time to first token)"

STREAM_JSON=$(cat <<JSON
{
  "model": "$MODEL",
  "messages": [{"role": "user", "content": "$PROMPT"}],
  "max_tokens": $MAX_TOKENS,
  "stream": true
}
JSON
)

TTFT_CAPTURED=false
TOKEN_COUNT=0
START_TTFT=$(date +%s.%N)

curl -s -N \
  -X POST "$BASE_URL/v1/chat/completions" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d "$STREAM_JSON" 2>&1 | while IFS= read -r line; do
    if [[ "$line" == data:* ]]; then
        CONTENT=$(echo "$line" | sed 's/^data: //')
        if [[ "$CONTENT" != "[DONE]" ]]; then
            DELTA=$(echo "$CONTENT" | jq -r '.choices[0].delta.content // empty' 2>/dev/null || echo "")
            if [ -n "$DELTA" ]; then
                ((TOKEN_COUNT++))
                if [ "$TTFT_CAPTURED" = false ]; then
                    END_TTFT=$(date +%s.%N)
                    TTFT=$(echo "$END_TTFT - $START_TTFT" | bc)
                    echo "Time to 1st token: ${TTFT}s"
                    TTFT_CAPTURED=true
                fi
            fi
        fi
    fi
done

echo "Streaming tokens received: ${TOKEN_COUNT}"
echo ""
echo "Done."
