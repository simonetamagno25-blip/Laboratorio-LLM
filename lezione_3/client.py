

"""Client minimo per il server locale di LM Studio.

Estensioni: domanda da terminale in ciclo (uscita con "esci" o Ctrl+C),
risposta in streaming, history della conversazione in memoria.
Import e gestione degli errori sono gia' presenti: conservarli.
"""

import json
import os

import requests
from dotenv import load_dotenv

# --- Configurazione -------------------------------------------------------
load_dotenv()
base_url = os.environ["LM_BASE_URL"]
model = os.environ["LM_MODEL"]

# --- Messaggi -------------------------------------------------------------
# La history vive solo in memoria: alla chiusura del programma si perde.
messages = [
    {
        "role": "system",
        "content": "Sei un assistente utile. Rispondi sempre in italiano, "
        "in modo chiaro e conciso.",
    },
]


def invia(messages):
    """Invia la conversazione e stampa la risposta a frammenti; la restituisce intera."""
    # --- Payload ----------------------------------------------------------
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 512,
        "reasoning_effort": "none",
        "stream": True,
    }

    # --- Chiamata ---------------------------------------------------------
    global response  # usata dal gestore di HTTPError
    response = requests.post(
        f"{base_url}/chat/completions", json=payload, stream=True, timeout=(5, 120)
    )
    response.raise_for_status()
    response.encoding = "utf-8"  # lo stream non dichiara il charset

    # Il server invia eventi SSE: righe "data: {...}" e infine "data: [DONE]".
    risposta = ""
    print("Modello: ", end="", flush=True)
    for riga in response.iter_lines(decode_unicode=True):
        if not riga or not riga.startswith("data: "):
            continue
        dati = riga[len("data: "):]
        if dati == "[DONE]":
            break
        frammento = json.loads(dati)["choices"][0]["delta"].get("content") or ""
        print(frammento, end="", flush=True)
        risposta += frammento
    print()
    return risposta


print("Scrivi una domanda; 'esci' o Ctrl+C per terminare.")
try:
    while True:
        domanda = input("\nTu: ").strip()
        if not domanda:
            continue
        if domanda.lower() == "esci":
            break

        messages.append({"role": "user", "content": domanda})
        try:
            risposta = invia(messages)
            messages.append({"role": "assistant", "content": risposta})
        except requests.exceptions.Timeout:
            print("Attesa scaduta: controllare server, carico e tempi.")
            messages.pop()
        except requests.exceptions.ConnectionError:
            print("Connessione fallita: controllare server, URL e porta.")
            messages.pop()
        except requests.exceptions.HTTPError:
            print("Errore HTTP:", response.status_code, response.text)
            messages.pop()
except (KeyboardInterrupt, EOFError):
    print()
print("Uscita.")
