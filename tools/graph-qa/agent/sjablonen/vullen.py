"""Wat elk sjabloon nodig heeft: de rijen die de tools in deze beurt teruggaven."""
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from typing import Any

from bronmodel.antwoord import Vindplaats
from bronmodel.vindplaats import vindplaats

from ..tools.begrip_tools import AFGELEIDE_TOOL_NAMEN

#: Deze controle in de catalogus (ADR-014 §7, concept hook): deterministisch, op een vast moment, niet door het model
#: uit te zetten.
CONTROLE = {"naam": "sjabloon_vullen", "label": "Sjabloon vullen uit de bron", "doel": ("Vult de blokken van een antwoordsjabloon uit de rijen die de graaf of de bron in deze beurt teruggaf; het model wijst aan, de code neemt de tekst over, en wat niet te vullen is gaat als fout terug."),
            "moment": "na de sjabloonaanroep van het model (sjabloon_node; PostToolUse-hook)", "tests": ('tools/graph-qa/tests/test_sjablonen.py',)}


Trace = list[tuple[str, str]]


class Onvulbaar(ValueError):
    """Het sjabloon kan niet uit de trace gevuld worden. De tekst gaat als fout terug naar het model, dat
    eerst ophaalt wat ontbreekt: een halve vulling tonen we nooit.

    `ophalen` zijn de artikelen die de code zelf ophaalt voordat het model het opnieuw probeert, als
    `{"bwb_id", "artikel"}` voor `get_artikel`: een artikel dat het antwoord noemt en dat de opgehaalde tekst
    aanwijst, maar waarvan de tekst er niet bij zit (D, "genoemd is gelezen")."""

    def __init__(self, tekst: str, *, ophalen: Iterable[dict[str, str]] = (), code: str = "") -> None:
        super().__init__(tekst)
        self.ophalen = list(ophalen)
        #: Waarom, als naam uit de code en zonder inhoud (`geen_passage`, `genoemd_onbekend`): de meting telt erop
        #: (`beurtmeting`, `geweigerd_reden`). De tekst zelf gaat alleen naar het model.
        self.code = code


def _data(tekst: str) -> dict[str, Any] | None:
    try:
        data = json.loads(tekst)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def resultaten(trace: Trace, tools: Iterable[str]) -> Iterator[dict[str, Any]]:
    """De geslaagde resultaten van deze tools, oudste eerst."""
    namen = set(tools)
    for naam, tekst in trace:
        data = _data(tekst) if naam in namen else None
        if data is not None and data.get("status") in ("ok", "partial"):
            yield data


def rijen(trace: Trace, tools: Iterable[str]) -> Iterator[dict[str, Any]]:
    for data in resultaten(trace, tools):
        yield from (r for r in data.get("resultaten") or [] if isinstance(r, dict))


def _rijen_diep(v: Any) -> Iterator[dict[str, Any]]:
    if isinstance(v, dict):
        yield v
        v = list(v.values())
    if isinstance(v, list):
        for x in v:
            yield from _rijen_diep(x)


#: De velden waarin een tool-rij de iri van zijn eigen tekst draagt.
_IRI_VELDEN = ("node", "iri", "uri", "lid", "onderdeel")


def bron_rijen(trace: Trace) -> dict[str, dict[str, Any]]:
    """Per bronnode de rij met de langste hele tekst. Een zoekrij draagt soms een voorproef; als de bepaling is
    opgehaald, staat de hele tekst er ook. Annotaties en begrippen tellen niet: die zijn duiding, geen bron."""
    uit: dict[str, dict[str, Any]] = {}
    for naam, tekst in trace:
        for rij in _rijen_diep(None if naam in AFGELEIDE_TOOL_NAMEN else _data(tekst)):
            t = rij.get("tekst")
            if not isinstance(t, str) or rij.get("tekst_volledig") is False:
                continue
            for iri in (rij.get(veld) for veld in _IRI_VELDEN):
                if isinstance(iri, str) and iri and len(t) > len(uit.get(iri, {}).get("tekst", "")):
                    uit[iri] = rij
    return uit


def ouders(trace: Trace) -> dict[str, str]:
    """Per onderdeel uit `get_lid` het lid waar het bij hoort. Een slotzin na de onderdelen ("…, indien …") heeft een
    eigen `:id:`-iri die niet onder die van het lid valt; zonder deze kaart stond hij voor de code in geen enkel lid
    (Iw 24 lid 1, eval 7 nov 2026)."""
    uit: dict[str, str] = {}
    for naam, tekst in trace:
        data = _data(tekst) if naam == "get_lid" else None
        lid = ((data or {}).get("lid") or {}).get("iri")
        for r in (data or {}).get("resultaten") or []:
            if isinstance(r, dict) and lid and isinstance(r.get("onderdeel"), str):
                uit[r["onderdeel"]] = lid
    return uit


def iri_van_jci(trace: Trace) -> dict[str, str]:
    """Per jci die een rij draagt de iri van die rij, ook zonder de toestandsstaart (`&z=…&g=…`). Het model nam soms de
    jci uit het toolresultaat als bepaling; de rijen staan op hun iri (eval 7 nov 2026)."""
    uit: dict[str, str] = {}
    for naam, tekst in trace:
        for rij in _rijen_diep(None if naam in AFGELEIDE_TOOL_NAMEN else _data(tekst)):
            jci, iri = rij.get("jci"), next((rij[v] for v in _IRI_VELDEN if isinstance(rij.get(v), str) and rij[v]), "")
            if isinstance(jci, str) and jci and iri:
                uit.setdefault(jci, iri)
                uit.setdefault(jci.split("&z=", 1)[0], iri)
    return uit


def artikel_in_trace(nummer: str, trace: Trace) -> str:
    """De iri van artikel `nummer` als de opgehaalde resultaten het aanwijzen, en in precies één regeling; anders leeg.

    Een artikel staat vaak in een resultaat zonder zijn tekst: `get_context` noemt de bepalingen die naar het gevraagde
    artikel verwijzen (Iw 28 verwijst naar 25 en 9; eval 7 nov 2026). Dan weet het model dát het erbij hoort, maar heeft
    het niets gelezen. In twee regelingen is niet te zeggen welk artikel het antwoord bedoelt: dan haalt de code niets."""
    patroon = re.compile(rf"urn:bwb:(BWB[RV]\d+):artikel:{re.escape(nummer)}(?![0-9A-Za-z.])")
    regelingen = {m.group(1) for naam, tekst in trace if naam not in AFGELEIDE_TOOL_NAMEN for m in patroon.finditer(tekst or "")}
    return f"urn:bwb:{regelingen.pop()}:artikel:{nummer}" if len(regelingen) == 1 else ""


#: Het label dat de importer een verwijzingsdoel geeft dat niet in de graaf staat (`bwb:doelLabel`, "art. 53 (BWBR0001860)").
#: Een doel dat er wél in staat, draagt zijn eigen label, en dat wint in de verwijzingsquery's.
_STOMP_LABEL = re.compile(r"art\.\s+\S+\s+\((BWB[RV]\d+)\)")
_ARTIKEL_IRI = re.compile(r"urn:bwb:BWB[RV]\d+:artikel:[^:\s\"]+")


def verwezen_buiten_graaf(trace: Trace) -> set[str]:
    """De artikelen waar een opgehaalde bepaling naar verwijst en die de graaf niet heeft: een rij met `naar`, het label
    dat de importer zo'n doel geeft en zonder `doelRegeling`. De verwijzing zelf is wat de graaf erover weet; de tekst kan
    geen tool ophalen. Iw 24 verwijst zo naar de Faillissementswet en de Wet Vpb 1969 (ADR-016 ronde 4, E03: na de
    weigering zocht het model die wetten op, drie modelrondes extra in beide vormen)."""
    uit: set[str] = set()
    for naam, tekst in trace:
        for rij in _rijen_diep(None if naam in AFGELEIDE_TOOL_NAMEN else _data(tekst)):
            naar, label = rij.get("naar"), rij.get("doelLabel")
            if (isinstance(naar, str) and isinstance(label, str) and not rij.get("doelRegeling")
                    and _STOMP_LABEL.fullmatch(label.strip()) and (m := _ARTIKEL_IRI.match(naar))):
                uit.add(m.group(0))
    return uit


def volledige_tekst(iri: str, trace: Trace) -> str:
    return bron_rijen(trace).get(iri, {}).get("tekst", "")


_TOESTAND = re.compile(r"jci[\d.]+:c:(BWB[RV]\d+)[^\s\"]*?(&z=[^&\s\"]+&g=[^&\s\"]+)")


def toestanden(trace: Trace) -> dict[str, str]:
    """Per regeling de toestand die de tools in deze beurt lazen, als jci-staart (`&z=…&g=…`). Een lid uit `get_artikel` en
    een onderdeel uit `get_lid` dragen hun jci zonder die staart (herhaling binnen één regeling); de link naar
    wetten.overheid.nl moet wél de gelezen toestand openen, niet de actuele (acceptatie 7 nov 2026)."""
    uit: dict[str, str] = {}
    for naam, tekst in trace:
        if naam in AFGELEIDE_TOOL_NAMEN:
            continue
        for m in _TOESTAND.finditer(tekst or ""):
            uit.setdefault(m.group(1), m.group(2))
    return uit


def met_toestand(jci: str, staarten: dict[str, str]) -> str:
    """De jci met de gelezen toestand van zijn regeling, als hij die nog niet draagt."""
    if not jci or "&z=" in jci:
        return jci
    m = re.match(r"jci[\d.]+:c:(BWB[RV]\d+)", jci)
    return jci + staarten.get(m.group(1), "") if m else jci


def vindplaats_van(iri: str, *, jci: str = "", regeling: str = "", label: str = "") -> Vindplaats:
    """De vindplaats zoals `bronmodel` hem leest; `label` is de terugval voor een wet-lokale node."""
    vp = vindplaats(iri)
    return Vindplaats(iri=iri, jci=jci, regeling=regeling, label=(vp.label if vp else "") or label or iri)
