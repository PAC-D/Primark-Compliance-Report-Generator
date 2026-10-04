"""HTML -> PDF via headless Chromium (Playwright), plus pypdf merging/page numbers."""

import atexit
import os
import tempfile
from datetime import datetime

from playwright.sync_api import Browser, sync_playwright
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import FreeText
from pypdf.generic import ArrayObject, NameObject, TextStringObject

from tps.reports.html import ALLPORT_LOGO, PRIMARK_LOGO

NO_MARGIN = {"top": "0", "right": "0", "bottom": "0", "left": "0"}

_browser: Browser | None = None
_playwright = None


def get_browser() -> Browser:
    """One shared headless browser for the whole run, closed at exit."""
    global _browser, _playwright
    if _browser is None:
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=True)
    return _browser


def close_browser():
    global _playwright, _browser
    if _browser:
        _browser.close()
        _browser = None
    if _playwright:
        _playwright.stop()
        _playwright = None


atexit.register(close_browser)


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


def _render_page(html: str, landscape: bool = False, header_template: str = "",
                 footer_template: str = "") -> bytes:
    viewport = ({"width": 2970, "height": 42000, "device_scale_factor": 2} if landscape
                else {"width": 2100, "height": 2970, "device_scale_factor": 2})
    page = get_browser().new_page(viewport=viewport)
    try:
        page.set_content(html, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)
        if landscape:
            return page.pdf(width="297mm", height="210mm", print_background=True, margin=NO_MARGIN,
                            display_header_footer=True, header_template=header_template,
                            footer_template=footer_template)
        return page.pdf(format="A4", print_background=True, margin=NO_MARGIN)
    finally:
        page.close()


def html_to_pdf(html_content: str, output_path: str) -> None:
    """Single A4 portrait PDF."""
    try:
        pdf = _render_page(html_content)
    except Exception as e:
        raise RuntimeError(f"PDF generation failed: {e}") from e
    with open(output_path, "wb") as f:
        f.write(pdf)


def html_to_pdf_mixed(portrait_html: str, landscape_html: str | None, output_path: str) -> None:
    """Portrait pages followed by landscape pages; landscape pages get page numbers."""
    if landscape_html is None:
        html_to_pdf(portrait_html, output_path)
        return

    header_tmpl, footer_tmpl = _landscape_header_footer()

    with tempfile.TemporaryDirectory() as tmpdir:
        portrait_path = os.path.join(tmpdir, "portrait.pdf")
        landscape_path = os.path.join(tmpdir, "landscape.pdf")

        with open(portrait_path, "wb") as f:
            f.write(_render_page(portrait_html))
        portrait_page_count = len(PdfReader(portrait_path).pages)

        with open(landscape_path, "wb") as f:
            f.write(_render_page(landscape_html, landscape=True,
                                 header_template=header_tmpl, footer_template=footer_tmpl))

        _merge_pdfs([portrait_path, landscape_path], output_path)
        _add_page_numbers(output_path, output_path, start_page=portrait_page_count + 1)


def _merge_pdfs(input_paths: list[str], output_path: str) -> None:
    writer = PdfWriter()
    for path in input_paths:
        writer.append(path)
    with open(output_path, "wb") as f:
        writer.write(f)


def _add_page_numbers(input_path: str, output_path: str, start_page: int = 3) -> None:
    writer = PdfWriter()
    writer.append(input_path)

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

    with open(output_path, "wb") as f:
        writer.write(f)
