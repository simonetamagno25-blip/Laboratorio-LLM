from datetime import datetime, timezone

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

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


class ModelloInterrotto:
    def invoke(self, messaggi, config=None):
        raise KeyboardInterrupt


def test_ctrl_c_durante_la_risposta_esce_pulito():
    grafo = costruisci_grafo(ModelloInterrotto(), crea_strumenti(AUTUNNO), "Europe/Rome", 3)
    sessione = Sessione(grafo, limite_ricorsione(3))
    assert "Arrivederci." in ciclo(sessione, ["ciao"])
    assert sessione.cronologia == []


# --- Note: conferma nel terminale ---

from assistente.cli import Conferma, e_un_si
from assistente.note import apri_archivio

DOMANDA = 'Eliminare la nota 1 (2026-10-26 17:05): "sensore SEN-004 da ricalibrare"? [sì/no]'


@pytest.fixture
def archivio(tmp_path):
    archivio = apri_archivio(tmp_path / "note.sqlite3", "Europe/Rome", AUTUNNO)
    archivio.aggiungi("sensore SEN-004 da ricalibrare")
    yield archivio
    archivio.chiudi()


def crea_con_note(archivio, dopo=None):
    risposte = [
        chiamata_strumento(None, nome="elimina_nota", args={"numero": 1}),
        AIMessage("fatto") if dopo is None else dopo,
    ]
    modello = ModelloFinto(risposte)
    grafo = costruisci_grafo(
        modello, crea_strumenti(AUTUNNO, archivio=archivio), "Europe/Rome", 3, archivio=archivio
    )
    return Sessione(grafo, limite_ricorsione(3))


@pytest.mark.parametrize(
    "risposta, atteso",
    [
        ("sì", True),
        (" Sì ", True),
        ("si", True),
        ("S", True),
        ("", False),
        ("no", False),
        ("sìì", False),
        ("yes", False),
        ("ok", False),
    ],
)
def test_e_un_si(risposta, atteso):
    assert e_un_si(risposta) is atteso


def test_chiedi_restituisce_la_conferma(archivio):
    sessione = crea_con_note(archivio)
    assert sessione.chiedi("elimina la nota sul sensore") == Conferma(DOMANDA)
    assert sessione.cronologia == []


def test_conferma_completa_il_turno(archivio):
    sessione = crea_con_note(archivio)
    sessione.chiedi("elimina")
    assert sessione.conferma(True) == "fatto"
    assert archivio.leggi(1) is None
    assert any(
        isinstance(m, ToolMessage) and m.content == "Nota 1 eliminata."
        for m in sessione.cronologia
    )


def test_conferma_rifiutata_completa_il_turno(archivio):
    sessione = crea_con_note(archivio)
    sessione.chiedi("elimina")
    sessione.conferma(False)
    assert archivio.leggi(1) is not None
    assert len(sessione.cronologia) == 4


def test_errore_dopo_la_conferma_non_entra_in_cronologia(archivio):
    sessione = crea_con_note(archivio, dopo=RuntimeError("giù"))
    sessione.chiedi("elimina")
    with pytest.raises(RuntimeError):
        sessione.conferma(True)
    assert sessione.cronologia == []
    assert archivio.leggi(1) is None


def test_ciclo_con_conferma_si(archivio):
    out = ciclo(crea_con_note(archivio), ["elimina", "sì", "/esci"])
    assert DOMANDA in out
    assert "Assistente> fatto" in out
    assert archivio.leggi(1) is None


def test_ciclo_con_conferma_vuota(archivio):
    out = ciclo(crea_con_note(archivio), ["elimina", "", "/esci"])
    assert DOMANDA in out
    assert archivio.leggi(1) is not None


@pytest.mark.parametrize("eccezione", [EOFError, KeyboardInterrupt])
def test_ciclo_interrotto_durante_la_conferma(archivio, eccezione):
    out = ciclo(crea_con_note(archivio), ["elimina", eccezione])
    assert out.endswith("Arrivederci.")
    assert archivio.leggi(1) is not None


def test_ciclo_legge_la_conferma_con_il_suo_prompt(archivio):
    prompt = []
    voci = iter(["elimina", "no", "/esci"])

    def leggi(p):
        prompt.append(p)
        return next(voci)

    esegui_ciclo(crea_con_note(archivio), "http://x/v1", leggi=leggi, scrivi=lambda _: None)
    assert prompt == ["Tu> ", "Conferma> ", "Tu> "]


def test_turno_fallito_con_checkpointer_non_resta_nel_thread(archivio):
    modello = ModelloFinto([RuntimeError("giù"), AIMessage("ok")])
    grafo = costruisci_grafo(
        modello, crea_strumenti(AUTUNNO, archivio=archivio), "Europe/Rome", 3, archivio=archivio
    )
    sessione = Sessione(grafo, limite_ricorsione(3))
    with pytest.raises(RuntimeError):
        sessione.chiedi("primo")
    assert sessione.chiedi("secondo") == "ok"
    umani = [m.content for m in modello.chiamate[1] if isinstance(m, HumanMessage)]
    assert umani == ["secondo"]
