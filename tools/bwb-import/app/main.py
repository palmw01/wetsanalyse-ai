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

from app.collect import Batch, collect, structuurindex
from app.config import Settings
from app.dekking import Dekking, bron_tekens
from app.downloader import BwbDownloader
from app.graphdb_writer import GraphDbWriter
from app.models import ImportResult, ImportSummary, ToestandRef, Wet
from app.parser import ToestandParser
from app.rdf_vocab import Vocab
from app.wti_parser import WtiInfo, WtiParser

logger = logging.getLogger(__name__)


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


def run_import(
    bwb_id: str, settings: Settings, writer: GraphDbWriter | None = None
) -> ImportSummary:
    """Voer de volledige importpijplijn uit voor één regeling.

    Zonder meegegeven ``writer`` (losse aanroep) worden de waarborgen
    (:func:`prepare`) eerst uitgevoerd; in een batch gebeurt dat één keer.

    De structuurindex bevat hier alleen déze wet — een verwijzing naar een structuurdeel van een
    ándere regeling blijft dus een open stub. Dat is geen tekortkoming van deze functie maar de
    grens van één import: die kennis bestaat pas als de doelwet is gezien. `run_imports` haalt alle
    wetten in één run binnen en heeft die grens niet.
    """
    logger.info("Start import voor %s (doel: GraphDB %s)", bwb_id, settings.graphdb_repository)

    if writer is None:
        writer = maak_writer(settings)
        prepare(writer)

    item = _verzamel(bwb_id, settings)
    return _schrijf(item, writer, structuurindex([item.batch]))


def _haal_en_parse(bwb_id: str, settings: Settings) -> tuple[Wet, WtiInfo | None, Path]:
    """Download de laatste toestand, valideer tegen het XSD en parse hem tot een ``Wet``."""
    downloader = BwbDownloader(settings)
    toestand = downloader.latest_toestand(bwb_id)
    xml_path = downloader.download_toestand(bwb_id, toestand)

    schema_path = settings.schemas_dir / "toestand.xsd"
    parser = ToestandParser(schema_path=schema_path if settings.validate_xsd else None)
    if settings.validate_xsd:
        parser.validate(xml_path)

    wet = parser.parse(xml_path)
    # Geldigheidsvenster uit de SRU-index aanvullen.
    wet.geldig_vanaf = toestand.geldig_vanaf or wet.geldig_vanaf
    wet.geldig_tot = toestand.geldig_tot

    wti = _laad_wti(downloader, toestand) if settings.import_wti else None
    return wet, wti, xml_path


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
    logger.info(
        "Structuurindex: %d ondubbelzinnige padloze sleutels over %d wetten",
        len(index), len(verzameld),
    )

    # Fase 2 – schrijven, met de index van álle wetten bij de hand.
    geschreven: dict[str, ImportSummary] = {}
    for item in verzameld:
        try:
            geschreven[item.wet.bwb_id] = _schrijf(item, writer, index)
        except Exception as exc:  # noqa: BLE001 - batch loopt door, fout per wet
            logger.error("Schrijven mislukt voor %s: %s", item.wet.bwb_id, exc)
            mislukt[item.wet.bwb_id] = str(exc)

    # De volgorde van `bwb_ids` aanhouden: het overzicht leest zoals de gebruiker het opgaf.
    resultaten: list[ImportResult] = []
    for bwb_id in bwb_ids:
        if bwb_id in geschreven:
            resultaten.append(ImportResult(bwb_id=bwb_id, ok=True, overzicht=geschreven[bwb_id]))
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


def _verzamel(bwb_id: str, settings: Settings) -> _Verzameld:
    """Downloaden, valideren, parsen en verzamelen – alles behalve schrijven."""
    logger.info("Verzamelen voor %s", bwb_id)
    wet, wti, xml_path = _haal_en_parse(bwb_id, settings)
    batch, summary = collect(wet, tekstuele_refs=settings.detect_tekstuele_refs)
    return _Verzameld(wet=wet, wti=wti, batch=batch, summary=summary, xml_path=xml_path)


def _schrijf(item: _Verzameld, writer: GraphDbWriter, index: dict[str, str]) -> ImportSummary:
    """Schrijf één verzamelde wet weg, met de structuurindex van de hele batch."""
    summary = writer.write_wet(
        item.wet,
        wti=item.wti,
        verzameld=(item.batch, item.summary),
        structuurindex=index,
    )
    _meet_dekking(summary, item.xml_path, item.wet.bwb_id)
    logger.info("Import voltooid voor %s", item.wet.bwb_id)
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

    Resultaten zonder meting (`bron_tekens == 0`) tellen niet mee. De meting zit in `run_import` in
    een `try` — ze mag de import nooit breken — en een mislukte meting is geen bewijs van een gat.
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
    2 = de tekstdekking zakte onder `BWB_MIN_DEKKING`.

    Die twee foutcodes staan los van elkaar omdat ze om iets anders vragen. Een 1 betekent dat er
    een wet níét geschreven is; een 2 betekent dat alles geschreven is maar dat er tekst ontbreekt
    ten opzichte van de bron — de graaf is dan even compleet als hij zonder deze controle geweest
    zou zijn, want `write_wet` schrijft de named graph vóórdat er iets te meten valt. Een 2 is dus
    een signaal, geen dataverlies.
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
    args = parser.parse_args(argv)
    bwb_ids = args.bwb_ids or [settings.default_bwb_id]

    resultaten = run_imports(bwb_ids, settings)
    for resultaat in resultaten:
        if resultaat.ok and resultaat.overzicht:
            _print_overzicht(resultaat.overzicht)
        else:
            logger.error("Import mislukt voor %s: %s", resultaat.bwb_id, resultaat.fout)

    if not all(r.ok for r in resultaten):
        return 1
    # Pas ná alle imports: de batch moet doorlopen zodat één dip de andere regelingen niet
    # tegenhoudt, en op dit punt staat de graaf toch al volledig geschreven.
    if settings.min_dekking > 0 and _dekkingsrapport(resultaten, settings.min_dekking):
        logger.error(
            "Tekstdekking onder de drempel (%.1f%%). De graaf is geschreven, maar er ontbreekt "
            "tekst ten opzichte van de bron-XML.",
            settings.min_dekking * 100,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
