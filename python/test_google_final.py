import urllib.request
import urllib.parse
import re

def fetch(url, ua):
    print(f"Fetching {url} with UA {ua[:20]}...")
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": ua},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read().decode('utf-8', errors='replace')
    except Exception as e:
        return f"Error: {e}"

query = "python"
encoded_query = urllib.parse.quote(query)

ua_mobile = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1"
ua_desktop = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

urls = [
    (f"https://www.google.com/search?q={encoded_query}&hl=en", ua_mobile),
    (f"https://www.google.com/search?q={encoded_query}&hl=en&gbv=1", ua_desktop),
]

for url, ua in urls:
    content = fetch(url, ua)
    print(f"Length: {len(content)}")
    if "trouble accessing Google Search" in content:
        print("Bot detected (trouble accessing message)")
    elif "captcha" in content.lower():
        print("Captcha detected")
    else:
        print("Possible success?")
        print(content[:1000])
    print("-" * 20)
