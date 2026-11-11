"""Parser voor de BWB toestand-XML (lxml), met optionele XSD-validatie.

Gebouwd op de geverifieerde structuur:
``toestand -> wetgeving -> wet-besluit -> wettekst ->
hoofdstuk/afdeling/paragraaf -> artikel -> lid -> al``.

De structurele opbouw verloopt via een generieke recursie zodat wisselende
nesting (afdeling in hoofdstuk, paragraaf in afdeling, ...) en latere
uitbreiding naar andere regelingsoorten werken zonder modelwijziging.
"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path
from typing import Any

from lxml import etree

from .models import (
    Artikel,
    Bijlage,
    Divisie,
    Illustratie,
    Lid,
    Onderdeel,
    Ondertekenaar,
    Structuurdeel,
    Verwijzing,
    Wet,
)
from .references import extract_references

logger = logging.getLogger(__name__)

# Tags die als structuurdeel worden behandeld (label = structuur-soort).
_STRUCTUUR_TAGS = {
    "hoofdstuk": "hoofdstuk",
    "titeldeel": "titeldeel",
    "afdeling": "afdeling",
    "paragraaf": "paragraaf",
    # Een paragraaf binnen een paragraaf (Boek 7 BW, titel 7.10). Geen eigen soort in de graaf: een geneste paragraaf. De
    # IRI van een artikel verandert er niet door (die noemt alleen het artikel).
    "sub-paragraaf": "paragraaf",
}


# Kinderen die geen eigen structuur dragen: wat een container hier niet kent, wordt gemeld
# (`_meld_onbekend`). Stil overslaan is hoe Bijlage 2 van de Awb (66.086 tekens) en elf artikelen van
# de Leidraad verdwenen.
_GEEN_STRUCTUUR = frozenset({"kop", "meta-data", "officiele-inhoudsopgave"})
# Een bijlage is ook tekstdrager: deze kinderen leest `_bijlage_tekst` of `_parse_onderdelen`.
_BIJLAGE_TEKST = _GEEN_STRUCTUUR | {
    "al", "al-groep", "lijst", "table", "plaatje", "tussenkop", "wetcitaat", "model",
    "bijlage-sluiting",
}


# Kondigt een lid/artikel een begrippenlijst aan? "Deze wet verstaat onder:", "Deze wet verstaat
# MEDE onder:" (art. 2 lid 2 IW 1990 – een echte definitiegroep, dus die moet erin), "waar wordt
# verstaan onder". Zie `ToestandParser._definities` voor waarom dit een harde eis is.
_DEFINITIE_AANHEF = re.compile(
    r"\bverstaa[tn]\b[^:]{0,40}\bonder\b|\bwordt\s+verstaan\b", re.IGNORECASE
)
# De vorm `term: definitie` binnen zo'n lijst. De term is kort en draagt zelf geen zinsafsluitend
# leesteken; dat weert opsommingen die toevallig een dubbele punt bevatten.
_DEFINITIE_TERM = re.compile(r"^([^:;.]{2,60}):\s+\S")

# De vorm `Onder X wordt verstaan` (Awb 1:2), alleen aan het begin van de tekst: midden in een lid is het
# vaak een aanvulling op iets anders. "niet verstaan" sluit uit en definieert dus niet; "bedoeld in …"
# hoort niet bij de term.
_ONDER_TERM = re.compile(r"^Onder\s+(?:(?:de|het|een)\s+)?([^,:;.]{2,60}?)"
                         r"(?:,?\s+(?:als\s+)?bedoeld\s+in\b[^:;]*?,?)?"
                         r"\s+(?:wordt|worden)\s+(?:(?:mede|ook|tevens)\s+)?verstaan\b")

# Een `<al>` ná een `<lijst>` in hetzelfde element is geen tekst van de aanhef: hij wordt een eigen
# slottekst-node (zie `ToestandParser._parse_onderdelen`). De ouders zijn precies de elementen
# waarvan die methode de lijsten leest; een `<lijst>` in iets anders heeft geen onderdelen en dan
# blijft de alinea bij zijn ouder staan, zodat er nooit tekst tussen wal en schip valt.
_SLOT_AL = (
    "al[preceding-sibling::lijst]"
    "[parent::lid or parent::li or parent::artikel or parent::tekst or parent::bijlage]"
)
# Als XPath-voorwaarde: dit element is geen slottekst en staat er ook niet in.
_GEEN_SLOT = f" and not(ancestor-or-self::{_SLOT_AL})"


class ParseError(RuntimeError):
    """De XML kon niet als geldige toestand worden geïnterpreteerd."""


class ToestandParser:
    """Zet een toestand-XML om naar het :class:`~bronmodel.bwb.models.Wet`-model."""

    def __init__(self, schema_path: Path | None = None) -> None:
        self._schema_path = schema_path
        self._overgeslagen: list[str] = []
        self._schema: etree.XMLSchema | None = None

    # ------------------------------------------------------------- validatie
    def validate(self, xml_path: Path | bytes) -> bool:
        """Valideer tegen het XSD. Niet-blokkerend: faalt zacht met waarschuwing.

        Geeft ``True`` bij geldig, ``False`` bij ongeldig of als het schema niet
        beschikbaar is. Neemt een pad (de importer) of de XML zelf (de connector, die niets op schijf zet).
        """
        naam = _naam(xml_path)
        if self._schema_path is None:
            logger.warning("Geen XSD opgegeven; validatie overgeslagen")
            return False
        try:
            schema = self._load_schema()
            doc = etree.parse(_bron(xml_path))
            schema.assertValid(doc)
            logger.info("XSD-validatie geslaagd voor %s", naam)
            return True
        except etree.DocumentInvalid as exc:
            logger.warning("XSD-validatie mislukt voor %s: %s", naam, exc)
            return False
        except (etree.XMLSchemaParseError, OSError) as exc:
            logger.warning("XSD kon niet worden geladen (%s); validatie overgeslagen", exc)
            return False

    def _load_schema(self) -> etree.XMLSchema:
        if self._schema is None:
            assert self._schema_path is not None
            self._schema = etree.XMLSchema(etree.parse(str(self._schema_path)))
        return self._schema

    # ----------------------------------------------------------------- parse
    def parse(self, xml_path: Path | bytes) -> Wet:
        """Parse de toestand-XML (een pad of de XML zelf) naar een :class:`Wet`."""
        tree = etree.parse(_bron(xml_path))
        root = tree.getroot()
        if root.tag != "toestand":
            raise ParseError(f"Onverwacht root-element: {root.tag!r} (verwacht 'toestand')")

        bwb_id = root.get("bwb-id") or ""
        wetgeving = root.find("wetgeving")
        if wetgeving is None:
            raise ParseError("Geen <wetgeving>-element gevonden")

        wet = Wet(
            bwb_id=bwb_id,
            citeertitel=self._tekst(wetgeving.find("citeertitel")),
            opschrift=self._tekst(wetgeving.find("intitule")),
            soort=wetgeving.get("soort", ""),
            geldig_vanaf=root.get("inwerkingtreding"),
            geldig_tot=None,
            label_id=wetgeving.get("label-id"),
            vast_deel_url=root.get("bwb-ng-vast-deel"),
            **self._wet_aanhef(wetgeving),
            **self._wet_brondata(wetgeving),
        )
        self._overgeslagen = wet.overgeslagen

        # Ministeriële regelingen dragen dezelfde bouwstenen als een
        # wettekst, maar onder <regeling>/<regeling-tekst>.
        wettekst = wetgeving.find("wet-besluit/wettekst")
        if wettekst is None:
            wettekst = wetgeving.find("regeling/regeling-tekst")
        if wettekst is not None:
            self._lees_kinderen(wettekst, bwb_id, wet.structuurdelen, wet.losse_artikelen)
            # Bijlagen staan náást de wettekst: kind van <wet-besluit>/<regeling>.
            houder = wettekst.getparent()
            if houder is not None:
                for bijlage in houder.iterfind("bijlage"):
                    wet.bijlagen.append(self._parse_bijlage(bijlage, bwb_id))
        else:
            # Circulaires/beleidsregels dragen geen wettekst maar een
            # recursieve <circulaire.divisie>-boom.
            circulaire = wetgeving.find("circulaire/circulaire-tekst")
            if circulaire is not None:
                for child in circulaire:
                    tag = child.tag if isinstance(child.tag, str) else ""
                    if tag == "circulaire.divisie":
                        wet.divisies.append(self._parse_divisie(child, bwb_id))
                    elif tag == "artikel":
                        wet.losse_artikelen.append(self._parse_artikel(child, bwb_id))
                    elif tag and tag not in _GEEN_STRUCTUUR:
                        self._meld_onbekend(circulaire, tag)
                # Het XSD staat ook een bijlage bij een circulaire toe.
                for bijlage in circulaire.getparent().iterfind("bijlage"):
                    wet.bijlagen.append(self._parse_bijlage(bijlage, bwb_id))
            else:
                logger.warning(
                    "Geen <wettekst>, <regeling-tekst> of <circulaire> gevonden voor %s",
                    bwb_id,
                )
                return wet

        wet.ondertekenaars = self._parse_ondertekenaars(wetgeving)

        logger.info(
            "Parse klaar voor %s: %d structuurdelen, %d losse artikelen, %d divisies, "
            "%d bijlagen, %d ondertekenaars",
            bwb_id,
            len(wet.structuurdelen),
            len(wet.losse_artikelen),
            len(wet.divisies),
            len(wet.bijlagen),
            len(wet.ondertekenaars),
        )
        return wet

    # ------------------------------------------------------------- structuur
    def _meld_onbekend(self, houder: etree._Element, tag: str) -> None:
        """Noteer structuur die de parser niet leest. De importpoort behandelt dat als een dip.

        Geen ParseError: dan ontbreekt de hele wet op een lege graaf. Geen stil overslaan: de dekking
        heeft een halve procent speling, en dat is bij de Awb ruim 1.800 tekens, een heel artikel.
        """
        melding = f"{houder.tag}/{tag}"
        if melding not in self._overgeslagen:
            logger.warning("Onbekende structuur overgeslagen: %s", melding)
            self._overgeslagen.append(melding)

    def _structuursoort(self, element: etree._Element) -> str | None:
        """De structuursoort van een element. Een ``<divisie>`` in een bijlage noemt die in zijn kop."""
        if element.tag == "divisie":
            kop = element.find("kop")
            label = self._tekst(kop.find("label")).lower() if kop is not None else ""
            return _STRUCTUUR_TAGS.get(label)
        return _STRUCTUUR_TAGS.get(element.tag)

    def _lees_kinderen(
        self,
        element: etree._Element,
        bwb_id: str,
        delen: list[Structuurdeel],
        artikelen: list[Artikel],
        tekst: frozenset[str] = _GEEN_STRUCTUUR,
        divisies: list[Divisie] | None = None,
    ) -> None:
        """De kinderen van een container, in documentvolgorde. Eén lus voor elke container. Een structuurdeel geeft
        `divisies` mee voor een ``<structuurtekst>`` (`_parse_structuurtekst`)."""
        for child in element:
            tag = child.tag if isinstance(child.tag, str) else ""
            if not tag:
                continue
            if tag == "artikel":
                artikelen.append(self._parse_artikel(child, bwb_id))
            elif tag == "boek" and element.tag == "wettekst":
                # Een boek van het Burgerlijk Wetboek is een eigen regeling (Boek 7 is BWBR0005290), en zijn wettekst is
                # precies één `<boek>`. Het is dus geen deel binnen de regeling maar de regeling zelf: zijn titeldelen
                # horen er direct onder. De jci noemt het boek, maar een vindplaats rekent het niet mee
                # (`bronmodel.vindplaats`: alleen hoofdstuk, titeldeel, afdeling en paragraaf), dus de IRI verandert
                # niet. Zonder deze tak viel de hele tekst als "onbekende structuur" weg.
                self._lees_kinderen(child, bwb_id, delen, artikelen, tekst)
            elif self._structuursoort(child):
                delen.append(self._parse_structuurdeel(child, bwb_id))
            elif tag == "structuurtekst" and divisies is not None:
                divisies.append(self._parse_structuurtekst(child, element, bwb_id))
            elif tag not in tekst:
                self._meld_onbekend(element, tag)

    def _parse_structuurdeel(self, element: etree._Element, bwb_id: str) -> Structuurdeel:
        kop = element.find("kop")
        deel = Structuurdeel(
            id=self._knoop_id(bwb_id, element),
            soort=self._structuursoort(element) or "",
            nummer=self._tekst(kop.find("nr")) if kop is not None else "",
            label=self._tekst(kop.find("label")) if kop is not None else "",
            titel=self._tekst(kop.find("titel")) if kop is not None else "",
            jci=self._element_jci(element),
            label_id=element.get("label-id"),
        )
        self._lees_kinderen(element, bwb_id, deel.subdelen, deel.artikelen, divisies=deel.divisies)
        return deel

    def _parse_structuurtekst(self, element: etree._Element, ouder: etree._Element, bwb_id: str) -> Divisie:
        """Een ``<structuurtekst>``: de tekst van een paragraaf zonder artikelen (beleidsregels als het BBBB). Een
        divisie met het nummer, label en de titel van de paragraaf, en eigen alinea's en onderdelen (de genummerde
        punten). Zonder deze tak viel de hele tekst weg als onbekende structuur (iteratie wetgeving_live, I12: dekking
        0%). De jci is die van het element zelf; die van de paragraaf zou de divisie op de IRI van de paragraaf zetten."""
        kop = ouder.find("kop")
        excl = f" and not(ancestor::li){_GEEN_SLOT}"
        return Divisie(
            id=self._knoop_id(bwb_id, element),
            nummer=self._tekst(kop.find("nr")) if kop is not None else "",
            label=ouder.get("label", ""),
            titel=self._tekst(kop.find("titel")) if kop is not None else "",
            tekst=_tekst_in(element, ".//", "not(ancestor::li)"),
            jci=self._element_jci(element),
            inwerking=element.get("inwerking"),
            bron=element.get("bron"),
            effect=element.get("effect"),
            status=element.get("status"),
            terugwerkend_tot=self._terugwerkend(element),
            wijzigingsbronnen=self._wijzigingsbronnen(element),
            **self._bronverwijzingen(element),
            verwijzingen=self._verwijzingen_scope(element, bwb_id, base=".//*", extra_excl=excl),
            onderdelen=self._parse_onderdelen(element, bwb_id),
            voetnoten=[self._noot_tekst(noot) for noot in element.xpath(f".//noot[not(ancestor::li){_GEEN_SLOT}]")],
            illustraties=self._illustraties(element, base=".//illustratie", extra_excl=excl),
        )

    def _parse_divisie(self, element: etree._Element, bwb_id: str) -> Divisie:
        """Parse een ``<circulaire.divisie>`` (recursief) uit een circulaire.

        De divisie draagt een eigen tekst (``./tekst``) én kan subdivisies
        bevatten; onderdelen (``<lijst>/<li>``) en verwijzingen komen uit die
        ``./tekst``. Verwijzingen binnen onderdelen worden op divisie-niveau
        uitgesloten (die horen bij het onderdeel-node) om dubbeling te vermijden.

        Een divisie kan daarnaast eigen ``<artikel>``-kinderen hebben – het XSD
        (``class.circulaire-tekst``) staat die naast ``circulaire.divisie`` en ``tekst`` toe, en de
        Leidraad Invordering 2008 gebruikt het ook: tien artikelen onder ``/Circulaire.divisie22bis``
        en één onder ``/Circulaire.divisie79``. Die vielen hiervóór stilzwijgend weg (10.052 tekens).
        Ze staan bùiten ``./tekst``, dus de tekst-, verwijzings- en onderdeelscopes hierboven raken
        ze niet en er ontstaat geen dubbeling.

        Subdivisies en artikelen worden in **documentvolgorde** gelezen, niet in twee losse passes:
        ``volgtOp`` wordt per soort geketend, en een divisie die beide bevat zou anders een
        volgorde krijgen die niet die van de bron is.
        """
        kop = element.find("kop")
        tekst_el = element.find("tekst")
        divisie = Divisie(
            id=self._knoop_id(bwb_id, element),
            nummer=self._tekst(kop.find("nr")) if kop is not None else "",
            label=element.get("label", ""),
            titel=self._tekst(kop.find("titel")) if kop is not None else "",
            tekst=self._divisie_tekst(element),
            jci=self._element_jci(element),
            inwerking=element.get("inwerking"),
            bron=element.get("bron"),
            effect=element.get("effect"),
            status=element.get("status"),
            terugwerkend_tot=self._terugwerkend(element),
            wijzigingsbronnen=self._wijzigingsbronnen(element),
            **self._bronverwijzingen(element),
            verwijzingen=self._verwijzingen_scope(
                element, bwb_id, base="./tekst//*", extra_excl=f" and not(ancestor::li){_GEEN_SLOT}"
            ),
            onderdelen=self._parse_onderdelen(tekst_el, bwb_id) if tekst_el is not None else [],
            voetnoten=[
                self._noot_tekst(noot)
                for noot in element.xpath(f"./tekst//noot[not(ancestor::li){_GEEN_SLOT}]")
            ],
            illustraties=self._illustraties(
                element,
                base="./tekst//illustratie",
                extra_excl=f" and not(ancestor::li){_GEEN_SLOT}",
            ),
        )
        for child in element:
            tag = child.tag if isinstance(child.tag, str) else ""
            if tag == "circulaire.divisie":
                divisie.subdivisies.append(self._parse_divisie(child, bwb_id))
            elif tag == "artikel":
                divisie.artikelen.append(self._parse_artikel(child, bwb_id))
            elif tag and tag != "tekst" and tag not in _GEEN_STRUCTUUR:
                self._meld_onbekend(element, tag)
        return divisie

    def _parse_bijlage(self, element: etree._Element, bwb_id: str) -> Bijlage:
        """Parse een ``<bijlage>`` (kind van ``<wet-besluit>``/``<regeling>``).

        Een bijlage is container én tekstdrager: eigen alinea's + onderdelen, en
        kan eigen artikelen bevatten (die als aparte ``Artikel``-nodes tellen).
        Tekst/verwijzingen/onderdelen op bijlage-niveau sluiten de inhoud van
        geneste artikelen/leden/onderdelen uit om dubbeling te vermijden.

        De artikelen hoeven geen direct kind te zijn: Bijlage 2 van de Awb deelt ze in onder
        ``<divisie>``-en met het koplabel Hoofdstuk. Die worden gewone structuurdelen, zodat leden,
        bronboom en annotatie-eenheden werken zoals in de hoofdwet.
        """
        kop = element.find("kop")
        excl = f" and not(ancestor::artikel) and not(ancestor::lid) and not(ancestor::li){_GEEN_SLOT}"
        bijlage = Bijlage(
            id=self._knoop_id(bwb_id, element),
            nummer=self._tekst(kop.find("nr")) if kop is not None else "",
            label=self._tekst(kop.find("label")) if kop is not None else element.get("label", ""),
            titel=self._tekst(kop.find("titel")) if kop is not None else "",
            tekst=self._bijlage_tekst(element),
            jci=self._element_jci(element),
            inwerking=element.get("inwerking"),
            bron=element.get("bron"),
            effect=element.get("effect"),
            status=element.get("status"),
            terugwerkend_tot=self._terugwerkend(element),
            wijzigingsbronnen=self._wijzigingsbronnen(element),
            **self._bronverwijzingen(element),
            verwijzingen=self._verwijzingen_scope(element, bwb_id, extra_excl=excl),
            onderdelen=self._parse_onderdelen(element, bwb_id),
            voetnoten=self._noten(element, excl),
            illustraties=self._illustraties(element, extra_excl=excl),
        )
        self._lees_kinderen(
            element, bwb_id, bijlage.structuurdelen, bijlage.artikelen, _BIJLAGE_TEKST
        )
        return bijlage

    def _parse_artikel(self, element: etree._Element, bwb_id: str) -> Artikel:
        kop = element.find("kop")
        excl = f" and not(ancestor::lid) and not(ancestor::li){_GEEN_SLOT}"
        artikel = Artikel(
            id=self._knoop_id(bwb_id, element),
            nummer=self._tekst(kop.find("nr")) if kop is not None else "",
            label=element.get("label", ""),
            titel=self._tekst(kop.find("titel")) if kop is not None else "",
            tekst=self._lichaamstekst(element, binnen_lid=False),
            jci=self._element_jci(element),
            label_id=element.get("label-id"),
            inwerking=element.get("inwerking"),
            bron=element.get("bron"),
            effect=element.get("effect"),
            status=element.get("status"),
            terugwerkend_tot=self._terugwerkend(element),
            definieert_begrippen=self._definities(element),
            wijzigingsbronnen=self._wijzigingsbronnen(element),
            **self._bronverwijzingen(element),
            verwijzingen=self._verwijzingen_scope(element, bwb_id, extra_excl=excl),
            onderdelen=self._parse_onderdelen(
                element, bwb_id, self._leidt_definities_in(element)
            ),
            voetnoten=self._noten(element, excl),
            illustraties=self._illustraties(element, extra_excl=excl),
        )
        for lid in element.iterfind("lid"):
            artikel.leden.append(self._parse_lid(lid, bwb_id))
        return artikel

    def _parse_lid(self, element: etree._Element, bwb_id: str) -> Lid:
        excl = f" and not(ancestor::li){_GEEN_SLOT}"
        return Lid(
            id=self._knoop_id(bwb_id, element),
            nummer=self._tekst(element.find("lidnr")),
            tekst=self._lichaamstekst(element, binnen_lid=True),
            jci=self._element_jci(element),
            terugwerkend_tot=self._terugwerkend(element),
            verwijzingen=self._verwijzingen_scope(element, bwb_id, extra_excl=excl),
            onderdelen=self._parse_onderdelen(
                element, bwb_id, self._leidt_definities_in(element)
            ),
            voetnoten=self._noten(element, excl),
            definieert_begrippen=self._definities(element),
            illustraties=self._illustraties(element, extra_excl=excl),
        )

    # --------------------------------------------------------------- onderdelen
    def _parse_onderdelen(
        self, element: etree._Element, bwb_id: str, definitie_context: bool = False
    ) -> list[Onderdeel]:
        """Onderdelen uit direct geneste ``<lijst>/<li>`` (recursief), in documentvolgorde.

        Tekst die ná een lijst doorloopt komt ertussen als slottekst (`_parse_slottekst`): die hoort
        op de plek waar hij staat, en niet achter de aanhef van zijn ouder. De bron kan zo ook lijst
        en tekst laten afwisselen (art. 25 lid 14 IW 1990): elk stuk tekst krijgt dan zijn eigen node.

        `definitie_context` komt van de houder (zie `_leidt_definities_in`) en **erft naar
        beneden**:
        de subonderdelen van "aa." (1°–4°: Koninkrijk, Rijk, Nederland, BES eilanden) staan in
        dezelfde begrippenlijst als hun ouder, maar de aanhef staat alleen bij het lid.
        """
        onderdelen: list[Onderdeel] = []
        reeks: list[etree._Element] = []
        slotteksten = 0

        def sluit_reeks() -> None:
            nonlocal slotteksten
            if reeks:
                slotteksten += 1
                onderdelen.append(self._parse_slottekst(element, reeks, slotteksten, bwb_id))
                reeks.clear()

        for kind in element.xpath(f"./lijst | ./{_SLOT_AL}"):
            if kind.tag == "al":
                reeks.append(kind)
                continue
            sluit_reeks()
            for li in kind.findall("li"):
                onderdelen.append(self._parse_onderdeel(li, bwb_id, definitie_context))
        sluit_reeks()
        return onderdelen

    def _parse_slottekst(
        self, houder: etree._Element, alineas: list[etree._Element], volgnummer: int, bwb_id: str
    ) -> Onderdeel:
        """Aaneengesloten alinea's ná een opsomming: een ongenummerd onderdeel van de houder.

        Een eigen node en geen veld op de ouder: één laag per bronnode, ankers in de eigen tekst en
        de bronboom die de volgorde draagt werken dan zonder meer. De bron geeft een `<al>` geen eigen
        jci, dus de sleutel volgt uit de houder (`bwb-ng-variabel-deel`) en de plek.
        """
        tekst = " ".join(_tekst_zonder_noot(al) for al in alineas)
        verwijzingen: list[Verwijzing] = []
        voetnoten: list[str] = []
        illustraties: list[Illustratie] = []
        for al in alineas:
            verwijzingen.extend(self._verwijzingen_scope(al, bwb_id))
            voetnoten.extend(self._noten(al, ""))
            illustraties.extend(self._illustraties(al))
        return Onderdeel(
            id=f"{self._knoop_id(bwb_id, houder)}/Slottekst{volgnummer}",
            nummer="",
            tekst=re.sub(r"\s+", " ", tekst).strip(),
            slottekst=True,
            verwijzingen=verwijzingen,
            voetnoten=voetnoten,
            illustraties=illustraties,
        )

    def _parse_onderdeel(
        self, li: etree._Element, bwb_id: str, definitie_context: bool = False
    ) -> Onderdeel:
        nr = li.find("li.nr")
        tekst_delen = [
            _tekst_zonder_noot(node) for node in li.xpath("./al[not(preceding-sibling::lijst)]")
        ]
        return Onderdeel(
            id=self._knoop_id(bwb_id, li),
            nummer=self._tekst(nr) if nr is not None else "",
            tekst=re.sub(r"\s+", " ", " ".join(tekst_delen)).strip(),
            jci=self._element_jci(li),
            verwijzingen=self._verwijzingen_scope(li, bwb_id, base="./al//*", extra_excl=_GEEN_SLOT),
            subonderdelen=self._parse_onderdelen(li, bwb_id, definitie_context),
            voetnoten=[
                self._noot_tekst(noot)
                for noot in li.xpath(f"./al//noot[not(ancestor::meta-data){_GEEN_SLOT}]")
            ],
            definieert_begrippen=self._definities(li, definitie_context=definitie_context),
            illustraties=self._illustraties(li, base="./al//illustratie", extra_excl=_GEEN_SLOT),
        )

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _knoop_id(bwb_id: str, element: etree._Element) -> str:
        """Stabiele sleutel uit ``bwb-ng-variabel-deel`` (valt terug op tag)."""
        pad = element.get("bwb-ng-variabel-deel")
        return f"{bwb_id}{pad}" if pad else f"{bwb_id}/{element.tag}"

    @staticmethod
    def _tekst(element: etree._Element | None) -> str:
        """Genormaliseerde tekst van een element, exclusief meta-data-subtrees."""
        if element is None:
            return ""
        delen = element.xpath(".//text()[not(ancestor::meta-data)]")
        return re.sub(r"\s+", " ", "".join(delen)).strip()

    @staticmethod
    def _lichaamstekst(element: etree._Element, *, binnen_lid: bool) -> str:
        """De lopende tekst van een artikel of lid. Tekst in een lid hoort bij het lid, tekst in een onderdeel
        (``<li>``) bij het onderdeel, en tekst ná een opsomming is een eigen slottekst-node (`_parse_onderdelen`)."""
        binnen = "not(ancestor::li)" if binnen_lid else "not(ancestor::lid) and not(ancestor::li)"
        return _tekst_in(element, ".//", binnen)

    @staticmethod
    def _bijlage_tekst(element: etree._Element) -> str:
        """Eigen lopende tekst van een bijlage: wat niet in een genest artikel, lid of onderdeel staat."""
        return _tekst_in(element, ".//", "not(ancestor::artikel) and not(ancestor::lid) and not(ancestor::li)")

    @staticmethod
    def _illustraties(
        element: etree._Element,
        *,
        base: str = ".//illustratie",
        extra_excl: str = "",
    ) -> list[Illustratie]:
        """Illustraties binnen ``element`` (uit ``<plaatje>/<illustratie>``),
        beperkt via ``base`` + exclusies zoals de tekst-scope, zodat een
        illustratie bij de meest specifieke tekstdrager landt."""
        out: list[Illustratie] = []
        for il in element.xpath(f"{base}[not(ancestor::meta-data){extra_excl}]"):
            out.append(
                Illustratie(
                    id=il.get("id") or il.get("naam") or "",
                    naam=il.get("naam"),
                    formaat=il.get("formaat"),
                    breedte=il.get("breedte"),
                    hoogte=il.get("hoogte"),
                    alt=il.get("alt"),
                )
            )
        return out

    def _parse_ondertekenaars(self, wetgeving: etree._Element) -> list[Ondertekenaar]:
        """Ondertekenaars uit de ``<ondertekening>``-blokken van de regeling.

        Een ondertekening bevat een ``<functie>`` en een ``<naam>`` (met
        ``<voornaam>``/``<achternaam>``). Ontdubbelt op (functie, naam)."""
        gezien: set[tuple[str, str, str]] = set()
        out: list[Ondertekenaar] = []
        for ondt in wetgeving.iter("ondertekening"):
            naam_el = ondt.find("naam")
            functie = self._tekst(ondt.find("functie")) or None
            voornaam = self._tekst(naam_el.find("voornaam")) if naam_el is not None else ""
            achternaam = self._tekst(naam_el.find("achternaam")) if naam_el is not None else ""
            naam = self._tekst(naam_el) if naam_el is not None else ""
            if not (functie or naam):
                continue
            sleutel = (functie or "", naam, achternaam)
            if sleutel in gezien:
                continue
            gezien.add(sleutel)
            out.append(
                Ondertekenaar(
                    functie=functie,
                    naam=naam or None,
                    voornaam=voornaam or None,
                    achternaam=achternaam or None,
                    plaats=self._tekst(ondt.find("plaats")) or None,
                    datum=None,
                )
            )
        return out

    @staticmethod
    def _divisie_tekst(element: etree._Element) -> str:
        """Lopende tekst van een divisie: wat in ``./tekst`` staat, buiten de onderdelen. Geneste subdivisies staan
        buiten ``./tekst`` en tellen dus niet mee."""
        return _tekst_in(element, "./tekst//", "not(ancestor::li)")

    def _wet_aanhef(self, wetgeving: etree._Element) -> dict[str, str | None]:
        """Aanhef en considerans (``wet-besluit/aanhef`` of ``regeling/aanhef``)."""
        aanhef_el = wetgeving.find("wet-besluit/aanhef")
        if aanhef_el is None:
            aanhef_el = wetgeving.find("regeling/aanhef")
        if aanhef_el is None:
            return {"aanhef": None, "considerans": None}
        aanhef_delen = [
            # Wetten/besluiten openen met <wij>, ministeriële regelingen met <wie>.
            self._tekst(aanhef_el.find("wij")),
            self._tekst(aanhef_el.find("wie")),
            self._tekst(aanhef_el.find("afkondiging")),
        ]
        aanhef = " ".join(d for d in aanhef_delen if d).strip() or None
        considerans_delen = [
            _tekst_zonder_noot(al) for al in aanhef_el.xpath("./considerans/considerans.al")
        ]
        considerans = re.sub(r"\s+", " ", " ".join(considerans_delen)).strip() or None
        return {"aanhef": aanhef, "considerans": considerans}

    def _noten(self, element: etree._Element, extra_excl: str) -> list[str]:
        """Voetnoten binnen het tekstbereik van deze node (zelfde exclusies
        als de lopende tekst, zodat noot en tekst op hetzelfde niveau landen)."""
        xpath = f".//noot[not(ancestor::meta-data){extra_excl}]"
        return [self._noot_tekst(noot) for noot in element.xpath(xpath)]

    @staticmethod
    def _noot_tekst(noot: etree._Element) -> str:
        delen = noot.xpath(".//text()[not(ancestor::meta-data)]")
        return re.sub(r"\s+", " ", "".join(delen)).strip()

    @staticmethod
    def _definities(element: etree._Element, *, definitie_context: bool = False) -> list[str]:
        """Gedefinieerde begrippen, langs twee routes.

        **1. Opmaak** – een cursieve term (``nadruk type="cur"``) die op een dubbele punt eindigt.
        Precies, maar de bron levert het niet consequent: in artikel 2 lid 1 IW 1990 staat
        ``rijksbelastingen:`` cursief en ``belastingschuldige:`` niet, in dezelfde opsomming en met
        dezelfde zinsvorm. Alleen op opmaak leunen levert zo maar enkele tientallen definities in de
        hele graaf op, en `zoek_definitie("belastingschuldige")` niets – de definitie-specialist moet
        dan definitieartikelen raden, precies wat die tool moet wegnemen.

        **2. Tekst** – de vorm ``term: definitie``, maar alléén als de houder (het lid of artikel)
        definities inleidt; dat zegt `definitie_context`. Die eis is niet optioneel: de dubbele punt
        alleen betekent niets. Dezelfde wet bevat onderdelen als "met betrekking tot een natuurlijk
        persoon: de naam, het adres en de geboortedatum;" — zelfde vorm, geen definitie. Gemeten
        over
        BWBR0004770 en BWBR0005537 laat de aanhef-eis precies die gevallen vallen.

        **3. Zin** – "Onder X wordt verstaan" aan het begin van de tekst (Awb 1:2): die zin leidt zichzelf
        in, dus zonder `definitie_context`.

        Beide eerste routes kunnen op hetzelfde onderdeel vuren (een cursieve term matcht ook het patroon),
        dus ontdubbelen we met behoud van volgorde.
        """
        begrippen: list[str] = []
        for term in element.xpath("./al/nadruk[@type='cur']/text()"):
            genormaliseerd = term.strip()
            if genormaliseerd.endswith(":"):
                begrippen.append(genormaliseerd.rstrip(":").strip())

        if definitie_context:
            for al in element.findall("al"):
                treffer = _DEFINITIE_TERM.match(ToestandParser._tekst(al))
                if treffer:
                    begrippen.append(treffer.group(1).strip())

        eerste = element.find("al")
        if eerste is not None and (treffer := _ONDER_TERM.match(ToestandParser._tekst(eerste))):
            begrippen.append(treffer.group(1).strip())

        return list(dict.fromkeys(begrippen))

    @staticmethod
    def _leidt_definities_in(element: etree._Element) -> bool:
        """Kondigt dit lid/artikel in zijn eigen alinea's een begrippenlijst aan?

        Alleen de eigen ``<al>``-kinderen tellen, niet de onderdelen eronder — anders zou één
        definitie ergens in de opsomming de hele lijst als definitielijst bestempelen.
        """
        eigen = " ".join(ToestandParser._tekst(al) for al in element.findall("al"))
        return bool(_DEFINITIE_AANHEF.search(eigen))

    @staticmethod
    def _element_jci(element: etree._Element) -> str | None:
        """De canonieke ``jci1.3``-verwijzing van een artikel/lid uit zijn meta-data."""
        for jci in element.xpath("./meta-data/jcis/jci/@verwijzing"):
            if jci.startswith("jci1.3:"):
                return jci
        return None

    @staticmethod
    def _verwijzingen_scope(
        element: etree._Element,
        bwb_id: str,
        *,
        base: str = ".//*",
        extra_excl: str = "",
    ) -> list[Verwijzing]:
        """Verwijzingen binnen ``element``, beperkt via ``base`` + extra exclusies.

        ``base`` bepaalt het zoekbereik (bv. ``./al//*`` voor alleen de directe
        alinea's van een onderdeel); ``extra_excl`` voegt voorwaarden toe zoals
        ``and not(ancestor::lid)`` om geneste niveaus uit te sluiten.
        """
        scope = etree.Element("scope")
        xpath = f"{base}[self::intref or self::extref][not(ancestor::meta-data){extra_excl}]"
        for ref in element.xpath(xpath):
            scope.append(_kopie(ref))
        return extract_references(scope, eigen_bwb_id=bwb_id)

    @staticmethod
    def _terugwerkend(element: etree._Element) -> str | None:
        """Retroactieve ingangsdatum uit het eigen meta-data-blok
        (``brondata/inwerkingtreding/terugwerkend.datum``), indien aanwezig."""
        for datum in element.xpath(
            "./meta-data/brondata/inwerkingtreding/terugwerkend.datum/@isodatum"
        ):
            if datum:
                return datum
        return None

    @staticmethod
    def _wijzigingsbronnen(element: etree._Element) -> list[str]:
        """Stb-bronnen waarmee dit artikel is gewijzigd (uit ``<juncto>``)."""
        bronnen: list[str] = []
        for pub in element.xpath("./meta-data//juncto/publicatie"):
            jaar = pub.findtext("publicatiejaar")
            nr = pub.findtext("publicatienr")
            if jaar and nr:
                bronnen.append(f"{pub.get('soort', 'Stb')}.{jaar}-{nr}")
        return bronnen

    @staticmethod
    def _bronverwijzingen(element: etree._Element) -> dict[str, Any]:
        """Kamerdossier, inwerkingtredingsbron en opmerking uit het eigen brondata-blok.

        De attributen van een tekstdeel noemen de Stb van de laatste wijziging (`bron`) en de datum
        (`inwerking`), maar niet het Kamerdossier van die wijziging. Dat staat alleen in
        ``meta-data/brondata``: ``oorspronkelijk/publicatie/dossierref`` (de wet die de tekst zijn
        huidige inhoud gaf) en de ``dossierref`` van de ``<juncto>``-publicaties ernaast. Daarmee
        vindt Lex de memorie van toelichting bij déze bepaling, zonder te raden. De
        inwerkingtredingsbron is de Stb van het inwerkingtredingsbesluit; de opmerking is
        redactioneel (vaak: waar het overgangsrecht staat). Alles wat er niet staat, blijft leeg.
        """
        dossiers: list[str] = []
        for d in element.xpath(
            "./meta-data/brondata/oorspronkelijk/publicatie/dossierref/@dossier"
            " | ./meta-data/brondata/oorspronkelijk/juncto/publicatie/dossierref/@dossier"
        ):
            d = d.strip()
            if d and d not in dossiers:
                dossiers.append(d)
        iwt = None
        pub = element.find("meta-data/brondata/inwerkingtreding/publicatie")
        if pub is not None and pub.findtext("publicatiejaar") and pub.findtext("publicatienr"):
            iwt = f"{pub.get('soort', 'Stb')}.{pub.findtext('publicatiejaar')}-{pub.findtext('publicatienr')}"
        alineas = [
            " ".join("".join(al.itertext()).split())
            for al in element.xpath("./meta-data/brondata/opmerkingen-inhoud/al")
        ]
        opmerking = "\n".join(a for a in alineas if a) or None
        return {"dossiers": dossiers, "inwerkingtredingsbron": iwt, "opmerking": opmerking}

    @staticmethod
    def _wet_brondata(wetgeving: etree._Element) -> dict[str, str | None]:
        """Brondata van de oorspronkelijke regeling (wetgeving/meta-data/brondata)."""
        pub = wetgeving.find("meta-data/brondata/oorspronkelijk/publicatie")
        if pub is None:
            return {
                "publicatiejaar": None,
                "publicatienr": None,
                "ondertekeningsdatum": None,
                "uitgiftedatum": None,
                "dossier": None,
            }
        ondt = pub.find("ondertekeningsdatum")
        uitg = pub.find("uitgiftedatum")
        doss = pub.find("dossierref")
        return {
            "publicatiejaar": pub.findtext("publicatiejaar"),
            "publicatienr": pub.findtext("publicatienr"),
            "ondertekeningsdatum": ondt.get("isodatum") if ondt is not None else None,
            "uitgiftedatum": uitg.get("isodatum") if uitg is not None else None,
            "dossier": doss.get("dossier") if doss is not None else None,
        }


def _bron(xml: Path | str | bytes) -> str | io.BytesIO:
    """Wat `etree.parse` leest: een pad als tekst, of de XML zelf als bestand in het geheugen."""
    return io.BytesIO(xml) if isinstance(xml, bytes) else str(xml)


def _naam(xml: Path | str | bytes) -> str:
    return "<xml in het geheugen>" if isinstance(xml, bytes) else Path(xml).name


def _tekst_in(element: etree._Element, basis: str, binnen: str) -> str:
    """De ene tekstfunctie voor artikel, lid, bijlage en divisie (D3).

    Alinea's én tussenkoppen in documentvolgorde, zonder voetnoten en meta-data; tabellen (CALS) als leesbare rijen
    ná de lopende tekst. `binnen` zegt welke tekst bij een ander node hoort. Drie plekken hadden elk een eigen
    variant, en de divisie las daardoor geen tabel en niemand een tussenkop."""
    scope = f"{binnen} and not(ancestor::meta-data)"
    delen = [_tekst_zonder_noot(node) for node in element.xpath(
        f"{basis}*[(self::al or self::tussenkop) and {scope} and not(ancestor::table){_GEEN_SLOT}]")]
    tekst = re.sub(r"\s+", " ", " ".join(delen)).strip()
    tabellen = [t for t in (_tabel_tekst(x) for x in element.xpath(f"{basis}table[{scope}]")) if t]
    return "\n".join([tekst, *tabellen]).strip() if tabellen else tekst


def _tekst_zonder_noot(element: etree._Element) -> str:
    """Alle tekst van een element, exclusief voetnoot-inhoud (``<noot>``)."""
    return "".join(element.xpath(".//text()[not(ancestor::noot)]"))


def _tabel_tekst(table: etree._Element) -> str:
    """Leesbare weergave van een CALS-tabel: cellen per rij met ``|`` gescheiden.

    De structuur (kolombreedtes, spans) gaat verloren; doel is dat geen tekst
    stilzwijgend verdwijnt en de inhoud full-text-doorzoekbaar is.
    """
    rijen: list[str] = []
    for row in table.xpath(".//row"):
        cellen: list[str] = []
        for entry in row.xpath("./entry"):
            delen = entry.xpath(".//text()[not(ancestor::meta-data) and not(ancestor::noot)]")
            cellen.append(re.sub(r"\s+", " ", "".join(delen)).strip())
        rij = " | ".join(cellen).strip()
        if rij.strip("| "):
            rijen.append(rij)
    return "\n".join(rijen)


def _kopie(element: etree._Element) -> etree._Element:
    """Maak een losse kopie van een element (zonder het uit de boom te halen)."""
    nieuw = etree.Element(element.tag, dict(element.attrib))
    nieuw.text = element.text
    for child in element:
        nieuw.append(_kopie(child))
    return nieuw
