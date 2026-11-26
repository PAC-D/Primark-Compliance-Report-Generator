"""Paths, config.yaml and logging setup shared by the whole package."""

import logging
import os
import sys
from pathlib import Path

import yaml
from sqlalchemy.engine import URL

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
ASSETS_DIR = PACKAGE_DIR / "assets"
CONFIG_PATH = ROOT / "config.yaml"

# config.yaml is optional: a container runs from environment variables alone.
CONFIG = yaml.safe_load(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}

DATA_DIR = ROOT / CONFIG.get("paths", {}).get("data_dir", "data")
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR") or ROOT / CONFIG.get("paths", {}).get("output_dir", "output"))


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    """An integer >= minimum from the environment; blank, garbage or too small gives the default."""
    try:
        value = int(os.environ.get(name) or default)
    except ValueError:
        return default
    return value if value >= minimum else default


PDF_WORKERS = _int_env("PDF_WORKERS", 2)
LOG_FILE = ROOT / "logs" / "run.log"
REPORT_MONTH_OFFSET = CONFIG.get("app", {}).get("report_month_offset", 1)

def database_url() -> URL:
    """DB_* environment variables when DB_HOST is set, else config.yaml's database block."""
    if os.environ.get("DB_HOST"):
        for name in ("DB_NAME", "DB_USER"):
            if not os.environ.get(name):
                raise RuntimeError(f"DB_HOST is set but {name} is missing")
        return URL.create(
            "postgresql+psycopg2", username=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"), host=os.environ["DB_HOST"],
            port=_int_env("DB_PORT", 5432), database=os.environ.get("DB_NAME"),
            query={"sslmode": os.environ["DB_SSLMODE"]} if os.environ.get("DB_SSLMODE") else {})
    if "database" not in CONFIG:
        raise RuntimeError("Set DB_HOST or create config.yaml")
    db = CONFIG["database"]
    return URL.create("postgresql+psycopg2", username=db["user"], password=db["password"],
                      host=db["host"], port=db["port"], database=db["name"])


# output/<YYYY-MM Month>/ holds everything produced for one reporting month:
#   Supplier_Reports/<BD|CN>_Region/*.pdf, Supplier_Data/<BD|CN>_Region/*.xlsx,
#   Summary_Report_<Month>_<Year>.xlsx, KPI_Report_<Month>_<Year>.pdf
SUPPLIER_REPORTS = "Supplier_Reports"
SUPPLIER_DATA = "Supplier_Data"


def month_folder(month) -> Path:
    """e.g. output/2026_August - no spaces in folder names."""
    return OUTPUT_DIR / f"{month:%Y_%B}"


def setup_logging() -> None:
    """Log to logs/run.log and the console."""
    LOG_FILE.parent.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout),
        ],
    )
