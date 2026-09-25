"""Geversioneerde referentieset: schema, manifest en validator (onderzoek-empirische-validatie §10.4, V1).

Eén map per versie, `docs/wetsanalyse/referentieset/v<N>/`, met `cases.json` en `manifest.json`.
Het manifest draagt een hash over alle casussen; die hash is de identiteit van de versie. Drie regels:

1. **`adjudicated`/`gold` alleen met een volledig record.** Per casus: beide annotatoren, de
   adjudicator, datum en protocolversie, een beoordeelde `source_status`; per gold-element een
   `annotation_status`, herkenningsvraag, H2-verwijzing en het adjudicatiebesluit. Die status kan
   bovendien alleen in een **bevroren** versie staan.
2. **Een bevroren versie verandert niet.** Wie een fout in gold vindt, maakt `v<N+1>` met een
   changelog per gid; een stille correctie laat de hash afwijken en de test falen.
3. **Wat nog niet beoordeeld is, is leeg** (`None`), niet ingevuld. De provisional casussen dragen
   de nieuwe velden dus zonder waarde: een `source_status: valid` zonder broncontrole zou precies de
   schijnzekerheid zijn die dit schema moet voorkomen.

Coverage-status (`present`/`missed`/`superfluous`) hoort hier niet in: dat is een eigenschap van een
run tegen de referentie, en het harnas leidt hem af.

    python -m eval.referentieset --check          # valideer de actuele versie
    python -m eval.referentieset --bijwerken      # herbereken de hash van een niet-bevroren versie
    python -m eval.referentieset --dekking        # dekkingsmatrix §10.3: wat ontbreekt nog
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from agent.jas_klassen import GELDIGE_JAS_KLASSEN, JAS_KLASSEN, JAS_KLASSEN_VOLGORDE
from agent.jas_pipeline.profielen import referentieset_map
from agent.jas_pipeline.subtype import REGELS as SUBTYPES
from eval.metrieken import GEVALIDEERD, STATUSSEN

ACTUELE_VERSIE = "v1"

SPLITS = ("ontwikkeling", "held-out")
SOURCE_STATUS = ("valid", "ambiguous", "unusable")
TEKSTSOORTEN = ("wet", "amvb", "ministeriele_regeling", "beleidsregel", "circulaire")
ANNOTATION_STATUS = ("correct", "incorrect", "debatable")
RELATIESOORTEN = ("norm", "drager", "operand", "afleiding", "vergelijking", "tijdsanker")
# §11 stap 3 en 4: hoe A en B verschilden, en wat de adjudicator besloot. "Geen van beide" levert
# geen gold-element op; zo'n besluit staat hooguit als negatief element in de casus.
VERSCHILLEN = ("gelijk", "klasse", "span", "alleen_a", "alleen_b")
BESLUITEN = ("gelijk", "kies_a", "kies_b", "beide", "debatable")

# De dekkingsmatrix van §10.3, als vaste woordenlijst: een constructie die er niet in staat, is een
# tikfout of een nieuwe rij – en een nieuwe rij hoort eerst in het ontwerpdocument.
CONSTRUCTIES = (
    "actief", "passief", "naamwoordelijk_gezegde", "lange_samengestelde_zin", "opsomming",
    "relatieve_bijzin", "voorwaarde", "tenzij_uitzondering", "verwijzing", "termijn",
    "bedrag_percentage", "vergelijking", "berekening", "afleiding", "delegatie", "definitie",
    "subject_niet_rechtssubject", "object_niet_rechtsobject", "nested_spans",
    "meerdere_functies_zelfde_span", "als_voorwaarde", "als_vergelijking", "als_hoedanigheid",
    "of_en_exclusief_inclusief", "dan_wel", "tijdseenheid_niet_temporeel", "znw_geen_rechtsobject",
)

CASUS_VERPLICHT = ("id", "familie", "split", "bron_id", "vindplaats", "versie", "tekst", "tekst_sha256",
                   "source_status", "tekstsoort", "constructies", "referentie_status", "gold", "negatief")
# De leesbare dossiervelden (render_jas_referentieset.py) en het casusbrede adjudicatierecord.
CASUS_OPTIONEEL = ("grammatica", "samenhang", "scenario", "reviewvraag", "adjudicatie")
GOLD_VELDEN = ("gid", "start", "eind", "tekst", "klasse", "subtype", "context", "motivatie",
               "herkenningsvraag", "h2_ref", "annotation_status", "relaties", "adjudicatie")
NEGATIEF_VELDEN = ("start", "eind", "tekst", "waarom_geen_element")
MANIFEST_VELDEN = ("referentie_versie", "protocolversie", "bevroren_op", "referentie_status", "sha256",
                   "voorganger", "changelog", "toelichting")
CHANGELOG_VELDEN = ("casus", "gid", "reden", "oud", "nieuw", "datum", "adjudicator")
CASUS_ADJUDICATIE = ("annotator_a", "annotator_b", "adjudicator", "datum", "protocolversie")
ELEMENT_ADJUDICATIE = ("verschil", "besluit")

_H2 = re.compile(r"^H2:\d+$")
_WOORD = re.compile(r"\w")
_VRAAG = {k.naam: k.vraag for k in JAS_KLASSEN}


class ReferentieFout(ValueError):
    pass


def versiemap(versie: str = ACTUELE_VERSIE) -> Path:
    return referentieset_map() / versie


def laad(versie: str = ACTUELE_VERSIE) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Casussen en manifest van een versie, ongevalideerd."""
    m = versiemap(versie)
    return (json.loads((m / "cases.json").read_text(encoding="utf-8")),
            json.loads((m / "manifest.json").read_text(encoding="utf-8")))


def casussen(versie: str = ACTUELE_VERSIE) -> list[dict[str, Any]]:
    """De casussen van een versie, na validatie tegen schema en manifest."""
    cases, manifest = laad(versie)
    valideer(cases, manifest)
    return cases


def sethash(cases: list[dict[str, Any]]) -> str:
    """SHA-256 over de canonieke JSON: opmaak doet er niet toe, inhoud en volgorde wel."""
    canoniek = json.dumps(cases, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canoniek.encode("utf-8")).hexdigest()


# --- validatie ---------------------------------------------------------------------------------

def _velden(waar: str, d: dict[str, Any], verplicht: tuple[str, ...], optioneel: tuple[str, ...] = ()) -> None:
    ontbreekt = [v for v in verplicht if v not in d]
    onbekend = [v for v in d if v not in verplicht and v not in optioneel]
    if ontbreekt or onbekend:
        raise ReferentieFout(f"{waar}: ontbreekt {ontbreekt or '-'}, onbekend {onbekend or '-'}")


def _keuze(waar: str, waarde: Any, toegestaan: tuple[str, ...], leeg_mag: bool = False) -> None:
    if waarde is None and leeg_mag:
        return
    if waarde not in toegestaan:
        raise ReferentieFout(f"{waar}: {waarde!r} niet in {toegestaan}")


def _span(waar: str, tekst: str, e: dict[str, Any]) -> None:
    """Letterlijk en op woordgrenzen: een offset midden in een woord rekent een juiste keten af."""
    s, t = e["start"], e["eind"]
    if not (isinstance(s, int) and isinstance(t, int) and 0 <= s < t <= len(tekst)):
        raise ReferentieFout(f"{waar}: ongeldige span {s}–{t}")
    if tekst[s:t] != e["tekst"]:
        raise ReferentieFout(f"{waar}: tekst[{s}:{t}] = {tekst[s:t]!r}, verwacht {e['tekst']!r}")
    if (s > 0 and _WOORD.match(tekst[s - 1]) and _WOORD.match(tekst[s])) or \
       (t < len(tekst) and _WOORD.match(tekst[t]) and _WOORD.match(tekst[t - 1])):
        raise ReferentieFout(f"{waar}: span {s}–{t} ligt niet op woordgrenzen")


def _gevuld(waar: str, d: dict[str, Any], velden: tuple[str, ...]) -> None:
    leeg = [v for v in velden if d.get(v) in (None, "", [])]
    if leeg:
        raise ReferentieFout(f"{waar}: adjudicated zonder {', '.join(leeg)}")


def valideer_casus(c: dict[str, Any]) -> str:
    """Schema §10.4 voor één casus; geeft de referentiestatus terug."""
    waar = str(c.get("id", "?"))
    _velden(waar, c, CASUS_VERPLICHT, CASUS_OPTIONEEL)
    _keuze(f"{waar}.split", c["split"], SPLITS)
    _keuze(f"{waar}.referentie_status", c["referentie_status"], STATUSSEN)
    _keuze(f"{waar}.source_status", c["source_status"], SOURCE_STATUS, leeg_mag=True)
    _keuze(f"{waar}.tekstsoort", c["tekstsoort"], TEKSTSOORTEN)
    for k in c["constructies"]:
        _keuze(f"{waar}.constructies", k, CONSTRUCTIES)
    if hashlib.sha256(c["tekst"].encode("utf-8")).hexdigest() != c["tekst_sha256"]:
        raise ReferentieFout(f"{waar}: tekst_sha256 klopt niet met de tekst")

    gids = [g.get("gid") for g in c["gold"]]
    if len(gids) != len(set(gids)):
        raise ReferentieFout(f"{waar}: dubbele gid")
    for g in c["gold"]:
        gw = f"{waar}/{g.get('gid', '?')}"
        _velden(gw, g, GOLD_VELDEN)
        _span(gw, c["tekst"], g)
        _keuze(f"{gw}.klasse", g["klasse"], tuple(GELDIGE_JAS_KLASSEN))
        _keuze(f"{gw}.annotation_status", g["annotation_status"], ANNOTATION_STATUS, leeg_mag=True)
        if g["subtype"] is not None:
            _keuze(f"{gw}.subtype", g["subtype"], tuple(s for s, _ in SUBTYPES.get(g["klasse"], ())))
        if g["h2_ref"] is not None and not _H2.match(g["h2_ref"]):
            raise ReferentieFout(f"{gw}.h2_ref: {g['h2_ref']!r} is geen H2:NN")
        if g["herkenningsvraag"] is not None and g["herkenningsvraag"] not in _VRAAG[g["klasse"]]:
            raise ReferentieFout(f"{gw}.herkenningsvraag staat niet letterlijk in het profiel van {g['klasse']}")
        for r in g["relaties"]:
            _velden(f"{gw}.relaties", r, ("soort", "naar_gid"))
            _keuze(f"{gw}.relaties.soort", r["soort"], RELATIESOORTEN)
            if r["naar_gid"] not in gids:
                raise ReferentieFout(f"{gw}.relaties: onbekende gid {r['naar_gid']!r}")
        if g["adjudicatie"] is not None:
            _velden(f"{gw}.adjudicatie", g["adjudicatie"], ELEMENT_ADJUDICATIE)
            _keuze(f"{gw}.adjudicatie.verschil", g["adjudicatie"]["verschil"], VERSCHILLEN)
            _keuze(f"{gw}.adjudicatie.besluit", g["adjudicatie"]["besluit"], BESLUITEN)
            if (g["adjudicatie"]["besluit"] == "debatable") != (g["annotation_status"] == "debatable"):
                raise ReferentieFout(f"{gw}: besluit debatable en annotation_status debatable horen samen")
    for i, n in enumerate(c["negatief"]):
        nw = f"{waar}/negatief[{i}]"
        _velden(nw, n, NEGATIEF_VELDEN)
        _span(nw, c["tekst"], n)
        if not n["waarom_geen_element"]:
            raise ReferentieFout(f"{nw}: zonder waarom_geen_element")

    if c["referentie_status"] in GEVALIDEERD:
        _gevuld(waar, c, ("source_status", "constructies", "adjudicatie"))
        _velden(f"{waar}.adjudicatie", c["adjudicatie"], CASUS_ADJUDICATIE)
        _gevuld(f"{waar}.adjudicatie", c["adjudicatie"], CASUS_ADJUDICATIE)
        if c["source_status"] == "unusable":
            raise ReferentieFout(f"{waar}: unusable bron kan geen {c['referentie_status']} referentie zijn")
        for g in c["gold"]:
            _gevuld(f"{waar}/{g['gid']}", g, ("motivatie", "herkenningsvraag", "h2_ref", "annotation_status",
                                              "adjudicatie"))
    return c["referentie_status"]


def valideer(cases: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    """Hele versie: elke casus, en het manifest dat bij precies deze casussen hoort."""
    _velden("manifest", manifest, MANIFEST_VELDEN)
    statussen = {c.get("id"): valideer_casus(c) for c in cases}
    if len(statussen) != len(cases):
        raise ReferentieFout("dubbel casus-id")
    if manifest["referentie_status"] != statussen:
        raise ReferentieFout("manifest.referentie_status wijkt af van de casussen")
    if manifest["sha256"] != sethash(cases):
        raise ReferentieFout("manifest-drift: de casussen zijn gewijzigd zonder nieuwe hash"
                             + (" – en deze versie is bevroren: maak een nieuwe versie" if manifest["bevroren_op"] else ""))
    gevalideerd = [i for i, s in statussen.items() if s in GEVALIDEERD]
    if gevalideerd and not (manifest["bevroren_op"] and manifest["protocolversie"]):
        raise ReferentieFout(f"adjudicated casussen in een niet-bevroren versie: {', '.join(gevalideerd)}")
    for i, regel in enumerate(manifest["changelog"]):
        _velden(f"manifest.changelog[{i}]", regel, CHANGELOG_VELDEN)
    if manifest["changelog"] and not manifest["voorganger"]:
        raise ReferentieFout("changelog zonder voorganger")


# --- dekkingsmatrix §10.3 -----------------------------------------------------------------------

def dekkingsgaten(cases: list[dict[str, Any]], minimum: int = 2) -> dict[str, list[str]]:
    """Rijen van de matrix met minder dan `minimum` voorkomens in minder dan `minimum` families.

    Klassen tellen gold-elementen; constructies tellen casussen (ze staan op casusniveau). Een lege
    uitkomst is een voorwaarde om te bevriezen voor V7, geen bewijs van kwaliteit.
    """
    klassen: dict[str, list[str]] = defaultdict(list)
    constructies: dict[str, list[str]] = defaultdict(list)
    for c in cases:
        for g in c["gold"]:
            klassen[g["klasse"]].append(c["familie"])
        for k in c["constructies"]:
            constructies[k].append(c["familie"])

    def tekort(rij: list[str]) -> bool:
        return len(rij) < minimum or len(set(rij)) < minimum

    return {"klassen": [k for k in JAS_KLASSEN_VOLGORDE if tekort(klassen[k])],
            "constructies": [k for k in CONSTRUCTIES if tekort(constructies[k])]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--versie", default=ACTUELE_VERSIE)
    groep = ap.add_mutually_exclusive_group(required=True)
    groep.add_argument("--check", action="store_true")
    groep.add_argument("--bijwerken", action="store_true")
    groep.add_argument("--dekking", action="store_true")
    args = ap.parse_args()
    cases, manifest = laad(args.versie)
    if args.bijwerken:
        if manifest["bevroren_op"]:
            print(f"{args.versie} is bevroren op {manifest['bevroren_op']}: maak een nieuwe versie.")
            return 1
        manifest["referentie_status"] = {c["id"]: c["referentie_status"] for c in cases}
        manifest["sha256"] = sethash(cases)
        (versiemap(args.versie) / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    valideer(cases, manifest)
    if args.dekking:
        for rij, gaten in dekkingsgaten(cases).items():
            print(f"{rij}: {', '.join(gaten) or 'compleet'}")
        return 0
    print(f"{args.versie}: {len(cases)} casussen, sha256 {manifest['sha256'][:12]}, "
          f"{'bevroren ' + manifest['bevroren_op'] if manifest['bevroren_op'] else 'niet bevroren'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
