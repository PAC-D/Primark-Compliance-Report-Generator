import pytest
from werkzeug.serving import BaseWSGIServer, make_server

from tps import __main__ as entry


def test_second_copy_cannot_share_the_port(monkeypatch):
    """On Windows a forgotten older copy of the app kept answering on port 5000
    with old code, next to the new copy."""
    monkeypatch.setattr(BaseWSGIServer, "allow_reuse_address", True)  # werkzeug's default; restored after
    app = lambda environ, start_response: []
    first = make_server("127.0.0.1", 0, app)
    try:
        entry._exclusive_port()
        with pytest.raises(SystemExit):
            make_server("127.0.0.1", first.server_port, app)
    finally:
        first.server_close()
