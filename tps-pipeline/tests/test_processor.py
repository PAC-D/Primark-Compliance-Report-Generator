import pytest
import sys
sys.path.insert(0, "..")
from processor import load_excel
from database import normalise_supplier


class TestNormaliseSupplier:
    def test_known_supplier(self):
        assert normalise_supplier("WEIHAI BETTEX INTERNATIONAL TRADING CO., LTD") == "BETTEX (HK) LIMITED (80243)"

    def test_unknown_supplier(self):
        assert normalise_supplier("UNKNOWN SUPPLIER") == "UNKNOWN SUPPLIER"

    def test_whitespace_stripping(self):
        assert normalise_supplier("  BETTEX (HK) LIMITED (80243)  ") == "BETTEX (HK) LIMITED (80243)"

    def test_case_sensitivity(self):
        assert normalise_supplier("weihai bettex international trading co., ltd") == "weihai bettex international trading co., ltd"

    def test_maps_current_source_spelling_to_id_suffixed_name(self):
        # Primark's source files already emit the post-rename name (without the
        # ID suffix) rather than the original pre-rename name, so the mapping
        # needs a key on that current spelling to ever produce the ID-suffixed form.
        assert normalise_supplier("PENTI GIYIM TICARET A.S.") == "PENTI GIYIM TICARET A.S (80651)"
        assert normalise_supplier("SAIDE GROUP DIS TICARET AS") == "SAIDE GROUP DIS TICARET AS (80111)"
        assert normalise_supplier("BODYLINE TRADING (PRIVATE) LIMITED") == "BODYLINE TRADING (PRIVATE) LIMITED (67247)"
        assert normalise_supplier("TEXPORT SYNDICATE PRIVATE LIMITED") == "TEXPORT SYNDICATE PRIVATE LIMITED (83002)"
        assert normalise_supplier("BETTEX (HK) LIMITED") == "BETTEX (HK) LIMITED (80243)"


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
        with patch('processor.normalise_supplier', side_effect=lambda x: x):
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
        with patch('processor.normalise_supplier', side_effect=lambda x: x):
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
        with patch('processor.normalise_supplier', side_effect=lambda x: x):
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
        with patch('processor.normalise_supplier', side_effect=lambda x: x):
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
        with patch('processor.normalise_supplier', side_effect=lambda x: x):
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
        with patch('processor.normalise_supplier', side_effect=lambda x: x):
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