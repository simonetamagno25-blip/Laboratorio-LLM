"""Collegamento al modello servito da LM Studio (API compatibile con OpenAI)."""

import openai
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

from assistente.config import Configurazione
from assistente.revisore import DecisioneRevisore
from assistente.router import DecisioneRouter


def _chat(config: Configurazione) -> ChatOpenAI:
    # Stessi parametri per agente, router e revisore: è lo stesso modello con prompt di sistema diversi.
    return ChatOpenAI(
        base_url=config.base_url,
        model=config.modello,
        api_key="lm-studio",
        temperature=0,
        max_retries=0,
        # Una risposta lunga (es. /prompt spiega) con il ragionamento del modello locale supera 120 s.
        timeout=300,
    )


def crea_modello(config: Configurazione, strumenti: list[BaseTool]) -> Runnable:
    return _chat(config).bind_tools(strumenti)


# Guasti di formato delle risposte strutturate (router e revisore). Con json_schema la libreria
# fa validare lo schema all'SDK openai, che solleva queste eccezioni invece di dare parsed=None.
ERRORI_FORMATO = (
    ValidationError,
    openai.LengthFinishReasonError,
    openai.ContentFilterFinishReasonError,
)


def _strutturato(config: Configurazione, schema: type[BaseModel]) -> Runnable:
    """Stesso modello con output strutturato: LM Studio impone lo schema JSON durante la generazione.

    Un output non valido non solleva eccezioni: restituisce
    {"raw": ..., "parsed": None, "parsing_error": ...} e il grafo decide cosa fare.
    Gli errori di connessione e di stato del server invece si propagano.
    """
    strutturato = _chat(config).with_structured_output(
        schema, method="json_schema", include_raw=True
    )

    def classifica(messaggi, config: RunnableConfig) -> dict:
        try:
            return strutturato.invoke(messaggi, config)
        except ERRORI_FORMATO as exc:
            return {"raw": None, "parsed": None, "parsing_error": exc}

    return RunnableLambda(classifica)


def crea_riassuntore(config: Configurazione) -> Runnable:
    # Il riassunto è testo libero: stesso modello, senza strumenti né schema.
    return _chat(config)


def crea_router(config: Configurazione) -> Runnable:
    return _strutturato(config, DecisioneRouter)


def crea_revisore(config: Configurazione) -> Runnable:
    return _strutturato(config, DecisioneRevisore)


def descrivi_errore(exc: Exception, base_url: str) -> str:
    # APITimeoutError è una sottoclasse di APIConnectionError: va controllata prima.
    if isinstance(exc, openai.APITimeoutError):
        return (
            f"LM Studio non ha risposto in tempo su {base_url} (modello occupato o risposta "
            "troppo lunga). Riprova tra poco."
        )
    if isinstance(exc, openai.APIConnectionError):
        return f"LM Studio non raggiungibile su {base_url}. È avviato con il server attivo?"
    if isinstance(exc, openai.APIStatusError):
        return f"LM Studio ha risposto con un errore ({exc.status_code}): {exc.message}"
    return f"Errore durante la risposta: {exc}"
