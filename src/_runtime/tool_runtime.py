import json
import re
from dataclasses import dataclass, asdict
from html import unescape
from pathlib import Path
from typing import Any, Iterable


@dataclass
class ToolResult:
    ok: bool
    toolName: str
    output: str
    data: dict[str, Any]
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def __contains__(self, key: object) -> bool:
        return key in self.to_dict()


def normalize_optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "undefined"}:
        return None
    return text


def parse_bool(value: Any, default: bool = False) -> bool:
    text = normalize_optional(value)
    if text is None:
        return default
    return text.lower() in {"1", "true", "yes", "y", "on"}


def parse_int(value: Any, default: int) -> int:
    text = normalize_optional(value)
    if text is None:
        return default
    try:
        return int(str(text).strip().rstrip(")"))
    except Exception:
        return default


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def strip_fence(text: str | None) -> str:
    trimmed = (text or "").strip()
    if trimmed.startswith("```"):
        trimmed = re.sub(r"^```(?:yaml|json|markdown|md|text)?\s*", "", trimmed)
        trimmed = re.sub(r"\s*```$", "", trimmed)
    return trimmed.strip()


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(normalized) <= max_chars:
        return normalized, False
    return normalized[: max(0, max_chars)] + "\n...(truncated)", True


def emit_result(result: ToolResult) -> None:
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def success(tool_name: str, output: str, data: dict[str, Any] | None = None) -> ToolResult:
    return ToolResult(True, tool_name, output or "", data or {}, "")


def failure(tool_name: str, error: str) -> ToolResult:
    return ToolResult(False, tool_name, "", {}, error or "Unknown error")


def resolve_tool_home(script_file: str) -> Path:
    return Path(script_file).resolve().parent


def load_json(text: str | None) -> dict[str, Any]:
    if text is None or not str(text).strip():
        return {}
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object")
    return value


def required_keys_missing(required_keys: str | None, structured: dict[str, Any]) -> list[str]:
    if not required_keys or not required_keys.strip():
        return []
    keys = [key.strip() for key in required_keys.split(",")]
    return [key for key in keys if key and key not in structured]


def sanitize_html(value: str | None) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", value or "")).replace("\n", " ")


def join_lines(lines: Iterable[str]) -> str:
    return "\n".join(line for line in lines if line is not None)
