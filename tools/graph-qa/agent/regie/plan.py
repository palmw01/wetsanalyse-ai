"""Het plan van een regie (ADR-012), in code: wat er per deelvraag te doen is, uit de stand bij de api.

Zuiver: geen api, geen graaf, geen model. De regisseur leest de stand en geeft hem hier aan; dezelfde stand geeft
hetzelfde plan, met hetzelfde `plan_id`. Dat id is wat de jurist bevestigt: een plan dat intussen veranderde, start
niet.

Twee opdrachten:

- **`bronnen`**: één taak per deelvraag die nog niet klaar is, in de volgorde van de deelvragen. Zonder deelvragen
  is er één taak voor de analysevraag. Het zoeken zelf kost geen tokens.
- **`annoteren`**: de werkvoorraad (status *nieuw*, rol *analyseren*), verdeeld zonder overlap. Elke bepaling hoort
  bij de eerste deelvraag waaronder ze valt; zo werken nooit twee kinderen aan dezelfde. Samen hoogstens `PLAFOND`.
  Past de bovenkant van de schatting niet in het budget dat resteert, dan krimpt het plan tot het past.

Wat niet in het plan komt, staat in `buiten`, met de reden. Er valt niets stil weg.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace
from typing import Any, Literal

Opdracht = Literal["bronnen", "annoteren"]

#: Hoeveel bepalingen een regie samen hoogstens annoteert: gelijk aan het plafond van één werkgebiedrun.
PLAFOND = 40
#: De bovenkant van de schatting, als factor op de mediaan: daarop krimpt het plan.
MARGE = 1.5
#: Het aandeel van een kind, als factor op zijn schatting.
AANDEEL = 1.25
#: De eenheid van de bronselectie zonder deelvragen (api `bronselectie.ANALYSEVRAAG`).
ANALYSEVRAAG = "analysevraag"


def _bepalingen(n: int) -> str:
    return "bepaling" if n == 1 else "bepalingen"


def _getal(n: int) -> str:
    return f"{n:,}".replace(",", ".")


@dataclass(frozen=True)
class Taak:
    """Eén kind: wat het doet, onder welke deelvraag, en bij annoteren welke bepalingen."""
    soort: Opdracht
    deelvraag_id: str               # leeg of ANALYSEVRAAG: het werkgebied zonder deelvragen
    nr: int
    vraag: str
    eenheden: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()
    schatting: int | None = None    # tokens: de mediaan keer het aantal
    aandeel: int | None = None      # tokens die het kind hoogstens mag gebruiken

    @property
    def onder_deelvraag(self) -> bool:
        return bool(self.deelvraag_id) and self.deelvraag_id != ANALYSEVRAAG

    @property
    def titel(self) -> str:
        """De titel van het kindgesprek."""
        wat = "Bronnen" if self.soort == "bronnen" else "Annoteren"
        waar = f"deelvraag {self.nr}" if self.onder_deelvraag else "analysevraag"
        if self.soort == "annoteren":
            return f"{wat} · {waar} ({len(self.eenheden)} {_bepalingen(len(self.eenheden))})"
        return f"{wat} · {waar}"


@dataclass(frozen=True)
class Plan:
    opdracht: Opdracht
    werkgebied_id: str
    taken: tuple[Taak, ...]
    buiten: tuple[str, ...] = ()
    schatting: int | None = None
    hoog: int | None = None
    resterend: int | None = None
    plan_id: str = ""

    def als_dict(self) -> dict[str, Any]:
        """Het plan zoals de api het bewaart en de werkplek het toont."""
        d = asdict(self)
        d["taken"] = [{**asdict(t), "titel": t.titel} for t in self.taken]
        return d


def _met_id(plan: Plan) -> Plan:
    """Het id is een hash van wat er gebeurt: opdracht, werkgebied en per taak soort, deelvraag en bepalingen. De
    schatting en het budget horen er niet in: die veranderen met elke beurt elders, het werk niet."""
    kern = {"opdracht": plan.opdracht, "werkgebied_id": plan.werkgebied_id,
            "taken": [[t.soort, t.deelvraag_id, list(t.eenheden)] for t in plan.taken]}
    digest = hashlib.sha256(json.dumps(kern, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    return replace(plan, plan_id=digest)


def plan_bronnen(werkgebied_id: str, overzicht: dict[str, Any]) -> Plan:
    """Per deelvraag die nog niet klaar is een taak, uit het overzicht van `GET …/bronselectie`."""
    taken, buiten = [], []
    for v in overzicht.get("deelvragen") or []:
        did = str(v.get("id") or "")
        nr = int(v.get("nr") or 0)
        if v.get("klaar"):
            buiten.append(f"Deelvraag {nr} is al klaar." if did != ANALYSEVRAAG else "De analysevraag is al klaar.")
            continue
        taken.append(Taak(soort="bronnen", deelvraag_id=did, nr=nr, vraag=str(v.get("vraag") or "")))
    return _met_id(Plan(opdracht="bronnen", werkgebied_id=werkgebied_id, taken=tuple(taken), buiten=tuple(buiten),
                        schatting=0, hoog=0))


def _actief(werkgebied: dict[str, Any]) -> list[dict[str, Any]]:
    dv = [d for d in werkgebied.get("deelvragen") or [] if d.get("status") == "actief"]
    return sorted(dv, key=lambda d: (d.get("volgorde", 0), str(d.get("id", ""))))


def _groepen(werkgebied: dict[str, Any], te: list[str], per_iri: dict[str, dict]) -> tuple[list, list[str]]:
    """De werkvoorraad per deelvraag, zonder overlap: een bepaling gaat naar de eerste deelvraag waaronder ze valt."""
    deelvragen = _actief(werkgebied)
    if not deelvragen:
        return ([("", 0, str(werkgebied.get("analysevraag") or ""), te)] if te else []), []
    groepen, vrij = [], list(te)
    for nr, d in enumerate(deelvragen, start=1):
        bronnen = set(d.get("bronnen") or [])
        hier = [i for i in vrij if bronnen & set(per_iri.get(i, {}).get("selecties") or [])]
        vrij = [i for i in vrij if i not in hier]
        if hier:
            groepen.append((str(d["id"]), nr, str(d.get("vraag") or ""), hier))
    buiten = []
    if vrij:
        buiten.append(f"{len(vrij)} {_bepalingen(len(vrij))} {'hangt' if len(vrij) == 1 else 'hangen'} onder geen "
                      "deelvraag; koppel de bron aan een deelvraag, of annoteer het hele werkgebied.")
    return groepen, buiten


#: Hoe het plan de stand noemt van een bepaling die al een annotatie heeft (api `werkgebied_werkvoorraad._stand`).
STAND_ZIN = {"te_beoordelen": "wacht op beoordeling", "beoordeeld": "beoordeeld", "afgerond": "afgerond",
             "zonder_markeringen": "geannoteerd, zonder markeringen"}
#: Zoveel bepalingen noemt het plan bij naam; de rest telt het.
MAX_GENOEMD = 5
_NIVEAUS = {"Hoofdstuk", "Afdeling", "Titel", "Titeldeel", "Paragraaf", "Divisie"}


def _naam(eenheid: dict[str, Any]) -> str:
    """"Artikel 9, Lid 1": zonder een kaal niveau ("Hoofdstuk, …") dat de werkvoorraad soms zonder nummer draagt."""
    delen = [d for d in str(eenheid.get("label") or "").split(", ") if d and d not in _NIVEAUS]
    return ", ".join(delen) or str(eenheid.get("bron_iri") or "")


def _al_geannoteerd(werkvoorraad: dict[str, Any]) -> list[str]:
    """Bepalingen die al een annotatie hebben, gaan niet mee, en dat staat erbij: anders lijkt een opgenomen bron stil
    uit het plan te vallen (meting 8 nov 2026). De lagen zijn gedeeld, dus ook werk van een collega telt."""
    al = [e for e in werkvoorraad.get("eenheden") or [] if (e.get("stand") or {}).get("status", "nieuw") != "nieuw"]
    if not al:
        return []
    namen = [f"{_naam(e)} ({STAND_ZIN.get((e.get('stand') or {}).get('status', ''), 'al geannoteerd')})"
             for e in al[:MAX_GENOEMD]]
    rest = len(al) - len(namen)
    n = len(al)
    return [f"{n} {_bepalingen(n)} {'heeft' if n == 1 else 'hebben'} al een annotatie en {'is' if n == 1 else 'zijn'} "
            f"overgeslagen: {', '.join(namen)}{f' en {rest} meer' if rest else ''}. Opnieuw annoteren vraag je per "
            "bepaling in het gesprek."]


def _hoogstens(groepen: list, n: int) -> list:
    """De eerste `n` bepalingen, in de volgorde van de deelvragen."""
    uit = []
    for did, nr, vraag, iris in groepen:
        if n <= 0:
            break
        uit.append((did, nr, vraag, iris[:n]))
        n -= len(iris[:n])
    return uit


def plan_annoteren(werkgebied: dict[str, Any], werkvoorraad: dict[str, Any], *, plafond: int = PLAFOND) -> Plan:
    """De werkvoorraad van het hele werkgebied (`GET …/annotatie-werkvoorraad`) zonder overlap over de deelvragen.

    De bronnen van een deelvraag zijn haar gekoppelde selecties (`deelvragen[].bronnen` van het werkgebied); een
    eenheid noemt de selecties waaronder ze valt (`eenheden[].selecties`)."""
    te = list(werkvoorraad.get("te_annoteren") or [])
    per_iri = {e["bron_iri"]: e for e in werkvoorraad.get("eenheden") or []}
    groepen, buiten = _groepen(werkgebied, te, per_iri)
    buiten = _al_geannoteerd(werkvoorraad) + buiten

    totaal = sum(len(g[3]) for g in groepen)
    if totaal > plafond:
        weg = totaal - plafond
        buiten.append(f"{weg} {_bepalingen(weg)} vallen buiten het plafond van {plafond} per regie; die komen bij een "
                      "volgende regie.")
        groepen, totaal = _hoogstens(groepen, plafond), plafond

    per_bepaling = int((werkvoorraad.get("schatting") or {}).get("per_bepaling") or 0) or None
    budget = werkvoorraad.get("budget") or {}
    resterend = int(budget["resterend"]) if budget.get("actief") and budget.get("resterend") is not None else None
    if per_bepaling and resterend is not None:
        past = max(0, math.floor(resterend / (per_bepaling * MARGE)))
        if past < totaal:
            weg = totaal - past
            buiten.append(f"{weg} {_bepalingen(weg)} passen niet in je budget: er resteert ~{_getal(resterend)} tokens, "
                          f"en ik reken ~{_getal(round(per_bepaling * MARGE))} per bepaling (met marge).")
            groepen, totaal = _hoogstens(groepen, past), past

    taken = []
    for did, nr, vraag, iris in groepen:
        schatting = per_bepaling * len(iris) if per_bepaling else None
        if schatting:
            aandeel = math.ceil(schatting * AANDEEL)
        elif resterend is not None:
            aandeel = max(1, resterend // len(groepen))   # zonder schatting: het budget gelijk verdeeld
        else:
            aandeel = None
        labels = tuple(", ".join(x for x in (per_iri.get(i, {}).get("regeling"), per_iri.get(i, {}).get("label")) if x)
                       or i for i in iris)
        taken.append(Taak(soort="annoteren", deelvraag_id=did, nr=nr, vraag=vraag, eenheden=tuple(iris),
                          labels=labels, schatting=schatting, aandeel=aandeel))
    return _met_id(Plan(
        opdracht="annoteren", werkgebied_id=str(werkgebied.get("id") or ""), taken=tuple(taken), buiten=tuple(buiten),
        schatting=per_bepaling * totaal if per_bepaling else None,
        hoog=math.ceil(per_bepaling * totaal * MARGE) if per_bepaling else None, resterend=resterend))


def kind_verzoek(taak: Taak, *, werkgebied_id: str, gesprek_id: str) -> dict[str, Any]:
    """Het verzoek voor de kind-run (een `ChatRequest`): dezelfde actie als een klik in de werkplek."""
    onderwerp = ({"onderwerp": {"soort": "deelvraag", "werkgebied_id": werkgebied_id, "id": taak.deelvraag_id,
                                "label": taak.vraag[:300]}} if taak.onder_deelvraag else {})
    waar = f"deelvraag {taak.nr}: {taak.vraag}" if taak.onder_deelvraag else "de analysevraag"
    basis = {"conversation_id": gesprek_id, "werkgebied_id": werkgebied_id, **onderwerp}
    if taak.soort == "bronnen":
        return {"question": f"Bepaal de bronnen bij {waar}", "actie": "bronselectie", **basis}
    n = len(taak.eenheden)
    return {"question": f"Annoteer de {n} {_bepalingen(n)} onder {waar}",
            "actie": "deelvragen_annoteren" if taak.onder_deelvraag else "werkgebied_annoteren", **basis,
            "bevestigd": n, "eenheden": list(taak.eenheden),
            **({"budget_aandeel": taak.aandeel} if taak.aandeel else {})}
