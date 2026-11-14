import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import ValidationError

from assistente import revisore
from assistente.revisore import DecisioneRevisore, e_indicazione, indicazione, prompt_revisore
from tests.fakes import chiamata_strumento


def test_schema():
    d = DecisioneRevisore(coerente=False, motivo="manca la seconda parte")
    assert d.coerente is False
    with pytest.raises(ValidationError):
        DecisioneRevisore(motivo="senza esito")


def test_prompt_descrive_il_compito_senza_strumenti():
    prompt = prompt_revisore()
    assert "coerente" in prompt
    assert "tutte le parti" in prompt
    assert "ora_corrente" not in prompt
    assert "strumento" not in prompt


def test_testo_con_domanda_e_risposta_proposta():
    messaggi = [
        HumanMessage("Che ore sono a Tokyo e quanto fa 2+2?"),
        chiamata_strumento("Asia/Tokyo"),
        ToolMessage("2026-11-15T00:49:12+09:00", tool_call_id="call_1", name="ora_corrente"),
        AIMessage("A Tokyo sono le 00:49."),
    ]
    testo = revisore.testo_da_revisionare(messaggi)
    assert "Domanda dell'utente: Che ore sono a Tokyo e quanto fa 2+2?" in testo
    assert testo.endswith("Risposta proposta: A Tokyo sono le 00:49.")
    # Le chiamate e i risultati degli strumenti non sono mostrati al revisore.
    assert "2026-11-15T00:49:12" not in testo
    assert "Turni precedenti" not in testo


def test_testo_con_turni_precedenti_per_i_seguiti():
    messaggi = [
        HumanMessage("Che ore sono a Tokyo?"),
        AIMessage("A Tokyo sono le 00:49."),
        HumanMessage("e a New York?"),
        AIMessage("A New York sono le 10:49."),
    ]
    testo = revisore.testo_da_revisionare(messaggi)
    assert "Turni precedenti:\nUtente: Che ore sono a Tokyo?\nAssistente: A Tokyo sono le 00:49." in testo
    assert "Domanda dell'utente: e a New York?" in testo
    assert testo.endswith("Risposta proposta: A New York sono le 10:49.")


def test_testo_dopo_un_rifiuto_del_revisore():
    # Domanda corrente = ultima domanda vera; risposta proposta = ultima risposta dell'agente.
    messaggi = [
        HumanMessage("Che ore sono a Tokyo e quanto fa 2+2?"),
        AIMessage("A Tokyo sono le 00:49."),
        indicazione("manca il calcolo"),
        AIMessage("A Tokyo sono le 00:49 e 2+2 fa 4."),
    ]
    testo = revisore.testo_da_revisionare(messaggi)
    assert "Domanda dell'utente: Che ore sono a Tokyo e quanto fa 2+2?" in testo
    assert testo.endswith("Risposta proposta: A Tokyo sono le 00:49 e 2+2 fa 4.")
    assert "Indicazione del revisore" not in testo
    assert "Turni precedenti" not in testo


def test_indicazione():
    messaggio = indicazione("manca il calcolo")
    assert isinstance(messaggio, HumanMessage)
    assert messaggio.name == "revisore"
    assert messaggio.content.startswith("Indicazione del revisore:")
    assert "manca il calcolo" in messaggio.content
    assert e_indicazione(messaggio)
    assert not e_indicazione(HumanMessage("ciao"))
    assert not e_indicazione(AIMessage("ciao"))
