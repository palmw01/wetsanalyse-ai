"""Welke bepaling wijst een annotatievraag aan – deterministisch, zonder model.

Eén annotatievraag gaat over **één artikel** (of één beleidsregel, zoals Leidraad 9). Binnen dat
artikel mag de jurist meerdere leden noemen ("artikel 9 lid 1 en 3", "9.1 en 9.5"); die staan dan
vooraf aangevinkt op de keuzekaart. Meer artikelen in één vraag ("artikel 8 en 9") is het afbakenen
van een werkgebied – een andere functie – en wordt afgewezen met het verzoek de vraag per artikel
te stellen.

Dit leest alleen wat er letterlijk staat. Het bepaalt nooit zelf de bron: dat doet de graaf. Het
kan wel met zekerheid zeggen dat er meer dan één artikel genoemd wordt, en dat hoort niet van de
ophaal-agent af te hangen – die haalt er anders twee op en annoteert stil de laatste.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_NUM = r"\d+[a-z]{0,3}(?:[:.]\d+[a-z]{0,3})*"
_SCHEIDER = r"\s*(?:,|en|of|t/m|tot en met|-|–)\s*"
_LIJST = rf"{_NUM}(?:{_SCHEIDER}(?:art(?:ikel(?:en)?)?\.?\s*)?{_NUM})*"
# "artikel 9", "artikelen 8 en 9", "art. 9", "artt. 8-10". Niet na een woord (b.v. "startartikel").
_ARTIKEL = re.compile(rf"(?<![\w])(?:artikelen|artikel|artt\.|art\.?)\s*({_LIJST})", re.IGNORECASE)
_LEDEN = re.compile(rf"(?<![\w])(?:leden|lid)\s+({_NUM}(?:{_SCHEIDER}(?:lid\s+)?{_NUM})*)", re.IGNORECASE)
_RANGTELWOORDEN = ("eerste", "tweede", "derde", "vierde", "vijfde", "zesde", "zevende", "achtste",
                   "negende", "tiende", "elfde", "twaalfde", "dertiende", "veertiende", "vijftiende",
                   "zestiende", "zeventiende", "achttiende", "negentiende", "twintigste")
_RANG = "|".join(_RANGTELWOORDEN)
_RANG_LEDEN = re.compile(rf"(?<![\w])((?:{_RANG})(?:{_SCHEIDER}(?:{_RANG}))*)\s+(?:lid|leden)\b", re.IGNORECASE)
_BEREIK = re.compile(r"\s*(?:t/m|tot en met|-|–)\s*")


@dataclass(frozen=True)
class Aanwijzing:
    """`artikelen`: de genoemde artikelen (bij een decimaal nummer de stam: 9.1 → 9), in volgorde.
    `leden`: de genoemde leden of subnummers binnen dat ene artikel (9.5 → "5")."""

    artikelen: tuple[str, ...] = ()
    leden: tuple[str, ...] = field(default_factory=tuple)

    @property
    def meerdere_artikelen(self) -> bool:
        return len(self.artikelen) > 1


def _items(lijst: str) -> list[str]:
    """"8, 9 en 10" → [8, 9, 10]; "8 t/m 10" → [8, 9, 10]; "9.1 t/m 9.3" → [9.1, 9.2, 9.3]."""
    delen = re.split(rf"({_SCHEIDER})", lijst)
    uit: list[str] = []
    for i in range(0, len(delen), 2):
        nummer = re.sub(r"^(?:art(?:ikel(?:en)?)?\.?|lid)\s*", "", delen[i].strip(), flags=re.IGNORECASE)
        vorige = delen[i - 1] if i else ""
        if uit and _BEREIK.fullmatch(vorige):
            uit.extend(_bereik(uit[-1], nummer))
        else:
            uit.append(nummer)
    return [x.lower() for x in uit if x]


def _bereik(van: str, tot: str) -> list[str]:
    """De tussenliggende nummers van een bereik, alleen als dat ondubbelzinnig kan (zelfde stam,
    kale getallen). Anders alleen het eindpunt: dat is genoeg om te zien of het één artikel is."""
    stam_van, _, eind_van = van.rpartition(".")
    stam_tot, _, eind_tot = tot.rpartition(".")
    if stam_van == stam_tot and eind_van.isdigit() and eind_tot.isdigit() and int(eind_van) < int(eind_tot) <= int(eind_van) + 60:
        pre = f"{stam_van}." if stam_van else ""
        return [f"{pre}{n}" for n in range(int(eind_van) + 1, int(eind_tot) + 1)]
    return [tot]


def _stam(nummer: str) -> str:
    """9.1 → 9 (een Leidraad-subbepaling hoort bij artikel 9); 3:40 blijft 3:40 (Awb-nummering)."""
    return nummer.split(".", 1)[0]


def lees_aanwijzing(vraag: str) -> Aanwijzing:
    artikelen: list[str] = []
    leden: list[str] = []
    for match in _ARTIKEL.finditer(vraag):
        for nummer in _items(match.group(1)):
            if _stam(nummer) not in artikelen:
                artikelen.append(_stam(nummer))
            if "." in nummer:
                leden.append(nummer.split(".", 1)[1])
    for match in _LEDEN.finditer(vraag):
        leden.extend(_items(match.group(1)))
    for match in _RANG_LEDEN.finditer(vraag):
        woorden = re.split(_SCHEIDER, match.group(1).lower())
        leden.extend(str(_RANGTELWOORDEN.index(w) + 1) for w in woorden if w in _RANGTELWOORDEN)
    uniek = tuple(dict.fromkeys(leden))
    return Aanwijzing(artikelen=tuple(artikelen), leden=uniek if len(artikelen) <= 1 else ())


MELDING_MEERDERE = (
    "Je noemt meer dan één artikel ({artikelen}). Ik annoteer per vraag één artikel, zodat elke "
    "annotatie een eigen laag en beoordeling krijgt. Stel de vraag opnieuw voor één artikel – "
    "binnen dat artikel kun je daarna zelf de leden kiezen."
)


def melding_meerdere(artikelen: tuple[str, ...] | list[str]) -> str:
    namen = [f"artikel {a}" for a in artikelen]
    opsomming = namen[0] if len(namen) == 1 else ", ".join(namen[:-1]) + " en " + namen[-1]
    return MELDING_MEERDERE.format(artikelen=opsomming)
