#!/usr/bin/env python3
"""Genereer de relatiecatalogus (ADR-011) uit de wetsanalyse-skill naar de api, graph-qa en de werkplek.

De bron is `.claude/skills/wetsanalyse/relaties.json`. De api en de werkplek dragen elk een gegenereerde kopie, want
het productie-image van de api draagt de skill niet en een browser kan geen JSON uit de repo lezen. graph-qa draagt
dezelfde Python als de api (`agent/jas_relaties.py`): de relatievoorstellen van de keten (`jas_pipeline/relaties.py`)
toetsen ermee wat de api daarna opnieuw toetst, dus beide kanten lezen letterlijk dezelfde regels. Wie een type wil
wijzigen, bewerkt de JSON en draait dit script; een met de hand bewerkte kopie faalt op `--check`.

Alleen de standaardbibliotheek: `tests/poort` gebruikt `genereer()` ook. `scripts/genereer_jas_klassen.py` roept dit
script mee aan, zodat de bestaande `--check` in CI de relaties ook dekt.

Gebruik: python3 scripts/genereer_jas_relaties.py [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pprint
import sys
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[3]
BRON = WORTEL / ".claude" / "skills" / "wetsanalyse" / "relaties.json"
API_DOEL = WORTEL / "api" / "app" / "jas_relaties.py"
GRAPHQA_DOEL = WORTEL / "tools" / "graph-qa" / "agent" / "jas_relaties.py"
FRONTEND_DOEL = WORTEL / "frontend" / "lib" / "jasRelaties.ts"

#: De velden van een type in de gegenereerde vorm, met hun standaard.
VELDEN = {"leesvorm": "", "invers": "", "van": [], "naar": [], "paren": [], "drager": "", "volgorde": False,
          "tekstueel": False, "eindpunt_bron": False, "methodisch": True, "bron": []}
#: De pseudoklasse van een eindpunt dat een hele bepaling is (soort `bron`, M-1-1): geen JAS-klasse, wel een kant.
BRON_KLASSE = "Bron"

_API_FUNCTIES = '''

def type_van(code: str) -> dict | None:
    """Het type met deze code, of None."""
    return RELATIETYPEN.get(code)


def als_klassen(klasse: str, subtype: str = "") -> list[tuple[str, str]]:
    """De klassen waarvan een markering de relaties mag aangaan: haar eigen klasse, en bij een verbijzondering ook de
    klasse die zij verbijzondert, met het subtype dat zij daar heeft (een tijdsaanduiding die een variabele
    verbijzondert, is ook een variabele; H2:107, M01 h.4 §12)."""
    v = VERBIJZONDERINGEN.get(klasse, {}).get(subtype)
    return [(klasse, subtype)] + ([(v["klasse"], v["subtype"])] if v else [])


def _past(t: dict, van_klasse: str, naar_klasse: str, van_subtype: str, naar_subtype: str) -> bool:
    if t["paren"]:
        return any(p["van"] == van_klasse and p["naar"] == naar_klasse
                   and p.get("van_subtype", van_subtype) == van_subtype
                   and p.get("naar_subtype", naar_subtype) == naar_subtype for p in t["paren"])
    return van_klasse in t["van"] and naar_klasse in t["naar"]


def toegestaan(code: str, van_klasse: str, naar_klasse: str, van_subtype: str = "", naar_subtype: str = "") -> bool:
    """Past dit klassenpaar bij het type? Bij een type met `paren` telt alleen een paar uit die lijst, en een paar
    dat een subtype noemt eist dat subtype; anders telt elke klasse aan beide kanten. Een kant met een verbijzondering
    telt ook als de klasse die zij verbijzondert (`als_klassen`). Een hele bepaling (`BRON`) mag alleen aan de kant
    naar, bij een type met `eindpunt_bron` (M-1-1)."""
    t = RELATIETYPEN.get(code)
    if t is None or van_klasse == BRON:
        return False
    if naar_klasse == BRON:
        return t["eindpunt_bron"] and any(k in t["van"] for k, _ in als_klassen(van_klasse, van_subtype))
    return any(_past(t, vk, nk, vs, ns) for vk, vs in als_klassen(van_klasse, van_subtype)
               for nk, ns in als_klassen(naar_klasse, naar_subtype))


def drager_kant(code: str) -> str:
    """"van" of "naar": de kant waarvan de laag de relatie draagt (ADR-011)."""
    return RELATIETYPEN[code]["drager"]
'''


#: Dezelfde regel als `toegestaan` in de api; `frontend/lib/jasRelaties.vectoren.json` toetst beide kanten.
_TS_FUNCTIES = """
/** De klassen waarvan een markering de relaties mag aangaan: haar eigen klasse, en bij een verbijzondering ook de klasse
 * die zij verbijzondert, met het subtype dat zij daar heeft (zoals `als_klassen` in de api). */
export function alsKlassen(klasse: string, subtype = ""): [string, string][] {
  const v = VERBIJZONDERINGEN[klasse]?.[subtype];
  return v ? [[klasse, subtype], [v.klasse, v.subtype]] : [[klasse, subtype]];
}

function past(t: RelatieType, vanKlasse: string, naarKlasse: string, vanSubtype: string, naarSubtype: string): boolean {
  if (t.paren.length) {
    return t.paren.some((p) => p.van === vanKlasse && p.naar === naarKlasse
      && (p.van_subtype ?? vanSubtype) === vanSubtype && (p.naar_subtype ?? naarSubtype) === naarSubtype);
  }
  return t.van.includes(vanKlasse) && t.naar.includes(naarKlasse);
}

/** Past dit klassenpaar bij het type? Bij een type met `paren` telt alleen een paar uit die lijst, en een paar dat een
 * subtype noemt eist dat subtype; anders telt elke klasse aan beide kanten. Een kant met een verbijzondering telt ook als
 * de klasse die zij verbijzondert (zoals `toegestaan` in de api). */
export function toegestaan(code: string, vanKlasse: string, naarKlasse: string, vanSubtype = "", naarSubtype = ""): boolean {
  const t = RELATIETYPEN[code];
  if (!t || vanKlasse === BRON) return false;
  if (naarKlasse === BRON) return t.eindpunt_bron && alsKlassen(vanKlasse, vanSubtype).some(([k]) => t.van.includes(k));
  return alsKlassen(vanKlasse, vanSubtype).some(([vk, vs]) =>
    alsKlassen(naarKlasse, naarSubtype).some(([nk, ns]) => past(t, vk, nk, vs, ns)));
}

/** De typen die tussen deze twee klassen passen, in deze richting: de keuzelijst bij *Verbind met…*. */
export function typenTussen(vanKlasse: string, naarKlasse: string, vanSubtype = "", naarSubtype = ""): string[] {
  return Object.keys(RELATIETYPEN).filter((code) => toegestaan(code, vanKlasse, naarKlasse, vanSubtype, naarSubtype));
}
"""


def lees(bron: Path = BRON) -> dict:
    """De catalogus, met elk type aangevuld tot alle velden van `VELDEN`."""
    data = json.loads(bron.read_text(encoding="utf-8"))
    typen = {}
    for code, t in data["typen"].items():
        onbekend = set(t) - set(VELDEN)
        if onbekend:
            raise ValueError(f"onbekend veld bij {code}: {sorted(onbekend)}")
        typen[code] = {veld: t.get(veld, standaard) for veld, standaard in VELDEN.items()}
    return {
        "versie": hashlib.sha256(bron.read_bytes()).hexdigest()[:12],
        "typen": dict(sorted(typen.items())),
        "centrale_klassen": data["centrale_klassen"],
        "impliciet_toegestaan": data["impliciet_toegestaan"],
        "kardinaliteit": data["kardinaliteit"],
        "verbijzonderingen": data["verbijzonderingen"],
    }


def api_bron(catalogus: dict) -> str:
    def blok(naam: str, waarde, uitleg: str) -> str:
        return f"#: {uitleg}\n{naam} = " + pprint.pformat(waarde, width=110, sort_dicts=False) + "\n\n"
    return ("# Gegenereerd uit .claude/skills/wetsanalyse/relaties.json; niet handmatig bewerken.\n"
            "# Draai tools/graph-qa/scripts/genereer_jas_relaties.py (ADR-011).\n"
            '"""De catalogus van relaties tussen markeringen (deelactiviteit 2c): typen, klassenparen, drager."""\n'
            "from __future__ import annotations\n\n"
            + blok("CATALOGUS_VERSIE", catalogus["versie"], "De eerste twaalf tekens van de sha256 van de bron.")
            + blok("BRON", BRON_KLASSE, "De pseudoklasse van een eindpunt dat een hele bepaling is (soort bron, M-1-1).")
            + blok("RELATIETYPEN", catalogus["typen"], "code → type.")
            + blok("CENTRALE_KLASSEN", tuple(catalogus["centrale_klassen"]), "De klassen waaromheen een 2c-diagram staat.")
            + blok("IMPLICIET_TOEGESTAAN", tuple(catalogus["impliciet_toegestaan"]),
                   "De klassen van een impliciete partij (besluit gebruiker, 7 nov 2026).")
            + blok("VERBIJZONDERINGEN", catalogus["verbijzonderingen"],
                   "klasse → subtype → de klasse die zij verbijzondert en haar subtype daar (H2:107, M01 h.4 §12).")
            + blok("KARDINALITEIT", catalogus["kardinaliteit"], "Diagnostisch, nooit in het schrijfpad.").rstrip("\n")
            + "\n" + _API_FUNCTIES)


def frontend_bron(catalogus: dict) -> str:
    def j(waarde) -> str:
        return json.dumps(waarde, ensure_ascii=False, indent=2)
    return ("// Gegenereerd uit .claude/skills/wetsanalyse/relaties.json; niet handmatig bewerken.\n"
            "// Draai tools/graph-qa/scripts/genereer_jas_relaties.py (ADR-011).\n\n"
            "export type RelatiePaar = { van: string; naar: string; van_subtype?: string; naar_subtype?: string };\n\n"
            "export type RelatieType = {\n"
            "  leesvorm: string;\n  invers: string;\n  van: readonly string[];\n  naar: readonly string[];\n"
            "  paren: readonly RelatiePaar[];\n  drager: \"van\" | \"naar\";\n  volgorde: boolean;\n"
            "  tekstueel: boolean;\n  eindpunt_bron: boolean;\n  methodisch: boolean;\n  bron: readonly string[];\n};\n\n"
            f"export const CATALOGUS_VERSIE = {j(catalogus['versie'])};\n\n"
            "/** De pseudoklasse van een eindpunt dat een hele bepaling is (soort bron, M-1-1). */\n"
            f"export const BRON = {j(BRON_KLASSE)};\n\n"
            f"export const RELATIETYPEN: Record<string, RelatieType> = {j(catalogus['typen'])};\n\n"
            f"export const CENTRALE_KLASSEN: readonly string[] = {j(catalogus['centrale_klassen'])};\n\n"
            f"export const IMPLICIET_TOEGESTAAN: readonly string[] = {j(catalogus['impliciet_toegestaan'])};\n\n"
            "/** klasse → subtype → de klasse die zij verbijzondert en haar subtype daar (H2:107, M01 h.4 §12). */\n"
            "export const VERBIJZONDERINGEN: Record<string, Record<string, { klasse: string; subtype: string; bron: readonly string[] }>> = "
            f"{j(catalogus['verbijzonderingen'])};\n"
            + _TS_FUNCTIES)


def genereer(bron: Path = BRON) -> dict[Path, str]:
    """Doelbestand → verwachte inhoud."""
    catalogus = lees(bron)
    return {API_DOEL: api_bron(catalogus), GRAPHQA_DOEL: api_bron(catalogus), FRONTEND_DOEL: frontend_bron(catalogus)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true",
                   help="niets schrijven; exitcode 1 als een kopie niet bij de skill past")
    args = p.parse_args(argv)
    afwijkend = []
    for doel, inhoud in genereer().items():
        if args.check:
            if not doel.exists() or doel.read_text(encoding="utf-8") != inhoud:
                afwijkend.append(doel)
        else:
            doel.write_text(inhoud, encoding="utf-8")
    if afwijkend:
        for doel in afwijkend:
            print(f"{doel.relative_to(WORTEL)} loopt uit de pas met relaties.json.", file=sys.stderr)
        print("Draai: python3 tools/graph-qa/scripts/genereer_jas_relaties.py", file=sys.stderr)
        return 1
    print("relatiecatalogus " + ("komt overeen met de skill." if args.check else "bijgewerkt uit de skill."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
