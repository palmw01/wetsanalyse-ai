"""Wat er gelezen is en wat alleen gevonden: één regel voor het rapport uit code en de controle (meting bundel 115, D01).

De centrale agent schreef "de 16 uitspraken die de subagent las", terwijl het kind er 9 op naam opvroeg en 7 alleen in
een zoekresultaat zag. Een stuk is **gelezen** als een leestool zijn tekst gaf (`spoorbronnen`: `leestools`): bij een
bronconnector het `stuk` van het resultaat, bij de kennisgraaf de bepalingen in het resultaat. Wat alleen een zoektool
noemde, is **gevonden**. Een verwijzing in de tekst van een gelezen stuk (een voetnoot, een aangehaalde uitspraak) is
geen gelezen stuk.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

from .spoorbronnen import bron_van


def _stuk(tekst: str) -> tuple[str, str] | None:
    try:
        data = json.loads(tekst)
    except (TypeError, ValueError):
        return None
    stuk = data.get("stuk") if isinstance(data, dict) else None
    # Een foutresultaat met een stuk (alleen een PDF, geen tekst bij de bron) is niet gelezen.
    if not isinstance(stuk, dict) or data.get("status") == "error" or stuk.get("leesbaar") is False or not stuk.get("id"):
        return None
    from bronmodel.extern import externe_vindplaats

    ident = str(stuk["id"])
    vp = externe_vindplaats(ident)
    # De canonieke id, zoals `collect_sources` hem uit een zoekresultaat haalt: anders telt hetzelfde stuk twee keer.
    return (vp.id if vp else ident), str(stuk.get("label") or ident)


def _bronnen(paren: list[tuple[str, str]]) -> list[tuple[str, str]]:
    from .provenance import collect_sources

    try:
        bronnen = collect_sources(paren)
    except Exception:  # noqa: BLE001 – een label is een gemak; zonder labels blijft de rest staan
        return []
    return [(str(getattr(b, "uri", "") or ""), str(getattr(b, "label", "") or getattr(b, "uri", ""))) for b in bronnen
            if b and getattr(b, "uri", "")]


def gelezen_en_gevonden(trace: Iterable[Any]) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """(gelezen, alleen gevonden) als lijsten (id, label), ontdubbeld, in volgorde van de trace."""
    gelezen: dict[str, str] = {}
    zoeken: list[tuple[str, str]] = []
    for item in trace:
        tool, tekst = str(item[0]), str(item[1])
        bron = bron_van(tool)
        if bron is None or tool not in bron.leestools:
            zoeken.append((tool, tekst))
            continue
        if bron.connector is not None:
            if (stuk := _stuk(tekst)) is not None:
                gelezen.setdefault(*stuk)
            continue
        for ident, label in _bronnen([(tool, tekst)]):
            gelezen.setdefault(ident, label)
    gevonden = {i: lab for i, lab in _bronnen(zoeken) if i not in gelezen}
    return list(gelezen.items()), list(gevonden.items())


#: Hoeveel eigen woorden een zin of lijstregel over een stuk hoogstens heeft zonder dat het een samenvatting is: woorden
#: die niet in het zoekresultaat van dat stuk staan (titel, label, instantie, datum) en geen functiewoord zijn. "ECLI:… (Hoge
#: Raad, 12 maart 2026), over de melding" is een vermelding; wat de rechter oordeelde is een samenvatting.
MAX_EIGEN_WOORDEN = 5

_WOORD = re.compile(r"[a-zà-ÿ]{3,}")
_SEGMENT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý(])|\n+")
_FUNCTIEWOORDEN = frozenset(
    "de het een en van in op over met voor door aan bij dat die dit deze zijn is was wordt werd worden heeft hebben had "
    "naar uit ook niet als zoals dan maar om tot onder tegen hij zij ze er hier daar wat welke wie waar wel nog al geen "
    "kan kon zou zal moet mag uitspraak uitspraken arrest arresten vonnis rechter rechtbank hof hoge raad gerechtshof "
    "zaak stuk stukken waarin waarbij volgens gaat ging betreft".split())


_ALINEA = re.compile(r"\n\s*\n")
#: Een link is geen tekst over het stuk (de bronregel onder een citaat: "[Hoge Raad …](https://…)").
_URL = re.compile(r"https?://\S+?(?=\)|\s|$)")


_MAAND = "januari februari maart april mei juni juli augustus september oktober november december".split()
_DATUM = re.compile(rf"\b(\d{{1,2}}) ({'|'.join(_MAAND)}) (\d{{4}})\b", re.IGNORECASE)
#: Hoe een kop de instantie noemt, en waarmee het label van het stuk begint (`provenance.collect_sources`: "Parket bij de
#: Hoge Raad 13 september 2024, ECLI:…"). Een kop zonder instantie laat alle stukken van die datum toe.
_INSTANTIES = ((re.compile(r"\b(PHR|A-G|AG|Parket|conclusie)\b", re.IGNORECASE), ("Parket",)),
               (re.compile(r"\b(HR|Hoge Raad)\b"), ("Hoge Raad",)),
               (re.compile(r"\b(Hof|Gerechtshof)\b", re.IGNORECASE), ("Gerechtshof",)),
               (re.compile(r"\b(Rb|Rechtbank)\b", re.IGNORECASE), ("Rechtbank",)))
#: Een zin die zegt uit welk stuk ze haar inhoud heeft ("volgens de conclusie in …", "aangehaald in …").
_HERKOMST = re.compile(r"\b(volgens|aangehaald|besproken|beschreven|blijkens|weergegeven|samengevat\s+(?:in|door))\b",
                       re.IGNORECASE)


def _ids(tekst: str) -> list[str]:
    from bronmodel.extern import externe_verwijzingen

    return list(dict.fromkeys(vp.id for vp in externe_verwijzingen(tekst)))


def _uit_kop(kop: str, labels: dict[str, str]) -> list[str]:
    """De stukken die een kop zonder id noemt met instantie en datum ("**HR 6 oktober 2023 — …**"): de stukken uit de
    trace met die datum in hun label (meting bundel 120, D01: de kop noemde het stuk zo, en de regels eronder telden voor
    geen enkel stuk). De eerste datum: daarna noemt een kop soms een ander stuk ("*(voortbouwend op HR 10 februari
    2023)*")."""
    m = _DATUM.search(kop)
    if m is None or not labels:
        return []
    dag, maand, jaar = m.groups()
    datum = f"{int(dag)} {maand.casefold()} {jaar}"
    voor = kop[:m.start()]
    begin = next((b for patroon, b in _INSTANTIES if patroon.search(voor)), ())
    return [i for i, lab in labels.items() if datum in lab.casefold()
            and (not begin or lab.startswith(begin) and not (begin == ("Hoge Raad",) and lab.startswith("Parket")))]


def _herkomst(segment: str, ids: list[str], gelezen: set[str]) -> list[str]:
    """Zegt de regel uit welk gelezen stuk ze een ongelezen stuk weergeeft ("volgens de conclusie in PHR:2025:435 oordeelde
    de Hoge Raad in HR:2023:1371 …"), dan gaat ze over dat gelezen stuk en rust ze op zijn tekst. Anders de ids zelf."""
    bron = [i for i in ids if i in gelezen]
    return bron if bron and len(bron) < len(ids) and _HERKOMST.search(segment) else ids


def per_stuk(tekst: str, gelezen: Iterable[str] | None = None,
             labels: dict[str, str] | None = None) -> list[tuple[str, list[str]]]:
    """De zinnen en lijstregels van `tekst` met de stukken naast de wet waar ze over gaan: de stukken die de regel bij id
    noemt, en anders het onderwerp van haar alinea. Een samenvatting staat vaak onder een kop met het id ("**2. HR 14 april
    2023 (ECLI:…)**" en dan de tekst): zonder deze toewijzing toetste de controle alleen de kop (meting bundel 119, D01: twee
    foute samenvattingen, *gegrond*).

    Het onderwerp: de stukken uit de eerste regel (de kop), met id of met instantie en datum (`_uit_kop`, via `labels`:
    id → label uit de trace), en anders de stukken van de eerste zin die er een noemt (meting bundel 120, D01: "**HR 6
    oktober 2023 — …**", dan "De Hoge Raad (ECLI:…) verwerpt …" en zes zinnen zonder id). Met `gelezen`: een regel die zegt
    uit welk gelezen stuk ze een ander stuk weergeeft, gaat over het gelezen stuk (`_herkomst`)."""
    gelezen = set(gelezen or ())
    uit: list[tuple[str, list[str]]] = []
    for alinea in _ALINEA.split(tekst or ""):
        segmenten = [s for s in _SEGMENT.split(alinea) if s.strip()]
        kop = alinea.strip().split("\n", 1)[0]
        onderwerp = _herkomst(kop, _ids(kop) or _uit_kop(kop, labels or {}), gelezen)
        if not onderwerp:
            eerste = next((s for s in segmenten if _ids(s)), "")
            onderwerp = _herkomst(eerste, _ids(eerste), gelezen)
        # Een kop die zegt uit welk gelezen stuk de alinea komt ("**HR 6 oktober 2023, volgens de conclusie in …**"): een
        # ongelezen stuk dat een zin eronder noemt, geeft de alinea weer uit dat gelezen stuk.
        bron = onderwerp if onderwerp and set(onderwerp) <= gelezen and _HERKOMST.search(kop) else []
        for segment in segmenten:
            ids = _herkomst(segment, _ids(segment), gelezen)
            if bron and ids and not set(ids) & gelezen:
                ids = bron
            uit.append((_URL.sub("", segment), ids or onderwerp))
    return uit


def _context(items: list[tuple[str, str]]) -> tuple[set[str], dict[str, str]]:
    """(de gelezen stukken, id → label van elk stuk in de trace): wat `per_stuk` nodig heeft."""
    gelezen, gevonden = gelezen_en_gevonden(items)
    return {i for i, _ in gelezen}, {**dict(gevonden), **dict(gelezen)}


def ongelezen_samengevat(tekst: str, trace: Iterable[Any]) -> list[str]:
    """De stukken die `tekst` inhoudelijk samenvat terwijl hun tekst niet gelezen is (meting bundel 116, D01: twee
    uitspraken samengevat die niemand las, en het oordeel *gegrond* omdat de blokcitaten letterlijk waren). Een stuk is pas
    bron als het gelezen is; dezelfde regel geldt voor wat het antwoord erover zegt. Per zin of lijstregel die het stuk bij
    id noemt, of onder een kop die het noemt (`per_stuk`): meer dan `MAX_EIGEN_WOORDEN` woorden die niet uit zijn
    zoekresultaat komen, is een samenvatting."""
    items = [(str(x[0]), str(x[1])) for x in trace]
    gelezen, labels = _context(items)
    uit: list[str] = []
    for segment, ids in per_stuk(tekst, gelezen, labels):
        for ident in ids:
            if ident in gelezen or ident in uit:
                continue
            bekend = _rijwoorden(items, ident)
            eigen = [w for w in _WOORD.findall(segment.casefold()) if w not in bekend and w not in _FUNCTIEWOORDEN]
            if len(eigen) > MAX_EIGEN_WOORDEN:
                uit.append(ident)
    return [f"samenvatting van {i} zonder gelezen tekst" for i in uit]


def _rijwoorden(items: list[tuple[str, str]], ident: str) -> set[str]:
    """De woorden van de zoekrijen van één stuk (label, titel, instantie, datum): wat het zoekresultaat over dat stuk zegt,
    niet over de andere treffers in hetzelfde resultaat."""
    woorden: set[str] = set()
    for tool, tekst in items:
        bron = bron_van(tool)
        if bron is not None and tool in bron.leestools:
            continue
        try:
            data = json.loads(tekst)
        except (TypeError, ValueError):
            continue
        for rij in (data.get("resultaten") if isinstance(data, dict) else None) or []:
            if isinstance(rij, dict) and ident in json.dumps(rij, ensure_ascii=False):
                woorden |= set(_WOORD.findall(json.dumps(rij, ensure_ascii=False).casefold()))
    return woorden


#: Hoeveel van de eigen woorden van een duiding in de passages van het stuk moeten staan (op hun stam).
MIN_STEUN = 0.5
_STAM = 5


def _stammen(woorden: Iterable[str]) -> set[str]:
    return {w[:_STAM] for w in woorden}


def zonder_steun(tekst: str, steun: dict[str, str], trace: Iterable[Any]) -> list[str]:
    """Na een rapport van een subagent: de stukken die `tekst` duidt zonder dat een passage van dat stuk het draagt
    (meting bundel 117, D01: zeven samenvattingen van gelezen uitspraken, geen enkele klopte, en toch *gegrond*, want de
    stukken stonden in de trace). Een stuk mag het antwoord noemen, met wat het zoekresultaat erover zegt; wie meer zegt
    (meer dan `MAX_EIGEN_WOORDEN` eigen woorden in een zin of lijstregel), moet dat uit de passages van dat stuk halen:
    die van het rapport, en die het antwoord zelf toont (`steun`). Ten minste `MIN_STEUN` van die woorden staat erin, op
    hun stam. Zonder passage van het stuk is een duiding een bewering."""
    items = [(str(x[0]), str(x[1])) for x in trace]
    uit: dict[str, str] = {}
    for segment, ids in per_stuk(tekst, *_context(items)):
        ids = [i for i in ids if i not in uit]
        if not ids:
            continue
        bekend = set().union(*(_rijwoorden(items, i) for i in ids))
        eigen = [w for w in _WOORD.findall(segment.casefold()) if w not in bekend and w not in _FUNCTIEWOORDEN]
        if len(eigen) <= MAX_EIGEN_WOORDEN:
            continue
        # Een regel over twee stukken ("HR:2023:181 en :184") mag op de passages van elk van beide rusten.
        passages = _stammen(_WOORD.findall(" ".join(steun.get(i) or "" for i in ids).casefold()))
        for ident in ids:
            if not passages:
                uit[ident] = f"duiding van {ident} zonder passage van dat stuk in het rapport"
            elif sum(w[:_STAM] in passages for w in eigen) < MIN_STEUN * len(eigen):
                uit[ident] = f"duiding van {ident} die de passages van dat stuk niet dragen"
    return list(uit.values())


_ZIE = re.compile(r"\bzie\b", re.IGNORECASE)
#: De woorden van een verwijzing zelf ("zie de toelichting bij …"): geen duiding.
_VERWIJSWOORDEN = frozenset("zie toelichting bij hierboven hieronder onder eerder genoemde vorige volgende".split())


def verwijzing_als_duiding(tekst: str, trace: Iterable[Any]) -> list[str]:
    """De stukken die `tekst` niet duidt maar met "zie …" naar een ander stuk verwijst (meting bundel 118, D01: bij
    HR:2023:176 en :183 stond "Zie toelichting bij HR:2023:181", en die gaat over iets anders). Een verwijzing naar een
    ander stuk is geen duiding van dit stuk. Per zin of lijstregel: noemt ze stuk A en na "zie" een ander stuk B, en zegt ze
    over A verder niets (hoogstens `MAX_EIGEN_WOORDEN` eigen woorden), dan is het een bewering. Ook als A de kop erboven
    is en de regel met "zie" begint."""
    from bronmodel.extern import externe_verwijzingen

    items = [(str(x[0]), str(x[1])) for x in trace]
    uit: dict[str, str] = {}
    vorige: list[str] = []
    for segment in _SEGMENT.split(tekst or ""):
        if not segment.strip():
            continue
        ids = list(dict.fromkeys(vp.id for vp in externe_verwijzingen(segment)))
        zie = _ZIE.search(segment)
        if zie is None:
            vorige = ids
            continue
        voor = list(dict.fromkeys(vp.id for vp in externe_verwijzingen(segment[:zie.start()])))
        na = [i for i in dict.fromkeys(vp.id for vp in externe_verwijzingen(segment[zie.end():]))]
        onderwerp = voor[0] if voor else (vorige[0] if len(vorige) == 1 and not segment[:zie.start()].strip(" -*•\t") else "")
        anders = [b for b in na if b != onderwerp]
        vorige = ids
        if not onderwerp or not anders or onderwerp in uit:
            continue
        bekend = set().union(*(_rijwoorden(items, i) for i in [onderwerp, *anders]))
        eigen = [w for w in _WOORD.findall(segment.casefold())
                 if w not in bekend and w not in _FUNCTIEWOORDEN and w not in _VERWIJSWOORDEN]
        if len(eigen) <= MAX_EIGEN_WOORDEN:
            uit[onderwerp] = f"verwijzing van {onderwerp} naar {anders[0]} in plaats van een duiding"
    return list(uit.values())


#: Woorden uit de vraag die niets over de inhoud zeggen: wat er gevraagd wordt, niet waarover.
_VRAAGVORM = frozenset("rechtspraak uitspraak uitspraken periode dossier samenvatten samengevat zoeken relevante "
                       "conclusie conclusies arresten instanties instantie artikel artikelen bepaling bepalingen "
                       "onderdeel".split())
_REGELINGNAAM = re.compile(r"(wet|wetboek|leidraad|besluit|regeling|richtlijn|verordening)$")
#: Een zin die zegt dat een stuk ergens níét over gaat, mag het woord uit de vraag noemen.
_ONTKENNING = re.compile(r"\b(niet|geen|nergens|zonder)\b", re.IGNORECASE)
#: Hoe lang een woord uit de vraag hoogstens is om mee te tellen: korte woorden staan in elke tekst.
MIN_VRAAGWOORD = 7


def _stuktekst(items: list[tuple[str, str]], ident: str) -> str:
    """Alles wat een leestool van dit stuk gaf (alle pagina's), in kleine letters."""
    delen = []
    for tool, tekst in items:
        bron = bron_van(tool)
        if bron is None or tool not in bron.leestools or bron.connector is None:
            continue
        if (stuk := _stuk(tekst)) is not None and stuk[0] == ident:
            delen.append(tekst)
    return "\n".join(delen).casefold()


def vraag_niet_in_stuk(tekst: str, trace: Iterable[Any], vraag: str) -> list[str]:
    """De duidingen die het onderwerp van de vraag aan een stuk toeschrijven terwijl het stuk dat woord niet bevat (meting
    bundel 119, D01: bij HR:2023:563 "tijdig betalingsonmacht gemeld"; in de uitspraak staat het woord niet. Bundel 117:
    zeven uitspraken werden een meldingszaak). Per zin of lijstregel over een gelezen stuk (`per_stuk`): een inhoudswoord uit
    de vraag (ten minste `MIN_VRAAGWOORD` letters, geen regelingnaam) dat niet in de gelezen tekst van dat stuk staat, is een
    bewering. Een zin met een ontkenning ("gaat niet over de melding") niet: die zegt wat er ontbreekt."""
    items = [(str(x[0]), str(x[1])) for x in trace]
    woorden = {w for w in _WOORD.findall((vraag or "").casefold())
               if len(w) >= MIN_VRAAGWOORD and w not in _FUNCTIEWOORDEN and w not in _VRAAGVORM
               and not _REGELINGNAAM.search(w)}
    if not woorden:
        return []
    teksten: dict[str, str] = {}
    uit: dict[str, str] = {}
    for segment, ids in per_stuk(tekst, *_context(items)):
        if _ONTKENNING.search(segment):
            continue
        genoemd = sorted(w for w in woorden if re.search(rf"\b{re.escape(w)}\b", segment.casefold()))
        for ident in ids:
            if ident in uit or not genoemd:
                continue
            stuk = teksten.setdefault(ident, _stuktekst(items, ident))
            if not stuk:
                continue  # niet gelezen: daarvoor is `ongelezen_samengevat`
            if ontbreekt := [w for w in genoemd if w not in stuk]:
                uit[ident] = f"duiding van {ident} met '{ontbreekt[0]}' uit de vraag, dat niet in dat stuk staat"
    return list(uit.values())


#: De filters die de opdracht zelf al geeft (de bepaling, de peildatum van het werkgebied): geen eigen afbakening.
_UIT_OPDRACHT = frozenset({"bwb_id", "artikel", "peildatum"})
_JAAR = re.compile(r"\b(1[89]\d\d|20\d\d)\b")


def zelf_afgebakend(trace: Iterable[Any], gevraagd: str) -> list[str]:
    """De filters waarmee een zoektool van een connector zocht en die niet uit `gevraagd` komen (de opdracht en de
    antwoorden van de jurist), als "label: waarde" (meting bundel 119, D01: het kind zocht alleen bij de Hoge Raad en het
    Parket, en de jurist had "alle instanties" gezegd). De filters komen uit de `zoekvraag` van het resultaat en uit de
    beschrijving van de connector; een datum telt als gevraagd als haar jaar in `gevraagd` staat."""
    tekst = (gevraagd or "").casefold()
    uit: dict[str, None] = {}
    for item in trace:
        tool, resultaat = str(item[0]), str(item[1])
        bron = bron_van(tool)
        if bron is None or bron.connector is None or tool in bron.leestools:
            continue
        try:
            data = json.loads(resultaat)
        except (TypeError, ValueError):
            continue
        zoekvraag = data.get("zoekvraag") if isinstance(data, dict) else None
        if not isinstance(zoekvraag, dict):
            continue
        velden = bron.connector.filters
        for arg, waarde in zoekvraag.items():
            if arg in _UIT_OPDRACHT or arg not in velden or waarde in ("", None, [], {}):
                continue
            w = str(waarde)
            jaren = _JAAR.findall(w)
            gevonden = all(j in tekst for j in jaren) if jaren else w.casefold() in tekst
            if not gevonden:
                uit[f"{velden[arg].label}: {w}"] = None
    return list(uit)


#: Een periode in de woorden van de jurist: "2022 tot en met 2024", "2022–2024", "van 2022 tot 2024".
_PERIODE = re.compile(r"\b(1[89]\d\d|20\d\d)\s*(?:–|—|-|t/m|tot en met|tot)\s*(1[89]\d\d|20\d\d)\b")
_ECLI_JAAR = re.compile(r"^ECLI:[A-Z]{2}:[A-Z0-9]+:(\d{4}):")


def gekozen_periode(tekst: str) -> tuple[int, int] | None:
    """De periode die de jurist noemde (de laatste, want een later antwoord gaat voor), of None."""
    treffers = _PERIODE.findall(tekst or "")
    if not treffers:
        return None
    a, b = (int(j) for j in treffers[-1])
    return (a, b) if a <= b else (b, a)


def jaar_van(ident: str) -> int | None:
    """Het jaar uit een ECLI (het jaar van de uitspraak of de conclusie), of None."""
    m = _ECLI_JAAR.match(ident or "")
    return int(m.group(1)) if m else None


def buiten_periode(tekst: str, trace: Iterable[Any], periode: tuple[int, int] | None) -> list[str]:
    """De stukken van buiten de periode die de jurist koos en die `tekst` toch duidt (meting bundel 120, D01: de jurist koos
    2022–2024, en twee van de vier blokken waren uitspraken uit 2025, met "buiten de periode" erbij). Noemen mag (hoogstens
    `MAX_EIGEN_WOORDEN` eigen woorden, zoals bij een vermelding); een samenvatting is een bewering. Het jaar komt uit het
    ECLI."""
    if periode is None:
        return []
    items = [(str(x[0]), str(x[1])) for x in trace]
    uit: dict[str, str] = {}
    for segment, ids in per_stuk(tekst, *_context(items)):
        buiten = [i for i in ids if i not in uit and (j := jaar_van(i)) is not None and not periode[0] <= j <= periode[1]]
        if not buiten:
            continue
        bekend = set().union(*(_rijwoorden(items, i) for i in buiten))
        eigen = [w for w in _WOORD.findall(segment.casefold()) if w not in bekend and w not in _FUNCTIEWOORDEN]
        if len(eigen) > MAX_EIGEN_WOORDEN:
            for i in buiten:
                uit[i] = f"duiding van {i} van buiten de gekozen periode {periode[0]}–{periode[1]}"
    return list(uit.values())


_WOORDVORM = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")


def vreemd_schrift(tekst: str) -> list[str]:
    """De woorden met Latijnse letters waarin een letter uit een ander schrift staat (meting bundel 120, D01: "niet-melدende",
    een Arabische letter midden in een Nederlands woord, een tokenfout van het model). Een woord helemaal in een ander schrift
    blijft staan; welke letter bedoeld was, weet de code niet, dus het model herstelt het."""
    import unicodedata

    uit: dict[str, None] = {}
    for w in _WOORDVORM.findall(tekst or ""):
        schriften = {unicodedata.name(c, "?").split(" ")[0] for c in w if c.isalpha()}
        if "LATIN" in schriften and len(schriften) > 1:
            uit[f"spelling: '{w}' bevat een letter uit een ander schrift"] = None
    return list(uit)
