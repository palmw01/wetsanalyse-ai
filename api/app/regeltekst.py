"""De regeltekst van een afleidingsregel, afgeleid uit de delen (ADR-018 §5). Puur: dezelfde delen geven dezelfde tekst.

De taalpatronen komen uit de methode (M02 §3.5.2b en het praktijkvoorbeeld van de zorgtoeslag); de vorm voor gevallen is
een projectkeuze. Begrippen staan in de Markdown cursief, operatorbegrippen vet, naar de schrijfwijze van het boek. De
Markdown geeft voorwaarden en gevallen als lijsten, nooit als tabel: het is kopieertekst.
"""
from __future__ import annotations

from typing import Any

ONBEKEND = "(onbekend begrip)"


def _naam(namen: dict[str, str], begrip_id: str) -> str:
    return namen.get(begrip_id) or ONBEKEND


def _term(t: dict, namen: dict[str, str], md: bool) -> str:
    if t["soort"] == "tekst":
        return t["tekst"].strip()
    naam = _naam(namen, t.get("begrip_id", ""))
    if not md:
        return naam
    return f"**{naam}**" if t["soort"] == "operator" else f"_{naam}_"


def uitdrukking(termen: list[dict], namen: dict[str, str], md: bool = False) -> str:
    return " ".join(x for x in (_term(t, namen, md) for t in termen) if x)


def _kop(verband: str) -> str:
    return "aan alle volgende voorwaarden is voldaan" if verband == "alle" \
        else "aan ten minste één van de volgende voorwaarden is voldaan"


def _blad(v: dict) -> str:
    tekst = v["tekst"].strip().rstrip(";.")
    return f"niet: {tekst}" if v.get("niet") else tekst


def _voorwaarden_regels(groep: dict, diepte: int, md: bool) -> list[str]:
    """De delen van een groep als lijst; een geneste groep als "voldoet aan …" met haar eigen lijst eronder."""
    uit: list[str] = []
    inspring = "  " * diepte
    teken = "- " if md else "• "
    for deel in groep["delen"]:
        if "delen" in deel:
            uit.append(f"{inspring}{teken}het voldoet {_kop(deel.get('verband', 'alle')).replace('is voldaan', '').strip()}:")
            uit += _voorwaarden_regels(deel, diepte + 1, md)
        else:
            uit.append(f"{inspring}{teken}{_blad(deel)}")
    return uit


def _indien(groep: dict | None, md: bool) -> tuple[str, list[str]]:
    """De zin "indien …" en de lijst eronder. Eén voorwaarde zonder nesting blijft in de zin."""
    if not groep:
        return "", []
    delen = groep["delen"]
    if len(delen) == 1 and "delen" not in delen[0]:
        return f" indien {_blad(delen[0])}", []
    return f" indien {_kop(groep.get('verband', 'alle'))}:", _voorwaarden_regels(groep, 0, md)


def _uitvoer(inhoud: dict, namen: dict[str, str], md: bool) -> str:
    """Het uitvoerbegrip met zijn lidwoord: het taalpatroon draagt het lidwoord, het begrip niet (M02 §3.5.2a)."""
    naam = _naam(namen, inhoud["uitvoer_begrip_id"])
    naam = f"_{naam}_" if md else naam
    lidwoord = inhoud.get("lidwoord", "de")
    return f"{lidwoord.capitalize()} {naam}" if lidwoord else naam[:1].upper() + naam[1:]


def _hoofdzin(inhoud: dict, uitkomst: str, namen: dict[str, str], md: bool) -> str:
    uitvoer = _uitvoer(inhoud, namen, md)
    soort = inhoud["soort"]
    if soort == "rekenregel":
        return f"{uitvoer} moet berekend worden als {uitkomst}"
    if soort == "specialisatie":
        onderwerp = _naam(namen, inhoud.get("onderwerp_begrip_id", "")) if inhoud.get("onderwerp_begrip_id") else "het"
        if md and inhoud.get("onderwerp_begrip_id"):
            onderwerp = f"_{onderwerp}_"
        naam = _naam(namen, inhoud["uitvoer_begrip_id"])
        return f"Een {onderwerp} is een {'_' + naam + '_' if md else naam}" if uitkomst in ("", "ja") \
            else f"Een {onderwerp} is {uitkomst}"
    # beslisregel
    return f"{uitvoer} is {uitkomst}"


def regeltekst(inhoud: dict[str, Any], namen: dict[str, str]) -> dict[str, Any]:
    """`{tekst, markdown, gevallen: [{label, tekst}]}`. `namen`: begrip-id → naam van alles wat de regel noemt."""
    gevallen = sorted(inhoud["gevallen"], key=lambda g: -int(g.get("voorrang", 0) or 0)) \
        if any(g.get("voorrang") for g in inhoud["gevallen"]) else inhoud["gevallen"]
    regels_tekst: list[str] = []
    regels_md: list[str] = []
    per_geval: list[dict[str, str]] = []

    if len(gevallen) == 1:
        g = gevallen[0]
        for md, doel in ((False, regels_tekst), (True, regels_md)):
            zin, lijst = _indien(g.get("voorwaarden"), md)
            doel.append(_hoofdzin(inhoud, uitdrukking(g["uitkomst"], namen, md), namen, md) + zin + ("" if lijst else "."))
            doel += lijst
        # De tekst per geval draagt de voorwaarden als lijst, regel voor regel (slotmeting na #1798: "indien aan alle
        # volgende voorwaarden is voldaan:, dan" zonder voorwaarden).
        per_geval.append({"label": g.get("label", ""), "tekst": "\n".join(regels_tekst)})
    else:
        for md, doel in ((False, regels_tekst), (True, regels_md)):
            doel.append(f"{_uitvoer(inhoud, namen, md)} moet bepaald worden volgens het geval dat geldt:")
            for g in gevallen:
                zin, lijst = _indien(g.get("voorwaarden"), md)
                uitkomst = uitdrukking(g["uitkomst"], namen, md)
                voorrang = " (gaat voor)" if g.get("voorrang") else ""
                kop = f"Geval {g['label']}{voorrang}"
                kop = f"**{kop}**" if md else kop
                if lijst:
                    doel.append(f"- {kop}:{zin}" if md else f"{kop}:{zin}")
                    doel += ["  " + r for r in lijst]
                    doel.append(f"  dan: {uitkomst}." if md else f"  dan: {uitkomst}.")
                else:
                    regel = f"{kop}:{zin}, dan {uitkomst}." if zin else f"{kop}: {uitkomst}."
                    doel.append(f"- {regel}" if md else regel)
                if not md:
                    per_geval.append({"label": g["label"], "tekst": "\n".join([zin.strip(), *lijst, f"dan: {uitkomst}."])
                                      if lijst else (f"{zin.strip()}, dan {uitkomst}." if zin else f"{uitkomst}.")})
    return {"tekst": "\n".join(regels_tekst), "markdown": "\n".join(regels_md), "gevallen": per_geval}


def genoemde_begrippen(inhoud: dict[str, Any]) -> list[str]:
    """Elk begrip dat de regel noemt, in de volgorde van de regel, één keer."""
    ids = [inhoud["regelbegrip_id"], inhoud["uitvoer_begrip_id"]]
    if inhoud.get("onderwerp_begrip_id"):
        ids.append(inhoud["onderwerp_begrip_id"])
    ids += [i["begrip_id"] for i in inhoud.get("invoer", [])]
    for g in inhoud["gevallen"]:
        ids += [t["begrip_id"] for t in g["uitkomst"] if t.get("begrip_id")]
    return list(dict.fromkeys(i for i in ids if i))
