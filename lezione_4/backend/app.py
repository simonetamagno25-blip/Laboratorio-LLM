"""API del back-end per il front-end: chat salvate in PostgreSQL, domande inoltrate all'agente.

Il front-end conosce solo queste rotte (/api/...); l'agente resta dietro al back-end.
"""

import logging
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from backend.agente import AgenteNonRaggiungibile, ClientAgente, ErroreDellAgente
from backend.archivio import ErroreDatabase, StatoAgente

log = logging.getLogger(__name__)


class ChatCreata(BaseModel):
    id: int
    titolo: str


class VoceElenco(BaseModel):
    id: int
    titolo: str
    ultimo_messaggio: datetime | None = Field(description="data dell'ultimo messaggio, se c'è")


class MessaggioJSON(BaseModel):
    ruolo: Literal["utente", "assistente"]
    testo: str
    strumenti: list[dict]
    creato: datetime


class ChatCompleta(BaseModel):
    id: int
    titolo: str
    messaggi: list[MessaggioJSON] = Field(description="in ordine cronologico")
    conferma_in_attesa: bool


class NuovoMessaggio(BaseModel):
    testo: str

    @field_validator("testo")
    @classmethod
    def non_vuoto(cls, valore: str) -> str:
        if not valore.strip():
            raise ValueError("il messaggio è vuoto")
        return valore.strip()


class Conferma(BaseModel):
    conferma: bool


class RispostaChat(BaseModel):
    tipo: Literal["risposta", "conferma"]
    risposta: str | None = None
    strumenti: list[dict] = Field(default_factory=list)
    domanda: str | None = Field(None, description="domanda di conferma (solo con tipo=conferma)")


class Stato(BaseModel):
    backend: str
    database: str
    agente: str


def crea_app(archivio, agente: ClientAgente, origini: list[str] | None = None) -> FastAPI:
    app = FastAPI(
        title="Back-end dell'assistente del laboratorio",
        description="Chat salvate in PostgreSQL; le domande vanno all'agente. "
        "È l'unico servizio che il front-end chiama.",
        version="1.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    if origini:
        app.add_middleware(
            CORSMiddleware, allow_origins=origini, allow_methods=["*"], allow_headers=["*"]
        )

    def stato_della_chat(id_chat: int) -> StatoAgente:
        stato = _db(lambda: archivio.stato_agente(id_chat))
        if stato is None:
            raise HTTPException(404, f"chat {id_chat} inesistente")
        return stato

    def chiama_agente(funzione):
        try:
            return funzione()
        except AgenteNonRaggiungibile as errore:
            raise HTTPException(
                503,
                f"Agente non raggiungibile su {errore.args[0]}: la domanda non è stata salvata, "
                "riprova quando l'agente è attivo.",
            ) from errore
        except ErroreDellAgente as errore:
            raise HTTPException(
                502, f"{errore} (la domanda non è stata salvata, riprova)"
            ) from errore

    def registra(id_chat: int, domanda: str | None, esito: dict, stato: StatoAgente) -> RispostaChat:
        if esito["tipo"] == "conferma":
            # La domanda resta salvata; la risposta arriverà dopo la conferma.
            nuovo = StatoAgente(stato.cronologia, stato.riassunto, esito["id_conferma"])
            _db(lambda: archivio.salva_scambio(
                id_chat, domanda=domanda, risposta=None, strumenti=[], stato=nuovo
            ))
            return RispostaChat(tipo="conferma", domanda=esito["domanda"])
        nuovo = StatoAgente(esito["cronologia"], esito["riassunto"], None)
        _db(lambda: archivio.salva_scambio(
            id_chat, domanda=domanda, risposta=esito["risposta"],
            strumenti=esito["strumenti"], stato=nuovo,
        ))
        log.info(
            "chat %d: risposta salvata, strumenti %s",
            id_chat, [s["nome"] for s in esito["strumenti"]],
        )
        return RispostaChat(tipo="risposta", risposta=esito["risposta"], strumenti=esito["strumenti"])

    @app.post(
        "/api/chat", status_code=201, response_model=ChatCreata, summary="Crea una chat",
        operation_id="creaChat",
    )
    def crea():
        chat = _db(archivio.crea)
        log.info("chat %d creata", chat.id)
        return ChatCreata(id=chat.id, titolo=chat.titolo)

    @app.get(
        "/api/chat", response_model=list[VoceElenco], summary="Elenca le chat",
        operation_id="elencaChat",
    )
    def elenca():
        return [
            VoceElenco(id=c.id, titolo=c.titolo, ultimo_messaggio=c.ultimo_messaggio)
            for c in _db(archivio.elenca)
        ]

    @app.get(
        "/api/chat/{id_chat}", response_model=ChatCompleta, summary="Legge una chat",
        operation_id="leggiChat",
    )
    def leggi(id_chat: int):
        trovata = _db(lambda: archivio.leggi(id_chat))
        if trovata is None:
            raise HTTPException(404, f"chat {id_chat} inesistente")
        chat, messaggi = trovata
        stato = _db(lambda: archivio.stato_agente(id_chat))
        return ChatCompleta(
            id=chat.id,
            titolo=chat.titolo,
            messaggi=[MessaggioJSON(**vars(m)) for m in messaggi],
            conferma_in_attesa=bool(stato and stato.id_conferma),
        )

    @app.post(
        "/api/chat/{id_chat}/messaggi",
        response_model=RispostaChat,
        summary="Invia un messaggio: chiama l'agente, salva domanda e risposta",
        operation_id="inviaMessaggio",
    )
    def invia(id_chat: int, messaggio: NuovoMessaggio):
        stato = stato_della_chat(id_chat)
        if stato.id_conferma:
            raise HTTPException(409, "c'è una conferma in attesa: rispondi prima sì o no")
        log.info("chat %d: domanda inoltrata all'agente", id_chat)
        esito = chiama_agente(
            lambda: agente.invia(messaggio.testo, stato.cronologia, stato.riassunto)
        )
        return registra(id_chat, messaggio.testo, esito, stato)

    @app.post(
        "/api/chat/{id_chat}/conferma",
        response_model=RispostaChat,
        summary="Risponde sì o no alla conferma chiesta dall'agente",
        operation_id="rispondiConferma",
    )
    def conferma(id_chat: int, risposta: Conferma):
        stato = stato_della_chat(id_chat)
        if not stato.id_conferma:
            raise HTTPException(409, "nessuna conferma in attesa per questa chat")
        esito = chiama_agente(lambda: agente.conferma(stato.id_conferma, risposta.conferma))
        return registra(id_chat, None, esito, stato)

    @app.delete(
        "/api/chat/{id_chat}", status_code=204, summary="Elimina la chat e i suoi messaggi",
        operation_id="eliminaChat",
    )
    def elimina(id_chat: int):
        if not _db(lambda: archivio.elimina(id_chat)):
            raise HTTPException(404, f"chat {id_chat} inesistente")
        log.info("chat %d eliminata", id_chat)
        return Response(status_code=204)

    @app.get(
        "/api/stato", response_model=Stato, summary="Back-end, database e agente",
        operation_id="statoBackend",
    )
    def stato():
        try:
            archivio.controlla()
            database = "ok"
        except ErroreDatabase as errore:
            database = str(errore)
        return Stato(backend="ok", database=database, agente=agente.stato())

    return app


def _db(funzione):
    try:
        return funzione()
    except ErroreDatabase as errore:
        raise HTTPException(503, f"Database non disponibile: {errore}") from errore
