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


def test_model_patch_cannot_delete_protected_paths_in_no_prefix_form():
    patch = """diff --git a/.github/workflows/main.yml b/.github/workflows/main.yml
deleted file mode 100644
--- .github/workflows/main.yml
+++ /dev/null
@@ -1,3 +0,0 @@
-...workflow content...
"""

    assert pr_repair.patch_targets_protected_path(patch) is True


def test_model_patch_cannot_delete_protected_env_via_no_prefix():
    patch = """--- .env
+++ /dev/null
@@ -1,3 +0,0 @@
-TOKEN=secret
"""

    assert pr_repair.patch_targets_protected_path(patch) is True


def test_model_patch_cannot_target_absolute_paths():
    patch = """--- /etc/passwd
+++ /dev/null
"""

    assert pr_repair.patch_targets_protected_path(patch) is True


def test_model_patch_cannot_rename_away_protected_workflows():
    patch = """diff --git a/.github/workflows/main.yml b/other.yml
similarity index 100%
rename from .github/workflows/main.yml
rename to other.yml
"""

    assert pr_repair.patch_targets_protected_path(patch) is True


def test_model_patch_cannot_rename_into_protected_workflows():
    patch = """diff --git a/other.yml b/.github/workflows/main.yml
similarity index 100%
rename from other.yml
rename to .github/workflows/main.yml
"""

    assert pr_repair.patch_targets_protected_path(patch) is True


def test_model_patch_cannot_traverse_through_dot_segments():
    patch = """--- a/./.github/workflows/main.yml
+++ b/./.github/workflows/main.yml
"""

    assert pr_repair.patch_targets_protected_path(patch) is True


def test_regular_patch_outside_protected_paths_is_allowed():
    patch = """diff --git a/src/agent.py b/src/agent.py
--- a/src/agent.py
+++ b/src/agent.py
@@ -1,3 +1,4 @@
 def run():
-    pass
+    return True
"""

    assert pr_repair.patch_targets_protected_path(patch) is False
