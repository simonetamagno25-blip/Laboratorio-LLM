from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.revisore import indicazione
from assistente import riassunto
from assistente.riassunto import prompt_riassunto, punto_di_taglio
from tests.fakes import chiamata_strumento


def turno_semplice(domanda, risposta):
    return [HumanMessage(domanda), AIMessage(risposta)]


def turno_con_strumento(domanda, id):
    return [
        HumanMessage(domanda),
        chiamata_strumento("Europe/Rome", id=id),
        ToolMessage("17:05", tool_call_id=id, name="ora_corrente"),
        AIMessage("Sono le 17:05."),
    ]


def test_taglio_all_inizio_del_turno_che_conserva_almeno_n_messaggi():
    messaggi = (
        turno_semplice("Mi chiamo Giulia", "Piacere!")       # 0-1
        + turno_con_strumento("Che ore sono?", "c1")         # 2-5
        + turno_semplice("Grazie", "Prego")                  # 6-7
        + [HumanMessage("Come mi chiamo?")]                   # 8
    )
    # Con 3 conservati il taglio cade sulla domanda «Grazie» (restano 3 messaggi).
    assert punto_di_taglio(messaggi, 3) == 6
    # Con 4 conservati non si può tagliare dentro il turno con lo strumento: si arretra al suo inizio.
    assert punto_di_taglio(messaggi, 4) == 2


def test_il_taglio_non_separa_mai_strumenti_e_risultati():
    messaggi = turno_con_strumento("a", "c1") + turno_con_strumento("b", "c2") + [HumanMessage("c")]
    for conservati in range(1, len(messaggi)):
        taglio = punto_di_taglio(messaggi, conservati)
        tenuti = messaggi[taglio:]
        assert isinstance(tenuti[0], HumanMessage)
        richieste = {c["id"] for m in tenuti if isinstance(m, AIMessage) for c in m.tool_calls}
        risposte = {m.tool_call_id for m in tenuti if isinstance(m, ToolMessage)}
        assert richieste == risposte


def test_nessun_taglio_possibile():
    # Un unico turno lungo (più la domanda corrente non basta a conservare N): nessun taglio.
    messaggi = turno_con_strumento("a", "c1") + [HumanMessage("b")]
    assert punto_di_taglio(messaggi, 3) == 0


def test_il_taglio_non_cade_su_un_indicazione_del_revisore():
    messaggi = [
        HumanMessage("Ora e calcolo?"),
        AIMessage("Sono le 17:05."),
        indicazione("manca il calcolo"),
        AIMessage("Sono le 17:05 e fa 4."),
        HumanMessage("Grazie"),
    ]
    # L'indicazione (indice 2) è un HumanMessage ma non un inizio di turno: tagliarci
    # separerebbe la bozza dalla sua correzione.
    assert punto_di_taglio(messaggi, 1) == 4
    assert punto_di_taglio(messaggi, 2) == 0
    assert punto_di_taglio(messaggi, 3) == 0


def test_testo_da_riassumere_con_riassunto_precedente():
    messaggi = turno_con_strumento("Che ore sono?", "c1")
    testo = riassunto.testo_da_riassumere("L'utente si chiama Giulia.", messaggi)
    assert testo.startswith("Riassunto precedente:\nL'utente si chiama Giulia.")
    assert "Utente: Che ore sono?" in testo
    assert "Strumento ora_corrente: 17:05" in testo
    assert "Assistente: Sono le 17:05." in testo


def test_testo_da_riassumere_senza_bozze_e_indicazioni():
    messaggi = [
        HumanMessage("Ora e calcolo?"),
        AIMessage("bozza parziale"),
        indicazione("manca il calcolo"),
        AIMessage("risposta completa"),
    ]
    testo = riassunto.testo_da_riassumere("", messaggi)
    assert "Riassunto precedente" not in testo
    assert "bozza parziale" not in testo
    assert "Indicazione del revisore" not in testo
    assert "Assistente: risposta completa" in testo


def test_prompt_chiede_un_unico_riassunto_aggiornato():
    prompt = prompt_riassunto()
    assert "riassunto precedente" in prompt
    assert "nomi" in prompt
    assert "un unico riassunto" in prompt
