"""Orkestratie van de BWB-import: download -> validatie -> parse -> GraphDB.

Na ``python main.py`` wordt de toestand-XML gedownload, gevalideerd tegen het
XSD, geparsed en als RDF weggeschreven naar GraphDB, gevolgd door een overzicht
van het aantal geïmporteerde elementen en relaties.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from bronmodel.bwb.models import ImportResult, ImportSummary, ToestandRef, Wet
from bronmodel.bwb.parser import ToestandParser

from app.collect import Batch, bepalingsindex, collect, structuurindex
from app.config import Settings
from app.dekking import Dekking, Stand, bron_tekens, poortbesluit
from app.downloader import BwbDownloader
from app.graphdb_writer import GraphDbWriter
from app.rdf_vocab import Vocab
from app.wti_parser import WtiInfo, WtiParser

logger = logging.getLogger(__name__)


class LegeToestand(RuntimeError):
    """De bron leverde geen tekst op. Dat is geen regeling, en die schrijven we nooit weg."""


def maak_writer(settings: Settings) -> GraphDbWriter:
    return GraphDbWriter(
        url=settings.graphdb_url,
        repository=settings.graphdb_repository,
        vocab=Vocab(base=settings.graphdb_base_iri, ontology=settings.graphdb_ontology_iri),
        user=settings.graphdb_user,
        password=settings.graphdb_password,
        tekstuele_refs=settings.detect_tekstuele_refs,
    )


def prepare(writer: GraphDbWriter) -> None:
    """Eenmalige waarborgen per (batch-)import: repo, ontologie, FTS-index."""
    writer.ensure_constraints()
    writer.write_ontology()
    writer.ensure_fts_connector()


def _haal_en_parse(
    bwb_id: str, settings: Settings
) -> tuple[Wet, WtiInfo | None, Path, bool | None]:
    """Download de laatste toestand, valideer tegen het XSD en parse hem tot een ``Wet``."""
    downloader = BwbDownloader(settings)
    toestand = downloader.latest_toestand(bwb_id)
    xml_path = downloader.download_toestand(bwb_id, toestand)

    schema_path = settings.schemas_dir / "toestand.xsd"
    parser = ToestandParser(schema_path=schema_path if settings.validate_xsd else None)
    xsd_geldig = parser.validate(xml_path) if settings.validate_xsd else None

    wet = parser.parse(xml_path)
    # Geldigheidsvenster uit de SRU-index aanvullen.
    wet.geldig_vanaf = toestand.geldig_vanaf or wet.geldig_vanaf
    wet.geldig_tot = toestand.geldig_tot

    wti = _laad_wti(downloader, toestand) if settings.import_wti else None
    return wet, wti, xml_path, xsd_geldig


def _laad_wti(downloader: BwbDownloader, toestand: ToestandRef) -> WtiInfo | None:
    """Download en parse de WTI; verrijking is best-effort (nooit blokkerend)."""
    try:
        wti_path = downloader.download_wti(toestand)
        if wti_path is None:
            logger.warning("Geen WTI-locatie bekend voor %s", toestand.bwb_id)
            return None
        return WtiParser().parse(wti_path)
    except Exception as exc:  # noqa: BLE001 - verrijking mag de import niet breken
        logger.warning("WTI-verrijking overgeslagen voor %s: %s", toestand.bwb_id, exc)
        return None


def run_imports(bwb_ids: list[str], settings: Settings) -> list[ImportResult]:
    """Importeer meerdere regelingen met één gedeelde writer: eerst verzamelen, dan schrijven.

    **Waarom twee fasen en niet één lus.** Een verwijzing duidt haar doel vaak onvolledig aan — de
    bron schrijft `jci1.3:c:BWBR0005537&titeldeel=5.1` zonder het hoofdstuk, terwijl dat titeldeel
    sinds de collisie-fix `{bwb}#hoofdstuk=5#titeldeel=5.1` heet. Los je dat op tijdens de import
    van de *citerende* wet, dan kan het per definitie niet voor een doel in een ándere wet: die is
    dan nog niet gezien. Zo landden 26 verwijzingen die daarvoor gewoon werkten op een lege node.

    Dat was geen echt informatiegat. Alle wetten komen in één run binnen; de kennis bestond, alleen
    op het verkeerde moment. Fase 1 verzamelt daarom álle wetten (parsen gebeurt nog steeds één keer
    per wet, dus de dure XSD-validatie wordt niet verdubbeld), fase 2 bouwt daaruit één
    structuurindex en schrijft de named graphs. Geheugen is geen bezwaar: alle wettekst samen is
    ~1,4 MB en de job draait op 2 GiB.

    Dit vervangt de eerdere reparatie die per wet naar een sleutel zocht die op `#afdeling=1`
    eindigde. Zo'n staartmatch is een gok zodra er meerdere kandidaten zijn; de index beslist dat
    één keer, expliciet, en laat een écht ambigue verwijzing bewust onopgelost.

    Per wet idempotent (named-graph PUT); een falende wet breekt de batch niet – de fout komt in het
    per-wet resultaat terecht, in welke fase hij ook optreedt.
    """
    writer = maak_writer(settings)
    prepare(writer)

    # Fase 1 – verzamelen. Een wet die hier sneuvelt (download, XSD, parse) ontbreekt simpelweg in
    # de index; de rest van de batch gaat gewoon door.
    verzameld: list[_Verzameld] = []
    mislukt: dict[str, str] = {}
    for bwb_id in bwb_ids:
        try:
            verzameld.append(_verzamel(bwb_id, settings))
        except Exception as exc:  # noqa: BLE001 - batch loopt door, fout per wet
            logger.error("Verzamelen mislukt voor %s: %s", bwb_id, exc)
            mislukt[bwb_id] = str(exc)

    index = structuurindex(v.batch for v in verzameld)
    bepalingen = bepalingsindex(v.batch for v in verzameld)
    logger.info(
        "Structuurindex: %d ondubbelzinnige padloze sleutels over %d wetten",
        len(index), len(verzameld),
    )

    # De stand voor de importpoort. Faalt dit, dan stopt de run: terugvallen op "er staat niets"
    # zou de poort stil openzetten, en die bestaat juist om een goede graph te beschermen.
    stand = writer.graaf_stand([v.wet.bwb_id for v in verzameld]) if verzameld else {}

    # Fase 2 – schrijven, met de index van álle wetten bij de hand.
    verwerkt: dict[str, ImportSummary] = {}
    for item in verzameld:
        try:
            verwerkt[item.wet.bwb_id] = _schrijf(item, writer, index, bepalingen, stand, settings)
        except Exception as exc:  # noqa: BLE001 - batch loopt door, fout per wet
            logger.error("Schrijven mislukt voor %s: %s", item.wet.bwb_id, exc)
            mislukt[item.wet.bwb_id] = str(exc)

    # Fase 3 – de similarity-index, en pas hier. Anders dan de Lucene-connector (die live meeloopt
    # met wat er wordt geschreven) is een similarity-index een momentopname: hij wordt bij het
    # aanmaken getraind over wat er op dát moment staat. In `prepare()` zou hij dus over een lege
    # graaf worden gebouwd en daarna nooit iets vinden.
    geschreven = [bwb_id for bwb_id, summary in verwerkt.items() if not summary.tegengehouden]
    if geschreven:
        # Kwam er een wet bij, dan mist een bestaande index die: bijvoorbeeld na een run waarin ze mislukte.
        writer.ensure_similarity_index(herbouw=any(not stand[b].tekens for b in geschreven if b in stand))

    # De volgorde van `bwb_ids` aanhouden: het overzicht leest zoals de gebruiker het opgaf.
    resultaten: list[ImportResult] = []
    for bwb_id in bwb_ids:
        if bwb_id in verwerkt:
            resultaten.append(ImportResult(bwb_id=bwb_id, ok=True, overzicht=verwerkt[bwb_id]))
        else:
            resultaten.append(
                ImportResult(bwb_id=bwb_id, ok=False, fout=mislukt.get(bwb_id, "onbekende fout"))
            )
    return resultaten


@dataclass(frozen=True)
class _Verzameld:
    """Wat fase 1 per wet oplevert en fase 2 nodig heeft."""

    wet: Wet
    wti: WtiInfo | None
    batch: Batch
    summary: ImportSummary
    xml_path: Path
    xsd_geldig: bool | None = None


def _verzamel(bwb_id: str, settings: Settings) -> _Verzameld:
    """Downloaden, valideren, parsen en verzamelen – alles behalve schrijven."""
    logger.info("Verzamelen voor %s", bwb_id)
    wet, wti, xml_path, xsd_geldig = _haal_en_parse(bwb_id, settings)
    batch, summary = collect(wet, tekstuele_refs=settings.detect_tekstuele_refs)
    return _Verzameld(
        wet=wet, wti=wti, batch=batch, summary=summary, xml_path=xml_path, xsd_geldig=xsd_geldig
    )


def _schrijf(
    item: _Verzameld,
    writer: GraphDbWriter,
    index: dict[str, str],
    bepalingen: set[str],
    stand: dict[str, Stand],
    settings: Settings,
) -> ImportSummary:
    """Bouw één verzamelde wet, meet hem, en schrijf hem pas als de importpoort dat toestaat.

    De volgorde is het punt: een named-graph PUT vervangt alles, dus een controle erna kan niets
    meer tegenhouden.
    """
    bwb_id = item.wet.bwb_id
    graph, summary = writer.build_graph(
        item.wet,
        wti=item.wti,
        verzameld=(item.batch, item.summary),
        structuurindex=index,
        bepalingsindex=bepalingen,
    )
    summary.graaf_tekens = writer.tel_tekens(graph)
    summary.xsd_geldig = item.xsd_geldig
    if item.xsd_geldig is False:
        logger.warning("XSD-validatie mislukt voor %s; de import gaat door", bwb_id)
    _meet_dekking(summary, item.xml_path, bwb_id)
    if summary.graaf_tekens <= 0:
        raise LegeToestand(f"{bwb_id}: de toestand levert geen tekst op; niet geschreven")

    besluit = poortbesluit(
        Dekking(bwb_id, summary.bron_tekens, summary.graaf_tekens),
        stand.get(bwb_id, Stand()),
        drempel=settings.min_dekking,
        wti_mislukt=settings.import_wti and item.wti is None,
        overgeslagen=item.wet.overgeslagen,
    )
    summary.poort = besluit.reden
    summary.tegengehouden = not besluit.schrijven
    if besluit.reden:
        logger.warning("Importpoort %s: %s", bwb_id, besluit.reden)
    if besluit.schrijven:
        writer.vervang_wet(bwb_id, graph)
        logger.info("Import voltooid voor %s", bwb_id)
    return summary


def _meet_dekking(summary: ImportSummary, xml_path: Path, bwb_id: str) -> None:
    try:
        summary.bron_tekens = bron_tekens(xml_path)
    except Exception:  # noqa: BLE001 - een meting mag de import nooit breken
        logger.warning("Dekkingsmeting overgeslagen voor %s", bwb_id, exc_info=True)


def _print_overzicht(summary: ImportSummary) -> None:
    regels = [
        ("Wet", summary.bwb_id),
        ("Wetten", summary.wetten),
        ("Hoofdstukken", summary.hoofdstukken),
        ("Afdelingen", summary.afdelingen),
        ("Paragrafen", summary.paragrafen),
        ("Divisies", summary.divisies),
        ("Artikelen", summary.artikelen),
        ("Leden", summary.leden),
        ("Onderdelen", summary.onderdelen),
        ("Relaties", summary.relaties),
    ]
    if summary.bron_tekens:
        dekking = summary.graaf_tekens / summary.bron_tekens
        mist = max(0, summary.bron_tekens - summary.graaf_tekens)
        regels.append(
            ("Tekstdekking", f"{dekking:.1%} ({summary.graaf_tekens}/{summary.bron_tekens})"
             + (f" – MIST {mist} tekens" if mist else ""))
        )
    if summary.xsd_geldig is not None:
        regels.append(("XSD", "geldig" if summary.xsd_geldig else "ONGELDIG"))
    if summary.poort:
        status = "NIET GESCHREVEN" if summary.tegengehouden else "geschreven"
        regels.append(("Importpoort", f"{status} – {summary.poort}"))
    breedte = max(len(label) for label, _ in regels)
    print("\n=== Import-overzicht ===")
    for label, waarde in regels:
        print(f"  {label.ljust(breedte)} : {waarde}")
    print()


def _dekkingsrapport(resultaten: list[ImportResult], drempel: float) -> list[Dekking]:
    """De regelingen die onder de drempel zakken, met een geconsolideerd overzicht op stdout.

    Waarom over álle regelingen heen en niet per wet: `_print_overzicht` toont de dekking al per
    import, maar bij zeven regelingen wil je in één blok zien wélke zakt en met hoeveel tekens. Een
    cijfer dat je moet opsporen tussen zeven overzichten is precies het probleem dat deze drempel
    oplost.

    Resultaten zonder meting (`bron_tekens == 0`) tellen niet mee. De meting zit in een `try` — ze
    mag de import nooit breken — en een mislukte meting is geen bewijs van een gat.
    """
    gemeten = [
        Dekking(
            bwb_id=r.overzicht.bwb_id,
            bron_tekens=r.overzicht.bron_tekens,
            graaf_tekens=r.overzicht.graaf_tekens,
        )
        for r in resultaten
        if r.ok and r.overzicht and r.overzicht.bron_tekens > 0
    ]
    tekort = [d for d in gemeten if d.verhouding < drempel]
    if tekort:
        print(f"\n=== Tekstdekking onder de drempel ({drempel:.1%}) ===")
        for dekking in gemeten:
            merk = "  ZAKT" if dekking in tekort else "  ok  "
            print(f"{merk}  {dekking.regel()}")
        print()
    return tekort


def main(argv: list[str] | None = None) -> int:
    """Importeer de opgegeven regelingen. Exitcodes: 0 = goed, 1 = een import mislukte,
    2 = de importpoort sloeg aan (dekking onder `BWB_MIN_DEKKING`, of de WTI mislukte).

    Die twee foutcodes staan los van elkaar omdat ze om iets anders vragen. Een 1 betekent dat een
    wet niet gelezen of geschreven kon worden. Een 2 betekent dat de inhoud niet klopt: de poort
    heeft de bestaande graph laten staan, of geschreven omdat er niets beters stond. De graaf gaat
    bij een 2 dus nooit achteruit, maar hij kan achterlopen op de bron: `dekking.poortbesluit`.
    """
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = Settings.from_env()

    parser = argparse.ArgumentParser(
        description="Importeer één of meer BWB-regelingen naar GraphDB."
    )
    parser.add_argument(
        "bwb_ids",
        nargs="*",
        default=[settings.default_bwb_id],
        help=f"BWB-id's van de regelingen (default: {settings.default_bwb_id})",
    )
    parser.add_argument(
        "--alleen-bij-verlies",
        action="store_true",
        help=(
            "Peil eerst of de graaf compleet is en importeer alleen als er iets ontbreekt. "
            "De stand van de graafwacht-job; zie GraphDbWriter.graaf_is_compleet."
        ),
    )
    args = parser.parse_args(argv)
    bwb_ids = args.bwb_ids or [settings.default_bwb_id]

    if args.alleen_bij_verlies and maak_writer(settings).graaf_is_compleet(bwb_ids):
        logger.info("Graaf is compleet; niets te doen (--alleen-bij-verlies).")
        return 0

    resultaten = run_imports(bwb_ids, settings)
    for resultaat in resultaten:
        if resultaat.ok and resultaat.overzicht:
            _print_overzicht(resultaat.overzicht)
        else:
            logger.error("Import mislukt voor %s: %s", resultaat.bwb_id, resultaat.fout)

    if not all(r.ok for r in resultaten):
        return 1
    # Pas ná alle imports: de batch moet doorlopen zodat één dip de andere regelingen niet tegenhoudt.
    dip = settings.min_dekking > 0 and _dekkingsrapport(resultaten, settings.min_dekking)
    signalen = [r for r in resultaten if r.overzicht and r.overzicht.poort]
    if dip or signalen:
        logger.error(
            "Importpoort sloeg aan bij %d regeling(en); %d graph(s) ongewijzigd gelaten.",
            len(signalen) or len(dip),
            sum(1 for r in resultaten if r.tegengehouden),
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
