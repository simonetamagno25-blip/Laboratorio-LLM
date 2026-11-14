"""Collegamento al modello servito da LM Studio (API compatibile con OpenAI)."""

import openai
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from assistente.config import Configurazione
from assistente.router import DecisioneRouter


def _chat(config: Configurazione) -> ChatOpenAI:
    # Stessi parametri per agente e router: è lo stesso modello con prompt di sistema diversi.
    return ChatOpenAI(
        base_url=config.base_url,
        model=config.modello,
        api_key="lm-studio",
        temperature=0,
        max_retries=0,
        timeout=120,
    )


def crea_modello(config: Configurazione, strumenti: list[BaseTool]) -> Runnable:
    return _chat(config).bind_tools(strumenti)


def crea_router(config: Configurazione) -> Runnable:
    """Router con output strutturato: LM Studio impone lo schema JSON durante la generazione.

    Con include_raw=True un output non valido non solleva eccezioni: restituisce
    {"raw": ..., "parsed": None, "parsing_error": ...} e il grafo decide cosa fare.
    """
    return _chat(config).with_structured_output(
        DecisioneRouter, method="json_schema", include_raw=True
    )


def descrivi_errore(exc: Exception, base_url: str) -> str:
    if isinstance(exc, openai.APIConnectionError):
        return f"LM Studio non raggiungibile su {base_url}. È avviato con il server attivo?"
    if isinstance(exc, openai.APIStatusError):
        return f"LM Studio ha risposto con un errore ({exc.status_code}): {exc.message}"
    return f"Errore durante la risposta: {exc}"
