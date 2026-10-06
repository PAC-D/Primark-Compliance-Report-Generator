"""python -m tps: start the local web app and open it in the browser."""

import logging
import os
import threading
import webbrowser

from werkzeug.serving import BaseWSGIServer

HOST, PORT = "127.0.0.1", 5000  # local only; serve on 0.0.0.0 + add a login for team use


def _exclusive_port() -> None:
    """Werkzeug sets SO_REUSEADDR, which on Windows lets a second copy of the app bind
    the same port, so a forgotten older copy kept answering with old code. Without it a
    second start stops with werkzeug's "Port 5000 is in use"."""
    if os.name == "nt":
        BaseWSGIServer.allow_reuse_address = False


def main() -> None:
    from tps.config import setup_logging
    from tps.db import ensure_indexes
    from tps.web.app import create_app

    setup_logging()
    # One line per HTTP request (the page polls every second) would flood logs/run.log.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    ensure_indexes()

    url = f"http://{HOST}:{PORT}"
    print(f"TPS Compliance Reports: {url}  (Ctrl+C to stop)")
    opener = threading.Timer(1.0, webbrowser.open, [url])
    opener.daemon = True  # a start that fails (port in use) exits without opening the old copy's page
    opener.start()
    _exclusive_port()
    create_app().run(host=HOST, port=PORT)


if __name__ == "__main__":
    main()
