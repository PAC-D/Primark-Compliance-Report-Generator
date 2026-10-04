from unittest.mock import patch

import openpyxl
import pytest

from tps.ingest import import_supplier_emails, load_excel


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
        from unittest.mock import patch
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
        from unittest.mock import patch
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
        from unittest.mock import patch
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
        from unittest.mock import patch
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
        from unittest.mock import patch
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
        from unittest.mock import patch
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
    def inserted(self):
        rows = []
        with patch("tps.ingest.init_supplier_emails_table"), \
             patch("tps.ingest.clear_supplier_emails") as clear, \
             patch("tps.ingest.insert_supplier_email", side_effect=lambda s, e: rows.append((s, e))):
            yield rows
            clear.assert_called_once()

    def _workbook(self, tmp_path, header, *rows):
        wb = openpyxl.Workbook()
        wb.active.append(header)
        for row in rows:
            wb.active.append(row)
        path = tmp_path / "emails.xlsx"
        wb.save(path)
        return str(path)

    def test_splits_multiple_addresses_and_skips_blanks(self, tmp_path, inserted):
        path = self._workbook(tmp_path, ["Email", "Supplier Name"],
                              ["a@x.com; b@x.com,", "ACME"], [None, "NO EMAIL LTD"])
        assert import_supplier_emails(path) == 2
        assert inserted == [("ACME", "a@x.com"), ("ACME", "b@x.com")]

    def test_missing_columns_raise(self, tmp_path):
        path = self._workbook(tmp_path, ["Supplier", "Contact"], ["ACME", "a@x.com"])
        with pytest.raises(ValueError, match="Could not find"):
            import_supplier_emails(path)
