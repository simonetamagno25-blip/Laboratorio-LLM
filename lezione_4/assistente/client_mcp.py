"""Adattatore sincrono per un server MCP via stdio.

Il client MCP è asincrono: qui gira in un event loop dedicato, in un thread di fondo,
così il resto dell'assistente resta sincrono.
"""

import asyncio
import concurrent.futures
import logging
import sys
import tempfile
import threading
from contextlib import AsyncExitStack
from pathlib import Path

from langchain_core.tools import BaseTool, StructuredTool
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

log = logging.getLogger(__name__)

CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent


class ErroreMCP(RuntimeError):
    """Il server MCP non è partito o non ha risposto."""


def comando_convertitore() -> tuple[str, list[str]]:
    return sys.executable, ["-m", "convertitore_mcp"]


class ClientMCP:
    def __init__(
        self,
        comando: str,
        argomenti: list[str],
        timeout: float = 15.0,
        timeout_avvio: float = 30.0,
    ):
        self._parametri = StdioServerParameters(
            command=comando, args=argomenti, cwd=str(CARTELLA_PROGETTO)
        )
        self._timeout = timeout
        self._timeout_avvio = timeout_avvio
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._custode: concurrent.futures.Future | None = None
        self._sessione: ClientSession | None = None
        self._chiusura: asyncio.Event | None = None
        self._strumenti: list[BaseTool] = []
        # Lo stderr del server non deve finire sul terminale dell'utente: lo si
        # conserva per riportarlo nei messaggi d'errore.
        self._stderr = tempfile.TemporaryFile(mode="w+", encoding="utf-8")

    def __enter__(self) -> "ClientMCP":
        self.avvia()
        return self

    def __exit__(self, *dettagli) -> None:
        self.chiudi()

    def avvia(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        pronto: concurrent.futures.Future = concurrent.futures.Future()
        self._custode = asyncio.run_coroutine_threadsafe(self._custodisci(pronto), self._loop)
        try:
            strumenti_mcp = pronto.result(timeout=self._timeout_avvio)
        except concurrent.futures.TimeoutError:
            self.chiudi()
            raise ErroreMCP(
                f"il server non ha risposto entro {self._timeout_avvio:g} secondi"
            ) from None
        except Exception as errore:
            dettaglio = self._ultimo_stderr()
            self.chiudi()
            motivo = f"{type(errore).__name__}: {errore}" if str(errore) else type(errore).__name__
            raise ErroreMCP(motivo + (f" — {dettaglio}" if dettaglio else "")) from errore
        self._strumenti = [self._converti(s) for s in strumenti_mcp]
        log.info("server MCP avviato con gli strumenti %s", [s.name for s in self._strumenti])

    async def _custodisci(self, pronto: concurrent.futures.Future) -> None:
        # Apertura e chiusura della sessione avvengono nello stesso task, come richiede anyio.
        try:
            async with AsyncExitStack() as pila:
                lettura, scrittura = await pila.enter_async_context(
                    stdio_client(self._parametri, errlog=self._stderr)
                )
                sessione = await pila.enter_async_context(ClientSession(lettura, scrittura))
                await sessione.initialize()
                elenco = await sessione.list_tools()
                self._sessione = sessione
                self._chiusura = asyncio.Event()
                pronto.set_result(elenco.tools)
                await self._chiusura.wait()
        except BaseException as errore:
            if not pronto.done():
                pronto.set_exception(errore)
            raise

    def _converti(self, strumento) -> BaseTool:
        nome = strumento.name

        def chiama(**argomenti) -> str:
            return self._chiama(nome, argomenti)

        return StructuredTool(
            name=nome,
            description=strumento.description or nome,
            args_schema=strumento.input_schema,
            func=chiama,
        )

    def _chiama(self, nome: str, argomenti: dict) -> str:
        if self._sessione is None or self._loop is None:
            return "Errore: server MCP non disponibile (sessione chiusa)"
        futuro = asyncio.run_coroutine_threadsafe(
            self._sessione.call_tool(nome, argomenti), self._loop
        )
        try:
            risultato = futuro.result(timeout=self._timeout)
        except concurrent.futures.TimeoutError:
            futuro.cancel()
            log.warning("timeout dello strumento MCP %s", nome)
            return "Errore: timeout del server MCP"
        except Exception as errore:
            log.warning("strumento MCP %s non eseguito: %r", nome, errore)
            return f"Errore: server MCP non disponibile ({errore or type(errore).__name__})"
        testo = "".join(c.text for c in risultato.content if c.type == "text")
        if risultato.is_error and not testo.startswith("Errore"):
            testo = f"Errore: {testo}"
        return testo

    def strumenti(self) -> list[BaseTool]:
        return list(self._strumenti)

    def _ultimo_stderr(self) -> str:
        try:
            self._stderr.seek(0)
            righe = self._stderr.read().strip().splitlines()
        except (OSError, ValueError):
            return ""
        return righe[-1] if righe else ""

    def chiudi(self) -> None:
        loop, self._loop = self._loop, None
        if loop is None:
            return
        self._sessione = None
        if self._chiusura is not None:
            loop.call_soon_threadsafe(self._chiusura.set)
        elif self._custode is not None:
            self._custode.cancel()
        if self._custode is not None:
            try:
                self._custode.result(timeout=self._timeout_avvio)
            except (Exception, asyncio.CancelledError) as errore:
                log.debug("chiusura del server MCP: %r", errore)
        loop.call_soon_threadsafe(loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=self._timeout_avvio)
        if not loop.is_running():
            loop.close()
        self._stderr.close()
