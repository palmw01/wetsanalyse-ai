"""De resolver (ADR-001 PR 13, opdracht §18): vaste beslisregels op het oordeel van de reviewer.

De reviewer adviseert, deze tabel voert uit. Drie principes, rechtstreeks uit de opdracht:

- *conflict blijft bestaan → menselijke review*: wie het niet eens wordt, gaat naar de jurist;
- *toegestane transitie → wijzig voorstel*, met de oude lezing als alternatief;
- *nooit tegen een JAS-regel in*: een CHANGE die een voorrangsregel schendt (bv. Tijdsaanduiding →
  Parameter) wordt niet uitgevoerd maar voorgelegd.

Er wordt nooit een rood oordeel automatisch uitgevoerd en er verdwijnt niets: een samengevoegde
kandidaat wordt REJECTED met de regel als reden. Elke transitie komt in de meting (`resolutie`).

Aandacht op het voorstel (de werkplek toont die): leeg = niet betwist; `groen` = na review
bevestigd of opgelost; `geel` = de jurist moet kiezen, met de alternatieven erbij.
"""
from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, ConfigDict

from ..jas_klassen import REGELS, RegelType
from .besluit import Beslissing
from .kandidaten import Candidate, CandidateStatus
from .onzekerheid import Twijfel
from .review import Oordeel

# (reden, actie) → (regel-id, uitkomst). Uitkomst: ACCEPT (voorstel blijft/komt, groen),
# CHANGE (klasse wordt het voorstel van de reviewer, oude klasse alternatief, groen),
# HUMAN (geel, alternatieven erbij), MERGE (ZELFDE_SPAN: één klasse blijft, de ander wordt alternatief).
TABEL: dict[tuple[str, str], tuple[str, str]] = {
    ("DETECTOR_CONFLICT", "KEEP"): ("R-CONFLICT-KEEP", "HUMAN"),     # conflict met de detectie blijft
    ("DETECTOR_CONFLICT", "CHANGE"): ("R-CONFLICT-CHANGE", "CHANGE"),  # reviewer volgt het sterke bewijs
    ("DETECTOR_CONFLICT", "HUMAN_REVIEW"): ("R-CONFLICT-HUMAN", "HUMAN"),
    ("CLASSIFIER_ABSTAIN", "KEEP"): ("R-ABSTAIN-KEEP", "HUMAN"),      # er is niets om te behouden
    ("CLASSIFIER_ABSTAIN", "CHANGE"): ("R-ABSTAIN-CHANGE", "CHANGE"),
    ("CLASSIFIER_ABSTAIN", "HUMAN_REVIEW"): ("R-ABSTAIN-HUMAN", "HUMAN"),
    ("ZELFDE_SPAN", "KEEP"): ("R-SPAN-KEEP", "ACCEPT"),               # verschillende functies: overlap mag
    ("ZELFDE_SPAN", "CHANGE"): ("R-SPAN-CHANGE", "MERGE"),
    ("ZELFDE_SPAN", "HUMAN_REVIEW"): ("R-SPAN-HUMAN", "HUMAN"),
    ("DEGRADED_PARSE", "-"): ("R-DEGRADED", "HUMAN"),                # geen reviewer: minder signalen
}
ONGELDIG = ("R-ONGELDIG", "HUMAN")
TEGEN_REGEL = "R-PRIORITEIT"


class Transitie(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    reden: str
    actie: str
    regel: str
    van: str
    naar: str


def _schendt_prioriteit(van: str, naar: str) -> str:
    for r in REGELS:
        if r.type is RegelType.PRIORITEIT and van in r.applies_to and naar in r.applies_to:
            rang = dict(r.priority)
            if rang.get(van, 0) > rang.get(naar, 0):
                return r.id
    return ""


def _alt(v: dict[str, Any], klassen, motivatie: str) -> None:
    bestaand = {a["klasse"] for a in v.get("alternatieven", [])}
    for k in klassen:
        if k and k != v["klasse"] and k not in bestaand:
            v.setdefault("alternatieven", []).append({"klasse": k, "motivatie": motivatie})
            bestaand.add(k)


def los_op(voorstellen: list[dict[str, Any]], beslissingen: list[Beslissing], twijfels: list[Twijfel],
           oordelen: list[Oordeel], kandidaten_per_label: dict[str, Candidate],
           maak_voorstel: Callable[[Candidate, Beslissing], dict[str, Any]],
           ) -> tuple[list[dict[str, Any]], list[Beslissing], list[Transitie]]:
    per_oordeel = {o.label: o for o in oordelen}
    per_label_b = {b.label: b for b in beslissingen}
    voorstel_van: dict[str, list[dict[str, Any]]] = {}  # label → voorstellen (ZELFDE_SPAN: meerdere)
    uit = [dict(v) for v in voorstellen]
    for v in uit:
        voorstel_van.setdefault(v["_label"], []).append(v)
    # Bij ZELFDE_SPAN hangt de twijfel aan één label, maar gaat hij over alle voorstellen op die
    # grens – ook die van een andere kandidaat.
    per_grens: dict[tuple, list[dict[str, Any]]] = {}
    for v in uit:
        per_grens.setdefault(tuple((a["bron_iri"], a["start"], a["eind"]) for a in v["ankers"]), []).append(v)
    for t in twijfels:
        if t.reden == "ZELFDE_SPAN" and voorstel_van.get(t.label):
            grens = tuple((a["bron_iri"], a["start"], a["eind"]) for a in voorstel_van[t.label][0]["ankers"])
            voorstel_van[t.label] = per_grens[grens]
    transities: list[Transitie] = []

    for t in twijfels:
        o = per_oordeel.get(t.label)
        actie = "-" if t.reden == "DEGRADED_PARSE" else (o.actie if o else "HUMAN_REVIEW")
        regel, uitkomst = TABEL.get((t.reden, actie), ONGELDIG) if (o is None or o.geldig or actie == "-") else ONGELDIG
        b = per_label_b[t.label]
        k = kandidaten_per_label[t.label]
        naar = o.klasse if (o and o.actie == "CHANGE") else ""
        if uitkomst in {"CHANGE", "MERGE"} and t.huidig and (schending := _schendt_prioriteit(t.huidig, naar)):
            regel, uitkomst = TEGEN_REGEL + ":" + schending, "HUMAN"
        vs = voorstel_van.get(t.label, [])

        if uitkomst == "ACCEPT":
            for v in vs:
                v.update(aandacht="groen", critic="Gerichte review: beide functies blijven.")
        elif uitkomst == "CHANGE":
            if vs:
                v = vs[0]
                oud = v["klasse"]
                v.update(klasse=naar, aandacht="groen", critic=f"Gerichte review: {oud} → {naar}.")
                _alt(v, [oud], "eerdere keuze van de classifier")
            else:                                        # abstain: de reviewer kiest de eerste klasse
                nb = b.model_copy(update={"status": CandidateStatus.ACCEPTED, "klasse": naar, "door": "model",
                                          "reden": regel})
                nv = {**maak_voorstel(k, nb), "_label": t.label, "aandacht": "groen",
                      "critic": "Gekozen in de gerichte review; de classifier gaf geen beslissing."}
                uit.append(nv)
                per_label_b[t.label] = nb
            per_label_b[t.label] = per_label_b[t.label].model_copy(update={"klasse": naar, "reden": regel})
        elif uitkomst == "MERGE":
            houden = next((v for v in vs if v["klasse"] == naar), None)
            if houden is not None:
                for v in vs:
                    if v is not houden:
                        uit.remove(v)
                        _alt(houden, [v["klasse"]], "zelfde fragment, andere lezing")
                        weg = per_label_b[v["_label"]]
                        per_label_b[v["_label"]] = weg.model_copy(
                            update={"status": CandidateStatus.REJECTED, "reden": regel})
                houden.update(aandacht="groen", critic=f"Gerichte review: één functie ({naar}).")
        else:                                            # HUMAN
            if vs:
                for v in vs:
                    v.update(aandacht="geel", critic=_uitleg(t))
                    _alt(v, t.alternatieven, "ook mogelijk; kies in de review")
            else:                                        # geen klasse gekozen: leg het voor, met alle opties
                eerste = k.possible_classes[0]
                nb = b.model_copy(update={"status": CandidateStatus.HUMAN_REVIEW, "klasse": eerste, "reden": regel})
                nv = {**maak_voorstel(k, nb), "_label": t.label, "aandacht": "geel", "critic": _uitleg(t)}
                _alt(nv, k.possible_classes, "ook mogelijk; kies in de review")
                uit.append(nv)
                per_label_b[t.label] = nb
            if per_label_b[t.label].status is CandidateStatus.ACCEPTED:
                per_label_b[t.label] = per_label_b[t.label].model_copy(
                    update={"status": CandidateStatus.HUMAN_REVIEW, "reden": regel})
        transities.append(Transitie(label=t.label, reden=t.reden, actie=actie, regel=regel,
                                    van=b.status.value, naar=per_label_b[t.label].status.value))
    return uit, [per_label_b[b.label] for b in beslissingen], transities


def _uitleg(t: Twijfel) -> str:
    return {
        "DETECTOR_CONFLICT": f"De gekozen klasse botst met een vast herkenningspatroon ({t.detail}). Kies zelf.",
        "CLASSIFIER_ABSTAIN": "De classificatie bleef onbeslist; de eerste klasse is een voorstel, kies zelf.",
        "ZELFDE_SPAN": "Hetzelfde fragment kreeg twee klassen; overlap mag alleen bij verschillende functies.",
        "DEGRADED_PARSE": "Zonder zinsontleding geclassificeerd; minder signalen dan normaal.",
    }[t.reden]
