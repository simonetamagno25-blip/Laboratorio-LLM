"""Client dell'API dell'agente (step 6) usato dal back-end."""

import logging

import httpx

log = logging.getLogger(__name__)

# Un turno può richiedere diverse chiamate al modello locale.
TIMEOUT_TURNO = 600.0


class AgenteNonRaggiungibile(RuntimeError):
    pass


class AgenteInRitardo(RuntimeError):
    """L'agente non ha risposto entro il timeout: potrebbe aver completato il turno lo stesso."""


class ConfermaScaduta(RuntimeError):
    """L'agente non conosce più la conferma (riavviato, o ripresa del turno già tentata)."""


class ErroreDellAgente(RuntimeError):
    """L'agente ha risposto con un errore (es. LM Studio spento); il messaggio è già leggibile."""


class ClientAgente:
    def __init__(self, url: str, http: httpx.Client | None = None):
        self.url = url.rstrip("/")
        self._http = http or httpx.Client(base_url=self.url, timeout=TIMEOUT_TURNO)

    def _post(self, percorso: str, corpo: dict) -> dict:
        try:
            risposta = self._http.post(percorso, json=corpo)
        except httpx.TimeoutException as errore:
            log.warning("agente in ritardo su %s: %r", self.url, errore)
            raise AgenteInRitardo(self.url) from errore
        except httpx.TransportError as errore:
            log.warning("agente non raggiungibile su %s: %r", self.url, errore)
            raise AgenteNonRaggiungibile(self.url) from errore
        if risposta.status_code == 404 and percorso == "/conferma":
            raise ConfermaScaduta(self.url)
        if risposta.is_error:
            try:
                dettaglio = risposta.json().get("detail")
            except ValueError:
                dettaglio = None
            raise ErroreDellAgente(str(dettaglio or f"errore {risposta.status_code} dell'agente"))
        return risposta.json()

    def invia(self, testo: str, cronologia: list[dict], riassunto: str) -> dict:
        return self._post(
            "/conversazione",
            {"messaggio": testo, "cronologia": cronologia, "riassunto": riassunto},
        )

    def conferma(self, id_conferma: str, si: bool) -> dict:
        return self._post("/conferma", {"id_conferma": id_conferma, "conferma": si})

    def stato(self) -> str:
        try:
            corpo = self._http.get("/stato", timeout=10).json()
        except (httpx.HTTPError, ValueError):
            return "non raggiungibile"
        problemi = [f"{k}: {v}" for k, v in corpo.items() if k != "strumenti_mcp" and v != "ok"]
        return "ok" if not problemi else "; ".join(problemi)
