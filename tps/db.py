"""PostgreSQL connection, schema and table maintenance."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from tps.config import CONFIG

_db = CONFIG["database"]

engine = create_engine(
    f"postgresql+psycopg2://{_db['user']}:{_db['password']}"
    f"@{_db['host']}:{_db['port']}/{_db['name']}"
)
_SessionFactory = sessionmaker(bind=engine)


def get_session() -> Session:
    return _SessionFactory()


def init_db() -> None:
    """Drop and recreate raw_data; create supplier_emails if missing."""
    with engine.connect() as conn:
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
        conn.commit()
    init_supplier_emails_table()
    ensure_indexes()


def ensure_indexes() -> None:
    """Every report query filters on supplier and/or handover month; without these
    each one scans the whole table (measured: 8.7 s -> 0.12 s per supplier report)."""
    with engine.connect() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS raw_data_supplier_date_idx ON raw_data (supplier, handover_date)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS raw_data_handover_date_idx ON raw_data (handover_date)"))
        conn.commit()


def init_supplier_emails_table() -> None:
    """Creates the supplier_emails table if it doesn't exist."""
    with engine.connect() as conn:
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
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM supplier_emails"))
        conn.commit()


def clear_all_tables() -> None:
    """Clears all rows from all data tables."""
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM raw_data"))
        conn.execute(text("DELETE FROM supplier_emails"))
        conn.commit()


def insert_supplier_email(supplier_name: str, email: str) -> None:
    """Inserts a single supplier/email pair. Supplier name is lowercased."""
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO supplier_emails (supplier_name, email) VALUES (:supplier, :email) ON CONFLICT DO NOTHING"),
            {"supplier": supplier_name.strip().lower(), "email": email.strip()}
        )
        conn.commit()
