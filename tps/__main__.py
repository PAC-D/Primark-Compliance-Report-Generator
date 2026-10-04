"""python -m tps: start the local web app and open it in the browser."""

import logging
import threading
import webbrowser

from tps.config import setup_logging
from tps.web.app import create_app

HOST, PORT = "127.0.0.1", 5000  # local only; serve on 0.0.0.0 + add a login for team use

setup_logging()
# One line per HTTP request (the page polls every second) would flood logs/run.log.
logging.getLogger("werkzeug").setLevel(logging.WARNING)

url = f"http://{HOST}:{PORT}"
print(f"TPS Compliance Reports: {url}  (Ctrl+C to stop)")
threading.Timer(1.0, webbrowser.open, [url]).start()
create_app().run(host=HOST, port=PORT)
