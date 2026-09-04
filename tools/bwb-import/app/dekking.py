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
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

# Containers waarvan de inhoud in de graaf een eigen node wordt (of er helemaal niet in hoort).
# Ze worden bij het meten van een `<al>` overgeslagen, zodat niets dubbel telt.
_NIET_MEETELLEN = ("lijst", "table", "meta-data", "opmerkingen-inhoud", "noot")

_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class Dekking:
    """Wat de bron biedt, wat de importer eruit haalt, en het verschil."""

    bwb_id: str
    bron_tekens: int
    graaf_tekens: int

    @property
    def verhouding(self) -> float:
        """Graaf gedeeld door bron. 1.0 = alles; >1.0 mag (bijlagen tellen in de bronmeting niet mee)."""
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
    """Tekstomvang van de wettekst in de bron-XML, zoals de importer hem hoort over te nemen."""
    wortel = etree.parse(str(xml_pad)).getroot()
    totaal = 0
    for lichaam in wortel.xpath("//wettekst | //regeling-tekst | //circulaire-tekst"):
        for alinea in lichaam.xpath(".//al"):
            if any(voorouder.tag == "opmerkingen-inhoud" for voorouder in alinea.iterancestors()):
                continue
            totaal += len(_tekst_zonder(alinea))
    return totaal


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


def meet_map(map_pad: str | Path) -> list[Dekking]:
    """Meet elke gecachte toestand-XML onder `map_pad` (één per BWB-map)."""
    uit: list[Dekking] = []
    for regeling in sorted(Path(map_pad).iterdir()):
        if not regeling.is_dir():
            continue
        toestanden = [
            p for p in sorted(regeling.glob("*.xml"))
            if "wti" not in p.name.lower() and "manifest" not in p.name.lower()
        ]
        if toestanden:
            uit.append(meet(toestanden[0]))
    return uit
