import ast
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1] / "Project"
LOCAL_MODULES = {"Application", "Domain", "Integration"}


def _top_level_imports(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imports.add(node.module.split(".", 1)[0])
    return imports


def _declared_packages(requirements_path: Path) -> set[str]:
    packages = set()
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        package = re.split(r"[<>=!~;\[]", line, maxsplit=1)[0]
        packages.add(package.replace("-", "_").lower())
    return packages


def test_top5_entrypoint_imports_are_declared():
    imports = _top_level_imports(PROJECT_ROOT / "run_top5.py")
    declared = _declared_packages(PROJECT_ROOT / "requirements.txt")
    undeclared = sorted(
        name
        for name in imports
        if name not in sys.stdlib_module_names
        and name not in LOCAL_MODULES
        and name.lower() not in declared
    )

    assert undeclared == [], (
        "Project/run_top5.py imports packages that the workflow does not install: "
        + ", ".join(undeclared)
    )
