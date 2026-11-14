"""Front-end in locale: python -m frontend (file statici + config.js da BACKEND_URL).

In Docker gli stessi file sono serviti da nginx, che inoltra /api al back-end.
"""

import functools
import json
import logging
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CARTELLA = Path(__file__).resolve().parent
# Solo i file dell'interfaccia: niente sorgenti Python né test.
PUBBLICI = {"index.html", "app.js", "api.js", "logica.js", "stile.css", "openapi.json"}


def testo_config(backend_url: str) -> str:
    return f"window.CONFIG = {json.dumps({'backend': backend_url.rstrip('/')})};\n"


class Gestore(SimpleHTTPRequestHandler):
    backend_url = "http://localhost:8200"

    def do_GET(self):
        percorso = self.path.split("?", 1)[0].lstrip("/") or "index.html"
        if percorso == "config.js":
            corpo = testo_config(self.backend_url).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        if percorso not in PUBBLICI:
            self.send_error(404)
            return
        self.path = "/" + percorso
        super().do_GET()

    def log_message(self, formato, *argomenti):
        logging.getLogger("frontend").info(formato, *argomenti)


Gestore.extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript"}


def crea_server(host: str, porta: int, backend_url: str) -> ThreadingHTTPServer:
    gestore = functools.partial(Gestore, directory=str(CARTELLA))
    Gestore.backend_url = backend_url
    return ThreadingHTTPServer((host, porta), gestore)


def main() -> int:
    logging.basicConfig(level="INFO", stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    host = os.environ.get("FRONTEND_HOST", "").strip() or "127.0.0.1"
    porta = int(os.environ.get("FRONTEND_PORTA", "").strip() or "8300")
    backend_url = os.environ.get("BACKEND_URL", "").strip() or "http://localhost:8200"
    server = crea_server(host, porta, backend_url)
    logging.getLogger("frontend").info(
        "front-end su http://%s:%d (back-end %s)", host, porta, backend_url
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
