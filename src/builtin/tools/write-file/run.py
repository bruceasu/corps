import argparse
import os
import sys
from pathlib import Path

def add_runtime_path() -> None:
    scripts_dir = os.getenv("CORPS_PYTHON_SCRIPTS_DIR")
    if scripts_dir:
        runtime_dir = Path(scripts_dir).resolve() / "_runtime"
    else:
        # Heuristic to find _runtime if CORPS_PYTHON_SCRIPTS_DIR is not set
        runtime_dir = Path(__file__).resolve().parents[3] / "_runtime"
        if not runtime_dir.is_dir():
             runtime_dir = Path(__file__).resolve().parents[2] / "_runtime"
    sys.path.insert(0, str(runtime_dir))

add_runtime_path()

from tool_runtime import emit_result, failure, success

def main() -> None:
    parser = argparse.ArgumentParser(description="Write content to a file.")
    parser.add_argument("--path", required=True)
    parser.add_argument("--content", required=True)
    args = parser.parse_args()

    path = Path(str(args.path)).expanduser().resolve()
    try:
        os.makedirs(path.parent, exist_ok=True)
        path.write_text(args.content, encoding="utf-8")
        emit_result(success("write-file", f"✅ Written to {path} ({len(args.content)} chars)", {
            "path": str(path).replace("\\", "/"),
            "chars": len(args.content)
        }))
    except Exception as e:
        emit_result(failure("write-file", f"❌ Failed to write to {path}: {e}"))
        raise SystemExit(1)

if __name__ == "__main__":
    main()
