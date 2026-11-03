"""Punto d'ingresso: python -m scadenze_api."""

import logging
import os
import sys
from collections.abc import Mapping

from scadenze_api.servizio import crea_server


def indirizzo_ascolto(env: Mapping[str, str]) -> tuple[str, int]:
    # In locale si ascolta solo su 127.0.0.1; Docker Compose imposta 0.0.0.0.
    host = env.get("SCADENZE_API_HOST", "").strip() or "127.0.0.1"
    grezza = env.get("SCADENZE_API_PORTA", "").strip() or "8000"
    if not grezza.isascii() or not grezza.isdigit() or not 0 < int(grezza) < 65536:
        raise ValueError(f"SCADENZE_API_PORTA non valida: {grezza!r}")
    return host, int(grezza)


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        host, porta = indirizzo_ascolto(os.environ)
    except ValueError as errore:
        print(errore, file=sys.stderr)
        return 2
    server = crea_server(host, porta)
    logging.getLogger(__name__).info("servizio scadenze in ascolto su %s:%d", host, porta)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
