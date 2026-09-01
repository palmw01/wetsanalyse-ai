"""Gestructureerde artikeltekst uit de graaf.

Eén bron voor zowel de **weergave** (documentpaneel in de workbench) als de **annotatie-corpus**: beide
komen uit `queries.get_artikel` op GraphDB, geparseerd via `parse_select`. Zo is er geen drift tussen
wat de jurist ziet en waartegen de brongetrouwheid van de agent wordt gecheckt.
"""
from __future__ import annotations

import logging
import re

from .graph import queries
from .graph.results import parse_select
from .ports import GraphPort

logger = logging.getLogger("graph_qa.artikel")


class OngeldigeVindplaats(ValueError):
    """De aanduiding kan geen bepaling zijn – een tikfout, geen lege graaf.

    Dit onderscheid bestond niet: één `except ValueError` dekte twee gevallen (de decimale-nummer-
    fallback, die bedoeld is, en echte invoerfouten, die dat niet zijn), waarna het endpoint 200 met
    een lege tekst gaf. De jurist zag dan een leeg documentpaneel zonder uitleg en kon niet zien of
    hij zich vertypte, of de graaf de bepaling niet kent, of de dienst stuk was.
    """

_NUM = re.compile(r"\d+")


def _lidsleutel(lid: str) -> tuple[int, str]:
    """Numeriek sorteren op lidnummer (de SPARQL ORDER BY ?lid is lexicaal: 1,10,11,2,…)."""
    m = _NUM.search(lid or "")
    return (int(m.group()) if m else 10**9, lid or "")


def _onderdeelsleutel(iri: str) -> list[tuple[int, str]]:
    """Documentvolgorde uit het onderdeel-IRI, cijferreeksen als getal.

    Dezelfde les als bij `_lidsleutel`, één niveau dieper en nooit toegepast. Het onderdeel-id komt
    uit `bwb-ng-variabel-deel` en codeert het volledige documentpad
    (".../Opsomming_1/Onderdeel._8/Onderdeela"), dus de volgorde zít in de data — alleen lexicaal
    sorteren haalt hem eruit als 1, 10, 11, 12, 13, 2, 3, … Nagemeten op Leidraad-bepaling 26.1.9:
    lexicaal reproduceert de documentvolgorde niet, natuurlijk sorteren exact.

    Waarom hier en niet in de SPARQL: `get_bepaling_corpus` heeft een `ORDER BY ?o` die op de IRI
    als string sorteert, en `get_artikel_corpus` heeft er helemaal geen. In Python sorteren maakt
    het corpus onafhankelijk van wat GraphDB teruggeeft.
    """
    return [(int(deel), "") if deel.isdigit() else (-1, deel)
            for deel in re.split(r"(\d+)", iri or "") if deel]


def _match_lid(lidnummer: str, lid: str) -> bool:
    """Vergelijk lidnummers robuust ('1' == '01'); valt terug op string-gelijkheid."""
    a, b = _lidsleutel(lidnummer), _lidsleutel(lid)
    if a[0] != 10**9 and b[0] != 10**9:
        return a[0] == b[0]
    return (lidnummer or "").strip() == (lid or "").strip()


def _bepaling_fallback(bwb_id: str, artikel: str, graph: GraphPort) -> list[dict]:
    """Beleidsregels/circulaires (decimale nummers zoals '9.1') gaan niet via het artikel/lid-IRI-
    patroon; haal ze dan op via `bwb:nummer`.

    Mét de onderdelen, om dezelfde reden als bij een lid: bij zo'n bepaling zit de inhoud er vaak
    ín. Bepaling 26.1.9 van de Leidraad Invordering 2008 heeft 221 tekens eigen tekst ("Er wordt
    geen kwijtschelding verleend als:") en 16 onderdelen met 6128 tekens — 96% van de bepaling. In
    de hele Leidraad geldt dat voor 153 van de 800 bepalingen, samen goed voor 99.329 tekens die
    hiervóór uit het corpus vielen. Wie zo'n bepaling annoteerde, markeerde de aankondiging en miste
    de opsomming — en bij een voorwaardenlijst is dat precies de inhoud.

    Geen lidnummer: een bepaling heeft er geen, en `regelsVan` in de frontend rendert een lege `lid`
    zonder voorvoegsel.
    """
    try:
        rows = parse_select(graph.sparql(queries.get_bepaling_corpus(bwb_id, artikel)))
    except ValueError:
        return []
    tekst = next((r.get("tekst") for r in rows if (r.get("tekst") or "").strip()), "")
    # Géén vroege uitstap op lege tekst: zes bepalingen in de Leidraad hebben alleen onderdelen
    # (14.2.4, 14.2a, 25.4.6, 73.3a.2, …). Die waren daardoor niet te openen en niet te annoteren.
    regels = [tekst.strip()] if tekst.strip() else []
    # Documentvolgorde, om dezelfde reden als bij `_vouw_onderdelen_in`: `get_bepaling_corpus`
    # sorteert met `ORDER BY ?o` op de IRI als string, en dat is niet de volgorde van de wet.
    for r in sorted(rows, key=lambda r: _onderdeelsleutel(str(r.get("o") or ""))):
        onderdeel = _onderdeelregel(r)
        if onderdeel and onderdeel not in regels:
            regels.append(onderdeel)
    return [{"lid": "", "tekst": "\n".join(regels)}] if regels else []


def _controleer_vindplaats(bwb_id: str, artikel: str, lid: str | None) -> None:
    """Kan dit überhaupt een bepaling aanduiden? Zo nee: een tikfout, en dat is iets anders dan niets
    gevonden. De query-bouwers valideren streng; hier vragen we ze dat alvast, vóór er een SPARQL de
    deur uit gaat."""
    try:
        queries.regeling_iri(bwb_id)
    except ValueError as exc:
        raise OngeldigeVindplaats(str(exc)) from exc
    # Een artikelnummer ('9', '22a') óf een bepaling-nummer ('9.1'): één van de twee moet passen.
    for bouwer in (queries._art, queries._nummer_vrij):
        try:
            bouwer(artikel)
            break
        except ValueError:
            continue
    else:
        raise OngeldigeVindplaats(f"Ongeldige aanduiding: {artikel!r} (verwacht bv. '9', '22a' of '9.1').")
    if lid and str(lid).strip():
        try:
            queries._num(str(lid))
        except ValueError as exc:
            raise OngeldigeVindplaats(str(exc)) from exc


def _vouw_onderdelen_in(rows: list[dict]) -> list[dict]:
    """Eén regel per lid, met zijn onderdelen eronder.

    De query levert één rij per (lid, onderdeel); hier worden die weer één tekst. Onderdelen komen
    op een eigen regel achter hun nummer ("a. rijksbelastingen: …"), zonder inspringing — witruimte
    wordt deel van het corpus en dus van elke fragmentgrens, en een markering die met spaties begint
    is niet meer terug te vinden.

    Waarom dit erin moet: bij een definitieartikel ís het lid alleen de aanhef. Artikel 2, lid 1 IW
    1990 heeft als eigen tekst "Deze wet verstaat onder:" en 21 definities in de onderdelen. Zonder
    die onderdelen annoteert de agent een lege zin — en dat is precies waar hij op 1 sep 2026 op
    vastliep toen een jurist erom vroeg.

    Onderdelen zónder tekst worden overgeslagen: 'aa.' is in de Invorderingswet een lege container
    voor de geneste subonderdelen eronder, en zou anders als kale regel in de wettekst staan die de
    jurist leest.
    """
    per_lid: dict[str, dict] = {}
    losse_onderdelen: list[str] = []
    # Documentvolgorde afdwingen: de graaf levert de onderdelen niet op volgorde (zie
    # `_onderdeelsleutel`). Zonder dit las bepaling 26.1.9 in de werkplek met de subonderdelen
    # a.–h. vóór de opsomming waar ze onder hangen — en dan zijn het geen uitwerking meer van één
    # weigeringsgrond maar zelfstandige gronden. Dat verandert de juridische strekking.
    rows = sorted(rows, key=lambda r: _onderdeelsleutel(str(r.get("o") or "")))
    for r in rows:
        onderdeel = _onderdeelregel(r)
        lidnummer = (r.get("lidnummer") or "").strip()
        lidtekst = (r.get("lidtekst") or "").strip()
        if not lidtekst:
            # Een onderdeel dat rechtstreeks onder het artikel hangt (opsomming zonder leden).
            if onderdeel:
                losse_onderdelen.append(onderdeel)
            continue
        bestaand = per_lid.setdefault(lidnummer, {"lid": lidnummer, "tekst": lidtekst, "delen": []})
        if onderdeel and onderdeel not in bestaand["delen"]:
            bestaand["delen"].append(onderdeel)

    leden = [
        {"lid": ld["lid"], "tekst": "\n".join([ld["tekst"], *ld["delen"]])}
        for ld in per_lid.values()
    ]
    if losse_onderdelen and not leden:
        leden = [{"lid": "", "tekst": "\n".join(losse_onderdelen)}]
    return leden


def _onderdeelregel(rij: dict) -> str:
    """"a." + tekst → "a. rijksbelastingen: …"; leeg als het onderdeel geen eigen tekst heeft."""
    tekst = (rij.get("otekst") or "").strip()
    if not tekst:
        return ""
    nummer = (rij.get("onummer") or "").strip()
    return f"{nummer} {tekst}".strip()


def _leden_en_corpus(bwb_id: str, artikel: str, graph: GraphPort, lid: str | None = None) -> tuple[list[dict], str]:
    """(leden_teksten, corpus) uit de graaf. Corpus = de leden samengevoegd ('N. tekst'),
    of de artikeltekst zelf als er geen genummerde leden zijn. Met `lid` scope je tot dat ene lid.
    Voor decimale/divisie-nummers valt het terug op get_bepaling (bv. Leidraad '9.1')."""
    _controleer_vindplaats(bwb_id, artikel, lid)
    try:
        rows = parse_select(graph.sparql(queries.get_artikel_corpus(bwb_id, artikel)))
    except ValueError:
        rows = []  # bv. artikel "9.1" wordt door get_artikel geweigerd → straks de bepaling-fallback
    art_tekst = next((r["tekst"] for r in rows if r.get("tekst")), "")
    leden = _vouw_onderdelen_in(rows)
    leden.sort(key=lambda ld: _lidsleutel(ld["lid"]))
    lid_gevraagd = bool(lid and str(lid).strip())
    if lid_gevraagd:
        leden = [ld for ld in leden if _match_lid(ld["lid"], str(lid))]
    elif not leden and art_tekst.strip():
        leden = [{"lid": "", "tekst": art_tekst.strip()}]
    # Bepaling-fallback (decimaal nummer zoals '9.1') alleen zónder specifiek lid; een niet-bestaand
    # lid levert leeg op i.p.v. terug te vallen op de hele bepaling.
    if not leden and not lid_gevraagd:
        leden = _bepaling_fallback(bwb_id, artikel, graph)
    corpus = "\n\n".join((f'{ld["lid"]}. {ld["tekst"]}' if ld["lid"] else ld["tekst"]) for ld in leden)
    return leden, corpus


def artikel_corpus(bwb_id: str, artikel: str, graph: GraphPort, lid: str | None = None) -> str:
    """Alleen de corpus-tekst (voor de annotatie-flow; één SPARQL, geen regeling-info)."""
    return _leden_en_corpus(bwb_id, artikel, graph, lid)[1]


def haal_artikel_sync(bwb_id: str, artikel: str, graph: GraphPort, lid: str | None = None) -> dict:
    """Volledige artikelinfo voor de workbench-weergave: leden-teksten + citeertitel + corpus.
    Met `lid` beperk je de weergave tot dat ene lid."""
    leden, corpus = _leden_en_corpus(bwb_id, artikel, graph, lid)
    citeertitel = ""
    try:
        info = parse_select(graph.sparql(queries.get_regeling_info(bwb_id)))
        if info:
            citeertitel = (info[0].get("citeertitel") or "").strip()
    except Exception:  # citeertitel is cosmetisch – nooit de artikeltekst blokkeren
        logger.warning("citeertitel ophalen mislukt", exc_info=True)
    return {
        "bwbId": bwb_id,
        "artikel": artikel,
        "citeertitel": citeertitel,
        "opschrift": "",
        "leden_teksten": leden,
        "corpus": corpus,
    }
