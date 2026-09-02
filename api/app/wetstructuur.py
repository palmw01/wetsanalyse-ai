"""Structuur herkennen in één regel wettekst, voor de PDF-export.

`artikel._vouw_onderdelen_in` (graph-qa) bouwt het corpus op als één regel per onderdeel, in de vorm
`"{nummer} {tekst}"`, met de lidtekst als eerste regel. In de PDF ging elk lid tot 2 sep 2026 als
één reportlab-`Paragraph` naar buiten — en die vouwt witruimte samen, dus de `\\n` tussen de
onderdelen verdween en a./b./c. plakten aan elkaar als lopende tekst. Erger dan in de webapp, waar
`whitespace-pre-wrap` de regeleindes tenminste nog liet staan.

**Het niveau is afgeleid, geen waarheid.** De echte nesting zit in de graaf (`heeftOnderdeel+` met
`?ouder`) maar reist niet mee naar de export: de werkplek stuurt de leden als platte tekst mee in de
body. Het niveau wordt hier dus uit de vórm van het nummer gelezen. Bij een regeling waar `1°.` wél
op het hoogste niveau staat, springt het ten onrechte in — een scheve marge, en verder niets: de
tekst zelf verandert geen teken.

Deze parser bestaat twee keer: hier voor de PDF, en in `frontend/lib/wetstructuur.ts` voor het
documentpaneel. `frontend/lib/wetstructuur.vectoren.json` bewaakt dat beide kanten hetzelfde blijven
doen; zonder die guard staat een onderdeel in de PDF op een andere marge dan in de werkplek en gaat
de jurist twijfelen aan de bron in plaats van aan de opmaak. Zelfde patroon als
`bronHash.vectoren.json`, dat er kwam nadat Python en JS uiteenliepen op niet-ASCII.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Opsommingstekens die als onderdeelnummer gelden. Alleen aan het BEGIN van een regel — een en-dash
#: komt ook midden in een zin voor als gedachtestreepje ("…opheldering niet – of niet volledig…"),
#: en dat is geen opsomming.
STREEPJES = ("–", "—", "•")

#: `a.` `b.` `aa.` `1.` `12.` – een letter- of cijfergroep met een punt erachter.
_NUMMER = re.compile(r"^([a-z]{1,3}|\d{1,3})\.(?=\s|$)")

#: `1°.` `2°` – graden, in de BWB-conventie een niveau dieper dan de letters eromheen.
_GRADEN = re.compile(r"^(\d{1,3}°)\.?(?=\s|$)")

#: Een gedefinieerd begrip is kort ("de BES eilanden"); een volzin die toevallig een dubbele punt
#: bevat is dat niet. Vier woorden pakt de definities in art. 2 IW 1990 wél en de volzinnen niet.
MAX_TERM_WOORDEN = 4


@dataclass(frozen=True)
class Onderdeel:
    """Wat één regel wettekst blijkt te zijn."""

    nummer: str = ""   # zoals het in de wet staat, inclusief punt ("a.", "1°.", "–")
    term: str = ""     # de gedefinieerde term vóór de dubbele punt, alleen vlak ná een nummer
    tekst: str = ""    # de rest van de regel
    niveau: int = 0    # 0 = aanhef/lopende tekst, 1 = letter- of streepje-onderdeel, 2 = genest


def ontleed(regel: str) -> Onderdeel:
    """Ontleed één regel van de brontekst.

    De regel gaat er ongeschonden weer uit: `nummer + term + tekst` bevat elk teken dat er stond, op
    de scheidende spaties en de dubbele punt na. Dat is geen finesse maar de eis waaronder deze
    functie mag bestaan — de weergave verplaatst tekst, ze verandert hem niet.
    """
    kaal = regel.lstrip()
    if not kaal:
        return Onderdeel()

    # 1. Graden eerst: `1°.` mag niet als het gewone `1.` worden gelezen, want dan valt het
    #    nestingniveau weg — dezelfde reden waarom `_onderdeel_nummer` in de agent de `°` laat staan.
    if (graden := _GRADEN.match(kaal)):
        return _met_term(kaal[graden.end():], graden.group(0), 2)

    # 2. Een streepje als opsommingsteken (Leidraad). Alleen aan het begin, en er moet iets achter
    #    staan — een losse dash is geen onderdeel.
    for streep in STREEPJES:
        if kaal.startswith(streep) and kaal[len(streep):].lstrip():
            return _met_term(kaal[len(streep):], streep, 1)

    # 3. Letters en cijfers met een punt. De lookahead eist witruimte of regeleinde erachter, zodat
    #    "art.2" en "nr.3" niet als onderdeel tellen.
    if (nummer := _NUMMER.match(kaal)):
        return _met_term(kaal[nummer.end():], nummer.group(0), 1)

    return Onderdeel(tekst=regel.strip())


def _met_term(rest: str, nummer: str, niveau: int) -> Onderdeel:
    """De definitieterm afsplitsen: alleen vlak ná een nummer, en alleen als hij kort genoeg is.

    Een dubbele punt staat ook in gewone volzinnen ("…voor de loonbelasting: ieder van de
    bestuurders"), dus zonder grens zou de halve bepaling vet worden.
    """
    tekst = rest.strip()
    punt = tekst.find(":")
    if punt > 0:
        kandidaat = tekst[:punt].strip()
        if kandidaat and len(kandidaat.split()) <= MAX_TERM_WOORDEN:
            return Onderdeel(nummer=nummer, term=kandidaat, tekst=tekst[punt + 1:].strip(), niveau=niveau)
    return Onderdeel(nummer=nummer, tekst=tekst, niveau=niveau)
