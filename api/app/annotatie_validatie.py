"""Invarianten die de api zélf afdwingt vóór hij een annotatie vastlegt.

**Waarom dit hier hoort en niet alleen in de agent.** Tot 2 sep 2026 valideerde de api bij het
opslaan precies twee dingen: dat de JAS-klasse bestaat en dat het fragment niet leeg is. Al het
overige leunde op de partij die het voorstel aanleverde – graph-qa (grounding) of de werkplek
(`segmenteer`). Dat is een trust boundary op de verkeerde plek: de api is de partij die het
**vastlegt**, en dus de laatste plek waar iets tegengehouden kan worden.

Niet theoretisch. Op 1 sep 2026 stond er live een Operator `"en"` – twee tekens – met een anker van
83 tekens eromheen; de patcher had `tekst` vervangen zonder het anker bij te werken. Omdat
`bron_hash` klopte gebruikte de werkplek die offsets rechtstreeks en lichtte de verkeerde span op.
Dat is in de agent gerepareerd, maar de api nam het klakkeloos aan en zou het morgen weer aannemen.

**Wat hier NIET gebeurt: de juridische interpretatie overdoen.** De api heeft de wettekst niet – die
zit in GraphDB en daar praat de api niet mee – dus of een fragment letterlijk in de bron staat is
hier niet vast te stellen. Dat blijft bij graph-qa. Wat hier kan, is de **interne samenhang** van wat
er binnenkomt: een anker dat zijn eigen fragment niet dekt is kapot, ongeacht welke wet erachter zit.

Twee soorten uitkomst, met opzet verschillend behandeld:

* **Kapot** (`controleer_element`) → verwerpen, meegeteld in de bestaande `X-Verworpen`. Dat is een
  fout in het voorstel zelf.
* **Geschoven** (`bronversies`) → markeren, niet verwerpen. Dat een document over twee
  brontekstversies gaat is meestal geen fout van de indiener maar van de wereld: de importer draait
  wekelijks en overheid.nl verandert. Werk van een jurist weggooien om een hash zou de rekening bij
  de verkeerde partij leggen.
"""

from __future__ import annotations

from typing import Any, Protocol

from .validation import GELDIGE_JAS_KLASSEN


class _MetAnker(Protocol):
    """Wat deze module van een element nodig heeft – `AnnotatieElement` én `ElementInvoer` voldoen."""

    klasse: str
    tekst: str
    lid: str
    anker: Any


def controleer_element(element: _MetAnker) -> str:
    """Geef de reden waarom dit element niet vastgelegd mag worden, of `""` als het in orde is.

    De reden is een korte sleutel (`ongeldige_klasse`, `leeg_fragment`, `anker_dekt_fragment_niet`,
    …) zodat de aanroeper hem in het auditspoor kan zetten; hij is niet bedoeld voor de jurist.
    """
    if element.klasse not in GELDIGE_JAS_KLASSEN:
        return "ongeldige_klasse"
    if not element.tekst.strip():
        return "leeg_fragment"

    anker = element.anker
    if anker is None:
        # Een ONTBREKEND anker is toegestaan, en dat is een bewuste keuze aan de andere kant:
        # `_anker_voor` in de agent geeft None terug als lokaliseren niet lukt, want "een ontbrekend
        # anker is zichtbaar in de werkplek, een fout anker niet". Dat hier alsnog fataal maken zou
        # brongetrouwe tekst weggooien wegens een plaatsbepaling die niet scherp te krijgen was.
        return ""

    start, eind = _int(anker, "start"), _int(anker, "eind")
    if start < 0 or eind <= start:
        return "anker_offsets_ongeldig"

    # DE KERNCONTROLE. Beide ankerbouwers construeren het anker als een slice van de brontekst –
    # `maakAnker` doet `bron.slice(start, eind)` (frontend/lib/selectie.ts) en `_anker_voor` hetzelfde
    # (tools/graph-qa/agent/annotatie.py) – dus de offsets moeten exact het fragment omspannen. Loopt
    # dat uiteen, dan wijst het anker naar iets anders dan het element beweert te zijn, en juist dát
    # is wat de werkplek gebruikt om op te lichten.
    if eind - start != len(element.tekst):
        return "anker_dekt_fragment_niet"

    # Het anker draagt zijn eigen lid; spreekt dat het element tegen, dan is één van beide fout en
    # kunnen we niet weten welke. In de agent zijn dit sinds `_lokaliseer` één beslissing, dus
    # uiteenlopen betekent daar dat er iets tussen zit dat ze los heeft getrokken.
    anker_lid = str(getattr(anker, "lid", "") or "").strip()
    if anker_lid and element.lid.strip() and anker_lid != element.lid.strip():
        return "anker_lid_wijkt_af"

    return ""


def bronversies(elementen: list[Any]) -> list[str]:
    """De verschillende brontekstversies waar de ankers van dit document over gaan, gesorteerd.

    Eén waarde is normaal. Méér betekent dat het document over meerdere versies van de wettekst
    gaat: er is opnieuw geïmporteerd terwijl er al geannoteerd was, of er zijn elementen uit een
    andere bepaling in beland. Dat is niets om te verwerpen, maar wel iets wat de jurist moet zien –
    want de offsets van de oudere elementen wijzen dan naar tekst die verschoven is.

    Elementen zonder anker of zonder hash tellen niet mee: die claimen geen positie, dus ze kunnen
    er ook niet naast zitten.
    """
    gezien: set[str] = set()
    for el in elementen:
        anker = getattr(el, "anker", None)
        if anker is None:
            continue
        h = str(getattr(anker, "bron_hash", "") or "").strip()
        if h:
            gezien.add(h)
    return sorted(gezien)


def _int(anker: Any, veld: str) -> int:
    """Lees een offset als int; een niet-numerieke waarde telt als ongeldig, niet als crash."""
    try:
        return int(getattr(anker, veld, 0) or 0)
    except (TypeError, ValueError):
        return -1
