"""Jinja environment and everything the HTML reports embed: logos, fonts and
Chart.js - so rendering never touches the network.
(Re-fetch the vendored files with `python -m tps.reports.build_assets`.)"""

import base64
import re

from jinja2 import Environment, FileSystemLoader, select_autoescape

from tps.config import ASSETS_DIR, TEMPLATES_DIR

VENDOR = ASSETS_DIR / "vendor"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _data_uri(path, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _fonts_css() -> str:
    css = (VENDOR / "fonts.css").read_text()
    return re.sub(r"url\(([\w.-]+\.woff2)\)",
                  lambda m: f"url({_data_uri(VENDOR / m.group(1), 'font/woff2')})", css)


PRIMARK_LOGO = _data_uri(ASSETS_DIR / "Primark-logo.png", "image/png")
ALLPORT_LOGO = _data_uri(ASSETS_DIR / "allport-pacd-logo.png", "image/png")
DEAN_MOSS_SIGNATURE = _data_uri(ASSETS_DIR / "DeanMoss.jpg", "image/jpeg")

# Where the templates used to load Inter and Chart.js from the web.
REPORT_HEAD = (f"<style>{_fonts_css()}</style>\n"
               f"<script>{(VENDOR / 'chart.umd.min.js').read_text(encoding='utf-8')}</script>")


def render(template: str, **context) -> str:
    return _env.get_template(template).render(report_head=REPORT_HEAD, **context)
