"""Agente come servizio HTTP (FastAPI): python -m assistente.servizio.

Lo stesso grafo della CLI, senza stato tra un turno e l'altro: cronologia e riassunto arrivano dal
chiamante e tornano aggiornati. La documentazione OpenAPI è su /docs e /openapi.json.
"""

import logging
import sys
from collections.abc import Callable
from typing import Literal

import httpx
import openai
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage, messages_from_dict, messages_to_dict
from pydantic import BaseModel, Field, model_validator

from assistente.agente import Agente, ConfermaSconosciuta, RichiestaConferma, Risposta
from assistente.catalogo import ErroreCatalogo, carica_catalogo
from assistente.client_api import crea_strumenti_api
from assistente.client_mcp import ClientMCP, ErroreMCP, comando_convertitore
from assistente.config import ErroreConfigurazione, carica_configurazione
from assistente.grafo import costruisci_grafo, limite_ricorsione
from assistente.modello import (
    crea_modello,
    crea_revisore,
    crea_riassuntore,
    crea_router,
    descrivi_errore,
)
from assistente.note import ErroreArchivio, apri_archivio
from assistente.preferenze import carica_preferenze, predefinite
from assistente.strumenti import crea_strumenti

log = logging.getLogger(__name__)


# --- Schemi dell'API (diventano il documento OpenAPI) ---


class RichiestaConversazione(BaseModel):
    """Una domanda (`messaggio`) oppure messaggi già pronti (`messaggi`, es. da un prompt MCP)."""

    messaggio: str | None = Field(None, description="testo della domanda dell'utente")
    messaggi: list[dict] | None = Field(
        None, description="messaggi LangChain serializzati (messages_to_dict), al posto di messaggio"
    )
    cronologia: list[dict] = Field(
        default_factory=list, description="cronologia restituita dalla risposta precedente"
    )
    riassunto: str = Field("", description="riassunto restituito dalla risposta precedente")

    @model_validator(mode="after")
    def una_sola_domanda(self):
        if (self.messaggio is None) == (self.messaggi is None):
            raise ValueError("serve esattamente uno tra messaggio e messaggi")
        if self.messaggio is not None and not self.messaggio.strip():
            raise ValueError("il messaggio è vuoto")
        if self.messaggi is not None and not self.messaggi:
            raise ValueError("messaggi è vuoto")
        return self


class RichiestaDiConferma(BaseModel):
    id_conferma: str
    conferma: bool = Field(description="true per eseguire l'eliminazione, false per annullarla")


class StrumentoUsatoJSON(BaseModel):
    nome: str
    argomenti: dict
    risultato: str


class RispostaAgente(BaseModel):
    tipo: Literal["risposta", "conferma"]
    risposta: str | None = None
    strumenti: list[StrumentoUsatoJSON] = Field(default_factory=list)
    cronologia: list[dict] = Field(default_factory=list)
    riassunto: str = ""
    domanda: str | None = Field(None, description="domanda di conferma (solo con tipo=conferma)")
    id_conferma: str | None = None


class StatoServizio(BaseModel):
    agente: str
    server_mcp: str
    strumenti_mcp: list[str]
    modello: str


class ArgomentoJSON(BaseModel):
    nome: str
    descrizione: str
    obbligatorio: bool


class PromptJSON(BaseModel):
    nome: str
    descrizione: str
    argomenti: list[ArgomentoJSON]


class RichiestaPrompt(BaseModel):
    argomenti: dict[str, str] = Field(default_factory=dict)


class MessaggioPrompt(BaseModel):
    ruolo: str
    testo: str


class MessaggiPrompt(BaseModel):
    messaggi: list[MessaggioPrompt]


def _in_json(esito: Risposta | RichiestaConferma) -> RispostaAgente:
    if isinstance(esito, RichiestaConferma):
        return RispostaAgente(tipo="conferma", domanda=esito.domanda, id_conferma=esito.id_conferma)
    return RispostaAgente(
        tipo="risposta",
        risposta=esito.testo,
        strumenti=[StrumentoUsatoJSON(**vars(s)) for s in esito.strumenti],
        cronologia=messages_to_dict(esito.cronologia),
        riassunto=esito.riassunto,
    )


def _messaggi(dati: list[dict]):
    try:
        return messages_from_dict(dati)
    except (KeyError, TypeError, ValueError) as errore:
        raise HTTPException(422, f"messaggi non validi: {errore}") from errore


def controllo_lm_studio(base_url: str) -> Callable[[], str | None]:
    """Funzione per /stato: None se LM Studio risponde, altrimenti il messaggio d'errore."""

    def controlla() -> str | None:
        try:
            httpx.get(f"{base_url.rstrip('/')}/models", timeout=3).raise_for_status()
        except httpx.HTTPError as errore:
            log.warning("stato: LM Studio non raggiungibile (%s)", errore)
            return f"LM Studio non raggiungibile su {base_url}"
        return None

    return controlla


def crea_app(agente: Agente, *, mcp, controlla_modello: Callable[[], str | None], base_url: str):
    app = FastAPI(
        title="Agente del laboratorio",
        description="Grafo LangGraph dell'assistente del laboratorio come servizio HTTP, senza "
        "stato: cronologia e riassunto arrivano dal chiamante e tornano aggiornati.",
        version="1.0.0",
    )

    def esegui(funzione):
        try:
            return _in_json(funzione())
        except openai.APIConnectionError as errore:
            raise HTTPException(503, descrivi_errore(errore, base_url)) from errore
        except openai.APIStatusError as errore:
            raise HTTPException(502, descrivi_errore(errore, base_url)) from errore
        except ConfermaSconosciuta as errore:
            raise HTTPException(404, f"nessuna conferma in attesa con id {errore.args[0]}") from None
        except Exception as errore:
            log.exception("api: errore durante il turno")
            raise HTTPException(500, descrivi_errore(errore, base_url)) from errore

    @app.post("/conversazione", response_model=RispostaAgente, summary="Un turno della conversazione")
    def conversazione(richiesta: RichiestaConversazione):
        nuovi = (
            [HumanMessage(richiesta.messaggio)]
            if richiesta.messaggio is not None
            else _messaggi(richiesta.messaggi)
        )
        cronologia = _messaggi(richiesta.cronologia)
        log.info(
            "api: POST /conversazione (%d messaggi in cronologia, %d nuovi)",
            len(cronologia),
            len(nuovi),
        )
        risposta = esegui(lambda: agente.turno(nuovi, cronologia, richiesta.riassunto))
        log.info(
            "api: risposta %s, strumenti usati %s",
            risposta.tipo,
            [s.nome for s in risposta.strumenti],
        )
        return risposta

    @app.post("/conferma", response_model=RispostaAgente, summary="Risposta a una conferma")
    def conferma(richiesta: RichiestaDiConferma):
        log.info("api: POST /conferma %s -> %s", richiesta.id_conferma, richiesta.conferma)
        return esegui(lambda: agente.conferma(richiesta.id_conferma, richiesta.conferma))

    @app.get(
        "/stato",
        response_model=StatoServizio,
        summary="Agente, server MCP e modello raggiungibili",
        responses={503: {"model": StatoServizio}},
    )
    def stato():
        strumenti = [s.name for s in mcp.strumenti()]
        errore_modello = controlla_modello()
        corpo = StatoServizio(
            agente="ok",
            server_mcp="ok" if strumenti else "non disponibile",
            strumenti_mcp=strumenti,
            modello=errore_modello or "ok",
        )
        codice = 200 if strumenti and errore_modello is None else 503
        return JSONResponse(corpo.model_dump(), status_code=codice)

    @app.get("/prompts", response_model=list[PromptJSON], summary="prompts/list del server MCP")
    def prompts():
        try:
            elenco = mcp.elenca_prompt()
        except ErroreMCP as errore:
            raise HTTPException(502, f"server MCP: {errore}") from errore
        return [
            PromptJSON(
                nome=p.nome,
                descrizione=p.descrizione,
                argomenti=[ArgomentoJSON(**vars(a)) for a in p.argomenti],
            )
            for p in elenco
        ]

    @app.post("/prompts/{nome}", response_model=MessaggiPrompt, summary="prompts/get del server MCP")
    def prompt(nome: str, richiesta: RichiestaPrompt):
        try:
            coppie = mcp.ottieni_prompt(nome, richiesta.argomenti)
        except ErroreMCP as errore:
            raise HTTPException(502, f"server MCP: {errore}") from errore
        return MessaggiPrompt(messaggi=[MessaggioPrompt(ruolo=r, testo=t) for r, t in coppie])

    return app


# --- Avvio: python -m assistente.servizio ---


def servi(app, host: str, porta: int) -> None:
    import uvicorn

    log.info("servizio agente in ascolto su %s:%d (documentazione su /docs)", host, porta)
    uvicorn.run(app, host=host, port=porta, log_level="warning")


def main() -> int:
    try:
        config = carica_configurazione()
    except ErroreConfigurazione as errore:
        print(errore, file=sys.stderr)
        return 2

    logging.basicConfig(
        level=config.log_level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)

    # Prima del server MCP: con un catalogo non valido non resta nessun sottoprocesso da chiudere.
    try:
        catalogo = carica_catalogo()
    except ErroreCatalogo as errore:
        print(f"Catalogo non valido: {errore}", file=sys.stderr)
        return 4

    # Anche l'archivio prima del server MCP, per lo stesso motivo.
    try:
        archivio = apri_archivio(config.percorso_db_note, config.fuso_predefinito)
    except ErroreArchivio as errore:
        print(f"Archivio note non disponibile: {errore}", file=sys.stderr)
        return 5
    try:
        return _avvia(config, catalogo, archivio)
    finally:
        archivio.chiudi()


def _avvia(config, catalogo, archivio) -> int:
    client_mcp = ClientMCP(
        *comando_convertitore(), ambiente={"PERCORSO_PREFERENZE": config.percorso_preferenze}
    )
    try:
        client_mcp.avvia()
    except ErroreMCP as errore:
        print(f"Server MCP del convertitore non avviato: {errore}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        client_mcp.chiudi()
        print("Arrivederci.")
        return 130

    # Il try/finally chiude il server MCP anche con Ctrl+C o errori imprevisti.
    try:
        # Resource: la legge l'host una volta, prima della prima domanda (non è uno strumento).
        preferenze = carica_preferenze(client_mcp, predefinite(config.fuso_predefinito))
        strumenti = (
            crea_strumenti(catalogo=catalogo, archivio=archivio)
            + client_mcp.strumenti()
            + crea_strumenti_api(config.scadenze_api_url)
        )
        grafo = costruisci_grafo(
            crea_modello(config, strumenti),
            strumenti,
            config.fuso_predefinito,
            config.max_passaggi_strumenti,
            archivio=archivio,
            router=crea_router(config),
            ambito=config.ambito,
            revisore=crea_revisore(config),
            max_revisioni=config.max_revisioni,
            riassuntore=crea_riassuntore(config),
            soglia_riassunto=config.soglia_riassunto,
            messaggi_conservati=config.messaggi_conservati,
            preferenze=preferenze,
        )
        agente = Agente(
            grafo, limite_ricorsione(config.max_passaggi_strumenti, config.max_revisioni)
        )
        app = crea_app(
            agente,
            mcp=client_mcp,
            controlla_modello=controllo_lm_studio(config.base_url),
            base_url=config.base_url,
        )
        servi(app, config.agente_host, config.agente_porta)
    except KeyboardInterrupt:
        pass
    finally:
        client_mcp.chiudi()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
