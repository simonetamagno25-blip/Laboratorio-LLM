"""Punto d'ingresso: python -m backend."""

import logging
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigurazioneBackend:
    database_url: str
    agente_url: str
    host: str
    porta: int
    origini: list[str]
    attesa_database: float


def carica(env: Mapping[str, str]) -> ConfigurazioneBackend:
    database_url = env.get("DATABASE_URL", "").strip()
    if not database_url:
        raise ValueError("Variabile d'ambiente obbligatoria mancante o vuota: DATABASE_URL")
    grezza = env.get("BACKEND_PORTA", "").strip() or "8200"
    if not grezza.isdigit() or not 0 < int(grezza) < 65536:
        raise ValueError(f"BACKEND_PORTA non valida: {grezza!r}")
    attesa = env.get("ATTESA_DATABASE", "").strip() or "30"
    try:
        attesa_database = float(attesa)
    except ValueError:
        raise ValueError(f"ATTESA_DATABASE non valida: {attesa!r}") from None
    origini = env.get("ORIGINI_CONSENTITE", "").strip() or "http://localhost:8300"
    return ConfigurazioneBackend(
        database_url=database_url,
        agente_url=(env.get("AGENTE_URL", "").strip() or "http://localhost:8100").rstrip("/"),
        host=env.get("BACKEND_HOST", "").strip() or "127.0.0.1",
        porta=int(grezza),
        origini=[o.strip() for o in origini.split(",") if o.strip()],
        attesa_database=attesa_database,
    )


def servi(app, host: str, porta: int) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=porta, log_level="warning")


def main() -> int:
    from backend.agente import ClientAgente
    from backend.app import crea_app
    from backend.archivio import ArchivioPostgres, ErroreDatabase

    logging.basicConfig(
        level=(os.environ.get("LOG_LEVEL", "").strip() or "INFO").upper(),
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        config = carica(os.environ)
    except ValueError as errore:
        print(errore, file=sys.stderr)
        return 2
    archivio = ArchivioPostgres(config.database_url)
    try:
        archivio.prepara(config.attesa_database)
    except ErroreDatabase as errore:
        print(f"Database non disponibile: {errore}", file=sys.stderr)
        return 3
    app = crea_app(archivio, ClientAgente(config.agente_url), config.origini)
    logging.getLogger(__name__).info(
        "back-end in ascolto su %s:%d (agente %s, documentazione su /api/docs)",
        config.host, config.porta, config.agente_url,
    )
    try:
        servi(app, config.host, config.porta)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
