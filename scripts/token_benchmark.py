#!/usr/bin/env python3
"""
Token Speed Benchmark — model-agnostic, multi-provider
Usage:
    python3 token_benchmark.py                          # compare all providers
    python3 token_benchmark.py fireworks               # test specific provider
    python3 token_benchmark.py minimax                 # test minimax only
"""

import urllib.request
import json
import time
import sys

PROVIDERS = {
    "fireworks-k2p5": {
        "url": "https://api.fireworks.ai/inference/v1/chat/completions",
        "api_key": "fw_Lv7Z5vCrqqWAyBvtsdQCtd",
        "model": "accounts/fireworks/routers/kimi-k2p5-turbo",
        "is_reasoning": False,
    },
    "fireworks-k2p6": {
        "url": "https://api.fireworks.ai/inference/v1/chat/completions",
        "api_key": "fw_Lv7Z5vCrqqWAyBvtsdQCtd",
        "model": "accounts/fireworks/models/kimi-k2p6",
        "is_reasoning": False,
    },
    "minimax": {
        "url": "https://api.minimax.io/v1/text/chatcompletion_v2",
        "api_key": "sk-cp-47dYVe9QJIj732X68hINusCgJhqXz6_XFcy1WIGQpl5N6cPL28EjF4dLl9Iqu3BR5NKNBw1WhiNn1oh-Gsk4MNLq_dN2AlmLDojSShq7RFwsNtMPuYCMzgk",
        "model": "MiniMax-M2.7-highspeed",
        "is_reasoning": True,  # output in reasoning_content, not content
    },
}

PROMPT = "Write exactly 400 words about distributed systems architecture. Be detailed and technical."
MAX_TOKENS = 500


def benchmark(name: str, cfg: dict, max_tokens: int = MAX_TOKENS) -> dict:
    print(f"\n{'='*60}")
    print(f"  {name.upper()} — {cfg['model']}")
    print(f"{'='*60}")

    payload = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": max_tokens,
        "stream": False,
    }

    req = urllib.request.Request(
        cfg["url"],
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            elapsed = time.time() - start
            data = json.loads(resp.read())

            if cfg["is_reasoning"]:
                content = data.get("choices", [{}])[0].get("message", {}).get("reasoning_content", "")
                completion_tokens = data.get("usage", {}).get("completion_tokens", 0)
            else:
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                completion_tokens = data.get("usage", {}).get("completion_tokens", 0)

            tps = completion_tokens / elapsed if elapsed > 0 else 0

            print(f"  Wall clock:   {elapsed:.3f}s")
            print(f"  Completion:   {completion_tokens} tokens")
            print(f"  Content:      {len(content)} chars")
            print(f"  Throughput:   ~{tps:.2f} tokens/sec")

            return {"provider": name, "model": cfg["model"], "elapsed": elapsed,
                    "tokens": completion_tokens, "tps": tps}

    except Exception as e:
        print(f"  ERROR: {e}")
        return {"provider": name, "model": cfg["model"], "elapsed": 0, "tokens": 0, "tps": 0}


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(PROVIDERS.keys())

    print(f"\n{'='*60}")
    print("  TOKEN SPEED BENCHMARK")
    print(f"{'='*60}")
    print(f"  Prompt:  {PROMPT[:60]}...")
    print(f"  Max:     {MAX_TOKENS} tokens")
    print(f"  Targets: {', '.join(targets)}")

    results = []
    for name in targets:
        if name not in PROVIDERS:
            print(f"\nUnknown provider: {name}")
            print(f"Available: {', '.join(PROVIDERS.keys())}")
            continue
        r = benchmark(name, PROVIDERS[name])
        results.append(r)

    if results:
        print(f"\n{'='*60}")
        print("  SUMMARY")
        print(f"{'='*60}")
        print(f"  {'Provider':<16}  {'Model':<45}  {'Tok/s':>8}  {'Tokens':>8}  {'Time':>8}")
        print(f"  {'-'*16}  {'-'*45}  {'-'*8}  {'-'*8}  {'-'*8}")
        for r in results:
            print(f"  {r['provider']:<16}  {r['model']:<45}  {r['tps']:>8.2f}  {r['tokens']:>8}  {r['elapsed']:>8.3f}s")


if __name__ == "__main__":
    main()
