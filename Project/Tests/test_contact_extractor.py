import builtins
import importlib
import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_seller_classification_does_not_require_optional_outreach_dependencies(monkeypatch):
    module_name = "Application.outreach.contact_extractor"
    for loaded_name in list(sys.modules):
        if (
            loaded_name == "Application.outreach"
            or loaded_name.startswith("Application.outreach.")
            or loaded_name == "bleach"
            or loaded_name.startswith("selenium")
        ):
            sys.modules.pop(loaded_name, None)

    real_import = builtins.__import__

    def import_without_selenium(name, *args, **kwargs):
        if name == "selenium" or name.startswith("selenium."):
            raise ModuleNotFoundError("No module named 'selenium'")
        if name == "bleach":
            raise ModuleNotFoundError("No module named 'bleach'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_selenium)
    module = importlib.import_module(module_name)

    assert module.classify_seller("Makler GmbH") == "agency"
    assert "Application.outreach.email_sender" not in sys.modules
