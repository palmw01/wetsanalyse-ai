"""De inhoudsopgave van een regeling als boom: documentvolgorde, bereiken, hele niveaus.

`inhoudsopgave` gaf ruwe rijen op IRI-volgorde (artikel 1, 10, 11 … 2) met per rij IRI, jci, label en
titel. De Invorderingswet werd zo ruim 20k tekens; afgeknipt op 8000 zag het model een willekeurige
greep en vulde het de rest met "…". Deze module maakt er een overzicht van dat wél past én klopt:

- **documentvolgorde** uit `bwb:volgtOp` (de keten die de importer schrijft), met een natuurlijke
  nummersortering als terugval (hoofdstukken Romeins: II vóór IV vóór IX);
- **nummerreeksen**: opeenvolgende artikelen of divisies zonder eigen titel worden één regel met
  hun nummers zoals ze in het document staan ("32, 33, 33a, 34 …") – geen "32–35", want dat suggereert
  een artikel 34 dat er misschien niet is;
- **hele niveaus**: zo diep als binnen de begroting past, nooit een half niveau. Een deel waarvan
  de onderdelen niet meer passen staat er ingeklapt, met zijn telling en een `openen`-aanroep
  (`inhoudsopgave` met `vanaf` = zijn IRI) die precies dat deel levert. Ingeklapt is verdieping,
  geen onvolledigheid: `volledig` blijft true zolang elk deel van de gevraagde scope genoemd of
  geteld is.
- Past zelfs het bovenste niveau niet (de Leidraad heeft ~100 divisies met een eigen titel), dan
  pagineert hij dat niveau met `offset`.
"""
from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from ..resultaat import BUDGET, TeGroot, compact, passend, resultaat

# Wat in een bereik samengaat: bepalingen, geen structuur.
_BEPALING = {"Artikel", "Divisie"}
_ROMEINS = re.compile(r"^([IVXLC]+)(.*)$")
_WAARDE = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def _romeins(tekst: str) -> int:
    som = 0
    for i, c in enumerate(tekst):
        nu, volgende = _WAARDE[c], _WAARDE.get(tekst[i + 1], 0) if i + 1 < len(tekst) else 0
        som += -nu if nu < volgende else nu
    return som


def natuurlijke_sleutel(nummer: str) -> tuple:
    """"VIIa" → (7, "a"); "27quinquies" → ((27, "quinquies"),); "10.2.1" → numeriek per segment."""
    nummer = (nummer or "").strip().rstrip(".")
    m = _ROMEINS.match(nummer)
    if m:
        return (0, _romeins(m.group(1)), m.group(2))
    delen = []
    for seg in re.split(r"[.:]", nummer):
        g = re.match(r"^(\d+)(.*)$", seg)
        delen.append((int(g.group(1)), g.group(2)) if g else (10**9, seg))
    return (1, *delen)


def _documentvolgorde(kinderen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Volg de `volgtOp`-keten; waar die ontbreekt of breekt, de natuurlijke nummervolgorde."""
    rest = sorted(kinderen, key=lambda k: natuurlijke_sleutel(k["nummer"]))
    ids = {k["iri"] for k in rest}
    uit: list[dict[str, Any]] = []
    gedaan: set[str] = set()
    while rest:
        klaar = next((k for k in rest if k["vorige"] not in ids or k["vorige"] in gedaan), rest[0])
        rest.remove(klaar)
        gedaan.add(klaar["iri"])
        uit.append(klaar)
    return uit


def _nummers(groep: list[dict[str, Any]]) -> str:
    return ", ".join(k["nummer"] for k in groep)


class Boom:
    """De geparste rijen van `queries.inhoudsopgave` als boom onder `wortel`."""

    def __init__(self, rijen: Sequence[dict[str, str]], wortel: str, query_diepte: int, bwb_id: str = ""):
        self.wortel = wortel
        self.bwb_id = bwb_id
        # Op de diepste opgehaalde laag kan een structuurdeel onderdelen hebben die de query niet meer
        # meenam (een Awb-paragraaf op niveau 4 met zijn artikelen op 5). Zo'n deel is ingeklapt, niet leeg.
        self.query_diepte = query_diepte
        knopen: dict[str, dict[str, Any]] = {}
        for r in rijen:
            iri = r.get("deel", "")
            if not iri:
                continue
            k = knopen.setdefault(iri, {"iri": iri, "soort": "", "nummer": "", "titel": "", "vorige": "",
                                        "ouder": r.get("ouder", ""), "niveau": int(r.get("niveau") or 1)})
            for veld, bron in (("soort", "soort"), ("nummer", "nummer"), ("titel", "titel"), ("vorige", "volgtOp")):
                if not k[veld] and r.get(bron):
                    k[veld] = r[bron].strip()
        self.knopen = knopen
        per_ouder: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for k in knopen.values():
            per_ouder[k["ouder"]].append(k)
        self.kinderen = {ouder: _documentvolgorde(lijst) for ouder, lijst in per_ouder.items()}
        self.diepte = max((k["niveau"] for k in knopen.values()), default=0)

    def _openen(self, iri: str) -> dict[str, Any]:
        return {"tool": "inhoudsopgave", "args": {"bwb_id": self.bwb_id, "vanaf": iri}}

    def telling(self) -> dict[str, int]:
        uit: dict[str, int] = defaultdict(int)
        for k in self.knopen.values():
            uit[k["soort"] or "Onbekend"] += 1
        return dict(uit)

    def _niet_opgehaald(self, k: dict[str, Any]) -> bool:
        return (not self.kinderen.get(k["iri"]) and k["niveau"] >= self.query_diepte
                and k["soort"] not in _BEPALING)

    def _onder(self, iri: str) -> tuple[int, bool]:
        """Het aantal bepalingen (artikelen/divisies) onder een deel, en of die telling compleet is:
        een structuurdeel op de diepste opgehaalde laag kan nog bepalingen dragen die er niet bij zitten."""
        n, compleet = 0, True
        for k in self.kinderen.get(iri, []):
            onder, c = self._onder(k["iri"])
            n += (k["soort"] in _BEPALING) + onder
            compleet = compleet and c and not self._niet_opgehaald(k)
        return n, compleet

    def rijen(self, tot: int, *, top: Sequence[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        """De boom tot en met niveau `tot`, in documentvolgorde, met bereiken voor bepalingen
        zonder eigen titel en een telling op elk deel dat ingeklapt blijft."""
        uit: list[dict[str, Any]] = []

        def loop(kinderen: Sequence[dict[str, Any]], niveau: int) -> None:
            groep: list[dict[str, Any]] = []

            def sluit() -> None:
                if groep:
                    uit.append(compact({"niveau": niveau, "soort": groep[0]["soort"],
                                        "nummers": _nummers(groep), "bepalingen": len(groep)}))
                    groep.clear()

            for k in kinderen:
                eigen = self.kinderen.get(k["iri"], [])
                niet_opgehaald = self._niet_opgehaald(k)
                if k["soort"] in _BEPALING and not k["titel"] and not eigen:
                    groep.append(k)
                    continue
                sluit()
                rij = {"niveau": niveau, "soort": k["soort"], "nummer": k["nummer"], "titel": k["titel"]}
                ingeklapt = bool(eigen) and niveau >= tot
                if ingeklapt:
                    # Wat eronder zit, met de IRI als ondubbelzinnige ingang voor `vanaf`: "afdeling 1"
                    # komt in elk hoofdstuk terug, de IRI niet.
                    n, compleet = self._onder(k["iri"])
                    rij.update({"onderdelen": len(eigen), "bepalingen" if compleet else "bepalingen_minstens": n,
                                "openen": self._openen(k["iri"])})
                elif niet_opgehaald:
                    rij.update({"onderdelen": "niet opgehaald", "openen": self._openen(k["iri"])})
                uit.append(compact(rij))
                if eigen and not ingeklapt:
                    loop(eigen, niveau + 1)
            sluit()

        loop(top if top is not None else self.kinderen.get(self.wortel, []), 1)
        return uit


def inhoudsopgave_resultaat(
    rijen: Sequence[dict[str, str]],
    *,
    bwb_id: str,
    wortel: str,
    args: dict[str, Any],
    query_diepte: int,
    offset: int = 0,
    budget: int = BUDGET,
) -> str:
    """Het contract voor `inhoudsopgave`: zo diep als past, anders het bovenste niveau per pagina."""
    boom = Boom(rijen, wortel, query_diepte, bwb_id)
    top = boom.kinderen.get(wortel, [])
    kop = {"bwb_id": bwb_id, "wortel": wortel, "telling": boom.telling()}
    toelichting = ("Documentvolgorde. 'nummers' = opeenvolgende bepalingen zonder eigen titel, zoals ze in "
                   "het document staan. Een ingeklapt deel draagt 'openen': die aanroep levert dat deel.")

    def contract(rijen_: Sequence[dict[str, Any]], *, volledig: bool, vervolg: dict[str, Any] | None) -> str:
        return resultaat(rijen_, volledig=volledig, vervolg=vervolg, toelichting=toelichting, extra=kop)

    if offset == 0:
        # Zo diep als past. Ingeklapte delen zijn géén onvolledigheid: hun telling staat erbij en hun
        # ingang ook. Volledig betekent hier: elk deel van de regeling is genoemd of geteld.
        for tot in range(max(boom.diepte, 1), 0, -1):
            tekst = contract(boom.rijen(tot), volledig=True, vervolg=None)
            if len(tekst) <= budget:
                return tekst
    # Zelfs het bovenste niveau past niet: pagineer het, met dezelfde vorm per deel.
    def maak(deel: Sequence[dict[str, Any]]) -> str:
        eind = offset + len(deel)
        klaar = eind >= len(top)
        return contract(boom.rijen(1, top=deel), volledig=klaar,
                        vervolg=None if klaar else {"tool": "inhoudsopgave", "args": {**args, "offset": eind}})

    k, tekst = passend(top[offset:], maak, budget)
    if top[offset:] and k == 0:
        raise TeGroot("inhoudsopgave: één deel van het bovenste niveau is groter dan de begroting")
    return tekst
