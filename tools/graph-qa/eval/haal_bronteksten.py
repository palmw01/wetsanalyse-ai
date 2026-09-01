"""Haal `bronteksten.json` opnieuw op uit overheid.nl, mét recursie in de subonderdelen.

Draaien vanuit `tools/graph-qa` met de venv van bwb-import:
    ../bwb-import/.venv/bin/python eval/haal_bronteksten.py

Dit script staat hier omdat de vorige ophaal niet reproduceerbaar was en daardoor stil scheef
raakte ten opzichte van wat de graaf levert.

De vorige versie nam alleen de onderdelen op lid-niveau. Daardoor miste BWBR0004770/2/1 de vier
geneste definities (Koninkrijk, Rijk, Nederland, BES eilanden) die in de graaf via
`heeftOnderdeel+` wél in het corpus komen: 3528 tekens vastgelegd tegen 4730 in productie.
"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "bwb-import"))
from app.config import Settings
from app.downloader import BwbDownloader
from app.parser import ToestandParser

s = Settings.from_env(); dl = BwbDownloader(s)
parser = ToestandParser(schema_path=(s.schemas_dir / "toestand.xsd") if s.validate_xsd else None)
cache = {}
def wet(bwb):
    if bwb not in cache:
        cache[bwb] = parser.parse(dl.download_toestand(bwb, dl.latest_toestand(bwb)))
    return cache[bwb]

def regels(eigen, onderdelen):
    """Zoals `artikel._vouw_onderdelen_in`: eigen tekst, daarna elk onderdeel op een eigen regel."""
    uit = [eigen.strip()] if eigen.strip() else []
    def loop(ond):
        for o in ond:
            t = (o.tekst or "").strip()
            if t: uit.append(f"{(o.nummer or '').strip()} {t}".strip())
            loop(o.subonderdelen or [])          # <- de recursie die eerder ontbrak
    loop(onderdelen or [])
    return "\n".join(uit)

def alle_art(d):
    for a in d.artikelen or []: yield a
    for sd in d.subdelen or []: yield from alle_art(sd)
def alle_div(d):
    yield d
    for sd in getattr(d, "subdivisies", []) or []: yield from alle_div(sd)

def haal(sleutel):
    delen = sleutel.split("/")
    w = wet(delen[0])
    if "." in delen[1]:                                   # bepaling (decimaal nummer)
        div = next(y for d in (w.divisies or []) for y in alle_div(d)
                   if getattr(y, "nummer", None) == delen[1])
        return regels(getattr(div, "tekst", "") or "", getattr(div, "onderdelen", []))
    kandidaten = [a for d in (w.structuurdelen or []) for a in alle_art(d)] + list(w.losse_artikelen or [])
    art = next(a for a in kandidaten if a.nummer == delen[1])
    leden = art.leden or []
    if len(delen) == 3:
        lid = next(l for l in leden if l.nummer == delen[2])
        return regels(lid.tekst or "", lid.onderdelen)
    return "\n\n".join(regels(l.tekst or "", l.onderdelen) for l in leden)

pad = pathlib.Path(__file__).with_name("bronteksten.json")
data = json.loads(pad.read_text(encoding="utf-8"))
for sleutel in list(data["bepalingen"]):
    nieuw = haal(sleutel)
    oud = data["bepalingen"][sleutel]
    vlag = "ONGEWIJZIGD" if nieuw == oud else f"GEWIJZIGD  {len(oud)} -> {len(nieuw)}"
    print(f"  {sleutel:22} {vlag}", file=sys.stderr)
    data["bepalingen"][sleutel] = nieuw
pad.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
