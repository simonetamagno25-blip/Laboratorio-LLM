from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente import router
from assistente.router import messaggio_rifiuto, prompt_router
from tests.fakes import chiamata_strumento


def test_prompt_contiene_ambito_e_categorie():
    prompt = prompt_router("ora e date")
    assert "ora e date" in prompt
    assert "conversazione" in prompt
    assert "fuori_ambito" in prompt
    # Il router non valuta gli strumenti: il prompt non li nomina.
    assert "ora_corrente" not in prompt
    assert "strumento" not in prompt


def test_testo_solo_domanda():
    testo = router.testo_da_classificare([HumanMessage("Ciao")])
    assert testo.endswith("Domanda da classificare: Ciao")
    assert "Turni precedenti" not in testo


def test_testo_esclude_strumenti_e_tiene_la_domanda_in_fondo():
    cronologia = [
        HumanMessage("Che ore sono a Tokyo?"),
        chiamata_strumento("Asia/Tokyo"),
        ToolMessage("10:00 (Asia/Tokyo)", tool_call_id="call_1"),
        AIMessage("A Tokyo sono le 10:00."),
        HumanMessage("e a New York?"),
    ]
    testo = router.testo_da_classificare(cronologia)
    assert "Utente: Che ore sono a Tokyo?" in testo
    assert "Assistente: A Tokyo sono le 10:00." in testo
    assert "10:00 (Asia/Tokyo)" not in testo
    assert testo.endswith("Domanda da classificare: e a New York?")


def test_testo_tiene_solo_gli_ultimi_tre_turni():
    cronologia = []
    for i in range(1, 6):
        cronologia += [HumanMessage(f"d{i}"), AIMessage(f"r{i}")]
    cronologia.append(HumanMessage("d6"))
    testo = router.testo_da_classificare(cronologia)
    for presente in ("d3", "r3", "d4", "r4", "d5", "r5"):
        assert presente in testo
    assert "d2" not in testo and "r2" not in testo
    assert testo.endswith("d6")


def test_testo_tronca_i_messaggi_lunghi():
    cronologia = [HumanMessage("d1"), AIMessage("x" * 1000), HumanMessage("d2")]
    testo = router.testo_da_classificare(cronologia)
    assert "x" * 300 in testo
    assert "x" * 301 not in testo


def test_testo_con_contenuto_a_blocchi():
    cronologia = [
        HumanMessage("d1"),
        AIMessage(content=[{"type": "text", "text": "ciao"}]),
        HumanMessage("d2"),
    ]
    assert "Assistente: ciao" in router.testo_da_classificare(cronologia)


def test_rifiuto_cita_l_ambito():
    rifiuto = messaggio_rifiuto("ora e date")
    assert "fuori" in rifiuto
    assert rifiuto.rstrip(".").endswith("ora e date")


def test_prompt_seguiti_solo_di_argomenti_in_ambito():
    # Un seguito di una domanda fuori ambito («e quella dell'amatriciana?») resta fuori ambito.
    prompt = prompt_router("ora e date")
    assert "in ambito" in prompt
    assert "seguito di una domanda fuori ambito" in prompt
