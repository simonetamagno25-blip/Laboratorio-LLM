"""Punto d'ingresso: python -m assistente."""

import logging
import sys

from assistente.cli import Sessione, esegui_ciclo
from assistente.config import ErroreConfigurazione, carica_configurazione
from assistente.grafo import costruisci_grafo, limite_ricorsione
from assistente.modello import crea_modello
from assistente.strumenti import crea_strumenti


def main() -> int:
    try:
        config = carica_configurazione()
    except ErroreConfigurazione as errore:
        print(errore, file=sys.stderr)
        return 2

    logging.basicConfig(
        level=config.log_level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)

    strumenti = crea_strumenti()
    modello = crea_modello(config, strumenti)
    grafo = costruisci_grafo(
        modello, strumenti, config.fuso_predefinito, config.max_passaggi_strumenti
    )
    sessione = Sessione(grafo, limite_ricorsione(config.max_passaggi_strumenti))

    print(f"Assistente del laboratorio (modello: {config.modello}). Scrivi /esci per uscire.")
    esegui_ciclo(sessione, config.base_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
