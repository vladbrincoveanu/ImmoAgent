#!/usr/bin/env python3
"""PreToolUse(Bash) linter: deny known token-noisy command forms with a
corrective suggestion. Deterministic, conservative — only fires on clear
violations; anything ambiguous is allowed.
"""
import json, os, re, sys

try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)

cmd = str((d.get("tool_input") or {}).get("command", ""))
if not cmd:
    sys.exit(0)

# Already disciplined? Pipes/filters/limits present -> allow.
TAMED = re.compile(r"(\b(rtk|head|tail|grep|rg|wc|awk)\b|sed -n|--stat|--shortstat|"
                   r"--name-only|--name-status|--reporter|\s-q\b|--quiet|--oneline|2>/dev/null)")

def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": "[rtk-enforce] " + reason}}))
    sys.exit(0)

if TAMED.search(cmd):
    sys.exit(0)

# 1. git diff/log/show without limiting flags or pipe
if re.search(r"\bgit\s+(diff|show)\b", cmd):
    deny("Unbounded git diff/show. Use `git diff --stat` first; then targeted "
         "`git diff -- <path> | head -100` only for files you must inspect.")
if re.search(r"\bgit\s+log\b", cmd):
    deny("Use `git log --oneline -20` (or -n with --stat) instead of full git log.")

# 2. pytest without quiet flags
if re.search(r"\bpytest\b", cmd):
    deny("Run pytest quietly: `pytest -q --tb=short`. Add -x when bisecting a failure.")

# 3. playwright test without a reporter
if re.search(r"\bplaywright\s+test\b", cmd):
    deny("Run with `--reporter=dot` while iterating (line for the final gate), "
         "per .claude/rules/ui-testing.md.")

# 4. bare cat of a large file
m = re.match(r"\s*cat\s+([^\s|;&><]+)\s*$", cmd)
if m:
    f = os.path.expanduser(m.group(1))
    try:
        if os.path.isfile(f) and os.path.getsize(f) > 20_000:
            deny(f"{m.group(1)} is {os.path.getsize(f)//1024}KB. Use Read with "
                 "offset/limit, or `head -50` / `grep <pattern>` instead of cat.")
    except OSError:
        pass

# 5. npm build/test unpiped
if re.search(r"\bnpm\s+(run\s+build|test|run\s+lint)\b", cmd):
    deny("Pipe noisy npm output: append `2>&1 | tail -30` (build) or "
         "`2>&1 | grep -iE \"error|fail\" -A3` (test/lint).")

sys.exit(0)
