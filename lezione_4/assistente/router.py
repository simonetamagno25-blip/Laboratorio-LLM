"""Router: decide se la domanda rientra nell'ambito dell'agente, prima dell'agente."""

from typing import Literal

from langchain_core.messages import AnyMessage
from pydantic import BaseModel, Field

from assistente.turni import indice_domanda_corrente, righe_precedenti


class DecisioneRouter(BaseModel):
    """Classificazione della domanda dell'utente rispetto all'ambito dell'agente."""

    categoria: Literal["conversazione", "fuori_ambito"] = Field(
        description="conversazione se la domanda rientra nell'ambito, altrimenti fuori_ambito"
    )
    motivo: str = Field(description="motivo della scelta, in una frase breve in italiano")


def prompt_router(ambito: str) -> str:
    # Nessun riferimento agli strumenti: se servono lo decide l'agente, non il router.
    return (
        "Sei il router dell'assistente del laboratorio. Il tuo unico compito è classificare "
        "la domanda dell'utente: non rispondere alla domanda.\n"
        f"Ambito dell'assistente: {ambito}.\n"
        "Rispondi con categoria «conversazione» se la domanda rientra nell'ambito, "
        "con «fuori_ambito» se non vi rientra, e con il motivo in una frase breve in italiano.\n"
        "Sono sempre «conversazione»: saluti, ringraziamenti, domande sull'assistente e "
        "domande brevi che proseguono un argomento in ambito dei turni precedenti "
        "(per esempio «e a Tokyo?» dopo una domanda sull'ora).\n"
        "Il seguito di una domanda fuori ambito resta «fuori_ambito» (per esempio "
        "«e quella dell'amatriciana?» dopo una richiesta di ricetta)."
    )


def testo_da_classificare(messaggi: list[AnyMessage], turni: int = 3, massimo: int = 300) -> str:
    """Domanda corrente (ultima domanda vera) preceduta dagli ultimi turni, senza strumenti."""
    precedenti = righe_precedenti(messaggi, turni, massimo)
    corrente = messaggi[indice_domanda_corrente(messaggi)]
    domanda = f"Domanda da classificare: {corrente.text.strip()}"
    if not precedenti:
        return domanda
    return "Turni precedenti:\n" + "\n".join(precedenti) + "\n\n" + domanda


def messaggio_rifiuto(ambito: str) -> str:
    return f"Mi dispiace, questa richiesta è fuori dal mio ambito. Posso aiutarti con: {ambito}."
