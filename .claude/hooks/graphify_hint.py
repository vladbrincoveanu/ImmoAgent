#!/usr/bin/env python3
"""PreToolUse hook: nudge toward graphify, max once per session per kind.

Replaces the inline always-firing hooks. Each repeated injection costs
~80 tokens AND breaks the prompt-cache prefix, so emit the hint only the
first time per session (sentinel keyed by session_id).
"""
import json, os, sys

try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)

if not os.path.isfile("graphify-out/graph.json"):
    sys.exit(0)

tool = d.get("tool_name", "")
ti = d.get("tool_input", {}) or {}
sid = d.get("session_id", "nosession")

if tool == "Bash":
    cmd = str(ti.get("command", ""))
    if not any(k in cmd for k in ("grep", "rg ", "ripgrep", "find ", "fd ", "ack ", "ag ")):
        sys.exit(0)
    kind = "bash"
    hint = ("graphify: knowledge graph at graphify-out/. For focused questions run "
            "`graphify query \"<question>\"` (scoped subgraph, much smaller than grep output).")
else:  # Read | Glob
    s = (str(ti.get("file_path") or "") + " " + str(ti.get("pattern") or "") + " " +
         str(ti.get("path") or "")).lower().replace("\\", "/")
    exts = (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb", ".c", ".h",
            ".cpp", ".hpp", ".cc", ".cs", ".kt", ".swift", ".php", ".scala", ".lua", ".sh",
            ".md", ".rst", ".txt", ".mdx")
    if "graphify-out/" in s or not any(e in s for e in exts):
        sys.exit(0)
    kind = "read"
    hint = ("graphify: for codebase questions prefer `graphify query/explain/path` over reading "
            "files one by one. Read raw files only to modify/debug specific code.")

sentinel = f"/tmp/graphify-hint-{sid}-{kind}"
if os.path.exists(sentinel):
    sys.exit(0)
open(sentinel, "w").close()

print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": hint}}))
