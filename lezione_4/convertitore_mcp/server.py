"""Server MCP che espone il convertitore di unità e le preferenze dell'utente."""

import os
from pathlib import Path
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

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


# Prompt: li richiama l'utente in modo esplicito (/prompt nella CLI), non il modello.
LIVELLI = ("base", "intermedio", "avanzato")
STILI_RIASSUNTO = ("sintetico", "dettagliato")


@server.prompt(description="Spiega un argomento al livello richiesto.")
def spiega(
    argomento: Annotated[str, Field(description="concetto da spiegare")],
    livello: Annotated[str, Field(description="base, intermedio o avanzato")] = "base",
) -> str:
    if livello not in LIVELLI:
        raise ValueError(f"livello non valido: {livello!r} (ammessi: {', '.join(LIVELLI)})")
    return (
        f"Spiegami «{argomento}» a livello {livello}. "
        "Parti da una definizione in una frase, poi spiega a cosa serve e fai un esempio concreto, "
        f"con un linguaggio adatto al livello {livello}."
    )


@server.prompt(description="Riassume i turni della conversazione corrente.")
def riassumi_conversazione(
    stile: Annotated[str, Field(description="sintetico o dettagliato")] = "sintetico",
) -> str:
    if stile not in STILI_RIASSUNTO:
        raise ValueError(f"stile non valido: {stile!r} (ammessi: {', '.join(STILI_RIASSUNTO)})")
    return (
        f"Riassumi in modo {stile} la nostra conversazione fino a questo momento: "
        "le domande che ho fatto e le risposte che mi hai dato, senza aggiungere informazioni nuove."
    )
