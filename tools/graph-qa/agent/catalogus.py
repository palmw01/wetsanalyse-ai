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
from dataclasses import replace
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from bronmodel.agentprofiel import Agentprofiel
from bronmodel.catalogus import EIGEN, NEUTRAAL, Herkomst, Onderdeel, Stap, oid, versie, zwaarste
from bronmodel.connectors import CONNECTORS, ConnectorBeschrijving

from . import bronnen_vinden, bronpakket, bronselectie, profielen, werkgebied_intake
from .agentvorm import CENTRAAL, CENTRAAL_BREED, Agent
from .agents.register import AGENTS, NAAM
from .begrippen_pipeline import keten as begrippenketen
from .jas_pipeline import keten as annotatieketen
from .llm_stap import Rol
from .models import ACTIE_TAAK, BRONSELECTIE_ACTIES, INTAKE_ACTIES, REGIE_ACTIES
from .methode import vingerafdruk
from .methodepakket import PAKKET
from .sjablonen import SJABLONEN, Sjabloon



def _eerste_zin(tekst: str) -> str:
    tekst = " ".join((tekst or "").split())
    punt = tekst.find(". ")
    return tekst if punt < 0 else tekst[: punt + 1]


# --- methode en rollen ---------------------------------------------------------------------------------------------

def _methode_herkomst(codes: tuple[str, ...] = (), skill: str | None = None) -> Herkomst:
    lex = PAKKET["skills"][skill or _basis()]["lex"]
    return Herkomst(bron=lex["herkomst"], licentie=lex["licentie"], letterlijk=lex["letterlijk"] == "ja",
                    verwijzing=codes)


def _basis() -> str:
    return next(iter(PAKKET["skills"]))


def _andere_skills() -> tuple[str, ...]:
    """De voorvoegsels van de bronbestanden van de skills naast de basis (`<naam>/…`)."""
    return tuple(f"{n}/" for n in PAKKET["skills"] if n != _basis())


def uit_methode() -> list[Onderdeel]:
    """Eén onderdeel per methode-skill. De basis bepaalt de rollen; een andere skill vult ze aan (ADR-014 §7)."""
    uit: list[Onderdeel] = []
    for naam, meta in PAKKET["skills"].items():
        eigen = {k: x for k, x in PAKKET["secties"].items() if x["skill"] == naam}
        codes = tuple(sorted({c for x in eigen.values() for c in x["bronnen"]}))
        rollen = {r: [k for k in ids if k in eigen] for r, ids in PAKKET["rollen"].items()}
        prefix = "" if naam == _basis() else f"{naam}/"
        uit.append(Onderdeel(
            id=oid("methode", naam), soort="methode", label=meta["lex"]["label"], doel=meta["lex"]["beschrijving"],
            model="geen", herkomst=_methode_herkomst(
                codes + ((f"{meta['map']}/BRON.md",) if meta["lex"]["letterlijk"] == "ja" else ()), naam),
            bestand=tuple(f"{meta['map']}/{p.removeprefix(prefix)}" for p in sorted(PAKKET["bronbestanden"])
                          if (p.startswith(prefix) if prefix else not p.startswith(_andere_skills()))),
            versie=versie(meta["versie"], *(x["sha256"] for x in eigen.values())), bronhash=bronpakket.bronhash("skill", naam),
            uitvoer="methodetekst per rol",
            tests=("tools/graph-qa/tests/methode/test_methodepakket.py", "tools/graph-qa/tests/methode/test_methode_drift.py"),
            bewerkbaar=tuple(sorted(eigen)),
            inhoud={"methode_versie": meta["versie"], "rollen": {r: ids for r, ids in rollen.items() if ids},
                    "secties": {k: {"bestand": x["bestand"], "bronnen": x["bronnen"]} for k, x in eigen.items()}},
        ))
    return uit


def _aanroepers(rol: str) -> tuple[str, ...]:
    """Wie de methodetekst van deze rol krijgt: modelaanroepen uit `llm_stap.Rol` en specialisten."""
    namen = {r.naam for r in Rol if r.methoderol == rol}
    namen |= {n for n, p in profielen.PROFIELEN.items() if p.rol == rol}
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
            bestand=tuple(sorted({f".claude/skills/{s['skill']}/{s['bestand']}" for s in secties.values()}
                                 | {f".claude/skills/{s['skill']}/agentrollen.json" for s in secties.values()})),
            versie=vingerafdruk(rol), ingang=_aanroepers(rol),
            context="vóór de systeemprompt, in het stabiele deel (cache-prefix)", uitvoer="systeemprompt",
            tests=("tools/graph-qa/tests/methode/test_methoderollen.py",), deel_van=oid("methode", _basis()), bewerkbaar=tuple(ids),
            inhoud={"secties": [{"id": k, "skill": s["skill"], "bestand": f".claude/skills/{s['skill']}/{s['bestand']}",
                                 "bronnen": s["bronnen"], "sha256": s["sha256"], "tekst": s["tekst"]}
                                for k, s in secties.items()]},
        ))
    return uit


# --- agentprofielen --------------------------------------------------------------------------------------------------

def uit_agentprofielen() -> list[Onderdeel]:
    """Eén onderdeel per profiel uit het register (ADR-016 §A2). De specialisten van de supervisor zijn de eerste."""
    uit: list[Onderdeel] = []
    for naam, p in profielen.PROFIELEN.items():
        tools = tuple(sorted(_tools_van(p)))
        sjablonen = sorted(p.sjablonen)
        uit.append(Onderdeel(
            id=oid("agentprofiel", naam), soort="agentprofiel", label=naam.replace("_", " ").capitalize(),
            doel=p.beschrijving, model="agent", herkomst=EIGEN, bestand=(f".claude/lex-agents/{naam}.md",),
            versie=profielen.versie(p), bronhash=bronpakket.bronhash("agentprofiel", naam), tools=tools,
            ingang=PROFIELPLEK[profielplek(naam) or "onbekend"]["ingang"],
            straat=None,
            uitvoer=", ".join(sjablonen) or "doel-JSON voor de annotatieroute",
            twijfel="leemte of doorvragen; een citaat dat niet letterlijk in de opgehaalde tekst staat, valt weg (grounding)",
            tests=("tools/graph-qa/tests/centrale_agent/test_profielregister.py", "tools/graph-qa/tests/routes/test_specialists.py"),
            hangt_af_van=(oid("rol", p.rol), *(oid("methode", s) for s in p.skills),
                          *(oid("sjabloon", s) for s in sorted(_sjablonen_van(p))),
                          *(oid("connector", c) for c in CONNECTORS if c in p.connectors),
                          *(oid("tool", t) for t in tools), *ANTWOORD_CONTROLES),
            inhoud={"systeemtekst": p.instructie, "kiesbaar": p.kiesbaar,
                    "skills": list(p.skills),
                    # De grenzen gelden alleen voor een subagent, dus alleen voor een kiesbaar profiel.
                    **({"max_rondes": Agent(p).max_rondes, "budget": Agent(p).budget} if p.kiesbaar else {}),
                    "plek": profielplek(naam),
                    **(_centraal_inhoud(naam) if naam in (CENTRAAL, CENTRAAL_BREED) else {})},
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
            tests=("tools/graph-qa/tests/sjablonen/test_sjablonen.py",),
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
        tests=("tools/graph-qa/tests/connectors/test_connectorbeschrijving.py",),
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
            tests=("tools/graph-qa/tests/centrale_agent/test_agents.py", "tools/graph-qa/tests/runs/test_agent_contracten.py"),
            hangt_af_van=(*AGENT_WORKFLOWS.get(naam, ()), *((oid("rol", naam),) if naam in PAKKET["rollen"] else ())),
            inhoud={"taken": taken},
        ))
    return uit


# --- regelsets: elke YAML in een keten -------------------------------------------------------------------------------

_AGENT = Path(__file__).resolve().parent
#: Per map met regels: de keten, en de test die de regels draait. Een YAML in een map die hier niet staat, maakt
#: `tests/test_catalogus.py` rood.
REGELMAPPEN: dict[str, tuple[str, str]] = {
    "jas_pipeline/detectoren/regels": ("jas", "tools/graph-qa/tests/annotatieketen/test_detectoren.py"),
    "jas_pipeline/profielen": ("jas", "tools/graph-qa/tests/annotatieketen/test_detectieprofielen.py"),
    "jas_pipeline": ("jas", "tools/graph-qa/tests/annotatieketen/test_verklaringen.py"),
    "begrippen_pipeline/regels": ("begrippen", "tools/graph-qa/tests/begrippen/test_begrippen_patronen.py"),
    "begrippen_pipeline/betekenisregels": ("begrippen", "tools/graph-qa/tests/begrippen/test_betekenis.py"),
    "begrippen_pipeline": ("begrippen", "tools/graph-qa/tests/begrippen/test_begrippen_signalen.py"),
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
    return uit + uit_skillregels()


#: Per keten de test die de tests van een skillregel draait (dezelfde als voor de eigen regels).
_SKILLREGELTEST = {"jas": "tools/graph-qa/tests/methode/test_skill_zonder_code.py",
                   "begrippen": "tools/graph-qa/tests/methode/test_skill_zonder_code.py"}


def uit_skillregels() -> list[Onderdeel]:
    """Regelsets uit een methode-skill (S6): een deel van hun skill, achter de proefvlag `SKILL_REGELS`."""
    from . import skill_regels
    uit: list[Onderdeel] = []
    for keten in ("jas", "begrippen"):
        for naam, items in skill_regels.regelsets(keten).items():
            skill, familie = naam.split(".", 1)
            regels = _regels(items)
            uit.append(Onderdeel(
                id=oid("regelset", f"{keten}.{naam}"), soort="regelset", label=f"{keten}.{naam}",
                doel=f"Regels uit de methode {PAKKET['skills'][skill]['lex']['label']} voor de {keten}keten "
                     f"({familie}); alleen actief met de proefvlag.",
                model="geen", herkomst=_methode_herkomst(tuple(sorted({str(r['bron']) for r in regels if r.get('bron')})), skill),
                bestand=(f"{PAKKET['skills'][skill]['map']}/regels/{keten}/{familie}.yaml",), versie=versie(items),
                tests=(_SKILLREGELTEST[keten],), uitvoer="bewijscodes met een bestaande verklaring",
                deel_van=oid("methode", skill), straat=skill_regels.VLAG, inhoud={"regels": regels},
            ))
    return uit


# --- workflows: de ketens met hun stappen ----------------------------------------------------------------------------

def _wf(naam: str, label: str, doel: str, laag: str, stappen: tuple[Stap, ...], *, bestand: tuple[str, ...],
        tests: tuple[str, ...], ingang: tuple[str, ...] = (), hangt_af_van: tuple[str, ...] = (),
        uitvoer: str = "", twijfel: str = "", straat: str | None = None, context: str = "",
        inhoud: dict[str, Any] | None = None) -> Onderdeel:
    return Onderdeel(
        id=oid("workflow", naam), soort="workflow", label=label, doel=doel, laag=laag,  # type: ignore[arg-type]
        model=zwaarste([s.model for s in stappen]), herkomst=EIGEN, bestand=bestand,
        versie=versie([(s.naam, s.model, s.onderdeel) for s in stappen]), stappen=stappen, ingang=ingang,
        hangt_af_van=tuple(dict.fromkeys((*hangt_af_van, *(s.onderdeel for s in stappen if s.onderdeel)))),
        uitvoer=uitvoer, twijfel=twijfel, tests=tests, straat=straat, context=context,
        inhoud={"stappen": [{"naam": s.naam, "model": s.model, "onderdeel": s.onderdeel} for s in stappen],
                **(inhoud or {})},
    )


def uit_workflows() -> list[Onderdeel]:
    sets = uit_regelsets()
    detectoren = tuple(o.id for o in sets if o.naam.startswith("jas.detector.") or (o.straat and o.naam.startswith("jas.")))
    uit_skill_begrippen = tuple(o.id for o in sets if o.straat and o.naam.startswith("begrippen."))
    return [
        _wf("annotatieketen", "Annotatieketen (ADR-001)",
            "Markeert en classificeert de formuleringen van één bepaling in JAS-klassen: detectoren en vaste "
            "besluiten eerst, een kleine classifier en een gerichte reviewer alleen waar dat nodig is.",
            "taakagent", annotatieketen.FASEN,
            bestand=("tools/graph-qa/agent/jas_pipeline/keten.py", "docs/architectuur/annotatieketen.md"),
            tests=("tools/graph-qa/tests/annotatieketen/test_detectoren.py", "tools/graph-qa/tests/annotatieketen/test_provenance_element.py"),
            ingang=("annoteer",), hangt_af_van=(*detectoren, "regelset/jas.profielen"),
            uitvoer="markeringen met ankers, trace en aandachtniveau; het beslisregister",
            twijfel="geel met alternatieven voor de jurist; nooit automatisch rood", ),
        _wf("begrippenketen", "Begrippenketen (ADR-004)",
            "Stelt voor welke geannoteerde formuleringen één begrip aanduiden en welke in een relatie staan, "
            "zonder model; het meedenken bij twijfel is een aparte taak van de begrippen-agent.",
            "taakagent", begrippenketen.FASEN,
            bestand=("tools/graph-qa/agent/begrippen_pipeline/keten.py",),
            tests=("tools/graph-qa/tests/begrippen/test_begrippen_patronen.py",),
            hangt_af_van=("regelset/begrippen.berekening", "regelset/begrippen.verklaringen", *uit_skill_begrippen),
            uitvoer="betekenisgroepen, relaties en vragen (het begrippenartefact)",
            twijfel="een vraag aan de analist, of geel; sterk tegenbewijs wint altijd"),
        _wf("bronnen_vinden", "Bronnen vinden",
            "Zoekt zonder model bepalingen die bij een werkgebied kunnen horen, per methode met een plafond; "
            "wat er gevonden is, beslist de analist in de bronselectie.",
            "workflow", tuple(Stap(m, "geen") for m in bronnen_vinden.METHODEN),
            bestand=("tools/graph-qa/agent/bronnen_vinden.py", "tools/graph-qa/agent/zoekvragen.py",
                     ".claude/skills/wetsanalyse/references/zoekvragen-bronselectie.md"),
            tests=("tools/graph-qa/tests/werkgebied/test_bronnen_vinden.py", "tools/graph-qa/tests/werkgebied/test_zoekvragen.py"),
            uitvoer="kandidaten per methode met hun bewijs",
            twijfel="een methode die faalt wordt `volledig: false`; falen ze allemaal, dan een fout"),
        _wf("bronselectie", "Bronselectie per deelvraag (spoor J)",
            "Werkt de deelvragen één voor één af met vraagkaarten: kernbepalingen, wat eraan hangt, afronden; "
            "de stand staat bij de api.",
            "workflow", tuple(Stap(s, "geen") for s in bronselectie.KAARTSTAPPEN),
            bestand=("tools/graph-qa/agent/bronselectie.py", "docs/architectuur/bronselectie-per-deelvraag.md"),
            tests=("tools/graph-qa/tests/werkgebied/test_bronselectie.py",), ingang=BRONSELECTIE_ACTIES,
            hangt_af_van=("workflow/bronnen_vinden",), uitvoer="vraagkaarten en het bronselectie-artefact",
            twijfel="de analist beslist in het paneel; een 412 toont de stand van nu"),
        _wf("werkgebied_intake", "Werkgebied samenstellen (activiteit 1)",
            "Stelt met vraagkaarten in de volgorde van de methode een werkgebied samen of vult zijn dossier aan; "
            "het model doet alleen voorstellen, de volgorde is een stapmachine.",
            "workflow", tuple(Stap(s, "strict", rol=_INTAKE_ROL[s]) if s in werkgebied_intake.MODEL_STAPPEN else Stap(s, "geen")
                              for s in werkgebied_intake.KAARTSTAPPEN),
            bestand=("tools/graph-qa/agent/werkgebied_intake.py",),
            tests=("tools/graph-qa/tests/werkgebied/test_werkgebied_intake.py",), ingang=INTAKE_ACTIES,
            uitvoer="vraagkaarten en het werkgebiedartefact", twijfel="overslaan kan; een praktijkvoorbeeld verzint Lex niet"),
        _wf("overzicht", "Overzicht van een onderwerp",
            "Bouwt op 'welke artikelen gaan over X?' een overzicht en een samenvatting uit de opbouw van de wet, zonder "
            "model: dezelfde vraag geeft hetzelfde overzicht.", "workflow",
            (Stap("regelingen in de vraag", "geen"), Stap("opbouw zoeken", "geen", "tool/zoek_opbouw"),
             Stap("samenvatting", "geen")),
            bestand=("tools/graph-qa/agent/overzicht.py", "tools/graph-qa/agent/nodes/overzicht.py"),
            tests=("tools/graph-qa/tests/routes/test_overzicht.py",), uitvoer="het overzicht-event en een kaartje",
            twijfel="een bouwfout gaat naar de agent"),
        _wf("bepaling", "De tekst van een bepaling (ADR-010, D1)",
            "Haalt de tekst van één genoemde bepaling uit de graaf (of live bij overheid.nl); het model schrijft alleen "
            "de toelichting.", "workflow",
            (Stap("bepaling lezen", "geen"), Stap("toelichting", "strict", rol="bepaling_toelichting")),
            bestand=("tools/graph-qa/agent/bepaling_workflow.py", "tools/graph-qa/agent/nodes/bepaling.py"),
            tests=("tools/graph-qa/tests/routes/test_bepaling_workflow.py",), uitvoer="het sjabloon antwoord_bepaling",
            hangt_af_van=("sjabloon/antwoord_bepaling", "controle/brongetrouwheid"),
            twijfel="niet te lezen: de agent neemt het over"),
        _wf("bron_lezen", "Een genoemd stuk vooraf lezen (ADR-013)",
            "Leest een stuk dat de vraag bij id of citeervorm noemt met de leestool van zijn connector, voordat de "
            "specialist formuleert; een stuk zonder tekst krijgt een vaste melding.", "workflow",
            (Stap("stuk lezen", "geen"),),
            bestand=("tools/graph-qa/agent/nodes/bron_lezen.py",),
            tests=("tools/graph-qa/tests/routes/test_bronroutering.py",), uitvoer="het gelezen stuk in het bronspoor",
            twijfel="niet te lezen of niet gevonden: een vaste melding met de reden"),
        _wf("bron_lijst", "Een lijst- of telvraag over een bron",
            "Beantwoordt een lijst- of telvraag over een bron naast de wet met de zoektool in code: het blok stukken, "
            "de telling uit de bron, zonder model.", "workflow",
            (Stap("zoekvraag lezen", "geen"), Stap("zoeken", "geen"), Stap("lijst of telling", "geen")),
            bestand=("tools/graph-qa/agent/bron_lijst.py", "tools/graph-qa/agent/nodes/bron_lijst.py"),
            tests=("tools/graph-qa/tests/routes/test_bron_lijst.py",), uitvoer="het blok stukken",
            twijfel="een fout van de bron is een vaste melding; een andere fout gaat naar de agent"),
        _wf("vaste_melding", "Een vaste melding",
            "Antwoordt zonder model met een vaste tekst uit de code: een bron die uit staat, een regeling buiten de "
            "graaf, meer artikelen tegelijk, of de keuzevraag van het vorige antwoord.", "workflow",
            (Stap("melding", "geen"),),
            bestand=("tools/graph-qa/agent/nodes/supervisie.py",),
            tests=("tools/graph-qa/tests/routes/test_bronroutering.py",), uitvoer="een tekst met de reden",
            twijfel="geen: de melding zegt wat er niet kan en wat wel"),
        _wf("regie", "Regie per deelvraag (ADR-012)",
            "Verdeelt het werk in een werkgebied over deelgesprekken, na een bevestiging; neemt zelf geen besluit.",
            "workflow", (Stap("plan", "geen"), Stap("bevestiging door de jurist", "geen"),
                         Stap("kindgesprekken", "geen", "workflow/bronselectie"), Stap("bundel", "geen")),
            bestand=("tools/graph-qa/agent/regie/plan.py", "tools/graph-qa/agent/regie/regisseur.py"),
            tests=("tools/graph-qa/tests/centrale_agent/test_regie_plan.py", "tools/graph-qa/tests/centrale_agent/test_regisseur.py"),
            ingang=REGIE_ACTIES, hangt_af_van=("agent/annotatie",),
            uitvoer="het regie-artefact: opgeleverd, wacht op jou, mislukt",
            twijfel="de jurist is de poort tussen bronnen zoeken en annoteren", inhoud=_regie_inhoud()),
        _subagent_workflow(),
    ]


# --- routes (ingangen) ----------------------------------------------------------------------------------------------

def uit_routes() -> list[Onderdeel]:
    from .routes import ROUTES
    return [Onderdeel(
        id=oid("route", r.naam), soort="route", label=r.label, doel=r.doel_zin, model="geen", herkomst=EIGEN,
        bestand=("tools/graph-qa/agent/routes.py", "tools/graph-qa/agent/nodes/supervisie.py"),
        versie=versie(r.naam, r.herkenner, r.doel, r.moment), ingang=(r.herkenner,), context=r.moment,
        tests=("tests/poort/test_routecontract.py", "tools/graph-qa/tests/routes/test_graafopbouw.py"),
        hangt_af_van=(r.doel,), inhoud={"herkenner": r.herkenner, "moment": r.moment},
    ) for r in ROUTES]


# --- tools ----------------------------------------------------------------------------------------------------------

def _sjablonen_van(p: Agentprofiel) -> frozenset[str]:
    """De sjablonen die het profiel kan krijgen: zijn eigen, en `antwoord_extern` als het een connector noemt
    (`nodes/antwoord.py`, ADR-013)."""
    from .sjablonen import EXTERN
    eigen = frozenset(p.sjablonen)
    return eigen | {EXTERN} if eigen and p.connectors else eigen


def _tools_van(p: Agentprofiel) -> frozenset[str]:
    """Wat het profiel mag krijgen: `None` is elke tool die het model aangeboden kan krijgen (de JAS-kennistools zijn
    opt-in, `anthropic_schemas`). Of een connector in een beurt aanstaat, beslist `toegestane_tools`."""
    from .tools import TOOLS
    eigen = profielen.tools_van(p)
    return frozenset(t["name"] for t in TOOLS) if eigen is None else eigen


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
            tests=("tools/graph-qa/tests/graaf/test_resultaatcontract.py", "tools/graph-qa/tests/centrale_agent/test_toolverdeling.py"),
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


# --- de centrale agent en zijn overdrachten (ADR-016) -----------------------------------------------------------------
#
# Waar een overdracht van de centrale agent uitkomt en welke plek een profiel heeft, afgeleid uit de registers: de
# overdrachten (`overdracht.OVERDRACHT`), de profielen (`profielen.PROFIELEN`) en de routes (`routes.ROUTES`).
# `tests/test_catalogus_agentvorm.py` maakt een overdracht, een doelnode of een profiel zonder plek hier rood.
# (Het blok *Hoe een vraag binnenkomt* van de werkwijze-pagina is weg, plan instellingen-aanpassingen.)

#: Waar een overdracht uitkomt, per node van de graaf: het onderdeel van de catalogus dat die node uitvoert. De node
#: `agent` staat er niet in: daar blijft de beurt bij een agent, en wat dat betekent zegt `_VIA_AGENT` per overdracht.
_NODE_ONDERDEEL: dict[str, tuple[str, ...]] = {
    "afwijzen": ("workflow/vaste_melding",),
    "bepaling_lezen": ("workflow/bepaling",),
    "overzicht_bouwen": ("workflow/overzicht",),
    "annotaties_zoeken": ("agentprofiel/annotaties_lezen",),
    "begrippen_zoeken": ("agentprofiel/begrippen_lezen",),
    "regels_zoeken": ("agentprofiel/regels_lezen",),
    "bron_lijst": ("workflow/bron_lijst",),
    "subagent_plan": ("workflow/subagent",),
    "werkgebied_intake": ("workflow/werkgebied_intake",),
    "bronselectie": ("workflow/bronselectie",),
    "regie_voorstel": ("workflow/regie",),
}


def _node_onderdeel(node: str) -> tuple[str, ...]:
    from .overdracht import TAAKAGENTS
    if node == "agent_taak":   # de taak van een agent uit `agents/register.py`
        return tuple(oid("agent", a) for a in TAAKAGENTS)
    return _NODE_ONDERDEEL[node]


def _via_agent(naam: str) -> tuple[str, ...]:
    """Een overdracht die de beurt (ook) bij de node `agent` laat: welk onderdeel daar het werk doet."""
    from .overdracht import ANNOTEER, DELEGATIE_STAND, LAAD_SKILL, LEES_SKILL, SUBAGENT, _skillnamen
    methodes = tuple(oid("methode", n) for n in _skillnamen())
    return {
        "meer_tools": (oid("agentprofiel", CENTRAAL_BREED),),
        SUBAGENT: ("workflow/subagent",),
        DELEGATIE_STAND: ("workflow/subagent", "workflow/regie"),
        LAAD_SKILL: methodes, LEES_SKILL: methodes,
        ANNOTEER: ("workflow/annotatieketen",),   # de ophaal-agent zoekt de bepaling, dan de keten
    }[naam]


def overdracht_doelen(naam: str) -> tuple[str, ...]:
    """De onderdelen waar de overdracht `naam` de beurt heen kan sturen, in de volgorde van haar nodes."""
    from .overdracht import INGANG, OVERDRACHT
    o = OVERDRACHT[naam]
    nodes = o.ingangen if o.naar == INGANG else (o.naar, *o.ingangen)
    uit = [d for n in nodes for d in (_via_agent(naam) if n == "agent" else _node_onderdeel(n))]
    return tuple(dict.fromkeys(uit))


def _overdrachten(profiel: str) -> list[dict[str, Any]]:
    from .overdracht import voor
    return [{"naam": n, "doel": _eerste_zin(o.beschrijving).replace("Roep dit aan als ", "Als ", 1), "naar": list(overdracht_doelen(n)),
             "alleen_in_werkgebied": o.werkgebied}
            for n, o in voor(profiel).items()]


def _centraal_inhoud(naam: str) -> dict[str, Any]:
    """Wat de centrale agent zelf meebrengt: zijn overdrachten, en de kernset tegenover het brede profiel."""
    from .overdracht import LAAD_SKILL, LEES_SKILL, _skillnamen
    kern = _tools_van(profielen.PROFIELEN[CENTRAAL])
    breed = _tools_van(profielen.PROFIELEN[CENTRAAL_BREED])
    return {"overdrachten": _overdrachten(naam), "kernset": sorted(kern), "alleen_breed": sorted(breed - kern),
            "skills": {"tools": [LAAD_SKILL, LEES_SKILL], "methodes": [oid("methode", n) for n in _skillnamen()]}}


#: Waar een profiel staat. `profielplek` deelt elk profiel in; `ingang` gaat mee in de catalogus.
PROFIELPLEK: dict[str, dict[str, Any]] = {
    "centraal": {"label": "De centrale agent", "ingang": ("elke vraag die geen route in code pakt (ADR-016 §A7)",)},
    "centraal_breed": {"label": "De centrale agent met alle graaftools",
                       "ingang": ("de overdracht meer_tools van het profiel centraal",)},
    "subagent": {"label": "Profiel van een subagent",
                 "ingang": ("de overdracht subagent van de centrale agent (een kiesbaar profiel)",)},
    "route": {"label": "Profiel van een route in code", "ingang": ("een route in code",)},
    "ophaal": {"label": "De ophaal-agent van de annotatieketen", "ingang": ("de annotatieketen en de regie",)},
    "onbekend": {"label": "Zonder plek", "ingang": ("een route in code",)},
}


def profielplek(naam: str) -> str | None:
    """De plek van een profiel, afgeleid: de vorm van de centrale agent, een subagent, het doel van een route (ook het
    profiel waarmee een route in code verder antwoordt, `overdracht._SPECIALISTEN`), of de rol van de ophaal-agent. Een
    profiel zonder plek is `None`."""
    from .overdracht import _SPECIALISTEN
    from .routes import ROUTES
    if naam in (CENTRAAL, CENTRAAL_BREED):
        return naam
    if naam in profielen.KIESBAAR:
        return "subagent"
    if oid("agentprofiel", naam) in {r.doel for r in ROUTES} or naam in _SPECIALISTEN:
        return "route"
    p = profielen.PROFIELEN.get(naam)
    if p is not None and p.rol == Rol.OPHAAL.methoderol:
        return "ophaal"
    return None


def _subagent_limieten() -> list[dict[str, Any]]:
    from . import stukcontrole
    from . import subagent as sub
    from .agentvorm import MAX_RONDES_SUBAGENT
    from .nodes.antwoord import MAX_TOKENS_SUBAGENT
    from .sjablonen import rapport
    return [
        {"naam": "MAX_SUBAGENTS", "waarde": sub.MAX_SUBAGENTS, "uitleg": "opdrachten in één fase"},
        {"naam": "REGIE_PARALLEL", "waarde": sub.REGIE_PARALLEL, "uitleg": "subagents die tegelijk lopen"},
        {"naam": "DELEGATIE_AANDEEL", "waarde": sub.DELEGATIE_AANDEEL,
         "uitleg": "deel van het budget dat de gebruiker deze week nog heeft: het plafond van een plan"},
        {"naam": "MAX_RONDES_SUBAGENT", "waarde": MAX_RONDES_SUBAGENT, "uitleg": "modelrondes per subagent"},
        {"naam": "MAX_TOKENS_SUBAGENT", "waarde": MAX_TOKENS_SUBAGENT,
         "uitleg": "tokens per subagent per deel; de ronde die er niet meer in past, wordt niet meer gestart"},
        {"naam": "MAX_VRAGEN", "waarde": rapport.MAX_VRAGEN, "uitleg": "vragen naar de jurist in één rapport"},
        {"naam": "MAX_OPTIES", "waarde": rapport.MAX_OPTIES, "uitleg": "opties per vraag"},
        {"naam": "stukcontrole.MAX_STUKKEN", "waarde": stukcontrole.MAX_STUKKEN,
         "uitleg": "stukken die de controle per stuk leest"},
    ]


def _subagent_workflow() -> Onderdeel:
    from .overdracht import SUBAGENT
    from .sjablonen import rapport
    return _wf(
        "subagent", "Subagents (ADR-016 §A3–A5)",
        "De centrale agent geeft een opdracht die op zichzelf staat en veel lezen vraagt aan een subagent: een kindgesprek "
        "met een kiesbaar profiel, één laag diep, dat alleen met een rapport terugkomt. Niet voor een vraag die hij in een "
        "paar rondes zelf beantwoordt, en niet per deelvraag (dat is de regie).",
        "open",
        (Stap("opdracht in vaste velden", "geen"),
         Stap("bevestiging en plafond bij twee of meer", "geen"),
         Stap("kindgesprek met een kiesbaar profiel", "geen"),
         Stap("rapport", "geen", oid("sjabloon", rapport.NAAM)),
         Stap("controle per stuk", "strict", rol=Rol.STUKCONTROLE.naam),
         Stap("vragen naar de jurist en hervatten", "geen"),
         Stap("bundel door de centrale agent", "geen")),
        bestand=("tools/graph-qa/agent/subagent.py", "tools/graph-qa/agent/sjablonen/rapport.py",
                 "tools/graph-qa/agent/stukcontrole.py", "tools/graph-qa/agent/nodes/delegatie_plan.py",
                 "tools/graph-qa/agent/nodes/subagent_vervolg.py"),
        tests=("tools/graph-qa/tests/centrale_agent/test_subagent.py", "tools/graph-qa/tests/centrale_agent/test_subagent_vragen.py",
               "tools/graph-qa/tests/centrale_agent/test_subagenten.py", "tools/graph-qa/tests/centrale_agent/test_delegatie_afsluiten.py"),
        ingang=(SUBAGENT,), hangt_af_van=ANTWOORD_CONTROLES,
        context="de opdracht als eerste bericht, met het werkgebied en de bronnen van de beurt; zonder de historie",
        uitvoer="een rapport (klaar, vraag of niet gelukt) als toolresultaat van de centrale agent",
        twijfel="een vraag naar de jurist als vraagkaart; zonder rapport een tekst uit code, nooit vrije modeltekst",
        inhoud={
            "profielen": [oid("agentprofiel", n) for n in profielen.KIESBAAR],
            "een_laag": "Een subagent heeft geen eigen overdrachten en start geen subagent. Zijn enige uitgang is het "
                        "sjabloon rapport; geen profiel mag dat sjabloon noemen.",
            "vragen": "Een vraag naar boven is een rapport met status vraag. Die gaat altijd naar de jurist, als "
                      "vraagkaart: de centrale agent beantwoordt haar niet zelf. Na het laatste antwoord hervat de code "
                      "de subagent in hetzelfde deelgesprek; daarna schrijft de centrale agent de bundel.",
            "meer": "Eén opdracht start meteen. Twee of meer legt de code eerst voor, met een plafond; de klik start "
                    "ze, en bij het plafond start er niets nieuws.",
            "limieten": _subagent_limieten(),
            "controles": [
                {"naam": "elke passage", "uitleg": "gaat door de toets van een uitleg; wat niet te tonen is, laat de "
                                                   "code weg en noemt ze"},
                {"naam": "gelezen is niet gevonden", "uitleg": "alleen wat een leestool gaf, telt als gelezen"},
                {"naam": "zonder rapport geen duiding", "uitleg": "een duiding van een stuk rust op een passage van "
                                                                  "dat stuk"},
                {"naam": "per stuk", "uitleg": "na een rapport leest één modelaanroep elke zin die een stuk duidt "
                                               "tegen de passages eruit: steunt, spreekt tegen of niet te zien"},
                {"naam": "na een subagent", "uitleg": "de centrale agent leest de stukken niet zelf opnieuw; hij vat het "
                                                      "rapport samen, en leest hoogstens twee bepalingen na"},
            ],
        },
    )


def _regie_inhoud() -> dict[str, Any]:
    """De regie als tool van de centrale agent (`regie_plan`), naast de regie als vaste route."""
    from .overdracht import OVERDRACHT, REGIE_PLAN
    from .regie.regisseur import FASEN_TEKST
    plan = OVERDRACHT[REGIE_PLAN]
    return {"als_tool": {"tool": REGIE_PLAN, "opdrachten": plan.invoer["opdracht"]["enum"],
                         "alleen_in_werkgebied": plan.werkgebied},
            "fasen": [r.split(". ", 1)[1].rstrip(";.") for r in FASEN_TEKST.splitlines() if r[:1].isdigit()]}


def _met_overdrachten(alle: list[Onderdeel]) -> list[Onderdeel]:
    """Een overdracht is een ingang van het onderdeel waar ze heen leidt (afgeleid, zoals een actie)."""
    from .overdracht import OVERDRACHT
    extra: dict[str, list[str]] = {}
    for naam in OVERDRACHT:
        for d in overdracht_doelen(naam):
            extra.setdefault(d, []).append(naam)
    return [replace(o, ingang=tuple(dict.fromkeys((*o.ingang, *extra[o.id])))) if o.id in extra else o for o in alle]


# --- de catalogus ----------------------------------------------------------------------------------------------------

ADAPTERS = (uit_methode, uit_rollen, uit_regelsets, uit_tools, uit_connectors, uit_sjablonen, uit_workflows,
            uit_agentprofielen, uit_agents, uit_routes, uit_controles)


#: De methode waar de annotatieketen, de annotatie-UI en de JAS-tools van zijn.
WETSANALYSE = "wetsanalyse"

#: Wat van wetsanalyse is zonder dat het uit een rol of een deel volgt (plan methodes scheiden, §5): de annotatieketen
#: en haar leestools, de begrippen, en het werkgebied met de bronselectie. Rollen, agentprofielen en routes staan hier
#: niet: die erven (`_methode`). Een id dat niet meer bestaat, maakt `tests/test_catalogus_methode.py` rood.
VAN_WETSANALYSE: frozenset[str] = frozenset({
    "workflow/annotatieketen", "workflow/begrippenketen", "workflow/bronnen_vinden", "workflow/bronselectie",
    "workflow/werkgebied_intake",
    "agent/annotatie", "agent/begrippen", "agent/deelvragen",
    "tool/get_annotatie", "tool/get_annotatiedekking", "tool/overzicht_annotaties", "tool/search_annotaties",
    "tool/get_begrip", "tool/search_begrippen", "tool/jas_klasse_opvragen", "tool/get_regel", "tool/search_regels",
    "sjabloon/antwoord_annotaties", "sjabloon/antwoord_begrip",
    "route/meerdere_artikelen",
})

#: De regelsets van de annotatieketen en de begrippenketen; een regelset uit een andere skill is van die skill.
_REGELSETS_VAN_WETSANALYSE = ("jas.", "begrippen.")


def _methode(o: Onderdeel, per_id: dict[str, Onderdeel], gezien: frozenset[str] = frozenset()) -> str:
    """Van welke methode een onderdeel is. Eén regel per soort, in deze volgorde:

    - een methode is van zichzelf, en een deel (een rol) van zijn geheel;
    - wat in `VAN_WETSANALYSE` staat, en de regelsets van de twee ketens, zijn van wetsanalyse;
    - een agentprofiel of agent is van de methode van zijn rol, een route van de methode van wat ze kiest;
    - al het andere is neutraal."""
    if o.soort == "methode":
        return o.naam
    if o.id in gezien:
        return NEUTRAAL
    gezien = gezien | {o.id}
    if o.deel_van and o.deel_van in per_id:
        return _methode(per_id[o.deel_van], per_id, gezien)
    if o.id in VAN_WETSANALYSE or (o.soort == "regelset" and o.naam.startswith(_REGELSETS_VAN_WETSANALYSE)):
        return WETSANALYSE
    if o.soort in ("agentprofiel", "agent"):
        rollen = [per_id[i] for i in o.hangt_af_van if i.startswith("rol/") and i in per_id]
        if rollen:
            return _methode(rollen[0], per_id, gezien)
    if o.soort == "route" and o.hangt_af_van and o.hangt_af_van[0] in per_id:
        return _methode(per_id[o.hangt_af_van[0]], per_id, gezien)
    return NEUTRAAL


@cache
def catalogus() -> tuple[Onderdeel, ...]:
    """Alle onderdelen, op soort en naam, elk met zijn methode. Een id dat twee keer voorkomt, is een fout."""
    alle = _met_overdrachten([o for adapter in ADAPTERS for o in adapter()])
    ids = [o.id for o in alle]
    dubbel = {i for i in ids if ids.count(i) > 1}
    if dubbel:
        raise ValueError(f"dubbele onderdelen in de catalogus: {sorted(dubbel)}")
    per_id = {o.id: o for o in alle}
    return tuple(replace(o, methode=_methode(o, per_id)) for o in alle)


def onderdeel(id_: str) -> Onderdeel | None:
    return next((o for o in catalogus() if o.id == id_), None)
