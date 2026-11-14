"""Punto d'ingresso della CLI: python -m assistente.

La CLI è un client dell'API dell'agente (python -m assistente.servizio), indicato da AGENTE_URL.
"""

import logging
import os
import sys

from assistente.cli import esegui_ciclo
from assistente.client_agente import ErroreAgente, PromptRemoti, SessioneRemota

URL_PREDEFINITO = "http://localhost:8100"


def main() -> int:
    logging.basicConfig(
        level=(os.environ.get("LOG_LEVEL", "").strip() or "INFO").upper(),
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    url = (os.environ.get("AGENTE_URL", "").strip() or URL_PREDEFINITO).rstrip("/")
    sessione = SessioneRemota(url)
    try:
        stato = sessione.stato()
    except ErroreAgente as errore:
        print(f"Attenzione: {errore}. Avviarlo con python -m assistente.servizio.")
    else:
        if stato.get("modello") != "ok" or stato.get("server_mcp") != "ok":
            print(f"Attenzione: stato dell'agente {stato}")
    print(f"Assistente del laboratorio (agente: {url}). Scrivi /esci o /prompts per i comandi.")
    esegui_ciclo(sessione, url, prompt=PromptRemoti(url))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
