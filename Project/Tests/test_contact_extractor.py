import builtins
import importlib
import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _load_contact_extractor_without_optional_dependencies(monkeypatch):
    module_name = "Application.outreach.contact_extractor"
    def is_probe_module(loaded_name):
        return (
            loaded_name == "Application.outreach"
            or loaded_name.startswith("Application.outreach.")
            or loaded_name == "bleach"
            or loaded_name.startswith("bleach.")
            or loaded_name == "selenium"
            or loaded_name.startswith("selenium.")
        )

    previous_modules = {
        loaded_name: sys.modules[loaded_name]
        for loaded_name in list(sys.modules)
        if is_probe_module(loaded_name)
    }
    application_module = sys.modules.get("Application")
    previous_outreach_attribute = (
        getattr(application_module, "outreach")
        if application_module is not None and hasattr(application_module, "outreach")
        else None
    )

    for loaded_name in list(sys.modules):
        if is_probe_module(loaded_name):
            sys.modules.pop(loaded_name, None)

    real_import = builtins.__import__

    def import_without_selenium(name, *args, **kwargs):
        if name == "selenium" or name.startswith("selenium."):
            raise ModuleNotFoundError("No module named 'selenium'")
        if name == "bleach" or name.startswith("bleach."):
            raise ModuleNotFoundError("No module named 'bleach'")
        return real_import(name, *args, **kwargs)

    try:
        monkeypatch.setattr(builtins, "__import__", import_without_selenium)
        return importlib.import_module(module_name)
    finally:
        for loaded_name in list(sys.modules):
            if is_probe_module(loaded_name):
                sys.modules.pop(loaded_name, None)
        sys.modules.update(previous_modules)
        if application_module is not None:
            if previous_outreach_attribute is None:
                application_module.__dict__.pop("outreach", None)
            else:
                application_module.outreach = previous_outreach_attribute


def test_seller_classification_does_not_require_optional_outreach_dependencies(monkeypatch):
    module = _load_contact_extractor_without_optional_dependencies(monkeypatch)

    assert module.classify_seller("Makler GmbH") == "agency"
    assert "Application.outreach.email_sender" not in sys.modules


def test_optional_dependency_probe_restores_import_state(monkeypatch):
    selenium_module = importlib.import_module("selenium")
    module_name = "Application.outreach.contact_extractor"
    previous_contact_module = sys.modules.get(module_name)

    module = _load_contact_extractor_without_optional_dependencies(monkeypatch)

    assert module.classify_seller("Makler GmbH") == "agency"
    assert sys.modules["selenium"] is selenium_module
    if previous_contact_module is None:
        assert module_name not in sys.modules
    else:
        assert sys.modules[module_name] is previous_contact_module
