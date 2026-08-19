import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_top5_help_starts_without_numpy():
    probe = """
import builtins
import runpy
import sys
from pathlib import Path

script_path = Path(sys.argv[1])
sys.path.insert(0, str(script_path.parent))
original_import = builtins.__import__


def guarded_import(name, *args, **kwargs):
    if name == "numpy" or name.startswith("numpy."):
        raise ModuleNotFoundError("No module named 'numpy'")
    return original_import(name, *args, **kwargs)


builtins.__import__ = guarded_import
sys.argv = [str(script_path), "--help"]
runpy.run_path(str(script_path), run_name="__main__")
"""
    result = subprocess.run(
        [sys.executable, "-c", probe, str(REPOSITORY_ROOT / "Project" / "run_top5.py")],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"Top5 startup failed without numpy.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
