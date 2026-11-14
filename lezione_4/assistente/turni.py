"""Turni della conversazione letti da router e revisore: domande vere e risposte finali."""

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage

# Nome dei messaggi con cui il revisore rimanda una risposta all'agente.
NOME_REVISORE = "revisore"


def e_indicazione(messaggio: AnyMessage) -> bool:
    """Vero per le indicazioni del revisore, che non sono domande dell'utente."""
    return isinstance(messaggio, HumanMessage) and messaggio.name == NOME_REVISORE


def indice_domanda_corrente(messaggi: list[AnyMessage]) -> int:
    """Posizione dell'ultima domanda vera dell'utente."""
    for i in range(len(messaggi) - 1, -1, -1):
        if isinstance(messaggi[i], HumanMessage) and not e_indicazione(messaggi[i]):
            return i
    raise ValueError("nella cronologia non c'è nessuna domanda dell'utente")


def e_bozza_rifiutata(messaggi: list[AnyMessage], i: int) -> bool:
    return i + 1 < len(messaggi) and e_indicazione(messaggi[i + 1])


def _riga(messaggio: AnyMessage, massimo: int) -> str:
    chi = "Utente" if isinstance(messaggio, HumanMessage) else "Assistente"
    return f"{chi}: {messaggio.text.strip()[:massimo]}"


def righe_precedenti(messaggi: list[AnyMessage], turni: int, massimo: int) -> list[str]:
    """Ultimi `turni` turni prima della domanda corrente, senza strumenti, indicazioni e bozze."""
    corrente = indice_domanda_corrente(messaggi)
    domande = [
        i for i, m in enumerate(messaggi[:corrente])
        if isinstance(m, HumanMessage) and not e_indicazione(m)
    ]
    inizio = domande[-turni] if len(domande) >= turni else (domande[0] if domande else corrente)
    righe = []
    for i in range(inizio, corrente):
        m = messaggi[i]
        if isinstance(m, HumanMessage) and not e_indicazione(m):
            righe.append(_riga(m, massimo))
        elif (
            isinstance(m, AIMessage)
            and not m.tool_calls
            and m.text.strip()
            and not e_bozza_rifiutata(messaggi, i)
        ):
            righe.append(_riga(m, massimo))
    return righe
