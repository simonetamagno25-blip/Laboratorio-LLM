from datetime import datetime, timezone

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.cli import Sessione, esegui_ciclo
from assistente.grafo import costruisci_grafo, limite_ricorsione
from assistente.strumenti import crea_strumenti
from assistente.router import DecisioneRouter
from tests.fakes import ModelloFinto, RouterFinto, chiamata_strumento

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

    esegui_ciclo(
        sessione, "http://x/v1", leggi=leggi, scrivi=uscite.append, scarta_anticipato=lambda: None
    )
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

from assistente.cli import ATTESA, Conferma, e_un_si
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

    esegui_ciclo(
        crea_con_note(archivio),
        "http://x/v1",
        leggi=leggi,
        scrivi=lambda _: None,
        scarta_anticipato=lambda: None,
    )
    assert prompt == ["Tu> ", "Conferma> ", "Tu> "]


def test_ciclo_scarta_il_testo_scritto_prima_della_conferma(archivio):
    # Il testo scritto mentre il modello lavora non deve diventare la risposta alla conferma.
    eventi = []
    voci = iter(["elimina", "no", "/esci"])

    def leggi(p):
        eventi.append(p)
        return next(voci)

    esegui_ciclo(
        crea_con_note(archivio),
        "http://x/v1",
        leggi=leggi,
        scrivi=lambda _: None,
        scarta_anticipato=lambda: eventi.append("scarta"),
    )
    assert eventi == ["Tu> ", "scarta", "Conferma> ", "Tu> "]


def test_ciclo_avvisa_che_il_modello_sta_lavorando(archivio):
    out = ciclo(crea_con_note(archivio), ["elimina", "sì", "/esci"])
    righe = out.split("\n")
    # Un avviso prima della domanda di conferma e uno prima della risposta finale.
    assert righe == [ATTESA, DOMANDA, ATTESA, "Assistente> fatto", "Arrivederci."]


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


# --- Testo scritto in anticipo nel terminale ---

import io
import os
import sys

from assistente.cli import scarta_input_anticipato


def test_scarta_non_tocca_un_input_da_pipe():
    # Con l'input da pipe le risposte sono scritte apposta in anticipo: vanno lette tutte.
    ingresso = io.StringIO("sì\n")
    scarta_input_anticipato(ingresso)
    assert ingresso.readline() == "sì\n"


def test_scarta_ignora_un_input_chiuso():
    ingresso = io.StringIO()
    ingresso.close()
    scarta_input_anticipato(ingresso)


@pytest.mark.skipif(sys.platform == "win32", reason="terminale POSIX (verificato nel container)")
def test_scarta_svuota_un_terminale_posix():
    import select

    principale, secondario = os.openpty()
    with os.fdopen(secondario, "r") as terminale:
        os.write(principale, b"si\n")
        assert select.select([terminale], [], [], 1)[0], "il testo deve essere in attesa"
        scarta_input_anticipato(terminale)
        assert select.select([terminale], [], [], 0.2)[0] == []
    os.close(principale)


# --- Router ---


def test_conferma_note_non_riesegue_il_router(archivio):
    nota = archivio.aggiungi("comprare cavi")
    router = RouterFinto([DecisioneRouter(categoria="conversazione", motivo="note")])
    modello = ModelloFinto(
        [
            chiamata_strumento(None, nome="elimina_nota", args={"numero": nota.numero}),
            AIMessage("fatto"),
        ]
    )
    grafo = costruisci_grafo(
        modello,
        crea_strumenti(AUTUNNO, archivio=archivio),
        "Europe/Rome",
        3,
        archivio=archivio,
        router=router,
        ambito="note",
    )
    sessione = Sessione(grafo, limite_ricorsione(3))
    assert isinstance(sessione.chiedi("elimina la nota sui cavi"), Conferma)
    assert sessione.conferma(True) == "fatto"
    assert len(router.chiamate) == 1
    assert archivio.leggi(nota.numero) is None


def test_errore_del_router_non_tocca_la_cronologia():
    router = RouterFinto(
        [DecisioneRouter(categoria="conversazione", motivo="saluto"), RuntimeError("giù")]
    )
    grafo = costruisci_grafo(
        ModelloFinto([AIMessage("Ciao!")]),
        crea_strumenti(AUTUNNO),
        "Europe/Rome",
        3,
        router=router,
        ambito="ora e date",
    )
    sessione = Sessione(grafo, limite_ricorsione(3))
    assert sessione.chiedi("Ciao") == "Ciao!"
    with pytest.raises(RuntimeError):
        sessione.chiedi("Che ore sono?")
    assert len(sessione.cronologia) == 2
