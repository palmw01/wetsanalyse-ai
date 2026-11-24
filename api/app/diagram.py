"""Het diagram rond een centrale klasse (deelactiviteit 2c): model, keuze van de diagrammen en een vaste layout.

De methode (Handleiding §3.4, deelactiviteit c) zet de gemarkeerde formuleringen rond één centrale formulering – een
rechtsbetrekking, rechtsfeit, afleidingsregel of voorwaarde – met hun klasse en de relaties ertussen. Dit module is
puur: het kent geen reportlab, geen database en geen graaf. Wie relaties en markeringen heeft (het rapport, een route,
Lex), bouwt hier het `Diagram`; de tekenaars (`diagram_teken`) maken er een PDF-tekening, SVG of Mermaid van.

- **Alleen de structuur.** Methodische relaties (partijen, voorwerp, voorwaarden, invoer en uitvoer, …); een tekstuele
  relatie zoals "maakt een uitzondering op" staat in de lijst Relaties, niet in het diagram. Van een knoop in een
  andere bepaling gaat het niet verder.
- **Alles behalve afgewezen.** Een voorstel van Lex, een goedgekeurde en een aangepaste markering staan erin, net als in
  de graaf; een afgewezen of vervangen markering en een afgewezen relatie niet (besluit eigenaar 24 nov 2026). Een
  voorstel is gestippeld, zodat je het in het diagram kunt beoordelen. Wat de methode bij
  een centrale klasse verwacht en ontbreekt, staat in `ontbreekt`: een signaal, geen oordeel.
- **De hele samenhang binnen de bepaling** (Handleiding §3.4c, p. 34–35): het vertrekpunt is de centrale formulering,
  en wat aan de niet-centrale formuleringen hangt, staat in hetzelfde diagram – ook een afleidingsregel die een kenmerk
  van het voorwerp oplevert, met haar invoer en operatoren. Een andere rechtsbetrekking of een ander rechtsfeit is een
  eindpunt: die krijgt haar eigen diagram (`EIGEN_DIAGRAM`). Acceptatie 24 nov 2026, art. 9 lid 1 IW: met een vaste
  diepte van twee kreeg de afleidingsregel (drie stappen van de rechtsbetrekking) een tweede diagram.
- **De buurt van de graaf.** `buurt` met `DIEPTE` volgt `diagramBuurt` in `frontend/lib/graaf/weergave.ts` (beide
  richtingen, twee relaties ver); `frontend/lib/graaf/diagram.vectoren.json` houdt die twee gelijk. Dat is de
  diagrammodus van de graaf, een buurt over bepalingen heen; het 2c-diagram gebruikt `buurt` zonder diepte.
- **Een vaste plaats per rol**, geen layoutmotor: dezelfde stand geeft altijd hetzelfde plaatje.
- **Brongetrouw.** Een knoop toont het letterlijke fragment, bij een lang fragment begin en eind met een weglatingsteken;
  nooit een parafrase. Met `vorm="begrippen"` toont hij de naam van het begrip (Handleiding: het diagram met begrippen),
  met het nummer van de markering erbij, zodat hij herleidbaar blijft.
"""
from __future__ import annotations

import textwrap
from collections.abc import Callable, Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .jas_relaties import CENTRALE_KLASSEN, RELATIETYPEN

DIEPTE = 2
"""Hoe ver de diagrammodus van de graaf reikt, in relaties: de centrale formulering, wat eraan hangt en wat daar weer aan
hangt. Het 2c-diagram heeft geen vaste diepte (`bouw`)."""

#: Centrale klassen die altijd een eigen diagram krijgen. Bereikt een diagram er een, dan staat ze erin als eindpunt en
#: gaat het daar niet verder. Een afleidingsregel en een voorwaarde hangen bij hun drager.
EIGEN_DIAGRAM = ("Rechtsbetrekking", "Rechtsfeit")
#: De volgorde waarin een centrale formulering wortel wordt: de methode neemt een rechtsbetrekking als vertrekpunt.
WORTELVOLGORDE = {k: i for i, k in enumerate(("Rechtsbetrekking", "Rechtsfeit", "Afleidingsregel", "Voorwaarde"))}

Zone = Literal["boven", "links", "midden", "rechts", "onder"]

#: Waar een buur van de centrale formulering staat, naar het type van de relatie. De rest staat eronder.
ZONE_VAN: dict[str, Zone] = {
    "voorwaarde": "boven", "uitzondering_op": "boven",
    "rechthebbende": "links", "plichthebbende": "links", "verricht": "links", "bevoegde": "links",
    "voorwerp": "rechts", "kenmerk": "rechts", "onderdeel": "rechts",
}

#: Wat de methode bij een centrale klasse verwacht (skill `relaties.md` §*Het diagram rond een centrale klasse*):
#: (relatietypen, richting gezien vanuit de centrale formulering, label). "in" = de relatie wijst naar haar.
VERWACHT: dict[str, tuple[tuple[frozenset[str], Literal["in", "uit"], str], ...]] = {
    "Rechtsbetrekking": ((frozenset({"rechthebbende"}), "in", "rechthebbende"),
                         (frozenset({"plichthebbende"}), "in", "plichthebbende"),
                         (frozenset({"voorwerp"}), "uit", "voorwerp")),
    "Rechtsfeit": ((frozenset({"creeert", "wijzigt", "beeindigt"}), "uit", "de rechtsbetrekking die het creëert, wijzigt of beëindigt"),
                   (frozenset({"verricht"}), "in", "wie het verricht"),
                   (frozenset({"voorwerp"}), "uit", "voorwerp")),
    "Afleidingsregel": ((frozenset({"uitvoer"}), "uit", "uitvoer"),
                        (frozenset({"invoer"}), "in", "invoer")),
    "Voorwaarde": ((frozenset({"voorwaarde"}), "in", "de drager waarvoor zij geldt"),),
}

_WEG = frozenset({"rejected", "vervangen"})


class _Deel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Knoop(_Deel):
    id: str
    soort: Literal["element", "impliciet"] = "element"
    nr: int = 0                                      # het nummer van de markering in haar bepaling; 0 als onbekend
    klasse: str = ""
    tekst: str = ""                                  # het letterlijke fragment, of het label van een impliciete partij
    elders: str = ""                                 # de vindplaats als de markering in een andere bepaling staat
    lifecycle: str = ""
    begrip: str = ""                                 # de naam van het begrip dat de markering aanduidt, als dat er is
    zone: Zone = "onder"
    diepte: int = 0                                  # 0 voor de centrale formulering


class Lijn(_Deel):
    van: str
    naar: str
    code: str
    leesvorm: str
    volgorde: int | None = None
    lifecycle: str = ""


class Diagram(_Deel):
    """Het diagram rond één centrale markering. Structuur, geen plaatsen: die rekent `plaats` uit."""

    centraal: str
    klasse: str
    nr: int = 0
    knopen: list[Knoop]
    lijnen: list[Lijn]
    ontbreekt: list[str] = []                        # wat de methode bij deze klasse verwacht en niet is vastgelegd


Info = Callable[[dict], dict]
"""Per eindpunt (de kant van een relatie, of de centrale markering) wat de bron van de relaties niet draagt: `nr`, `waar` (de bepaling) met `waar_label`, en `begrip`. Een
leeg dict mag. Staat een knoop in een andere bepaling dan de centrale formulering, dan krijgt hij die vindplaats en geen
nummer: dat nummer hoort bij een andere lijst."""


def _actief(r: dict) -> bool:
    return r.get("lifecycle") not in _WEG and r["van"].get("lifecycle") != "rejected" and r["naar"].get("lifecycle") != "rejected"


def _sleutel(kant: dict) -> str:
    return f"{kant.get('soort', 'element')}:{kant['id']}"


def buurt(centraal: str, relaties: Iterable[dict], diepte: int | None = DIEPTE,
          eindpunt: Callable[[str], bool] | None = None) -> dict[str, int]:
    """Wat er over relaties bereikbaar is vanaf `centraal` (een element-id), in beide richtingen, tot `diepte`; per knoop
    (`element:<id>` of `impliciet:<id>`) de afstand. Dezelfde regel als `diagramBuurt` in de werkplek; met `eindpunt`
    gaat het van zo'n knoop niet verder (`bouw`: een knoop in een andere bepaling)."""
    actief = [r for r in relaties if _actief(r)]
    start = f"element:{centraal}"
    afstand = {start: 0}
    rand = [start]
    d = 0
    while rand and (diepte is None or d < diepte):
        d += 1
        volgende = []
        for knoop in rand:
            if eindpunt is not None and knoop != start and eindpunt(knoop):
                continue
            for r in actief:
                a, b = _sleutel(r["van"]), _sleutel(r["naar"])
                ander = b if a == knoop else a if b == knoop else None
                if ander is not None and ander not in afstand:
                    afstand[ander] = d
                    volgende.append(ander)
        rand = volgende
    return afstand


_CODEVOLGORDE = {c: i for i, c in enumerate(RELATIETYPEN)}


def bouw(centraal: dict, relaties: Iterable[dict], info: Info | None = None, diepte: int | None = None) -> Diagram:
    """Het diagram rond `centraal` (een markering: `id`, `klasse`, `tekst`, `nr`) uit relaties in de vorm van de weergave
    (`annotatie_v2_relaties`: `van`/`naar` met `id`, `soort`, `klasse`, `tekst`, `lifecycle`). Zonder `diepte` de hele
    samenhang binnen de bepaling, tot een knoop elders of een andere centrale formulering met een eigen diagram."""
    info = info or (lambda _id: {})
    # Alleen de structuur van de methode: een tekstuele relatie (`uitzondering_op`, `toepassing`, `onderdeel`; in de
    # catalogus `methodisch: false`) is geen regelstructuur (skill `relaties.md`) en hoort niet in het diagram van een
    # centrale klasse (Handleiding §3.4c: partijen, voorwerp, voorwaarden en wat daar aan hangt). Ze blijft in de lijst
    # Relaties, die leidend is.
    relaties = [r for r in relaties if _actief(r) and RELATIETYPEN.get(r["type"], {}).get("methodisch", True)]
    kanten: dict[str, dict] = {f"element:{centraal['id']}": {"id": centraal["id"], "soort": "element", **centraal}}
    for r in relaties:
        for k in (r["van"], r["naar"]):
            kanten.setdefault(_sleutel(k), k)
    # Een knoop in een andere bepaling laat zien hoe de bepalingen samenhangen, maar wat daar weer aan hangt, hoort in het
    # diagram van die bepaling (Termijnen, art. 9 lid 1: 14 van de 23 knopen hingen aan de uitzonderingen in lid 5–7).
    hier_ = info({"soort": "element", **centraal}).get("waar")

    def elders(sleutel: str) -> bool:
        k = kanten.get(sleutel) or {}
        waar = info(k).get("waar") if k.get("soort", "element") == "element" else None
        return bool(hier_ and waar and waar != hier_)
    def eigen_diagram(sleutel: str) -> bool:
        return (kanten.get(sleutel) or {}).get("klasse") in EIGEN_DIAGRAM

    afstand = buurt(centraal["id"], relaties, diepte, eindpunt=lambda s: elders(s) or eigen_diagram(s))
    lijnen = [r for r in relaties if _sleutel(r["van"]) in afstand and _sleutel(r["naar"]) in afstand]
    lijnen.sort(key=lambda r: (_CODEVOLGORDE.get(r["type"], 99), r.get("volgorde") or 0, r.get("id", "")))

    # De zone volgt de eerste relatie waarlangs een knoop bereikt is: vanaf de centrale formulering naar het type,
    # verder die van de ouder.
    start = f"element:{centraal['id']}"
    zone: dict[str, Zone] = {start: "midden"}
    for d in range(1, max(afstand.values()) + 1):
        for r in lijnen:
            a, b = _sleutel(r["van"]), _sleutel(r["naar"])
            for ouder, kind in ((a, b), (b, a)):
                if afstand.get(kind) == d and afstand.get(ouder) == d - 1 and kind not in zone:
                    zone[kind] = ZONE_VAN.get(r["type"], "onder") if ouder == start else zone[ouder]
    knopen = []
    hier = hier_
    for s, d in afstand.items():
        k = kanten[s]
        extra = info(k) if k.get("soort", "element") == "element" else {}
        elders = extra.get("elders", "")
        if extra.get("waar") and hier and extra["waar"] != hier:
            elders = extra.get("waar_label") or extra["waar"]
        nr = 0 if elders else extra.get("nr", k.get("nr", 0)) or 0
        knopen.append(Knoop(id=k["id"], soort=k.get("soort", "element"), nr=nr,
                            klasse=k.get("klasse") or "", tekst=k.get("tekst") or "", elders=elders,
                            lifecycle=k.get("lifecycle") or "", begrip=extra.get("begrip", ""), zone=zone.get(s, "onder"),
                            diepte=d))
    knopen.sort(key=lambda k: (k.diepte, k.nr or 10 ** 6, k.id))
    uit = Diagram(centraal=centraal["id"], klasse=centraal.get("klasse", ""), nr=centraal.get("nr", 0) or 0, knopen=knopen,
                  lijnen=[Lijn(van=_sleutel(r["van"]).split(":", 1)[1], naar=_sleutel(r["naar"]).split(":", 1)[1], code=r["type"],
                               leesvorm=r.get("leesvorm") or RELATIETYPEN.get(r["type"], {}).get("leesvorm", r["type"]),
                               volgorde=r.get("volgorde"), lifecycle=r.get("lifecycle") or "") for r in lijnen])
    uit.ontbreekt = ontbreekt(uit)
    return uit


def ontbreekt(d: Diagram) -> list[str]:
    """Wat de methode bij de klasse van de centrale formulering verwacht en niet als relatie is vastgelegd."""
    uit = []
    for codes, richting, label in VERWACHT.get(d.klasse, ()):
        kant = (lambda l: l.naar) if richting == "in" else (lambda l: l.van)
        if not any(l.code in codes and kant(l) == d.centraal for l in d.lijnen):
            uit.append(label)
    return uit


def diagrammen(markeringen: Iterable[dict], relaties: list[dict], info: Info | None = None,
               diepte: int | None = None) -> list[Diagram]:
    """De diagrammen bij een verzameling markeringen (een bepaling, een werkgebied), in de volgorde van de markeringen.

    Eén diagram per *wortel*, in de volgorde van de methode (`WORTELVOLGORDE`): eerst elke rechtsbetrekking en elk
    rechtsfeit, dan een afleidingsregel die in geen van die diagrammen hangt, en tot slot zo'n voorwaarde met een relatie
    (een voorwaarde hoort bij haar drager). Een markering die al in een eerder diagram hangt, krijgt er geen eigen; een
    rechtsbetrekking of rechtsfeit die in een ander diagram alleen als eindpunt staat, wel."""
    markeringen = list(markeringen)
    centraal = sorted((m for m in markeringen if m.get("klasse") in CENTRALE_KLASSEN and m.get("lifecycle") != "rejected"),
                      key=lambda m: WORTELVOLGORDE.get(m["klasse"], 9))
    gedekt: set[str] = set()
    uit: list[Diagram] = []
    for voorwaarden in (False, True):
        for m in centraal:
            if (m["klasse"] == "Voorwaarde") != voorwaarden or m["id"] in gedekt:
                continue
            d = bouw(m, relaties, info, diepte)
            if voorwaarden and len(d.knopen) == 1:
                continue
            gedekt |= {k.id for k in d.knopen if k.soort == "element" and (k.id == d.centraal or k.klasse not in EIGEN_DIAGRAM)}
            uit.append(d)
    volgorde = {m["id"]: i for i, m in enumerate(markeringen)}
    return sorted(uit, key=lambda d: volgorde.get(d.centraal, 0))


# --- layout ---------------------------------------------------------------------------------------------------------

KNOOP_B = 120.0
KOP_H = 11.0
REGEL_H = 9.0
MARGE = 5.0
TUSSEN_X = 44.0                                     # ruimte voor het label op een lijn tussen twee knopen
TUSSEN_Y = 10.0
BAND = 34.0                                          # tussen de banden: ruimte voor de labels op de lijnen
TEKENS = 28                                          # per regel in een knoop, ruim genomen voor Fira 7,5 pt
MAX_REGELS = 4
MAX_TEKENS = 100
LABEL_TEKENS = 17                                    # per regel van een label op een lijn; hoogstens twee regels


class Geplaatst(_Deel):
    knoop: Knoop
    x: float
    y: float                                         # van boven gemeten; de tekenaar draait om waar dat moet
    b: float
    h: float
    kop: str
    regels: list[str]


class Plaatsing(_Deel):
    breedte: float
    hoogte: float
    knopen: list[Geplaatst]


def ingekort(tekst: str, maximaal: int = MAX_TEKENS) -> str:
    """Begin en eind van een lang fragment, met een weglatingsteken op een woordgrens. Nooit een parafrase."""
    tekst = " ".join(tekst.split())
    if len(tekst) <= maximaal:
        return tekst
    helft = (maximaal - 3) // 2
    begin = tekst[:helft].rsplit(" ", 1)[0]
    eind = tekst[-helft:].split(" ", 1)[-1]
    return f"{begin} … {eind}"


def knooptekst(k: Knoop, vorm: Literal["formuleringen", "begrippen"] = "formuleringen") -> tuple[str, list[str]]:
    """De kop (klasse met nummer of vindplaats) en de regels van een knoop."""
    plek = f"{k.nr} · " if k.nr else ""
    kop = f"{plek}{k.klasse or 'Partij'}" + (f" · {k.elders}" if k.elders else "")
    if k.soort == "impliciet":
        kop = f"{k.klasse or 'Rechtssubject'} · niet in de tekst"
    tekst = k.begrip if vorm == "begrippen" and k.begrip else k.tekst
    regels = textwrap.wrap(ingekort(tekst), TEKENS) or [""]
    if len(regels) > MAX_REGELS:
        regels = regels[:MAX_REGELS - 1] + [textwrap.shorten(" ".join(regels[MAX_REGELS - 1:]), TEKENS, placeholder=" …")]
    return kop, regels


def labelregels(tekst: str) -> list[str]:
    """Het label op een lijn in hoogstens twee regels, zodat het tussen twee knopen past."""
    regels = textwrap.wrap(tekst, LABEL_TEKENS) or [""]
    return regels if len(regels) <= 2 else [regels[0], textwrap.shorten(" ".join(regels[1:]), LABEL_TEKENS, placeholder=" …")]


def plaats(d: Diagram, breedte: float = 480.0, vorm: Literal["formuleringen", "begrippen"] = "formuleringen") -> Plaatsing:
    """Een vaste plaats per rol: voorwaarden en uitzonderingen boven, partijen links, het voorwerp rechts, de rest eronder, de centrale
    formulering in het midden. Binnen een zone de volgorde van `Diagram.knopen`."""
    # De ruimte tussen twee kolommen draagt het breedste label op een lijn, met marge: een label als "is invoer van (1)"
    # is breder dan de vaste ruimte en viel anders onder de blokken (melding gebruiker 24 nov 2026). Bij drie kolommen
    # worden de blokken smaller, zodat de tekening binnen de breedte blijft.
    from .diagram_teken import _labelmaat, _labeltekst
    tussen = max([TUSSEN_X] + [_labelmaat(_labeltekst(lijn))[0] + 8 for lijn in d.lijnen])
    b = min(KNOOP_B, (breedte - 2 * tussen) / 3)
    per_zone: dict[str, list[Knoop]] = {z: [] for z in ("boven", "links", "midden", "rechts", "onder")}
    for k in d.knopen:
        per_zone["midden" if k.id == d.centraal and k.soort == "element" else k.zone].append(k)
    teksten = {(k.soort, k.id): knooptekst(k, vorm) for k in d.knopen}

    def hoogte(k: Knoop) -> float:
        return KOP_H + len(teksten[(k.soort, k.id)][1]) * REGEL_H + 2 * MARGE

    geplaatst: list[Geplaatst] = []

    def zet(k: Knoop, x: float, y: float) -> float:
        kop, regels = teksten[(k.soort, k.id)]
        h = hoogte(k)
        geplaatst.append(Geplaatst(knoop=k, x=round(x, 2), y=round(y, 2), b=round(b, 2), h=round(h, 2), kop=kop, regels=regels))
        return h

    # Elke stap boven en onder krijgt één rij, de tweede stap verder van het midden. Een rij breekt nooit af: dan liep een
    # lijn naar de verste rij door een knoop van de dichtste. Past een rij niet, dan wordt de tekening breder en schaalt de
    # tekenaar haar terug naar de pagina.
    boven = [[k for k in per_zone["boven"] if k.diepte == d] for d in sorted({k.diepte for k in per_zone["boven"]}, reverse=True)]
    onder = [[k for k in per_zone["onder"] if k.diepte == d] for d in sorted({k.diepte for k in per_zone["onder"]})]
    rijbreedte = lambda rij: len(rij) * b + (len(rij) - 1) * TUSSEN_X
    # Een verdere stap staat in de volgorde van de knopen waar hij aan hangt, zodat de lijnen elkaar zo min mogelijk kruisen.
    buren: dict[str, list[str]] = {}
    for lijn in d.lijnen:
        buren.setdefault(lijn.van, []).append(lijn.naar)
        buren.setdefault(lijn.naar, []).append(lijn.van)

    def naar_ouders(rijen: list[list[Knoop]]) -> None:
        for i in range(1, len(rijen)):
            plek = {k.id: j for j, k in enumerate(rijen[i - 1])}
            def sleutel(k: Knoop, plek=plek) -> float:
                p_ = [plek[n] for n in buren.get(k.id, []) if n in plek]
                return sum(p_) / len(p_) if p_ else len(plek)
            rijen[i].sort(key=sleutel)

    naar_ouders(boven[::-1])
    naar_ouders(onder)
    # De middelste band: links de partijen, rechts het voorwerp, met elke verdere stap een kolom verder van het midden
    # (Handleiding §3.4c: de variabele bij het rechtsobject, de afleidingsregel die haar oplevert, haar invoer). Een keten
    # in één kolom gestapeld liet de lijnen door de knopen ertussen lopen (acceptatie 24 nov 2026, art. 9 lid 1 IW).
    def kolommen(zone: str) -> list[list[Knoop]]:
        return [[k for k in per_zone[zone] if k.diepte == dd] for dd in sorted({k.diepte for k in per_zone[zone]})]
    rechts, links = kolommen("rechts"), kolommen("links")
    naar_ouders([per_zone["midden"]] + rechts)
    naar_ouders([per_zone["midden"]] + links)
    banden = links[::-1] + [per_zone["midden"]] + rechts
    bandbreedte = len(banden) * b + (len(banden) - 1) * tussen
    totaal = max([breedte, bandbreedte] + [rijbreedte(r) for r in boven + onder])

    # Een rij boven of onder staat onder de centrale formulering, niet in het midden van een brede tekening (dan liep een
    # lange schuine lijn naar haar tijdsaanduiding); ze blijft binnen de tekening.
    if len(banden) <= 3 and (breedte - 3 * b) / 2 >= tussen:
        midden_kolom = (totaal - b) / 2
    else:
        midden_kolom = (totaal - bandbreedte) / 2 + len(links) * (b + tussen)

    def rij(knopen: list[Knoop], y: float) -> float:
        x0 = min(max(midden_kolom + b / 2 - rijbreedte(knopen) / 2, 0.0), totaal - rijbreedte(knopen))
        for j, k in enumerate(knopen):
            zet(k, x0 + j * (b + TUSSEN_X), y)
        return y + max(hoogte(k) for k in knopen) + BAND

    y = 0.0
    for r in boven:
        y = rij(r, y)
    # Met één kolom aan elke kant de oude verdeling over de hele breedte; met meer kolommen sluiten ze aan.
    if len(banden) <= 3 and (breedte - 3 * b) / 2 >= tussen:
        verschuif = (totaal - breedte) / 2
        xs = {"links": verschuif, "midden": verschuif + (breedte - b) / 2, "rechts": verschuif + breedte - b}
        kolom_x = ([xs["links"]] if links else []) + [xs["midden"]] + ([xs["rechts"]] if rechts else [])
    else:
        x0 = (totaal - bandbreedte) / 2
        kolom_x = [x0 + j * (b + tussen) for j in range(len(banden))]
    stapel = [sum(hoogte(k) for k in kol) + TUSSEN_Y * max(0, len(kol) - 1) for kol in banden]
    band = max(stapel)
    for kol, x, h in zip(banden, kolom_x, stapel):
        yz = y + (band - h) / 2
        for k in kol:
            yz += zet(k, x, yz) + TUSSEN_Y
    y += band + BAND
    for r in onder:
        y = rij(r, y)
    return Plaatsing(breedte=round(totaal, 2), hoogte=round(y - BAND, 2), knopen=geplaatst)
