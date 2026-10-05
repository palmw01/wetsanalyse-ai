"""De export van een bronnode-weergave: JSON, CSV, PDF en TriG.

Eén weergave, vier vormen. De herkomst van een element staat in elke vorm in dezelfde woorden: de
leesbare namen uit de gegenereerde vocabulaire (`vocabulaire/verklaringen.json`), met dezelfde
opzoekregels als de Waarom-uitklap in de werkplek (`frontend/lib/waarom.ts`). Onbekende codes
verschijnen als zichzelf – liever een id dan een verzonnen omschrijving.

De bestaande CSV-kolommen staan vooraan en in dezelfde volgorde; nieuwe kolommen komen erachter. Wie
de export al inleest, merkt alleen dat er meer staat.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from rdflib import Dataset

SCHEMA_PAD = Path(__file__).parent / "schemas" / "annotatie-export-v3.schema.json"
EXPORT_VERSIE = 3

# De secties van de vocabulaire die de export opzoekt. `api/tests/test_annotatie_export.py` toetst
# dat ze bestaan en dat de werkplek (`GEBRUIKTE_SECTIES` in `frontend/lib/verklaringen.ts`) niet
# minder leest dan hier staat.
GEBRUIKTE_SECTIES = ("besluit", "detectie", "regels", "resolutie", "twijfel", "validatie")

_JURIST = {"approve": "akkoord bevonden", "edit": "aangepast", "reject": "verworpen", "heropen": "heropend"}
_OUDE_KOLOMMEN = ["soort", "id", "eigenaar_iri", "klasse", "tekst", "lifecycle", "snapshot_id", "ankers",
                  "beslissingen", "herkomst", "provenance", "laagstatus"]
_NIEUWE_KOLOMMEN = ["subtype", "aandacht", "besloten_door", "regels", "detectoren", "twijfel", "resolutieregel",
                    "mogelijke_klassen", "validatie", "gedegradeerd", "jurist"]


def naam(verklaringen: dict, sectie: str, code: str) -> str:
    """De leesbare naam van een code; een achtervoegsel (`CODE:detail`) zoekt op het deel ervoor."""
    tabel = verklaringen.get(sectie) or {}
    gevonden = tabel.get(code) or tabel.get(code.split(":")[0]) or {}
    return gevonden.get("naam") or code


def _uniek(waarden) -> list[str]:
    return list(dict.fromkeys(w for w in waarden if w))


def herkomst_regels(element: dict, verklaringen: dict) -> dict[str, Any]:
    """Het spoor van één element in leesbare woorden. Zonder spoor (een eigen markering van de jurist)
    blijven de spoorvelden leeg; `herkomst` en `jurist` zeggen dan wat er te zeggen valt."""
    spoor = element.get("trace") or {}
    kandidaat = spoor.get("kandidaat") or {}
    beslissing = spoor.get("beslissing") or {}
    door = beslissing.get("door") or ""
    besloten = naam(verklaringen, "besluit", door) if door else ""
    if door == "specificiteit" and beslissing.get("reden"):
        besloten += f" ({naam(verklaringen, 'regels', beslissing['reden'])})"
    bewijs = [b for b in kandidaat.get("bewijs") or [] if b.get("code") != "PRIORITY_APPLIED"]
    laatste = next((b for b in reversed(element.get("beslissingen") or []) if b.get("type") in _JURIST), None)
    return {
        "herkomst": element.get("herkomst", ""),
        "besloten_door": besloten,
        # Geen keuze van het model: de resolver zette de eerste mogelijke klasse voorlopig neer.
        "terugval": door == "terugval",
        "regels": _uniek(naam(verklaringen, "regels", b["regel"]) if b.get("regel")
                         else naam(verklaringen, "detectie", b.get("code", "")) for b in bewijs),
        "detectoren": _uniek(b.get("detector") for b in bewijs),
        "twijfel": _uniek(naam(verklaringen, "twijfel", t.get("reden", "")) for t in spoor.get("twijfel") or []),
        "resolutieregel": _uniek(naam(verklaringen, "resolutie", t.get("regel", "")) for t in spoor.get("resolutie") or []),
        "mogelijke_klassen": list(kandidaat.get("mogelijke_klassen") or []),
        "subtype": element.get("jas_subtype") or "",
        "validatie": _uniek(naam(verklaringen, "validatie", v.get("code", "")) for v in spoor.get("validatie") or []),
        "aandacht": element.get("aandacht") or "",
        "gedegradeerd": bool(kandidaat.get("gedegradeerd")),
        "jurist": f"{_JURIST[laatste['type']]} door {laatste.get('actor', '')} op {laatste.get('tijd', '')}".strip()
                  if laatste else "",
    }


def herkomst_zin(regels: dict) -> str:
    """Eén zin voor de PDF: wie besliste, op grond waarvan, en wat er daarna mee gebeurde."""
    if not regels["besloten_door"]:
        delen = ["door een jurist zelf gemarkeerd" if regels["herkomst"] == "mens" else "geen spoor bewaard"]
    else:
        delen = [f"{regels['besloten_door']} – de klasse is voorlopig" if regels.get("terugval")
                 else f"besloten door {regels['besloten_door']}"]
        if regels["regels"]:
            delen.append("bewijs: " + ", ".join(regels["regels"]))
        if regels["twijfel"]:
            delen.append("twijfel: " + ", ".join(regels["twijfel"]))
        if regels["resolutieregel"]:
            delen.append("afgehandeld met: " + ", ".join(regels["resolutieregel"]))
        if regels["gedegradeerd"]:
            delen.append("zonder zinsontleding beoordeeld")
    if regels["subtype"]:
        delen.append("subtype " + regels["subtype"])
    if regels["jurist"]:
        delen.append(regels["jurist"])
    return "; ".join(delen) + "."


def runs(view: dict) -> list[dict]:
    """De agent-rondes onder deze weergave, elk één keer, oudste eerst – mét hun meting."""
    gezien: dict[tuple, dict] = {}
    for e in view.get("elementen") or []:
        run = e.get("geproduceerd_door") or {}
        if run:
            gezien.setdefault((run.get("ronde"), str(run.get("tijd", "")), run.get("model")), run)
    return sorted(gezien.values(), key=lambda r: str(r.get("tijd", "")))


def json_export(view: dict, verklaringen: dict) -> bytes:
    uit = {**view, "runs": runs(view),
           "elementen": [{**e, "herkomst_regels": herkomst_regels(e, verklaringen)} for e in view["elementen"]]}
    uit["export"] = {**view.get("export", {}), "versie": EXPORT_VERSIE, "schema": "annotatie-export-v3"}
    return json.dumps(uit, ensure_ascii=False, indent=2).encode()


def _cel(value: Any) -> str:
    # Aanhalingstekens houden een spreadsheetformule niet tegen; een voorloopapostrof wel.
    value = str(value)
    return "'" + value if value[:1] in {"=", "+", "-", "@", "\t", "\r"} else value


def _lijst(waarden: list[str]) -> str:
    return "; ".join(waarden)


def csv_export(view: dict, verklaringen: dict, provenance) -> bytes:
    """Eén rij per element (plus verwijzingen, brontekst en audit). `provenance(element)` levert de
    run met het spoor, zoals de router hem ook elders gebruikt."""
    tekst = io.StringIO()
    writer = csv.writer(tekst)
    writer.writerow(_OUDE_KOLOMMEN + _NIEUWE_KOLOMMEN)
    leeg = [""] * len(_NIEUWE_KOLOMMEN)
    snapshot_id = view.get("snapshot_id", "")
    for e in view["elementen"]:
        laagstatus = next((l["status"] for l in view["lagen"] if l["id"] == e["laag_id"]), "")
        r = herkomst_regels(e, verklaringen)
        writer.writerow(["element"] + [_cel(e.get(k, "")) for k in
            ("id", "eigenaar_iri", "klasse", "tekst", "lifecycle", "snapshot_id")]
            + [json.dumps(e["ankers"], ensure_ascii=False), json.dumps(e["beslissingen"], ensure_ascii=False),
               e["herkomst"], json.dumps(provenance(e), ensure_ascii=False), laagstatus]
            + [_cel(r["subtype"]), _cel(r["aandacht"]), _cel(r["besloten_door"]), _cel(_lijst(r["regels"])),
               _cel(_lijst(r["detectoren"])), _cel(_lijst(r["twijfel"])), _cel(_lijst(r["resolutieregel"])),
               _cel(_lijst(r["mogelijke_klassen"])), _cel(_lijst(r["validatie"])),
               "ja" if r["gedegradeerd"] else "nee", _cel(r["jurist"])])
    for ref in view["verwijzingen"]:
        writer.writerow(["verwijzing", ref["id"], ref["eigenaar_iri"], ref["klasse"], ref["label"], "", snapshot_id,
                         "[]", "[]", "", "", ""] + leeg)
    for segment in view["segmenten"]:
        writer.writerow(["brontekst", "", segment["bron_iri"], "", _cel(segment["tekst"]), "", snapshot_id,
                         "[]", "[]", "", "", ""] + leeg)
    for audit in view.get("audit") or []:
        writer.writerow(["audit", audit.get("element_id", ""), "", "", "", audit["actie"], snapshot_id,
                         "[]", json.dumps(audit, ensure_ascii=False, default=str), "", "", ""] + leeg)
    return tekst.getvalue().encode("utf-8-sig")


def _seconden(ms: int) -> str:
    return f"{ms / 1000:.1f}".replace(".", ",") + " s"


def pdf_regels(view: dict, verklaringen: dict) -> list[tuple[str, str]]:
    """De inhoud van de PDF als (stijl, tekst) – los van reportlab, zodat hij testbaar is."""
    uit: list[tuple[str, str]] = [("Title", str(view["doel"].get("label", "Annotaties"))),
                                  ("BodyText", "Bronstand: " + str(view.get("snapshot_id", "")))]
    for layer in view["lagen"]:
        uit.append(("BodyText", f"{layer['bron_iri']}: {layer['status']} (revisie {layer['revisie']})"))
    for segment in view["segmenten"]:
        uit.append(("BodyText", segment.get("tekst", "")))
    uit.append(("Heading2", "Markeringen"))
    for e in view["elementen"]:
        uit.append(("Heading4", f"{e['klasse']}: {e['tekst']} ({e['lifecycle']})"))
        uit.append(("BodyText", "Eigenaar: " + e["eigenaar_iri"]))
        if e.get("toelichting"):
            uit.append(("BodyText", e["toelichting"]))
        uit.append(("BodyText", "Herkomst: " + herkomst_zin(herkomst_regels(e, verklaringen))))
        vraag = (e.get("trace") or {}).get("vraag")
        if vraag:
            uit.append(("Code", "Modelvraag: " + vraag))
        for anchor in e["ankers"]:
            uit.append(("BodyText", f"Anker: {anchor['bron_iri']} [{anchor['start']}, {anchor['eind']}) – "
                                    f"bronhash {anchor['bron_hash']} – fragment: {anchor['tekst']}"))
        if e.get("beslissingen"):
            uit.append(("BodyText", "Beoordelingen: " + "; ".join(
                f"{b.get('type', '')} door {b.get('actor', '')} op {b.get('tijd', '')}"
                + (f" ({b['comment']})" if b.get("comment") else "") for b in e["beslissingen"])))
    if view["verwijzingen"]:
        uit.append(("BodyText", "Dit bereik bevat verwijzingen naar annotaties met een ruimere bronselectie."))
        for ref in view["verwijzingen"]:
            uit.append(("BodyText", f"{ref['id']}: {ref['klasse']} — {ref['eigenaar_iri']}"))
    rondes = runs(view)
    if rondes:
        uit.append(("Heading2", "Beurtmeting"))
        for run in rondes:
            meting = (run.get("instellingen") or {}).get("meting") or {}
            fasen = meting.get("fasen") or []
            uit.append(("Heading4", f"Ronde {run.get('ronde', '')} – {run.get('model', '')} – {run.get('tijd', '')}"))
            for f in fasen:
                uit.append(("BodyText", f"{f.get('fase', '')}: {f.get('samenvatting', '')} ({_seconden(int(f.get('ms') or 0))})"))
            if fasen:
                uit.append(("BodyText", "Totaal: " + _seconden(sum(int(f.get("ms") or 0) for f in fasen))))
            if meting.get("gedegradeerd"):
                uit.append(("BodyText", f"Zonder zinsontleding: {len(meting['gedegradeerd'])} bronnode(s)."))
    structureel = (view.get("dekking") or {}).get("structureel") or {}
    if structureel:
        uit.append(("Heading2", "Dekking"))
        uit.append(("BodyText", "Wat de detectoren konden bekijken – niet of de annotatie juist of volledig is."))
        for bron_iri, m in structureel.items():
            dims = m.get("dimensies") or {}
            onvolledig = [f"{d} {s}" for d, s in dims.items() if s != "uitgevoerd"]
            uit.append(("BodyText", f"{bron_iri}: {sum(s == 'uitgevoerd' for s in dims.values())} van {len(dims)} "
                                    "dimensies volledig bekeken" + (f" ({', '.join(onvolledig)})" if onvolledig else "")))
            for deel in m.get("ongedekt") or []:
                uit.append(("BodyText", f"Zonder detectortreffer: “{deel.get('tekst', '')}”"))
    if view.get("audit"):
        uit.append(("Heading2", "Historie"))
        for audit in view["audit"]:
            uit.append(("Code", json.dumps(audit, ensure_ascii=False, default=str)))
    return uit


def pdf_export(view: dict, verklaringen: dict) -> bytes:
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    output = io.BytesIO()
    styles = getSampleStyleSheet()
    story = []
    for stijl, tekst in pdf_regels(view, verklaringen):
        if stijl == "Heading4":
            story.append(Spacer(1, 6))
        story.append(Paragraph(escape(tekst), styles[stijl]))
    SimpleDocTemplate(output).build(story)
    return output.getvalue()


def trig_export(lagen: list[tuple[str, Any]]) -> bytes:
    """De lagen als named graphs, precies zoals de projectie ze in de kennisgraaf zet:
    `lagen` = [(graph-IRI, rdflib.Graph uit `bouw_graaf`)]."""
    ds = Dataset()
    for graph_iri, graaf in lagen:
        doel = ds.graph(graph_iri)
        for triple in graaf:
            doel.add(triple)
    return ds.serialize(format="trig").encode()
