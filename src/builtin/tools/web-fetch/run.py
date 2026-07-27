import argparse
import os
import sys
import urllib.request
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


def fetch(url: str, max_chars: int) -> tuple[str, bool]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "corps/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read().decode(charset, errors="replace")
    return truncate_text(body, max_chars)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a web page and return its content.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--max-chars", default="8000")
    args = parser.parse_args()

    max_chars = max(200, parse_int(args.max_chars, 8000))
    try:
        content, truncated = fetch(str(args.url), max_chars)
    except Exception as exc:
        emit_result(failure("web-fetch", str(exc)))
        raise SystemExit(1)
    emit_result(success("web-fetch", content, {"url": str(args.url), "maxChars": max_chars, "truncated": truncated}))


if __name__ == "__main__":
    main()
