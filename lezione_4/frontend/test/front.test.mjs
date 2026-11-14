// Test del front-end senza browser: node --test frontend/test/
import assert from "node:assert/strict";
import { test } from "node:test";

import { ErroreApi, creaChat, eliminaChat, inviaMessaggio, messaggioErrore } from "../api.js";
import { descriviStrumento, puoInviare, statoDopoRisposta, testoErrore, dataBreve } from "../logica.js";

function fetchFinto(stato, corpo, registro = []) {
  return async (url, opzioni) => {
    registro.push({ url, ...opzioni });
    return {
      status: stato,
      ok: stato >= 200 && stato < 300,
      json: async () => {
        if (corpo === undefined) throw new Error("niente corpo");
        return corpo;
      },
    };
  };
}

test("le chiamate generate usano base, metodo, percorso e corpo del contratto", async () => {
  const registro = [];
  const fetchFn = fetchFinto(200, { tipo: "risposta", risposta: "ok", strumenti: [] }, registro);
  const risposta = await inviaMessaggio(7, { testo: "Che ore sono?" }, { base: "http://be:8200", fetchFn });
  assert.equal(risposta.risposta, "ok");
  assert.equal(registro[0].url, "http://be:8200/api/chat/7/messaggi");
  assert.equal(registro[0].method, "POST");
  assert.deepEqual(JSON.parse(registro[0].body), { testo: "Che ore sono?" });
});

test("201 e 204", async () => {
  assert.deepEqual(await creaChat({ fetchFn: fetchFinto(201, { id: 1, titolo: "Nuova chat" }) }), {
    id: 1,
    titolo: "Nuova chat",
  });
  assert.equal(await eliminaChat(1, { fetchFn: fetchFinto(204) }), null);
});

test("errore del back-end con il messaggio di FastAPI", async () => {
  const fetchFn = fetchFinto(503, { detail: "Agente non raggiungibile su http://agente:8100" });
  await assert.rejects(inviaMessaggio(1, { testo: "x" }, { fetchFn }), (errore) => {
    assert.ok(errore instanceof ErroreApi);
    assert.equal(errore.stato, 503);
    assert.equal(errore.message, "Agente non raggiungibile su http://agente:8100");
    return true;
  });
});

test("back-end spento: errore leggibile, nessuna eccezione grezza", async () => {
  const fetchFn = async () => {
    throw new TypeError("Failed to fetch");
  };
  await assert.rejects(creaChat({ base: "http://be:8200", fetchFn }), /Back-end non raggiungibile su http:\/\/be:8200/);
});

test("messaggi di validazione (422)", () => {
  assert.equal(messaggioErrore(422, { detail: [{ msg: "il messaggio è vuoto" }] }), "il messaggio è vuoto");
  assert.equal(messaggioErrore(500, null), "Errore 500 dal back-end");
});

test("logica dell'interfaccia", () => {
  assert.equal(
    descriviStrumento({ nome: "ora_corrente", argomenti: { fuso_orario: "Asia/Tokyo" }, risultato: "01:05" }),
    "ora_corrente(fuso_orario=Asia/Tokyo) → 01:05",
  );
  assert.equal(puoInviare("  ", false), false);
  assert.equal(puoInviare("ciao", true), false);
  assert.equal(puoInviare("ciao", false), true);
  assert.deepEqual(statoDopoRisposta({ tipo: "conferma", domanda: "Eliminare?" }), {
    confermaInAttesa: true,
    domandaConferma: "Eliminare?",
  });
  assert.equal(testoErrore(new Error("boh")), "boh");
  assert.equal(dataBreve(null), "");
});
