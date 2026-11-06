"""Het hele werkgebied als één PDF: een overdrachtsdossier voor wie niet in Lex werkt.

`verzamel` leest de stand van nu met dezelfde functies als de schermen, `pdf_regels` zet die om in (stijl, tekst) – los
van reportlab, zodat de inhoud testbaar is – en `pdf_opmaak` maakt er het bestand van.

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
from datetime import datetime
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from . import (annotatie_v2_store, begrip_relatie_store, begrip_store, begrippen_run_store, bronselectie, db, pdf_opmaak,
               werkgebied_store)
from .annotatie_export import herkomst_regels
from .annotatie_v2_contracts import BEOORDEELD
from .jas_klassen import jas_sorteersleutel
from .pdf_opmaak import INHOUD, MARKERING, PAGINA
from .werkgebied_inventaris import Resolver, bwb_van, inventaris_met_bronbomen

_DOSSIER = (("aanleiding", "Aanleiding"), ("context", "Context"), ("doel", "Doel"), ("analysevraag", "Analysevraag"),
            ("praktijkvoorbeeld", "Praktijkvoorbeeld"), ("afbakening", "Afbakening"), ("gebeurtenis", "Gebeurtenis"))
_WERKGEBIED_STATUS = {"in_voorbereiding": "In voorbereiding", "actief": "Actief", "afgerond": "Afgerond"}
_VOORTGANG = {"niet_gestart": "Nog niet gestart", "in_behandeling": "In behandeling",
              "voorlopig_afgerond": "Voorlopig afgerond", "beoordeeld": "Beoordeeld"}
_BRONROL = {"analyseren": "analyseren", "context": "context"}
_KANDIDAATROL = {"kern": "kernbepaling", "afhankelijkheid": "afhankelijkheid", "aanverwant": "aanverwant"}
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
_ZONE = ZoneInfo("Europe/Amsterdam")
_MAANDEN = ("januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
            "november", "december")


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


def _datum(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    d = d.astimezone(_ZONE) if d.tzinfo else d
    return f"{d.day} {_MAANDEN[d.month - 1]} {d.year}"


def bestandsnaam(data: dict) -> str:
    """Alleen ASCII: de naam gaat een header in, en een aanhalingsteken erin zou die breken."""
    naam = unicodedata.normalize("NFKD", data["werkgebied"]["naam"]).encode("ascii", "ignore").decode()
    naam = re.sub(r"[^a-z0-9]+", "-", naam.lower()).strip("-")[:80].rstrip("-")
    return f"werkgebied-{naam or data['werkgebied']['id']}.pdf"


def _meervoud(n: int, een: str, meer: str) -> str:
    return f"{n} {een if n == 1 else meer}"


def _alinea(tekst: str, stijl: str = "BodyText") -> list[tuple[str, str]]:
    return [(stijl, a.strip()) for a in re.split(r"\n\s*\n", tekst) if a.strip()]


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


def _waarschuwingen(data: dict, nodes: dict[str, dict]) -> list[str]:
    """Wat een lezer moet weten voor hij dit dossier gebruikt; dezelfde punten staan ook op hun plek."""
    uit = []
    inv, toestanden = data["inventaris"], data["toestanden"]
    for s in inv["selecties"]:
        if s["onbereikbaar"]:
            uit.append(f"Niet in dit dossier: {s['label']}. {s['onbereikbaar']}")
        elif s["bron_gewijzigd"]:
            uit.append(f"De bron veranderde sinds de selectie: {s['label']}.")
    if not toestanden["volledig"]:
        uit.append("De toestand per regeling kon niet worden gelezen: de vergelijking met de peildatum ontbreekt.")
    for r in toestanden["regelingen"]:
        if r["na_peildatum"]:
            uit.append(f"{r['citeertitel']}: de tekst in dit dossier geldt pas sinds {_datum(r['geldig_vanaf'])}, na de "
                       "peildatum. Hij kan afwijken van wat op de peildatum gold.")
    elementen = [*inv["elementen"], *inv["afgewezen"]]
    if n := sum(bool(e.get("verouderd") or _anker_afwijkingen(e, nodes)) for e in elementen):
        uit.append(_meervoud(n, "markering staat op tekst die veranderde.", "markeringen staan op tekst die veranderde."))
    passages = sum(k["actualiteit"] != "actueel" for b in data["begrippen"] for k in b["koppelingen"])
    if passages:
        uit.append(_meervoud(passages, "passage bij een begrip veranderde; toen en nu staan bij het begrip.",
                             "passages bij begrippen veranderden; toen en nu staan bij het begrip."))
    opnieuw = [v["nr"] for v in data["overzicht"]["deelvragen"] if v["opnieuw_bekijken"]]
    if opnieuw:
        uit.append("Opnieuw te bekijken na een wijziging van de scope: deelvraag " + ", ".join(map(str, opnieuw)) + ".")
    dekking = data["overzicht"]["zoekdekking"]
    if dekking.get("gezocht") and (dekking.get("verouderd") or not dekking.get("volledig", True)):
        uit.append("Het zoeken naar bronnen is onvolledig of verouderd; zie deel 2.")
    return uit


def _voorblad(data: dict, nodes: dict[str, dict]) -> list[tuple[str, str]]:
    wg, toestanden, export = data["werkgebied"], data["toestanden"], data["export"]
    uit = [("Title", wg["naam"]), ("Subtitle", "Wetsanalyse: dossier van het werkgebied")]
    if wg.get("analysevraag"):
        uit.append(("BodyText", "Analysevraag: " + wg["analysevraag"]))
    uit.append(("BodyText", f"Status: {_WERKGEBIED_STATUS.get(wg['status'], wg['status'])} · revisie {wg['revisie']}"))
    if wg.get("thema_label"):
        uit.append(("BodyText", "Thema: " + wg["thema_label"]))
    peildatum = _datum(wg.get("peildatum"))
    uit.append(("BodyText", "Peildatum: " + (peildatum or "niet vastgelegd")
                + (" (de aanmaakdag)" if wg.get("peildatum_standaard") else "")))
    uit.append(("BodyText", f"Stand van {_datum(export['op'])}, geëxporteerd door {export['actor']}."))
    if toestanden["regelingen"]:
        uit.append(("Heading4", "Bronstand per regeling"))
        for r in toestanden["regelingen"]:
            # De graaf zet een regeling zonder einde op 9999-12-31.
            tot = f" tot {_datum(r['geldig_tot'])}" if r["geldig_tot"] and r["geldig_tot"] < "9999" else ""
            vanaf = f"geldt vanaf {_datum(r['geldig_vanaf'])}{tot}" if r["geldig_vanaf"] else "geldigheid onbekend"
            uit.append(("Meta", f"{r['citeertitel']} ({r['bwb_id']}): {vanaf}"))
    waarschuwingen = _waarschuwingen(data, nodes)
    if waarschuwingen:
        uit.append(("Heading4", "Let op"))
        uit += [("Waarschuwing", w) for w in waarschuwingen]
    uit += [("Heading4", "Zo lees je dit dossier"),
            ("Meta", "Dit is een analyse-uitkomst, geen wettelijke definitie en geen juridisch oordeel. De wettekst is "
                     "letterlijk overgenomen uit de kennisgraaf, die gevuld is uit de officiële publicatie. Bij elke "
                     "bepaling staat de vindplaats en de bronreferentie (jci)."),
            ("Meta", "Lex stelt voor, de jurist beslist. Beoordeeld of geaccordeerd betekent dat een jurist het bevestigde. "
                     "Voorstel en concept zijn nog niet bevestigd; afgewezen en uitgesloten zijn bewust niet meegenomen.")]
    return uit


def _dossier(data: dict) -> list[tuple[str, str]]:
    wg = data["werkgebied"]
    uit: list[tuple[str, str]] = [(PAGINA, ""), ("Heading1", "1. Dossier")]
    for veld, label in _DOSSIER:
        uit.append(("Heading4", label))
        uit += _alinea(wg.get(veld) or "") or [("Meta", "Niet ingevuld.")]
    if wg.get("regelingen"):
        uit.append(("Heading4", "Zoekbereik"))
        uit += [("BodyText", f"{r.get('label') or r['bwb_id']} ({r['bwb_id']})") for r in wg["regelingen"]]
    return uit


def _deelvragen(data: dict, nodes: dict[str, dict]) -> list[tuple[str, str]]:
    wg, overzicht = data["werkgebied"], data["overzicht"]
    selecties = {s["id"]: s for s in wg["bronnen"]}
    uit: list[tuple[str, str]] = [(PAGINA, ""), ("Heading1", "2. Deelvragen en bronnen")]
    uitgesloten: dict[str, dict] = {}
    voorstellen: dict[str, dict] = {}
    for v in overzicht["deelvragen"]:
        titel = "Analysevraag" if overzicht["modus"] == "analysevraag" else f"Deelvraag {v['nr']}"
        uit.append(("Heading2", titel))
        uit.append(("BodyText", v["vraag"]))
        stand = "Opnieuw bekijken" if v["opnieuw_bekijken"] else _VOORTGANG.get(v["status"], v["status"])
        uit.append(("Meta", f"Stand: {stand} · {_meervoud(len(v['bronnen']), 'bron', 'bronnen')}"))
        if v["opnieuw_bekijken"]:
            uit.append(("Waarschuwing", "De scope veranderde na het afronden; deze deelvraag moet opnieuw bekeken worden."))
        uit += [("Waarschuwing", "Open punt: " + p["tekst"]) for p in v["open_punten"]]
        for b in v["bronnen"]:
            reden = (selecties.get(b["selectie_id"]) or {}).get("reden")
            uit.append(("BodyText", f"{b['label']} · {_BRONROL.get(b['rol'], b['rol'])}" + (f": {reden}" if reden else "")))
        if niet := v["telling"].get("niet_gekozen"):
            uit.append(("Meta", _meervoud(niet, "voorstel van Lex is niet gekozen.", "voorstellen van Lex zijn niet gekozen.")))
        for k in v["kandidaten"]:
            doel = uitgesloten if k["stand"] == "uitgesloten" else voorstellen if k["stand"] == "voorgesteld" else None
            if doel is not None:
                doel.setdefault(k["id"], {**k, "nrs": []})["nrs"].append(v["nr"])

    uit.append(("Heading2", "Uitgesloten bronnen"))
    if not uitgesloten:
        uit.append(("Meta", "Er zijn geen bronnen uitgesloten."))
    for k in uitgesloten.values():
        waar = "alle deelvragen" if k["overal"] else "deelvraag " + ", ".join(map(str, k["nrs"]))
        uit.append(("BodyText", f"{k['label']} · uitgesloten voor {waar}"
                    + (f" door {k['besloten_door']}" if k["besloten_door"] else "") + f". Reden: {k['reden'] or 'niet vastgelegd'}"))

    open_vragen = [d for d in wg["deelvragen"] if d.get("status") == "voorgesteld"]
    open_bronnen = [*voorstellen.values(), *overzicht["zonder_deelvraag"]]
    uit.append(("Heading2", "Open voorstellen van Lex"))
    if not open_vragen and not open_bronnen:
        uit.append(("Meta", "Er staan geen voorstellen open."))
    else:
        uit.append(("Meta", "Hierover is nog geen besluit genomen; ze horen niet tot de analyse."))
    uit += [("Voorstel", "Voorstel voor een deelvraag: " + d["vraag"]) for d in open_vragen]
    for k in open_bronnen:
        rol = _KANDIDAATROL.get(k["rol"], k["rol"])
        waar = f" · deelvraag {', '.join(map(str, k['nrs']))}" if k.get("nrs") else " · bij geen deelvraag"
        uit.append(("Voorstel", f"Voorstel voor een bron: {k['label']} · {rol}{waar}"))

    dekking = overzicht["zoekdekking"]
    if dekking.get("gezocht"):
        uit.append(("Heading2", "Zoekdekking"))
        onvolledig = dekking.get("onvolledig") or []
        uit.append(("BodyText", "Lex heeft gezocht"
                    + (", maar niet alles kon worden doorzocht: " + ", ".join(map(str, onvolledig)) + "." if onvolledig else ".")))
        if dekking.get("verouderd"):
            uit.append(("Waarschuwing", "Het werkgebied veranderde na het zoeken."))
        if dekking.get("reden"):
            uit.append(("Meta", str(dekking["reden"])))
    return uit


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
    uit = [(MARKERING + klasse, f"{kop} · {_LIFECYCLE.get(e['lifecycle'], e['lifecycle'])}"),
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
    return uit


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
        uit.append(("Heading2", _regeling_titel(bwb, data)))
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
        uit.append(("Heading2", "Markeringen buiten de getoonde tekst"))
        for e in rest:
            uit += _markering(e, nodes, verklaringen)
    uit.append(("Heading2", "Afgewezen markeringen"))
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
    i = b["inhoud"]
    uit: list[tuple[str, str]] = [("Heading3", i["naam"])]
    meta = [_BEGRIPSTATUS.get(b["status"], b["status"])]
    if b.get("kader") == "generiek":
        meta.append("generiek begrip, gebruikt in dit werkgebied")
    uit.append(("Meta", " · ".join(meta)))
    if i.get("alternatieve_termen"):
        uit.append(("BodyText", "Ook genoemd: " + ", ".join(i["alternatieve_termen"])))
    if (i.get("definitie") or "").strip():
        aard = [_DEFINITIE.get(i.get("definitie_herkomst") or "", "definitie"), _DEFINITIE_DOOR.get(i.get("definitie_door") or "", "")]
        uit.append(("Heading4", "Definitie"))
        uit.append(("Citaat" if i.get("definitie_herkomst") == "letterlijk" else "BodyText", i["definitie"]))
        uit.append(("Meta", ", ".join(filter(None, aard)) + "."))
    else:
        uit.append(("Voorstel", "Nog geen definitie."))
    if (i.get("uitleg") or "").strip():
        uit.append(("Heading4", "Uitleg"))
        uit += _alinea(i["uitleg"])
    if (i.get("context") or "").strip():
        uit.append(("Heading4", "Toelichting"))
        uit += _alinea(i["context"])
    if i.get("voorbeelden"):
        uit.append(("Heading4", "Voorbeelden"))
        uit += [("BodyText", f"{_OORDEEL.get(v['oordeel'], v['oordeel']).capitalize()}: {v['tekst']}") for v in i["voorbeelden"]]
    o = b.get("definitie_onderbouwing") or {}
    if o.get("fragmenten"):
        uit.append(("Heading4", "Waarop de definitie rust"))
        if o.get("aangepast"):
            uit.append(("Meta", "De analist paste de definitie aan; deze fragmenten waren het vertrekpunt."))
        for f in o["fragmenten"]:
            uit += [("Citaat", f"“{f['tekst']}”"), ("Meta", f"{_vindplaats(f['bron_iri'], nodes)} · {_verwijzing(f['bron_iri'], nodes)}")]
    if b["koppelingen"]:
        uit.append(("Heading4", _meervoud(len(b["koppelingen"]), "passage", "passages")))
        for k in sorted(b["koppelingen"], key=lambda k: (("duiding", "definitie", "context").index(k["rol"])
                                                         if k["rol"] in ("duiding", "definitie", "context") else 9)):
            uit += _passage(k, elementen, nodes)
    relaties = [r for r in data["relaties"]["relaties"] if r["beoordeling"] == "akkoord" and b["id"] in (r["van_begrip"], r["naar_begrip"])]
    if relaties:
        uit.append(("Heading4", "Relaties"))
        for r in relaties:
            uit.append(("BodyText", f"{r['van_naam']} {_RELATIE.get(r['type'], r['type'])} {r['naar_naam']}"
                        + (f": {r['toelichting']}" if r.get("toelichting") else "")))
    if b.get("aandachtspunten"):
        uit.append(("Heading4", "Nog open"))
        uit += [("Waarschuwing", p) for p in b["aandachtspunten"]]
    if b["status"] == "geaccordeerd":
        reden = redenen.get(b["id"])
        uit.append(("Meta", f"Geaccordeerd door {b['geaccordeerd_door']} op {_datum(b['geaccordeerd_op'])}"
                    + (f". Reden: {reden}" if reden else ".")))
    if b.get("vervangen_door"):
        uit.append(("Meta", "Vervangen door een opvolger; dit begrip is alleen nog te lezen."))
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
    for status, kop in (("geaccordeerd", "Geaccordeerde begrippen"), ("concept", "Conceptbegrippen"), ("vervangen", "Vervangen begrippen")):
        groep = sorted((b for b in data["begrippen"] if b["status"] == status), key=lambda b: b["inhoud"]["naam"].casefold())
        if not groep:
            continue
        uit.append(("Heading2", f"{kop} ({len(groep)})"))
        if status == "concept":
            uit.append(("Meta", "Nog niet geaccordeerd: de inhoud kan veranderen."))
        for b in groep:
            uit += _begrip(b, data, elementen, nodes, redenen)
    open_groepen = [g for g in data["groepen"]["groepen"] if g["besluit"] in ("open", "geparkeerd") and g["leden"]]
    voorstellen = data["relaties"]["voorstellen"]
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
    return [*_voorblad(data, nodes), (PAGINA, ""), ("Heading4", "Inhoud"), (INHOUD, ""), *_dossier(data),
            *_deelvragen(data, nodes), *_wettekst(data, nodes, verklaringen), *_begrippen(data, nodes),
            *_verantwoording(data, nodes)]


def pdf_export(data: dict, verklaringen: dict) -> bytes:
    naam = data["werkgebied"]["naam"]
    return pdf_opmaak.render(pdf_regels(data, verklaringen), titel=naam,
                             voet=f"{naam} · stand van {_datum(data['export']['op'])}")
