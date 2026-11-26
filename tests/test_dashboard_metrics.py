from datetime import date
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest

from tps.metrics import dashboard
from tps.metrics.dashboard import Filters, kpi, line_filter_sql, supplier_compliance

MONTH = date(2026, 6, 1)


def _sup(name, countries, lines, rate, factories=1):
    """A per-supplier month row with `rate`% compliant lines."""
    return NS(supplier=name, countries=countries, factories=factories, lines=lines,
              compliant=round(lines * rate / 100), approved=lines, pending=0, rejected=0, escalated=0)


class FakeSession:
    """Answers each dashboard query by what it asks for. `months` maps a
    month start to its supplier rows."""

    def __init__(self, months, ranks=None, trend=(), countries=(), min_date=date(2026, 1, 1), regions=None):
        self.months, self.ranks, self.trend = months, ranks or {}, trend
        self.country_rows, self.min_date, self.regions = countries, min_date, regions
        self.calls = []

    def execute(self, query, params=None):
        sql = str(query)
        self.calls.append((sql, params))
        if "DENSE_RANK" in sql:
            rows = [NS(supplier=s, dr=r) for s, r in self.ranks.items()]
        elif "all_countries" in sql:
            rows = [NS(supplier=n, all_countries=c) for n, c in self._all_countries().items()]
        elif "MIN(handover_date)" in sql:
            rows = [NS(min_date=self.min_date)]
        elif "GROUP BY month, origin_country" in sql:
            rows = list(self.trend)
        elif "GROUP BY origin_country" in sql:
            rows = list(self.country_rows)
        else:
            rows = self.months.get(params["start"], [])
        return NS(fetchall=lambda: rows, fetchone=lambda: rows[0] if rows else None)

    def _all_countries(self):
        """Every origin country per supplier in the report month: `regions`
        when given, else what the month's rows show."""
        if self.regions is not None:
            return self.regions
        return {r.supplier: r.countries for r in self.months.get(MONTH, [])}

    def close(self):
        pass


def run(f, **kw):
    session = FakeSession(**kw)
    with patch("tps.metrics.dashboard.get_session", return_value=session):
        return supplier_compliance(f), session


def four_suppliers():
    return {MONTH: [_sup("A", ["India"], 1000, 22.1), _sup("B", ["India"], 1000, 44.8),
                    _sup("C", ["India"], 1000, 76.4), _sup("D", ["India"], 1000, 96.1)]}


def test_bands_and_cards():
    out, _ = run(Filters(month=MONTH), months=four_suppliers())
    assert out["month"] == "2026-06"
    assert out["bands"] == {"all": 4, "high": 2, "mid": 1, "low": 1}
    assert out["cards"]["top_count"] == 1
    assert out["totals"] == {"suppliers": 4, "lines": 4000}
    assert [s["name"] for s in out["suppliers"]] == ["A", "B", "C", "D"]
    assert out["suppliers"][0]["compliance"] == 22.1
    assert out["cards"]["status"]["total"] == 4000


def test_follow_up_needs_both_conditions():
    months = {MONTH: [_sup("S", ["India"], 100, 30)],
              date(2026, 5, 1): [_sup("S", ["India"], 100, 60)],
              date(2026, 4, 1): [_sup("S", ["India"], 100, 60)]}
    out, _ = run(Filters(month=MONTH), months=months)
    assert out["suppliers"][0]["avg_3m"] == 50.0
    assert out["suppliers"][0]["change"] == -30.0
    assert out["cards"]["follow_up_count"] == 0
    months[date(2026, 4, 1)] = [_sup("S", ["India"], 100, 10)]
    months[date(2026, 5, 1)] = [_sup("S", ["India"], 100, 20)]
    out, _ = run(Filters(month=MONTH), months=months)
    assert out["cards"]["follow_up_count"] == 1


def test_rank_ignores_filters():
    out, session = run(Filters(month=MONTH, supplier="B"), months={MONTH: [_sup("B", ["India"], 10, 50)]},
                       ranks={"A": 1, "B": 2})
    assert out["suppliers"][0]["rank"] == 2
    rank_sql, rank_params = next(c for c in session.calls if "DENSE_RANK" in c[0])
    assert "ILIKE" not in rank_sql and "supplier" not in rank_params


def test_rank_unaffected_by_country_filter():
    out, session = run(Filters(month=MONTH, country="India"),
                       months={MONTH: [_sup("B", ["India"], 10, 90)]}, ranks={"A": 1, "B": 2})
    assert out["suppliers"][0]["rank"] == 2  # filtered to B alone it would be 1
    _, rank_params = next(c for c in session.calls if "DENSE_RANK" in c[0])
    assert "country" not in rank_params


def test_country_filter_keeps_region_from_all_countries():
    # Lines narrowed to India, but the supplier also ships from China: still CN.
    months = {MONTH: [_sup("Mixed", ["India"], 10, 50)]}
    regions = {"Mixed": ["India", "China"]}
    cn, session = run(Filters(month=MONTH, country="India", region="CN"), months=months, regions=regions)
    assert [s["name"] for s in cn["suppliers"]] == ["Mixed"]
    assert cn["suppliers"][0]["region"] == "CN" and cn["suppliers"][0]["countries"] == ["India"]
    assert any(p and p.get("country") == "India" for _, p in session.calls)
    bd, _ = run(Filters(month=MONTH, country="India", region="BD"), months=months, regions=regions)
    assert bd["suppliers"] == []


def test_factory_filter_narrows_lines():
    months = {MONTH: [_sup("S", ["India"], 7, 50)]}
    out, session = run(Filters(month=MONTH, factory="north"), months=months)
    sql, params = next(c for c in session.calls if c[1] and "factory" in c[1])
    assert "factory ILIKE :factory" in sql and params["factory"] == "%north%"
    assert out["suppliers"][0]["lines"] == 7 and out["totals"]["lines"] == 7


def test_previous_months_follow_region_by_name():
    # Narrowed to China lines this month, while last month the supplier's lines
    # in the same filter were India: it must still be matched by name.
    months = {MONTH: [_sup("Mixed", ["China"], 100, 30)],
              date(2026, 5, 1): [_sup("Mixed", ["India"], 100, 50)]}
    out, _ = run(Filters(month=MONTH, region="CN"), months=months, regions={"Mixed": ["India", "China"]})
    assert out["suppliers"][0]["change"] == -20.0
    assert out["suppliers"][0]["avg_3m"] == 40.0


def test_missing_previous_month_gives_no_change():
    out, _ = run(Filters(month=MONTH), months={MONTH: [_sup("S", ["India"], 10, 50)]})
    assert out["suppliers"][0]["change"] is None
    assert out["cards"]["compliance_change"] is None and out["cards"]["top_change"] is None


def test_top_change_and_compliance_change():
    months = {MONTH: [_sup("A", ["India"], 100, 96), _sup("B", ["India"], 100, 97)],
              date(2026, 5, 1): [_sup("A", ["India"], 100, 96), _sup("B", ["India"], 100, 50)]}
    out, _ = run(Filters(month=MONTH), months=months)
    assert out["cards"]["top_count"] == 2 and out["cards"]["top_change"] == 1
    assert out["cards"]["compliance"] == 96.5 and out["cards"]["compliance_change"] == 23.5


def test_countries_ordered_by_rate_descending():
    rows = [NS(country="China", compliant=1, total=2), NS(country="India", compliant=9, total=10),
            NS(country="Turkey", compliant=3, total=4)]
    out, _ = run(Filters(month=MONTH), months=four_suppliers(), countries=rows)
    assert out["countries"] == [{"country": "India", "rate": 90.0},
                                {"country": "Turkey", "rate": 75.0},
                                {"country": "China", "rate": 50.0}]


def test_region_filter_uses_report_region():
    months = {MONTH: [_sup("Mixed", ["India", "China"], 10, 50), _sup("Bd", ["India"], 10, 50)]}
    cn, _ = run(Filters(month=MONTH, region="CN"), months=months)
    assert [s["name"] for s in cn["suppliers"]] == ["Mixed"]
    assert cn["suppliers"][0]["region"] == "CN"
    bd, _ = run(Filters(month=MONTH, region="BD"), months=months)
    assert [s["name"] for s in bd["suppliers"]] == ["Bd"]


def test_empty_month():
    out, _ = run(Filters(month=MONTH), months={})
    assert out["totals"] == {"suppliers": 0, "lines": 0}
    assert out["bands"] == {"all": 0, "high": 0, "mid": 0, "low": 0}
    assert out["cards"]["compliance"] is None
    assert out["cards"]["compliance_change"] is None
    assert out["cards"]["top_count"] == 0 and out["cards"]["follow_up_count"] == 0
    assert out["cards"]["status"] == {"approved": 0, "pending": 0, "rejected": 0, "escalated": 0, "total": 0}
    assert out["suppliers"] == [] and out["countries"] == []
    assert set(out["trend"]["bd"] + out["trend"]["cn"] + out["trend"]["all"]) == {None}


def test_trend_folds_regions():
    trend = [NS(month=MONTH, country="India", compliant=1, total=2),
             NS(month=MONTH, country="China", compliant=3, total=4)]
    out, _ = run(Filters(month=MONTH), months=four_suppliers(), trend=trend, min_date=MONTH)
    assert out["trend"] == {"labels": ["Jun '26"], "bd": [50.0], "cn": [75.0], "all": [66.7]}


def test_filter_sql_binds_values():
    evil = "x' OR 1=1"
    sql, params = line_filter_sql(Filters(month=MONTH, supplier=evil, region="BD", country="India"),
                                  MONTH, date(2026, 7, 1))
    assert evil not in sql and "BD" not in sql
    assert evil in " ".join(str(v) for v in params.values())
    assert params["country"] == "India" and "ILIKE" in sql


# ---- KPI tab ----

AUG = date(2026, 8, 1)


def _kr(month, country, supplier, factory, lines, active=None):
    return NS(month=month, country=country, supplier=supplier, factory=factory,
              lines=lines, active=lines if active is None else active)


class KpiSession:
    def __init__(self, rows=(), approvers=(), min_date=date(2026, 1, 1)):
        self.rows, self.approvers, self.min_date, self.calls = rows, approvers, min_date, []

    def execute(self, query, params=None):
        sql = str(query)
        self.calls.append((sql, params))
        if "MIN(handover_date)" in sql:
            rows = [NS(min_date=self.min_date)]
        elif "GROUP BY month, approved_by" in sql:
            rows = list(self.approvers)
        else:
            rows = list(self.rows)
        return NS(fetchall=lambda: rows, fetchone=lambda: rows[0] if rows else None)

    def close(self):
        pass


def run_kpi(f, **kw):
    session = KpiSession(**kw)
    with patch("tps.metrics.dashboard.get_session", return_value=session):
        return kpi(f), session


def test_working_day_average():
    rows = [_kr(AUG, "Bangladesh", "S1", "F1", 7000, active=6340), _kr(AUG, "China", "S2", "F2", 50, active=40)]
    out, _ = run_kpi(Filters(month=AUG), rows=rows)
    assert out["cards"]["bd"] == {"lines": 6340, "working_days": 22, "avg": 289}
    assert out["cards"]["cn"] == {"lines": 40, "working_days": 21, "avg": 2}
    assert out["cards"]["lines"] == 7050  # reflected lines count every row


def test_same_month_last_year_missing_is_none():
    rows = [_kr(AUG, "China", "S", "F", 10), _kr(date(2026, 7, 1), "China", "S", "F", 5),
            _kr(date(2025, 8, 1), "India", "S", "F", 3)]
    out, _ = run_kpi(Filters(month=AUG), rows=rows)
    assert out["table_months"] == ["Aug '26", "Jul '26", "Aug '25"]
    cells = {c["country"]: c["cells"] for c in out["countries"]}
    assert cells["China"] == [10, 5, None]
    assert cells["India"] == [None, None, 3]
    assert out["cards"]["lines_change_pct"] == 100


def test_kpi_empty_month():
    out, _ = run_kpi(Filters(month=AUG), rows=[])
    assert out["month"] == "2026-08"
    assert out["cards"]["lines"] == 0 and out["cards"]["lines_change_pct"] is None
    assert out["countries"] == [] and out["approvers"] == []
    assert out["cards"]["bd"]["avg"] == 0


def test_region_filter_drops_other_region_rows():
    rows = [_kr(AUG, "Bangladesh", "S1", "F1", 30), _kr(AUG, "China", "S2", "F2", 70)]
    out, _ = run_kpi(Filters(month=AUG, region="BD"), rows=rows,
                     approvers=[NS(month=AUG, approved_by="Ann", country="China", lines=4),
                                NS(month=AUG, approved_by="Bob", country="Bangladesh", lines=2)])
    assert [c["country"] for c in out["countries"]] == ["Bangladesh"]
    assert out["countries"][0]["share"] == 100
    assert out["cards"]["lines"] == 30 and out["cards"]["suppliers"] == 1
    assert out["cards"]["cn"]["lines"] == 0
    assert [a["name"] for a in out["approvers"]] == ["Bob"]


def test_people_and_region_series_and_approvers():
    rows = [_kr(AUG, "Bangladesh", "S1", "F1", 5), _kr(AUG, "Bangladesh", "S1", "F2", 5),
            _kr(AUG, "China", "S1", "F3", 5), _kr(date(2026, 7, 1), "China", "S1", "F3", 5)]
    out, session = run_kpi(Filters(month=AUG, supplier="s1", approved_by="Ann"), rows=rows,
                           approvers=[NS(month=AUG, approved_by="Ann", country="China", lines=9),
                                      NS(month=date(2026, 7, 1), approved_by="Ann", country="China", lines=6)])
    assert out["people"]["labels"][-2:] == ["Jul '26", "Aug '26"]
    assert out["people"]["bd"]["factories"][-1] == 2 and out["people"]["cn"]["suppliers"][-2:] == [1, 1]
    assert out["cards"]["suppliers"] == 1 and out["cards"]["factories"] == 3  # S1 counted once overall
    assert out["region_lines"]["bd"][-1] == 10 and out["region_lines"]["cn"][-2:] == [5, 5]
    assert out["approvers"] == [{"name": "Ann", "lines": [9, 6], "change_pct": 50}]
    assert all("supplier ILIKE" in sql and "approved_by = " in sql and params["approved_by"] == "Ann"
               for sql, params in session.calls if "MIN(" not in sql)


def test_supplier_and_factory_change_are_absolute():
    jul = date(2026, 7, 1)
    rows = [_kr(AUG, "China", f"S{i}", f"F{i}", 1) for i in range(3)] +            [_kr(jul, "China", f"S{i}", f"F{i}", 1) for i in range(2)]
    out, _ = run_kpi(Filters(month=AUG), rows=rows)
    assert out["cards"]["suppliers_change"] == 1 and out["cards"]["factories_change"] == 1
    # no previous month in the data range: nothing to compare with
    out, _ = run_kpi(Filters(month=AUG), rows=rows, min_date=AUG)
    assert out["cards"]["suppliers_change"] is None and out["cards"]["factories_change"] is None


def test_band_uses_the_unrounded_rate():
    # 69.96% shows as 70.0 but is in the mid band, as `bands` counts it
    out, _ = run(Filters(month=MONTH), months={MONTH: [_sup("S", ["India"], 10000, 69.96)]})
    row = out["suppliers"][0]
    assert row["compliance"] == 70.0 and row["band"] == "mid"
    assert out["bands"]["mid"] == 1 and out["bands"]["high"] == 0


def test_filter_options_lists_the_months_countries_and_approvers():
    class Options:
        def __init__(self):
            self.calls = []

        def execute(self, query, params):
            sql = str(query)
            self.calls.append((sql, params))
            values = ["Vietnam", "China"] if "origin_country" in sql else ["Sam", "Alex"]
            return NS(fetchall=lambda: [NS(value=v) for v in values])

        def close(self):
            pass

    session = Options()
    with patch("tps.metrics.dashboard.get_session", return_value=session):
        out = dashboard.filter_options(MONTH)
    assert out == {"countries": ["China", "Vietnam"], "approvers": ["Alex", "Sam"]}
    assert all(p == {"start": MONTH, "end": date(2026, 7, 1)} for _, p in session.calls)
    assert all("IS NOT NULL" in sql for sql, _ in session.calls)


def test_search_returns_only_names_in_the_month():
    class Search:
        def __init__(self):
            self.calls = []

        def execute(self, query, params):
            sql = str(query)
            self.calls.append((sql, params))
            if "DISTINCT supplier" in sql and "factory" not in sql:
                return NS(fetchall=lambda: [NS(supplier="Acme"), NS(supplier="Zed")])
            return NS(fetchall=lambda: [NS(factory="F1", supplier="Acme"), NS(factory="F1", supplier="Zed"),
                                        NS(factory="F2", supplier="Zed")])

        def close(self):
            pass

    session = Search()
    with patch("tps.metrics.dashboard.get_session", return_value=session):
        out = dashboard.search(MONTH, "e_")
        assert dashboard.search(MONTH, "  ") == {"suppliers": [], "factories": []}
    assert out == {"suppliers": ["Acme", "Zed"],
                   "factories": [{"factory": "F1", "suppliers": ["Acme", "Zed"]},
                                 {"factory": "F2", "suppliers": ["Zed"]}]}
    assert all(p["q"] == "%e\_%" and p["start"] == MONTH and "handover_date >= :start" in s
               for s, p in session.calls)
