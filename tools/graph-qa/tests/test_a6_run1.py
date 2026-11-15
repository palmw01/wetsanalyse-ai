"""De fixes na A6 run 1 (15 nov 2026, `docs/architectuur/metingen/centrale-agent-2026-11-15-a6/`), met de opdrachten van
die meting als test.

1. Delegatie: S03–S05, M01 en M06 deed de centrale agent zelf. De code herkent zulke opdrachten nu (`subagent_route.plan`).
2. Vragen naar boven: V02 en V03 ving de bronselectieroute af. Die laat ze nu door naar de centrale agent.
3. De controle per stuk gaf een valse tegenspraak bij PHR:2025:435. Een tegenspraak moet nu een passage aanwijzen.
4. `onbevestigd` na een rapport: een zin over wat de passages niet opleveren, is geen duiding.
5. E09: na een weigering voor een gelezen artikel zonder passage wist het model niet waar die passage stond. De
   weigering geeft nu de plek.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import gelezen, stukcontrole
from agent.bronselectie import is_bronselectievraag
from agent.nodes import subagent_route as route
from agent.nodes import supervisie
from agent.sjablonen import vul
from agent.sjablonen.vullen import Onvulbaar
from bronmodel.connectors import CONNECTORS
from fakes import FakeLLM, make_settings, response, tool_block
from test_sjablonen import TIEN_1, duiding, tien
from test_subagent import STATE

EVAL = Path(__file__).resolve().parents[1] / "eval"
AAN = {n: {"naam": n, "label": c.label, "aan": True, "reden": "aan"} for n, c in CONNECTORS.items()}
IW, AWB, LEIDRAAD = "BWBR0004770", "BWBR0005537", "BWBR0024096"
_NAMEN = {IW: ("Invorderingswet 1990", ("invorderingswet",)),
          AWB: ("Algemene wet bestuursrecht", ("algemene wet bestuursrecht", "awb")),
          LEIDRAAD: ("Leidraad Invordering 2008", ("leidraad invordering",))}


def regelingen(vraag: str) -> list[tuple[str, str]]:
    """Wat `overzicht.regelingen_in_vraag` met de graaf vindt, voor de drie regelingen van de agentset."""
    laag = vraag.casefold()
    return [(i, titel) for i, (titel, namen) in _NAMEN.items() if any(n in laag for n in namen)]


def _set(naam: str) -> dict[str, dict]:
    rijen = [json.loads(r) for r in (EVAL / naam).read_text().splitlines() if r.strip().startswith("{")]
    return {r["id"]: r for r in rijen if r.get("opdracht")}


AGENTSET = _set("golden_centrale_agent.jsonl")


# 1. Delegatie ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("id, profielen", [
    ("S01", ["rechtspraak_lezen"]), ("S03", ["bepalingen_duiden"]), ("S04", ["bepalingen_duiden"]),
    ("S05", ["wetsgeschiedenis_lezen"]), ("M01", ["bepalingen_duiden"] * 3),
    ("M06", ["wetsgeschiedenis_lezen", "wetsgeschiedenis_lezen", "rechtspraak_lezen"]),
])
def test_een_opdracht_die_de_set_aan_subagents_geeft_herkent_de_code(id, profielen):
    rij = AGENTSET[id]
    plan = route.plan(rij["opdracht"], AAN, regelingen)
    laag, hoog = rij["verwacht"]["subagents"]
    assert [p for p, _ in plan] == profielen and laag <= len(plan) <= hoog
    assert set(profielen) <= set(rij["verwacht"]["profielen"])


def test_de_delen_van_een_plan_zeggen_elk_wat_ze_doen_en_wat_een_ander_doet():
    """M01: per regeling één subagent, met de vraag erbij; de centrale agent vergelijkt daarna de rapporten."""
    plan = route.plan(AGENTSET["M01"]["opdracht"], AAN, regelingen)
    assert [o.onderwerp for _, o in plan] == ["de Invorderingswet 1990", "de Algemene wet bestuursrecht",
                                             "de Leidraad Invordering 2008"]
    for _, o in plan:
        assert AGENTSET["M01"]["opdracht"] in o.doel and o.onderwerp in o.doel
        assert o.onderwerp not in o.buiten and "andere subagents" in o.buiten
    m06 = route.plan(AGENTSET["M06"]["opdracht"], AAN, regelingen)
    assert sorted(o.bronnen for _, o in m06) == sorted(AAN[n]["label"] for n in ("rechtspraak", "kamerstukken",
                                                                                 "bekendmakingen"))


def _alle_vragen() -> list[tuple[str, str, dict]]:
    uit = []
    for pad in sorted(EVAL.glob("golden*.jsonl")):
        for regel in pad.read_text().splitlines():
            if not regel.strip().startswith("{"):
                continue
            rij = json.loads(regel)
            vragen = [rij.get("vraag"), rij.get("opdracht"), rij.get("question"),
                      *(b.get("vraag") for b in rij.get("beurten", []) if isinstance(b, dict))]
            uit += [(f"{pad.name}:{rij.get('id', '')}", v, rij) for v in vragen if isinstance(v, str) and v]
    return uit


def test_in_alle_vragensets_valt_alleen_wat_een_subagent_verwacht_onder_de_route():
    """Geen vraag uit de kwaliteits-, routerings-, gespreks- en agentsets valt erin zonder dat de set een subagent
    verwacht (B04, "welke artikelen vallen onder elke afdeling", en E09, twee genoemde artikelen, blijven bij de centrale
    agent)."""
    gevangen = {naam: len(route.plan(v, AAN, regelingen)) for naam, v, _ in _alle_vragen() if route.plan(v, AAN, regelingen)}
    verwacht = {naam: rij["verwacht"]["subagents"] for naam, _, rij in _alle_vragen()
                if (rij.get("verwacht") or {}).get("subagents", [0])[0] >= 1}
    assert set(gevangen) <= set(verwacht), set(gevangen) - set(verwacht)
    assert all(verwacht[n][0] <= k <= verwacht[n][1] for n, k in gevangen.items())
    assert {"golden_centrale_agent.jsonl:" + i for i in ("S01", "S03", "S04", "S05", "M01", "M06")} <= set(gevangen)


@pytest.mark.parametrize("vraag", [
    "Annoteer per artikel het hoofdstuk over dwanginvordering van de Invorderingswet 1990.",
    "Vat per uitspraak samen wat de rechter over artikel 30 zegt.",                        # artikel zonder regeling
    "Hoe verhoudt de aanmaning van artikel 11 van de Invorderingswet 1990 zich tot die van artikel 4:112 van de "
    "Algemene wet bestuursrecht?",                                                         # E09: twee korte bepalingen
    "Hoe is hoofdstuk IV van de Invorderingswet 1990 opgebouwd, en welke artikelen vallen onder elke afdeling?",  # B04
])
def test_wat_de_centrale_agent_zelf_doet(vraag):
    assert route.plan(vraag, AAN, regelingen) == []


def test_zonder_bron_aan_gaat_een_reeks_stukken_niet_naar_een_subagent():
    assert route.plan(AGENTSET["S05"]["opdracht"], {}, regelingen) == []
    assert route.plan(AGENTSET["M06"]["opdracht"], {"rechtspraak": AAN["rechtspraak"]}, regelingen) == []


def _bouw(**extra):
    return SimpleNamespace(settings=SimpleNamespace(centrale_agent="aan", legt_zelf_vast=True), graph=None,
                           kinderen=object(), **extra)


def test_de_supervisor_legt_meer_subagents_zonder_model_voor(monkeypatch):
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))
    monkeypatch.setattr(supervisie, "_regelingtitels", lambda _g: regelingen)
    state = {**STATE, "question": AGENTSET["M01"]["opdracht"], "modus": "auto", "agentvorm": "centraal",
             "bronstand": AAN, "gesprek_id": "g1"}
    upd = supervisie._kies(_bouw(), state)
    assert upd["specialist"] == "subagent_plan" and supervisie._entry_node(_bouw(), upd) == "subagent_plan"
    assert [o["profiel"] for o in upd["subagent_plan"]] == ["bepalingen_duiden"] * 3
    # Kan er geen kind starten (geen gesprek), dan beantwoordt de centrale agent de vraag zelf.
    upd = supervisie._kies(_bouw(), {**state, "gesprek_id": ""})
    assert upd["specialist"] == "centraal"


def test_de_supervisor_geeft_een_reeks_in_de_graaf_aan_een_subagent(monkeypatch):
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))
    monkeypatch.setattr(supervisie, "_regelingtitels", lambda _g: regelingen)
    state = {**STATE, "question": AGENTSET["S03"]["opdracht"], "modus": "auto", "agentvorm": "centraal",
             "bronstand": {}, "gesprek_id": "g1"}
    upd = supervisie._kies(_bouw(), state)
    assert upd["specialist"] == "subagent_route" and upd["subagent_plan"][0]["profiel"] == "bepalingen_duiden"
    assert upd["subagent_plan"][0]["opdracht"]["doel"] == AGENTSET["S03"]["opdracht"]


# 2. Vragen naar boven --------------------------------------------------------------------------------------------------

def test_v02_en_v03_zijn_geen_bronselectie():
    """V02 noemt een deelvraag bij haar onderwerp: de bronselectie zou stil bij de volgende deelvraag verder zoeken. V03
    vraagt wat de memorie van toelichting zegt: een connector, geen bronselectie. Beide gaan naar de centrale agent, die
    het dossier leest."""
    assert not is_bronselectievraag(AGENTSET["V02"]["opdracht"])
    assert not is_bronselectievraag(AGENTSET["V03"]["opdracht"])
    for vraag in ("Zoek per deelvraag de bronnen.", "Help mij de bronnen bij dit werkgebied te bepalen",
                  "Zoek de bronnen bij deelvraag 2", AGENTSET["M05"]["opdracht"]):
        assert is_bronselectievraag(vraag), vraag


# 3. De controle per stuk -----------------------------------------------------------------------------------------------

PHR = "ECLI:NL:PHR:2025:435"
PHR_PASSAGES = ("De hiervoor genoemde lichtpuntjes breng ik in beeld in hoofdstuk 7. Het eerste lichtpuntje wordt gevormd "
                "door het oordeel dat ook andere omstandigheden dan overmacht kunnen leiden tot het oordeel dat het niet "
                "melden niet aan de bestuurder is te wijten. Als tweede lichtpuntje is in de literatuur gesuggereerd dat "
                "een lichtere bewijslast geldt. Daar ben ik het niet mee eens. De bewijsmaatstaf was aannemelijk maken en "
                "dat blijft zo.")
PHR_ANTWOORD = (f"**Conclusie AG 11 april 2025 ({PHR}) – vervolg na het antwoord van het HvJ EU**\n"
                "Hij formuleert vijf lichtpuntjes: (1) ook andere omstandigheden dan overmacht kunnen ertoe leiden dat "
                "het niet melden niet aan de bestuurder te wijten is; (2) de bewijsmaatstaf blijft aannemelijk maken.\n"
                "Meer detail is niet beschikbaar zonder het stuk opnieuw te lezen.")


def _oordeel(bevestigd: bool = True, **o) -> FakeLLM:
    """Het oordeel van de controle, en de tweede lezing (sinds A6 run 3) die het bevestigt of niet."""
    return FakeLLM([response([tool_block("o", "oordelen", {"oordelen": [{"stuk": 1, "zin": 1, **o}]})], "tool_use"),
                    response([tool_block("b", "bevestiging", {"gevallen": [
                        {"geval": 1, "zelfde_onderwerp": bevestigd, "omgekeerd": bevestigd}]})], "tool_use")])


def test_de_kop_en_een_zin_over_het_lezen_gaan_niet_naar_de_controle_per_stuk():
    [stuk] = stukcontrole.te_controleren(PHR_ANTWOORD, {PHR: PHR_PASSAGES}, [])
    assert len(stuk["zinnen"]) == 1 and stuk["zinnen"][0].startswith("Hij formuleert vijf lichtpuntjes")


#: Het zinsdeel dat de tegenspraak aanwijst (sinds A6 run 2 verplicht, `tests/test_a6_run2.py`).
DEEL = "de bewijsmaatstaf blijft aannemelijk maken"


def test_een_tegenspraak_zonder_aangewezen_passage_is_geen_bewering():
    """PHR:2025:435 in S01: `spreekt_tegen` op een zin die de passages wel dragen. Zonder letterlijke passage die het
    tegendeel zegt, is het oordeel geen bewering. Met zo'n passage wel, en dan staat die passage in de bewering, zodat
    de correctieronde weet wat er niet klopt."""
    steun = {PHR: PHR_PASSAGES}
    for tegen in ("", "niet", "het stuk noemt maar twee lichtpuntjes"):   # leeg, één woord, niet uit de passages
        assert stukcontrole.controleer(_oordeel(oordeel="spreekt_tegen", deel=DEEL, tegen=tegen), make_settings(), PHR_ANTWOORD,
                                       steun, []) == []
    [bewering] = stukcontrole.controleer(_oordeel(oordeel="spreekt_tegen", deel=DEEL, tegen="Daar ben ik het niet mee eens."),
                                         make_settings(), PHR_ANTWOORD, steun, [])
    assert bewering.startswith(f"duiding van {PHR} die de passages van dat stuk tegenspreekt")
    assert "(de passage: 'Daar ben ik het niet mee eens.')" in bewering
    # Andere aanhalingstekens en spaties in het fragment tellen niet als verschil.
    assert stukcontrole.aangewezen("de  bewijsmaatstaf was ‘aannemelijk maken’", "De bewijsmaatstaf was 'aannemelijk maken'.")


def test_het_schema_vraagt_de_passage_bij_elk_oordeel():
    rij = stukcontrole.schema()["input_schema"]["properties"]["oordelen"]["items"]
    assert "tegen" in rij["required"] and rij["properties"]["tegen"] == {"type": "string"}


# 4. Onbevestigd na een rapport -----------------------------------------------------------------------------------------

HR563 = "ECLI:NL:HR:2023:563"
STEUN_563 = ("Invordering; art. 36 IW 1990, art. 2:248 BW; aansprakelijkstelling door de ontvanger na een schikking met "
             "de curator. Na de opheffing van de faillissementen heeft de Ontvanger een onderzoek ingesteld.")


@pytest.mark.parametrize("zin", [
    "De passages die de subagent ophaalde dragen geen inhoudelijke duiding over de invorderingsrente in deze zaak.",
    "Meer detail is niet beschikbaar zonder het stuk opnieuw te lezen, want de subagent las het maar half.",
    "Meer valt uit de beschikbare informatie over deze zaak en haar achtergrond niet brongetrouw te zeggen.",
    "De passages die de subagent aanwees, droegen de samenvatting van dit arrest over de melding niet volledig.",
])
def test_een_zin_over_wat_de_passages_niet_opleveren_is_geen_duiding(zin):
    tekst = f"**Hoge Raad 14 april 2023 ({HR563})**\n{zin}"
    assert gelezen.zonder_steun(tekst, {HR563: STEUN_563}, []) == []


def test_een_duiding_met_verslagwoorden_rust_op_haar_inhoud():
    """S01: "Het rapport vermeldt dat dit stuk gaat over …" telde "rapport" en "vermeldt" als woorden die de passages
    moesten dragen. Een duiding die de passages niet dragen, blijft een bewering."""
    goed = (f"**Hoge Raad 14 april 2023 ({HR563})**\nHet rapport vermeldt dat dit stuk gaat over aansprakelijkstelling "
            "door de ontvanger na een schikking met de curator op grond van art. 2:248 BW.")
    assert gelezen.zonder_steun(goed, {HR563: STEUN_563}, []) == []
    fout = (f"**Hoge Raad 14 april 2023 ({HR563})**\nHet rapport vermeldt dat de Hoge Raad de bestuurder vrijpleit omdat "
            "hij tijdig betalingsonmacht meldde bij de inspecteur en de ontvanger.")
    assert gelezen.zonder_steun(fout, {HR563: STEUN_563}, []) == [
        f"duiding van {HR563} die de passages van dat stuk niet dragen"]


# 5. E09: een gelezen artikel zonder passage ----------------------------------------------------------------------------

ELF = "urn:bwb:BWBR0004770:artikel:11"
ZIN_11 = "De belastingschuldige wordt door de ontvanger aangemaand om alsnog binnen twee weken te betalen."


def elf() -> tuple[str, str]:
    rij = {"lid": ELF, "nummer": "", "tekst": ZIN_11}
    return "get_artikel", json.dumps({"status": "ok", "volledig": True, "aantal": 1, "artikel": {"iri": ELF, "delen": 1},
                                      "resultaten": [rij]})


def test_de_weigering_voor_een_gelezen_artikel_geeft_de_plek_en_die_is_over_te_nemen():
    trace = [tien(), elf()]
    with pytest.raises(Onvulbaar) as fout:
        vul("antwoord_duiding", duiding(twijfel=["Artikel 11 kent een eigen termijn van twee weken."]), trace)
    melding = str(fout.value)
    assert fout.value.code == "genoemd_gelezen" and "terwijl de tekst al is opgehaald" in melding
    plek = f"bepaling {ELF}, van „De belastingschuldige wordt door de ontvanger”, tot „alsnog binnen twee weken te betalen.”"
    assert plek in melding
    # Wat de melding geeft, vult het sjabloon in één keer.
    invoer = duiding(twijfel=["Artikel 11 kent een eigen termijn van twee weken."])
    invoer["onderbouwing"].append({"bepaling": ELF, "van": "De belastingschuldige wordt door de ontvanger",
                                   "tot": "alsnog binnen twee weken te betalen.", "waarom": "De aanmaning."})
    antwoord = vul("antwoord_duiding", invoer, trace)
    assert {c.vindplaats.iri for c in antwoord.blokken[1].items} >= {TIEN_1, ELF}
