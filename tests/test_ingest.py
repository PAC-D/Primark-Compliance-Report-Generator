from unittest.mock import MagicMock, patch

import openpyxl
import pandas as pd
import pytest

from tps.ingest import import_supplier_emails, load_excel, process_file


class TestCartonType:
    def test_cartons_type_standard(self):
        data = {
            "Current Handover Date": ["2024-01-15"],
            "Origin Country": ["China"],
            "Origin Port": ["Shanghai"],
            "Supplier": ["Test Supplier"],
            "Factory": ["Factory 1"],
            "Destination PO": ["PO001"],
            "Kimball": ["K001"],
            "Description": ["Test Product"],
            "Colour Code": ["Red"],
            "Size": ["M"],
            "PO Qty": [100],
            "Carton Matrix Code": ["MATRIX123"],
            "Units Per Carton": [12],
            "Outer Carton Type": ["Regular"],
            "Outer Carton Length (mm)": [300],
            "Outer Carton Width (mm)": [200],
            "Outer Carton Height (mm)": [150],
            "Packaging Supplier": ["PackSup"],
            "Updated Date": ["2024-01-10"],
            "Updated By": ["User1"],
            "Approved Date": ["2024-01-10"],
            "Approved By": ["Approver1"],
            "Packaging Confirmation Status": ["Approved"],
        }
        import pandas as pd
        df = pd.DataFrame(data)
        result = load_excel.__wrapped__(df) if hasattr(load_excel, '__wrapped__') else None
        
        if result is None:
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
                df.to_excel(f.name, index=False)
                temp_path = f.name
            try:
                result = load_excel(temp_path)
            finally:
                os.unlink(temp_path)
        
        assert result.iloc[0]["carton_type"] == "Standard"

    def test_cartons_type_custom(self):
        data = {
            "Current Handover Date": ["2024-01-15"],
            "Origin Country": ["China"],
            "Origin Port": ["Shanghai"],
            "Supplier": ["Test Supplier"],
            "Factory": ["Factory 1"],
            "Destination PO": ["PO001"],
            "Kimball": ["K001"],
            "Description": ["Test Product"],
            "Colour Code": ["Red"],
            "Size": ["M"],
            "PO Qty": [100],
            "Carton Matrix Code": [None],
            "Units Per Carton": [12],
            "Outer Carton Type": ["Regular"],
            "Outer Carton Length (mm)": [300],
            "Outer Carton Width (mm)": [200],
            "Outer Carton Height (mm)": [150],
            "Packaging Supplier": ["PackSup"],
            "Updated Date": ["2024-01-10"],
            "Updated By": ["User1"],
            "Approved Date": ["2024-01-10"],
            "Approved By": ["Approver1"],
            "Packaging Confirmation Status": ["Approved"],
        }
        import pandas as pd
        from unittest.mock import MagicMock, patch
        with patch('tps.ingest.normalise_supplier', side_effect=lambda x: x):
            df = pd.DataFrame(data)
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
                df.to_excel(f.name, index=False)
                temp_path = f.name
            try:
                result = load_excel(temp_path)
            finally:
                os.unlink(temp_path)
            assert result.iloc[0]["carton_type"] == "Custom"


class TestCBMCalculation:
    def test_cbm_calculation(self):
        data = {
            "Current Handover Date": ["2024-01-15"],
            "Origin Country": ["China"],
            "Origin Port": ["Shanghai"],
            "Supplier": ["Test Supplier"],
            "Factory": ["Factory 1"],
            "Destination PO": ["PO001"],
            "Kimball": ["K001"],
            "Description": ["Test Product"],
            "Colour Code": ["Red"],
            "Size": ["M"],
            "PO Qty": [100],
            "Carton Matrix Code": ["MATRIX123"],
            "Units Per Carton": [12],
            "Outer Carton Type": ["Regular"],
            "Outer Carton Length (mm)": [1000],
            "Outer Carton Width (mm)": [1000],
            "Outer Carton Height (mm)": [1000],
            "Packaging Supplier": ["PackSup"],
            "Updated Date": ["2024-01-10"],
            "Updated By": ["User1"],
            "Approved Date": ["2024-01-10"],
            "Approved By": ["Approver1"],
            "Packaging Confirmation Status": ["Approved"],
        }
        import pandas as pd
        from unittest.mock import MagicMock, patch
        with patch('tps.ingest.normalise_supplier', side_effect=lambda x: x):
            df = pd.DataFrame(data)
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
                df.to_excel(f.name, index=False)
                temp_path = f.name
            try:
                result = load_excel(temp_path)
            finally:
                os.unlink(temp_path)
            assert result.iloc[0]["cbm"] == 1.0

    def test_cbm_missing_dimension_returns_none(self):
        data = {
            "Current Handover Date": ["2024-01-15"],
            "Origin Country": ["China"],
            "Origin Port": ["Shanghai"],
            "Supplier": ["Test Supplier"],
            "Factory": ["Factory 1"],
            "Destination PO": ["PO001"],
            "Kimball": ["K001"],
            "Description": ["Test Product"],
            "Colour Code": ["Red"],
            "Size": ["M"],
            "PO Qty": [100],
            "Carton Matrix Code": ["MATRIX123"],
            "Units Per Carton": [12],
            "Outer Carton Type": ["Regular"],
            "Outer Carton Length (mm)": [1000],
            "Outer Carton Width (mm)": [None],
            "Outer Carton Height (mm)": [1000],
            "Packaging Supplier": ["PackSup"],
            "Updated Date": ["2024-01-10"],
            "Updated By": ["User1"],
            "Approved Date": ["2024-01-10"],
            "Approved By": ["Approver1"],
            "Packaging Confirmation Status": ["Approved"],
        }
        import pandas as pd
        from unittest.mock import MagicMock, patch
        with patch('tps.ingest.normalise_supplier', side_effect=lambda x: x):
            df = pd.DataFrame(data)
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
                df.to_excel(f.name, index=False)
                temp_path = f.name
            try:
                result = load_excel(temp_path)
            finally:
                os.unlink(temp_path)
            assert result.iloc[0]["cbm"] is None


class TestComplianceStatus:
    def test_compliance_status_approved_with_valid_dates(self):
        data = {
            "Current Handover Date": ["2024-01-20"],
            "Origin Country": ["China"],
            "Origin Port": ["Shanghai"],
            "Supplier": ["Test Supplier"],
            "Factory": ["Factory 1"],
            "Destination PO": ["PO001"],
            "Kimball": ["K001"],
            "Description": ["Test Product"],
            "Colour Code": ["Red"],
            "Size": ["M"],
            "PO Qty": [100],
            "Carton Matrix Code": ["MATRIX123"],
            "Units Per Carton": [12],
            "Outer Carton Type": ["Regular"],
            "Outer Carton Length (mm)": [300],
            "Outer Carton Width (mm)": [200],
            "Outer Carton Height (mm)": [150],
            "Packaging Supplier": ["PackSup"],
            "Updated Date": ["2024-01-15"],
            "Updated By": ["User1"],
            "Approved Date": ["2024-01-15"],
            "Approved By": ["Approver1"],
            "Packaging Confirmation Status": ["Approved"],
        }
        import pandas as pd
        from unittest.mock import MagicMock, patch
        with patch('tps.ingest.normalise_supplier', side_effect=lambda x: x):
            df = pd.DataFrame(data)
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
                df.to_excel(f.name, index=False)
                temp_path = f.name
            try:
                result = load_excel(temp_path)
            finally:
                os.unlink(temp_path)
            assert result.iloc[0]["compliance_status"] == "Compliant"

    def test_compliance_status_rejected(self):
        data = {
            "Current Handover Date": ["2024-01-20"],
            "Origin Country": ["China"],
            "Origin Port": ["Shanghai"],
            "Supplier": ["Test Supplier"],
            "Factory": ["Factory 1"],
            "Destination PO": ["PO001"],
            "Kimball": ["K001"],
            "Description": ["Test Product"],
            "Colour Code": ["Red"],
            "Size": ["M"],
            "PO Qty": [100],
            "Carton Matrix Code": ["MATRIX123"],
            "Units Per Carton": [12],
            "Outer Carton Type": ["Regular"],
            "Outer Carton Length (mm)": [300],
            "Outer Carton Width (mm)": [200],
            "Outer Carton Height (mm)": [150],
            "Packaging Supplier": ["PackSup"],
            "Updated Date": ["2024-01-15"],
            "Updated By": ["User1"],
            "Approved Date": ["2024-01-15"],
            "Approved By": ["Approver1"],
            "Packaging Confirmation Status": ["Rejected"],
        }
        import pandas as pd
        from unittest.mock import MagicMock, patch
        with patch('tps.ingest.normalise_supplier', side_effect=lambda x: x):
            df = pd.DataFrame(data)
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
                df.to_excel(f.name, index=False)
                temp_path = f.name
            try:
                result = load_excel(temp_path)
            finally:
                os.unlink(temp_path)
            assert result.iloc[0]["compliance_status"] == "Non-compliant"

    def test_compliance_status_updated_after_handover(self):
        data = {
            "Current Handover Date": ["2024-01-15"],
            "Origin Country": ["China"],
            "Origin Port": ["Shanghai"],
            "Supplier": ["Test Supplier"],
            "Factory": ["Factory 1"],
            "Destination PO": ["PO001"],
            "Kimball": ["K001"],
            "Description": ["Test Product"],
            "Colour Code": ["Red"],
            "Size": ["M"],
            "PO Qty": [100],
            "Carton Matrix Code": ["MATRIX123"],
            "Units Per Carton": [12],
            "Outer Carton Type": ["Regular"],
            "Outer Carton Length (mm)": [300],
            "Outer Carton Width (mm)": [200],
            "Outer Carton Height (mm)": [150],
            "Packaging Supplier": ["PackSup"],
            "Updated Date": ["2024-01-20"],
            "Updated By": ["User1"],
            "Approved Date": ["2024-01-20"],
            "Approved By": ["Approver1"],
            "Packaging Confirmation Status": ["Approved"],
        }
        import pandas as pd
        from unittest.mock import MagicMock, patch
        with patch('tps.ingest.normalise_supplier', side_effect=lambda x: x):
            df = pd.DataFrame(data)
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
                df.to_excel(f.name, index=False)
                temp_path = f.name
            try:
                result = load_excel(temp_path)
            finally:
                os.unlink(temp_path)
            assert result.iloc[0]["compliance_status"] == "Non-compliant"

class TestImportSupplierEmails:
    @pytest.fixture
    def stored(self):
        """What import_supplier_emails hands to set_supplier_emails."""
        calls = []
        with patch("tps.ingest.init_supplier_emails_table"), \
             patch("tps.ingest.set_supplier_emails", side_effect=calls.append):
            yield calls

    def _workbook(self, tmp_path, header, *rows):
        wb = openpyxl.Workbook()
        wb.active.append(header)
        for row in rows:
            wb.active.append(row)
        path = tmp_path / "emails.xlsx"
        wb.save(path)
        return str(path)

    def test_splits_multiple_addresses_and_skips_blanks(self, tmp_path, stored):
        path = self._workbook(tmp_path, ["Email", "Supplier Name"],
                              ["a@x.com; b@x.com,", "ACME"], [None, "NO EMAIL LTD"])
        assert import_supplier_emails(path) == 1
        # Only suppliers in the file with an address are replaced; nothing else is touched.
        assert stored == [{"acme": ["a@x.com", "b@x.com"]}]

    def test_rows_of_one_supplier_are_combined(self, tmp_path, stored):
        path = self._workbook(tmp_path, ["Supplier Name", "Email"],
                              ["ACME", "a@x.com"], [" acme ", "b@x.com"])
        import_supplier_emails(path)
        assert stored == [{"acme": ["a@x.com", "b@x.com"]}]

    def test_missing_columns_raise(self, tmp_path):
        path = self._workbook(tmp_path, ["Supplier", "Contact"], ["ACME", "a@x.com"])
        with pytest.raises(ValueError, match="Could not find"):
            import_supplier_emails(path)

def test_process_file_replaces_rows_of_the_same_file(tmp_path):
    path = tmp_path / "Multi Search (Packaging Management)_2026_May_1-15.xlsx"
    pd.DataFrame({"Supplier": ["ACME"], "Carton Matrix Code": [None],
                  "Packaging Confirmation Status": ["Pending"]}).to_excel(path, index=False)
    engine = MagicMock()
    conn = engine.begin.return_value.__enter__.return_value
    with patch("tps.ingest.get_engine", return_value=engine):
        assert process_file(str(path)) == 1

    delete, insert = conn.execute.call_args_list
    assert str(delete.args[0]).startswith("DELETE FROM raw_data WHERE source_file")
    assert delete.args[1] == {"source_file": path.name}
    assert str(insert.args[0]).startswith("INSERT INTO raw_data")
