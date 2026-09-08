import sys
sys.path.insert(0, "..")

import pytest
from unittest.mock import patch, MagicMock

import database


@pytest.fixture
def mock_conn():
    mock_engine = MagicMock()
    conn = mock_engine.connect.return_value.__enter__.return_value
    with patch("database._engine", mock_engine):
        yield conn


def _statements(conn):
    return [str(c.args[0]) for c in conn.execute.call_args_list]


def test_clear_raw_data_deletes_rows_only(mock_conn):
    database.clear_raw_data()
    stmts = _statements(mock_conn)
    assert any("DELETE FROM raw_data" in s for s in stmts)
    assert not any("DROP TABLE" in s.upper() for s in stmts)
    mock_conn.commit.assert_called_once()


def test_clear_all_tables_deletes_both_tables(mock_conn):
    database.clear_all_tables()
    stmts = _statements(mock_conn)
    assert any("DELETE FROM raw_data" in s for s in stmts)
    assert any("DELETE FROM supplier_emails" in s for s in stmts)
    assert not any("DROP TABLE" in s.upper() for s in stmts)
    mock_conn.commit.assert_called_once()
