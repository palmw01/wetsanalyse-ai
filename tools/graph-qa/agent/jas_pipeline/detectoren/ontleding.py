"""Gedeelde ontledingshulp voor detectoren die een parse nodig hebben.

Geen detectie hier: alleen toegang tot de parse, verwijzingsmaskers en brongetrouwe grenzen.
"""
from __future__ import annotations

from ..taal import LinguisticAnalysis
from . import BronTekst
from .regels import maskers


def parse_of_reden(bron: BronTekst) -> tuple[LinguisticAnalysis | None, str]:
    if bron.analyse is None:
        return None, "geen taalanalyse aangeleverd"
    if bron.analyse.gedegradeerd:
        return None, f"geen parse: {bron.analyse.fout}"
    return bron.analyse, ""


def in_verwijzing(bron: BronTekst, s: int, e: int) -> bool:
    return any(ms <= s and e <= me for ms, me in maskers(bron.tekst).get("verwijzing", []))


def bereik(a: LinguisticAnalysis, tokens) -> tuple[int, int] | None:
    tokens = [i for i in tokens if a.tokens[i].upos != "PUNCT"]
    if not tokens or not a.aaneengesloten(tuple(tokens)):
        return None
    return a.bereik(tokens)


_RANDFUNCTIE = {"case", "cc", "mark", "punct"}

#: De zinsdelen van een naamwoordelijk gezegde: is een zelfstandig naamwoord de kern van een zin ('In afwijking van het
#: eerste lid is een voorlopige aanslag waarvan …'), dan hangen het koppelwerkwoord, het onderwerp en de bepalingen aan
#: dat naamwoord. Ze horen niet bij de groep (Termijnen, 19 nov 2026: art. 9 lid 7 IW).
ZINSFUNCTIE = frozenset({"cop", "aux", "aux:pass", "nsubj", "nsubj:pass", "csubj", "obl", "obl:agent", "advcl", "expl"})


def zinsdelen(a: LinguisticAnalysis, kop: int) -> set[int]:
    """De tokens van de zinsdelen die aan naamwoord `kop` hangen omdat het een naamwoordelijk gezegde is."""
    if not any(a.tokens[k].deprel == "cop" for k in a.kinderen(kop)):
        return set()
    return {i for k in a.kinderen(kop) if a.tokens[k].deprel in ZINSFUNCTIE for i in a.subboom(k)}


def zonder_randfunctie(a: LinguisticAnalysis, tokens, kop: int) -> list[int]:
    """Een voorzetsel, voegwoord of leesteken vóór de groep hoort er niet bij ('Voor een partner')."""
    tokens = sorted(tokens)
    while tokens and tokens[0] != kop and a.tokens[tokens[0]].deprel in _RANDFUNCTIE:
        tokens.pop(0)
    return tokens
