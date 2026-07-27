import sys
import types
import importlib.util
from pathlib import Path


def load_run_module():
    path = Path(__file__).resolve().parents[2] / "run.py"
    loader = importlib.machinery.SourceFileLoader("llm_run", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def test_fallback_required_missing():
    mod = load_run_module()
    schema = {"type": "object", "required": ["a"]}
    structured = {}
    errors = mod.validate_against_schema(structured, schema)
    assert any("required property missing: a" in e for e in errors)


def test_fallback_type_mismatch():
    mod = load_run_module()
    schema = {"type": "object", "properties": {"x": {"type": "string"}}}
    structured = {"x": 1}
    errors = mod.validate_against_schema(structured, schema)
    assert any("x: expected string" in e for e in errors)


def test_jsonschema_path():
    # Prepare a fake jsonschema module exposing Draft7Validator
    class FakeError:
        def __init__(self, path, message):
            self.path = path
            self.message = message

    class FakeValidator:
        def __init__(self, schema):
            pass

        def iter_errors(self, obj):
            yield FakeError(["x"], "is not of type string")

    fake = types.SimpleNamespace(Draft7Validator=FakeValidator)
    sys.modules["jsonschema"] = fake
    try:
        mod = load_run_module()
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        structured = {"x": 1}
        errors = mod.validate_against_schema(structured, schema)
        assert any("x: is not of type string" in e for e in errors)
    finally:
        del sys.modules["jsonschema"]
