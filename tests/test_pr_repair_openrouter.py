import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / ".github" / "pr-repair-openrouter.py"
SPEC = importlib.util.spec_from_file_location("pr_repair_openrouter", MODULE_PATH)
pr_repair = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(pr_repair)


def test_request_body_targets_openrouter_nemotron_without_unsupported_json_mode():
    body = pr_repair.build_request_body(
        instructions="Review the change.",
        context={"pull_request": {"base": "main"}},
        diff="diff --git a/example.py b/example.py",
    )

    assert body["model"] == "nvidia/nemotron-3-ultra-550b-a55b:free"
    assert "response_format" not in body


def test_model_patch_cannot_delete_protected_workflow_files():
    patch = """diff --git a/.github/workflows/main.yml b/.github/workflows/main.yml
--- a/.github/workflows/main.yml
+++ /dev/null
"""

    assert pr_repair.patch_targets_protected_path(patch) is True
