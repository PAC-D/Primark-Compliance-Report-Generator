"""Jinja environment and the images embedded in the HTML reports."""

import base64

from jinja2 import Environment, FileSystemLoader, select_autoescape

from tps.config import ASSETS_DIR, TEMPLATES_DIR

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render(template: str, **context) -> str:
    return _env.get_template(template).render(**context)


def _data_uri(name: str, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode((ASSETS_DIR / name).read_bytes()).decode()}"


PRIMARK_LOGO = _data_uri("Primark-logo.png", "image/png")
ALLPORT_LOGO = _data_uri("allport-pacd-logo.png", "image/png")
DEAN_MOSS_SIGNATURE = _data_uri("DeanMoss.jpg", "image/jpeg")
