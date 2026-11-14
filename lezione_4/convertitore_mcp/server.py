"""Server MCP che espone il convertitore di unità e le preferenze dell'utente."""

import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from convertitore_mcp.unita import Unita, descrivi_conversione

CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent

server = MCPServer("convertitore")


@server.tool()
def converti_unita(valore: float, da: Unita, a: Unita) -> str:
    """Converte un valore tra due unità della stessa grandezza (lunghezza, massa,
    temperatura, volume, tempo). Usare solo i simboli ammessi dallo schema."""
    return descrivi_conversione(valore, da, a)


def percorso_preferenze() -> Path:
    percorso = Path(os.environ.get("PERCORSO_PREFERENZE", "").strip() or "preferenze.json")
    return percorso if percorso.is_absolute() else CARTELLA_PROGETTO / percorso


# Resource: la legge l'host (l'assistente) a inizio sessione, non il modello.
# Il file viene riletto a ogni richiesta, così le modifiche valgono dalla sessione successiva.
@server.resource(
    "utente://preferenze",
    name="preferenze",
    mime_type="application/json",
    description="Preferenze dell'utente per le risposte: lingua, fuso orario predefinito, stile.",
)
def preferenze() -> str:
    """Preferenze dell'utente per le risposte."""
    return percorso_preferenze().read_text(encoding="utf-8")
