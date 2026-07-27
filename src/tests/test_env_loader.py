import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("CORPS_PYTHON_SCRIPTS_DIR", str(ROOT))
sys.path.insert(0, str(ROOT))

from env_loader import find_project_root, load_env_file  # noqa: E402


def test_find_project_root_discovers_nearest_env_file(tmp_path):
    project_root = tmp_path / "corps"
    nested = project_root / "src" / "module"
    nested.mkdir(parents=True)
    (project_root / ".env").write_text("CORPS_PROVIDER=groq\n", encoding="utf-8")

    discovered = find_project_root(nested / "script.py")

    assert discovered == project_root


def test_load_env_file_sets_environment_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("CORPS_MODEL=llama-3.1-8b-instant\n", encoding="utf-8")
    monkeypatch.delenv("CORPS_MODEL", raising=False)

    load_env_file(env_file)

    import os

    assert os.getenv("CORPS_MODEL") == "llama-3.1-8b-instant"
