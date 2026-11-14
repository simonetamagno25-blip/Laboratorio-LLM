"""Genera frontend/api.js dal documento OpenAPI del back-end (il contratto del front-end).

Uso: python -m frontend.genera_api          (rigenera openapi.json e api.js)
     python -m frontend.genera_api --verifica (esce con 1 se non sono allineati)
"""

import json
import re
import sys
from pathlib import Path

CARTELLA = Path(__file__).resolve().parent
FILE_OPENAPI = CARTELLA / "openapi.json"
FILE_API = CARTELLA / "api.js"

INTESTAZIONE = """// GENERATO da frontend/genera_api.py a partire da frontend/openapi.json: non modificare a mano.
// Ogni funzione corrisponde a un'operazione del back-end (operationId).

export class ErroreApi extends Error {
  constructor(stato, messaggio) {
    super(messaggio);
    this.stato = stato;
  }
}

// Messaggio leggibile dal corpo di errore di FastAPI ({"detail": ...}).
export function messaggioErrore(stato, corpo) {
  const dettaglio = corpo && corpo.detail;
  if (typeof dettaglio === "string") return dettaglio;
  if (Array.isArray(dettaglio) && dettaglio.length) {
    return dettaglio.map((d) => d.msg).join("; ");
  }
  return `Errore ${stato} dal back-end`;
}

async function chiama(base, metodo, percorso, corpo, fetchFn) {
  let risposta;
  try {
    risposta = await fetchFn(base + percorso, {
      method: metodo,
      headers: corpo === undefined ? {} : { "Content-Type": "application/json" },
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    });
  } catch (errore) {
    throw new ErroreApi(0, `Back-end non raggiungibile su ${base || "questo indirizzo"}.`);
  }
  if (risposta.status === 204) return null;
  let dati = null;
  try {
    dati = await risposta.json();
  } catch (errore) {
    dati = null;
  }
  if (!risposta.ok) throw new ErroreApi(risposta.status, messaggioErrore(risposta.status, dati));
  return dati;
}
"""


def contratto_dal_backend() -> dict:
    from backend.agente import ClientAgente
    from backend.app import crea_app
    from backend.archivio import ArchivioMemoria

    return crea_app(ArchivioMemoria(), ClientAgente("http://agente")).openapi()


def _funzione(percorso: str, metodo: str, operazione: dict) -> str:
    parametri = re.findall(r"{(\w+)}", percorso)
    con_corpo = "requestBody" in operazione
    argomenti = parametri + (["corpo"] if con_corpo else [])
    url = "`" + re.sub(r"{(\w+)}", r"${encodeURIComponent(\1)}", percorso) + "`"
    firma = ", ".join(argomenti + ['{ base = "", fetchFn = fetch } = {}'])
    corpo = "corpo" if con_corpo else "undefined"
    return (
        f"// {metodo.upper()} {percorso} — {operazione.get('summary', '')}\n"
        f"export function {operazione['operationId']}({firma}) {{\n"
        f'  return chiama(base, "{metodo.upper()}", {url}, {corpo}, fetchFn);\n'
        "}\n"
    )


def genera(contratto: dict) -> str:
    funzioni = [
        _funzione(percorso, metodo, operazione)
        for percorso, operazioni in sorted(contratto["paths"].items())
        for metodo, operazione in sorted(operazioni.items())
    ]
    return INTESTAZIONE + "\n" + "\n".join(funzioni)


def testo_contratto(contratto: dict) -> str:
    return json.dumps(contratto, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argomenti: list[str]) -> int:
    contratto = contratto_dal_backend()
    attesi = {FILE_OPENAPI: testo_contratto(contratto), FILE_API: genera(contratto)}
    if "--verifica" in argomenti:
        diversi = [p.name for p, testo in attesi.items() if p.read_text(encoding="utf-8") != testo]
        if diversi:
            print(f"Da rigenerare: {', '.join(diversi)} (python -m frontend.genera_api)")
            return 1
        print("openapi.json e api.js sono allineati al back-end")
        return 0
    for percorso, testo in attesi.items():
        percorso.write_text(testo, encoding="utf-8", newline="\n")
        print(f"scritto {percorso.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
