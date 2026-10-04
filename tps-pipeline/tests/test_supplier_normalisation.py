import sys
sys.path.insert(0, "..")
from supplier_normalisation import normalise_supplier


class TestNormaliseSupplier:
    def test_known_supplier(self):
        assert normalise_supplier("WEIHAI BETTEX INTERNATIONAL TRADING CO., LTD") == "BETTEX (HK) LIMITED (80243)"

    def test_unknown_supplier(self):
        assert normalise_supplier("UNKNOWN SUPPLIER") == "UNKNOWN SUPPLIER"

    def test_whitespace_stripping(self):
        assert normalise_supplier("  BETTEX (HK) LIMITED (80243)  ") == "BETTEX (HK) LIMITED (80243)"
