"""Dekkingsmeting: hoeveel van de brontekst komt er daadwerkelijk in de graaf terecht?

Waarom dit bestaat. "De graaf is volledig" was een oordeel, geen cijfer — en daardoor kon er
anderhalve maand lang tekst ontbreken zonder dat iets afging. Concreet: het XSD staat `<artikel>`
toe als kind van een `circulaire.divisie`, de parser had daar geen tak voor, en elf artikelen van de
Leidraad Invordering 2008 (10.052 tekens) verdwenen stil. Geen fout, geen lege node, geen
waarschuwing — alleen tekst die er niet was.

Deze module legt de brontekst naast wat de importer ervan maakt. Hij draait **offline**: parser →
`build_graph` → tel de `bwb:tekst`-literals, en vergelijk met de `<al>`-tekens in de XML. Geen
GraphDB nodig, dus hij kan in de testsuite en in CI.

**De valkuil bij het meten van de bron.** Een `<al>` kan een `<lijst>` bevatten, en de `<li>`-items
daarin zijn in de graaf eigen `Onderdeel`-nodes. Telt de bronmeting de lijstinhoud mee via de
omhullende `<al>` én nog eens via de `<li>` zelf, dan is de bron kunstmatig groter dan de graaf ooit
kan zijn. Dat suggereerde bij de eerste meting een gat van 3–13% bij álle regelingen, terwijl er
alleen bij de Leidraad echt iets miste. Vandaar `_tekst_zonder` hieronder: de container wordt
overgeslagen waar zijn inhoud elders al geteld wordt.

`opmerkingen-inhoud` (redactionele opmerkingen) en `meta-data` horen niet bij de wettekst en tellen
aan beide kanten niet mee.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

# Containers waarvan de inhoud in de graaf een eigen node wordt (of er helemaal niet in hoort).
# Ze worden bij het meten van een `<al>` overgeslagen, zodat niets dubbel telt.
_NIET_MEETELLEN = ("lijst", "table", "meta-data", "opmerkingen-inhoud", "noot")

_WS = re.compile(r"\s+")

# Ondergrens waaronder een import als onvolledig geldt. Eén bron: `Settings.min_dekking` neemt hem
# als default en de tests toetsen ertegen.
#
# Waarom 0,995 en niet 1,0. Gemeten verhouding graaf/bron op de toestanden van november 2026, mét
# bijlagen in de bronmeting: Awr 1,00002 · Uitv.reg. IW 1,00012 · IW 1,00003 · Awir 1,00000 ·
# Uitv.reg. Awir 1,00003 · Leidraad 1,00013 · Awb 1,00125. De krapste marge is nul, dus een halve
# procent speling is geen luxe. Ter ijking: de Leidraad stond op 98,4% toen er elf artikelen
# ontbraken, en de Awb op 81,6% toen Bijlage 2 ontbrak (66.086 tekens).
STANDAARD_DREMPEL = 0.995


@dataclass(frozen=True)
class Dekking:
    """Wat de bron biedt, wat de importer eruit haalt, en het verschil."""

    bwb_id: str
    bron_tekens: int
    graaf_tekens: int

    @property
    def verhouding(self) -> float:
        """Graaf gedeeld door bron. 1.0 = alles; een klein overschot komt van de tekstopbouw per node."""
        if self.bron_tekens <= 0:
            return 1.0
        return self.graaf_tekens / self.bron_tekens

    @property
    def ontbrekend(self) -> int:
        """Tekens die de bron wél heeft en de graaf niet (nooit negatief)."""
        return max(0, self.bron_tekens - self.graaf_tekens)

    def regel(self) -> str:
        return (
            f"{self.bwb_id}: bron {self.bron_tekens} · graaf {self.graaf_tekens} · "
            f"dekking {self.verhouding:.1%}"
            + (f" · MIST {self.ontbrekend}" if self.ontbrekend else "")
        )


def _tekst_zonder(element: etree._Element) -> str:
    """Tekst van dit element, zonder de containers waarvan de inhoud elders geteld wordt."""
    delen: list[str] = []

    def loop(node: etree._Element) -> None:
        if node.tag in _NIET_MEETELLEN:
            return
        if node.text:
            delen.append(node.text)
        for kind in node:
            loop(kind)
            if kind.tail:
                delen.append(kind.tail)

    loop(element)
    return _WS.sub(" ", "".join(delen)).strip()


def bron_tekens(xml_pad: str | Path) -> int:
    """Tekstomvang van de wettekst in de bron-XML, zoals de importer hem hoort over te nemen.

    Bijlagen horen erbij. Ze staan náást de wettekst, en zolang de meting dat volgde kon Bijlage 2
    van de Awb (66.086 tekens) ontbreken terwijl de dekking op 104% stond. Eén xpath over de
    alinea's, zodat een alinea hoogstens één keer telt, hoe de containers ook genest zijn.
    """
    wortel = etree.parse(str(xml_pad)).getroot()
    alineas = wortel.xpath(
        "//al[(ancestor::wettekst or ancestor::regeling-tekst or ancestor::circulaire-tekst"
        " or ancestor::bijlage) and not(ancestor::opmerkingen-inhoud) and not(ancestor::meta-data)]"
    )
    return sum(len(_tekst_zonder(alinea)) for alinea in alineas)


@dataclass(frozen=True)
class Stand:
    """Wat er nu van een regeling in de graaf staat. Nul tekens = er staat niets."""

    tekens: int = 0
    wti: bool = False


@dataclass(frozen=True)
class Poortbesluit:
    """Mag deze graph de bestaande vervangen, en is er iets te melden? `reden` leeg = niets."""

    schrijven: bool
    reden: str | None = None


def poortbesluit(
    dekking: Dekking,
    stand: Stand,
    *,
    drempel: float,
    wti_mislukt: bool = False,
    overgeslagen: Sequence[str] = (),
) -> Poortbesluit:
    """Beslis vóór de PUT, want een named-graph PUT vervangt alles en een controle erna is te laat.

    De regel is **vervang nooit door minder**, en niet "bij een dip niet schrijven". GraphDB komt na
    een herstart leeg op; zou een dip dan de PUT tegenhouden, dan ontbreekt de hele regeling in
    plaats van een deel ervan. Tegen een lege graaf wint alles, behalve niets: een toestand zonder
    tekst is geen regeling en valt buiten dit besluit (`LegeToestand` in `app/main.py`).

    Een mislukte WTI vervangt geen verrijkte graph door een kale. Citeertitels en rechtsgebieden
    staan in dezelfde named graph, dus ze verdwijnen stil mee.

    Een mislukte bronmeting (`bron_tekens == 0`) is geen bewijs van een gat, maar ook geen bewijs
    van het tegendeel: dan telt alleen dat er niet minder mag komen te staan. `drempel == 0` zet
    alleen de dipregel uit.

    Structuur die de parser oversloeg weegt als een dip, ook bij volle dekking: de speling van de
    drempel is groot genoeg om een heel artikel te verbergen.
    """
    tekort = drempel > 0 and dekking.bron_tekens > 0 and dekking.verhouding < drempel
    onmeetbaar = dekking.bron_tekens <= 0
    probleem = dekking.regel()
    if overgeslagen:
        probleem = f"{probleem}; onbekende structuur overgeslagen: {', '.join(overgeslagen)}"
    if (tekort or onmeetbaar or overgeslagen) and dekking.graaf_tekens < stand.tekens:
        return Poortbesluit(
            False, f"{probleem}; de bestaande graph ({stand.tekens} tekens) blijft staan"
        )
    if wti_mislukt and stand.wti:
        return Poortbesluit(False, "WTI mislukt; de bestaande verrijkte graph blijft staan")
    if tekort or overgeslagen:
        return Poortbesluit(True, f"{probleem}; geschreven, er staat niets beters")
    if wti_mislukt:
        return Poortbesluit(True, "WTI mislukt; geschreven zonder verrijking")
    return Poortbesluit(True)


def meet(xml_pad: str | Path, geldig_vanaf: str | None = None) -> Dekking:
    """Parse en schrijf de wet offline, en leg het resultaat naast de bron.

    Importeert `parser`/`graphdb_writer` binnenin om een importcyclus te vermijden en om deze module
    bruikbaar te houden als alleen `bron_tekens` nodig is.
    """
    from .graphdb_writer import GraphDbWriter
    from .parser import ToestandParser
    from .rdf_vocab import Vocab

    vocab = Vocab()
    wet = ToestandParser().parse(str(xml_pad))
    if geldig_vanaf:
        wet.geldig_vanaf = geldig_vanaf
    graaf, _ = GraphDbWriter(url="offline", repository="offline", vocab=vocab).build_graph(wet)
    graaf_tekens = sum(len(str(o)) for o in graaf.objects(None, vocab.ns.tekst))
    return Dekking(bwb_id=wet.bwb_id, bron_tekens=bron_tekens(xml_pad), graaf_tekens=graaf_tekens)


