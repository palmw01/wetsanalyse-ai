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

from rdflib import Dataset

from . import pdf_opmaak

EXPORT_VERSIE = 4
SCHEMA_NAAM = f"annotatie-export-v{EXPORT_VERSIE}"
SCHEMA_PAD = Path(__file__).parent / "schemas" / f"{SCHEMA_NAAM}.schema.json"

# De secties van de vocabulaire die de export opzoekt. `api/tests/test_annotatie_export.py` toetst
# dat ze bestaan en dat de werkplek (`GEBRUIKTE_SECTIES` in `frontend/lib/verklaringen.ts`) niet
# minder leest dan hier staat.
GEBRUIKTE_SECTIES = ("besluit", "detectie", "regels", "resolutie", "twijfel", "validatie")

_JURIST = {"approve": "akkoord bevonden", "edit": "aangepast", "reject": "verworpen", "heropen": "heropend"}
_OUDE_KOLOMMEN = ["soort", "id", "eigenaar_iri", "klasse", "tekst", "lifecycle", "snapshot_id", "ankers",
                  "beslissingen", "herkomst", "provenance", "laagstatus"]
_NIEUWE_KOLOMMEN = ["subtype", "aandacht", "besloten_door", "regels", "detectoren", "twijfel", "resolutieregel",
                    "mogelijke_klassen", "validatie", "gedegradeerd", "jurist"]
# Relaties tussen markeringen (ADR-011): alleen gevuld op een rij van soort `relatie`.
_RELATIEKOLOMMEN = ["leesvorm", "relatietype", "van_klasse", "van_tekst", "naar_klasse", "naar_tekst", "volgorde", "veranderd"]


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
        delen = [f"{regels['besloten_door']} – de jurist kiest uit de mogelijke klassen" if regels.get("terugval")
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
    # v4: de relaties tussen markeringen en de impliciete partijen staan er expliciet in, ook als er geen zijn.
    uit["relaties"] = list(view.get("relaties") or [])
    uit["impliciet"] = list(view.get("impliciet") or [])
    uit["export"] = {**view.get("export", {}), "versie": EXPORT_VERSIE, "schema": SCHEMA_NAAM}
    return json.dumps(uit, ensure_ascii=False, indent=2).encode()


def cel(value: Any) -> str:
    """Eén CSV-cel die een spreadsheet niet als formule leest (CSV-injectie). Aanhalingstekens houden een formule niet
    tegen; een voorloopapostrof wel. Elke CSV-export van de api gebruikt deze, ook `begrip_store.csv_export`."""
    value = str(value)
    return "'" + value if value[:1] in {"=", "+", "-", "@", "\t", "\r"} else value


def _lijst(waarden: list[str]) -> str:
    return "; ".join(waarden)


def eindpunt(kant: dict) -> str:
    """Eén kant van een relatie in woorden: de tekst van de markering (of het label van de impliciete partij) en haar klasse."""
    if not kant.get("bestaat", True):
        return "een eindpunt dat niet meer bestaat"
    soort = ", impliciete partij" if kant.get("soort") == "impliciet" else ""
    return f"“{kant.get('tekst', '')}” ({kant.get('klasse', '')}{soort})"


def relatie_zin(r: dict) -> str:
    """"“de ontvanger” (Rechtssubject) is plichthebbende van “…” (Rechtsbetrekking)": de leesvorm tussen de twee kanten."""
    return f"{eindpunt(r['van'])} {r.get('leesvorm') or r['type']} {eindpunt(r['naar'])}"


def csv_export(view: dict, verklaringen: dict, provenance) -> bytes:
    """Eén rij per element (plus verwijzingen, brontekst, audit en relaties). `provenance(element)` levert de
    run met het spoor, zoals de router hem ook elders gebruikt."""
    tekst = io.StringIO()
    writer = csv.writer(tekst)
    writer.writerow(_OUDE_KOLOMMEN + _NIEUWE_KOLOMMEN + _RELATIEKOLOMMEN)
    leeg = [""] * (len(_NIEUWE_KOLOMMEN) + len(_RELATIEKOLOMMEN))
    geen_relatie = [""] * len(_RELATIEKOLOMMEN)
    snapshot_id = view.get("snapshot_id", "")
    for e in view["elementen"]:
        laagstatus = next((l["status"] for l in view["lagen"] if l["id"] == e["laag_id"]), "")
        r = herkomst_regels(e, verklaringen)
        writer.writerow(["element"] + [cel(e.get(k, "")) for k in
            ("id", "eigenaar_iri", "klasse", "tekst", "lifecycle", "snapshot_id")]
            + [json.dumps(e["ankers"], ensure_ascii=False), json.dumps(e["beslissingen"], ensure_ascii=False),
               e["herkomst"], json.dumps(provenance(e), ensure_ascii=False), laagstatus]
            + [cel(r["subtype"]), cel(r["aandacht"]), cel(r["besloten_door"]), cel(_lijst(r["regels"])),
               cel(_lijst(r["detectoren"])), cel(_lijst(r["twijfel"])), cel(_lijst(r["resolutieregel"])),
               cel(_lijst(r["mogelijke_klassen"])), cel(_lijst(r["validatie"])),
               "ja" if r["gedegradeerd"] else "nee", cel(r["jurist"])] + geen_relatie)
    for ref in view["verwijzingen"]:
        writer.writerow(["verwijzing", ref["id"], ref["eigenaar_iri"], ref["klasse"], ref["label"], "", snapshot_id,
                         "[]", "[]", "", "", ""] + leeg)
    for segment in view["segmenten"]:
        writer.writerow(["brontekst", "", segment["bron_iri"], "", cel(segment["tekst"]), "", snapshot_id,
                         "[]", "[]", "", "", ""] + leeg)
    for audit in view.get("audit") or []:
        writer.writerow(["audit", audit.get("element_id", ""), "", "", "", audit["actie"], snapshot_id,
                         "[]", json.dumps(audit, ensure_ascii=False, default=str), "", "", ""] + leeg)
    for rel in view.get("relaties") or []:
        laagstatus = next((l["status"] for l in view["lagen"] if l["id"] == rel.get("laag_id")), "")
        van, naar = rel["van"], rel["naar"]
        writer.writerow(["relatie", rel["id"], "", "", cel(relatie_zin(rel)), cel(rel.get("lifecycle", "")), snapshot_id,
                         "[]", json.dumps(rel.get("beslissingen") or [], ensure_ascii=False), cel(rel.get("herkomst", "")), "",
                         laagstatus]
                        + [""] * len(_NIEUWE_KOLOMMEN)
                        + [cel(rel.get("leesvorm", "")), cel(rel["type"]), cel(van.get("klasse", "")), cel(van.get("tekst", "")),
                           cel(naar.get("klasse", "")), cel(naar.get("tekst", "")),
                           "" if rel.get("volgorde") is None else str(rel["volgorde"]), "ja" if rel.get("veranderd") else "nee"])
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
        # Een terugval draagt geen klasse: zeg dat, en noem de keuze.
        kop = e["klasse"] or "Nog geen klasse (" + ", ".join(a.get("klasse", "") for a in e.get("alternatieven") or []) + ")"
        uit.append(("Heading4", f"{kop}: {e['tekst']} ({e['lifecycle']})"))
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
    uit += _relatie_regels(view)
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
            gevonden = m.get("aangetroffen") or {}
            if gevonden:
                # Gezocht is niet hetzelfde als gevonden: per dimensie wat er aangetroffen werd.
                uit.append(("BodyText", "Gevonden: " + " · ".join(
                    f"{d} {gevonden[d] if gevonden.get(d) else 'niets'}" for d in dims if d in gevonden)))
            for deel in m.get("ongedekt") or []:
                uit.append(("BodyText", f"Zonder detectortreffer: “{deel.get('tekst', '')}”"))
            for deel in m.get("alleen_als_geheel") or []:
                # Geraakt, maar alleen door een kandidaat over het geheel: binnen de zin niets gevonden.
                uit.append(("BodyText", f"Alleen als geheel gemarkeerd: “{deel.get('tekst', '')}”"))
    if view.get("audit"):
        uit.append(("Heading2", "Historie"))
        for audit in view["audit"]:
            uit.append(("Code", json.dumps(audit, ensure_ascii=False, default=str)))
    return uit


def _relatie_regels(view: dict) -> list[tuple[str, str]]:
    """Per bepaling (de laag die de relatie draagt) een korte lijst, geen tabel; daarna de impliciete partijen."""
    relaties = view.get("relaties") or []
    if not relaties and not view.get("impliciet"):
        return []
    labels = {s["bron_iri"]: s.get("label") or s["bron_iri"] for s in view.get("segmenten") or []}
    lagen = {l["id"]: l["bron_iri"] for l in view["lagen"]}
    uit: list[tuple[str, str]] = [("Heading2", "Relaties")]
    groepen: dict[str, list[dict]] = {}
    for r in relaties:
        groepen.setdefault(lagen.get(r.get("laag_id"), ""), []).append(r)
    for bron_iri in [*(l["bron_iri"] for l in view["lagen"]), ""]:
        if bron_iri not in groepen:
            continue
        uit.append(("Heading4", labels.get(bron_iri, bron_iri) if bron_iri else "Met de drager in een andere bepaling"))
        for r in groepen[bron_iri]:
            plek = f" · plek {r['volgorde']}" if r.get("volgorde") is not None else ""
            uit.append(("BodyText", f"{relatie_zin(r)}{plek} ({r.get('lifecycle', '')})"))
            if r.get("toelichting"):
                uit.append(("BodyText", "Toelichting: " + r["toelichting"]))
            if r.get("veranderd"):
                uit.append(("BodyText", "Veranderd: een eindpunt veranderde na het vastleggen; deze relatie vraagt opnieuw een oordeel."))
    if view.get("impliciet"):
        uit.append(("Heading4", "Impliciete partijen"))
        for p in view["impliciet"]:
            uit.append(("BodyText", f"{p.get('label', '')} ({p.get('klasse', '')}): {p.get('toelichting', '')}"))
    return uit


def pdf_export(view: dict, verklaringen: dict) -> bytes:
    return pdf_opmaak.render(pdf_regels(view, verklaringen), titel=str(view["doel"].get("label", "Annotaties")))


def trig_export(lagen: list[tuple[str, Any]]) -> bytes:
    """De lagen als named graphs, precies zoals de projectie ze in de kennisgraaf zet:
    `lagen` = [(graph-IRI, rdflib.Graph uit `bouw_graaf`)]."""
    ds = Dataset()
    for graph_iri, graaf in lagen:
        doel = ds.graph(graph_iri)
        for triple in graaf:
            doel.add(triple)
    return ds.serialize(format="trig").encode()
