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
        if not runtime_dir.is_dir():
             runtime_dir = Path(__file__).resolve().parents[2] / "_runtime"
    sys.path.insert(0, str(runtime_dir))

add_runtime_path()

from tool_runtime import emit_result, failure, success

def main() -> None:
    parser = argparse.ArgumentParser(description="Replace text in a file.")
    parser.add_argument("--path", required=True)
    parser.add_argument("--old-text", required=True)
    parser.add_argument("--new-text", required=True)
    args = parser.parse_args()

    path = Path(str(args.path)).expanduser().resolve()
    if not path.is_file():
        emit_result(failure("edit-file", f"❌ File not found: {path}"))
        raise SystemExit(1)

    try:
        content = path.read_text(encoding="utf-8")
        if args.old_text not in content:
            emit_result(failure("edit-file", "❌ Target text not found in file"))
            raise SystemExit(1)
        
        new_content = content.replace(args.old_text, args.new_text, 1)
        path.write_text(new_content, encoding="utf-8")
        emit_result(success("edit-file", f"✅ Edited {path}", {
            "path": str(path).replace("\\", "/"),
            "modified": True
        }))
    except Exception as e:
        emit_result(failure("edit-file", f"❌ Error editing {path}: {e}"))
        raise SystemExit(1)

if __name__ == "__main__":
    main()
