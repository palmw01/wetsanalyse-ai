"""LiDO-spike: per artikel van een regeling alle LiDO-versies, hun links, verenigd op label-id.

Alleen lezend, beleefd (sequentieel, pauze per aanroep), met een schijfcache per URL.
Gebruik: python -I lido_spike.py <BWB-id> <toestand.xml> <uitmap>
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from lxml import etree

BASIS = "https://linkeddata.overheid.nl/service"
PAUZE = 0.15
UA = "wetsanalyse-lido-spike/0.1 (onderzoek, alleen lezen)"

STAT = {"aanroepen": 0, "cache": 0, "seconden": 0.0, "fouten": 0}


def haal(url: str, cache: pathlib.Path) -> str | None:
    pad = cache / (hashlib.sha1(url.encode()).hexdigest() + ".xml")
    if pad.exists():
        STAT["cache"] += 1
        return pad.read_text(encoding="utf-8")
    tekst = None
    for poging in range(2):
        t0 = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                kandidaat = r.read().decode("utf-8")
            ET.fromstring(kandidaat)  # alleen een geldig XML-antwoord telt
            tekst = kandidaat
        except Exception as e:  # noqa: BLE001
            print("FOUT", poging, url, repr(e)[:120], file=sys.stderr)
        STAT["aanroepen"] += 1
        STAT["seconden"] += time.monotonic() - t0
        time.sleep(PAUZE if tekst else 2.0)
        if tekst:
            break
    if tekst is None:
        STAT["fouten"] += 1
    if tekst is not None:
        pad.write_text(tekst, encoding="utf-8")
    return tekst


def get_id(ref: str, cache) -> str | None:
    t = haal(f"{BASIS}/get-id?juriconnect-ref={urllib.parse.quote(ref, safe='')}", cache)
    if not t:
        return None
    m = re.search(r"<id>([^<]+)</id>", t)
    return m.group(1) if m else None


def get_id_jci(jci: str, cache) -> str | None:
    t = haal(f"{BASIS}/get-id?juriconnect={urllib.parse.quote(jci, safe='')}", cache)
    if not t:
        return None
    # LiDO geeft soms naast de echte id een kapotte zonder BWB-id ("/bwb/id//<label>/..."): die telt niet.
    ids = [i for i in re.findall(r"<id>([^<]+)</id>", t) if "/bwb/id//" not in i]
    return ids[0] if ids else None


TOESTANDEN: list[str] = []


def toestanden(bwb: str) -> list[str]:
    url = ("https://zoekservice.overheid.nl/sru/Search?operation=searchRetrieve&version=2.0&x-connection=BWB"
           f"&maximumRecords=1000&query=dcterms.identifier%3D{bwb}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        t = r.read().decode("utf-8")
    return sorted(set(re.findall(r"/(\d{4}-\d{2}-\d{2})_\d+/xml/", t)))


def met_datum(jci: str, datum: str) -> str:
    jci = re.sub(r"&z=[0-9-]+", f"&z={datum}", jci)
    return re.sub(r"&g=[0-9-]+", f"&g={datum}", jci)


def versies(bwb: str, artikel: str, cache, jci: str | None = None) -> list[str]:
    """Van nieuw naar oud: vorige versie = de versie die gold op de dag vóór de begindatum.

    Met de volledige jci uit de toestand (werkt voor elke regeling); `juriconnect-ref` faalt bij de Awb."""
    uit: list[str] = []
    if jci:  # de nieuwste toestand kent LiDO vaak nog niet: neem de nieuwste die hij wel kent
        vid = None
        for d in list(reversed(TOESTANDEN))[:6]:
            vid = get_id_jci(met_datum(jci, d), cache)
            if vid:
                break
    else:
        vid = get_id(f"{bwb}&artikel={artikel}", cache)
    while vid and vid not in uit:
        uit.append(vid)
        begin = vid.rstrip("/").split("/")[-2]  # .../<label>/<geldig>/<zicht>
        try:
            vorig = (dt.date.fromisoformat(begin) - dt.timedelta(days=1)).isoformat()
        except ValueError:
            break
        if jci:  # met de jci werkt alleen een datum waarop een toestand bestaat
            eerder = [d for d in TOESTANDEN if d < begin]
            if not eerder:
                break
            vorig = eerder[-1]
        if vorig < "2002-01-01":
            break
        vid = (get_id_jci(met_datum(jci, vorig), cache) if jci
               else get_id(f"{bwb}&artikel={artikel}&g={vorig}&z={vorig}", cache))
    return uit


RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
RL = "{http://linkeddata.overheid.nl/terms/}"


def _groep(uri: str) -> str:
    if "/jurisprudentie/id/" in uri:
        return "Jurisprudentie"
    if "/oep/id/" in uri:
        return "Officiele overheidspublicatie"
    return "Wet" if "/bwb/id/" in uri else "Overig"


def links_rdf(vid: str, cache) -> list[dict] | None:
    """Terugval: dezelfde links uit het RDF-formaat (de XML-vorm breekt bij sommige versies af)."""
    STAT["rdf_terugval"] = STAT.get("rdf_terugval", 0) + 1
    t = haal(f"{BASIS}/get-links?id={urllib.parse.quote(vid, safe='')}&max=5000", cache)
    if not t:
        return None
    uit = []
    for d in ET.fromstring(t).iter(f"{RDF}Description"):
        typ = d.find(f"{RDF}type")
        if typ is None or not typ.get(f"{RDF}resource", "").endswith("/LinkAct"):
            continue
        van = d.find(f"{RL}linktVan").get(f"{RDF}resource")
        naar = d.find(f"{RL}linktNaar").get(f"{RDF}resource")
        lt = d.find(f"{RL}heeftLinktype").get(f"{RDF}resource")
        inkomend = naar == vid
        ander = van if inkomend else naar
        label = "Door computer herkende referentie" if lt.endswith("lx-referentie") else lt.rsplit("/", 1)[-1]
        uit.append({"richting": "inkomende" if inkomend else "uitgaande", "groep": _groep(ander),
                    "label": label, "type": lt, "doel": ander, "titel": "", "versie": vid, "via": "rdf"})
    return uit


def links(vid: str, cache) -> list[dict]:
    """Alle inkomende en uitgaande links van één versie, over alle pagina's."""
    uit, start = [], 0
    while True:
        url = f"{BASIS}/get-links?id={urllib.parse.quote(vid, safe='')}&output=xml&rows=50&start={start}"
        t = haal(url, cache)
        if not t:
            rdf = links_rdf(vid, cache)
            if rdf is None:
                STAT["versies_onvolledig"] = STAT.get("versies_onvolledig", 0) + 1
                return uit
            return rdf
        root = ET.fromstring(t)
        subj = [x for x in root if x.tag == "subject"]
        if not subj:
            return uit
        eigen = subj[0]
        titels = {x.get("id"): next((c.text for c in x if c.tag.endswith("title")), "") for x in subj[1:]}
        for richting in ("inkomende-links", "uitgaande-links"):
            for el in eigen:
                if el.tag.endswith(richting):
                    for l in el:
                        uit.append({"richting": richting.split("-")[0], "groep": l.get("groep"),
                                    "label": l.get("label"), "type": l.get("type"), "doel": l.get("idref"),
                                    "titel": titels.get(l.get("idref"), ""), "versie": vid})
        if len(subj) - 1 < 50:
            return uit
        start += 50


def artikelen(toestand: str) -> list[tuple[str, str]]:
    t = etree.parse(toestand)
    uit = []
    for a in t.xpath("//artikel"):
        nr = a.findtext("kop/nr")
        if nr and a.get("status") != "vervallen":
            jci = a.xpath("string(meta-data/jcis/jci[@versie='1.3']/@verwijzing)") or None
            uit.append((nr.strip(), a.get("label-id"), jci))
    return uit


def main():
    bwb, toestand, uitmap = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
    cache = uitmap / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    TOESTANDEN.extend(toestanden(bwb))
    print("toestanden", len(TOESTANDEN), file=sys.stderr)
    arts = artikelen(toestand)
    if len(sys.argv) > 5:  # willekeurige steekproef: <n> <seed>
        import random
        random.seed(int(sys.argv[5]))
        arts = random.sample(arts, min(int(sys.argv[4]), len(arts)))
    elif len(sys.argv) > 4:
        arts = arts[: int(sys.argv[4])]
    resultaat = []
    for i, (nr, label, jci) in enumerate(arts, 1):
        vs = versies(bwb, nr, cache, jci)
        alle = [l for v in vs for l in links(v, cache)]
        labels = {v.rstrip("/").split("/")[-3] for v in vs}
        resultaat.append({"artikel": nr, "label_id_bwb": label, "label_id_lido": sorted(labels),
                          "versies": vs, "links": alle})
        if i % 10 == 0:
            print(f"{i}/{len(arts)} {STAT}", file=sys.stderr, flush=True)
    (uitmap / f"{bwb}.json").write_text(json.dumps({"stat": STAT, "artikelen": resultaat}, ensure_ascii=False))
    print(json.dumps(STAT))


if __name__ == "__main__":
    main()
