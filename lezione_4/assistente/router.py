"""Router: decide se la domanda rientra nell'ambito dell'agente, prima dell'agente."""

from typing import Literal

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from pydantic import BaseModel, Field


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
        "domande che proseguono i turni precedenti della conversazione, anche se brevi "
        "(per esempio «e a Tokyo?»)."
    )


def _riga(messaggio: AnyMessage, massimo: int) -> str:
    chi = "Utente" if isinstance(messaggio, HumanMessage) else "Assistente"
    return f"{chi}: {messaggio.text.strip()[:massimo]}"


def testo_da_classificare(messaggi: list[AnyMessage], turni: int = 3, massimo: int = 300) -> str:
    """Domanda corrente (ultimo HumanMessage) preceduta dagli ultimi turni, senza strumenti."""
    indici = [i for i, m in enumerate(messaggi) if isinstance(m, HumanMessage)]
    corrente = indici[-1]
    # Un turno inizia con una domanda dell'utente: si parte dall'inizio dei turni da tenere.
    inizio = indici[max(0, len(indici) - 1 - turni)] if len(indici) > 1 else corrente
    precedenti = [
        _riga(m, massimo)
        for m in messaggi[inizio:corrente]
        if isinstance(m, HumanMessage)
        or (isinstance(m, AIMessage) and not m.tool_calls and m.text.strip())
    ]
    domanda = f"Domanda da classificare: {messaggi[corrente].text.strip()}"
    if not precedenti:
        return domanda
    return "Turni precedenti:\n" + "\n".join(precedenti) + "\n\n" + domanda


def messaggio_rifiuto(ambito: str) -> str:
    return f"Mi dispiace, questa richiesta è fuori dal mio ambito. Posso aiutarti con: {ambito}."
