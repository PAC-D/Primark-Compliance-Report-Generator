from unittest.mock import MagicMock, patch

from tps import db


def test_clear_all_tables_deletes_rows_but_keeps_tables():
    engine = MagicMock()
    conn = engine.connect.return_value.__enter__.return_value
    with patch("tps.db.engine", engine):
        db.clear_all_tables()

    statements = [str(c.args[0]) for c in conn.execute.call_args_list]
    assert any("DELETE FROM raw_data" in s for s in statements)
    assert any("DELETE FROM supplier_emails" in s for s in statements)
    assert not any("DROP TABLE" in s.upper() for s in statements)
    conn.commit.assert_called_once()
