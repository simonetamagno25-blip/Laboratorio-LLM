"""Punto d'ingresso: python -m scadenze_api."""

import logging
import os
import sys

from scadenze_api.servizio import crea_server


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    grezza = os.environ.get("SCADENZE_API_PORTA", "").strip() or "8000"
    if not grezza.isdigit():
        print(f"SCADENZE_API_PORTA non valida: {grezza!r}", file=sys.stderr)
        return 2
    server = crea_server("0.0.0.0", int(grezza))
    logging.getLogger(__name__).info("servizio scadenze in ascolto sulla porta %s", grezza)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
