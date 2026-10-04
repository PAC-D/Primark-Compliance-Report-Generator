from datetime import date
from unittest.mock import patch

import pytest

from tps import common
from tps.common import (
    add_months,
    ask_report_month,
    month_label,
    months_back,
    next_month_start,
    normalise_supplier,
    report_region,
    safe_filename,
)


class TestSafeFilename:
    @pytest.mark.parametrize("name", [
        "HANGZHOU BESTSINO IMP & EXP CO LTD",
        "HAPPY PUNT S.L.U.",
        "BETTEX (HK) LIMITED",
        "Guangdong Pan-Think Footwear Co Ltd",
        "JIANGSU SOHO TECHNOLOGY TRADING CO., LTD",
        "P&R HK Holdings Limited",
        "Supplier's Name",
        "ABC123 Supplier",
    ])
    def test_keeps_legal_punctuation(self, name):
        assert safe_filename(name) == name

    @pytest.mark.parametrize("char", list('/\\:*?|<>"'))
    def test_replaces_illegal_characters(self, char):
        assert safe_filename(f"A{char}B Supplier") == "A_B Supplier"


class TestNormaliseSupplier:
    def test_known_supplier(self):
        assert normalise_supplier("WEIHAI BETTEX INTERNATIONAL TRADING CO., LTD") == "BETTEX (HK) LIMITED (80243)"

    def test_unknown_supplier(self):
        assert normalise_supplier("UNKNOWN SUPPLIER") == "UNKNOWN SUPPLIER"

    def test_whitespace_stripping(self):
        assert normalise_supplier("  BETTEX (HK) LIMITED (80243)  ") == "BETTEX (HK) LIMITED (80243)"

    def test_case_sensitive(self):
        name = "weihai bettex international trading co., ltd"
        assert normalise_supplier(name) == name

    def test_maps_current_source_spelling_to_id_suffixed_name(self):
        # Source files already emit the post-rename name (without the ID
        # suffix), so the mapping needs a key on that spelling too.
        assert normalise_supplier("PENTI GIYIM TICARET A.S.") == "PENTI GIYIM TICARET A.S (80651)"
        assert normalise_supplier("SAIDE GROUP DIS TICARET AS") == "SAIDE GROUP DIS TICARET AS (80111)"
        assert normalise_supplier("BODYLINE TRADING (PRIVATE) LIMITED") == "BODYLINE TRADING (PRIVATE) LIMITED (67247)"
        assert normalise_supplier("TEXPORT SYNDICATE PRIVATE LIMITED") == "TEXPORT SYNDICATE PRIVATE LIMITED (83002)"
        assert normalise_supplier("BETTEX (HK) LIMITED") == "BETTEX (HK) LIMITED (80243)"


class TestReportRegion:
    def test_any_cn_country_means_cn(self):
        assert report_region("Bangladesh, China".split(",")) == "CN Region"

    def test_bd_only(self):
        assert report_region(["Bangladesh", "India"]) == "BD Region"

    def test_unlisted_country_is_bd(self):
        assert report_region(["Egypt"]) == "BD Region"


class TestMonths:
    def test_month_label(self):
        assert month_label(date(2026, 6, 1)) == "Jun '26"

    def test_add_months_crosses_years(self):
        assert add_months(date(2026, 1, 15), -1) == date(2025, 12, 1)
        assert add_months(date(2025, 12, 1), 1) == date(2026, 1, 1)
        assert add_months(date(2026, 6, 1), -12) == date(2025, 6, 1)

    def test_next_month_start(self):
        assert next_month_start(date(2026, 12, 1)) == date(2027, 1, 1)

    def test_months_back_full_year(self):
        months = months_back(date(2026, 6, 1), date(2020, 1, 1))
        assert len(months) == 12
        assert months[0] == date(2025, 7, 1)
        assert months[-1] == date(2026, 6, 1)

    def test_months_back_stops_at_earliest_month(self):
        months = months_back(date(2026, 6, 1), date(2026, 4, 20))
        assert months == [date(2026, 4, 1), date(2026, 5, 1), date(2026, 6, 1)]

    def test_months_back_empty_when_earliest_is_later(self):
        assert months_back(date(2026, 6, 1), date(2026, 7, 1)) == []


class TestAskReportMonth:
    def test_explicit_month(self):
        with patch("builtins.input", side_effect=["2025", "3"]):
            assert ask_report_month("X") == date(2025, 3, 1)

    def test_blank_gives_default(self):
        with patch("builtins.input", side_effect=["", ""]), \
             patch.object(common, "get_report_month", return_value=date(2026, 9, 1)):
            assert ask_report_month("X") == date(2026, 9, 1)

    def test_invalid_month_gives_default(self, capsys):
        with patch("builtins.input", side_effect=["2026", "13"]), \
             patch.object(common, "get_report_month", return_value=date(2026, 9, 1)):
            assert ask_report_month("X") == date(2026, 9, 1)
        assert "Invalid date" in capsys.readouterr().out
