import argparse
import html
import os
import re
import sys
import urllib.parse
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

from tool_runtime import clamp, emit_result, failure, join_lines, parse_int, success  # noqa: E402


RESULT_PATTERN = re.compile(
    r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)


def fetch(url: str, max_chars: int) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "corps/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read().decode(charset, errors="replace")
    body = body.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(body) <= max_chars:
        return body
    return body[: max(0, max_chars)] + "\n...(truncated)"


def parse_results(html_text: str, limit: int) -> list[str]:
    lines: list[str] = []
    for index, match in enumerate(RESULT_PATTERN.finditer(html_text or ""), start=1):
        if index > max(1, limit):
            break
        href = html.unescape(match.group(1))
        title = re.sub(r"<[^>]+>", " ", html.unescape(match.group(2)))
        title = re.sub(r"\s+", " ", title).strip()
        lines.append(f"{index}. {title} | {href}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Search the web and return compact results.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--site", default="")
    parser.add_argument("--limit", default="5")
    args = parser.parse_args()

    query = str(args.query).strip()
    if not query:
        emit_result(failure("web-search", "No search query provided."))
        raise SystemExit(1)

    effective_query = query
    if str(args.site).strip():
        effective_query = f"{effective_query} site:{str(args.site).strip()}"
    encoded = urllib.parse.quote_plus(effective_query)
    html_text = fetch(f"https://html.duckduckgo.com/html/?q={encoded}", 40_000)
    limit = clamp(parse_int(args.limit, 5), 1, 10)
    lines = parse_results(html_text, limit)
    if not lines:
        emit_result(success("web-search", f"No search results found for query: {effective_query}", {
            "query": query,
            "site": str(args.site).strip(),
            "limit": limit,
            "results": [],
        }))
        return

    output = join_lines(lines)
    emit_result(success("web-search", output, {
        "query": query,
        "site": str(args.site).strip(),
        "limit": limit,
        "results": lines,
    }))


if __name__ == "__main__":
    main()
