from pathlib import Path

import yaml
from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from typing import List, Dict

CONFIG_PATH = Path(__file__).parent / "config.yaml"

with open(CONFIG_PATH) as f:
    _config = yaml.safe_load(f)

_db_config = _config["database"]

_engine = create_engine(
    f"postgresql+psycopg2://{_db_config['user']}:{_db_config['password']}"
    f"@{_db_config['host']}:{_db_config['port']}/{_db_config['name']}"
)
_SessionFactory = sessionmaker(bind=_engine)

SUPPLIER_NORMALISATION = {
    "WEIHAI BETTEX INTERNATIONAL TRADING CO., LTD": "BETTEX (HK) LIMITED (80243)",
    "YIWU HONGZHOU IMPORT & EXPORT CO LTD": "HOME JOY TEXTILE CO. LIMITED (82056)",
    "HIGH HOPE INTERNATIONAL G": "JIANGSU HUAJING INTERNATIONAL TRADE CO LTD (80070)",
    "ZHEJIANG ZHUJI IMP&EXP CO LTD": "ZHEJIANG LIJIA FOREIGN TRADE CO LTD (82990)",
    "BODYLINE (PRIVATE) LIMITED": "BODYLINE TRADING (PRIVATE) LIMITED (67247)",
    "PENTI CORAP SANAYI VE TICARET AS": "PENTI GIYIM TICARET A.S (80651)",
    "FUZHOU BICANO TRADING CO. LIMITED": "HONG KONG DIJIA TUO TECHNOLOGY CO., LIMITED (83666)",
    "TEXPORT SYNDICATE LIMITED": "TEXPORT SYNDICATE PRIVATE LIMITED (83002)",
    "JADE FOOTWEAR CO LTD": "ABUNDANT GRACE LIMITED (80064)",
    "SAIDE TEKSTIL": "SAIDE GROUP DIS TICARET AS (80111)",
    # Source files now deliver the post-rename name directly (without the ID
    # suffix) instead of the original pre-rename name above, so the old keys
    # never match. These entries key on that current spelling instead.
    "BETTEX (HK) LIMITED": "BETTEX (HK) LIMITED (80243)",
    "BODYLINE TRADING (PRIVATE) LIMITED": "BODYLINE TRADING (PRIVATE) LIMITED (67247)",
    "PENTI GIYIM TICARET A.S.": "PENTI GIYIM TICARET A.S (80651)",
    "TEXPORT SYNDICATE PRIVATE LIMITED": "TEXPORT SYNDICATE PRIVATE LIMITED (83002)",
    "SAIDE GROUP DIS TICARET AS": "SAIDE GROUP DIS TICARET AS (80111)",
}


def init_db() -> None:
    with _engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS raw_data CASCADE"))
        conn.execute(text("""
        CREATE TABLE raw_data (
            id SERIAL PRIMARY KEY,
            area TEXT,
            sub_area TEXT,
            origin_country TEXT,
            origin_port TEXT,
            supplier TEXT,
            factory TEXT,
            destination_po TEXT,
            kimball TEXT,
            colour_code TEXT,
            description TEXT,
            size TEXT,
            po_qty INTEGER,
            handover_date DATE,
            carton_matrix_code TEXT,
            units_per_carton INTEGER,
            carton_length_mm INTEGER,
            carton_width_mm INTEGER,
            carton_height_mm INTEGER,
            packaging_supplier TEXT,
            updated_date TIMESTAMPTZ,
            updated_by TEXT,
            approved_date TIMESTAMPTZ,
            approved_by TEXT,
            packaging_status TEXT,
            source_file TEXT,
            carton_type TEXT,
            cbm NUMERIC(10,4),
            density NUMERIC(10,2),
            compliance_status TEXT
        )
        """))
        init_supplier_emails_table()
        conn.commit()


def get_session() -> Session:
    return _SessionFactory()


def init_supplier_emails_table() -> None:
    """Creates the supplier_emails table if it doesn't exist."""
    with _engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS supplier_emails (
                id SERIAL PRIMARY KEY,
                supplier_name TEXT NOT NULL,
                email TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS supplier_emails_supplier_email_idx
            ON supplier_emails (supplier_name, email)
        """))
        conn.commit()


def clear_supplier_emails() -> None:
    """Clears all rows from the supplier_emails table."""
    with _engine.connect() as conn:
        conn.execute(text("DELETE FROM supplier_emails"))
        conn.commit()


def clear_raw_data() -> None:
    """Clears all rows from the raw_data table."""
    with _engine.connect() as conn:
        conn.execute(text("DELETE FROM raw_data"))
        conn.commit()


def clear_all_tables() -> None:
    """Clears all rows from all data tables."""
    with _engine.connect() as conn:
        conn.execute(text("DELETE FROM raw_data"))
        conn.execute(text("DELETE FROM supplier_emails"))
        conn.commit()


def insert_supplier_email(supplier_name: str, email: str) -> None:
    """Inserts a single supplier/email pair. Supplier name is lowercased."""
    with _engine.connect() as conn:
        conn.execute(
            text("INSERT INTO supplier_emails (supplier_name, email) VALUES (:supplier, :email) ON CONFLICT DO NOTHING"),
            {"supplier": supplier_name.strip().lower(), "email": email.strip()}
        )
        conn.commit()


def normalise_supplier(raw_name: str) -> str:
    stripped = raw_name.strip()
    return SUPPLIER_NORMALISATION.get(stripped, stripped)


# Alias for backwards compatibility
engine = _engine