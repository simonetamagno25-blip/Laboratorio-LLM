from datetime import datetime, timezone

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from assistente.cli import Sessione, esegui_ciclo
from assistente.grafo import costruisci_grafo, limite_ricorsione
from assistente.strumenti import crea_strumenti
from tests.fakes import ModelloFinto, chiamata_strumento

AUTUNNO = lambda: datetime(2026, 10, 26, 16, 5, 12, tzinfo=timezone.utc)


def crea(risposte, max_passaggi=3):
    modello = ModelloFinto(risposte)
    grafo = costruisci_grafo(modello, crea_strumenti(AUTUNNO), "Europe/Rome", max_passaggi)
    return modello, Sessione(grafo, limite_ricorsione(max_passaggi))


def test_la_cronologia_passa_al_turno_successivo():
    modello, sessione = crea([AIMessage("prima"), AIMessage("seconda")])
    assert sessione.chiedi("uno") == "prima"
    assert sessione.chiedi("due") == "seconda"
    secondo = modello.chiamate[1]
    assert any(isinstance(m, HumanMessage) and m.content == "uno" for m in secondo)
    assert any(isinstance(m, AIMessage) and m.content == "prima" for m in secondo)


def test_turno_fallito_non_entra_in_cronologia():
    _, sessione = crea(
        [chiamata_strumento("Europe/Rome"), RuntimeError("giù"), AIMessage("ok")]
    )
    with pytest.raises(RuntimeError):
        sessione.chiedi("che ora è?")
    assert sessione.cronologia == []
    assert sessione.chiedi("ciao") == "ok"
    assert len(sessione.cronologia) == 2


def test_il_contatore_dei_passaggi_si_azzera_a_ogni_turno():
    _, sessione = crea(
        [
            chiamata_strumento("Europe/Rome", id="a"),
            AIMessage("primo"),
            chiamata_strumento("Europe/Rome", id="b"),
            AIMessage("secondo"),
        ],
        max_passaggi=1,
    )
    assert sessione.chiedi("ora?") == "primo"
    assert sessione.chiedi("ancora?") == "secondo"


def test_risposta_vuota():
    _, sessione = crea([AIMessage("")])
    assert sessione.chiedi("x") == "(risposta vuota)"


def ciclo(sessione, ingressi):
    voci = iter(ingressi)
    uscite = []

    def leggi(_prompt):
        v = next(voci)
        if isinstance(v, type) and issubclass(v, BaseException):
            raise v
        return v

    esegui_ciclo(sessione, "http://x/v1", leggi=leggi, scrivi=uscite.append)
    return "\n".join(uscite)


def test_ciclo_esce_con_esci():
    modello, sessione = crea([AIMessage("ciao!")])
    ciclo(sessione, ["", "ciao", "/esci"])
    assert len(modello.chiamate) == 1


@pytest.mark.parametrize("eccezione", [EOFError, KeyboardInterrupt])
def test_ciclo_esce_senza_traceback(eccezione):
    _, sessione = crea([])
    assert "Arrivederci." in ciclo(sessione, [eccezione])


def test_errore_mostrato_e_ciclo_continua():
    _, sessione = crea([RuntimeError("giù"), AIMessage("ok")])
    out = ciclo(sessione, ["a", "b", "/esci"])
    assert "Errore durante la risposta: giù" in out
    assert out.index("Errore durante la risposta: giù") < out.index("Assistente> ok")
