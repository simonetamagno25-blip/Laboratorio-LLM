"""Riassunto della cronologia: comprime i turni vecchi in un testo aggiornato nello stato."""

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage

from assistente.turni import e_bozza_rifiutata, e_indicazione


def punto_di_taglio(messaggi: list[AnyMessage], conservati: int) -> int:
    """Indice da cui conservare i messaggi: l'inizio di turno più recente che ne lascia almeno
    `conservati`. Un turno inizia con una domanda vera dell'utente, quindi il taglio non separa
    mai una richiesta di strumento dal suo ToolMessage. 0 vuol dire: niente da comprimere."""
    inizi = [
        i for i, m in enumerate(messaggi)
        if i > 0 and isinstance(m, HumanMessage) and not e_indicazione(m)
    ]
    validi = [i for i in inizi if len(messaggi) - i >= conservati]
    return max(validi, default=0)


def prompt_riassunto() -> str:
    return (
        "Riassumi la conversazione tra l'utente e l'assistente del laboratorio. "
        "Scrivi un unico riassunto in italiano che unisce il riassunto precedente, se c'è, "
        "con i nuovi messaggi: riscrivilo da capo, non aggiungere un secondo riassunto.\n"
        "Conserva sempre nomi, preferenze e fatti dichiarati dall'utente, le richieste fatte e "
        "i risultati importanti (orari, calcoli, note, articoli del catalogo). "
        "Non inventare nulla e non rispondere alle domande. Al massimo 120 parole."
    )


def testo_da_riassumere(riassunto_precedente: str, messaggi: list[AnyMessage]) -> str:
    righe = []
    for i, m in enumerate(messaggi):
        if e_indicazione(m):
            continue
        if isinstance(m, HumanMessage):
            righe.append(f"Utente: {m.text.strip()}")
        elif isinstance(m, ToolMessage):
            righe.append(f"Strumento {m.name}: {m.text.strip()}")
        elif isinstance(m, AIMessage) and m.text.strip() and not e_bozza_rifiutata(messaggi, i):
            righe.append(f"Assistente: {m.text.strip()}")
    testo = "Nuovi messaggi:\n" + "\n".join(righe)
    if riassunto_precedente.strip():
        return f"Riassunto precedente:\n{riassunto_precedente.strip()}\n\n{testo}"
    return testo
