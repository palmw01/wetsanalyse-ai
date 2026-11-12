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

import re
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from bronmodel.catalogus import EIGEN, Herkomst, Onderdeel, Stap, oid, versie, zwaarste
from bronmodel.connectors import CONNECTORS, ConnectorBeschrijving

from . import bronnen_vinden, bronselectie, specialists, werkgebied_intake
from .agents.register import AGENTS, NAAM
from .begrippen_pipeline import keten as begrippenketen
from .jas_pipeline import keten as annotatieketen
from .llm_stap import Rol
from .models import ACTIE_TAAK, BRONSELECTIE_ACTIES, INTAKE_ACTIES, REGIE_ACTIES
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
        uit.append(Onderdeel(
            id=oid("rol", rol), soort="rol", label=f"Methoderol {rol}",
            doel=f"De methodetekst die {', '.join(_aanroepers(rol)) or 'geen aanroeper'} krijgt: "
                 f"de secties {', '.join(ids)}.",
            model="geen", herkomst=_methode_herkomst(codes),
            bestand=tuple(sorted({f"{_SKILL}/{s['bestand']}" for s in secties.values()} | {f"{_SKILL}/agentrollen.json"})),
            versie=versie(*(s["sha256"] for s in secties.values())), ingang=_aanroepers(rol),
            context="vóór de systeemprompt, in het stabiele deel (cache-prefix)", uitvoer="systeemprompt",
            tests=("tools/graph-qa/tests/test_methoderollen.py",), deel_van=METHODE, bewerkbaar=tuple(ids),
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
                          *(oid("connector", c.naam) for c in CONNECTORS.values() if naam in c.specialisten),
                          *(oid("tool", t) for t in sorted(_tools_van(spec))), *ANTWOORD_CONTROLES),
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
        hangt_af_van=tuple(oid("tool", t) for t in sorted(c.tools)), straat=c.env,
        inhoud={"dekt": c.dekt, "beheer": c.beheer, "rol_in_antwoord": c.rol_in_antwoord, "levert": list(c.levert),
                "niet_in_tekst": list(c.niet_in_tekst), "voorbeeldvragen": list(c.voorbeeldvragen)},
    )


def uit_connectors() -> list[Onderdeel]:
    return [_connector(c) for c in CONNECTORS.values()]


#: De vaste keten die een agent gebruikt (een agent gebruikt workflows, nooit andersom; ADR-014 §7).
AGENT_WORKFLOWS: dict[str, tuple[str, ...]] = {
    "annotatie": ("workflow/annotatieketen",),
    "begrippen": ("workflow/begrippenketen",),
}
#: De rol van `llm_stap` die een modelstap van de intake draagt.
_INTAKE_ROL = {"naam": "intake", "aanleiding": "intake", "doel": "intake", "analysevraag": "intake",
               "deelvragen": "deelvragen_voorstel"}


# --- agents ----------------------------------------------------------------------------------------------------------

def uit_agents() -> list[Onderdeel]:
    uit: list[Onderdeel] = []
    for naam, mod in AGENTS.items():
        taken = [{"taak": t.value, "model": t in mod.MODEL_TAKEN,
                  "acties": sorted(a for a, (ag, tk) in ACTIE_TAAK.items() if ag == naam and tk == t.value)}
                 for t in mod.Taak]
        uit.append(Onderdeel(
            id=oid("agent", naam), soort="agent", label=NAAM[naam].capitalize(), doel=mod.DOEL,
            model="strict" if mod.MODEL_TAKEN else "geen", herkomst=EIGEN,
            bestand=(f"tools/graph-qa/agent/agents/{naam}.py", "tools/graph-qa/agent/agents/register.py"),
            versie=versie(taken), ingang=tuple(sorted({a for t in taken for a in t["acties"]})),
            context="het werkgebied van het gesprek en het object van Vraag Lex (`agents/register.parameters`)",
            uitvoer="een artefact, een bevestiging of een vraagkaart (`agents.Uitkomst`); altijd een voorstel",
            twijfel="geweigerd met een reden, of een vraagkaart; nooit een besluit",
            tests=("tools/graph-qa/tests/test_agents.py", "tools/graph-qa/tests/test_agent_contracten.py"),
            hangt_af_van=AGENT_WORKFLOWS.get(naam, ()),
            inhoud={"taken": taken},
        ))
    return uit


# --- regelsets: elke YAML in een keten -------------------------------------------------------------------------------

_AGENT = Path(__file__).resolve().parent
#: Per map met regels: de keten, en de test die de regels draait. Een YAML in een map die hier niet staat, maakt
#: `tests/test_catalogus.py` rood.
REGELMAPPEN: dict[str, tuple[str, str]] = {
    "jas_pipeline/detectoren/regels": ("jas", "tools/graph-qa/tests/test_detectoren.py"),
    "jas_pipeline/profielen": ("jas", "tools/graph-qa/tests/test_detectieprofielen.py"),
    "jas_pipeline": ("jas", "tools/graph-qa/tests/test_verklaringen.py"),
    "begrippen_pipeline/regels": ("begrippen", "tools/graph-qa/tests/test_begrippen_patronen.py"),
    "begrippen_pipeline/betekenisregels": ("begrippen", "tools/graph-qa/tests/test_betekenis.py"),
    "begrippen_pipeline": ("begrippen", "tools/graph-qa/tests/test_begrippen_signalen.py"),
}
_DETECTOR = "jas_pipeline/detectoren/regels"


def regelbestanden() -> list[Path]:
    return sorted(p for p in _AGENT.rglob("*.yaml") if "__pycache__" not in p.parts)


def _kop(tekst: str) -> str:
    """De eerste alinea van het commentaar bovenaan: daar zegt elk regelbestand wat het is."""
    regels: list[str] = []
    for r in tekst.splitlines():
        if not r.startswith("#"):
            break
        r = r.lstrip("#").strip()
        if not r:
            if regels:
                break
            continue
        regels.append(r)
    return " ".join(regels)


def _regels(data: Any) -> list[dict[str, Any]]:
    """Wat de werkplek per regel toont: id, code, klassen of hypothese, bron, versie en de voorbeeldzinnen."""
    if not isinstance(data, list):
        return []
    uit = []
    for d in data:
        if not isinstance(d, dict) or "id" not in d:
            continue
        tests = d.get("tests") or {}
        uit.append({k: d[k] for k in ("id", "code", "klassen", "hypothese", "masker", "bron", "versie", "bewijs") if k in d}
                   | {"voorbeelden": {soort: [t.get("tekst", "") for t in (tests.get(soort) or [])][:2]
                                      for soort in ("positief", "negatief") if tests.get(soort)}})
    return uit


def _regelset(pad: Path, map_: str) -> Onderdeel:
    keten, test = REGELMAPPEN[map_]
    tekst = pad.read_text(encoding="utf-8")
    data = yaml.safe_load(tekst)
    regels = _regels(data)
    stam = pad.stem.lstrip("_")
    naam = f"{keten}.detector.{stam}" if map_ == _DETECTOR and not pad.stem.startswith("_") else f"{keten}.{stam}"
    bronnen = tuple(sorted({str(r["bron"]) for r in regels if r.get("bron")}))
    rel = pad.relative_to(_AGENT.parent).as_posix()
    return Onderdeel(
        id=oid("regelset", naam), soort="regelset", label=naam, doel=_kop(tekst) or f"Regels in {pad.name}.",
        model="geen", herkomst=Herkomst(bron="eigen regels, met per regel de bron", licentie="repo", verwijzing=bronnen),
        bestand=(f"tools/graph-qa/{rel}",), versie=versie(tekst), tests=(test,),
        uitvoer="bewijscodes met een verklaring" if regels else "",
        inhoud={"regels": regels} if regels else {"sleutels": sorted(data) if isinstance(data, dict) else []},
    )


def _profielen(paden: list[Path]) -> Onderdeel:
    teksten = [p.read_text(encoding="utf-8") for p in paden]
    profielen = []
    for p, t in zip(paden, teksten):
        d = yaml.safe_load(t)
        profielen.append({"bestand": p.name, "klasse": d.get("jas_class"), "bron": d.get("bron"),
                          "regels": [r.get("id") for r in d.get("candidate_rules") or [] if isinstance(r, dict)]})
    return Onderdeel(
        id=oid("regelset", "jas.profielen"), soort="regelset", label="jas.profielen",
        doel="Een detectieprofiel per JAS-klasse: signalen, verwisselbare klassen, negatieve patronen en welke "
             "detectorregels de klasse dragen. De officiële tekst komt uit H2-JAS, niet uit het profiel.",
        model="geen", herkomst=Herkomst(bron="H2-JAS (BZK) via H2:NN-verwijzingen; eigen profielen", licentie="repo",
                                        verwijzing=tuple(sorted({str(v) for x in profielen for v in (x["bron"] or {}).values()}))),
        bestand=("tools/graph-qa/agent/jas_pipeline/profielen/",), versie=versie(*teksten),
        tests=(REGELMAPPEN["jas_pipeline/profielen"][1],), inhoud={"profielen": profielen},
    )


def uit_regelsets() -> list[Onderdeel]:
    uit: list[Onderdeel] = []
    profielen: list[Path] = []
    for pad in regelbestanden():
        map_ = pad.parent.relative_to(_AGENT).as_posix()
        if map_ not in REGELMAPPEN:
            raise ValueError(f"{pad}: een regelbestand in een map die de catalogus niet kent (REGELMAPPEN)")
        if map_ == "jas_pipeline/profielen":
            profielen.append(pad)
            continue
        uit.append(_regelset(pad, map_))
    if profielen:
        uit.append(_profielen(profielen))
    return uit


# --- workflows: de ketens met hun stappen ----------------------------------------------------------------------------

def _wf(naam: str, label: str, doel: str, laag: str, stappen: tuple[Stap, ...], *, bestand: tuple[str, ...],
        tests: tuple[str, ...], ingang: tuple[str, ...] = (), hangt_af_van: tuple[str, ...] = (),
        uitvoer: str = "", twijfel: str = "", straat: str | None = None) -> Onderdeel:
    return Onderdeel(
        id=oid("workflow", naam), soort="workflow", label=label, doel=doel, laag=laag,  # type: ignore[arg-type]
        model=zwaarste([s.model for s in stappen]), herkomst=EIGEN, bestand=bestand,
        versie=versie([(s.naam, s.model, s.onderdeel) for s in stappen]), stappen=stappen, ingang=ingang,
        hangt_af_van=tuple(dict.fromkeys((*hangt_af_van, *(s.onderdeel for s in stappen if s.onderdeel)))),
        uitvoer=uitvoer, twijfel=twijfel, tests=tests, straat=straat,
        inhoud={"stappen": [{"naam": s.naam, "model": s.model, "onderdeel": s.onderdeel} for s in stappen]},
    )


def uit_workflows() -> list[Onderdeel]:
    detectoren = tuple(o.id for o in uit_regelsets() if o.naam.startswith("jas.detector."))
    return [
        _wf("annotatieketen", "Annotatieketen (ADR-001)",
            "Markeert en classificeert de formuleringen van één bepaling in JAS-klassen: detectoren en vaste "
            "besluiten eerst, een kleine classifier en een gerichte reviewer alleen waar dat nodig is.",
            "taakagent", annotatieketen.FASEN,
            bestand=("tools/graph-qa/agent/jas_pipeline/keten.py", "docs/architectuur/annotatieketen.md"),
            tests=("tools/graph-qa/tests/test_detectoren.py", "tools/graph-qa/tests/test_provenance_element.py"),
            ingang=("annoteer",), hangt_af_van=(*detectoren, "regelset/jas.profielen"),
            uitvoer="markeringen met ankers, trace en aandachtniveau; het beslisregister",
            twijfel="geel met alternatieven voor de jurist; nooit automatisch rood", ),
        _wf("begrippenketen", "Begrippenketen (ADR-004)",
            "Stelt voor welke geannoteerde formuleringen één begrip aanduiden en welke in een relatie staan, "
            "zonder model; het meedenken bij twijfel is een aparte taak van de begrippen-agent.",
            "taakagent", begrippenketen.FASEN,
            bestand=("tools/graph-qa/agent/begrippen_pipeline/keten.py",),
            tests=("tools/graph-qa/tests/test_begrippen_patronen.py",),
            hangt_af_van=("regelset/begrippen.berekening", "regelset/begrippen.verklaringen"),
            uitvoer="betekenisgroepen, relaties en vragen (het begrippenartefact)",
            twijfel="een vraag aan de analist, of geel; sterk tegenbewijs wint altijd"),
        _wf("bronnen_vinden", "Bronnen vinden",
            "Zoekt zonder model bepalingen die bij een werkgebied kunnen horen, per methode met een plafond; "
            "wat er gevonden is, beslist de analist in de bronselectie.",
            "workflow", tuple(Stap(m, "geen") for m in bronnen_vinden.METHODEN),
            bestand=("tools/graph-qa/agent/bronnen_vinden.py", "tools/graph-qa/agent/zoekvragen.py",
                     ".claude/skills/wetsanalyse/references/zoekvragen-bronselectie.md"),
            tests=("tools/graph-qa/tests/test_bronnen_vinden.py", "tools/graph-qa/tests/test_zoekvragen.py"),
            uitvoer="kandidaten per methode met hun bewijs",
            twijfel="een methode die faalt wordt `volledig: false`; falen ze allemaal, dan een fout"),
        _wf("bronselectie", "Bronselectie per deelvraag (spoor J)",
            "Werkt de deelvragen één voor één af met vraagkaarten: kernbepalingen, wat eraan hangt, afronden; "
            "de stand staat bij de api.",
            "workflow", tuple(Stap(s, "geen") for s in bronselectie.KAARTSTAPPEN),
            bestand=("tools/graph-qa/agent/bronselectie.py", "docs/architectuur/bronselectie-per-deelvraag.md"),
            tests=("tools/graph-qa/tests/test_bronselectie.py",), ingang=BRONSELECTIE_ACTIES,
            hangt_af_van=("workflow/bronnen_vinden",), uitvoer="vraagkaarten en het bronselectie-artefact",
            twijfel="de analist beslist in het paneel; een 412 toont de stand van nu"),
        _wf("werkgebied_intake", "Werkgebied samenstellen (activiteit 1)",
            "Stelt met vraagkaarten in de volgorde van de methode een werkgebied samen of vult zijn dossier aan; "
            "het model doet alleen voorstellen, de volgorde is een stapmachine.",
            "workflow", tuple(Stap(s, "strict", rol=_INTAKE_ROL[s]) if s in werkgebied_intake.MODEL_STAPPEN else Stap(s, "geen")
                              for s in werkgebied_intake.KAARTSTAPPEN),
            bestand=("tools/graph-qa/agent/werkgebied_intake.py",),
            tests=("tools/graph-qa/tests/test_werkgebied_intake.py",), ingang=INTAKE_ACTIES,
            uitvoer="vraagkaarten en het werkgebiedartefact", twijfel="overslaan kan; een praktijkvoorbeeld verzint Lex niet"),
        _wf("regie", "Regie per deelvraag (ADR-012)",
            "Verdeelt het werk in een werkgebied over deelgesprekken, na een bevestiging; neemt zelf geen besluit.",
            "workflow", (Stap("plan", "geen"), Stap("bevestiging door de jurist", "geen"),
                         Stap("kindgesprekken", "geen", "workflow/bronselectie"), Stap("bundel", "geen")),
            bestand=("tools/graph-qa/agent/regie/plan.py", "tools/graph-qa/agent/regie/regisseur.py"),
            tests=("tools/graph-qa/tests/test_regie_plan.py", "tools/graph-qa/tests/test_regisseur.py"),
            ingang=REGIE_ACTIES, hangt_af_van=("agent/annotatie",),
            uitvoer="het regie-artefact: opgeleverd, wacht op jou, mislukt",
            twijfel="de jurist is de poort tussen bronnen zoeken en annoteren"),
    ]


# --- tools ----------------------------------------------------------------------------------------------------------

def _tools_van(spec: specialists.Specialist) -> frozenset[str]:
    return frozenset(alle_tools()) if spec.tools is None else spec.tools


def _bronbestand(obj: Any) -> str:
    """Het repo-pad van de module of functie (een package wijst naar zijn `__init__.py`)."""
    import inspect
    pad = Path(inspect.getfile(obj)).resolve() if obj is not None else _AGENT / "tools" / "__init__.py"
    return "tools/graph-qa/" + pad.relative_to(_AGENT.parent).as_posix()


def alle_tools() -> dict[str, dict[str, Any]]:
    """Elke tool die een agent kan krijgen of `dispatch` kan uitvoeren, op naam."""
    from .tools import _BY_NAME
    return dict(_BY_NAME)


def uit_tools() -> list[Onderdeel]:
    uit: list[Onderdeel] = []
    for naam, t in sorted(alle_tools().items()):
        bundel = next((c.naam for c in CONNECTORS.values() if naam in c.tools), None)
        uit.append(Onderdeel(
            id=oid("tool", naam), soort="tool", label=naam, doel=_eerste_zin(t.get("description", "")), model="geen",
            herkomst=EIGEN, bestand=(_bronbestand(t.get("handler")),),
            versie=versie(t.get("description", ""), t.get("input_schema", {})), ingang=(naam,), tools=(naam,),
            uitvoer="het resultaatcontract (`agent/resultaat.py`)",
            twijfel="een fout met een reden; nooit een stil afgekapt resultaat",
            tests=("tools/graph-qa/tests/test_resultaatcontract.py", "tools/graph-qa/tests/test_toolverdeling.py"),
            straat=CONNECTORS[bundel].env if bundel else None,
            inhoud={"beschrijving": t.get("description", ""),
                    "argumenten": sorted((t.get("input_schema") or {}).get("properties", {}))},
        ))
    return uit


# --- controles (hooks) -----------------------------------------------------------------------------------------------

def _controlemodules() -> tuple[Any, ...]:
    from . import beweringen, grounding, id_herkomst
    from .sjablonen import vullen
    return (grounding, id_herkomst, beweringen, vullen)


#: De controles rond de antwoordlus van elke specialist (verify_node, tools_node, sjabloon_node).
ANTWOORD_CONTROLES: tuple[str, ...] = ("controle/brongetrouwheid", "controle/id_herkomst", "controle/beweringen",
                                       "controle/sjabloon_vullen")


def uit_controles() -> list[Onderdeel]:
    uit: list[Onderdeel] = []
    for mod in _controlemodules():
        c = mod.CONTROLE
        uit.append(Onderdeel(
            id=oid("controle", c["naam"]), soort="controle", label=c["label"], doel=c["doel"], model="geen",
            herkomst=EIGEN, bestand=(_bronbestand(mod),),
            versie=versie(c), ingang=(c["moment"],), tests=tuple(c["tests"]),
            twijfel="een afwijking gaat terug naar het model of wordt zichtbaar voor de jurist; nooit stil",
        ))
    return uit


# --- de catalogus ----------------------------------------------------------------------------------------------------

ADAPTERS = (uit_methode, uit_rollen, uit_regelsets, uit_tools, uit_connectors, uit_sjablonen, uit_workflows,
            uit_specialisten, uit_agents, uit_controles)


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
