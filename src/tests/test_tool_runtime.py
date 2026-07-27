import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("CORPS_PYTHON_SCRIPTS_DIR", str(ROOT))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "_runtime"))

from tool_runtime import failure, success  # noqa: E402


def test_tool_result_supports_dict_like_access():
    result = success("demo-tool", "hello", {"count": 1})

    assert result.get("ok") is True
    assert result["toolName"] == "demo-tool"
    assert result["output"] == "hello"
    assert result.get("missing", "fallback") == "fallback"


def test_tool_result_failure_supports_dict_like_access():
    result = failure("demo-tool", "boom")

    assert result.get("ok") is False
    assert result["error"] == "boom"
    assert "error" in result
