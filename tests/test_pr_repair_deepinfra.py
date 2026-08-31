import json
import runpy
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REPAIR_SCRIPT = ROOT / ".github" / "pr-repair-deepinfra.py"


class _Response:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._body


def _git(*args, cwd):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )


def test_invalid_model_patch_is_reported_as_noop(monkeypatch, tmp_path, capsys):
    _git("init", cwd=tmp_path)
    _git("branch", "-M", "main", cwd=tmp_path)
    _git("config", "user.name", "Test User", cwd=tmp_path)
    _git("config", "user.email", "test@example.com", cwd=tmp_path)
    tracked_file = tmp_path / "tracked.txt"
    tracked_file.write_text("unchanged", encoding="utf-8")
    _git("add", "tracked.txt", cwd=tmp_path)
    _git("commit", "-m", "initial", cwd=tmp_path)
    _git("update-ref", "refs/remotes/origin/main", "HEAD", cwd=tmp_path)

    (tmp_path / "pr-repair-context.json").write_text(
        json.dumps({"pull_request": {"base": "main"}}), encoding="utf-8"
    )
    (tmp_path / "pr-repair-prompt.md").write_text("Repair safely.", encoding="utf-8")
    response_payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "action": "patch",
                            "patch": "not a unified diff",
                            "summary": "The model proposed a malformed patch.",
                            "tests": [],
                        }
                    )
                }
            }
        ]
    }


    def fake_urlopen(_request, timeout):
        assert timeout == 300
        return _Response(response_payload)

    monkeypatch.setenv("GITHUB_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("DEEPINFRA_TOKEN", "test-token")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(SystemExit) as raised:
        runpy.run_path(str(REPAIR_SCRIPT), run_name="__main__")

    assert raised.value.code == 0
    assert tracked_file.read_text(encoding="utf-8") == "unchanged"
    assert "invalid model patch" in capsys.readouterr().out.lower()
