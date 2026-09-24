"""Constituenten afgeleid uit UD: naamwoordgroepen, bijzinnen en werkwoordgroepen.

Dit zijn geen JAS-klassen maar grammaticale eenheden. De detectoren (PR 6-7) gebruiken ze als
kandidaatgrenzen en als spanopties; welke JAS-klasse erbij hoort beslist een latere stap.

Alles hier is een functie van het UD-model, dus werkt voor elke provider die dat levert. Op een
gedegradeerde analyse (geen dependencies) leveren ze niets – en dat is zichtbaar, niet stil: de
aanroeper ziet `analyse.gedegradeerd`.
"""
from __future__ import annotations

from dataclasses import dataclass

from .model import LinguisticAnalysis

_NOMINAAL = {"NOUN", "PROPN", "PRON"}
# UD-relaties waarmee een (bij)zin aan zijn hoofd hangt.
_BIJZIN = {"advcl", "acl", "acl:relcl", "ccomp", "csubj", "xcomp"}


@dataclass(frozen=True, slots=True)
class Constituent:
    soort: str                # "np", "bijzin", "predicaat"
    kop: int                  # tokenindex van het hoofd
    tokens: tuple[int, ...]
    start: int
    eind: int
    relatie: str              # deprel van het hoofd
    markeerder: str = ""      # voegwoord van een bijzin ("indien", "tenzij"), lowercase


def _maak(a: LinguisticAnalysis, soort: str, kop: int, tokens: tuple[int, ...], markeerder: str = ""):
    start, eind = a.bereik(tokens)
    return Constituent(soort, kop, tokens, start, eind, a.tokens[kop].deprel, markeerder)


def _zonder_rand_interpunctie(a: LinguisticAnalysis, tokens: tuple[int, ...]) -> tuple[int, ...]:
    lijst = list(tokens)
    while lijst and a.tokens[lijst[0]].upos == "PUNCT":
        lijst.pop(0)
    while lijst and a.tokens[lijst[-1]].upos == "PUNCT":
        lijst.pop()
    return tuple(lijst)


# Modificeerders die bij de kern van een naamwoordgroep horen: lidwoord, bijvoeglijk naamwoord,
# telwoord, bezitter, samenstelling, meerwoordige naam. Een PP of bijzin erna niet.
_KERN = {"det", "amod", "nummod", "nmod:poss", "compound", "flat", "flat:name", "fixed", "advmod"}


def naamwoordgroepen(a: LinguisticAnalysis) -> list[Constituent]:
    """Per nominale kop twee grenzen: de volledige groep (`np`) en de kern (`np_kern`).

    Uit de referentieset blijkt dat een rechtssubject meestal de kern is ("voetgangers",
    "de verzekerde"), terwijl de volledige groep er een PP of bijzin bij pakt ("voetgangers die de
    rijbaan oversteken"). Welke grens juridisch klopt is een latere keuze; beide moeten als
    spanoptie bestaan. Een bijzin die aan de kop hangt zit nooit in `np`: die is als bijzin apart
    te vinden.
    """
    if a.gedegradeerd:
        return []
    uit = []
    for t in a.tokens:
        if t.upos not in _NOMINAAL:
            continue
        weg = set()
        for k in a.kinderen(t.i):
            if a.tokens[k].deprel in _BIJZIN:
                weg.update(a.subboom(k))
        tokens = _zonder_rand_interpunctie(a, tuple(i for i in a.subboom(t.i) if i not in weg))
        if tokens and a.aaneengesloten(tokens):
            uit.append(_maak(a, "np", t.i, tokens))
        kern = {t.i}
        for k in a.kinderen(t.i):
            if a.tokens[k].deprel in _KERN:
                kern.update(a.subboom(k))
        kern_t = _zonder_rand_interpunctie(a, tuple(sorted(kern)))
        if kern_t and a.aaneengesloten(kern_t) and kern_t != tokens:
            uit.append(_maak(a, "np_kern", t.i, kern_t))
    return uit


def bijzinnen(a: LinguisticAnalysis) -> list[Constituent]:
    """Elke (bij)zin die met een UD-bijzinrelatie aan een hoofd hangt, met zijn voegwoord."""
    if a.gedegradeerd:
        return []
    uit = []
    for t in a.tokens:
        if t.deprel not in _BIJZIN:
            continue
        mark = next((a.tokens[k].tekst.lower() for k in a.kinderen(t.i)
                     if a.tokens[k].deprel == "mark"), "")
        tokens = _zonder_rand_interpunctie(a, a.subboom(t.i))
        if tokens and a.aaneengesloten(tokens):
            uit.append(_maak(a, "bijzin", t.i, tokens, mark))
    return uit


def predicaten(a: LinguisticAnalysis) -> list[Constituent]:
    """Per werkwoordelijk hoofd het hoofd plus zijn hulpwerkwoorden, koppelwerkwoord en partikels.

    Dat is de uitdrukkingswijze van een rechtsbetrekking ("kan verzoeken", "is verplicht"); het
    bereik mag onderbroken zijn in de tekst ("is hij … verschuldigd"), dus `tokens` is de set en
    `start`/`eind` het omvattende bereik.
    """
    if a.gedegradeerd:
        return []
    uit = []
    for t in a.tokens:
        if t.upos not in {"VERB", "AUX", "ADJ"} or t.deprel not in {"root", *_BIJZIN, "conj"}:
            continue
        leden = [t.i] + [k for k in a.kinderen(t.i)
                         if a.tokens[k].deprel in {"aux", "aux:pass", "cop", "compound:prt"}]
        if t.upos == "ADJ" and not any(a.tokens[k].deprel == "cop" for k in leden[1:]):
            continue
        uit.append(_maak(a, "predicaat", t.i, tuple(sorted(leden))))
    return uit


def spanopties(a: LinguisticAnalysis) -> set[tuple[int, int]]:
    """Alle grenzen die de parse aanreikt: elke subboom, elke (kern-)naamwoordgroep, elke bijzin,
    elk aaneengesloten predicaat en elke zin – zonder interpunctie aan de rand.

    Dit is de verzameling waaruit een detector of de classifier een spanoptie kiest (ADR-001 §4:
    het model typt geen tekst, het kiest een optie). Op een gedegradeerde analyse blijven alleen
    de zinnen over.
    """
    uit = {(z.start, z.eind) for z in a.zinnen}
    if a.gedegradeerd:
        return {_zonder_rand(a, s, e) for s, e in uit}
    for t in a.tokens:
        sub = _zonder_rand_interpunctie(a, a.subboom(t.i))
        if sub:
            uit.add(a.bereik(sub))
    for c in (*naamwoordgroepen(a), *bijzinnen(a), *predicaten(a)):
        if a.aaneengesloten(c.tokens):
            uit.add((c.start, c.eind))
    return {_zonder_rand(a, s, e) for s, e in uit}


def _zonder_rand(a: LinguisticAnalysis, start: int, eind: int) -> tuple[int, int]:
    fragment = a.tekst[start:eind]
    return (start + len(fragment) - len(fragment.lstrip(" .,;:\n")),
            eind - (len(fragment) - len(fragment.rstrip(" .,;:\n"))))
