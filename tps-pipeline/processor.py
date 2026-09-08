import shutil
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from database import engine, normalise_supplier

DROPPED_COLUMNS = [
    "Carton Specification(s)", "Priority", "Pack Type",
    "Pallet Plan(s)", "Container Plan(s)", "Dialog(s)",
    "ProductSKULine", "Colour"
]

COLUMN_RENAME = {
    "Area": "area",
    "Sub-Area": "sub_area",
    "Current Handover Date": "handover_date",
    "Origin Country": "origin_country",
    "Origin Port": "origin_port",
    "Supplier": "supplier",
    "Factory": "factory",
    "Destination PO": "destination_po",
    "Kimball": "kimball",
    "Colour Code": "colour_code",
    "Description": "description",
    "Size": "size",
    "PO Qty": "po_qty",
    "Carton Matrix Code": "carton_matrix_code",
    "Units Per Carton": "units_per_carton",
    "Outer Carton Length (mm)": "carton_length_mm",
    "Outer Carton Width (mm)": "carton_width_mm",
    "Outer Carton Height (mm)": "carton_height_mm",
    "Packaging Supplier": "packaging_supplier",
    "Updated Date": "updated_date",
    "Updated By": "updated_by",
    "Approved Date": "approved_date",
    "Approved By": "approved_by",
    "Packaging Confirmation Status": "packaging_status",
}


def load_excel(filepath: str) -> pd.DataFrame:
    df = pd.read_excel(filepath)

    df.drop(columns=[c for c in DROPPED_COLUMNS if c in df.columns], inplace=True)

    df.rename(columns=COLUMN_RENAME, inplace=True)

    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace("nan", None)

    if "supplier" in df.columns:
        df["supplier"] = df["supplier"].apply(lambda x: normalise_supplier(str(x)) if pd.notna(x) and x != "None" else x)

    numeric_cols = ["po_qty", "units_per_carton", "carton_length_mm", "carton_width_mm", "carton_height_mm"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "handover_date" in df.columns:
        df["handover_date"] = pd.to_datetime(df["handover_date"], errors="coerce").dt.date

    if "updated_date" in df.columns:
        df["updated_date"] = pd.to_datetime(df["updated_date"], errors="coerce")

    if "approved_date" in df.columns:
        df["approved_date"] = pd.to_datetime(df["approved_date"], errors="coerce")

    df["carton_type"] = df["carton_matrix_code"].apply(lambda x: "Standard" if pd.notna(x) and str(x) not in ("", "None", "nan") else "Custom")

    def calc_cbm(row):
        l = row.get("carton_length_mm")
        w = row.get("carton_width_mm")
        h = row.get("carton_height_mm")
        if pd.isna(l) or pd.isna(w) or pd.isna(h):
            return None
        return round((l / 1000) * (w / 1000) * (h / 1000), 4)

    df["cbm"] = df.apply(calc_cbm, axis=1)

    def calc_density(row):
        cbm = row.get("cbm")
        units = row.get("units_per_carton")
        if pd.isna(cbm) or cbm == 0 or pd.isna(units):
            return None
        return round(units / cbm, 2)

    df["density"] = df.apply(calc_density, axis=1)

    def calc_compliance(row):
        status = row.get("packaging_status")
        handover = row.get("handover_date")
        updated = row.get("updated_date")

        if pd.isna(status) or status != "Approved":
            return "Non-compliant"
        if pd.isna(handover):
            return "Non-compliant"
        if pd.isna(updated):
            return "Non-compliant"

        updated_naive = updated.tz_localize(None) if updated.tzinfo else updated
        if updated_naive.date() > handover:
            return "Non-compliant"

        return "Compliant"

    df["compliance_status"] = df.apply(calc_compliance, axis=1)

    df["source_file"] = Path(filepath).name

    return df


def process_file(filepath: str) -> int:
    df = load_excel(filepath)

    columns = [
        "area", "sub_area", "origin_country", "origin_port", "supplier", "factory",
        "destination_po", "kimball", "colour_code", "description", "size", "po_qty",
        "handover_date", "carton_matrix_code", "units_per_carton",
        "carton_length_mm", "carton_width_mm", "carton_height_mm", "packaging_supplier",
        "updated_date", "updated_by", "approved_date", "approved_by", "packaging_status",
        "source_file", "carton_type", "cbm", "density", "compliance_status"
    ]
    available_cols = [c for c in columns if c in df.columns]

    records = df[available_cols].where(pd.notnull(df[available_cols]), None).to_dict(orient="records")

    for record in records:
        for k, v in record.items():
            if isinstance(v, pd.Timestamp):
                record[k] = v.to_pydatetime()
            elif pd.isna(v):
                record[k] = None

    col_names = ", ".join(available_cols)
    placeholders = ", ".join([f":{c}" for c in available_cols])

    with engine.begin() as conn:
        conn.execute(text(f"INSERT INTO raw_data ({col_names}) VALUES ({placeholders})"), records)

    return len(df)


def is_file_processed(filepath: str) -> bool:
    filename = Path(filepath).name
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1 FROM raw_data WHERE source_file = :filename LIMIT 1"), {"filename": filename})
        return result.fetchone() is not None


def copy_to_data(filepath: str) -> None:
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    shutil.copy2(filepath, data_dir / Path(filepath).name)