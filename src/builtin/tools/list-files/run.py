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

from tool_runtime import clamp, emit_result, failure, join_lines, parse_int, success  # noqa: E402


def normalize_pattern(pattern: str) -> str:
    clean = (pattern or "").strip().lstrip("\\").rstrip("$")
    if not clean or clean == "*":
        return "*"
    if clean.startswith("."):
        return f"*{clean}"
    if not any(char in clean for char in "*?[]"):
        return f"*{clean}*"
    return clean


def list_files(root: Path, pattern: str, limit: int) -> list[str]:
    resolved: list[str] = []
    clean_pattern = normalize_pattern(pattern)
    if clean_pattern == "*":
        iterator = root.rglob("*")
    else:
        iterator = root.rglob(clean_pattern)

    for path in iterator:
        if not path.is_file():
            continue
        rel_path = str(path.relative_to(root)).replace("\\", "/")
        if clean_pattern != "*" and not any(char in clean_pattern for char in "*?[]"):
            if clean_pattern.strip("*").lower() not in rel_path.lower():
                continue
        resolved.append(rel_path)
        if len(resolved) >= limit:
            break

    if not resolved and clean_pattern != "*":
        needle = clean_pattern.replace("*", "").lower()
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel_path = str(path.relative_to(root)).replace("\\", "/")
            if needle in rel_path.lower():
                resolved.append(rel_path)
                if len(resolved) >= limit:
                    break

    return sorted(resolved)


def main() -> None:
    parser = argparse.ArgumentParser(description="List files in a directory with glob filtering.")
    parser.add_argument("--path", default=".")
    parser.add_argument("--pattern", default="*")
    parser.add_argument("--limit", default="100")
    args = parser.parse_args()

    root = Path(str(args.path)).expanduser().resolve()
    if not root.is_dir():
        emit_result(failure("list-files", f"Error: {root} is not a directory."))
        raise SystemExit(1)

    limit = clamp(parse_int(args.limit, 100), 1, 200)
    files = list_files(root, str(args.pattern), limit)
    if not files:
        emit_result(success("list-files", f"No files matching '{args.pattern}' found in {root}", {
            "root": str(root).replace("\\", "/"),
            "pattern": str(args.pattern),
            "limit": limit,
            "files": [],
        }))
        return

    output = join_lines(files)
    emit_result(success("list-files", output, {
        "root": str(root).replace("\\", "/"),
        "pattern": str(args.pattern),
        "limit": limit,
        "files": files,
    }))


if __name__ == "__main__":
    main()
