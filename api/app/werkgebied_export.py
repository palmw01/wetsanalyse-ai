"""Het hele werkgebied als één PDF: een overdrachtsdossier voor wie niet in Lex werkt.

`verzamel` leest de stand van nu met dezelfde functies als de schermen, en de bouwfuncties maken daar het gestructureerde
rapport van (`werkgebied_rapport`, ADR-009). Dat wordt (stijl, tekst) – los van reportlab, zodat de inhoud testbaar is – en
`pdf_opmaak` maakt er het bestand van.

Brongetrouw:
- Een citaat komt uit de bronboom of uit het opgeslagen anker, nooit uit afgeleide tekst, en elke bepaling draagt haar
  vindplaats en jci. Staat een ankerfragment niet meer op zijn offsets, dan staat dat bij het citaat, met toen en nu.
- Wat niet beoordeeld is, draagt dat label. Voorstellen staan in eigen delen.
- Niets verdwijnt stil: wat niet te lezen was, staat op het voorblad én op zijn plek. Is geen enkele regeling te lezen,
  dan is er geen dossier te maken (503).
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Awaitable, Callable

from fastapi import HTTPException

from . import (annotatie_v2_store, begrip_relatie_store, begrip_store, begrippen_run_store, bronselectie, db, pdf_opmaak,
               werkgebied_store)
from .annotatie_export import herkomst_regels
from .annotatie_v2_contracts import BEOORDEELD
from .bestandsnaam import met_tijd
from .jas_klassen import jas_sorteersleutel
from .pdf_opmaak import BEGRIP, BLOK_BEGIN, BLOK_EIND, INHOUD, MARKERING, PAGINA
from .werkgebied_inventaris import Resolver, bwb_van, inventaris_met_bronbomen
from .werkgebied_rapport import (_BRONROL, DOSSIERVELDEN, Bronstand, Bronvoorstel, Deelvraag, DeelvraagBron, Deelvragen, Dossier,
                                 DossierVeld, Signaal, Stand, UitgeslotenBron, Voorblad, Zoekdekking, Zoekregeling, deelvragen_regels,
                                 dossier_regels, voorblad_regels)
from .werkgebied_rapport import alinea as _alinea, datum as _datum, meervoud as _meervoud

_LIFECYCLE = {"voorgesteld": "voorstel, nog niet beoordeeld", "human_approved": "beoordeeld: akkoord",
              "edited": "beoordeeld: aangepast", "published": "beoordeeld: gepubliceerd",
              "rejected": "afgewezen", "reused": "hergebruikt, nog niet beoordeeld"}
_BEGRIPSTATUS = {"geaccordeerd": "Geaccordeerd", "concept": "Concept, nog niet geaccordeerd", "vervangen": "Vervangen"}
_KOPPELROL = {"duiding": "duidt dit begrip aan", "definitie": "ondersteunt de definitie", "context": "context"}
_BEOORDELING = {"open": "nog niet beoordeeld", "akkoord": "akkoord", "afgewezen": "afgewezen"}
_ACTUALITEIT = {"gewijzigd": "de passage veranderde", "verworpen": "de annotatie is verworpen",
                "verdwenen": "de annotatie bestaat niet meer"}
_OORDEEL = {"wel": "valt eronder", "niet": "valt er niet onder", "onzeker": "twijfel"}
_RELATIE = {"kwalificatie": "kwalificeert", "inclusie": "omvat", "uitsluiting": "omvat niet", "hierarchie": "heeft als soort",
            "verwant": "is verwant met", "opvolging": "wordt opgevolgd door"}
_DEFINITIE = {"letterlijk": "brondefinitie, letterlijk uit de wettekst", "samengesteld": "analysebegrip, samengesteld uit de wettekst",
              "geformuleerd": "analysebegrip, geformuleerd"}
_DEFINITIE_DOOR = {"lex": "voorgesteld door Lex", "analist": "door de analist"}
_LEEG = "Niet ingevuld."
_BLOK = ((BLOK_BEGIN, ""),)
_BLOK_UIT = ((BLOK_EIND, ""),)

async def verzamel(werkgebied_id: str, actor: str, resolve: Resolver,
                   toestanden: Callable[[dict], Awaitable[dict]]) -> dict:
    """De stand van nu, uit dezelfde leesfuncties als de schermen."""
    wg = await werkgebied_store.haal(werkgebied_id)
    inventaris, bomen = await inventaris_met_bronbomen(wg["bronnen"], resolve, volledige_elementen=True)
    if wg["bronnen"] and not bomen:
        raise HTTPException(503, "De brongraaf is tijdelijk niet beschikbaar; zonder wettekst is er geen dossier te maken.")
    return {"werkgebied": wg, "inventaris": inventaris, "bomen": bomen,
            "overzicht": await bronselectie.overzicht(werkgebied_id),
            "toestanden": await toestanden(wg),
            "begrippen": (await begrip_store.export(werkgebied_id, actor))["begrippen"],
            "relaties": await begrip_relatie_store.lijst(werkgebied_id),
            "groepen": await begrippen_run_store.groepen(werkgebied_id),
            "audit": await werkgebied_store.audit(werkgebied_id, None),
            "export": {"actor": actor, "op": db.utcnow().isoformat()}}


def bestandsnaam(data: dict) -> str:
    """Met het moment van de stand in het dossier, dus elke download is een eigen bestand."""
    naam = unicodedata.normalize("NFKD", data["werkgebied"]["naam"]).encode("ascii", "ignore").decode()
    naam = re.sub(r"[^a-z0-9]+", "-", naam.lower()).strip("-")[:80].rstrip("-")
    return met_tijd(f"werkgebied-{naam or data['werkgebied']['id']}", "pdf", data["export"]["op"])


def _nodes(data: dict) -> dict[str, dict]:
    uit: dict[str, dict] = {}
    for boom in data["bomen"].values():
        uit |= annotatie_v2_store.nodes_van(boom)
    return uit


def _verwijzing(iri: str, nodes: dict[str, dict]) -> str:
    """De bronreferentie: de jci, met de bron-IRI als terugval."""
    return (nodes.get(iri) or {}).get("jci") or iri


def _vindplaats(iri: str, nodes: dict[str, dict]) -> str:
    n = nodes.get(iri) or {}
    return n.get("vindplaats") or n.get("label") or iri


def _anker_afwijkingen(e: dict, nodes: dict[str, dict]) -> list[tuple[str, str, str]]:
    """Ankers die niet meer op hun plek staan: (vindplaats, toen, nu). Offsets zijn Unicode-codepoints."""
    uit = []
    for a in e.get("ankers") or []:
        n = nodes.get(a["bron_iri"])
        if n is None:
            uit.append((a["bron_iri"], a["tekst"], "de bepaling staat niet meer in de bron"))
        elif (nu := n.get("tekst", "")[a["start"]:a["eind"]]) != a["tekst"]:
            uit.append((_vindplaats(a["bron_iri"], nodes), a["tekst"], nu or "de tekst staat niet meer op deze plek"))
    return uit


def _signalen(data: dict, nodes: dict[str, dict]) -> list[Signaal]:
    """Wat een lezer moet weten voor hij dit dossier gebruikt; dezelfde punten staan ook op hun plek."""
    uit = []
    inv, toestanden = data["inventaris"], data["toestanden"]
    for s in inv["selecties"]:
        if s["onbereikbaar"]:
            uit.append(Signaal(soort="niet_in_dossier", label=s["label"], reden=s["onbereikbaar"]))
        elif s["bron_gewijzigd"]:
            uit.append(Signaal(soort="bron_veranderd", label=s["label"]))
    if not toestanden["volledig"]:
        uit.append(Signaal(soort="toestand_onvolledig"))
    uit += [Signaal(soort="na_peildatum", label=r["citeertitel"], datum=r["geldig_vanaf"]) for r in toestanden["regelingen"] if r["na_peildatum"]]
    elementen = [*inv["elementen"], *inv["afgewezen"]]
    if n := sum(bool(e.get("verouderd") or _anker_afwijkingen(e, nodes)) for e in elementen):
        uit.append(Signaal(soort="markeringen_veranderd", aantal=n))
    if n := sum(k["actualiteit"] != "actueel" for b in data["begrippen"] for k in b["koppelingen"]):
        uit.append(Signaal(soort="passages_veranderd", aantal=n))
    if opnieuw := [v["nr"] for v in data["overzicht"]["deelvragen"] if v["opnieuw_bekijken"]]:
        uit.append(Signaal(soort="opnieuw_bekijken", nrs=opnieuw))
    dekking = data["overzicht"]["zoekdekking"]
    if dekking.get("gezocht") and (dekking.get("verouderd") or not dekking.get("volledig", True)):
        uit.append(Signaal(soort="zoeken_onvolledig"))
    return uit


def _voorblad(data: dict, nodes: dict[str, dict]) -> Voorblad:
    wg = data["werkgebied"]
    return Voorblad(naam=wg["naam"], analysevraag=wg.get("analysevraag") or "", status=wg["status"], revisie=wg["revisie"],
                    thema=wg.get("thema_label") or "", peildatum=wg.get("peildatum"), peildatum_standaard=bool(wg.get("peildatum_standaard")),
                    regelingen=[Bronstand(bwb_id=r["bwb_id"], citeertitel=r["citeertitel"], geldig_vanaf=r["geldig_vanaf"],
                                          geldig_tot=r["geldig_tot"]) for r in data["toestanden"]["regelingen"]],
                    signalen=_signalen(data, nodes))


def _dossier(data: dict) -> Dossier:
    wg = data["werkgebied"]
    return Dossier(velden=[DossierVeld(veld=v, tekst=wg.get(v) or "") for v in DOSSIERVELDEN],
                   zoekbereik=[Zoekregeling(bwb_id=r["bwb_id"], label=r.get("label") or "") for r in wg.get("regelingen") or []])


def _deelvragen(data: dict) -> Deelvragen:
    wg, overzicht = data["werkgebied"], data["overzicht"]
    selecties = {s["id"]: s for s in wg["bronnen"]}
    vragen: list[Deelvraag] = []
    uitgesloten: dict[str, dict] = {}
    voorstellen: dict[str, dict] = {}
    for v in overzicht["deelvragen"]:
        vragen.append(Deelvraag(
            nr=v["nr"], vraag=v["vraag"], status=v["status"], opnieuw_bekijken=bool(v["opnieuw_bekijken"]),
            open_punten=[p["tekst"] for p in v["open_punten"]], niet_gekozen=v["telling"].get("niet_gekozen") or 0,
            bronnen=[DeelvraagBron(label=b["label"], rol=b["rol"], reden=(selecties.get(b["selectie_id"]) or {}).get("reden") or "")
                     for b in v["bronnen"]]))
        for k in v["kandidaten"]:
            doel = uitgesloten if k["stand"] == "uitgesloten" else voorstellen if k["stand"] == "voorgesteld" else None
            if doel is not None:
                doel.setdefault(k["id"], {**k, "nrs": []})["nrs"].append(v["nr"])
    dekking = overzicht["zoekdekking"]
    return Deelvragen(
        modus=overzicht["modus"], deelvragen=vragen,
        uitgesloten=[UitgeslotenBron(label=k["label"], overal=bool(k["overal"]), nrs=k["nrs"], besloten_door=k["besloten_door"] or "",
                                     reden=k["reden"] or "") for k in uitgesloten.values()],
        open_vragen=[d["vraag"] for d in wg["deelvragen"] if d.get("status") == "voorgesteld"],
        open_bronnen=[Bronvoorstel(label=k["label"], rol=k["rol"], nrs=k.get("nrs") or [])
                      for k in [*voorstellen.values(), *overzicht["zonder_deelvraag"]]],
        zoekdekking=Zoekdekking(onvolledig=[str(x) for x in dekking.get("onvolledig") or []], verouderd=bool(dekking.get("verouderd")),
                                reden=str(dekking.get("reden") or "")) if dekking.get("gezocht") else None)


def _herkomst(e: dict, verklaringen: dict) -> str:
    """Eén regel: wie stelde voor en wat deed de jurist. Het volledige spoor staat in de annotatie-export."""
    r = herkomst_regels(e, verklaringen)
    if not r["besloten_door"]:
        delen = ["door een jurist zelf gemarkeerd" if r["herkomst"] == "mens" else "geen spoor bewaard"]
    elif r["terugval"]:
        delen = [f"{r['besloten_door']} – de jurist kiest uit de mogelijke klassen"]
    else:
        delen = [f"voorgesteld door Lex ({r['besloten_door']})"]
    if r["twijfel"]:
        delen.append("twijfel: " + ", ".join(r["twijfel"]))
    if r["gedegradeerd"]:
        delen.append("zonder zinsontleding beoordeeld")
    if r["jurist"]:
        delen.append(re.sub(r"\d{4}-\d{2}-\d{2}T\S+", lambda m: _datum(m[0]), r["jurist"]))
    return "Herkomst: " + "; ".join(delen) + "."


def _markering(e: dict, nodes: dict[str, dict], verklaringen: dict, node_iri: str = "") -> list[tuple[str, str]]:
    klasse = e.get("klasse") or ""
    # Een terugval draagt geen klasse: zeg dat, en noem de keuze.
    kop = klasse or "Nog geen klasse (" + ", ".join(a.get("klasse", "") for a in e.get("alternatieven") or []) + ")"
    if e.get("jas_subtype"):
        kop += f", {e['jas_subtype']}"
    uit = [*_BLOK, (MARKERING + klasse, f"{kop} · {_LIFECYCLE.get(e['lifecycle'], e['lifecycle'])}"),
           ("Citaat", f"“{e['tekst']}”")]
    for iri in dict.fromkeys(a["bron_iri"] for a in e.get("ankers") or []):
        if iri != node_iri:
            uit.append(("Meta", f"Vindplaats: {_vindplaats(iri, nodes)} · {_verwijzing(iri, nodes)}"))
    if e.get("toelichting"):
        uit.append(("BodyText", e["toelichting"]))
    uit.append(("Meta", _herkomst(e, verklaringen)))
    for plek, toen, nu in _anker_afwijkingen(e, nodes):
        uit.append(("Waarschuwing", f"Brontekst gewijzigd bij {plek}. Toen: “{toen}” Nu: “{nu}”"))
    if e.get("verouderd") and not _anker_afwijkingen(e, nodes):
        uit.append(("Waarschuwing", "Verouderd: de bepaling veranderde na het annoteren."))
    if e.get("deels_buiten"):
        uit.append(("Meta", "Deze markering valt deels buiten de bronselectie."))
    return [*uit, *_BLOK_UIT]


def _kop_van(iri: str, nodes: dict[str, dict]) -> str:
    """De bepaling waarin een bronnode staat: het kopje waaronder haar tekst komt."""
    gezien: set[str] = set()
    while iri in nodes and iri not in gezien:
        gezien.add(iri)
        if nodes[iri]["type"] in ("Artikel", "Divisie"):
            return iri
        iri = nodes[iri].get("parent_iri") or ""
    return ""


def _regeling_titel(bwb: str, data: dict) -> str:
    for r in data["toestanden"]["regelingen"]:
        if r["bwb_id"] == bwb and r["citeertitel"] != bwb:
            return r["citeertitel"]
    for r in data["werkgebied"].get("regelingen") or []:
        if r["bwb_id"] == bwb and r.get("label"):
            return r["label"]
    return bwb


def _wettekst(data: dict, nodes: dict[str, dict], verklaringen: dict) -> list[tuple[str, str]]:
    """Per regeling, in de volgorde van de bronboom, elke bronnode één keer met haar markeringen eronder."""
    inv = data["inventaris"]
    uit: list[tuple[str, str]] = [(PAGINA, ""), ("Heading1", "3. Wettekst en annotaties")]
    per_klasse = Counter(e.get("klasse") or "Nog geen klasse" for e in inv["elementen"])
    beoordeeld = sum(e["lifecycle"] in BEOORDEELD for e in inv["elementen"])
    uit.append(("BodyText", f"{_meervoud(len(inv['elementen']), 'markering', 'markeringen')}, waarvan {beoordeeld} "
                            f"beoordeeld door een jurist; {len(inv['afgewezen'])} afgewezen."))
    for klasse in sorted(per_klasse, key=jas_sorteersleutel):
        uit.append(("Meta", f"{klasse}: {per_klasse[klasse]}"))

    per_eigenaar: dict[str, list[dict]] = {}
    for e in inv["elementen"]:
        per_eigenaar.setdefault(e["eigenaar_iri"], []).append(e)
    rollen: dict[str, str] = {}                      # bronnode → rol; analyseren wint van context
    gewijzigd: set[str] = set()
    per_bwb: dict[str, list[dict]] = {}
    onbereikbaar: list[dict] = []
    selecties = {s["id"]: s for s in data["werkgebied"]["bronnen"]}
    for regel in inv["selecties"]:
        sel = selecties[regel["id"]]
        if regel["onbereikbaar"]:
            onbereikbaar.append(regel)
            continue
        boom = data["bomen"][bwb_van(sel)]
        scope = annotatie_v2_store.bereik_van(boom, sel["bron_iri"]) if sel["bereik"] == "onderliggend" else {sel["bron_iri"]}
        for iri in scope:
            if sel["rol"] == "analyseren" or iri not in rollen:
                rollen[iri] = sel["rol"]
        if regel["bron_gewijzigd"]:
            gewijzigd.add(sel["bron_iri"])
        per_bwb.setdefault(bwb_van(sel), [])

    getoond: set[str] = set()
    for bwb in per_bwb:
        uit += [(PAGINA, ""), ("Heading2", _regeling_titel(bwb, data))]
        boom = annotatie_v2_store.nodes_van(data["bomen"][bwb])
        reeks = sorted((n for iri, n in boom.items() if iri in rollen),
                       key=lambda n: n.get("volgorde", 0))
        kop = None
        for node in reeks:
            iri, eigen = node["bron_iri"], per_eigenaar.get(node["bron_iri"], [])
            if not (node.get("tekst") or "").strip() and not eigen:
                continue
            nieuw = _kop_van(iri, nodes) or iri
            if nieuw != kop:
                kop = nieuw
                uit.append(("Heading3", _vindplaats(kop, nodes)))
            uit.append(("Meta", f"{_vindplaats(iri, nodes)} · rol {_BRONROL.get(rollen[iri], rollen[iri])} · {_verwijzing(iri, nodes)}"))
            if iri in gewijzigd:
                uit.append(("Waarschuwing", "Deze bron veranderde sinds de selectie."))
            if (node.get("tekst") or "").strip():
                uit.append(("Citaat", node["tekst"]))
            for e in eigen:
                uit += _markering(e, nodes, verklaringen, iri)
                getoond.add(e["id"])
    for regel in onbereikbaar:
        uit.append(("Heading3", regel["label"]))
        uit.append(("Waarschuwing", f"De tekst ontbreekt: {regel['onbereikbaar']}"))
    rest = [e for e in inv["elementen"] if e["id"] not in getoond]
    if rest:
        uit += [(PAGINA, ""), ("Heading2", "Markeringen buiten de getoonde tekst")]
        for e in rest:
            uit += _markering(e, nodes, verklaringen)
    uit += [(PAGINA, ""), ("Heading2", "Afgewezen markeringen")]
    if not inv["afgewezen"]:
        uit.append(("Meta", "Er zijn geen markeringen afgewezen."))
    else:
        uit.append(("Meta", "Deze markeringen verwierp een jurist; ze horen niet tot de analyse."))
    for e in inv["afgewezen"]:
        uit += _markering(e, nodes, verklaringen)
    return uit


def _passage(k: dict, elementen: dict[str, dict], nodes: dict[str, dict]) -> list[tuple[str, str]]:
    bewijs = k["bewijs"]
    ankers = bewijs.get("ankers") or []
    iri = ankers[0]["bron_iri"] if ankers else bewijs.get("eigenaar_iri", "")
    plek = bewijs.get("vindplaats") or _vindplaats(iri, nodes)
    uit = [("Citaat", f"“{bewijs.get('tekst', '')}”"),
           ("Meta", " · ".join(filter(None, [plek, _verwijzing(iri, nodes) if iri else "", bewijs.get("klasse"),
                                             _KOPPELROL.get(k["rol"], k["rol"]),
                                             "passage " + _BEOORDELING.get(k["beoordeling"], k["beoordeling"]),
                                             None if k["annotatie_beoordeeld"] else "annotatie nog niet beoordeeld"])))]
    if k.get("motivatie"):
        uit.append(("Meta", "Motivatie: " + k["motivatie"]))
    if k["actualiteit"] != "actueel":
        nu = elementen.get(k["element_id"])
        uit.append(("Waarschuwing", f"Na bevestiging: {_ACTUALITEIT.get(k['actualiteit'], k['actualiteit'])}. "
                                    f"Toen: “{bewijs.get('tekst', '')}”"
                    + (f" Nu: “{nu['tekst']}”" if nu else "")))
    return uit


def _begrip(b: dict, data: dict, elementen: dict[str, dict], nodes: dict[str, dict], redenen: dict[str, str]) -> list[tuple[str, str]]:
    """Eén begrip op een eigen pagina: elke pagina heeft dezelfde kopjes in dezelfde volgorde, ook als er niets staat."""
    i = b["inhoud"]
    uit: list[tuple[str, str]] = [(BEGRIP, i["naam"])]
    meta = [_BEGRIPSTATUS.get(b["status"], b["status"])]
    if b.get("kader") == "generiek":
        meta.append("generiek begrip, gebruikt in dit werkgebied")
    uit.append(("Meta", " · ".join(meta)))
    if i.get("alternatieve_termen"):
        uit.append(("BodyText", "Ook genoemd: " + ", ".join(i["alternatieve_termen"])))

    uit.append(("Heading4", "Definitie"))
    if (i.get("definitie") or "").strip():
        aard = [_DEFINITIE.get(i.get("definitie_herkomst") or "", "definitie"), _DEFINITIE_DOOR.get(i.get("definitie_door") or "", "")]
        uit.append(("Citaat" if i.get("definitie_herkomst") == "letterlijk" else "BodyText", i["definitie"]))
        uit.append(("Meta", ", ".join(filter(None, aard)) + "."))
    else:
        uit.append(("Meta", _LEEG))
    uit.append(("Heading4", "Uitleg"))
    uit += _alinea(i.get("uitleg") or "") or [("Meta", _LEEG)]
    uit.append(("Heading4", "Toelichting"))
    uit += _alinea(i.get("context") or "") or [("Meta", _LEEG)]
    uit.append(("Heading4", "Voorbeelden"))
    uit += [("BodyText", f"{_OORDEEL.get(v['oordeel'], v['oordeel']).capitalize()}: {v['tekst']}") for v in i.get("voorbeelden") or []] \
        or [("Meta", _LEEG)]

    uit.append(("Heading4", "Waarop de definitie rust"))
    o = b.get("definitie_onderbouwing") or {}
    if o.get("fragmenten"):
        if o.get("aangepast"):
            uit.append(("Meta", "De analist paste de definitie aan; deze fragmenten waren het vertrekpunt."))
        for f in o["fragmenten"]:
            uit += [("Citaat", f"“{f['tekst']}”"), ("Meta", f"{_vindplaats(f['bron_iri'], nodes)} · {_verwijzing(f['bron_iri'], nodes)}")]
    else:
        uit.append(("Meta", "Geen fragmenten vastgelegd."))

    uit.append(("Heading4", "Passages"))
    if b["koppelingen"]:
        uit.append(("Meta", _meervoud(len(b["koppelingen"]), "passage", "passages")))
        for k in sorted(b["koppelingen"], key=lambda k: (("duiding", "definitie", "context").index(k["rol"])
                                                         if k["rol"] in ("duiding", "definitie", "context") else 9)):
            uit += _passage(k, elementen, nodes)
    else:
        uit.append(("Meta", "Geen passages gekoppeld."))

    uit.append(("Heading4", "Relaties"))
    relaties = [r for r in data["relaties"]["relaties"] if r["beoordeling"] == "akkoord" and b["id"] in (r["van_begrip"], r["naar_begrip"])]
    uit += [("BodyText", f"{r['van_naam']} {_RELATIE.get(r['type'], r['type'])} {r['naar_naam']}"
             + (f": {r['toelichting']}" if r.get("toelichting") else "")) for r in relaties] or [("Meta", "Geen relaties vastgelegd.")]

    uit.append(("Heading4", "Nog open"))
    uit += [("Waarschuwing", p) for p in b.get("aandachtspunten") or []] or [("Meta", "Geen open punten.")]

    uit.append(("Heading4", "Beoordeling"))
    if b["status"] == "geaccordeerd":
        reden = redenen.get(b["id"])
        uit.append(("Meta", f"Geaccordeerd door {b['geaccordeerd_door']} op {_datum(b['geaccordeerd_op'])}"
                    + (f". Reden: {reden}" if reden else ".")))
    elif b.get("vervangen_door"):
        uit.append(("Meta", "Vervangen door een opvolger; dit begrip is alleen nog te lezen."))
    else:
        uit.append(("Meta", "Nog niet geaccordeerd."))
    return uit


def _begrippen(data: dict, nodes: dict[str, dict]) -> list[tuple[str, str]]:
    inv = data["inventaris"]
    elementen = {e["id"]: e for e in [*inv["elementen"], *inv["afgewezen"]]}
    redenen: dict[str, str] = {}
    for a in reversed(data["audit"]):                # de audit komt nieuwste eerst: de laatste reden wint
        if a["actie"] == "begrip-geaccordeerd" and (a["detail"] or {}).get("begrip_id"):
            redenen[a["detail"]["begrip_id"]] = a["detail"].get("reden") or ""
    uit: list[tuple[str, str]] = [(PAGINA, ""), ("Heading1", "4. Begrippen"),
                                  ("Meta", "Begrippen zijn analyse-uitkomsten van dit werkgebied, geen wettelijke definities.")]
    if not data["begrippen"]:
        uit.append(("Meta", "Dit werkgebied heeft nog geen begrippen."))
    # Een groepskop staat boven zijn eerste begrip, dus de breuk komt vóór de kop en niet erna: een kop blijft nooit alleen.
    eerste_groep = True
    for status, kop in (("geaccordeerd", "Geaccordeerde begrippen"), ("concept", "Conceptbegrippen"), ("vervangen", "Vervangen begrippen")):
        groep = sorted((b for b in data["begrippen"] if b["status"] == status), key=lambda b: b["inhoud"]["naam"].casefold())
        if not groep:
            continue
        if not eerste_groep:
            uit.append((PAGINA, ""))
        eerste_groep = False
        uit.append(("Heading2", f"{kop} ({len(groep)})"))
        if status == "concept":
            uit.append(("Meta", "Nog niet geaccordeerd: de inhoud kan veranderen."))
        for n, b in enumerate(groep):
            if n:
                uit.append((PAGINA, ""))
            uit += _begrip(b, data, elementen, nodes, redenen)
    open_groepen = [g for g in data["groepen"]["groepen"] if g["besluit"] in ("open", "geparkeerd") and g["leden"]]
    voorstellen = data["relaties"]["voorstellen"]
    if data["begrippen"]:
        uit.append((PAGINA, ""))
    uit.append(("Heading2", "Open voorstellen van Lex"))
    if not open_groepen and not voorstellen:
        uit.append(("Meta", "Er staan geen voorstellen open."))
    else:
        uit.append(("Meta", "Hierover is nog geen besluit genomen; ze horen niet tot de analyse."))
    for g in open_groepen:
        definitie = (g.get("kaart") or {}).get("definitie") or g["voorstel"].get("definitie")
        uit.append(("Voorstel", f"Voorstel voor een begrip: {g['voorstel']['naam']}" + (f". Definitie: {definitie}" if definitie else "")))
        uit += [("Meta", f"“{p['tekst']}” · {p['vindplaats'] or _vindplaats(p['bron_iri'], nodes)} · {_verwijzing(p['bron_iri'], nodes)}") for p in g["leden"]]
    for r in voorstellen:
        uit.append(("Voorstel", f"Voorstel voor een relatie: {r.get('van_naam', '')} {_RELATIE.get(r['type'], r['type'])} {r.get('naar_naam', '')}"))
    return uit


def _verantwoording(data: dict, nodes: dict[str, dict]) -> list[tuple[str, str]]:
    wg, inv = data["werkgebied"], data["inventaris"]
    uit: list[tuple[str, str]] = [(PAGINA, ""), ("Heading1", "5. Verantwoording"), ("Heading2", "Wie deed wat")]
    uit.append(("BodyText", f"Aangemaakt door {wg['aangemaakt_door']} op {_datum(wg['aangemaakt'])}, "
                            f"laatst gewijzigd op {_datum(wg['gewijzigd'])}."))
    juristen = sorted({b["actor"] for e in [*inv["elementen"], *inv["afgewezen"]] for b in e.get("beslissingen") or [] if b.get("actor")})
    if juristen:
        uit.append(("BodyText", "Markeringen beoordeeld door: " + ", ".join(juristen) + "."))
    accordeurs = sorted({b["geaccordeerd_door"] for b in data["begrippen"] if b["status"] == "geaccordeerd" and b["geaccordeerd_door"]})
    if accordeurs:
        uit.append(("BodyText", "Begrippen geaccordeerd door: " + ", ".join(accordeurs) + "."))
    uit.append(("Heading2", "Handelingen in dit werkgebied"))
    uit.append(("Meta", _meervoud(len(data["audit"]), "handeling", "handelingen") + " in de audit, per soort:"))
    for actie, n in Counter(a["actie"] for a in data["audit"]).most_common():
        uit.append(("Meta", f"{actie.replace('-', ' ')}: {n}"))
    uit.append(("Heading2", "Bronnen"))
    for s in wg["bronnen"]:
        uit.append(("BodyText", s["label"]))
        uit.append(("Meta", f"Rol {_BRONROL.get(s['rol'], s['rol'])} · {_verwijzing(s['bron_iri'], nodes)}"))
    return uit


def pdf_regels(data: dict, verklaringen: dict) -> list[tuple[str, str]]:
    """De inhoud van de PDF als (stijl, tekst)."""
    nodes = _nodes(data)
    stand = Stand(op=data["export"]["op"], door=data["export"]["actor"])
    return [*voorblad_regels(_voorblad(data, nodes), stand), (PAGINA, ""), ("Heading4", "Inhoud"), (INHOUD, ""),
            *dossier_regels(_dossier(data)), *deelvragen_regels(_deelvragen(data)),
            *_wettekst(data, nodes, verklaringen), *_begrippen(data, nodes),
            *_verantwoording(data, nodes)]


def pdf_export(data: dict, verklaringen: dict) -> bytes:
    naam = data["werkgebied"]["naam"]
    return pdf_opmaak.render(pdf_regels(data, verklaringen), titel=naam,
                             voet=f"{naam} · stand van {_datum(data['export']['op'])}")
