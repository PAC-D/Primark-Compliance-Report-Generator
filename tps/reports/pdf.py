"""HTML -> PDF via headless Chromium (Playwright), plus pypdf merging/page numbers.

Each thread gets its own browser and one reusable page: Playwright's sync API is
bound to the thread that started it, and opening a new page costs 1.5-2.5 s.
Whoever renders calls close_browser() from the same thread when done.
"""

import io
import threading
from datetime import datetime

from playwright.sync_api import Page, sync_playwright
from pypdf import PdfWriter
from pypdf.annotations import FreeText
from pypdf.generic import ArrayObject, NameObject, TextStringObject

from tps.reports.html import ALLPORT_LOGO, PRIMARK_LOGO

NO_MARGIN = {"top": "0", "right": "0", "bottom": "0", "left": "0"}
# Wider than an A4/A4-landscape page; 2x density keeps the chart canvases sharp.
VIEWPORT = {"width": 1240, "height": 1754, "device_scale_factor": 2}

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


def _landscape_header_footer() -> tuple[str, str]:
    header = f'''<table width="100%" cellpadding="0" cellspacing="0" style="margin:0;padding:10px 16px;border-bottom:4px solid #4A90D9;background:white;">
  <tr>
    <td width="50%" style="vertical-align:middle;">
      <img src="{PRIMARK_LOGO}" style="height:25px;width:auto;" alt="Primark">
      <span style="display:none">PRIMARK</span>
    </td>
    <td width="50%" style="text-align:right;vertical-align:middle;">
      <img src="{ALLPORT_LOGO}" style="height:28px;width:auto;" alt="Allport Pacd">
    </td>
  </tr>
</table>'''
    footer = '''<html><head><style>
</style></head><body>
<table width="100%" cellpadding="0" cellspacing="0" style="margin:0;padding:4px 16px;border-top:1px solid #e5e7eb;background:#f9fafb;">
  <tr>
    <td width="50%" style="font-size:8px;color:#6b7280;vertical-align:middle;">
      Generated: ''' + datetime.now().strftime("%d %B %Y") + '''
    </td>
    <td width="50%" style="text-align:right;font-size:8px;color:#6b7280;vertical-align:middle;">
    </td>
  </tr>
</table></body></html>'''
    return header, footer


def _render_page(html: str, landscape: bool = False) -> bytes:
    page = _page()
    # Every asset is inline and charts don't animate, so the page is final once
    # it has loaded and its fonts are ready - no network wait, no sleep.
    page.set_content(html, wait_until="load")
    page.evaluate("document.fonts.ready.then(() => true)")
    if landscape:
        header, footer = _landscape_header_footer()
        return page.pdf(width="297mm", height="210mm", print_background=True, margin=NO_MARGIN,
                        display_header_footer=True, header_template=header, footer_template=footer)
    return page.pdf(format="A4", print_background=True, margin=NO_MARGIN)


def html_to_pdf(html_content: str, output_path: str) -> None:
    """Single A4 portrait PDF."""
    try:
        pdf = _render_page(html_content)
    except Exception as e:
        raise RuntimeError(f"PDF generation failed: {e}") from e
    with open(output_path, "wb") as f:
        f.write(pdf)


def html_to_pdf_mixed(portrait_html: str, landscape_html: str | None, output_path: str) -> None:
    """Portrait pages followed by landscape pages; landscape pages get page numbers.
    Merged and numbered in memory, written once."""
    if landscape_html is None:
        html_to_pdf(portrait_html, output_path)
        return

    writer = PdfWriter()
    writer.append(io.BytesIO(_render_page(portrait_html)))
    first_numbered = len(writer.pages) + 1
    writer.append(io.BytesIO(_render_page(landscape_html, landscape=True)))
    _number_pages(writer, start_page=first_numbered)
    with open(output_path, "wb") as f:
        writer.write(f)


def _number_pages(writer: PdfWriter, start_page: int) -> None:
    """'Page N' in the bottom-right corner of every page from start_page on."""
    for i, page_obj in enumerate(writer.pages):
        page_num = i + 1
        if page_num < start_page:
            continue
        is_landscape = float(page_obj.mediabox.width) > float(page_obj.mediabox.height)
        rect = (780, 8, 840, 28) if is_landscape else (520, 8, 580, 28)

        annotation = FreeText(
            rect=rect,
            text=f"Page {page_num}",
            font="Helvetica",
            font_size="9pt",
            font_color="6b7280",
            border_color=None,
            background_color=None,
        )
        annotation[NameObject("/DA")] = TextStringObject("0.419608 0.419608 0.419608 rg")

        if "/Annots" not in page_obj:
            page_obj[NameObject("/Annots")] = ArrayObject()
        page_obj["/Annots"].append(annotation)
