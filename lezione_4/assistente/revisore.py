"""Revisore: controlla che la risposta dell'agente sia coerente con la domanda dell'utente."""

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from pydantic import BaseModel, Field

from assistente.turni import (
    NOME_REVISORE,
    e_indicazione,
    indice_domanda_corrente,
    righe_precedenti,
)

__all__ = [
    "DecisioneRevisore",
    "e_indicazione",
    "indicazione",
    "prompt_revisore",
    "testo_da_revisionare",
]


class DecisioneRevisore(BaseModel):
    """Giudizio sulla coerenza tra la domanda dell'utente e la risposta proposta."""

    coerente: bool = Field(
        description="true se la risposta risponde a tutte le parti della domanda e resta in tema"
    )
    motivo: str = Field(description="motivo del giudizio, in una frase breve in italiano")


def prompt_revisore() -> str:
    # Nessun riferimento agli strumenti: il revisore giudica solo domanda e risposta.
    return (
        "Sei il revisore dell'assistente del laboratorio. Il tuo unico compito è giudicare se la "
        "risposta proposta è coerente con la domanda dell'utente: non riscriverla e non "
        "rispondere tu alla domanda.\n"
        "La risposta è coerente se risponde a tutte le parti della domanda e resta in tema. "
        "Non è coerente se ignora una parte della domanda o parla d'altro.\n"
        "Non verificare i fatti, gli orari o i numeri: ti interessa solo che ogni parte della "
        "domanda abbia una risposta. Una risposta che spiega un errore o dice che un dato non "
        "è disponibile è coerente, se riguarda quello che è stato chiesto.\n"
        "Le domande brevi di seguito («e a New York?») vanno lette insieme ai turni precedenti.\n"
        "Rispondi con coerente true o false e con il motivo in una frase breve in italiano; "
        "se non è coerente, il motivo dice quale parte manca o che cosa è fuori tema."
    )


def testo_da_revisionare(messaggi: list[AnyMessage], turni: int = 3, massimo: int = 300) -> str:
    """Turni precedenti, domanda corrente e ultima risposta proposta dall'agente."""
    corrente = indice_domanda_corrente(messaggi)
    risposta = next(
        m for m in reversed(messaggi) if isinstance(m, AIMessage) and not m.tool_calls
    )
    precedenti = righe_precedenti(messaggi, turni, massimo)
    testo = (
        f"Domanda dell'utente: {messaggi[corrente].text.strip()}\n\n"
        f"Risposta proposta: {risposta.text.strip()}"
    )
    if not precedenti:
        return testo
    return "Turni precedenti:\n" + "\n".join(precedenti) + "\n\n" + testo


def indicazione(motivo: str) -> HumanMessage:
    """Messaggio con cui il revisore rimanda la risposta all'agente."""
    return HumanMessage(
        "Indicazione del revisore: la risposta precedente non risponde del tutto alla domanda "
        f"({motivo}). Rispondi di nuovo alla domanda dell'utente tenendone conto.",
        name=NOME_REVISORE,
    )
