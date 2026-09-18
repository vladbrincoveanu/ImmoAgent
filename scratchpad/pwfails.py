"""Print the failing spec titles from a Playwright JSON-reporter log.

Usage: python3 scratchpad/pwfails.py <log-path>

The rtk tee logs end with the reporter's JSON object, so we parse from the last
top-level "{" at column 0 to EOF rather than trusting the whole file to be JSON.
"""
import json
import sys

path = sys.argv[1]
txt = open(path, encoding="utf-8", errors="replace").read()
# The log is normally the reporter's JSON verbatim; tolerate a leading banner by
# falling back to the first "{" at the start of a line.
try:
    data = json.loads(txt)
except json.JSONDecodeError:
    start = txt.find("\n{\n")
    if start == -1:
        sys.exit("no JSON object found in log")
    data = json.loads(txt[start:])

fails = []


def walk(suite, file_hint=""):
    f = suite.get("file", file_hint)
    for spec in suite.get("specs", []):
        if not spec.get("ok", True):
            fails.append((f, spec["title"]))
    for sub in suite.get("suites", []):
        walk(sub, f)


for s in data.get("suites", []):
    walk(s)

print(f"{len(fails)} failing")
for f, t in sorted(fails):
    print(f"{f} :: {t}")
