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

from tool_runtime import emit_result, success  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Echo rendered text with an optional prefix.")
    parser.add_argument("--text", required=True)
    parser.add_argument("--prefix", default="")
    args = parser.parse_args()

    prefix = "" if args.prefix is None else str(args.prefix)
    text = "" if args.text is None else str(args.text)
    emit_result(success("echo-tool", prefix + text, {"text": text, "prefix": prefix}))


if __name__ == "__main__":
    main()
