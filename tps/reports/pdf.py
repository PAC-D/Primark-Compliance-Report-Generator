"""HTML -> PDF via headless Chromium (Playwright).

Each thread gets its own browser and one reusable page: Playwright's sync API is
bound to the thread that started it, and opening a new page costs 1.5-2.5 s.
Whoever renders calls close_browser() from the same thread when done.
"""

import threading
from datetime import datetime

from playwright.sync_api import Page, sync_playwright

from tps.reports.html import ALLPORT_LOGO, PRIMARK_LOGO

NO_MARGIN = {"top": "0", "right": "0", "bottom": "0", "left": "0"}
# Wider than an A4/A4-landscape page; 2x density keeps the chart canvases sharp.
VIEWPORT = {"width": 1240, "height": 1754, "device_scale_factor": 2}

# Chromium repeats these in every page's top and bottom margin (the template's @page rules
# set the margins). Templates can't load fonts, hence the system-font fallback.
HEADER = f'''<div style="width:100%;padding:0 30px;margin-top:6mm;display:flex;justify-content:space-between;align-items:center">
  <img src="{PRIMARK_LOGO}" style="height:22px"><img src="{ALLPORT_LOGO}" style="height:26px"></div>'''
FOOTER = '''<div style="width:100%;padding:0 30px;margin-bottom:4mm;display:flex;justify-content:space-between;
  font-family:Inter,'Segoe UI',sans-serif;font-size:8px;color:#9ca3af">
  <span>Generated: {date}</span><span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>'''

_local = threading.local()


def _page() -> Page:
    if getattr(_local, "page", None) is None:
        _local.playwright = sync_playwright().start()
        _local.browser = _local.playwright.chromium.launch(headless=True)
        _local.page = _local.browser.new_page(viewport=VIEWPORT)
    return _local.page


def close_browser() -> None:
    """Close this thread's browser, if it started one."""
    if getattr(_local, "page", None) is None:
        return
    _local.browser.close()
    _local.playwright.stop()
    _local.page = _local.browser = _local.playwright = None


def html_to_pdf(html_content: str, output_path: str, header_footer: bool = False) -> None:
    """Without header_footer: A4 portrait, no margins, the HTML draws everything.
    With it: page sizes and margins from the HTML's @page rules, and the logo header
    and "Generated / Page N of M" footer on every page."""
    page = _page()
    try:
        # Every asset is inline and charts don't animate, so the page is final once
        # it has loaded and its fonts are ready - no network wait, no sleep.
        page.set_content(html_content, wait_until="load")
        page.evaluate("document.fonts.ready.then(() => true)")
        if header_footer:
            pdf = page.pdf(prefer_css_page_size=True, print_background=True, display_header_footer=True,
                           header_template=HEADER,
                           footer_template=FOOTER.format(date=datetime.now().strftime("%d %B %Y")))
        else:
            pdf = page.pdf(format="A4", print_background=True, margin=NO_MARGIN)
    except Exception as e:
        raise RuntimeError(f"PDF generation failed: {e}") from e
    with open(output_path, "wb") as f:
        f.write(pdf)
