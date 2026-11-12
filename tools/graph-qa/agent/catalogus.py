"""De catalogus van Lex (ADR-014), afgeleid uit de registers die er al zijn.

Per soort is er één adapter (`uit_<soort>`). Die leest het bestaande register en maakt er een `Onderdeel` van; er
komt geen tweede lijst naast. Ontbreekt er iets, zoals het doel van een specialist, dan hoort dat in het register
zelf (`Specialist.doel`), niet hier.

Of er een model aan te pas komt, wordt afgeleid, niet met de hand gezet:
- een specialist draait een open lus;
- een sjabloon is een strikte tool;
- een connector is code.

`tests/test_catalogus.py` bewaakt de volledigheid in beide richtingen.
"""
from __future__ import annotations

from functools import cache

from bronmodel.catalogus import EIGEN, Herkomst, Onderdeel, oid, versie
from bronmodel.connectors import CONNECTORS, ConnectorBeschrijving

from . import specialists
from .llm_stap import Rol
from .methodepakket import PAKKET
from .sjablonen import SJABLONEN, Sjabloon

_SKILL = ".claude/skills/wetsanalyse"
METHODE = oid("methode", "wetsanalyse")


def _eerste_zin(tekst: str) -> str:
    tekst = " ".join((tekst or "").split())
    punt = tekst.find(". ")
    return tekst if punt < 0 else tekst[: punt + 1]


# --- methode en rollen ---------------------------------------------------------------------------------------------

def _methode_herkomst(codes: tuple[str, ...] = ()) -> Herkomst:
    lex = PAKKET["lex"]
    return Herkomst(bron=lex["herkomst"], licentie=lex["licentie"], letterlijk=lex["letterlijk"] == "ja",
                    verwijzing=codes)


def uit_methode() -> list[Onderdeel]:
    lex = PAKKET["lex"]
    codes = tuple(sorted({c for s in PAKKET["secties"].values() for c in s["bronnen"]}))
    return [Onderdeel(
        id=METHODE, soort="methode", label=lex["label"], doel=lex["beschrijving"], model="geen",
        herkomst=_methode_herkomst(codes),
        bestand=tuple(f"{_SKILL}/{p}" for p in sorted(PAKKET["bronbestanden"])),
        versie=PAKKET["sha256"][:12], uitvoer="methodetekst per rol",
        tests=("tools/graph-qa/tests/test_methodepakket.py", "tools/graph-qa/tests/test_methode_drift.py"),
        bewerkbaar=tuple(sorted(PAKKET["secties"])),
        inhoud={"methode_versie": PAKKET["versie"], "rollen": PAKKET["rollen"],
                "secties": {k: {"bestand": s["bestand"], "bronnen": s["bronnen"]} for k, s in PAKKET["secties"].items()}},
    )]


def _aanroepers(rol: str) -> tuple[str, ...]:
    """Wie de methodetekst van deze rol krijgt: modelaanroepen uit `llm_stap.Rol` en specialisten."""
    namen = {r.naam for r in Rol if r.methoderol == rol}
    namen |= {n for n in specialists.SPECIALISTS if specialists.methoderol(n) == rol}
    return tuple(sorted(namen))


def uit_rollen() -> list[Onderdeel]:
    uit: list[Onderdeel] = []
    for rol, ids in sorted(PAKKET["rollen"].items()):
        secties = {k: PAKKET["secties"][k] for k in ids}
        codes = tuple(sorted({c for s in secties.values() for c in s["bronnen"]}))
        agentisch = any(specialists.methoderol(n) == rol for n in specialists.SPECIALISTS)
        uit.append(Onderdeel(
            id=oid("rol", rol), soort="rol", label=f"Methoderol {rol}",
            doel=f"De methodetekst die {', '.join(_aanroepers(rol)) or 'geen aanroeper'} krijgt: "
                 f"de secties {', '.join(ids)}.",
            model="agent" if agentisch else "strict", herkomst=_methode_herkomst(codes),
            bestand=tuple(sorted({f"{_SKILL}/{s['bestand']}" for s in secties.values()} | {f"{_SKILL}/agentrollen.json"})),
            versie=versie(*(s["sha256"] for s in secties.values())), ingang=_aanroepers(rol),
            context="vóór de systeemprompt, in het stabiele deel (cache-prefix)", uitvoer="systeemprompt",
            tests=("tools/graph-qa/tests/test_methoderollen.py",), hangt_af_van=(METHODE,), bewerkbaar=tuple(ids),
            inhoud={"secties": [{"id": k, "bronnen": s["bronnen"], "sha256": s["sha256"], "tekst": s["tekst"]}
                                for k, s in secties.items()]},
        ))
    return uit


# --- specialisten ----------------------------------------------------------------------------------------------------

def uit_specialisten() -> list[Onderdeel]:
    uit: list[Onderdeel] = []
    for naam, spec in specialists.SPECIALISTS.items():
        tools = ("alle graaftools",) if spec.tools is None else tuple(sorted(spec.tools))
        uit.append(Onderdeel(
            id=oid("specialist", naam), soort="specialist", label=naam.replace("_", " ").capitalize(),
            doel=spec.doel, model="agent", herkomst=EIGEN, bestand=("tools/graph-qa/agent/specialists.py",),
            versie=versie(spec.system, tools, sorted(spec.sjablonen)), tools=tools,
            uitvoer=", ".join(sorted(spec.sjablonen)) or "doel-JSON voor de annotatieroute",
            twijfel="leemte of doorvragen; een citaat dat niet letterlijk in de opgehaalde tekst staat, valt weg (grounding)",
            tests=("tools/graph-qa/tests/test_specialists.py",),
            hangt_af_van=(oid("rol", specialists.methoderol(naam)), *(oid("sjabloon", s) for s in sorted(spec.sjablonen)),
                          *(oid("connector", c.naam) for c in CONNECTORS.values() if naam in c.specialisten)),
            inhoud={"systeemtekst": spec.system},
        ))
    return uit


# --- sjablonen -------------------------------------------------------------------------------------------------------

def _sjabloon_bestand(s: Sjabloon) -> str:
    return "tools/graph-qa/" + s.vul.__module__.replace(".", "/") + ".py"


def uit_sjablonen() -> list[Onderdeel]:
    uit: list[Onderdeel] = []
    for naam, s in SJABLONEN.items():
        velden = s.schema.get("input_schema", {}).get("properties", {})
        uit.append(Onderdeel(
            id=oid("sjabloon", naam), soort="sjabloon", label=naam.removeprefix("antwoord_").capitalize(),
            doel=_eerste_zin(s.schema.get("description", "")), model="strict", herkomst=EIGEN,
            bestand=(_sjabloon_bestand(s), "packages/bronmodel/bronmodel/antwoord.py"),
            versie=versie(s.schema), ingang=(naam,), tools=(naam,),
            context="de toolresultaten van deze beurt (feiten komen uit de rijen, niet uit het model)",
            uitvoer="vaste antwoordblokken (bronmodel.antwoord)",
            twijfel="onvulbaar gaat als fout terug naar het model; vrije tekst blijft een geldig antwoord (sjabloon_gemist)",
            tests=("tools/graph-qa/tests/test_sjablonen.py",),
            inhoud={"beschrijving": s.schema.get("description", ""),
                    "velden": {k: v.get("description", "") for k, v in velden.items()}},
        ))
    return uit


# --- connectors ------------------------------------------------------------------------------------------------------

def _connector(c: ConnectorBeschrijving) -> Onderdeel:
    return Onderdeel(
        id=oid("connector", c.naam), soort="connector", label=c.label, doel=_eerste_zin(c.beheer), model="geen",
        herkomst=Herkomst(bron=f"{c.label}: de stukken komen live van de dienst; de koppeling is eigen werk",
                          licentie="repo"),
        bestand=("packages/bronmodel/bronmodel/connectors.py", "tools/graph-qa/agent/tools/connectortools.py"),
        versie=versie(c.naam, c.dekt, sorted(c.tools), c.grenzen), ingang=tuple(sorted(c.tools)),
        tools=tuple(sorted(c.tools)), uitvoer=f"het blok extern ({c.brontype})", twijfel=c.grenzen,
        tests=("tools/graph-qa/tests/test_connectorbeschrijving.py",),
        hangt_af_van=tuple(oid("specialist", s) for s in sorted(c.specialisten)), straat=c.env,
        inhoud={"dekt": c.dekt, "beheer": c.beheer, "rol_in_antwoord": c.rol_in_antwoord, "levert": list(c.levert),
                "niet_in_tekst": list(c.niet_in_tekst), "voorbeeldvragen": list(c.voorbeeldvragen)},
    )


def uit_connectors() -> list[Onderdeel]:
    return [_connector(c) for c in CONNECTORS.values()]


# --- de catalogus ----------------------------------------------------------------------------------------------------

ADAPTERS = (uit_methode, uit_rollen, uit_specialisten, uit_sjablonen, uit_connectors)


@cache
def catalogus() -> tuple[Onderdeel, ...]:
    """Alle onderdelen, op soort en naam. Een id dat twee keer voorkomt, is een fout."""
    alle = [o for adapter in ADAPTERS for o in adapter()]
    ids = [o.id for o in alle]
    dubbel = {i for i in ids if ids.count(i) > 1}
    if dubbel:
        raise ValueError(f"dubbele onderdelen in de catalogus: {sorted(dubbel)}")
    return tuple(alle)


def onderdeel(id_: str) -> Onderdeel | None:
    return next((o for o in catalogus() if o.id == id_), None)
