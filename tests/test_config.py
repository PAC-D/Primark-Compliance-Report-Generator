import importlib

import pytest

from tps import config


def test_env_database_url(monkeypatch):
    for k, v in dict(DB_HOST="h", DB_NAME="n", DB_USER="u", DB_PASSWORD="p@ss:/w", DB_SSLMODE="require").items():
        monkeypatch.setenv(k, v)
    url = config.database_url()
    assert "p%40ss%3A%2Fw" in url.render_as_string(hide_password=False)
    assert url.query == {"sslmode": "require"}


def test_no_host_and_no_yaml_raises(monkeypatch):
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.setattr(config, "CONFIG", {})
    with pytest.raises(RuntimeError, match="Set DB_HOST or create config.yaml"):
        config.database_url()


def test_pdf_workers_default_is_2(monkeypatch):
    monkeypatch.delenv("PDF_WORKERS", raising=False)
    try:
        assert importlib.reload(config).PDF_WORKERS == 2
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_env_host_without_name_or_user_raises(monkeypatch):
    monkeypatch.setenv("DB_HOST", "h")
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.delenv("DB_NAME", raising=False)
    with pytest.raises(RuntimeError, match="DB_NAME is missing"):
        config.database_url()


def test_blank_pdf_workers_falls_back_to_2(monkeypatch):
    monkeypatch.setenv("PDF_WORKERS", "")
    try:
        assert importlib.reload(config).PDF_WORKERS == 2
    finally:
        monkeypatch.undo()
        importlib.reload(config)


@pytest.mark.parametrize("value", ["abc", "0", "-3", "2.5"])
def test_garbage_pdf_workers_falls_back_to_2(monkeypatch, value):
    monkeypatch.setenv("PDF_WORKERS", value)
    try:
        assert importlib.reload(config).PDF_WORKERS == 2
    finally:
        monkeypatch.undo()
        importlib.reload(config)


@pytest.mark.parametrize("value,expected", [("", 5432), ("x", 5432), ("6543", 6543)])
def test_db_port_tolerant(monkeypatch, value, expected):
    for k, v in dict(DB_HOST="h", DB_NAME="n", DB_USER="u", DB_PORT=value).items():
        monkeypatch.setenv(k, v)
    assert config.database_url().port == expected
