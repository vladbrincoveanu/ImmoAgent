"""Config discovery stays within the checkout containing the Python source."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.helpers import utils


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    repo = tmp_path / "home/runner/work/ImmoAgent/ImmoAgent"
    source = repo / "Project/Application/helpers/utils.py"
    source.parent.mkdir(parents=True)
    (repo / "README.md").touch()
    (repo / "dashboard").mkdir()
    (repo / "dashboard/config.json").write_text('{"PRICE_PER_SQM": 5000}')
    monkeypatch.setattr(utils, "__file__", str(source))
    monkeypatch.setattr(utils, "_config", None)
    monkeypatch.setattr(utils, "_project_root", None)
    monkeypatch.setattr(os, "environ", {})
    monkeypatch.chdir(repo)
    # Reproduce the old hardcoded CI scan against real files without /home access.
    walk = os.walk
    monkeypatch.setattr(os, "walk", lambda path, **kwargs: list(walk(repo.parent, **kwargs)))
    return repo


def test_ci_without_scraper_config_ignores_dashboard(checkout, monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/ci-test")

    config = utils.load_config()

    assert "PRICE_PER_SQM" not in config
    assert config["willhaben"]["search_url"].startswith("https://www.willhaben.at/")
    assert config["immo_kurier"]["search_url"].startswith("https://www.dibeo.at/obj/wie/b")
    assert config["mongodb_uri"] == "mongodb://localhost:27017/ci-test"


@pytest.mark.parametrize("cwd", [".", "Project", "dashboard"])
def test_worktree_does_not_load_parent_checkout_config(tmp_path, monkeypatch, cwd):
    (tmp_path / "config.json").write_text('{"source": "parent-checkout"}')
    repo = tmp_path / ".worktrees/fix"
    source = repo / "Project/Application/helpers/utils.py"
    source.parent.mkdir(parents=True)
    (repo / "README.md").touch()
    (repo / "dashboard").mkdir()
    monkeypatch.setattr(utils, "__file__", str(source))
    monkeypatch.setattr(utils, "_config", None)
    monkeypatch.setattr(utils, "_project_root", None)
    monkeypatch.setattr(os, "environ", {})
    monkeypatch.chdir(repo / cwd)

    assert utils.load_config()["source"] == "willhaben"


@pytest.mark.parametrize("location", ["config.json", "Project/config.json"])
@pytest.mark.parametrize("cwd", [".", "Project", "dashboard", ".."])
def test_checkout_config_overrides_defaults_from_any_cwd(checkout, monkeypatch, location, cwd):
    (checkout / location).write_text(json.dumps({
        "source": "custom-feed",
        "max_pages": 2,
        "immo_kurier": {"search_url": "https://example.com/custom-feed"},
    }))
    monkeypatch.chdir(checkout / cwd)
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/override-test")

    config = utils.load_config()

    assert config["source"] == "custom-feed"
    assert config["max_pages"] == 2
    assert config["immo_kurier"]["search_url"] == "https://example.com/custom-feed"
    assert config["mongodb_uri"] == "mongodb://localhost:27017/override-test"


def test_repo_root_config_precedes_project_config(checkout, monkeypatch):
    (checkout / "config.json").write_text('{"source": "root-config"}')
    (checkout / "Project/config.json").write_text('{"source": "project-config"}')
    monkeypatch.chdir(checkout / "Project")

    assert utils.load_config()["source"] == "root-config"


@pytest.mark.parametrize("invalid", ["{broken", "[]"])
def test_invalid_root_config_falls_back_to_project_config(checkout, invalid):
    (checkout / "config.json").write_text(invalid)
    (checkout / "Project/config.json").write_text('{"source": "project-config"}')

    assert utils.load_config()["source"] == "project-config"
