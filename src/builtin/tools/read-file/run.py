import argparse
import os
import sys
from pathlib import Path


def add_runtime_path() -> None:
    scripts_dir = os.getenv("CORPS_PYTHON_SCRIPTS_DIR")
    if scripts_dir:
        runtime_dir = Path(scripts_dir).resolve() / "_runtime"
    else:
        runtime_dir = Path(__file__).resolve().parents[3] / "_runtime"
    sys.path.insert(0, str(runtime_dir))


add_runtime_path()

from tool_runtime import emit_result, failure, parse_int, success, truncate_text  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Read a local text file and return its content.")
    parser.add_argument("--path", required=True)
    parser.add_argument("--max-chars", default="8000")
    args = parser.parse_args()

    path = Path(str(args.path)).expanduser().resolve()
    if not path.is_file():
        emit_result(failure("read-file", f"file not found: {path}"))
        raise SystemExit(1)

    max_chars = max(1, parse_int(args.max_chars, 8000))
    content = path.read_text(encoding="utf-8", errors="replace")
    truncated_content, truncated = truncate_text(content, max_chars)
    emit_result(success("read-file", truncated_content, {
        "path": str(path).replace("\\", "/"),
        "maxChars": max_chars,
        "truncated": truncated,
    }))


if __name__ == "__main__":
    main()
