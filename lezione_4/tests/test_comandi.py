import pytest
from langchain_core.messages import AIMessage, HumanMessage

from assistente.client_mcp import ArgomentoPrompt, InfoPrompt
from assistente.comandi import (
    ErroreComando,
    descrivi_prompt,
    in_messaggi,
    interpreta_comando_prompt,
    valida,
)

ELENCO = [
    InfoPrompt(
        "spiega",
        "Spiega un argomento al livello richiesto.",
        (
            ArgomentoPrompt("argomento", "concetto da spiegare", True),
            ArgomentoPrompt("livello", "base, intermedio o avanzato", False),
        ),
    ),
    InfoPrompt(
        "riassumi_conversazione",
        "Riassume i turni della conversazione corrente.",
        (ArgomentoPrompt("stile", "sintetico o dettagliato", False),),
    ),
]


def test_interpreta_con_virgolette():
    riga = '/prompt spiega argomento="Model Context Protocol" livello=base'
    assert interpreta_comando_prompt(riga) == (
        "spiega",
        {"argomento": "Model Context Protocol", "livello": "base"},
    )


def test_interpreta_senza_argomenti():
    assert interpreta_comando_prompt("/prompt riassumi_conversazione") == (
        "riassumi_conversazione",
        {},
    )


@pytest.mark.parametrize(
    "riga, frammento",
    [
        ("/prompt", "manca il nome"),
        ("/prompt spiega argomento", "chiave=valore"),
        ("/prompt spiega =x", "chiave=valore"),
        ('/prompt spiega argomento="non chiusa', "virgolette"),
        ("/prompt spiega livello=base livello=avanzato", "ripetuto"),
    ],
)
def test_interpreta_sintassi_errata(riga, frammento):
    with pytest.raises(ErroreComando, match=frammento):
        interpreta_comando_prompt(riga)


def test_valida_ok():
    valida("spiega", {"argomento": "MCP"}, ELENCO)
    valida("riassumi_conversazione", {}, ELENCO)


@pytest.mark.parametrize(
    "nome, argomenti, frammento",
    [
        ("traduci", {}, "Prompt sconosciuto: traduci"),
        ("spiega", {}, "Argomento obbligatorio mancante: argomento"),
        ("spiega", {"argomento": "MCP", "lingua": "en"}, "Argomento sconosciuto: lingua"),
        ("spiega", {"argomento": "  "}, "Argomento obbligatorio mancante: argomento"),
    ],
)
def test_valida_errori(nome, argomenti, frammento):
    with pytest.raises(ErroreComando, match=frammento):
        valida(nome, argomenti, ELENCO)


def test_descrivi_prompt():
    testo = descrivi_prompt(ELENCO)
    assert "spiega — Spiega un argomento al livello richiesto." in testo
    assert "argomento (obbligatorio): concetto da spiegare" in testo
    assert "livello (facoltativo): base, intermedio o avanzato" in testo
    assert "riassumi_conversazione" in testo


def test_descrivi_nessun_prompt():
    assert descrivi_prompt([]) == "Il server non espone prompt."


def test_in_messaggi():
    messaggi = in_messaggi([("user", "spiegami MCP"), ("assistant", "certo")])
    assert isinstance(messaggi[0], HumanMessage) and messaggi[0].content == "spiegami MCP"
    assert isinstance(messaggi[1], AIMessage) and messaggi[1].content == "certo"
