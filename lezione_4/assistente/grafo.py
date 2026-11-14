"""Grafo LangGraph: stato, nodi e instradamento della conversazione."""

import logging
from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from assistente.note import ArchivioNote
from assistente.revisore import e_indicazione, indicazione, prompt_revisore, testo_da_revisionare
from assistente.router import messaggio_rifiuto, prompt_router, testo_da_classificare

log = logging.getLogger(__name__)

ELIMINA = "elimina_nota"

MESSAGGIO_LIMITE = (
    "Ho raggiunto il limite di passaggi con gli strumenti "
    "e non posso completare la risposta a questa domanda."
)


class StatoConversazione(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    passaggi_strumenti: int
    # Chiamata elimina_nota confermata dall'utente in questo passaggio: {"id": ..., "numero": ...}.
    eliminazioni_confermate: NotRequired[list[dict]]
    # Decisione del router per la domanda corrente: "conversazione" o "fuori_ambito".
    categoria: NotRequired[str]
    motivo: NotRequired[str]
    # Risposte rimandate all'agente dal revisore nel turno corrente.
    revisioni: NotRequired[int]


def prompt_di_sistema(fuso_predefinito: str) -> str:
    return (
        "Sei l'assistente del laboratorio. "
        "Per qualsiasi domanda su data e ora usa sempre lo strumento ora_corrente "
        "e non inventare mai l'ora. "
        f"Se l'utente non indica un luogo, usa il fuso orario {fuso_predefinito}. "
        "Per i calcoli usa sempre lo strumento calcola e non calcolare a mente. "
        "Per le conversioni tra unità di misura usa sempre converti_unita, anche se le "
        "unità ti sembrano incompatibili: è lo strumento a verificarlo, quindi non "
        "rifiutare mai una conversione senza averlo chiamato. "
        "Per contare i giorni tra due date usa giorni_tra_date e per le scadenze "
        "calcola_scadenza, con le date nel formato AAAA-MM-GG. "
        "Il laboratorio ha un catalogo del suo materiale (schede, sensori, attuatori, cavi, "
        "alimentazione, strumenti di misura). Quando l'utente chiede se c'è un oggetto, "
        "quanti ce ne sono o dove si trova, usa sempre cerca_articoli prima di rispondere, "
        "anche se pensi che non ci sia; per la scheda completa di un codice usa "
        "dettaglio_articolo. Non citare articoli, quantità o posizioni che gli strumenti "
        "non hanno restituito. "
        "L'utente può salvare note personali. Le richieste «annota», «prendi nota», «segna», "
        "«segnati» e «ricordami» sono sempre richieste di salvare una nota: chiama sempre "
        "aggiungi_nota e non dire mai di aver salvato una nota senza averlo chiamato. Per ritrovarle usa cerca_note con una parola chiave, o elenca_note "
        "per vederle tutte. Per cancellarne una trova il numero con cerca_note e poi chiama "
        "subito elimina_nota con quel numero; non chiedere tu la conferma all'utente, perché "
        "la chiede il programma. Solo se più note corrispondono elencale e chiedi quale "
        "eliminare. Non citare note che gli strumenti non hanno restituito. "
        "Se uno strumento risponde con un errore, spiega all'utente il motivo "
        "senza inventare un risultato. "
        "Rispondi sempre in italiano."
    )


def instrada_dopo_modello(
    stato: StatoConversazione, max_passaggi: int
) -> Literal["strumenti", "conferma_eliminazione", "limite_raggiunto", "__end__"]:
    ultimo = stato["messages"][-1]
    if not (ultimo.tool_calls or ultimo.invalid_tool_calls):
        return "__end__"
    if stato["passaggi_strumenti"] >= max_passaggi:
        return "limite_raggiunto"
    if any(c["name"] == ELIMINA for c in ultimo.tool_calls):
        return "conferma_eliminazione"
    return "strumenti"


def instrada_dopo_router(stato: StatoConversazione) -> Literal["agente", "rifiuto"]:
    return "rifiuto" if stato.get("categoria") == "fuori_ambito" else "agente"


def instrada_dopo_revisore(stato: StatoConversazione) -> Literal["agente", "__end__"]:
    # Il revisore aggiunge un'indicazione solo quando rimanda la risposta all'agente.
    return "agente" if e_indicazione(stato["messages"][-1]) else "__end__"


def limite_ricorsione(max_passaggi: int, max_revisioni: int = 0) -> int:
    # Ogni giro con gli strumenti conta fino a tre passi: agente, conferma, strumenti.
    # Ogni risposta finale conta due passi: agente e revisore (al massimo max_revisioni + 1).
    # +6: router, rifiuto, e i passi iniziali/finali.
    return 3 * max_passaggi + 2 * (max_revisioni + 1) + 6


def numero_nota(args: dict) -> int | None:
    """Numero di nota valido dagli argomenti della chiamata, oppure None."""
    valore = args.get("numero")
    if isinstance(valore, str) and valore.strip().isdecimal():
        valore = int(valore.strip())
    if isinstance(valore, bool) or not isinstance(valore, int) or valore <= 0:
        return None
    return valore


def costruisci_grafo(
    modello: Runnable,
    strumenti: list[BaseTool],
    fuso_predefinito: str,
    max_passaggi: int,
    archivio: ArchivioNote | None = None,
    *,
    router: Runnable | None = None,
    ambito: str = "",
    revisore: Runnable | None = None,
    max_revisioni: int = 2,
) -> CompiledStateGraph:
    per_nome = {s.name: s for s in strumenti}
    if router is not None and not ambito.strip():
        raise ValueError("il router richiede l'ambito dell'agente")
    if ELIMINA in per_nome and archivio is None:
        raise ValueError("elimina_nota richiede l'archivio delle note per la conferma")

    def prima_eliminazione(messaggio: AIMessage) -> dict | None:
        return next((c for c in messaggio.tool_calls if c["name"] == ELIMINA), None)

    def nodo_conferma_eliminazione(stato: StatoConversazione) -> dict:
        chiamata = prima_eliminazione(stato["messages"][-1])
        numero = numero_nota(chiamata["args"]) if chiamata and archivio else None
        nota = archivio.leggi(numero) if numero is not None else None
        if nota is None:
            return {"eliminazioni_confermate": []}
        # Il grafo si ferma qui; il terminale mostra la nota salvata e riprende con sì/no.
        si = interrupt(
            {"numero": nota.numero, "creata": f"{nota.creata:%Y-%m-%d %H:%M}", "testo": nota.testo}
        )
        decisione = "confermata" if si is True else "annullata"
        log.info("eliminazione della nota %d %s", nota.numero, decisione)
        confermata = {"id": chiamata["id"], "numero": nota.numero}
        return {"eliminazioni_confermate": [confermata] if si is True else []}

    def esito_eliminazione(stato: StatoConversazione, chiamata: dict, prima: bool) -> str | None:
        """Risposta per una elimina_nota da non eseguire; None se va eseguita."""
        # La prima si riconosce per posizione, non per id: gli id possono ripetersi.
        if not prima:
            return "Errore: elimina una nota alla volta."
        numero = numero_nota(chiamata["args"])
        if numero is None:
            return f"Errore: numero di nota non valido: {chiamata['args'].get('numero')!r}"
        confermate = stato.get("eliminazioni_confermate", [])
        if {"id": chiamata["id"], "numero": numero} in confermate:
            return None
        if archivio.leggi(numero) is not None:
            return f"Eliminazione annullata dall'utente: la nota {numero} non è stata eliminata."
        return None  # nota inesistente: lo strumento risponde «non trovata» senza eliminare

    def nodo_router(stato: StatoConversazione) -> dict:
        esito = router.invoke(
            [
                SystemMessage(prompt_router(ambito)),
                HumanMessage(testo_da_classificare(stato["messages"])),
            ]
        )
        decisione = esito.get("parsed")
        if decisione is None:
            # Fail-open: un output non valido non deve bloccare una domanda legittima.
            log.warning(
                "router: output non valido (%s), la domanda passa all'agente",
                esito.get("parsing_error"),
            )
            categoria, motivo = "conversazione", "output del router non valido"
        else:
            categoria, motivo = decisione.categoria, decisione.motivo
        destinazione = instrada_dopo_router({"categoria": categoria})
        log.info("router: categoria=%s motivo=%s -> %s", categoria, motivo, destinazione)
        return {"categoria": categoria, "motivo": motivo}

    def nodo_rifiuto(stato: StatoConversazione) -> dict:
        log.info("rifiuto: domanda fuori ambito, agente non eseguito")
        return {"messages": [AIMessage(messaggio_rifiuto(ambito))]}

    def nodo_revisore(stato: StatoConversazione) -> dict:
        esito = revisore.invoke(
            [
                SystemMessage(prompt_revisore()),
                HumanMessage(testo_da_revisionare(stato["messages"])),
            ]
        )
        giudizio = esito.get("parsed")
        if giudizio is None:
            # Fail-open: un guasto di formato del revisore non deve bloccare la risposta.
            log.warning(
                "revisore: output non valido (%s), la risposta è approvata",
                esito.get("parsing_error"),
            )
            return {}
        if giudizio.coerente:
            log.info("revisore: coerente=sì motivo=%s -> fine", giudizio.motivo)
            return {}
        fatte = stato.get("revisioni", 0)
        if fatte >= max_revisioni:
            log.info("revisore: coerente=no motivo=%s -> fine", giudizio.motivo)
            log.warning(
                "revisore: limite di %d revisioni raggiunto, si restituisce l'ultima risposta",
                max_revisioni,
            )
            return {}
        log.info(
            "revisore: coerente=no motivo=%s -> agente (revisione %d di %d)",
            giudizio.motivo,
            fatte + 1,
            max_revisioni,
        )
        return {"messages": [indicazione(giudizio.motivo)], "revisioni": fatte + 1}

    def nodo_agente(stato: StatoConversazione) -> dict:
        log.info("agente: chiamata al modello")
        messaggi = [SystemMessage(prompt_di_sistema(fuso_predefinito))] + stato["messages"]
        return {"messages": [modello.invoke(messaggi)]}

    def nodo_strumenti(stato: StatoConversazione) -> dict:
        risultati = []
        # Chiamate con argomenti non JSON: vanno comunque risposte, altrimenti
        # restano senza ToolMessage nella cronologia.
        for non_valida in stato["messages"][-1].invalid_tool_calls:
            log.warning(
                "chiamata strumento %s con argomenti non validi: %s",
                non_valida["name"],
                non_valida["args"],
            )
            risultati.append(
                ToolMessage(
                    content=f"Errore: argomenti non validi: {non_valida['args']}",
                    tool_call_id=non_valida["id"],
                    name=non_valida["name"],
                )
            )
        prima = prima_eliminazione(stato["messages"][-1])
        for chiamata in stato["messages"][-1].tool_calls:
            nome, args = chiamata["name"], chiamata["args"]
            log.info("chiamata strumento %s con argomenti %s", nome, args)
            strumento = per_nome.get(nome)
            bloccata = None
            if nome == ELIMINA and strumento is not None:
                bloccata = esito_eliminazione(stato, chiamata, chiamata is prima)
                # Allo strumento arriva il numero già controllato, non l'argomento grezzo.
                args = {"numero": numero_nota(args)}
            if strumento is None:
                esito = f"Errore: strumento sconosciuto '{nome}'"
            elif bloccata is not None:
                esito = bloccata
            else:
                try:
                    esito = str(strumento.invoke(args))
                except Exception as errore:
                    esito = f"Errore: {errore}"
            log.info("risultato strumento %s: %s", nome, esito)
            risultati.append(ToolMessage(content=esito, tool_call_id=chiamata["id"], name=nome))
        return {"messages": risultati, "passaggi_strumenti": stato["passaggi_strumenti"] + 1}

    def nodo_limite_raggiunto(stato: StatoConversazione) -> dict:
        log.warning("limite di %d passaggi con gli strumenti raggiunto", max_passaggi)
        # Si toglie la richiesta di strumento senza risposta, per non lasciare
        # nella cronologia una chiamata priva del ToolMessage corrispondente.
        return {
            "messages": [
                RemoveMessage(id=stato["messages"][-1].id),
                AIMessage(MESSAGGIO_LIMITE),
            ]
        }

    def instrada(stato: StatoConversazione) -> str:
        return instrada_dopo_modello(stato, max_passaggi)

    grafo = StateGraph(StatoConversazione)
    grafo.add_node("agente", nodo_agente)
    grafo.add_node("strumenti", nodo_strumenti)
    grafo.add_node("conferma_eliminazione", nodo_conferma_eliminazione)
    grafo.add_node("limite_raggiunto", nodo_limite_raggiunto)
    if router is not None:
        grafo.add_node("router", nodo_router)
        grafo.add_node("rifiuto", nodo_rifiuto)
        grafo.add_edge(START, "router")
        grafo.add_conditional_edges(
            "router", instrada_dopo_router, {"agente": "agente", "rifiuto": "rifiuto"}
        )
        grafo.add_edge("rifiuto", END)
    else:
        grafo.add_edge(START, "agente")
    grafo.add_conditional_edges(
        "agente",
        instrada,
        {
            "strumenti": "strumenti",
            "conferma_eliminazione": "conferma_eliminazione",
            "limite_raggiunto": "limite_raggiunto",
            # Con il revisore la risposta finale passa da lui prima della fine del turno.
            "__end__": "revisore" if revisore is not None else END,
        },
    )
    if revisore is not None:
        grafo.add_node("revisore", nodo_revisore)
        grafo.add_conditional_edges(
            "revisore", instrada_dopo_revisore, {"agente": "agente", "__end__": END}
        )
    grafo.add_edge("conferma_eliminazione", "strumenti")
    grafo.add_edge("strumenti", "agente")
    grafo.add_edge("limite_raggiunto", END)
    # Il checkpointer (in memoria) serve solo alla pausa per la conferma.
    return grafo.compile(checkpointer=InMemorySaver() if archivio is not None else None)
