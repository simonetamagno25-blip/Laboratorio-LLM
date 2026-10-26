"""Collegamento al modello servito da LM Studio (API compatibile con OpenAI)."""

import openai
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from assistente.config import Configurazione


def crea_modello(config: Configurazione, strumenti: list[BaseTool]) -> Runnable:
    return ChatOpenAI(
        base_url=config.base_url,
        model=config.modello,
        api_key="lm-studio",
        temperature=0,
        max_retries=0,
        timeout=120,
    ).bind_tools(strumenti)


def descrivi_errore(exc: Exception, base_url: str) -> str:
    if isinstance(exc, openai.APIConnectionError):
        return f"LM Studio non raggiungibile su {base_url}. È avviato con il server attivo?"
    if isinstance(exc, openai.APIStatusError):
        return f"LM Studio ha risposto con un errore ({exc.status_code}): {exc.message}"
    return f"Errore durante la risposta: {exc}"
