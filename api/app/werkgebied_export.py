"""Het hele werkgebied als één rapport: een overdrachtsdossier voor wie niet in Lex werkt.

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

from bronmodel.antwoord import Vindplaats
from fastapi import HTTPException

from . import (annotatie_v2_store, begrip_relatie_store, begrip_store, begrippen_run_store, bronselectie, db, markdown_opmaak,
               pdf_opmaak, werkgebied_store)
from .annotatie_export import herkomst_regels
from .annotatie_v2_contracts import BEOORDEELD
from .bestandsnaam import met_tijd
from .jas_klassen import jas_sorteersleutel
from .werkgebied_inventaris import Resolver, bwb_van, inventaris_met_bronbomen
from .werkgebied_rapport import (DOSSIERVELDEN, Afwijking, Artikel, Begrip, Begrippen, Bepaling, Bronvoorstel, Deelvraag,
                                 DeelvraagBron, Deelvragen, Document, Dossier, DossierVeld, Fragment, Besluit, Handeling, Herkomst, Kerncijfers, KlasseTelling, Markering,
                                 Onbereikbaar, OpenGroep, OpenRelatie, Passage, Rapport, Regel, Regeling, RegelingInfo, Span, Structuurdeel, Verwijzing, Relatie, Selectie, Signaal,
                                 Stand, Telling, UitgeslotenBron, Verantwoording, Voorbeeld, Voorblad, Wettekst, Zoekdekking, Zoekregeling,
                                 BESLUITEN, datum, inhoud_hash, kort, rapport_regels)


GraafLezer = Callable[[list[str], list[str], list[str]], Awaitable[dict]]


async def _geen_graaf(_bwbs: list[str], _iris: list[str], _bronnen: list[str]) -> dict:
    return {"volledig": True, "regelingen": {}, "structuur": {}, "verwijzingen": [], "verwijzingen_volledig": True}


def bron_iris(wg: dict, bomen: dict) -> list[str]:
    """Elke bronnode in het dossier: daaruit vertrekken de verwijzingen die het rapport toont."""
    uit: set[str] = set()
    for sel in wg["bronnen"]:
        boom = bomen.get(bwb_van(sel))
        if boom:
            uit |= annotatie_v2_store.bereik_van(boom, sel["bron_iri"]) if sel["bereik"] == "onderliggend" else {sel["bron_iri"]}
    return sorted(uit)


def structuur_iris(wg: dict, bomen: dict) -> list[str]:
    """De voorouders van elke geselecteerde bronnode tot de regeling: daarvan wil het rapport titel en inwerkingtreding."""
    uit: set[str] = set()
    for sel in wg["bronnen"]:
        boom = bomen.get(bwb_van(sel))
        if not boom:
            continue
        nodes = annotatie_v2_store.nodes_van(boom)
        scope = annotatie_v2_store.bereik_van(boom, sel["bron_iri"]) if sel["bereik"] == "onderliggend" else {sel["bron_iri"]}
        for iri in scope:
            gezien: set[str] = set()
            while iri in nodes and iri not in gezien:
                gezien.add(iri)
                if nodes[iri].get("parent_iri") and nodes[iri]["type"] not in ("Lid", "Onderdeel"):     # de wortel is de regeling
                    uit.add(iri)
                iri = nodes[iri].get("parent_iri") or ""
    return sorted(uit)


async def verzamel(werkgebied_id: str, actor: str, resolve: Resolver,
                   toestanden: Callable[[dict], Awaitable[dict]], graaf: GraafLezer = _geen_graaf) -> dict:
    """De stand van nu, uit dezelfde leesfuncties als de schermen, en wat de graaf over regeling en opbouw weet."""
    wg = await werkgebied_store.haal(werkgebied_id)
    inventaris, bomen = await inventaris_met_bronbomen(wg["bronnen"], resolve, volledige_elementen=True)
    if wg["bronnen"] and not bomen:
        raise HTTPException(503, "De brongraaf is tijdelijk niet beschikbaar; zonder wettekst is er geen dossier te maken.")
    tst = await toestanden(wg)
    return {"werkgebied": wg, "inventaris": inventaris, "bomen": bomen,
            "graaf": await graaf([r["bwb_id"] for r in tst["regelingen"]], structuur_iris(wg, bomen), bron_iris(wg, bomen)),
            "overzicht": await bronselectie.overzicht(werkgebied_id),
            "toestanden": tst,
            "begrippen": (await begrip_store.export(werkgebied_id, actor))["begrippen"],
            "relaties": await begrip_relatie_store.lijst(werkgebied_id),
            "groepen": await begrippen_run_store.groepen(werkgebied_id),
            "audit": await werkgebied_store.audit(werkgebied_id, None),
            "export": {"actor": actor, "op": db.utcnow().isoformat()}}


def bestandsnaam(data: dict, extensie: str = "pdf") -> str:
    """Met het moment van de stand in het dossier, dus elke download is een eigen bestand."""
    naam = unicodedata.normalize("NFKD", data["werkgebied"]["naam"]).encode("ascii", "ignore").decode()
    naam = re.sub(r"[^a-z0-9]+", "-", naam.lower()).strip("-")[:80].rstrip("-")
    return met_tijd(f"werkgebied-{naam or data['werkgebied']['id']}", extensie, data["export"]["op"])


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
    if not data.get("graaf", {}).get("volledig", True):
        uit.append(Signaal(soort="graaf_onvolledig"))
    dekking = data["overzicht"]["zoekdekking"]
    if dekking.get("gezocht") and (dekking.get("verouderd") or not dekking.get("volledig", True)):
        uit.append(Signaal(soort="zoeken_onvolledig"))
    return uit


def _voorblad(data: dict, nodes: dict[str, dict]) -> Voorblad:
    wg = data["werkgebied"]
    return Voorblad(naam=wg["naam"], analysevraag=wg.get("analysevraag") or "", status=wg["status"], revisie=wg["revisie"],
                    thema=wg.get("thema_label") or "", peildatum=wg.get("peildatum"), peildatum_standaard=bool(wg.get("peildatum_standaard")),
                    regelingen=[RegelingInfo(bwb_id=r["bwb_id"], citeertitel=r["citeertitel"], geldig_vanaf=r["geldig_vanaf"],
                                             geldig_tot=r["geldig_tot"], **_graaf(data)["regelingen"].get(r["bwb_id"], {}))
                                for r in data["toestanden"]["regelingen"]],
                    signalen=_signalen(data, nodes))


def _dossier(data: dict) -> Dossier:
    wg = data["werkgebied"]
    return Dossier(velden=[DossierVeld(veld=v, tekst=wg.get(v) or "") for v in DOSSIERVELDEN],
                   zoekbereik=[Zoekregeling(bwb_id=r["bwb_id"], label=r.get("label") or "") for r in wg.get("regelingen") or []])


def _deelvragen(data: dict, nodes: dict[str, dict]) -> Deelvragen:
    wg, overzicht = data["werkgebied"], data["overzicht"]
    selecties = {s["id"]: s for s in wg["bronnen"]}
    vragen: list[Deelvraag] = []
    uitgesloten: dict[str, dict] = {}
    voorstellen: dict[str, dict] = {}
    for v in overzicht["deelvragen"]:
        vragen.append(Deelvraag(
            nr=v["nr"], vraag=v["vraag"], status=v["status"], opnieuw_bekijken=bool(v["opnieuw_bekijken"]),
            open_punten=[p["tekst"] for p in v["open_punten"]], niet_gekozen=v["telling"].get("niet_gekozen") or 0,
            bronnen=[DeelvraagBron(vindplaats=_plek(b["bron_iri"], nodes, b["label"]), rol=b["rol"], reden=(selecties.get(b["selectie_id"]) or {}).get("reden") or "")
                     for b in v["bronnen"]]))
        for k in v["kandidaten"]:
            doel = uitgesloten if k["stand"] == "uitgesloten" else voorstellen if k["stand"] == "voorgesteld" else None
            if doel is not None:
                doel.setdefault(k["id"], {**k, "nrs": []})["nrs"].append(v["nr"])
    dekking = overzicht["zoekdekking"]
    return Deelvragen(
        modus=overzicht["modus"], deelvragen=vragen,
        uitgesloten=[UitgeslotenBron(vindplaats=_plek(k["bron_iri"], nodes, k["label"]), overal=bool(k["overal"]), nrs=k["nrs"], besloten_door=k["besloten_door"] or "",
                                     reden=k["reden"] or "") for k in uitgesloten.values()],
        open_vragen=[d["vraag"] for d in wg["deelvragen"] if d.get("status") == "voorgesteld"],
        open_bronnen=[Bronvoorstel(vindplaats=_plek(k["bron_iri"], nodes, k["label"]), rol=k["rol"], nrs=k.get("nrs") or [])
                      for k in [*voorstellen.values(), *overzicht["zonder_deelvraag"]]],
        zoekdekking=Zoekdekking(onvolledig=[str(x) for x in dekking.get("onvolledig") or []], verouderd=bool(dekking.get("verouderd")),
                                reden=str(dekking.get("reden") or "")) if dekking.get("gezocht") else None)


def _plek(iri: str, nodes: dict[str, dict], label: str = "") -> Vindplaats:
    """Een vindplaats altijd uit de bronboom; zonder jci blijft de bron-IRI de bronreferentie."""
    return Vindplaats(iri=iri, label=label or _vindplaats(iri, nodes), jci=(nodes.get(iri) or {}).get("jci") or "")


def _reden_afwijzing(e: dict) -> str:
    """De reden bij de laatste afwijzing; alleen als de markering nu ook afgewezen is."""
    if e["lifecycle"] != "rejected":
        return ""
    laatste = next((b for b in reversed(e.get("beslissingen") or []) if b.get("type") == "reject"), {})
    return laatste.get("review_reason") or laatste.get("comment") or ""


def _markering(e: dict, nodes: dict[str, dict], verklaringen: dict) -> Markering:
    r = herkomst_regels(e, verklaringen)
    return Markering(
        id=e["id"], klasse=e.get("klasse") or "", alternatieven=[a.get("klasse", "") for a in e.get("alternatieven") or []],
        subtype=e.get("jas_subtype") or "", lifecycle=e["lifecycle"], tekst=e["tekst"], toelichting=e.get("toelichting") or "",
        vindplaatsen=[_plek(iri, nodes) for iri in dict.fromkeys(a["bron_iri"] for a in e.get("ankers") or [])],
        herkomst=Herkomst(herkomst=r["herkomst"], besloten_door=r["besloten_door"], terugval=bool(r["terugval"]), twijfel=r["twijfel"],
                          gedegradeerd=r["gedegradeerd"], jurist=r["jurist"]),
        afwijkingen=[Afwijking(plek=plek, toen=toen, nu=nu) for plek, toen, nu in _anker_afwijkingen(e, nodes)],
        reden_afwijzing=_reden_afwijzing(e),
        verouderd=bool(e.get("verouderd")), deels_buiten=bool(e.get("deels_buiten")), door="analist" if r["herkomst"] == "mens" else "lex")


def _spans(eigen: list[dict], iri: str, tekst: str) -> list[Span]:
    """De ankers die op deze bepaling liggen en nog letterlijk op hun offsets staan; de rest staat als afwijking bij de markering."""
    uit = []
    for n, e in enumerate(eigen, 1):
        for a in e.get("ankers") or []:
            if a["bron_iri"] == iri and 0 <= a["start"] < a["eind"] <= len(tekst) and tekst[a["start"]:a["eind"]] == a["tekst"]:
                uit.append(Span(start=a["start"], eind=a["eind"], nr=n, klasse=e.get("klasse") or ""))
    return sorted(uit, key=lambda x: (x.start, -x.eind, x.nr))


def _graaf(data: dict) -> dict:
    return {"volledig": True, "regelingen": {}, "structuur": {}, "verwijzingen": [], "verwijzingen_volledig": True, **(data.get("graaf") or {})}


def _verwijzingen(data: dict, nodes: dict[str, dict], in_dossier: set[str]) -> dict[str, list[Verwijzing]]:
    """Per bronnode de verwijzingen eruit. Een doel staat in het dossier als het daar zelf staat of een van zijn delen er staat."""
    uit: dict[str, list[Verwijzing]] = {}
    for v in _graaf(data)["verwijzingen"]:
        naar = v["naar"]
        binnen = naar in in_dossier or any(i.startswith(naar + ":") for i in in_dossier)
        label = " – ".join(filter(None, [v.get("regeling"), v.get("label")])) or naar
        uit.setdefault(v["van"], []).append(Verwijzing(
            van=_plek(v["van"], nodes), naar=Vindplaats(iri=naar, label=label, jci=v.get("jci") or ""), anker=v.get("anker") or "",
            in_graaf=v.get("in_graaf", True), in_dossier=binnen))
    return uit


def _artikel(kop: str, nodes: dict[str, dict], data: dict) -> Artikel:
    """Een artikel met zijn plaats in de opbouw (de voorouders tot de regeling) en wat de graaf over het artikel weet."""
    structuur = _graaf(data)["structuur"]
    plaats: list[Structuurdeel] = []
    iri, gezien = (nodes.get(kop) or {}).get("parent_iri") or "", set()
    while iri in nodes and iri not in gezien and nodes[iri].get("parent_iri"):      # de wortel is de regeling zelf
        gezien.add(iri)
        n = nodes[iri]
        plaats.append(Structuurdeel(soort=n["type"], nummer=n.get("nummer") or "", titel=(structuur.get(iri) or {}).get("titel") or "",
                                    iri=iri))
        iri = n.get("parent_iri") or ""
    eigen = structuur.get(kop) or {}
    return Artikel(kop=_vindplaats(kop, nodes), bepalingen=[], plaats=plaats[::-1], inwerking=eigen.get("inwerking") or None,
                   gewijzigd_bij=eigen.get("gewijzigd_bij") or "")


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


def _wettekst(data: dict, nodes: dict[str, dict], verklaringen: dict) -> Wettekst:
    """Per regeling, in de volgorde van de bronboom, elke bronnode één keer met haar markeringen eronder."""
    inv = data["inventaris"]
    per_klasse = Counter(e.get("klasse") or "Nog geen klasse" for e in inv["elementen"])
    per_eigenaar: dict[str, list[dict]] = {}
    for e in inv["elementen"]:
        per_eigenaar.setdefault(e["eigenaar_iri"], []).append(e)
    rollen: dict[str, str] = {}                      # bronnode → rol; analyseren wint van context
    gewijzigd: set[str] = set()
    per_bwb: dict[str, None] = {}
    onbereikbaar: list[Onbereikbaar] = []
    selecties = {s["id"]: s for s in data["werkgebied"]["bronnen"]}
    for regel in inv["selecties"]:
        sel = selecties[regel["id"]]
        if regel["onbereikbaar"]:
            onbereikbaar.append(Onbereikbaar(label=regel["label"], reden=regel["onbereikbaar"]))
            continue
        boom = data["bomen"][bwb_van(sel)]
        scope = annotatie_v2_store.bereik_van(boom, sel["bron_iri"]) if sel["bereik"] == "onderliggend" else {sel["bron_iri"]}
        for iri in scope:
            if sel["rol"] == "analyseren" or iri not in rollen:
                rollen[iri] = sel["rol"]
        if regel["bron_gewijzigd"]:
            gewijzigd.add(sel["bron_iri"])
        per_bwb[bwb_van(sel)] = None

    getoond: set[str] = set()
    regelingen: list[Regeling] = []
    verwijzingen = _verwijzingen(data, nodes, set(rollen))
    alle_verwijzingen: list[Verwijzing] = []
    for bwb in per_bwb:
        boom = annotatie_v2_store.nodes_van(data["bomen"][bwb])
        artikelen: list[Artikel] = []
        kop = None
        for node in sorted((n for iri, n in boom.items() if iri in rollen), key=lambda n: n.get("volgorde", 0)):
            iri, eigen = node["bron_iri"], per_eigenaar.get(node["bron_iri"], [])
            tekst = node.get("tekst") or ""
            if not tekst.strip() and not eigen:
                continue
            nieuw = _kop_van(iri, nodes) or iri
            if nieuw != kop:
                kop = nieuw
                artikelen.append(_artikel(kop, nodes, data))
            markeringen = [_markering(e, nodes, verklaringen).model_copy(update={"nr": n}) for n, e in enumerate(eigen, 1)]
            artikelen[-1].bepalingen.append(Bepaling(
                vindplaats=_plek(iri, nodes), rol=rollen[iri], bron_gewijzigd=iri in gewijzigd, tekst=tekst if tekst.strip() else "",
                markeringen=markeringen, spans=_spans(eigen, iri, tekst), verwijzingen=verwijzingen.get(iri, [])))
            alle_verwijzingen += verwijzingen.get(iri, [])
            getoond |= {e["id"] for e in eigen}
        # Een contextbepaling zonder markering is naslag: die gaat naar de bijlage, de rest is de analyse.
        analyse, context = [], []
        for a in artikelen:
            hoofd = [b for b in a.bepalingen if b.rol != "context" or b.markeringen]
            rest = [b for b in a.bepalingen if b.rol == "context" and not b.markeringen]
            if hoofd:
                analyse.append(a.model_copy(update={"bepalingen": hoofd}))
            if rest:
                context.append(a.model_copy(update={"bepalingen": rest}))
        regelingen.append(Regeling(bwb_id=bwb, titel=_regeling_titel(bwb, data), artikelen=analyse, context=context))
    return Wettekst(
        markeringen=len(inv["elementen"]), beoordeeld=sum(e["lifecycle"] in BEOORDEELD for e in inv["elementen"]),
        per_klasse=[KlasseTelling(klasse="" if k == "Nog geen klasse" else k, aantal=per_klasse[k]) for k in sorted(per_klasse, key=jas_sorteersleutel)],
        regelingen=regelingen, onbereikbaar=onbereikbaar, verwijzingen=alle_verwijzingen,
        verwijzingen_volledig=bool(_graaf(data).get("verwijzingen_volledig", True)),
        buiten_tekst=[_markering(e, nodes, verklaringen) for e in inv["elementen"] if e["id"] not in getoond],
        afgewezen=[_markering(e, nodes, verklaringen) for e in inv["afgewezen"]])


def _passage(k: dict, elementen: dict[str, dict], nodes: dict[str, dict]) -> Passage:
    bewijs = k["bewijs"]
    ankers = bewijs.get("ankers") or []
    iri = ankers[0]["bron_iri"] if ankers else bewijs.get("eigenaar_iri", "")
    nu = elementen.get(k["element_id"]) if k["actualiteit"] != "actueel" else None
    return Passage(tekst=bewijs.get("tekst", ""), vindplaats=_plek(iri, nodes, bewijs.get("vindplaats") or ""), klasse=bewijs.get("klasse") or "",
                   rol=k["rol"], beoordeling=k["beoordeling"], annotatie_beoordeeld=bool(k["annotatie_beoordeeld"]),
                   motivatie=k.get("motivatie") or "", beoordeeld_door=k.get("beoordeeld_door") or "",
                   beoordeeld_op=k.get("beoordeeld_op"), actualiteit=k["actualiteit"], nu=nu["tekst"] if nu else None)


def _begrip(b: dict, data: dict, elementen: dict[str, dict], nodes: dict[str, dict], redenen: dict[str, str]) -> Begrip:
    i = b["inhoud"]
    o = b.get("definitie_onderbouwing") or {}
    volgorde = ("duiding", "definitie", "context")
    koppelingen = sorted(b["koppelingen"], key=lambda k: volgorde.index(k["rol"]) if k["rol"] in volgorde else 9)
    return Begrip(
        id=b["id"], naam=i["naam"], status=b["status"], generiek=b.get("kader") == "generiek", alternatieve_termen=i.get("alternatieve_termen") or [],
        definitie=i.get("definitie") or "", definitie_herkomst=i.get("definitie_herkomst") or "", definitie_door=i.get("definitie_door") or "",
        definitie_vindplaats=_plek(o["definitie_bron_iri"], nodes, o.get("definitie_vindplaats") or "") if o.get("definitie_bron_iri") else None,
        uitleg=i.get("uitleg") or "", toelichting=i.get("context") or "",
        voorbeelden=[Voorbeeld(oordeel=v["oordeel"], tekst=v["tekst"]) for v in i.get("voorbeelden") or []],
        onderbouwing_aangepast=bool(o.get("aangepast")),
        fragmenten=[Fragment(tekst=f["tekst"], vindplaats=_plek(f["bron_iri"], nodes)) for f in o.get("fragmenten") or []],
        passages=[_passage(k, elementen, nodes) for k in koppelingen],
        relaties=[Relatie(van=r["van_naam"], type=r["type"], naar=r["naar_naam"], toelichting=r.get("toelichting") or "")
                  for r in data["relaties"]["relaties"] if r["beoordeling"] == "akkoord" and b["id"] in (r["van_begrip"], r["naar_begrip"])],
        open_punten=b.get("aandachtspunten") or [],
        geaccordeerd_door=b.get("geaccordeerd_door") or "", geaccordeerd_op=b.get("geaccordeerd_op"), reden=redenen.get(b["id"]) or "",
        vervangen=bool(b.get("vervangen_door")),
        door="bron" if i.get("definitie_herkomst") == "letterlijk" else "lex" if i.get("definitie_door") == "lex" else "analist")


def _begrippen(data: dict, nodes: dict[str, dict]) -> Begrippen:
    inv = data["inventaris"]
    elementen = {e["id"]: e for e in [*inv["elementen"], *inv["afgewezen"]]}
    redenen: dict[str, str] = {}
    for a in reversed(data["audit"]):                # de audit komt nieuwste eerst: de laatste reden wint
        if a["actie"] == "begrip-geaccordeerd" and (a["detail"] or {}).get("begrip_id"):
            redenen[a["detail"]["begrip_id"]] = a["detail"].get("reden") or ""
    return Begrippen(
        begrippen=[_begrip(b, data, elementen, nodes, redenen) for b in sorted(data["begrippen"], key=lambda b: b["inhoud"]["naam"].casefold())],
        open_groepen=[OpenGroep(naam=g["voorstel"]["naam"], definitie=(g.get("kaart") or {}).get("definitie") or g["voorstel"].get("definitie") or "",
                                leden=[Fragment(tekst=p["tekst"], vindplaats=_plek(p["bron_iri"], nodes, p["vindplaats"] or "")) for p in g["leden"]])
                      for g in data["groepen"]["groepen"] if g["besluit"] in ("open", "geparkeerd") and g["leden"]],
        open_relaties=[OpenRelatie(van=r.get("van_naam", ""), type=r["type"], naar=r.get("naar_naam", "")) for r in data["relaties"]["voorstellen"]])


def _document(data: dict) -> Document:
    wg = data["werkgebied"]
    return Document(titel=wg["naam"], kenmerk=f"WG-{wg['id'][:8]}-r{wg['revisie']}", werkgebied_id=wg["id"],
                    concept=wg["status"] != "afgerond")


def _telling(teller: Counter, volgorde: tuple[str, ...]) -> list[Telling]:
    """In een vaste volgorde, en een onbekende code achteraan op alfabet: dezelfde stand geeft dezelfde tekst."""
    return [Telling(code=c, aantal=teller[c]) for c in [*volgorde, *sorted(set(teller) - set(volgorde))] if teller[c]]


def _kerncijfers(data: dict) -> Kerncijfers:
    inv, overzicht = data["inventaris"], data["overzicht"]
    voortgang = Counter("opnieuw_bekijken" if v["opnieuw_bekijken"] else v["status"] for v in overzicht["deelvragen"])
    markeringen = Counter("beoordeeld" if e["lifecycle"] in BEOORDEELD else "voorstel" for e in inv["elementen"])
    markeringen["afgewezen"] = len(inv["afgewezen"])
    return Kerncijfers(
        deelvragen=_telling(voortgang, ("niet_gestart", "in_behandeling", "voorlopig_afgerond", "beoordeeld", "opnieuw_bekijken")),
        bronnen=_telling(Counter(s["rol"] for s in data["werkgebied"]["bronnen"]), ("analyseren", "context")),
        markeringen=_telling(markeringen, ("beoordeeld", "voorstel", "afgewezen")),
        begrippen=_telling(Counter(b["status"] for b in data["begrippen"]), ("geaccordeerd", "concept", "vervangen")))


def _onderwerp(detail: dict, data: dict, nodes: dict[str, dict]) -> str:
    """Waarover een besluit ging, leesbaar gemaakt uit de sleutels in de audit: een bron, een begrip, een deelvraag."""
    begrippen = {b["id"]: b["inhoud"]["naam"] for b in data["begrippen"]}
    deelvragen = {v.get("id"): v["nr"] for v in data["overzicht"]["deelvragen"] if v.get("id")}
    delen = []
    if detail.get("bron_iri"):
        delen.append(_vindplaats(detail["bron_iri"], nodes))
    if detail.get("begrip_id"):
        delen.append(begrippen.get(detail["begrip_id"], "een begrip dat niet meer bestaat"))
    if detail.get("van") and detail.get("naar") and detail.get("type"):
        delen.append(f"{begrippen.get(detail['van'], '?')} – {begrippen.get(detail['naar'], '?')} ({detail['type']})")
    if detail.get("deelvraag") in deelvragen:
        delen.append(f"deelvraag {deelvragen[detail['deelvraag']]}")
    if detail.get("veld"):
        delen.append(f"veld {detail['veld']}")
    return " · ".join(delen)


def _besluiten(data: dict, nodes: dict[str, dict]) -> list[Besluit]:
    uit = []
    for a in sorted(data["audit"], key=lambda a: (a["tijdstip"], a["id"])):
        detail = a.get("detail") or {}
        actie = "status-gewijzigd" if a["actie"] == "gewijzigd" and "status" in (detail.get("velden") or []) else a["actie"]
        if actie in BESLUITEN:
            uit.append(Besluit(op=a["tijdstip"], door=a["actor"], actie=actie, onderwerp=_onderwerp(detail, data, nodes),
                               reden=str(detail.get("reden") or "")))
    return uit


def _verantwoording(data: dict, nodes: dict[str, dict]) -> Verantwoording:
    wg, inv = data["werkgebied"], data["inventaris"]
    return Verantwoording(
        aangemaakt_door=wg["aangemaakt_door"], aangemaakt=wg["aangemaakt"], gewijzigd=wg["gewijzigd"],
        juristen=sorted({b["actor"] for e in [*inv["elementen"], *inv["afgewezen"]] for b in e.get("beslissingen") or [] if b.get("actor")}),
        accordeurs=sorted({b["geaccordeerd_door"] for b in data["begrippen"] if b["status"] == "geaccordeerd" and b["geaccordeerd_door"]}),
        handelingen=[Handeling(actie=a, aantal=n) for a, n in Counter(a["actie"] for a in data["audit"]).most_common()],
        besluiten=_besluiten(data, nodes),
        bronnen=[Selectie(rol=s["rol"], vindplaats=_plek(s["bron_iri"], nodes, s["label"]), toegevoegd_door=s.get("toegevoegd_door") or "",
                          toegevoegd=s.get("toegevoegd")) for s in wg["bronnen"]])


def bouw_rapport(data: dict, verklaringen: dict) -> Rapport:
    """Het gestructureerde rapport: alles wat een uitvoervorm mag tonen, en niets anders."""
    nodes = _nodes(data)
    r = Rapport(stand=Stand(op=data["export"]["op"], door=data["export"]["actor"]), document=_document(data),
                voorblad=_voorblad(data, nodes), samenvatting=_kerncijfers(data),
                dossier=_dossier(data), deelvragen=_deelvragen(data, nodes), wettekst=_wettekst(data, nodes, verklaringen),
                begrippen=_begrippen(data, nodes), verantwoording=_verantwoording(data, nodes))
    return r.model_copy(update={"document": r.document.model_copy(update={"inhoud_hash": inhoud_hash(r)})})


def regels(data: dict, verklaringen: dict) -> list[Regel]:
    """De regels van het rapport, langs de JSON: elke uitvoer ziet alleen wat in het document staat."""
    return rapport_regels(Rapport.model_validate_json(bouw_rapport(data, verklaringen).model_dump_json()))


def json_export(data: dict, verklaringen: dict) -> bytes:
    """Het document zelf (ADR-009): wat PDF en Markdown tonen, machineleesbaar, met `schema_naam` en `versie`."""
    return bouw_rapport(data, verklaringen).model_dump_json(indent=2).encode()


def markdown_export(data: dict, verklaringen: dict) -> bytes:
    return markdown_opmaak.markdown(regels(data, verklaringen)).encode()


def pdf_export(data: dict, verklaringen: dict) -> bytes:
    naam = data["werkgebied"]["naam"]
    wg = data["werkgebied"]
    concept = " · concept" if wg["status"] != "afgerond" else ""
    rapport = Rapport.model_validate_json(bouw_rapport(data, verklaringen).model_dump_json())
    voet = (f"Werkgebiedrapport{concept} · revisie {wg['revisie']} · inhoud {kort(rapport.document.inhoud_hash)} · "
            f"stand van {datum(data['export']['op'])}")
    return pdf_opmaak.render(rapport_regels(rapport), titel=naam, voet=voet,
                             onderwerp="Wetsanalyse – rapport van het werkgebied", auteur=data["export"]["actor"],
                             trefwoorden=", ".join(sorted({bwb_van(s) for s in wg["bronnen"]})))
