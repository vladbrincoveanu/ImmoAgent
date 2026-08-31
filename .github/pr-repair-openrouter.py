import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"


def command(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout


def build_request_body(instructions, context, diff, model=None):
    return {
        "model": model or DEFAULT_MODEL,
        "temperature": 0.1,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a careful software repair agent. Return JSON only with exactly these keys: "
                    "action (one of patch, no_change, blocked), patch (a unified git diff string), "
                    "summary (string), and tests (array of strings). Never return shell commands."
                ),
            },
            {
                "role": "user",
                "content": (
                    instructions
                    + "\n\nCurrent PR state:\n"
                    + json.dumps(context, indent=2)
                    + "\n\nCurrent PR diff:\n```diff\n"
                    + diff
                    + "\n```\n"
                    + "Return a minimal patch only for verified actionable findings. "
                    + "If no safe fix is possible, return action=blocked or action=no_change "
                    + "and an empty patch."
                ),
            },
        ],
    }


def _parse_decision(content):
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(content)


def _candidate_paths(patch_text):
    candidates = set()
    for line in patch_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("diff --git "):
            tokens = stripped.split()
            if len(tokens) >= 4:
                candidates.add(tokens[2][2:] if tokens[2].startswith(("a/", "b/")) else tokens[2])
                candidates.add(tokens[3][2:] if tokens[3].startswith(("a/", "b/")) else tokens[3])
        elif stripped.startswith("--- ") or stripped.startswith("+++ "):
            path = stripped[4:]
            if path.startswith(("a/", "b/")):
                path = path[2:]
            candidates.add(path)
        elif stripped.startswith("rename from ") or stripped.startswith("rename to "):
            candidates.add(stripped.split(maxsplit=2)[2])
    return candidates


def _path_is_protected(path):
    if path.startswith("/dev/null") or path in {"/dev/null", "dev/null"}:
        return False
    normalized = path
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return (
        normalized.startswith("/")
        or normalized.startswith(".github/workflows/")
        or normalized.startswith(".github/pr-repair-")
        or normalized in {".env", ".env.local", ".gitconfig"}
        or ".." in normalized.split("/")
    )


def patch_targets_protected_path(patch_text):
    return any(_path_is_protected(path) for path in _candidate_paths(patch_text))


def main():
    workspace = Path(os.environ.get("GITHUB_WORKSPACE", ".."))
    with open(workspace / "pr-repair-context.json", encoding="utf-8") as handle:
        context = json.load(handle)
    with open(workspace / "pr-repair-prompt.md", encoding="utf-8") as handle:
        instructions = handle.read()

    base_ref = context["pull_request"]["base"]
    diff = command("git", "-C", str(workspace), "diff", "--no-ext-diff", f"origin/{base_ref}...HEAD")
    if len(diff) > 120_000:
        diff = diff[:120_000] + "\n[diff truncated]\n"

    request_body = build_request_body(
        instructions,
        context,
        diff,
        model=os.environ.get("OPENROUTER_MODEL"),
    )
    request = urllib.request.Request(
        os.environ.get("OPENROUTER_ENDPOINT", DEFAULT_ENDPOINT),
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/vladbrincoveanu/ImmoAgent",
            "X-OpenRouter-Title": "PR Repair Agent",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"OpenRouter request failed ({error.code}): {detail}") from error

    content = result["choices"][0]["message"]["content"]
    decision = _parse_decision(content)

    with open(workspace / "repair-result.json", "w", encoding="utf-8") as handle:
        json.dump(decision, handle, indent=2)

    with open(workspace / "repair-result.md", "w", encoding="utf-8") as handle:
        handle.write(decision.get("summary", "No summary returned.") + "\n")

    patch_text = decision.get("patch") or ""
    if decision.get("action") != "patch" or not patch_text.strip():
        return

    if patch_targets_protected_path(patch_text):
        print("Refusing model patch for a protected path")
        return
    with tempfile.NamedTemporaryFile("w", suffix=".patch", encoding="utf-8") as handle:
        handle.write(patch_text)
        handle.flush()
        subprocess.run(["git", "-C", str(workspace), "apply", "--check", handle.name], check=True)
        subprocess.run(["git", "-C", str(workspace), "apply", handle.name], check=True)


if __name__ == "__main__":
    main()
