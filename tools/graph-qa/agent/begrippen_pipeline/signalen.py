"""Signalen uit termen, definities en verwijzingen (ADR-004).

Elk signaal is een hypothese over een paar formuleringen met één stuk bewijs: een code, een
richting (steun / tegen / onbeslist) en een ordinale sterkte. Wat er uiteindelijk met een paar
gebeurt, beslist de beslistabel; hier wordt alleen waargenomen.

| code | hypothese | richting, sterkte | wanneer |
|---|---|---|---|
| `ZELFDE_TERM` | zelfde betekenis | steun, zwak | dezelfde genormaliseerde term, geen van beide beperkt of een zin |
| `ZELFDE_BEPALING` | zelfde betekenis | steun, sterk | idem, en in dezelfde bronnode: één betekenis per bepaling (een aanname – de groep wordt geel) |
| `WETTELIJKE_TERM` | zelfde betekenis | steun, sterk | een term die de wet vastlegt, gebruikt binnen het bereik van die definitie |
| `UITBREIDING_MEDE` | zelfde betekenis | steun, sterk | "verstaat mede onder X" naast de definitie van X |
| `ANDERE_DEFINITIE` | zelfde betekenis | tegen, sterk | twee definities van dezelfde term met elk een eigen bron |
| `BUITEN_BEREIK` | zelfde betekenis | tegen, middel | de term wordt gebruikt buiten het bereik van zijn definitie |
| `BEREIK_ONBEKEND` | zelfde betekenis | onbeslist, zwak | de definitie heeft geen herkenbaar bereik |
| `AFWIJKENDE_KWALIFICATIE` | zelfde betekenis | tegen, sterk | "in afwijking van … geldt … als X": hier betekent X iets anders |
| `OPSOMMING_IN_DEFINITIE` | hiërarchie | steun, sterk | "X: A, B en C" – A, B en C zijn soorten X |
| `BEPERKTE_TERM` | hiërarchie | steun, middel | "een X die …": een soort van de wettelijke term X |
| `MEDE_VERSTAAN` | inclusie | steun, sterk | "onder X wordt mede verstaan Y" |
| `BEDOELD_IN` | zelfde betekenis | steun, sterk | "Y, bedoeld in onderdeel c" wijst de formulering met dezelfde kern daar aan |
| `AANWIJZEND` | zelfde betekenis | steun, sterk | "die X" wijst terug naar X (direct, of via "als bedoeld in") |
| `NIET_AANGEMERKT` | uitsluiting (+ tegen zelfde) | steun, sterk | aanhef "… als X niet wordt aangemerkt:" boven een opsomming |
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .definities import (
    VERSIE as DEF_VERSIE, WettelijkeTerm, bronnen_onder, genus_van_mede, regeling_van,
    verwijzing_na, wettelijke_termen,
)
from .model import Bewijs, Hypothese, Manifest, Polariteit, Sterkte, Taalanalyse

VERSIE = "3"

_AFWIJKING = re.compile(r"\bin afwijking\b.*?\b(?:lid|leden|artikel|artikelen)\b", re.IGNORECASE | re.DOTALL)
_GELDT_ALS = re.compile(r"\bgeldt\b.*?\bals\s+(?P<term>[\w-]+)", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class Signaal:
    hypothese: Hypothese
    van: str
    naar: str
    bewijs: Bewijs


def _b(code: str, pol: Polariteit, sterkte: Sterkte, regel: str, fragment: str = "",
       bron_iri: str = "", detail: str = "") -> Bewijs:
    return Bewijs(code=code, polariteit=pol, sterkte=sterkte, regel=regel,
                  versie=f"{VERSIE}/{DEF_VERSIE}", fragment=fragment, bron_iri=bron_iri, detail=detail)


def _zelfde(van: str, naar: str, bewijs: Bewijs) -> Signaal:
    a, b = sorted((van, naar))
    return Signaal(Hypothese.ZELFDE_BETEKENIS, a, b, bewijs)


def zelfde_term(manifest: Manifest, taal: dict[str, Taalanalyse]) -> list[Signaal]:
    """Dezelfde term is een aanleiding om te vergelijken (zwak). Binnen één bronnode is het meer: in
    één lid of onderdeel draagt hetzelfde woord dezelfde betekenis, tenzij iets dat doorbreekt
    ("one sense per discourse", ADR-004). Dat is sterke steun, maar geen wet: de groep wordt geel
    (`groeperen.AANNAMES`), en tegenbewijs wint zoals altijd."""
    per: dict[str, list[str]] = {}
    for f in manifest.formuleringen:
        t = taal[f.element_id]
        if not t.beperkt and not t.zin:
            per.setdefault(t.term, []).append(f.element_id)
    uit = []
    for term, ids in sorted(per.items()):
        ids = sorted(ids)
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                uit.append(_zelfde(a, b, _b("ZELFDE_TERM", Polariteit.STEUN, Sterkte.ZWAK,
                                            "begrip.term.gelijk", term)))
                bron = manifest.formulering(a).bron_iri
                if bron == manifest.formulering(b).bron_iri:
                    uit.append(_zelfde(a, b, _b("ZELFDE_BEPALING", Polariteit.STEUN, Sterkte.STERK,
                                                "begrip.term.zelfde_bepaling", term, bron)))
    return uit


def _gebruik(manifest: Manifest, taal: dict[str, Taalanalyse], term: str) -> list[str]:
    return sorted(f.element_id for f in manifest.formuleringen if taal[f.element_id].term == term)


def uit_definities(manifest: Manifest, taal: dict[str, Taalanalyse],
                   wts: list[WettelijkeTerm] | None = None) -> list[Signaal]:
    wts = wettelijke_termen(manifest, taal) if wts is None else wts
    uit: list[Signaal] = []
    gewone = [w for w in wts if w.soort == "definitie"]

    for w in wts:
        if w.soort == "niet":
            continue
        ankers = [w.anker] if w.anker else []
        for eid in _gebruik(manifest, taal, w.term):
            if eid == w.anker or taal[eid].beperkt:     # een beperkte formulering is een soort
                continue
            f = manifest.formulering(eid)
            binnen = w.bereik.omvat(f.bron_iri)
            fragment = f"{w.term} ({w.bereik.formule or 'bereik onbekend'})"
            for anker in ankers:
                if binnen is None:
                    uit.append(_zelfde(anker, eid, _b("BEREIK_ONBEKEND", Polariteit.ONBESLIST,
                                                      Sterkte.ZWAK, "begrip.definitie.bereik",
                                                      fragment, w.bron_iri)))
                elif binnen:
                    uit.append(_zelfde(anker, eid, _b("WETTELIJKE_TERM", Polariteit.STEUN,
                                                      Sterkte.STERK, "begrip.definitie.gebruik",
                                                      fragment, w.bron_iri)))
                else:
                    uit.append(_zelfde(anker, eid, _b("BUITEN_BEREIK", Polariteit.TEGEN,
                                                      Sterkte.MIDDEL, "begrip.definitie.bereik",
                                                      fragment, w.bron_iri)))
        # Een beperkte formulering met de kern van de term is een soort van die term.
        if w.anker:
            for f in manifest.formuleringen:
                t = taal[f.element_id]
                if t.beperkt and t.kern == w.term and f.element_id != w.anker \
                        and w.bereik.omvat(f.bron_iri):
                    uit.append(Signaal(Hypothese.HIERARCHIE, w.anker, f.element_id,
                                       _b("BEPERKTE_TERM", Polariteit.STEUN, Sterkte.MIDDEL,
                                          "begrip.definitie.beperking", f.tekst, f.bron_iri)))
        if w.soort == "opsomming" and w.definitie_anker:
            uit.append(Signaal(Hypothese.HIERARCHIE, w.definitie_anker, w.anker,
                               _b("OPSOMMING_IN_DEFINITIE", Polariteit.STEUN, Sterkte.STERK,
                                  "begrip.definitie.opsomming", w.term, w.bron_iri)))
        if w.soort == "mede" and w.anker:
            genus = genus_van_mede(manifest, w)
            if genus:
                uit.append(Signaal(Hypothese.INCLUSIE, w.anker, genus,
                                   _b("MEDE_VERSTAAN", Polariteit.STEUN, Sterkte.STERK,
                                      "begrip.definitie.mede", manifest.formulering(genus).tekst,
                                      w.bron_iri)))
            for g in gewone:
                if g.term == w.term and g.anker and regeling_van(g.bron_iri) == regeling_van(w.bron_iri):
                    uit.append(_zelfde(g.anker, w.anker, _b(
                        "UITBREIDING_MEDE", Polariteit.STEUN, Sterkte.STERK,
                        "begrip.definitie.mede", w.term, w.bron_iri)))

    for i, a in enumerate(gewone):
        for b in gewone[i + 1:]:
            if a.term == b.term and a.bron_iri != b.bron_iri and a.anker and b.anker:
                uit.append(_zelfde(a.anker, b.anker, _b(
                    "ANDERE_DEFINITIE", Polariteit.TEGEN, Sterkte.STERK, "begrip.definitie.homoniem",
                    a.term, b.bron_iri)))
    return uit


def afwijkende_kwalificatie(manifest: Manifest, taal: dict[str, Taalanalyse],
                            wts: list[WettelijkeTerm]) -> list[Signaal]:
    """"Voor de toepassing van deze wet geldt, in afwijking van het eerste lid, als X: …"."""
    uit = []
    for bron in manifest.bronnen:
        if not _AFWIJKING.search(bron.tekst) or not (m := _GELDT_ALS.search(bron.tekst)):
            continue
        for f in manifest.formuleringen:
            if f.bron_iri != bron.bron_iri:
                continue
            term = taal[f.element_id].term
            if term != m.group("term").lower():
                continue
            for w in wts:
                if w.term == term and w.anker and w.anker != f.element_id and w.soort != "opsomming":
                    uit.append(_zelfde(w.anker, f.element_id, _b(
                        "AFWIJKENDE_KWALIFICATIE", Polariteit.TEGEN, Sterkte.STERK,
                        "begrip.definitie.afwijking", bron.tekst[:120], bron.bron_iri)))
    return uit


_NIET_AANGEMERKT = re.compile(r"\bals\s+(?P<term>[\w-]+)\s+(?:niet\s+wordt|wordt\s+niet)\s+aangemerkt\s*:\s*$",
                              re.IGNORECASE)


def uitsluiting_in_aanhef(manifest: Manifest, taal: dict[str, Taalanalyse],
                          wts: list[WettelijkeTerm]) -> list[Signaal]:
    """"… met dien verstande dat als medebewoner niet wordt aangemerkt: 1° de partner …"."""
    uit = []
    for bron in manifest.bronnen:
        if not (m := _NIET_AANGEMERKT.search(bron.aanhef)):
            continue
        term = m.group("term").lower()
        boven = next((w.anker for w in sorted(wts, key=lambda w: w.soort != "definitie")
                      if w.term == term and w.anker and w.bereik.omvat(bron.bron_iri)), "")
        items = sorted((f for f in manifest.formuleringen if f.bron_iri == bron.bron_iri and f.start <= 4),
                       key=lambda f: (f.start, -f.eind))
        if not boven or not items:
            continue
        item = items[0].element_id
        uit.append(Signaal(Hypothese.UITSLUITING, boven, item, _b(
            "NIET_AANGEMERKT", Polariteit.STEUN, Sterkte.STERK, "begrip.uitsluiting.aanhef",
            m.group(0), bron.bron_iri)))
        uit.append(_zelfde(boven, item, _b(
            "NIET_AANGEMERKT", Polariteit.TEGEN, Sterkte.STERK, "begrip.uitsluiting.aanhef",
            m.group(0), bron.bron_iri)))
    return uit


def _aangewezen(manifest: Manifest, taal: dict[str, Taalanalyse], doel: str, kern: str,
                term: str) -> list[str]:
    """Formuleringen in de doelbron(nen) met dezelfde kern of term."""
    uit = []
    for bron in bronnen_onder(manifest, doel):
        for f in manifest.formuleringen:
            t = taal[f.element_id]
            if f.bron_iri == bron.bron_iri and (t.term == term or t.kern == kern):
                uit.append(f.element_id)
    return sorted(uit)


def uit_verwijzingen(manifest: Manifest, taal: dict[str, Taalanalyse]) -> list[Signaal]:
    uit: list[Signaal] = []
    for f in manifest.formuleringen:
        t = taal[f.element_id]
        bron = manifest.bron(f.bron_iri)
        # "Y, bedoeld in onderdeel c": de verwijzing staat in of direct achter de formulering.
        for begin in sorted({m.start() for m in re.finditer(r",?\s*(?:als\s+)?bedoeld\s+in\b",
                                                             bron.tekst[f.start:f.eind + 40])}):
            positie = f.start + begin
            if positie > f.eind + 3:
                continue
            doel = verwijzing_na(manifest, f.bron_iri, bron.tekst[positie:])
            for g in _aangewezen(manifest, taal, doel, t.kern, t.term) if doel else []:
                if g != f.element_id:
                    uit.append(_zelfde(f.element_id, g, _b(
                        "BEDOELD_IN", Polariteit.STEUN, Sterkte.STERK, "begrip.verwijzing.bedoeld_in",
                        bron.tekst[positie:positie + 60].strip(" ,"), f.bron_iri, doel)))
            break
        # "die X" wijst terug; is het antecedent zelf een formulering, of verwijst het verder?
        if t.aanwijzend and t.antecedent_start is not None:
            for g in manifest.formuleringen:
                if g.bron_iri == f.bron_iri and g.element_id != f.element_id and \
                        g.start <= t.antecedent_start and g.eind >= t.antecedent_eind:
                    uit.append(_zelfde(f.element_id, g.element_id, _b(
                        "AANWIJZEND", Polariteit.STEUN, Sterkte.STERK, "begrip.verwijzing.aanwijzend",
                        f.tekst, f.bron_iri)))
            doel = verwijzing_na(manifest, f.bron_iri, bron.tekst[t.antecedent_eind:])
            for g in _aangewezen(manifest, taal, doel, t.kern, t.term) if doel else []:
                if g != f.element_id:
                    uit.append(_zelfde(f.element_id, g, _b(
                        "AANWIJZEND", Polariteit.STEUN, Sterkte.STERK, "begrip.verwijzing.aanwijzend",
                        bron.tekst[t.antecedent_start:t.antecedent_eind + 60].strip(), f.bron_iri,
                        doel)))
    return uit


def alle(manifest: Manifest, taal: dict[str, Taalanalyse]) -> list[Signaal]:
    """Alle signalen van deze stap, in vaste volgorde."""
    wts = wettelijke_termen(manifest, taal)
    return [*zelfde_term(manifest, taal), *uit_definities(manifest, taal, wts),
            *afwijkende_kwalificatie(manifest, taal, wts), *uitsluiting_in_aanhef(manifest, taal, wts),
            *uit_verwijzingen(manifest, taal)]
