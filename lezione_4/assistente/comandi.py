"""Comandi /prompts e /prompt della CLI: richiamo esplicito dei prompt MCP da parte dell'utente.

MCP non prevede comandi standard: sintassi e controlli sono decisi qui, nell'host.
"""

import shlex

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from assistente.client_mcp import InfoPrompt


class ErroreComando(ValueError):
    """Comando scritto male o non coerente con prompts/list: il modello non viene chiamato."""


USO = 'Uso: /prompt nome chiave=valore ... (valori con spazi tra virgolette, es. argomento="a b")'


def interpreta_comando_prompt(riga: str) -> tuple[str, dict[str, str]]:
    """'/prompt spiega argomento="MCP" livello=base' → ("spiega", {...})."""
    try:
        parti = shlex.split(riga)
    except ValueError:
        raise ErroreComando(f"Virgolette non chiuse. {USO}") from None
    if len(parti) < 2:
        raise ErroreComando(f"Comando incompleto: manca il nome del prompt. {USO}")
    nome, argomenti = parti[1], {}
    for parte in parti[2:]:
        chiave, uguale, valore = parte.partition("=")
        if not uguale or not chiave:
            raise ErroreComando(f"Argomento non nella forma chiave=valore: {parte!r}. {USO}")
        if chiave in argomenti:
            raise ErroreComando(f"Argomento ripetuto: {chiave}")
        argomenti[chiave] = valore
    return nome, argomenti


def valida(nome: str, argomenti: dict[str, str], elenco: list[InfoPrompt]) -> None:
    """Controllo rispetto a prompts/list, prima di qualsiasi chiamata al modello."""
    prompt = next((p for p in elenco if p.nome == nome), None)
    if prompt is None:
        disponibili = ", ".join(p.nome for p in elenco) or "nessuno"
        raise ErroreComando(f"Prompt sconosciuto: {nome} (disponibili: {disponibili})")
    ammessi = {a.nome for a in prompt.argomenti}
    for chiave in argomenti:
        if chiave not in ammessi:
            raise ErroreComando(
                f"Argomento sconosciuto: {chiave} (ammessi da {nome}: {', '.join(sorted(ammessi))})"
            )
    for argomento in prompt.argomenti:
        if argomento.obbligatorio and not argomenti.get(argomento.nome, "").strip():
            raise ErroreComando(f"Argomento obbligatorio mancante: {argomento.nome}")


def descrivi_prompt(elenco: list[InfoPrompt]) -> str:
    """Testo del comando /prompts."""
    if not elenco:
        return "Il server non espone prompt."
    righe = []
    for prompt in elenco:
        righe.append(f"{prompt.nome} — {prompt.descrizione}")
        for a in prompt.argomenti:
            tipo = "obbligatorio" if a.obbligatorio else "facoltativo"
            righe.append(f"    {a.nome} ({tipo}): {a.descrizione}")
    righe.append(USO)
    return "\n".join(righe)


def in_messaggi(coppie: list[tuple[str, str]]) -> list[BaseMessage]:
    """Messaggi di prompts/get → messaggi di LangChain (ruoli user e assistant)."""
    return [HumanMessage(t) if ruolo == "user" else AIMessage(t) for ruolo, t in coppie]
