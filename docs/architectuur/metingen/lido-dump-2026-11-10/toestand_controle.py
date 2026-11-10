"""Controle op de volledigheid van de versies: veranderde er bij een BWB-toestand zonder LiDO-artikelversie toch een
artikel? Per toestand de tekst van elk artikel (label-id → hash van de tekst zonder metadata) naast de vorige toestand.

Gebruik: python -I toestand_controle.py <BWB> <sru.xml> <uitmap> <uitsnede.nt.gz> alle|<datum> …
(alleen lezend, 0,5 s pauze). Met de uitsnede uit de dump erbij: per toestand de gewijzigde artikelen naast de
LiDO-versies met die begindatum, in beide richtingen.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
import time
import urllib.request

from lxml import etree

UA = "wetsanalyse-lido-dump-spike/0.1 (onderzoek, alleen lezen)"


def haal(url: str, pad: pathlib.Path) -> bytes:
    if not pad.exists():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            pad.write_bytes(r.read())
        time.sleep(0.5)
    return pad.read_bytes()


def hashes(xml: bytes) -> dict[str, str]:
    t = etree.fromstring(xml)
    uit = {}
    for a in t.iter("artikel"):
        a2 = etree.fromstring(etree.tostring(a))
        for m in a2.iter("meta-data"):
            m.getparent().remove(m)
        tekst = re.sub(r"\s+", " ", "".join(a2.itertext())).strip()
        uit[a.get("label-id")] = hashlib.sha1(f"{a.get('status')}|{tekst}".encode()).hexdigest()
    return uit


def main() -> None:
    import gzip
    bwb, sru, uitmap = sys.argv[1], open(sys.argv[2]).read(), pathlib.Path(sys.argv[3])
    lido: set[tuple[str, str]] = set()
    patroon = re.compile(rf"^<http://linkeddata\.overheid\.nl/terms/bwb/id/{bwb}/(\d+)/([0-9-]+)/[0-9-]+> "
                         r'<http://purl\.org/dc/terms/type> "Artikel"')
    for r in gzip.open(sys.argv[4], "rt", encoding="utf-8"):
        m = patroon.match(r)
        if m:
            lido.add((m.group(1), m.group(2)))
    uitmap.mkdir(parents=True, exist_ok=True)
    urls = dict(re.findall(rf"(\d{{4}}-\d{{2}}-\d{{2}})_\d+/xml/({bwb}_\d{{4}}-\d{{2}}-\d{{2}}_\d+\.xml)", sru))
    toe = sorted(urls)
    rij = []
    datums = toe[1:] if sys.argv[5:] == ["alle"] else sys.argv[5:]
    for d in datums:
        vorige = toe[toe.index(d) - 1]
        h = {}
        for x in (vorige, d):
            url = f"https://repository.officiele-overheidspublicaties.nl/bwb/{bwb}/{x}_0/xml/{bwb}_{x}_0.xml"
            h[x] = hashes(haal(url, uitmap / f"{bwb}_{x}.xml"))
        gewijzigd = sorted(l for l in h[d] if h[vorige].get(l) != h[d][l])
        status = {}
        for a in etree.fromstring((uitmap / f"{bwb}_{d}.xml").read_bytes()).iter("artikel"):
            status[a.get("label-id")] = a.get("status")
        met_versie = {l for l, g in lido if g == d}
        rij.append({"toestand": d, "vorige": vorige, "artikelen_gewijzigd": len(gewijzigd),
                    "lido_versies": len(met_versie),
                    "gewijzigd_zonder_lido_versie": [(l, status.get(l)) for l in gewijzigd if l not in met_versie],
                    "lido_versie_zonder_wijziging": sorted(met_versie - set(gewijzigd))})
        print(json.dumps(rij[-1]), flush=True)
    json.dump(rij, open(uitmap / "toestand-controle.json", "w"), indent=1)


if __name__ == "__main__":
    main()
