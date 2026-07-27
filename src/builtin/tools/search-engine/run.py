import argparse
import html
import os
import re
import sys
import time
import random
import urllib.parse
import urllib.request
from pathlib import Path


def add_runtime_path() -> None:
    # Try multiple ways to find tool_runtime
    possible_dirs = []
    
    scripts_dir = os.getenv("CORPS_PYTHON_SCRIPTS_DIR")
    if scripts_dir:
        p = Path(scripts_dir).resolve()
        possible_dirs.append(p)
        possible_dirs.append(p / "_runtime")
    
    # Standard relative path in the repo: src/builtin/tools/search-engine/run.py -> src/_runtime
    try:
        possible_dirs.append(Path(__file__).resolve().parents[3] / "_runtime")
    except Exception:
        pass

    for d in possible_dirs:
        if d.exists() and (d / "tool_runtime.py").exists():
            if str(d) not in sys.path:
                sys.path.insert(0, str(d))
            return


add_runtime_path()

from tool_runtime import clamp, emit_result, failure, join_lines, parse_int, success  # noqa: E402


def fetch(url: str, headers: dict = None) -> str:
    if headers is None:
        # Simulate a real browser more closely
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Accept-Encoding": "identity", # Avoid compression issues for simple fetch
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
        
    # Add a random delay to simulate human behavior
    time.sleep(random.uniform(0.5, 1.5))
    
    # Try to set a plausible Referer
    parsed_url = urllib.parse.urlparse(url)
    if "google.com" in parsed_url.netloc:
        headers["Referer"] = "https://www.google.com/"
    elif "reddit.com" in parsed_url.netloc:
        headers["Referer"] = "https://www.reddit.com/"
    elif "duckduckgo.com" in parsed_url.netloc:
        headers["Referer"] = "https://duckduckgo.com/"
    elif "wikipedia.org" in parsed_url.netloc:
        headers["Referer"] = "https://www.wikipedia.org/"

    request = urllib.request.Request(
        url,
        headers=headers,
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read().decode(charset, errors="replace")
    return body


def parse_duckduckgo(html_text: str, limit: int) -> list[str]:
    pattern = re.compile(
        r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    lines: list[str] = []
    for index, match in enumerate(pattern.finditer(html_text), start=1):
        if index > limit:
            break
        href = html.unescape(match.group(1))
        title = re.sub(r"<[^>]+>", " ", html.unescape(match.group(2)))
        title = re.sub(r"\s+", " ", title).strip()
        lines.append(f"{index}. {title} | {href}")
    return lines


def parse_wikipedia(html_text: str, limit: int) -> list[str]:
    # Wikipedia search results heading pattern
    pattern = re.compile(
        r'<div class="mw-search-result-heading"><a href="([^"]+)"[^>]*title="([^"]+)"',
        re.IGNORECASE | re.DOTALL,
    )
    lines: list[str] = []
    for index, match in enumerate(pattern.finditer(html_text), start=1):
        if index > limit:
            break
        href = "https://en.wikipedia.org" + match.group(1)
        title = html.unescape(match.group(2))
        lines.append(f"{index}. {title} | {href}")
    return lines


def parse_reddit(html_text: str, limit: int) -> list[str]:
    # Old reddit search title pattern
    pattern = re.compile(
        r'<a href="([^"]+)"[^>]*class="search-title[^"]*"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    lines: list[str] = []
    for index, match in enumerate(pattern.finditer(html_text), start=1):
        if index > limit:
            break
        href = match.group(1)
        if href.startswith("/"):
            href = "https://old.reddit.com" + href
        title = re.sub(r"<[^>]+>", " ", html.unescape(match.group(2)))
        title = re.sub(r"\s+", " ", title).strip()
        lines.append(f"{index}. {title} | {href}")
    return lines


def parse_google(html_text: str, limit: int) -> list[str]:
    # Google search result pattern (basic version)
    pattern = re.compile(
        r'<a href="/url\?q=([^&]+)&amp;[^"]*"><h3[^>]*>(.*?)</h3>',
        re.IGNORECASE | re.DOTALL,
    )
    lines: list[str] = []
    for index, match in enumerate(pattern.finditer(html_text), start=1):
        if index > limit:
            break
        href = urllib.parse.unquote(match.group(1))
        title = re.sub(r"<[^>]+>", " ", html.unescape(match.group(2)))
        title = re.sub(r"\s+", " ", title).strip()
        lines.append(f"{index}. {title} | {href}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Search multiple engines and return results.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--engine", default="duckduckgo")
    parser.add_argument("--limit", default="5")
    args = parser.parse_args()

    query = str(args.query).strip()
    engine = str(args.engine).lower().strip()
    limit = clamp(parse_int(args.limit, 5), 1, 20)

    if not query:
        emit_result(failure("search-engine", "No search query provided."))
        raise SystemExit(1)

    encoded = urllib.parse.quote_plus(query)
    
    try:
        if engine == "duckduckgo":
            url = f"https://html.duckduckgo.com/html/?q={encoded}"
            html_text = fetch(url)
            results = parse_duckduckgo(html_text, limit)
        elif engine == "wikipedia":
            url = f"https://en.wikipedia.org/w/index.php?search={encoded}&title=Special:Search&fulltext=1"
            html_text = fetch(url)
            results = parse_wikipedia(html_text, limit)
        elif engine == "reddit":
            url = f"https://old.reddit.com/search?q={encoded}"
            html_text = fetch(url)
            results = parse_reddit(html_text, limit)
        elif engine == "google":
            url = f"https://www.google.com/search?q={encoded}&gbv=1"
            html_text = fetch(url)
            results = parse_google(html_text, limit)
            if not results and "trouble accessing Google Search" in html_text:
                emit_result(failure("search-engine", "Google detected a bot and blocked the request. Try another engine like duckduckgo."))
                return
        elif engine == "grepapp":
            # Grep.app often 429s or requires JS. Try API first.
            url = f"https://grep.app/api/search?q={encoded}"
            try:
                # This might fail or return JSON
                html_text = fetch(url)
                # Grep.app API returns JSON. We should ideally parse it.
                import json
                data = json.loads(html_text)
                results = []
                for index, item in enumerate(data.get("hits", {}).get("hits", []), start=1):
                    if index > limit:
                        break
                    repo = item.get("repo", {}).get("raw", "unknown")
                    path = item.get("path", {}).get("raw", "unknown")
                    href = f"https://github.com/{repo}/blob/master/{path}"
                    title = f"{repo}: {path}"
                    results.append(f"{index}. {title} | {href}")
            except Exception:
                emit_result(failure("search-engine", "Grep.app returned an error (likely 429 Too Many Requests)."))
                return
        else:
            emit_result(failure("search-engine", f"Unsupported engine: {engine}"))
            return

        if not results:
            emit_result(success("search-engine", f"No results found for query '{query}' on {engine}.", {
                "query": query,
                "engine": engine,
                "limit": limit,
                "results": [],
            }))
            return

        output = join_lines(results)
        emit_result(success("search-engine", output, {
            "query": query,
            "engine": engine,
            "limit": limit,
            "results": results,
        }))

    except Exception as e:
        emit_result(failure("search-engine", f"Error during search: {str(e)}"))


if __name__ == "__main__":
    main()
