import urllib.request
import urllib.parse
import re

def fetch(url):
    print(f"Fetching {url}...")
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read().decode('utf-8', errors='replace')
    except Exception as e:
        return f"Error: {e}"

query = "python"
encoded_query = urllib.parse.quote(query)

engines = {
    "google": f"https://www.google.com/search?q={encoded_query}",
    "reddit": f"https://www.reddit.com/search/?q={encoded_query}",
    "grepapp": f"https://grep.app/search?q={encoded_query}",
    "wikipedia": f"https://en.wikipedia.org/wiki/Special:Search?search={encoded_query}",
    "duckduckgo": f"https://html.duckduckgo.com/html/?q={encoded_query}"
}

for name, url in engines.items():
    content = fetch(url)
    print(f"{name}: {len(content)} bytes")
    if "Error" in content:
        print(content)
    # Print a snippet to see if it's usable
    print(content[:500])
    print("-" * 20)
