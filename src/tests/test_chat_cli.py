import importlib
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("CORPS_PYTHON_SCRIPTS_DIR", str(ROOT))
sys.path.insert(0, str(ROOT))

import chat_cli  # noqa: E402


def make_cli():
    cli = chat_cli.ChatCli.__new__(chat_cli.ChatCli)
    cli.session = type("Session", (), {"name": "session-test"})()
    cli.provider = "groq"
    cli.model = "llama-3.1-8b-instant"
    return cli


def test_startup_banner_includes_provider_and_model():
    cli = make_cli()

    banner = cli._build_startup_banner()

    assert banner == [
        "Chat session started: session-test",
        "Provider: groq",
        "Model: llama-3.1-8b-instant",
    ]


def test_chat_cli_imports_env_loader_from_repo_module(monkeypatch, tmp_path):
    import env_loader

    calls = {}

    def fake_find_project_root(start=None):
        return tmp_path

    def fake_load_project_envs(project_root):
        calls["project_root"] = project_root

    monkeypatch.setattr(env_loader, "find_project_root", fake_find_project_root)
    monkeypatch.setattr(env_loader, "load_project_envs", fake_load_project_envs)

    importlib.reload(chat_cli)

    assert calls["project_root"] == tmp_path


def test_read_multiline_prompt_returns_single_line_when_enter_submits():
    cli = make_cli()
    calls = []

    def read_line(prompt: str) -> str:
        calls.append(prompt)
        return "hello world"

    result = cli._read_multiline_prompt(read_line, "session-test > ")

    assert result == "hello world"
    assert calls == ["session-test > "]


def test_read_multiline_prompt_collects_backslash_continuation():
    cli = make_cli()
    inputs = iter(["first line \\", "second line"])
    prompts = []

    def read_line(prompt: str) -> str:
        prompts.append(prompt)
        return next(inputs)

    result = cli._read_multiline_prompt(read_line, "session-test > ")

    assert result == "first line \\\nsecond line"
    assert prompts == ["session-test > ", "... "]


def test_read_input_uses_prompt_toolkit_as_multiline_editor(monkeypatch):
    cli = make_cli()
    monkeypatch.setattr(chat_cli, "_PROMPT_TOOLKIT_AVAILABLE", True)
    captured = {}

    class FakePromptSession:
        def __init__(self, multiline=False, key_bindings=None):
            captured["multiline"] = multiline
            captured["key_bindings"] = key_bindings
            captured["prompts"] = []

        def prompt(self, prompt_text):
            captured["prompts"].append(prompt_text)
            return "from prompt toolkit"

    monkeypatch.setattr(chat_cli, "PromptSession", lambda **kwargs: FakePromptSession(**kwargs))

    result = cli._read_input()

    assert result == "from prompt toolkit"
    assert captured["multiline"] is True
    assert "Alt+S" in captured["prompts"][0]
    assert "Ctrl+Q" in captured["prompts"][0]


def test_prompt_toolkit_session_uses_multiline_and_alt_s_binding(monkeypatch):
    cli = make_cli()
    monkeypatch.setattr(chat_cli, "_PROMPT_TOOLKIT_AVAILABLE", True)

    captured = {}

    class FakePromptSession:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def prompt(self, prompt_text):
            captured["prompt_text"] = prompt_text
            return "hello"

    monkeypatch.setattr(chat_cli, "PromptSession", FakePromptSession)

    result = cli._read_input()

    assert result == "hello"
    assert captured["multiline"] is True
    assert "Alt+S" in captured["prompt_text"]
    assert "Ctrl+Q" in captured["prompt_text"]
    bindings = captured["key_bindings"]
    assert bindings.get_bindings_for_keys(("escape", "s"))
    assert bindings.get_bindings_for_keys(("c-q",))


def test_chat_orchestrator_defaults_to_five_steps():
    from orchestrator import DPEFOrchestrator

    orchestrator = DPEFOrchestrator(
        knowledge_store=type("KnowledgeStore", (), {})(),
    )

    assert orchestrator.max_steps == 5
