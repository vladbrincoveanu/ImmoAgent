#!/usr/bin/env python3
"""context-guard: enforce handoff + /clear instead of autocompact.

Events:
- PreCompact(auto): BLOCK autocompact; instruct model to write handoff + ask for /clear.
- UserPromptSubmit: warn once per 10%-band above 70% context.
- Stop: at >=80% with no recent handoff, block stop once and demand the handoff.
- SessionStart(startup|clear): inject newest handoff (<24h) into fresh context.

Context size is read from the last `usage` block in the transcript JSONL.
Fail-safe: any parse failure -> exit 0, no interference.
"""
import glob, json, os, sys, time

LIMIT = int(os.environ.get("CTX_LIMIT_TOKENS", "120000"))
WARN, HARD = 0.70, 0.80

try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)

ev = d.get("hook_event_name", "")
sid = d.get("session_id", "ns")
proj = os.environ.get("CLAUDE_PROJECT_DIR") or "."
hdir = os.path.join(proj, ".claude", "handoffs")

HANDOFF_SPEC = ("write a <=10-line handoff to .claude/handoffs/<YYYY-MM-DD-HHMM>.md "
                "(Goal / Done / Next single step / Open risks / Key files+commands)")

def ctx_pct():
    tp = d.get("transcript_path", "")
    if not tp or not os.path.isfile(tp):
        return 0.0
    try:
        with open(tp, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 400_000))
            lines = f.read().decode("utf-8", "ignore").splitlines()
        for line in reversed(lines):
            try:
                e = json.loads(line)
            except Exception:
                continue
            u = (e.get("message") or {}).get("usage") or {}
            if u.get("input_tokens") is not None:
                tot = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                       + u.get("cache_creation_input_tokens", 0))
                return tot / LIMIT
    except Exception:
        pass
    return 0.0

def newest_handoff():
    fs = sorted(glob.glob(os.path.join(hdir, "*.md")), key=os.path.getmtime)
    return fs[-1] if fs else None

if ev == "PreCompact":
    if d.get("trigger") == "auto":
        print(json.dumps({"decision": "block", "reason":
            "Autocompact BLOCKED by context-guard. Stop current work. 1) " + HANDOFF_SPEC +
            ". 2) Tell the user: run /clear and resume; the handoff autoloads in the next session."}))
    sys.exit(0)

if ev == "UserPromptSubmit":
    p = ctx_pct()
    if p >= WARN:
        s = f"/tmp/ctxguard-{sid}-{int(p * 10)}"
        if not os.path.exists(s):
            open(s, "w").close()
            print(f"[context-guard] Context at {p:.0%}. Finish the current task only; "
                  f"do not start new work. Then {HANDOFF_SPEC} and ask the user to /clear.")
    sys.exit(0)

if ev == "Stop":
    if d.get("stop_hook_active"):
        sys.exit(0)
    p = ctx_pct()
    s = f"/tmp/ctxguard-stop-{sid}"
    nh = newest_handoff()
    fresh = nh and (time.time() - os.path.getmtime(nh) < 3600)
    if p >= HARD and not fresh and not os.path.exists(s):
        open(s, "w").close()
        print(json.dumps({"decision": "block", "reason":
            f"Context at {p:.0%} and no handoff in the last hour. Before stopping, " +
            HANDOFF_SPEC + ", then tell the user to /clear."}))
    sys.exit(0)

if ev == "SessionStart":
    if d.get("source") in ("startup", "clear"):
        nh = newest_handoff()
        if nh and (time.time() - os.path.getmtime(nh) < 86400):
            try:
                print(f"[context-guard] Resuming from handoff {os.path.basename(nh)}:\n"
                      + open(nh).read()[:3000])
            except Exception:
                pass
    sys.exit(0)
