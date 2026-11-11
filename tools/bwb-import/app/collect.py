"""Opslag-agnostische traversal van het BWB-model naar een platte ``Batch``.

Loopt één keer door een :class:`~bronmodel.bwb.models.Wet` en verzamelt nodes, relaties en
verwijzingen in een neutrale representatie. De GraphDB-writer consumeert die
``Batch``, zodat de ref_key-/Citeerbaar-/verwijzing-logica (inclusief de telling
in :class:`~bronmodel.bwb.models.ImportSummary`) op één plek staat.

Elke node die JuriConnect-adresseerbaar is (wet, structuurdeel, artikel, lid,
onderdeel, divisie) draagt naast zijn XML-``id`` een ``ref_key``. Die sleutel is
de stabiele identiteit voor citaties: een ``VERWIJST_NAAR`` naar een nog niet
geïmporteerde wet gebruikt dezelfde ref_key, zodat de doel-node later
automatisch samenvalt (dezelfde IRI). Verwijzingen worden toegeschreven aan de
dichtstbijzijnde voorouder mét ref_key (onderdeel -> lid -> artikel).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from bronmodel.bwb.models import (
    Artikel,
    Bijlage,
    Divisie,
    Illustratie,
    ImportSummary,
    Onderdeel,
    Ondertekenaar,
    Structuurdeel,
    Verwijzing,
    Wet,
)
from bronmodel.bwb.references import (
    deeldoelen,
    detect_textual_references,
    jci_doel,
    jci_doel_ref_key,
    jci_node_ref_key,
    jci_to_ref_key,
)

# Relatie van ouder naar structuurdeel, per soort.
STRUCT_REL = {
    "hoofdstuk": "HEEFT_HOOFDSTUK",
    "titeldeel": "HEEFT_TITELDEEL",
    "afdeling": "HEEFT_AFDELING",
    "paragraaf": "HEEFT_PARAGRAAF",
}
# Structuursoort -> entiteitsnaam (voor label/klasse).
STRUCT_LABEL = {
    "hoofdstuk": "Hoofdstuk",
    "titeldeel": "Titeldeel",
    "afdeling": "Afdeling",
    "paragraaf": "Paragraaf",
}
# Structuursoort -> teller in ImportSummary.
_STRUCT_TELLER = {
    "hoofdstuk": "hoofdstukken",
    "titeldeel": "titeldelen",
    "afdeling": "afdelingen",
    "paragraaf": "paragrafen",
}

# Doel-soorten waarvan het "nummer" een artikelnummer is (voor labels).
_ARTIKEL_SOORTEN = {"artikel", "lid", "onderdeel"}


def nummer_van(nummer: str | None) -> str:
    """Het nummer zoals het in een vindplaats staat: "a." → "a", "1." → "1", "1°" blijft. Een
    opsommingsteken ("–", "•") is geen nummer: leeg."""
    n = (nummer or "").strip().rstrip(".").strip()
    return n if re.search(r"[0-9A-Za-z]", n) else ""


def _bepaling_naam(soort: str, nummer: str, *reserves: str | None) -> str:
    """"Artikel 9", "Bijlage 2"; zonder nummer het label of de titel uit de bron. Een divisie van een
    beleidsregel heet ook "Artikel 9.4": zo verwijst de Leidraad zelf naar zijn onderdelen."""
    nr = nummer_van(nummer)
    if nr:
        return f"{soort} {nr}"
    return next((r.strip() for r in reserves if r and r.strip()), soort)


@dataclass(frozen=True)
class _Plek:
    """Waar een onderdeel staat: de vindplaats van zijn ouder, of die al op een onderdeelnummer
    eindigt, en de kiesbare bepaling erboven (lid, artikel, divisie of bijlage) als (entiteit, id)."""

    vindplaats: str
    bepaling: tuple[str, str]
    in_onderdeel: bool = False


@dataclass
class Batch:
    """Verzamelde nodes en relaties, klaar om te schrijven.

    - ``nodes``: entiteit -> lijst prop-dicts (elk met ``id``; nodes met een
      JuriConnect-identiteit dragen ook ``ref_key``).
    - ``rels``: ``(src_ent, rel_type, dst_ent)`` -> rijen ``{"from": id, "to": id}``.
    - ``verwijzingen``: rijen met ``from``/``to`` als *ref_key* plus
      soort/doc/doel-metadata.
    """

    nodes: dict[str, list[dict]] = field(default_factory=dict)
    rels: dict[tuple[str, str, str], list[dict]] = field(default_factory=dict)
    verwijzingen: list[dict] = field(default_factory=list)

    def node(self, entiteit: str, props: dict) -> None:
        self.nodes.setdefault(entiteit, []).append(props)

    def rel(self, src: str, rel_type: str, dst: str, from_id: str, to_id: str) -> None:
        self.rels.setdefault((src, rel_type, dst), []).append({"from": from_id, "to": to_id})


class _Collector:
    """Bouwt een :class:`Batch` uit een :class:`Wet` (één traversal)."""

    def __init__(self, wet: Wet, *, tekstuele_refs: bool = True) -> None:
        self._bwb = wet.bwb_id
        self._tekstuele_refs = tekstuele_refs
        self.batch = Batch()
        self.summary = ImportSummary(bwb_id=wet.bwb_id, wetten=1)
        self._onderdeel_teller = 0
        # De naam van de bijlage waar we nu in zitten ("Bijlage 2"). Daar geldt een andere identiteit,
        # zie `_id_sleutel`.
        self._in_bijlage: str | None = None

    def _id_sleutel(self, node_id: str) -> str:
        """De wet-lokale sleutel van een node in een bijlage.

        Een artikelnummer is binnen een regeling alleen uniek buiten de bijlagen: Bijlage 2 en 3 van
        de Awb hebben allebei een artikel 1 en 2, en `&bijlage=2&hoofdstuk=1` is een ander hoofdstuk
        dan het eerste van de wet. Een sleutel uit de jci laat de bijlage weg en zou ze op één node
        laten vallen. De `id:`-vorm is wat de bijlage en haar onderdelen al hebben: hij is uniek,
        elke afnemer kent hem, en `bwb:jci` houdt de echte jci uit de bron.
        """
        return f"{self._bwb}#id={node_id}"

    def run(self, wet: Wet) -> None:
        self.batch.node(
            "Regeling",
            {
                "id": wet.bwb_id,
                "bwb_id": wet.bwb_id,
                "ref_key": wet.bwb_id,
                "label_id": wet.label_id,
                "citeertitel": wet.citeertitel,
                "opschrift": wet.opschrift,
                "soort": wet.soort,
                "geldig_vanaf": wet.geldig_vanaf,
                "geldig_tot": wet.geldig_tot,
                "publicatiejaar": wet.publicatiejaar,
                "publicatienr": wet.publicatienr,
                "ondertekeningsdatum": wet.ondertekeningsdatum,
                "uitgiftedatum": wet.uitgiftedatum,
                "dossier": wet.dossier,
                "aanhef": wet.aanhef,
                "considerans": wet.considerans,
                "stub": False,
            },
        )
        for deel in wet.structuurdelen:
            self._structuur(deel, wet.bwb_id, "Regeling")
        self._artikelen(wet.losse_artikelen, wet.bwb_id, "Regeling")
        self._divisies(wet.divisies, wet.bwb_id, "Regeling")
        self._bijlagen(wet.bijlagen, wet.bwb_id, "Regeling")
        self._ondertekenaars(wet.ondertekenaars, wet.bwb_id)

    def _structuur(
        self,
        deel: Structuurdeel,
        ouder_id: str,
        ouder_ent: str,
        ouder_ref_key: str | None = None,
    ) -> None:
        entiteit = STRUCT_LABEL[deel.soort]
        # `jci_node_ref_key` en niet `jci_doel_ref_key`: die tweede houdt alleen het laatste
        # structuursegment aan, waardoor elke "Afdeling 1" van een regeling op dezelfde IRI landde.
        # Zie de docstring daar voor de meting; kort: 16 van de 93 afdelingen waren samengevallen.
        ref_key, soort = jci_node_ref_key(deel.jci)
        if self._in_bijlage:
            ref_key, soort = self._id_sleutel(deel.id), deel.soort
        if soort == "wet":
            # Een jci zonder eigen structuursegment (bv. alleen `&bijlage=1`) wijst de hele
            # regeling aan; als identiteit zou dit deel op de regeling-IRI landen.
            ref_key = None
        if ref_key is None and deel.nummer:
            # Geen jci van de redactie. Bouw de sleutel dan op het pad van de ouder, om precies
            # dezelfde reden: zonder dat is "paragraaf 1" van elk hoofdstuk dezelfde node.
            basis = ouder_ref_key if ouder_ref_key else self._bwb
            ref_key = f"{basis}#{deel.soort}={deel.nummer}"
        self.batch.node(
            entiteit,
            {
                "id": deel.id,
                "nummer": deel.nummer,
                "label": deel.label,
                "titel": deel.titel,
                "soort": deel.soort,
                "ref_key": ref_key,
                "jci": deel.jci,
                "label_id": deel.label_id,
            },
        )
        self.batch.rel(ouder_ent, STRUCT_REL[deel.soort], entiteit, ouder_id, deel.id)
        teller = _STRUCT_TELLER[deel.soort]
        setattr(self.summary, teller, getattr(self.summary, teller) + 1)

        for sub in deel.subdelen:
            self._structuur(sub, deel.id, entiteit, ref_key)
        self._artikelen(deel.artikelen, deel.id, entiteit)
        # De tekst van een paragraaf zonder artikelen (een ``<structuurtekst>``, het BBBB): een divisie onder het deel.
        self._divisies(deel.divisies, deel.id, entiteit)

    def _artikelen(self, artikelen: list[Artikel], ouder_id: str, ouder_ent: str) -> None:
        vorige_artikel: str | None = None
        for artikel in artikelen:
            if self._in_bijlage:
                ref_key = self._id_sleutel(artikel.id)
            else:
                ref_key = jci_to_ref_key(artikel.jci) or self._id_sleutel(artikel.id)
            vindplaats = _bepaling_naam("Artikel", artikel.nummer, artikel.label)
            if self._in_bijlage:
                vindplaats = f"{self._in_bijlage}, {vindplaats[:1].lower()}{vindplaats[1:]}"
            self.batch.node(
                "Artikel",
                {
                    "id": artikel.id,
                    "nummer": artikel.nummer,
                    "label": artikel.label,
                    "titel": artikel.titel,
                    "vindplaats": vindplaats,
                    "tekst": artikel.tekst,
                    "ref_key": ref_key,
                    "definieert_begrip": artikel.definieert_begrippen,
                    "jci": artikel.jci,
                    "label_id": artikel.label_id,
                    "inwerking": artikel.inwerking,
                    "bron": artikel.bron,
                    "effect": artikel.effect,
                    "status": artikel.status,
                    "terugwerkend_tot": artikel.terugwerkend_tot,
                    "wijzigingsbronnen": artikel.wijzigingsbronnen,
                    "dossier": artikel.dossiers,
                    "inwerkingtredingsbron": artikel.inwerkingtredingsbron,
                    "opmerking": artikel.opmerking,
                    "voetnoot": artikel.voetnoten,
                },
            )
            self.batch.rel(ouder_ent, "HEEFT_ARTIKEL", "Artikel", ouder_id, artikel.id)
            self.summary.artikelen += 1
            if vorige_artikel is not None:
                self.batch.rel("Artikel", "VOLGT_OP", "Artikel", artikel.id, vorige_artikel)
            vorige_artikel = artikel.id

            self._verwijzingen(ref_key, artikel.verwijzingen, artikel.tekst)
            self._illustraties("Artikel", artikel.id, artikel.illustraties)
            self._leden(artikel, ref_key, vindplaats)
            self._onderdelen(artikel.onderdelen, artikel.id, "Artikel", ref_key,
                             _Plek(vindplaats, ("Artikel", artikel.id)))

    def _divisies(self, divisies: list[Divisie], ouder_id: str, ouder_ent: str) -> None:
        vorige_divisie: str | None = None
        for divisie in divisies:
            ref_key = jci_to_ref_key(divisie.jci) or f"{self._bwb}#id={divisie.id}"
            vindplaats = _bepaling_naam("Artikel", divisie.nummer, divisie.label, divisie.titel)
            self.batch.node(
                "Divisie",
                {
                    "id": divisie.id,
                    "nummer": divisie.nummer,
                    "label": divisie.label,
                    "vindplaats": vindplaats,
                    "titel": divisie.titel,
                    "tekst": divisie.tekst,
                    "ref_key": ref_key,
                    "jci": divisie.jci,
                    "inwerking": divisie.inwerking,
                    "bron": divisie.bron,
                    "effect": divisie.effect,
                    "status": divisie.status,
                    "terugwerkend_tot": divisie.terugwerkend_tot,
                    "wijzigingsbronnen": divisie.wijzigingsbronnen,
                    "dossier": divisie.dossiers,
                    "inwerkingtredingsbron": divisie.inwerkingtredingsbron,
                    "opmerking": divisie.opmerking,
                    "voetnoot": divisie.voetnoten,
                },
            )
            self.batch.rel(ouder_ent, "HEEFT_DIVISIE", "Divisie", ouder_id, divisie.id)
            self.summary.divisies += 1
            if vorige_divisie is not None:
                self.batch.rel("Divisie", "VOLGT_OP", "Divisie", divisie.id, vorige_divisie)
            vorige_divisie = divisie.id

            self._verwijzingen(ref_key, divisie.verwijzingen, divisie.tekst)
            self._illustraties("Divisie", divisie.id, divisie.illustraties)
            self._onderdelen(divisie.onderdelen, divisie.id, "Divisie", ref_key,
                             _Plek(vindplaats, ("Divisie", divisie.id)))
            self._divisies(divisie.subdivisies, divisie.id, "Divisie")
            # Een divisie kan eigen artikelen bevatten (aparte Artikel-nodes), net als een bijlage.
            self._artikelen(divisie.artikelen, divisie.id, "Divisie")

    def _bijlagen(self, bijlagen: list[Bijlage], ouder_id: str, ouder_ent: str) -> None:
        vorige_bijlage: str | None = None
        for bijlage in bijlagen:
            ref_key = jci_to_ref_key(bijlage.jci) or f"{self._bwb}#id={bijlage.id}"
            vindplaats = _bepaling_naam("Bijlage", bijlage.nummer, bijlage.label, bijlage.titel)
            self.batch.node(
                "Bijlage",
                {
                    "id": bijlage.id,
                    "nummer": bijlage.nummer,
                    "label": bijlage.label,
                    "vindplaats": vindplaats,
                    "titel": bijlage.titel,
                    "tekst": bijlage.tekst,
                    "ref_key": ref_key,
                    "jci": bijlage.jci,
                    "inwerking": bijlage.inwerking,
                    "bron": bijlage.bron,
                    "effect": bijlage.effect,
                    "status": bijlage.status,
                    "terugwerkend_tot": bijlage.terugwerkend_tot,
                    "wijzigingsbronnen": bijlage.wijzigingsbronnen,
                    "dossier": bijlage.dossiers,
                    "inwerkingtredingsbron": bijlage.inwerkingtredingsbron,
                    "opmerking": bijlage.opmerking,
                    "voetnoot": bijlage.voetnoten,
                },
            )
            self.batch.rel(ouder_ent, "HEEFT_BIJLAGE", "Bijlage", ouder_id, bijlage.id)
            self.summary.bijlagen += 1
            if vorige_bijlage is not None:
                self.batch.rel("Bijlage", "VOLGT_OP", "Bijlage", bijlage.id, vorige_bijlage)
            vorige_bijlage = bijlage.id

            self._verwijzingen(ref_key, bijlage.verwijzingen, bijlage.tekst)
            self._illustraties("Bijlage", bijlage.id, bijlage.illustraties)
            self._in_bijlage = vindplaats
            self._onderdelen(bijlage.onderdelen, bijlage.id, "Bijlage", ref_key,
                             _Plek(vindplaats, ("Bijlage", bijlage.id)))
            # Een bijlage kan eigen artikelen bevatten (aparte Artikel-nodes), direct of onder een
            # hoofdstuk.
            for deel in bijlage.structuurdelen:
                self._structuur(deel, bijlage.id, "Bijlage")
            self._artikelen(bijlage.artikelen, bijlage.id, "Bijlage")
            self._in_bijlage = None

    def _illustraties(self, ouder_ent: str, ouder_id: str, illustraties: list[Illustratie]) -> None:
        for illustratie in illustraties:
            self.batch.node(
                "Illustratie",
                {
                    "id": illustratie.id,
                    "naam": illustratie.naam,
                    "formaat": illustratie.formaat,
                    "breedte": illustratie.breedte,
                    "hoogte": illustratie.hoogte,
                    "alt": illustratie.alt,
                },
            )
            self.batch.rel(ouder_ent, "BEVAT_ILLUSTRATIE", "Illustratie", ouder_id, illustratie.id)
            self.summary.illustraties += 1

    def _ondertekenaars(self, ondertekenaars: list[Ondertekenaar], bwb_id: str) -> None:
        """Ondertekenaar-nodes met een wet-overstijgende slug-IRI (dezelfde persoon
        valt over regelingen heen samen) en een ONDERTEKEND_DOOR-relatie."""
        for index, ondertekenaar in enumerate(ondertekenaars):
            sleutel = (
                " ".join(
                    deel
                    for deel in (
                        ondertekenaar.functie,
                        ondertekenaar.naam or ondertekenaar.achternaam,
                    )
                    if deel
                )
                or f"{bwb_id}-{index}"
            )
            node_id = f"{bwb_id}/ondertekenaar/{index}"
            self.batch.node(
                "Ondertekenaar",
                {
                    "id": node_id,
                    "iri_soort": "ondertekenaar",
                    "iri_sleutel": sleutel,
                    "functie": ondertekenaar.functie,
                    "naam": ondertekenaar.naam,
                    "voornaam": ondertekenaar.voornaam,
                    "achternaam": ondertekenaar.achternaam,
                    "plaats": ondertekenaar.plaats,
                    "ondertekeningsdatum": ondertekenaar.datum,
                },
            )
            self.batch.rel("Regeling", "ONDERTEKEND_DOOR", "Ondertekenaar", bwb_id, node_id)
            self.summary.ondertekenaars += 1

    def _leden(self, artikel: Artikel, artikel_ref_key: str, artikel_vindplaats: str) -> None:
        vorige_lid: str | None = None
        for lid in artikel.leden:
            lb, la, ll = jci_doel(lid.jci)
            lid_ref = f"{lb}#artikel={la}#lid={ll}" if lb and la and ll else None
            if self._in_bijlage:
                lid_ref = self._id_sleutel(lid.id)
            nr = nummer_van(lid.nummer)
            vindplaats = f"{artikel_vindplaats}, lid {nr}" if nr else artikel_vindplaats
            self.batch.node(
                "Lid",
                {
                    "id": lid.id,
                    "nummer": lid.nummer,
                    "vindplaats": vindplaats,
                    "tekst": lid.tekst,
                    "jci": lid.jci,
                    "ref_key": lid_ref,
                    "terugwerkend_tot": lid.terugwerkend_tot,
                    "voetnoot": lid.voetnoten,
                    "definieert_begrip": lid.definieert_begrippen,
                },
            )
            self.batch.rel("Artikel", "HEEFT_LID", "Lid", artikel.id, lid.id)
            self.summary.leden += 1
            if vorige_lid is not None:
                self.batch.rel("Lid", "VOLGT_OP", "Lid", lid.id, vorige_lid)
            vorige_lid = lid.id

            bron = lid_ref or artikel_ref_key
            self._verwijzingen(bron, lid.verwijzingen, lid.tekst)
            self._illustraties("Lid", lid.id, lid.illustraties)
            self._onderdelen(lid.onderdelen, lid.id, "Lid", bron, _Plek(vindplaats, ("Lid", lid.id)))

    def _onderdelen(
        self,
        onderdelen: list[Onderdeel],
        ouder_id: str,
        ouder_ent: str,
        erf_ref_key: str,
        plek: _Plek,
    ) -> None:
        """``erf_ref_key`` is de ref_key van de dichtstbijzijnde voorouder;
        onderdelen zonder eigen jci schrijven hun verwijzingen daaraan toe.

        ``plek`` geeft elk onderdeel zijn vindplaats ("Artikel 2, lid 1, onderdeel a, 1°", zoals
        `bronmodel.vindplaats`) en zijn bepaling (`bwb:inBepaling`), uit de echte boom: de IRI van een
        onderdeel van een beleidsregel zegt niet waar het staat (`…:artikel:9:o:d` hangt onder divisie
        9.2). Een ongenummerd opsommingsteken heeft geen eigen naam: het heet zoals zijn ouder.

        **De volgorde.** `bwb:volgnummer` is de plek in het document, voor een query die op één
        niveau sorteert: de IRI's van een regeling zeggen dat niet (`…:o:aa` staat lexicaal vóór
        `…:o:b`, en een slottekst heeft een `:id:`-IRI). `bronmodel` leest `bwb:volgtOp` en sorteert
        verder op nummer. Alleen onderdelen met een slottekst ertussen krijgen die keten: een node
        zonder nummer staat anders vooraan, terwijl de rest van de regeling ongewijzigd blijft en
        haar snapshot-id houdt."""
        keten = any(o.slottekst for o in onderdelen)
        vorige: str | None = None
        for onderdeel in onderdelen:
            nr = nummer_van(onderdeel.nummer)
            if not nr:
                vindplaats, genummerd = plek.vindplaats, plek.in_onderdeel
            elif plek.in_onderdeel:
                vindplaats, genummerd = f"{plek.vindplaats}, {nr}", True
            else:
                vindplaats, genummerd = f"{plek.vindplaats}, onderdeel {nr}", True
            ref_key, soort = jci_doel_ref_key(onderdeel.jci)
            if soort != "onderdeel" or self._in_bijlage:
                # Een onderdeel van een bijlage draagt `&bijlage=1&o=a`: geen artikel, dus de
                # jci-sleutel valt terug op de hele regeling. Alle onderdelen van de bijlage
                # landden zo op `urn:bwb:<bwb>` (Awb, Uitvoeringsregeling IW 1990). Dan de
                # wet-lokale by_id-IRI, zoals de bijlage zelf. Binnen een artikel van de bijlage
                # geldt hetzelfde: die jci laat de bijlage weg uit de sleutel.
                ref_key = None
            self._onderdeel_teller += 1
            self.batch.node(
                "Onderdeel",
                {
                    "id": onderdeel.id,
                    "nummer": onderdeel.nummer,
                    "label": "Slottekst" if onderdeel.slottekst else None,
                    "volgnummer": self._onderdeel_teller,
                    "tekst": onderdeel.tekst,
                    "ref_key": ref_key,
                    "jci": onderdeel.jci,
                    "vindplaats": vindplaats,
                    "voetnoot": onderdeel.voetnoten,
                    "definieert_begrip": onderdeel.definieert_begrippen,
                },
            )
            self.batch.rel(ouder_ent, "HEEFT_ONDERDEEL", "Onderdeel", ouder_id, onderdeel.id)
            self.batch.rel("Onderdeel", "IN_BEPALING", plek.bepaling[0], onderdeel.id, plek.bepaling[1])
            self.summary.onderdelen += 1
            if keten and vorige is not None:
                self.batch.rel("Onderdeel", "VOLGT_OP", "Onderdeel", onderdeel.id, vorige)
            vorige = onderdeel.id

            bron = ref_key or erf_ref_key
            self._verwijzingen(bron, onderdeel.verwijzingen, onderdeel.tekst)
            self._illustraties("Onderdeel", onderdeel.id, onderdeel.illustraties)
            self._onderdelen(onderdeel.subonderdelen, onderdeel.id, "Onderdeel", bron,
                             _Plek(vindplaats, plek.bepaling, genummerd))

    def _verwijzingen(self, ref_key: str, refs: list[Verwijzing], tekst: str | None) -> None:
        """Voeg de verwijzingen van één bron-node toe aan de batch.

        ``ref_key`` is de bronsleutel. Elk jci-doel wordt geresolveerd naar het
        meest specifieke niveau (wet/structuurdeel/artikel/lid/onderdeel); een
        verwijzing zonder jci valt terug op ``doel_pad``. Daarna detecteert de
        tekstuele fallback ongetagde verwijzingen in de lopende tekst
        (``soort=tekstueel``, ``betrouwbaarheid=laag``).
        """
        gezien: set[tuple[str, ...]] = set()
        artikelnummers: set[str] = set()

        for verwijzing in refs:
            # `jci_node_ref_key` en niet `jci_doel_ref_key`: draagt de jci van de verwijzing het
            # volledige structuurpad (`&hoofdstuk=VIII&afdeling=2`), dan is dat exact de sleutel van
            # de doelnode en hoeft er niets geraden te worden. Voor artikel-, lid- en
            # onderdeeldoelen delegeert de functie naar `jci_doel_ref_key`, dus daar verandert niets.
            #
            # Dit was aanvankelijk NIET zo, en dat kostte 45 verwijzingen: het pad stond gewoon in
            # de `doc` van de verwijzing, maar het doel werd met de platte sleutel gebouwd waarna
            # `_koppel_structuurverwijzingen` moest gokken tussen tien "afdeling 2"-kandidaten — en
            # terecht weigerde. De informatie was er; ze werd alleen weggegooid.
            to_key, doel_soort = jci_node_ref_key(verwijzing.doc)
            to_bwb, to_art, to_lid = jci_doel(verwijzing.doc)
            if to_key is None:
                # Zonder jci: val terug op het doel-pad (bwb-ng-variabel-deel);
                # dat mint dezelfde IRI als de doel-node zelf (by_id-schema).
                if not verwijzing.doel_pad:
                    continue
                to_bwb = verwijzing.doel_bwb_id or self._bwb
                to_key = f"{to_bwb}#id={to_bwb}{verwijzing.doel_pad}"
                doel_soort = "pad"
            if to_art:
                artikelnummers.add(to_art)
            if to_key == ref_key:
                continue  # zelfverwijzing
            # De jci noemt alleen het artikel; lid en onderdeel staan in de tekst. Of ze bestaan,
            # beslist `koppel_deelverwijzingen`, als alle wetten van de run bekend zijn.
            delen = deeldoelen(verwijzing.tekst, to_art) if doel_soort == "artikel" else []
            sleutels = [d.sleutel(to_key) for d in delen]
            sleutel = (to_key, verwijzing.soort.value, *sleutels)
            if sleutel in gezien:
                continue
            gezien.add(sleutel)
            self.batch.verwijzingen.append(
                {
                    "from": ref_key,
                    "to": to_key,
                    "deelsleutels": sleutels,
                    "to_bwb": to_bwb,
                    "to_nummer": _doel_nummer(to_key, doel_soort, to_art),
                    "doel_lid": ", ".join(d.lid for d in delen if d.lid) or to_lid,
                    "doel_soort": doel_soort,
                    "doel_pad": verwijzing.doel_pad,
                    "soort": verwijzing.soort.value,
                    "doc": verwijzing.doc,
                    "anker_tekst": verwijzing.tekst or None,
                    "verwijzing_id": verwijzing.verwijzing_id,
                }
            )

        if not (self._tekstuele_refs and tekst):
            return
        for verwijzing in detect_textual_references(tekst, eigen_bwb_id=self._bwb):
            # "Artikel 16" zonder wet is in de wettekst een eigen artikel, maar in een bijlage niet:
            # Bijlage 2 van de Awb somt op die manier bepalingen van ándere wetten op.
            if self._in_bijlage and verwijzing.doel_bwb_id == self._bwb:
                continue
            # Ankertekst van een al gestructureerde verwijzing (zelfde
            # artikelnummer) opnieuw detecteren zou een dubbele/onterechte
            # edge opleveren -> overslaan.
            if verwijzing.doel_artikel in artikelnummers:
                continue
            to_key = f"{verwijzing.doel_bwb_id}#artikel={verwijzing.doel_artikel}"
            sleutel = (to_key, verwijzing.soort.value)
            if to_key == ref_key or sleutel in gezien:
                continue
            gezien.add(sleutel)
            self.batch.verwijzingen.append(
                {
                    "from": ref_key,
                    "to": to_key,
                    "to_bwb": verwijzing.doel_bwb_id,
                    "to_nummer": verwijzing.doel_artikel,
                    "doel_lid": None,
                    "doel_soort": "artikel",
                    "doel_pad": None,
                    "soort": verwijzing.soort.value,
                    "doc": None,
                    "anker_tekst": verwijzing.tekst,
                    "verwijzing_id": None,
                    "betrouwbaarheid": "laag",
                }
            )


def _doel_nummer(to_key: str, doel_soort: str | None, to_art: str | None) -> str | None:
    """Het "nummer" van het verwijsdoel: artikelnummer of structuurnummer."""
    if doel_soort in _ARTIKEL_SOORTEN:
        return to_art
    if doel_soort in STRUCT_LABEL:
        return to_key.rpartition("=")[2]
    return None


# Structuursoorten waarvan de NODE-sleutel het volledige pad draagt terwijl een verwijzing vaak
# alleen het laatste segment schrijft. Artikel/lid/onderdeel staan er niet bij: die sleutels zijn
# aan beide kanten gelijk.
_STRUCTUURSOORTEN = ("hoofdstuk", "titeldeel", "afdeling", "paragraaf")

_STRUCTUURENTITEITEN = ("Hoofdstuk", "Titeldeel", "Afdeling", "Paragraaf")


def structuurindex(batches: Iterable[Batch]) -> dict[str, str]:
    """Padloze sleutel -> volledige ref_key, over ALLE wetten van deze import heen.

    Waarom dit over de hele batch gaat en niet per wet. Een verwijzing duidt haar doel vaak
    onvolledig aan: de bron schrijft `jci1.3:c:BWBR0005537&titeldeel=5.1`, zonder het hoofdstuk,
    terwijl de node sinds de collisie-fix `{bwb}#hoofdstuk=5#titeldeel=5.1` heet. Binnen de eigen
    wet viel dat nog te repareren, maar juist **cross-wet** niet: importeer je de Invorderingswet,
    dan zit de structuur van de Awb niet in díe batch.

    Dat was geen echte onbekende — `run_imports` haalt alle wetten in één run binnen. De informatie
    bestond dus wel, alleen op het verkeerde moment: we schreven de citerende wet weg vóórdat de
    doelwet was gezien. Verzamelen vóór schrijven haalt die volgorde-afhankelijkheid weg.

    **Alleen ondubbelzinnige nummers komen erin.** Heeft een wet twee keer "afdeling 1" (het geval
    dat de hele collisie veroorzaakte), dan is de onvolledige verwijzing zelf ambigu en hoort ze
    onopgelost te blijven: een open stub is een zichtbaar gat, een gok is schijnzekerheid.
    """
    kandidaten: dict[str, set[str]] = {}
    for batch in batches:
        for entiteit in _STRUCTUURENTITEITEN:
            for props in batch.nodes.get(entiteit, []):
                ref_key, nummer, soort = props.get("ref_key"), props.get("nummer"), props.get("soort")
                if not ref_key or not nummer or not soort:
                    continue
                bwb, _, _rest = ref_key.partition("#")
                padloos = f"{bwb}#{soort}={nummer}"
                if padloos == ref_key:
                    continue  # sleutel draagt al geen pad; er valt niets op te lossen
                kandidaten.setdefault(padloos, set()).add(ref_key)
    return {k: next(iter(v)) for k, v in kandidaten.items() if len(v) == 1}


def koppel_structuurverwijzingen(batch: Batch, index: dict[str, str]) -> int:
    """Laat onvolledig aangeduide structuurverwijzingen op de juiste node uitkomen.

    Een **exacte lookup**, geen staartmatch: de index bepaalt of het nummer ondubbelzinnig is, en
    doet dat één keer voor alle wetten samen. De vorige opzet zocht per wet naar een sleutel die op
    `#afdeling=1` eindigde — dat werkte binnen één wet en principieel niet daarbuiten.

    Geeft terug hoeveel verwijzingen zijn gekoppeld (voor de logregel).
    """
    gekoppeld = 0
    for rij in batch.verwijzingen:
        to_key = rij.get("to")
        if rij.get("doel_soort") not in _STRUCTUURSOORTEN or not to_key:
            continue
        volledig = index.get(to_key)
        if volledig and volledig != to_key:
            rij["to"] = volledig
            gekoppeld += 1
    return gekoppeld


def bepalingsindex(batches: Iterable[Batch]) -> set[str]:
    """De sleutels van alle leden en onderdelen in deze run, over de wetten heen."""
    return {
        props["ref_key"]
        for batch in batches
        for entiteit in ("Lid", "Onderdeel")
        for props in batch.nodes.get(entiteit, [])
        if props.get("ref_key")
    }


def _meest_specifiek(sleutel: str, bekend: set[str]) -> str | None:
    """De sleutel zelf of de dichtstbijzijnde ouder die bestaat: onderdeel, dan lid, nooit het artikel."""
    while "#lid=" in sleutel or "#o=" in sleutel:
        if sleutel in bekend:
            return sleutel
        sleutel = sleutel.rpartition("#")[0]
    return None


def koppel_deelverwijzingen(batch: Batch, bekend: set[str]) -> int:
    """Laat een verwijzing uitkomen op het lid of onderdeel dat haar tekst noemt.

    De jci van een verwijzing stopt bij het artikel, de tekst niet: "artikel 25, derde lid". Daarom
    wijst `bwb:verwijstNaar` naar elk genoemd lid of onderdeel dat echt bestaat, ook als het er meer
    zijn ("eerste en tweede lid"). Bestaat een onderdeel niet, dan het lid eromheen.

    **Het artikel is de terugval**, en `bwb:doelLid` bewaart dan wat de tekst noemde. Dat is ook de
    uitkomst voor een doel in een wet die niet in de run zit: een open lid-IRI is van geen enkele
    query te bereiken, het artikel wel. Dezelfde lijn als `structuurindex`: wat niet vaststaat, wordt
    niet gegokt.

    Geeft terug hoeveel verwijzingen fijner zijn geworden (voor de logregel).
    """
    gekoppeld = 0
    rijen: list[dict] = []
    gezien: set[tuple[str, str, str]] = set()

    def voeg_toe(rij: dict) -> None:
        sleutel = (rij["from"], rij["to"], rij["soort"])
        if sleutel not in gezien and rij["from"] != rij["to"]:
            gezien.add(sleutel)
            rijen.append(rij)

    for rij in batch.verwijzingen:
        doelen = dict.fromkeys(
            d for d in (_meest_specifiek(s, bekend) for s in rij.pop("deelsleutels", [])) if d
        )
        if not doelen:
            voeg_toe(rij)
            continue
        gekoppeld += 1
        for doel in doelen:
            lid = re.search(r"#lid=([^#]+)", doel)
            voeg_toe(
                {
                    **rij,
                    "to": doel,
                    "doel_soort": "onderdeel" if "#o=" in doel else "lid",
                    "doel_lid": lid.group(1) if lid else None,
                }
            )
    batch.verwijzingen[:] = rijen
    return gekoppeld


def collect(wet: Wet, *, tekstuele_refs: bool = True) -> tuple[Batch, ImportSummary]:
    """Loop de wet één keer door en geef de verzamelde ``Batch`` + telling terug."""
    collector = _Collector(wet, tekstuele_refs=tekstuele_refs)
    collector.run(wet)
    return collector.batch, collector.summary
