"""Paths, config.yaml and logging setup shared by the whole package."""

import logging
import sys
from pathlib import Path

import yaml

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
ASSETS_DIR = PACKAGE_DIR / "assets"
CONFIG_PATH = ROOT / "config.yaml"

with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)

DATA_DIR = ROOT / CONFIG["paths"]["data_dir"]
OUTPUT_DIR = ROOT / CONFIG["paths"]["output_dir"]
LOG_FILE = ROOT / "logs" / "run.log"
REPORT_MONTH_OFFSET = CONFIG.get("app", {}).get("report_month_offset", 1)


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
