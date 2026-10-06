from unittest.mock import MagicMock, patch

from tps import db


def _statements(conn):
    return [str(c.args[0]) for c in conn.execute.call_args_list]


def test_clear_raw_data_deletes_rows_but_keeps_tables_and_emails():
    engine = MagicMock()
    conn = engine.connect.return_value.__enter__.return_value
    with patch("tps.db.engine", engine):
        db.clear_raw_data()

    statements = _statements(conn)
    assert any("DELETE FROM raw_data" in s for s in statements)
    assert not any("supplier_emails" in s for s in statements)
    assert not any("DROP TABLE" in s.upper() for s in statements)
    conn.commit.assert_called_once()


def test_set_supplier_emails_replaces_only_the_given_suppliers():
    engine = MagicMock()
    conn = engine.begin.return_value.__enter__.return_value
    with patch("tps.db.engine", engine):
        db.set_supplier_emails({" ACME ": ["a@x.com", "b@x.com"], "gone ltd": []})

    calls = conn.execute.call_args_list
    assert [str(c.args[0]).split()[0] for c in calls] == ["DELETE", "INSERT", "DELETE"]
    assert calls[0].args[1] == {"supplier": "acme"}
    assert calls[1].args[1] == [{"supplier": "acme", "email": "a@x.com"},
                                {"supplier": "acme", "email": "b@x.com"}]
    assert calls[2].args[1] == {"supplier": "gone ltd"}
