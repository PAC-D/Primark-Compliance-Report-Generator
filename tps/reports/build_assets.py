"""Rebuild the report assets in tps/assets/vendor/ so PDF rendering needs no network.

    python -m tps.reports.build_assets

- chart.umd.min.js and the Inter font files are downloaded once (skipped when present).
- tailwind.css is regenerated every run: every token in the report templates is fed
  to the Tailwind Play CDN in a headless browser, and the CSS it emits is saved.
  Re-run this after adding Tailwind classes to a template.
"""

import re
import urllib.request

from playwright.sync_api import sync_playwright

from tps.config import ASSETS_DIR, TEMPLATES_DIR

VENDOR = ASSETS_DIR / "vendor"
CHART_JS_URL = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"
INTER_CSS_URL = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
FONT_SUBSETS = ("latin", "latin-ext")  # supplier names are Latin script
TAILWIND_CDN = "https://cdn.tailwindcss.com"
# Google serves woff2 only to browsers it recognises.
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})) as r:
        return r.read()


def fetch_chart_js() -> None:
    path = VENDOR / "chart.umd.min.js"
    if not path.exists():
        path.write_bytes(_get(CHART_JS_URL))


def fetch_fonts() -> None:
    """fonts.css with Inter @font-face rules pointing at local woff2 files."""
    if (VENDOR / "fonts.css").exists():
        return
    css = _get(INTER_CSS_URL).decode()
    keep = []
    # Google's CSS is a series of "/* subset */ @font-face {...}" blocks.
    for subset, block in re.findall(r"/\* ([\w-]+) \*/\s*(@font-face \{.*?\})", css, re.S):
        if subset not in FONT_SUBSETS:
            continue
        url = re.search(r"url\((https://[^)]+\.woff2)\)", block).group(1)
        name = f"inter-{subset}.woff2"
        if not (VENDOR / name).exists():
            (VENDOR / name).write_bytes(_get(url))
        keep.append(f"/* {subset} */\n" + block.replace(url, name))
    (VENDOR / "fonts.css").write_text("\n".join(keep) + "\n")


def build_tailwind_css() -> int:
    tokens = set()
    for template in TEMPLATES_DIR.glob("*.j2"):
        # Same idea as Tailwind's own content scan: every word-like token is a candidate;
        # unknown ones are ignored, and unused rules match nothing.
        tokens |= set(re.split(r"[\s\"'`<>={}()|,;]+", template.read_text(encoding="utf-8")))
    classes = " ".join(sorted(t for t in tokens if t and len(t) < 80))

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_content(f'<html><head><script src="{TAILWIND_CDN}"></script></head>'
                         f'<body><div class="{classes}"></div></body></html>',
                         wait_until="networkidle")
        page.wait_for_timeout(500)  # one-off build step; let the CDN finish its pass
        css = page.evaluate("[...document.querySelectorAll('style')].map(s => s.textContent).join('\\n')")
        browser.close()

    (VENDOR / "tailwind.css").write_text(css)
    return len(css)


if __name__ == "__main__":
    VENDOR.mkdir(parents=True, exist_ok=True)
    fetch_chart_js()
    fetch_fonts()
    size = build_tailwind_css()
    for f in sorted(VENDOR.iterdir()):
        print(f"{f.stat().st_size // 1024:6} KB  {f.name}")
    print(f"tailwind.css: {size} chars")
