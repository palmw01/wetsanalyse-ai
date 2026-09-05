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


_SEGMENT = re.compile(r"^(\d*)([a-z]*)$", re.IGNORECASE)


def _lidsleutel(lid: str) -> tuple[tuple[int, str], ...]:
    """Numeriek sorteren op lidnummer (de SPARQL ORDER BY ?lid is lexicaal: 1,10,11,2,…).

    Per punt-gescheiden segment, want bij een beleidsregel zijn de corpussegmenten subdivisies met
    een decimaal nummer. Op alleen het eerste cijferblok sorteren gaf voor "25.1" t/m "25.12"
    overal dezelfde sleutel (25) en dus een willekeurige volgorde; per segment komt 25.2 vóór
    25.10 en valt 73.3a tussen 73.3 en 73.4. Een leeg/onherkenbaar nummer sorteert achteraan.
    """
    tekst = (lid or "").strip()
    if not tekst:
        return ((10**9, ""),)
    sleutel: list[tuple[int, str]] = []
    for deel in tekst.split("."):
        m = _SEGMENT.match(deel)
        if m is None or not deel:
            return ((10**9, tekst),)
        cijfers, letters = m.group(1), m.group(2).lower()
        sleutel.append((int(cijfers) if cijfers else 10**9, letters))
    return tuple(sleutel)


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
    """Vergelijk lidnummers robuust ('1' == '01'); valt terug op string-gelijkheid.

    De volle sleutel telt, niet alleen het eerste segment: bij een beleidsregel zou "25.1" anders
    op "25.2" matchen en zou een lid-filter de hele container teruggeven.
    """
    a, b = _lidsleutel(lidnummer), _lidsleutel(lid)
    onbekend = ((10**9, ""),)
    if a != onbekend and b != onbekend and a[0][0] != 10**9 and b[0][0] != 10**9:
        return a == b
    return (lidnummer or "").strip() == (lid or "").strip()


def _bepaling_fallback(bwb_id: str, artikel: str, graph: GraphPort) -> tuple[list[dict], str]:
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
        return [], ""
    tekst = next((r.get("tekst") for r in rows if (r.get("tekst") or "").strip()), "")
    # Géén vroege uitstap op lege tekst: zes bepalingen in de Leidraad hebben alleen onderdelen
    # (14.2.4, 14.2a, 25.4.6, 73.3a.2, …). Die waren daardoor niet te openen en niet te annoteren.
    regels = [tekst.strip()] if tekst.strip() else []
    # Documentvolgorde, om dezelfde reden als bij `_vouw_onderdelen_in`: `get_bepaling_corpus`
    # sorteert met `ORDER BY ?o` op de IRI als string, en dat is niet de volgorde van de wet.
    # Alleen de eigen onderdelen: die van een subbepaling horen bij haar, niet bij de container.
    eigen_rijen = [r for r in rows if not (r.get("sub") or "")]
    for r in _boomvolgorde(eigen_rijen):
        onderdeel = _onderdeelregel(r)
        if onderdeel and onderdeel not in regels:
            regels.append(onderdeel)
    eigen = [{"lid": "", "tekst": "\n".join(regels)}] if regels else []
    # Is dit een container (bv. Leidraad-bepaling 25 met 81 subdivisies), dan komen die er als
    # eigen regels achter — dezelfde vorm als leden, zodat anker en lid-filter blijven werken.
    return eigen + _vouw_subbepalingen_in(rows), _soort_van(rows)


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
        raise OngeldigeVindplaats(
            f"Ongeldige aanduiding: {artikel!r} (verwacht bv. '9', '22a', '3:40' of '9.1')."
        )
    if lid and str(lid).strip():
        # Een lidnummer ('1', '2a') óf een subbepaling-nummer ('25.1.1'): bij een beleidsregel is
        # het corpussegment een subdivisie, en dan is háár nummer de scope. Strikt op `_num` toetsen
        # gaf voor `lid=25.1.1` een 400 OngeldigeVindplaats op een segment dat gewoon bestaat.
        # `lid_iri` blijft wél strikt: dáár moet het een echt lid zijn.
        for bouwer in (queries._num, queries._nummer_vrij):
            try:
                bouwer(str(lid))
                break
            except ValueError as exc:
                laatste = exc
        else:
            raise OngeldigeVindplaats(str(laatste)) from laatste


def _boomvolgorde(rijen: list[dict]) -> list[dict]:
    """Zet onderdeel-rijen in documentvolgorde met behulp van de ouder-kindrelatie uit de graaf.

    Waarom niet (alleen) op de IRI sorteren. `heeftOnderdeel` ís de boom; die uit een string
    reconstrueren werkt alleen zolang het id toevallig het volledige documentpad draagt. Bij
    bepaling 26.1.9 van de Leidraad ging dat mis: de zestien directe onderdelen kwamen na #402
    keurig op volgorde, maar de acht geneste (`a.`–`h.` onder onderdeel 8) bleven vooraan staan
    omdat hun IRI in de graaf vóór die van hun ooms sorteert. Dan lezen ze als zelfstandige
    weigeringsgronden in plaats van als uitwerking van één grond — een verschil in juridische
    strekking, niet in opmaak.

    Broers en zussen worden onderling wél op hun IRI geordend (`_onderdeelsleutel`): die delen per
    definitie hun hele pad op het laatste segment na, dus daar is het cijfer betrouwbaar, ongeacht
    codering of prefix.

    Ontbreekt `?ouder` — een oudere graafstand, of een corpus dat niet uit deze query komt — dan
    valt hij terug op de vlakke sortering van #402. Geen verbetering, maar ook geen regressie.
    """
    met_ouder = [r for r in rijen if (r.get("ouder") or "").strip()]
    if not met_ouder:
        return sorted(rijen, key=lambda r: _onderdeelsleutel(str(r.get("o") or "")))

    kinderen: dict[str, list[dict]] = {}
    for r in rijen:
        kinderen.setdefault(str(r.get("ouder") or ""), []).append(r)
    for lijst in kinderen.values():
        lijst.sort(key=lambda r: _onderdeelsleutel(str(r.get("o") or "")))

    # Wortels: ouders die zelf geen onderdeel in deze verzameling zijn (het lid of de bepaling).
    eigen = {str(r.get("o") or "") for r in rijen}
    wortels = sorted(k for k in kinderen if k not in eigen)

    uit: list[dict] = []
    gezien: set[str] = set()

    def loop(ouder: str) -> None:
        for r in kinderen.get(ouder, []):
            sleutel = str(r.get("o") or "")
            if sleutel in gezien:      # een cyclus mag het corpus nooit laten vastlopen
                continue
            gezien.add(sleutel)
            uit.append(r)
            loop(sleutel)

    for wortel in wortels:
        loop(wortel)
    # Wat de boom niet bereikte (losse rijen, ontbrekende edge) hoort er nog steeds bij te staan.
    uit.extend(r for r in rijen if str(r.get("o") or "") not in gezien)
    return uit


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
    rows = _boomvolgorde(rows)
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


def _vouw_subbepalingen_in(rows: list[dict]) -> list[dict]:
    """Eén regel per subbepaling, met haar onderdelen eronder — de tegenhanger van
    `_vouw_onderdelen_in` voor een container.

    Bij een beleidsregel is de eenheid onder een bepaling geen lid maar een subdivisie (of een
    eigen artikel). Die krijgen hier dezelfde rijvorm als een lid, zodat alles wat daarop gebouwd
    is ongewijzigd blijft werken: het corpus dat op `"\\n\\n"` in segmenten valt, `_lid_segmenten`
    en het anker, het lid-filter, en `regelsVan` in de werkplek. Een tweede structuur zou een
    tweede ankerpad en een tweede lidtoewijzing betekenen — precies de drift die "het lid en het
    anker zijn één beslissing" moet voorkomen.

    Subbepalingen zónder eigen tekst én zonder onderdelen leveren geen regel op. Dat is geen
    randgeval maar de regel bij de Leidraad: bepaling 25 heeft negen directe subdivisies die samen
    nul tekens eigen tekst hebben; de inhoud zit een laag dieper. Het transitieve pad in de query
    haalt beide lagen op, en de lege tussenlaag valt hier weg.

    De volgorde komt uit het nummer (`_lidsleutel`, per punt-segment numeriek), niet uit de IRI:
    bij een `#id=`-IRI is het documentpad wel aanwezig maar bij een `:artikel:`-IRI niet, en het
    nummer is bij beide de bron van waarheid.
    """
    per_sub: dict[str, dict] = {}
    for r in _boomvolgorde(rows):
        sub = str(r.get("sub") or "")
        if not sub:
            continue
        bestaand = per_sub.setdefault(
            sub,
            {
                "lid": (r.get("subnummer") or "").strip(),
                "tekst": (r.get("subtekst") or "").strip(),
                "delen": [],
            },
        )
        onderdeel = _onderdeelregel(r)
        if onderdeel and onderdeel not in bestaand["delen"]:
            bestaand["delen"].append(onderdeel)

    uit: list[dict] = []
    for sub in per_sub.values():
        regels = [deel for deel in [sub["tekst"], *sub["delen"]] if deel]
        if not regels:
            continue
        uit.append({"lid": sub["lid"], "tekst": "\n".join(regels)})
    uit.sort(key=lambda ld: _lidsleutel(ld["lid"]))
    return uit


def _onderdeelregel(rij: dict) -> str:
    """"a." + tekst → "a. rijksbelastingen: …"; leeg als het onderdeel geen eigen tekst heeft."""
    tekst = (rij.get("otekst") or "").strip()
    if not tekst:
        return ""
    nummer = (rij.get("onummer") or "").strip()
    return f"{nummer} {tekst}".strip()


def _soort_van(rows: list[dict]) -> str:
    """Het knooptype van de opgevraagde bepaling: "Artikel" of "Divisie" (leeg als onbekend).

    Alleen om de vindplaats in de juiste woorden te zetten. Een divisie van een beleidsregel is
    geen artikel met leden, en "art. 25.1 lid 2" is dan een vindplaats die niet bestaat.
    """
    for r in rows:
        waarde = (r.get("soort") or "").strip()
        if waarde:
            return waarde.rsplit(":", 1)[-1].rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    return ""


def _leden_en_corpus(
    bwb_id: str, artikel: str, graph: GraphPort, lid: str | None = None
) -> tuple[list[dict], str, str]:
    """(leden_teksten, corpus) uit de graaf. Corpus = de leden samengevoegd ('N. tekst'),
    of de artikeltekst zelf als er geen genummerde leden zijn. Met `lid` scope je tot dat ene lid.
    Voor decimale/divisie-nummers valt het terug op get_bepaling (bv. Leidraad '9.1')."""
    _controleer_vindplaats(bwb_id, artikel, lid)
    try:
        rows = parse_select(graph.sparql(queries.get_artikel_corpus(bwb_id, artikel)))
    except ValueError:
        rows = []  # bv. artikel "9.1" wordt door get_artikel geweigerd → straks de bepaling-fallback
    art_tekst = next((r["tekst"] for r in rows if r.get("tekst")), "")
    # Rijen van subbepalingen apart houden: hun onderdelen horen bij die subbepaling, niet bij de
    # container. Door elkaar zouden ze als losse onderdelen van de bepaling zelf worden gelezen.
    eigen_rijen = [r for r in rows if not (r.get("sub") or "")]
    leden = _vouw_onderdelen_in(eigen_rijen)
    leden.sort(key=lambda ld: _lidsleutel(ld["lid"]))
    subbepalingen = _vouw_subbepalingen_in(rows)
    if subbepalingen:
        # Een container: haar eigen tekst (en directe opsomming) is de aanhef, de subbepalingen
        # vormen de rest van het corpus — zoals leden dat bij een artikel doen.
        #
        # De aanhef moet er expliciet bij. Bij bepaling 25 van de Leidraad zijn de directe
        # onderdelen acht opsommingsstreepjes; die vormen een eerste segment, waardoor `leden` niet
        # leeg is en de aanhef ("In aansluiting op artikel 25 van de wet …") anders wegviel.
        aanhef = art_tekst.strip()
        if aanhef and leden and leden[0]["lid"] == "":
            leden[0] = {"lid": "", "tekst": f"{aanhef}\n{leden[0]['tekst']}"}
        elif aanhef and not leden:
            leden = [{"lid": "", "tekst": aanhef}]
        leden = leden + subbepalingen
    lid_gevraagd = bool(lid and str(lid).strip())
    if lid_gevraagd:
        leden = [ld for ld in leden if _match_lid(ld["lid"], str(lid))]
    elif not leden and art_tekst.strip():
        leden = [{"lid": "", "tekst": art_tekst.strip()}]
    # Bepaling-fallback (decimaal nummer zoals '9.1') alleen zónder specifiek lid; een niet-bestaand
    # lid levert leeg op i.p.v. terug te vallen op de hele bepaling.
    soort = _soort_van(rows)
    if not leden and not lid_gevraagd:
        leden, soort = _bepaling_fallback(bwb_id, artikel, graph)
    corpus = "\n\n".join((f'{ld["lid"]}. {ld["tekst"]}' if ld["lid"] else ld["tekst"]) for ld in leden)
    return leden, corpus, soort


def artikel_corpus(bwb_id: str, artikel: str, graph: GraphPort, lid: str | None = None) -> str:
    """Alleen de corpus-tekst (voor de annotatie-flow; één SPARQL, geen regeling-info)."""
    return _leden_en_corpus(bwb_id, artikel, graph, lid)[1]


def corpus_en_soort(
    bwb_id: str, artikel: str, graph: GraphPort, lid: str | None = None
) -> tuple[str, str]:
    """Corpus + knooptype in één ophaalactie.

    Apart van `artikel_corpus` omdat die functie op tientallen plekken (en in de tests) als
    "geef me de tekst" wordt gebruikt; het soort erbij zou daar alleen ruis zijn. Wie de vindplaats
    in woorden moet uitdrukken heeft het wél nodig, en een tweede SPARQL-call daarvoor zou zonde
    zijn — de query levert het al mee.
    """
    leden, corpus, soort = _leden_en_corpus(bwb_id, artikel, graph, lid)
    return corpus, soort


def haal_artikel_sync(bwb_id: str, artikel: str, graph: GraphPort, lid: str | None = None) -> dict:
    """Volledige artikelinfo voor de workbench-weergave: leden-teksten + citeertitel + corpus.
    Met `lid` beperk je de weergave tot dat ene lid."""
    leden, corpus, soort = _leden_en_corpus(bwb_id, artikel, graph, lid)
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
        # "Artikel" of "Divisie"; stuurt alleen de bewoording van de vindplaats in werkplek en
        # annotatie. Leeg = onbekend, en dan valt alles terug op "artikel".
        "soort": soort,
    }
