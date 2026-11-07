"""Een bestaande wetsanalyse als referentie voor een e2e: inlezen en vergelijken met wat Lex opleverde.

Een team dat buiten het platform analyseert, legt activiteit 2 vaak vast in een wiki: per bepaling een tabel
"Klasse | Formulering uit wettekst | Toelichting", met een status, en bij activiteit 1 een bronnentabel met
de deelvragen waar een bepaling bij hoort. Deze module leest zo'n Confluence-export (HTML) in een neutraal
schema en vergelijkt dat met de elementen van een werkgebied (`GET /v1/werkgebieden/{id}/elementen`, of de
uitvoer van `werkgebied_lezen` uit de acceptatie-MCP).

**Het materiaal zelf hoort niet in de repo.** Zo'n export is van derden; hij en alles wat eruit komt (de
referentie, de transcriptie van de diagrammen, het rapport) staan in `docs/acceptatie/lokaal/` (gitignored) of
buiten de repo. Deze code kent daarom geen enkel pad: alles komt als argument binnen.

Wat de vergelijking wel en niet zegt:

- **Recall per klasse** op dezelfde plek (`scoring.klasse_dekking`): de referentie is één analyse, geen gold;
  `voorstellen - raak` is een bovengrens voor wat onjuist is.
- **Strikt en ruim.** Een fragment dat niet letterlijk in de brontekst staat (een parafrase, een los
  operatorwoord, een ellips) kan Lex nooit precies zo markeren: offsets komen uit de bron. Dat telt apart.
- **Impliciete elementen** (een rechtssubject dat alleen in de toelichting staat) zijn niet annoteerbaar en
  tellen niet mee; ze worden genoemd.
- **Relaties** legt het platform in activiteit 2 niet vast. Uit een transcriptie van de diagrammen
  (`relaties.json`, zie `lees_relaties`) is alleen de eindpuntdekking te meten: zijn beide knopen van een kant
  als element met de juiste klasse geannoteerd?

Gebruik:

    uv run python -m eval.extern_dossier lees --export <map> --uit <referentie.json>
    uv run python -m eval.extern_dossier vergelijk --referentie <referentie.json> --platform <elementen.json> \\
        [--werkgebied <werkgebied.json>] [--relaties <relaties.json>] [--uit <rapport.json>]
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.scoring import _norm, _token_iou, _zelfde_plek, klasse_dekking  # noqa: E402

# --- Klassen ------------------------------------------------------------------------------------------------

# De rijen van zo'n tabel volgen de JAS-tabel, met de samengestelde klassen gesplitst. Het platform kent er
# dertien (`api/app/jas_klassen.py`); het subtype is geen klasse.
KLASSEN: dict[str, str] = {
    "rechtssubject": "Rechtssubject",
    "rechtsobject": "Rechtsobject",
    "object": "Rechtsobject",
    "rechtsbetrekking": "Rechtsbetrekking",
    "rechtsfeit": "Rechtsfeit",
    "voorwaarde": "Voorwaarde",
    "afleidingsregel": "Afleidingsregel",
    "variabele": "Variabele en variabelewaarde",
    "variabelewaarde": "Variabele en variabelewaarde",
    "variabele en variabelewaarde": "Variabele en variabelewaarde",
    "parameter": "Parameter en parameterwaarde",
    "parameterwaarde": "Parameter en parameterwaarde",
    "parameter en parameterwaarde": "Parameter en parameterwaarde",
    "operator": "Operator",
    "tijdsaanduiding": "Tijdsaanduiding",
    "plaatsaanduiding": "Plaatsaanduiding",
    "delegatiebevoegdheid": "Delegatiebevoegdheid en delegatie-invulling",
    "delegatie-invulling": "Delegatiebevoegdheid en delegatie-invulling",
    "delegatiebevoegdheid en delegatie-invulling": "Delegatiebevoegdheid en delegatie-invulling",
    "brondefinitie": "Brondefinitie",
}

_LEEG = {"", "nvt", "nvt.", "n.v.t.", "-", "–"}
_HERHALING = re.compile(r"\s*\((\d+)\s*x\)\s*$", re.I)
_ELLIPS = re.compile(r"\s*(?:…|\.{2,})\s*")


def klasse_van(label: str) -> str | None:
    """De platformklasse van een rijlabel; "(Rechts)object" en hoofdletters tellen niet. Onbekend → None."""
    sleutel = re.sub(r"[()]", "", label).strip().lower()
    return KLASSEN.get(sleutel)


# --- Een kleine HTML-boom -----------------------------------------------------------------------------------

_LEEGTAGS = {"br", "img", "col", "hr", "meta", "link", "input"}


@dataclass
class Knoop:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    kinderen: list["Knoop | str"] = field(default_factory=list)

    def tekst(self, br: str = " ") -> str:
        delen: list[str] = []
        for k in self.kinderen:
            if isinstance(k, str):
                delen.append(k)
            elif k.tag == "br":
                delen.append(br)
            else:
                delen.append(k.tekst(br))
        return "".join(delen)

    def alle(self, tag: str) -> list["Knoop"]:
        uit: list[Knoop] = []
        for k in self.kinderen:
            if isinstance(k, Knoop):
                if k.tag == tag:
                    uit.append(k)
                uit.extend(k.alle(tag))
        return uit

    def kind(self, *tags: str) -> list["Knoop"]:
        return [k for k in self.kinderen if isinstance(k, Knoop) and k.tag in tags]


class _Bouwer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.wortel = Knoop("root")
        self.stapel = [self.wortel]

    def handle_starttag(self, tag, attrs):
        k = Knoop(tag, {a: v or "" for a, v in attrs})
        self.stapel[-1].kinderen.append(k)
        if tag not in _LEEGTAGS:
            self.stapel.append(k)

    def handle_endtag(self, tag):
        for i in range(len(self.stapel) - 1, 0, -1):
            if self.stapel[i].tag == tag:
                del self.stapel[i:]
                return

    def handle_data(self, data):
        self.stapel[-1].kinderen.append(data)


def boom(bron: str) -> Knoop:
    b = _Bouwer()
    b.feed(bron)
    return b.wortel


def _schoon(tekst: str) -> str:
    return " ".join(html.unescape(tekst).replace("\xa0", " ").split())


_OPSOMMING = re.compile(r"^(?:[a-z]{1,2}\.|\d+°|[ivx]+\.)\s", re.I)


def _regels(cel: Knoop) -> list[str]:
    """De regels van een cel: elke alinea (`<p>`/`<li>`) en elke `<br>` begint een regel, behalve een
    opsommingsonderdeel ("a. de te betalen geldsom"): dat hoort bij de regel ervoor, zoals in de wettekst."""
    blokken = cel.alle("p") + cel.alle("li") or [cel]
    uit: list[str] = []
    for b in blokken:
        eerste = True
        for regel in b.tekst("\n").split("\n"):
            regel = _schoon(regel)
            if not regel:
                continue
            if uit and not eerste and _OPSOMMING.match(regel):
                uit[-1] = f"{uit[-1]} {regel}"
            else:
                uit.append(regel)
            eerste = False
    return uit


def _cellen(rij: Knoop) -> list[Knoop]:
    return rij.kind("td", "th")


def _rijen(tabel: Knoop) -> list[Knoop]:
    return tabel.alle("tr")


def _koptekst(tabel: Knoop) -> list[str]:
    rijen = _rijen(tabel)
    return [_schoon(c.tekst()).lower() for c in _cellen(rijen[0])] if rijen else []


# --- De bron uit een link -----------------------------------------------------------------------------------

_BWB = re.compile(r"BWBR\d{7}")


def bron_uit(link: str, kop: str = "", citaat: str = "") -> dict[str, str]:
    """BWB-id, artikel en lid uit een wetten.overheid.nl-link en de kop.

    Een jci-link draagt `artikel=`; een beleidsregel heeft een anker `…divisie9.5`. Het lid staat niet in de
    link maar in de kop ("Artikel 9 lid 1") of aan het begin van het citaat ("lid 2. De beschikking…")."""
    link = html.unescape(unquote(link))
    m = _BWB.search(link) or _BWB.search(kop)
    bwb = m.group(0) if m else ""
    artikel = ""
    if m := re.search(r"[&?]artikel=([^&#]+)", link):
        artikel = m.group(1)
    elif m := re.search(r"divisie(\d+(?:\.\d+)*)(?![\d.])\s*$", link.split("#")[-1]):
        artikel = m.group(1)
    elif m := re.search(r"artikel\s+([\w:.]+?)\.?(?:\s|,|$)", kop, re.I):
        artikel = m.group(1)
    lid = ""
    if m := re.search(r"\blid\s+(\d+(?:\.\d+)*\w?)", kop, re.I):
        lid = m.group(1)
    elif m := re.match(r"\s*lid\s+(\d+\w?)\b", citaat, re.I):
        lid = m.group(1)
    if "." in lid:
        # Een beleidsregel nummert zijn divisies binnen het artikel ("Artikel 9 … lid 9.1"): dat is bepaling 9.1.
        artikel, lid = lid, ""
    return {"bwb_id": bwb, "artikel": artikel, "lid": lid}


# --- Activiteit 2: de annotatietabellen --------------------------------------------------------------------

def _fragment(regel: str) -> dict[str, Any] | None:
    """Eén regel uit de kolom "Formulering uit wettekst": telling eraf, ellips in delen."""
    tekst = regel.strip()
    if tekst.lower() in _LEEG:
        return None
    herhaling = 1
    if m := _HERHALING.search(tekst):
        herhaling, tekst = int(m.group(1)), tekst[: m.start()].strip()
    delen = [d.strip(" ,") for d in _ELLIPS.split(tekst) if d.strip(" ,")]
    if not delen:
        return None
    return {"tekst": tekst, "delen": delen, "herhaling": herhaling}


def _impliciet(toelichting: list[str]) -> list[str]:
    """De namen na "Impliciet:" in de toelichting, tot een regel die uitlegt ("Op te maken uit …")."""
    namen: list[str] = []
    bezig = False
    for r in toelichting:
        if r.lower().startswith("impliciet"):
            bezig = True
            rest = r.split(":", 1)[1].strip() if ":" in r else ""
            if rest:
                namen.append(rest)
            continue
        if bezig:
            if r.lower().startswith(("op te maken", "zie ", "volgt uit")) or len(r.split()) > 4:
                break
            namen.append(r)
    return namen


def _jas_tabel(tabel: Knoop) -> bool:
    kop = _koptekst(tabel)
    return len(kop) >= 2 and kop[0] == "klasse" and "formulering" in kop[1]


def _status(sectie: list[Knoop]) -> str:
    for el in sectie:
        for tabel in ([el] if el.tag == "table" else el.alle("table")):
            for rij in _rijen(tabel):
                c = _cellen(rij)
                if len(c) >= 2 and _schoon(c[0].tekst()).lower() == "status":
                    return " ".join(_regels(c[1])).lower()
    return ""


def status_soort(status: str) -> str:
    """`definitief` als alles wat er staat definitief is, anders `concept` (ook "to do")."""
    regels = [r for r in re.split(r"\s{2,}|\n|(?<=definitief)\s", status) if r.strip()]
    return "definitief" if regels and all("definitief" in r for r in regels) else "concept"


def _secties(wortel: Knoop) -> list[tuple[Knoop, list[Knoop]]]:
    """Per `<h2>` de elementen tot de volgende `<h2>`, in documentvolgorde (ook als ze in divs zitten)."""
    vlak: list[Knoop] = []

    def loop(k: Knoop) -> None:
        for c in k.kinderen:
            if not isinstance(c, Knoop):
                continue
            if c.tag in ("h2", "table", "p"):
                vlak.append(c)
            else:
                loop(c)
    loop(wortel)
    uit: list[tuple[Knoop, list[Knoop]]] = []
    for k in vlak:
        if k.tag == "h2":
            uit.append((k, []))
        elif uit:
            uit[-1][1].append(k)
    return uit


def lees_annotaties(bron: str) -> list[dict[str, Any]]:
    """De bepalingen van een activiteit-2-pagina: per kop met een JAS-tabel de bron, status, citaat en elementen."""
    uit = []
    for kop, sectie in _secties(boom(bron)):
        tabellen = [t for t in sectie if t.tag == "table" and _jas_tabel(t)]
        if not tabellen:
            continue
        koptekst = _schoon(kop.tekst())
        links = [a.attrs.get("href", "") for a in kop.alle("a")]
        citaat = " ".join(_schoon(p.tekst()) for p in sectie if p.tag == "p" and _schoon(p.tekst()))
        status = _status(sectie)
        elementen = []
        for ti, tabel in enumerate(tabellen):
            for rij in _rijen(tabel)[1:]:
                c = _cellen(rij)
                if len(c) < 2:
                    continue
                label = _schoon(c[0].tekst())
                klasse = klasse_van(label)
                toelichting = _regels(c[2]) if len(c) > 2 else []
                for regel in _regels(c[1]):
                    f = _fragment(regel)
                    if f:
                        elementen.append({"klasse_extern": label, "klasse": klasse, "tabel": ti, **f,
                                          "impliciet": False})
                if klasse == "Rechtssubject":
                    for naam in _impliciet(toelichting):
                        elementen.append({"klasse_extern": label, "klasse": klasse, "tabel": ti, "tekst": naam,
                                          "delen": [naam], "herhaling": 1, "impliciet": True})
        uit.append({"label": koptekst, "bron": bron_uit(links[0] if links else "", koptekst, citaat),
                    "status": status, "status_soort": status_soort(status), "citaat": citaat,
                    "tabellen": len(tabellen), "elementen": elementen})
    return uit


# --- Activiteit 1: de bronnentabel --------------------------------------------------------------------------

def lees_bronnen(bron: str) -> list[dict[str, Any]]:
    """De bronnentabellen ("<regeling> | Mogelijk relevant | Deelvraag"): per bepaling de relevantie en de
    deelvraagnummers. Een rij zonder nummers staat er wel, met een lege lijst."""
    uit = []
    for tabel in boom(bron).alle("table"):
        kop = _koptekst(tabel)
        if len(kop) < 3 or "mogelijk relevant" not in kop[1] or "deelvraag" not in kop[2]:
            continue
        regeling = kop[0]
        for rij in _rijen(tabel)[1:]:
            c = _cellen(rij)
            if len(c) < 2:
                continue
            regels = _regels(c[0])
            if not regels:
                continue
            links = [a.attrs.get("href", "") for a in c[0].alle("a")]
            nummers = [int(n) for n in re.findall(r"\((\d+)\)", _schoon(c[2].tekst()))] if len(c) > 2 else []
            uit.append({"regeling": regeling, "bepaling": regels[0], "relevantie": _schoon(c[1].tekst()).lower(),
                        "deelvragen": sorted(set(nummers)),
                        "bron": bron_uit(links[0] if links else "", regels[0])})
    return uit


def lees_confluence(paden: list[Path]) -> dict[str, Any]:
    """Alle pagina's van een export samen: de bepalingen met annotaties en de bronnen met deelvragen."""
    bepalingen, bronnen = [], []
    for p in paden:
        tekst = p.read_text(encoding="utf-8")
        bepalingen += lees_annotaties(tekst)
        bronnen += lees_bronnen(tekst)
    return {"schema": "extern-dossier-v1", "bepalingen": bepalingen, "bronnen": bronnen}


def toets_letterlijk(referentie: dict[str, Any], bronteksten: dict[str, str] | None = None) -> dict[str, Any]:
    """Zet per element `letterlijk`: alle delen staan in de brontekst. `bronteksten` (sleutel `bron_sleutel`)
    is de wettekst uit de graaf; zonder telt het citaat uit de export, en dat staat dan in `getoetst_tegen`."""
    for b in referentie["bepalingen"]:
        tekst = (bronteksten or {}).get(bron_sleutel(b["bron"]))
        b["getoetst_tegen"] = "bron" if tekst else "citaat"
        corpus = _norm(tekst or b["citaat"])
        for e in b["elementen"]:
            e["letterlijk"] = not e["impliciet"] and all(_woordgrens_in(_norm(d), corpus) for d in e["delen"])
    return referentie


_LEESTEKEN = re.compile(r"[;:,.]")


def _woordgrens_in(deel: str, corpus: str) -> bool:
    """Op woordgrenzen, en zonder leestekens: een weggelaten puntkomma maakt een fragment niet minder letterlijk."""
    deel, corpus = (" ".join(_LEESTEKEN.sub(" ", x).split()) for x in (deel, corpus))
    return bool(deel) and re.search(r"(?<!\w)" + re.escape(deel) + r"(?!\w)", corpus) is not None


def bron_sleutel(bron: dict[str, str]) -> str:
    return "/".join(x for x in (bron.get("bwb_id"), bron.get("artikel"), bron.get("lid")) if x)


# --- Bij welke bepaling hoort een platformelement ----------------------------------------------------------

def _iri_past(iri: str, bron: dict[str, str]) -> bool:
    """Valt een bron-IRI van het platform binnen deze bepaling? Een wet heeft `:artikel:<nr>[:lid:<n>]`, een
    beleidsregel `id:…divisie9.5` of `bepaling:9.5`; een dubbele punt in een artikelnummer is `%3A`."""
    iri = unquote(iri)
    if not bron.get("bwb_id") or bron["bwb_id"] not in iri:
        return False
    art, lid = bron.get("artikel", ""), bron.get("lid", "")
    if not art:
        return True
    if re.search(rf"(?:divisie|bepaling:){re.escape(art)}(?![\d.])", iri):
        return True
    if not re.search(rf":artikel:{re.escape(art)}(?![\w.])", iri):
        return False
    return not lid or re.search(rf":lid:{re.escape(lid)}(?!\w)", iri) is not None


def _iris(element: dict[str, Any]) -> list[str]:
    return [a.get("bron_iri", "") for a in element.get("ankers") or []] + [element.get("eigenaar_iri") or ""]


def wijs_toe(bepalingen: list[dict[str, Any]], elementen: list[dict[str, Any]]) -> tuple[dict[int, list], list]:
    """Per bepaling de platformelementen, op IRI; lukt dat niet, dan op het citaat (de tekst staat erin).
    Wat bij geen bepaling hoort, komt terug als `los`: niet stil weg."""
    per: dict[int, list] = {i: [] for i in range(len(bepalingen))}
    los = []
    for e in elementen:
        treffers = [i for i, b in enumerate(bepalingen) if any(_iri_past(x, b["bron"]) for x in _iris(e) if x)]
        if not treffers:
            treffers = [i for i, b in enumerate(bepalingen) if _norm(e.get("tekst", "")) and
                        _norm(e.get("tekst", "")) in _norm(b["citaat"])]
        if treffers:
            per[treffers[0]].append(e)
        else:
            los.append(e)
    return per, los


# --- Vergelijken ----------------------------------------------------------------------------------------------

def platform_elementen(data: Any) -> list[dict[str, Any]]:
    """De elementen uit een inventaris (`{elementen: [...]}`), de uitvoer van `werkgebied_lezen`
    (`{elementen: {elementen: [...]}}`) of een annotatie-export v3. Zoekt de eerste lijst met klasse + tekst."""
    if isinstance(data, list):
        if data and all(isinstance(x, dict) and "klasse" in x and "tekst" in x for x in data):
            return data
        for x in data:
            if (gevonden := platform_elementen(x)):
                return gevonden
        return []
    if isinstance(data, dict):
        voorkeur = [data[k] for k in ("elementen",) if k in data]
        for waarde in voorkeur + [v for k, v in data.items() if k != "elementen"]:
            if (gevonden := platform_elementen(waarde)):
                return gevonden
    return []


def _som(rijen: list[dict[str, dict[str, int]]]) -> dict[str, dict[str, Any]]:
    totaal: dict[str, dict[str, Any]] = {}
    for r in rijen:
        for klasse, x in r.items():
            t = totaal.setdefault(klasse, dict(n=0, gedekt=0, exact=0, voorstellen=0, raak=0))
            for k in t:
                t[k] += x[k]
    for t in totaal.values():
        t["recall"] = round(t["gedekt"] / t["n"], 3) if t["n"] else None
    return dict(sorted(totaal.items()))


def _referentie(b: dict[str, Any], strikt: bool) -> list[dict[str, Any]]:
    """De referentie-elementen die meetellen: met een platformklasse, niet impliciet, en bij `strikt` alleen wat
    letterlijk in de brontekst staat."""
    return _ontdubbel([{"klasse": e["klasse"], "tekst": e["tekst"]} for e in b["elementen"]
                       if e["klasse"] and not e["impliciet"] and (not strikt or e.get("letterlijk"))])


def _ontdubbel(uit: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dezelfde klasse op dezelfde tekst telt één keer: "(2x)" is één markering die twee keer voorkomt, en het
    platform ontdubbelt op tekst + lid."""
    gezien, schoon = set(), []
    for r in uit:
        k = (r["klasse"], _norm(r["tekst"]))
        if k not in gezien:
            gezien.add(k)
            schoon.append(r)
    return schoon


def vergelijk_annotaties(referentie: dict[str, Any], elementen: list[dict[str, Any]]) -> dict[str, Any]:
    bepalingen = referentie["bepalingen"]
    per, los = wijs_toe(bepalingen, elementen)
    rapport_bepalingen, strikt, ruim = [], [], []
    per_status: dict[str, list] = {}
    for i, b in enumerate(bepalingen):
        hier = per[i]
        ref_strikt, ref_ruim = _referentie(b, True), _referentie(b, False)
        d_strikt, d_ruim = klasse_dekking(hier, ref_strikt), klasse_dekking(hier, ref_ruim)
        strikt.append(d_strikt)
        ruim.append(d_ruim)
        per_status.setdefault(b["status_soort"], []).append(d_strikt)
        gemist = [r for r in ref_strikt if not any(e.get("klasse") == r["klasse"] and
                                                   _zelfde_plek(e.get("tekst", ""), r["tekst"]) for e in hier)]
        verwisseld = []
        for r in gemist:
            # Strenger dan "zelfde plek": een lange markering die het fragment toevallig bevat, is geen verwisseling.
            ander = [e for e in hier if _token_iou(e.get("tekst", ""), r["tekst"]) >= 0.5]
            if ander:
                verwisseld.append({"tekst": r["tekst"], "referentie": r["klasse"],
                                   "platform": sorted({e.get("klasse") or "" for e in ander})})
        extra = [{"klasse": e.get("klasse"), "tekst": e.get("tekst"), "id": e.get("id")} for e in hier
                 if not any(_zelfde_plek(e.get("tekst", ""), r["tekst"]) for r in ref_ruim)]
        rapport_bepalingen.append({
            "label": b["label"], "bron": bron_sleutel(b["bron"]), "status": b["status_soort"],
            "getoetst_tegen": b.get("getoetst_tegen", "niet getoetst"),
            "platform": len(hier), "referentie_strikt": len(ref_strikt), "referentie_ruim": len(ref_ruim),
            "niet_letterlijk": [e["tekst"] for e in b["elementen"] if not e["impliciet"] and not e.get("letterlijk")],
            "impliciet": [e["tekst"] for e in b["elementen"] if e["impliciet"]],
            "zonder_klasse": [e["klasse_extern"] for e in b["elementen"] if not e["klasse"]],
            "gemist": [{"klasse": r["klasse"], "tekst": r["tekst"]} for r in gemist],
            "klasse_verwisseld": verwisseld, "alleen_platform": extra})
    return {"per_klasse_strikt": _som(strikt), "per_klasse_ruim": _som(ruim),
            "per_status_strikt": {s: _som(r) for s, r in sorted(per_status.items())},
            "bepalingen": rapport_bepalingen,
            "niet_toegewezen": [{"klasse": e.get("klasse"), "tekst": e.get("tekst"), "id": e.get("id")} for e in los]}


# --- Relaties: eindpuntdekking ------------------------------------------------------------------------------

def lees_relaties(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Een transcriptie van de diagrammen: `{bepalingen: [{bron: {bwb_id, artikel, lid}, knopen: [{id, klasse,
    label, letterlijk: ja|nee|impliciet}], kanten: [{van, naar, type}]}]}`. Een klasse wordt gemapt zoals bij de
    tabellen; een kant naar een onbekende knoop is een fout in de transcriptie, geen stille misser."""
    uit = []
    for b in data.get("bepalingen", []):
        knopen = {k["id"]: {**k, "klasse": klasse_van(k.get("klasse", "")) or k.get("klasse")} for k in b["knopen"]}
        for kant in b.get("kanten", []):
            for kant_eind in (kant["van"], kant["naar"]):
                if kant_eind not in knopen:
                    raise ValueError(f"kant naar onbekende knoop {kant_eind!r} in {b.get('bron')}")
        uit.append({"bron": b["bron"], "knopen": knopen, "kanten": b.get("kanten", [])})
    return uit


def vergelijk_relaties(relaties: list[dict[str, Any]], elementen: list[dict[str, Any]]) -> dict[str, Any]:
    """Per relatietype: hoeveel kanten beide eindpunten geannoteerd hebben (juiste klasse, zelfde plek), één,
    geen, of niet meetbaar (een eindpunt dat niet letterlijk in de tekst staat)."""
    per_type: dict[str, dict[str, int]] = {}
    knoopstand: list[dict[str, Any]] = []
    for b in relaties:
        hier = [e for e in elementen if any(_iri_past(x, b["bron"]) for x in _iris(e) if x)]

        def gedekt(k: dict[str, Any]) -> bool | None:
            if k.get("letterlijk", "ja") != "ja":
                return None
            return any(e.get("klasse") == k["klasse"] and _zelfde_plek(e.get("tekst", ""), k["label"]) for e in hier)

        stand = {kid: gedekt(k) for kid, k in b["knopen"].items()}
        knoopstand += [{"bron": bron_sleutel(b["bron"]), "klasse": k["klasse"], "label": k["label"],
                        "gedekt": stand[kid]} for kid, k in b["knopen"].items()]
        for kant in b["kanten"]:
            t = per_type.setdefault(kant["type"], dict(n=0, beide=0, een=0, geen=0, niet_meetbaar=0))
            t["n"] += 1
            a, z = stand[kant["van"]], stand[kant["naar"]]
            if a is None or z is None:
                t["niet_meetbaar"] += 1
            else:
                t[{2: "beide", 1: "een", 0: "geen"}[int(a) + int(z)]] += 1
    return {"per_type": dict(sorted(per_type.items())), "knopen": knoopstand}


# --- Bronselectie per deelvraag -----------------------------------------------------------------------------

def vergelijk_bronnen(referentie: dict[str, Any], werkgebied: dict[str, Any]) -> list[dict[str, Any]]:
    """Per deelvraagnummer (de n-de actieve deelvraag, zoals de export ze nummert): welke bepalingen uit de
    bronnentabel ook bij die deelvraag in het werkgebied staan. Een bron telt als hij de bepaling omvat of erin
    valt (een artikel tegen een lid)."""
    wg = werkgebied.get("werkgebied", werkgebied)
    selecties = {s["id"]: s for s in wg.get("bronnen", [])}
    actief = [d for d in wg.get("deelvragen", []) if d.get("status", "actief") == "actief"]
    uit = []
    nummers = sorted({n for r in referentie["bronnen"] for n in r["deelvragen"]})
    for n in nummers:
        verwacht = [r for r in referentie["bronnen"] if n in r["deelvragen"]]
        d = actief[n - 1] if 0 < n <= len(actief) else None
        iris = [selecties[s]["bron_iri"] for s in (d or {}).get("bronnen", []) if s in selecties]
        gevonden = [r for r in verwacht if any(_iri_past(i, r["bron"]) or _omvat(i, r["bron"]) for i in iris)]
        uit.append({"deelvraag": n, "vraag": (d or {}).get("vraag"), "verwacht": len(verwacht),
                    "gevonden": len(gevonden), "recall": round(len(gevonden) / len(verwacht), 3) if verwacht else None,
                    "gemist": [f"{r['regeling']} {r['bepaling']}" for r in verwacht if r not in gevonden],
                    "platform": len(iris)})
    return uit


def _omvat(iri: str, bron: dict[str, str]) -> bool:
    """Een selectie op een artikel omvat het lid uit de referentie."""
    return bool(bron.get("lid")) and _iri_past(iri, {**bron, "lid": ""}) and ":lid:" not in unquote(iri)


def vergelijk(referentie: dict[str, Any], platform: Any, *, werkgebied: dict[str, Any] | None = None,
              relaties: dict[str, Any] | None = None) -> dict[str, Any]:
    elementen = platform_elementen(platform)
    uit: dict[str, Any] = {"schema": "extern-vergelijking-v1", "platform_elementen": len(elementen),
                           "annotaties": vergelijk_annotaties(referentie, elementen)}
    if werkgebied is not None:
        uit["bronselectie"] = vergelijk_bronnen(referentie, werkgebied)
    if relaties is not None:
        uit["relaties"] = vergelijk_relaties(lees_relaties(relaties), elementen)
    return uit


# --- CLI ------------------------------------------------------------------------------------------------------

def _print(rapport: dict[str, Any]) -> None:
    a = rapport["annotaties"]
    print(f"Platformelementen: {rapport['platform_elementen']}  (niet toegewezen: {len(a['niet_toegewezen'])})")
    print("\nRecall per klasse (strikt: alleen letterlijke referentiefragmenten)")
    for k, x in a["per_klasse_strikt"].items():
        print(f"  {k:<46} {x['gedekt']:>3}/{x['n']:<3} recall {x['recall']}  voorstellen {x['voorstellen']}, raak {x['raak']}")
    for b in a["bepalingen"]:
        print(f"\n{b['label']} [{b['status']}, getoetst tegen {b['getoetst_tegen']}]: platform {b['platform']}, "
              f"referentie {b['referentie_strikt']} strikt / {b['referentie_ruim']} ruim; gemist {len(b['gemist'])}, "
              f"klasse anders {len(b['klasse_verwisseld'])}, alleen platform {len(b['alleen_platform'])}")
    if "bronselectie" in rapport:
        print("\nBronselectie per deelvraag")
        for d in rapport["bronselectie"]:
            print(f"  {d['deelvraag']}: {d['gevonden']}/{d['verwacht']} (platform {d['platform']} bronnen)")
    if "relaties" in rapport:
        print("\nRelaties: eindpuntdekking per type")
        for t, x in rapport["relaties"]["per_type"].items():
            print(f"  {t:<24} n={x['n']} beide={x['beide']} één={x['een']} geen={x['geen']} "
                  f"niet meetbaar={x['niet_meetbaar']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Een bestaande wetsanalyse inlezen en vergelijken met Lex")
    sub = ap.add_subparsers(dest="actie", required=True)
    lees = sub.add_parser("lees", help="een Confluence-export inlezen naar het neutrale schema")
    lees.add_argument("--export", type=Path, required=True, help="map met de HTML-pagina's, of één bestand")
    lees.add_argument("--bronteksten", type=Path, help="JSON {bwb/artikel/lid: wettekst} om letterlijkheid te toetsen")
    lees.add_argument("--uit", type=Path, required=True)
    verg = sub.add_parser("vergelijk", help="een referentie vergelijken met de elementen van een werkgebied")
    verg.add_argument("--referentie", type=Path, required=True)
    verg.add_argument("--platform", type=Path, required=True, help="elementen (inventaris of werkgebied_lezen)")
    verg.add_argument("--werkgebied", type=Path, help="het werkgebied met deelvragen en bronnen")
    verg.add_argument("--relaties", type=Path, help="transcriptie van de diagrammen")
    verg.add_argument("--uit", type=Path)
    args = ap.parse_args(argv)

    def laad(p: Path | None) -> Any:
        return json.loads(p.read_text(encoding="utf-8")) if p else None

    if args.actie == "lees":
        paden = sorted(args.export.glob("*.html")) if args.export.is_dir() else [args.export]
        referentie = toets_letterlijk(lees_confluence(paden), laad(args.bronteksten))
        args.uit.write_text(json.dumps(referentie, ensure_ascii=False, indent=2), encoding="utf-8")
        n = sum(len(b["elementen"]) for b in referentie["bepalingen"])
        print(f"{len(referentie['bepalingen'])} bepalingen, {n} fragmenten, {len(referentie['bronnen'])} bronnen")
        return 0
    rapport = vergelijk(laad(args.referentie), laad(args.platform), werkgebied=laad(args.werkgebied),
                        relaties=laad(args.relaties))
    if args.uit:
        args.uit.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    _print(rapport)
    return 0


if __name__ == "__main__":
    sys.exit(main())
