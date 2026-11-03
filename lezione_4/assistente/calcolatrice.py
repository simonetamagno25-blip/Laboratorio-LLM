"""Calcolatrice sicura: espressioni aritmetiche valutate sull'albero sintattico, senza eval."""

import ast
import math
import operator

LUNGHEZZA_MASSIMA = 200
ESPONENTE_MASSIMO = 100
VALORE_MASSIMO = 1e100

Numero = int | float

_BINARI = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARI = {ast.UAdd: operator.pos, ast.USub: operator.neg}


class ErroreCalcolo(ValueError):
    """Espressione non valida o non consentita."""


def _controlla(valore: Numero) -> Numero:
    if isinstance(valore, complex):
        raise ErroreCalcolo("risultato non reale")
    if not math.isfinite(valore) or abs(valore) > VALORE_MASSIMO:
        raise ErroreCalcolo("risultato troppo grande o non finito")
    return valore


def _valuta_nodo(nodo: ast.AST) -> Numero:
    if isinstance(nodo, ast.Constant):
        # bool è sottoclasse di int: va escluso esplicitamente.
        if type(nodo.value) not in (int, float):
            raise ErroreCalcolo(f"valore non consentito: {nodo.value!r}")
        return _controlla(nodo.value)
    if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in _UNARI:
        return _UNARI[type(nodo.op)](_valuta_nodo(nodo.operand))
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in _BINARI:
        sinistro = _valuta_nodo(nodo.left)
        destro = _valuta_nodo(nodo.right)
        if isinstance(nodo.op, (ast.Div, ast.Mod)) and destro == 0:
            raise ErroreCalcolo("divisione per zero")
        if isinstance(nodo.op, ast.Pow):
            if abs(destro) > ESPONENTE_MASSIMO:
                raise ErroreCalcolo(f"esponente oltre il limite di {ESPONENTE_MASSIMO}")
            if sinistro == 0 and destro < 0:
                raise ErroreCalcolo("divisione per zero")
        try:
            return _controlla(_BINARI[type(nodo.op)](sinistro, destro))
        except OverflowError:
            raise ErroreCalcolo("risultato troppo grande o non finito") from None
    raise ErroreCalcolo(f"operazione non consentita: {type(nodo).__name__}")


def valuta(espressione: str) -> Numero:
    if len(espressione) > LUNGHEZZA_MASSIMA:
        raise ErroreCalcolo(f"espressione troppo lunga (massimo {LUNGHEZZA_MASSIMA} caratteri)")
    try:
        albero = ast.parse(espressione, mode="eval")
    except SyntaxError:
        raise ErroreCalcolo("espressione non valida") from None
    return _valuta_nodo(albero.body)


def _formatta(valore: Numero) -> str:
    if isinstance(valore, float) and valore.is_integer():
        valore = int(valore)
    return f"{valore:.12g}" if isinstance(valore, float) else str(valore)


def calcola(espressione: str) -> str:
    try:
        return f"{espressione} = {_formatta(valuta(espressione))}"
    except ErroreCalcolo as errore:
        return f"Errore: {errore}"
