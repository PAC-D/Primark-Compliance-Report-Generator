import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "supplier-data-extractor"))

from safe_filename import safe_filename


class TestSafeFilename:
    def test_preserves_ampersand(self):
        assert safe_filename("HANGZHOU BESTSINO IMP & EXP CO LTD") == "HANGZHOU BESTSINO IMP & EXP CO LTD"

    def test_preserves_period(self):
        assert safe_filename("HAPPY PUNT S.L.U.") == "HAPPY PUNT S.L.U."

    def test_preserves_parentheses(self):
        assert safe_filename("BETTEX (HK) LIMITED") == "BETTEX (HK) LIMITED"

    def test_preserves_hyphen(self):
        assert safe_filename("Guangdong Pan-Think Footwear Co Ltd") == "Guangdong Pan-Think Footwear Co Ltd"

    def test_preserves_comma(self):
        assert safe_filename("JIANGSU SOHO TECHNOLOGY TRADING CO., LTD") == "JIANGSU SOHO TECHNOLOGY TRADING CO., LTD"

    def test_preserves_ampersand_no_spaces(self):
        assert safe_filename("P&R HK Holdings Limited") == "P&R HK Holdings Limited"

    def test_preserves_apostrophe_safe(self):
        assert safe_filename("Supplier's Name") == "Supplier's Name"

    def test_replaces_illegal_forward_slash(self):
        assert safe_filename("A/B Supplier") == "A_B Supplier"

    def test_replaces_illegal_backslash(self):
        assert safe_filename("A\\B Supplier") == "A_B Supplier"

    def test_replaces_illegal_colon(self):
        assert safe_filename("A:B Supplier") == "A_B Supplier"

    def test_replaces_illegal_asterisk(self):
        assert safe_filename("A*B Supplier") == "A_B Supplier"

    def test_replaces_illegal_question_mark(self):
        assert safe_filename("A?B Supplier") == "A_B Supplier"

    def test_replaces_illegal_pipe(self):
        assert safe_filename("A|B Supplier") == "A_B Supplier"

    def test_replaces_illegal_less_than(self):
        assert safe_filename("A<B Supplier") == "A_B Supplier"

    def test_replaces_illegal_greater_than(self):
        assert safe_filename("A>B Supplier") == "A_B Supplier"

    def test_replaces_illegal_double_quote(self):
        assert safe_filename('A"B Supplier') == "A_B Supplier"

    def test_preserves_alphanumeric(self):
        assert safe_filename("ABC123 Supplier") == "ABC123 Supplier"
