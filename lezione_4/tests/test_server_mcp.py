import asyncio
import sys
from pathlib import Path
from typing import get_args

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from convertitore_mcp.unita import Unita

CARTELLA_PROGETTO = Path(__file__).parent.parent


async def _con_sessione(azione):
    parametri = StdioServerParameters(
        command=sys.executable, args=["-m", "convertitore_mcp"], cwd=str(CARTELLA_PROGETTO)
    )
    async with stdio_client(parametri) as (lettura, scrittura):
        async with ClientSession(lettura, scrittura) as sessione:
            await sessione.initialize()
            return await azione(sessione)


def _esegui(azione):
    return asyncio.run(_con_sessione(azione))


def _testo(risultato) -> str:
    return "".join(c.text for c in risultato.content if c.type == "text")


def _enum(schema: dict, proprieta: str) -> set[str]:
    nodo = schema["properties"][proprieta]
    if "$ref" in nodo:
        nodo = schema["$defs"][nodo["$ref"].rsplit("/", 1)[-1]]
    return set(nodo["enum"])


def test_elenco_strumenti_e_schema():
    async def elenca(sessione):
        return (await sessione.list_tools()).tools

    [strumento] = _esegui(elenca)
    assert strumento.name == "converti_unita"
    for proprieta in ("da", "a"):
        assert _enum(strumento.input_schema, proprieta) == set(get_args(Unita))


def test_chiamata_riuscita():
    async def chiama(sessione):
        return await sessione.call_tool("converti_unita", {"valore": 26, "da": "mi", "a": "km"})

    risultato = _esegui(chiama)
    assert not risultato.is_error
    assert _testo(risultato) == "26 mi = 41.8429 km"


def test_grandezze_incompatibili():
    async def chiama(sessione):
        return await sessione.call_tool("converti_unita", {"valore": 5, "da": "kg", "a": "m"})

    assert _testo(_esegui(chiama)).startswith("Errore:")


def test_unita_fuori_schema_rifiutata():
    async def chiama(sessione):
        return await sessione.call_tool("converti_unita", {"valore": 1, "da": "furlong", "a": "m"})

    # Con mcp 2.3.0 la validazione dello schema avviene nel server e produce is_error.
    risultato = _esegui(chiama)
    assert risultato.is_error
    assert "furlong" in _testo(risultato)
