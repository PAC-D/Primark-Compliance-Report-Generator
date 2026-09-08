from playwright.sync_api import sync_playwright, Browser
import atexit
from pathlib import Path
import tempfile
import os
import base64
from datetime import datetime

def _add_page_numbers(input_path: str, output_path: str, start_page: int = 3) -> None:
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.annotations import FreeText
        from pypdf.generic import ArrayObject, NameObject, TextStringObject
    except ImportError:
        return

    writer = PdfWriter()
    writer.append(input_path)

    for i in range(len(writer.pages)):
        actual_page_num = i + 1
        if actual_page_num >= start_page:
            page_obj = writer.pages[i]
            page_width = float(page_obj.mediabox.width)
            page_height = float(page_obj.mediabox.height)
            is_landscape = page_width > page_height
            rect = (780, 8, 840, 28) if is_landscape else (520, 8, 580, 28)

            annotation = FreeText(
                rect=rect,
                text=f"Page {actual_page_num}",
                font="Helvetica",
                font_size="9pt",
                font_color="6b7280",
                border_color=None,
                background_color=None
            )

            gray_da = "0.419608 0.419608 0.419608 rg"
            annotation[NameObject('/DA')] = TextStringObject(gray_da)

            if '/Annots' not in page_obj:
                page_obj[NameObject('/Annots')] = ArrayObject()
            page_obj['/Annots'].append(annotation)

    with open(output_path, 'wb') as f:
        writer.write(f)

ASSETS_PATH = Path(__file__).parent / "assets"

def _load_logo(name: str) -> str:
    with open(ASSETS_PATH / name, "rb") as f:
        return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"

PRIMARK_LOGO = _load_logo("Primark-logo.png")
ALLPORT_LOGO = _load_logo("allport-pacd-logo.png")

def _make_landscape_header_footer() -> tuple[str, str]:
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

_browser: Browser | None = None
_playwright = None
_lock = None


def _get_lock():
    global _lock
    if _lock is None:
        import threading
        _lock = threading.Lock()
    return _lock


def get_browser() -> Browser:
    global _browser, _playwright
    if _browser is None:
        with _get_lock():
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


def html_to_pdf(html_content: str, output_path: str, template_dir: Path | None = None, page_format: str = "A4") -> bool:
    browser = get_browser()
    page = browser.new_page(viewport={"width": 2100, "height": 2970, "device_scale_factor": 2})

    try:
        page.set_content(html_content, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)
        if page_format == "A5":
            pdf_opts = {
                "width": "148mm",
                "height": "210mm",
                "print_background": True,
                "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"}
            }
        elif page_format == "PORTRAIT_MULTI":
            pdf_opts = {
                "width": "210mm",
                "height": "297mm",
                "print_background": True,
                "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"}
            }
        else:
            pdf_opts = {
                "format": page_format,
                "print_background": True,
                "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"}
            }
        page.pdf(path=output_path, **pdf_opts)
        return True
    except Exception as e:
        raise RuntimeError(f"PDF generation failed: {e}") from e
    finally:
        page.close()


def _render_page(browser, html: str, landscape: bool = False, header_template: str = "", footer_template: str = "") -> bytes:
    viewport = {"width": 2970, "height": 42000, "device_scale_factor": 2} if landscape else {"width": 2100, "height": 2970, "device_scale_factor": 2}
    page = browser.new_page(viewport=viewport)
    try:
        page.set_content(html, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)
        if landscape:
            pdf_opts = {
                "width": "297mm",
                "height": "210mm",
                "print_background": True,
                "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
                "display_header_footer": True,
                "header_template": header_template,
                "footer_template": footer_template,
            }
        else:
            pdf_opts = {
                "format": "A4",
                "print_background": True,
                "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"}
            }
        return page.pdf(**pdf_opts)
    finally:
        page.close()


def html_to_pdf_mixed(portrait_html: str, landscape_html: str | None, output_path: str, template_dir: Path | None = None) -> bool:
    if landscape_html is None:
        return html_to_pdf(portrait_html, output_path, template_dir)

    browser = get_browser()
    header_tmpl, footer_tmpl = _make_landscape_header_footer()

    with tempfile.TemporaryDirectory() as tmpdir:
        portrait_path = os.path.join(tmpdir, 'portrait.pdf')
        landscape_path = os.path.join(tmpdir, 'landscape.pdf')

        portrait_pdf = _render_page(browser, portrait_html, landscape=False)
        with open(portrait_path, 'wb') as f:
            f.write(portrait_pdf)

        from pypdf import PdfReader
        portrait_page_count = len(PdfReader(portrait_path).pages)

        landscape_pdf = _render_page(browser, landscape_html, landscape=True, header_template=header_tmpl, footer_template=footer_tmpl)
        with open(landscape_path, 'wb') as f:
            f.write(landscape_pdf)

        _merge_pdfs([portrait_path, landscape_path], output_path)
        _add_page_numbers(output_path, output_path, start_page=portrait_page_count + 1)

    return True


def _merge_pdfs(input_paths: list[str], output_path: str) -> None:
    from pypdf import PdfWriter
    writer = PdfWriter()
    for path in input_paths:
        writer.append(path)
    with open(output_path, 'wb') as f:
        writer.write(f)


def render_and_generate_pdf(html_content: str, output_path: str, template_dir: Path | None = None) -> bool:
    return html_to_pdf_mixed(html_content, None, output_path, template_dir)