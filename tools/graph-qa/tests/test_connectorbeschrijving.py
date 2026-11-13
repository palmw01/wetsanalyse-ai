"""De connectorbeschrijving is de enige bron (ADR-013): een onvolledige beschrijving of handwerk ernaast wordt rood.

Een bronconnector is een beschrijving in `bronmodel.connectors`, tools in `agent/tools/` en een straatvlag. De rest
van de keten leidt af: de toollaag (`tools.CONNECTORS`), de specialisten, de api (register en toegestane namen) en de
werkplek (de groep in de bronnenlijst). Deze tests lezen ook de api en de frontend, en draaien daarom mee in
`scripts/kruistests.sh`.

De nep-connector onderaan bewijst het generieke: een connector die alleen een beschrijving en een tool heeft, komt
zonder één regel extra code in de toollaag; een profiel dat hem noemt (`.claude/lex-agents/`), krijgt zijn tools.
"""
from __future__ import annotations

import dataclasses
import re
import typing
from pathlib import Path

import pytest
from bronmodel import connectors as bm
from bronmodel.extern import BRONTYPEN, externe_vindplaats

from agent import specialists, tools
from agent.profielen import PROFIELEN, grenzen, tools_van
from agent.config import Settings
from agent.models import Connector

WORTEL = Path(__file__).resolve().parents[3]
BESCHRIJVINGEN = list(bm.CONNECTORS.values())
IDS = [c.naam for c in BESCHRIJVINGEN]

#: Gewone wetsvragen: geen enkele connector mag zich daardoor aangesproken voelen.
WETSVRAGEN = (
    "Wat staat er in artikel 9 van de Invorderingswet 1990?",
    "Wat is een belastingschuldige?",
    "Welke artikelen gaan over uitstel van betaling?",
    "Annoteer artikel 36 lid 2 van de Invorderingswet 1990",
    "Hoe verhoudt artikel 25 zich tot de Leidraad Invordering 2008?",
    "Wat voor weer wordt het morgen?",
    # Fiscale en procestaal met "uitspraak" en "rechter" die niet over rechtspraak gaat (bevinding bij #1170: op een
    # straat zonder de connector nam `_bron_uit` zo'n vraag over met "Rechtspraak staat uit").
    "Wat is een uitspraak op bezwaar?",
    "Binnen welke termijn moet de inspecteur uitspraak doen op het bezwaarschrift?",
    "Kan ik tegen de aansprakelijkstelling beroep instellen bij de rechter?",
    "Wat doet de rechter-commissaris bij een faillissement?",
    "Wanneer is de rechter bevoegd om de dwangbevelprocedure te schorsen?",
)


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_de_beschrijving_is_volledig(c: bm.ConnectorBeschrijving):
    # Een aanwijzing is alleen nodig waar een vraag naar de bron wijst zonder haar te noemen ("wat bedoelde de
    # wetgever"); de meeste connectors hebben er geen.
    # Een status-regel staat alleen bij een bron die je anders met de wet zou verwarren (een kennisgroepstandpunt).
    optioneel = {"aanwijzingen", "status_regel"}
    for veld in dataclasses.fields(c):
        if veld.init and veld.name not in optioneel:
            assert getattr(c, veld.name), f"{c.naam}: veld '{veld.name}' is leeg"
    assert re.fullmatch(r"[a-z][a-z0-9_]*", c.naam)
    assert c.brontype in BRONTYPEN and c.brontype != "wettekst"
    assert c.leestool in c.tools
    assert any(c.naam in p.connectors for p in PROFIELEN.values()), "geen profiel noemt deze connector"
    assert len(c.voorbeeldvragen) >= 3


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_de_metadata_gebruikt_de_vaste_sleutels(c: bm.ConnectorBeschrijving):
    """Een feit als de datum komt uit de dienst, in dezelfde sleutels voor elke connector: dan vult één stuk code de
    lijst, de kop van een gelezen stuk en de werkplek (gesprek e906567a, 9 nov 2026: de datum kwam uit modeltekst)."""
    sleutels = [v.sleutel for v in c.metadata]
    assert len(sleutels) == len(set(sleutels)), f"{c.naam}: een metadatasleutel dubbel"
    for v in c.metadata:
        assert v.sleutel in bm.METADATA_SLEUTELS, f"{c.naam}: '{v.sleutel}' is geen vaste sleutel"
        assert v.label and v.bron and v.betekenis, f"{c.naam}: '{v.sleutel}' mist label, bron of betekenis"
    assert {"datum", "titel", "leesbaar"} <= set(sleutels), f"{c.naam}: elke bron levert datum, titel en leesbaar"
    datum = c.veld(c.standaard_datum)
    assert datum is not None and datum.type == "datum" and datum.sorteerbaar, (
        f"{c.naam}: 'nieuwste' ordent op een sorteerbare datum uit de metadata")


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_elk_filter_is_een_argument_van_een_zoektool(c: bm.ConnectorBeschrijving):
    argumenten = {a for t in tools.TOOLS if t["name"] in c.tools - {c.leestool}
                  for a in t["input_schema"]["properties"]}
    for arg, veld in c.filters.items():
        assert arg in argumenten, f"{c.naam}: '{veld.sleutel}' filtert op '{arg}', maar geen zoektool heeft dat argument"


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_de_volgordes_zijn_de_enum_van_de_zoektool(c: bm.ConnectorBeschrijving):
    """"De laatste stukken" is een volgorde, geen bladeren door het hele dossier (gesprek e906567a: elf rondes voor een
    fout antwoord). De zoektool kent precies de volgordes uit de beschrijving, en 'nummer' alleen met een reeks."""
    assert c.volgordes and set(c.volgordes) <= set(bm.VOLGORDES)
    zoektools = [t for t in tools.TOOLS if t["name"] in c.tools - {c.leestool}]
    enums = [t["input_schema"]["properties"]["volgorde"].get("enum") for t in zoektools
             if "volgorde" in t["input_schema"]["properties"]]
    assert enums and all(e == list(c.volgordes) for e in enums), f"{c.naam}: volgorde-enum {enums} ≠ {c.volgordes}"
    if "nummer" in c.volgordes:
        assert c.veld("nummer") is not None and c.veld("reeks") is not None


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_de_tools_bestaan_en_horen_bij_een_connector(c: bm.ConnectorBeschrijving):
    bestaand = {t["name"] for t in tools.TOOLS}
    assert c.tools <= bestaand, f"{c.naam}: tools zonder implementatie: {c.tools - bestaand}"
    anderen = set().union(*(o.tools for o in BESCHRIJVINGEN if o is not c))
    assert not c.tools & anderen, "een tool hoort bij precies één connector"


def test_elke_connectortool_heeft_een_beschrijving():
    assert tools.CONNECTOR_TOOLS == frozenset().union(*(c.tools for c in BESCHRIJVINGEN))
    assert tools.CONNECTORS == {c.naam: c.tools for c in BESCHRIJVINGEN}


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_de_straat_kan_hem_aanbieden(c: bm.ConnectorBeschrijving):
    assert f"connector_{c.naam}" in Settings.model_fields, f"Settings mist connector_{c.naam}"
    config = (WORTEL / "tools" / "graph-qa" / "agent" / "config.py").read_text(encoding="utf-8")
    assert f'e.get("{c.env}")' in config, f"config.py leest {c.env} niet"
    assert Settings.model_fields[f"connector_{c.naam}"].default is False, "een connector staat standaard uit"


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_de_signalen_herkennen_zijn_vragen_en_geen_wetsvragen(c: bm.ConnectorBeschrijving):
    for v in c.voorbeeldvragen:
        assert c.herkent(v), f"{c.naam} herkent zijn eigen voorbeeldvraag niet: {v}"
    for v in WETSVRAGEN:
        assert not c.herkent(v), f"{c.naam} voelt zich aangesproken door een wetsvraag: {v}"


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_het_id_heeft_de_vorm_van_zijn_brontype(c: bm.ConnectorBeschrijving):
    for prefix in c.id_prefixen:
        voorbeeld = {"kst-": "kst-33755-3", "ECLI:": "ECLI:NL:HR:2020:1234", "CELEX:": "CELEX:32016R0679"}.get(prefix)
        if voorbeeld:
            vp = externe_vindplaats(voorbeeld)
            assert vp is not None and vp.brontype == c.brontype


def test_de_namen_in_de_contracten_zijn_de_beschrijving():
    assert set(typing.get_args(Connector)) == set(bm.CONNECTORS)
    # De api leest dezelfde namen; met de hand een Literal ernaast is drift die pas bij een nieuwe connector opvalt.
    for bestand in ("connectors.py", "gesprek_contracts.py", "werkgebied_contracts.py"):
        bron = (WORTEL / "api" / "app" / bestand).read_text(encoding="utf-8")
        assert "from bronmodel.connectors import" in bron, f"api/app/{bestand} leidt de namen niet af"
        for c in BESCHRIJVINGEN:
            assert f'Literal["{c.naam}"]' not in bron, f"api/app/{bestand}: '{c.naam}' met de hand"


def test_geen_profiel_noemt_een_connectortool_met_de_hand():
    """Een profiel noemt de connector; diens tools volgen uit de beschrijving. Het register weigert de andere weg."""
    assert not grenzen().tools & tools.CONNECTOR_TOOLS
    for naam, p in PROFIELEN.items():
        assert not set(p.tools or ()) & tools.CONNECTOR_TOOLS, f"{naam} noemt een connectortool"


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_de_rollen_krijgen_zijn_tools(c: bm.ConnectorBeschrijving):
    for rol, p in PROFIELEN.items():
        spec = specialists.SPECIALISTS[rol]
        if c.naam in p.connectors:
            assert spec.tools is None or c.tools <= spec.tools
        else:
            assert spec.tools is not None and not c.tools & spec.tools


def test_de_werkplek_kent_elke_groep():
    bronnen = (WORTEL / "frontend" / "lib" / "bronnen.ts").read_text(encoding="utf-8")
    naam = re.search(r"BRONTYPE_NAAM[^=]*=\s*\{([^}]*)\}", bronnen)
    assert naam, "BRONTYPE_NAAM niet gevonden"
    paren = dict(re.findall(r"(\w+):\s*\"([^\"]+)\"", naam.group(1)))
    for c in BESCHRIJVINGEN:
        assert paren.get(c.brontype) == c.groep, f"de werkplek noemt {c.brontype} anders dan de beschrijving"


# --- het generieke bewijs -------------------------------------------------------------------------------------

def test_een_nieuwe_connector_komt_er_zonder_code_bij(monkeypatch):
    """Een beschrijving en een tool: de toollaag, het filter en de specialisten volgen vanzelf."""
    nep = bm.ConnectorBeschrijving(
        naam="testbron", label="Testbron", brontype="uitspraak", groep="Uitspraken",
        dekt="uitspraken van een testgerecht", signalen=(r"\btestgerecht\b",), tools=frozenset({"zoek_testbron"}),
        leestool="zoek_testbron", lees_argument="id", id_prefixen=("ECLI:",),
        rol_in_antwoord="een uitspraak onderbouwt een uitleg, nooit wat de wet zegt", kop_in_antwoord="Uit de testrechtspraak", levert=("uitspraken",), niet_in_tekst=(),
        werkwoorden={"zoek_testbron": ("zoekt uitspraken over „{zoekterm}”", "zoekt uitspraken")}, grenzen="alleen een test",
        beheer="Een nep-connector.", voorbeeldvragen=("Wat zei het testgerecht?",))
    assert nep.herkent("Wat zei het testgerecht hierover?") and nep.herkent("Lees ECLI:NL:HR:2020:1234")
    assert not nep.herkent(WETSVRAGEN[0])

    monkeypatch.setitem(bm.CONNECTORS, nep.naam, nep)
    monkeypatch.setattr(tools, "CONNECTORS", {c.naam: c.tools for c in bm.CONNECTORS.values()})
    monkeypatch.setattr(tools, "CONNECTOR_TOOLS", frozenset().union(*tools.CONNECTORS.values()))
    assert "testbron" in bm.herkende("Wat zei het testgerecht?")
    # Het filter: uit tenzij de straat hem aanbiedt én de beurt hem kiest.
    uit = tools.toegestane_tools(frozenset({"zoek_testbron", "get_lid"}), Settings(), None)
    assert uit == {"get_lid"}
    aan = Settings().model_copy(update={"connector_testbron": True})
    assert tools.toegestane_tools(frozenset({"zoek_testbron"}), aan, ["testbron"]) == {"zoek_testbron"}
    assert tools.toegestane_tools(frozenset({"zoek_testbron"}), aan, []) == frozenset()
    # De profielen: het profiel dat de connector noemt krijgt de tool, een ander niet.
    duiding = PROFIELEN["duiding"]
    assert "zoek_testbron" in tools_van(duiding.model_copy(update={"connectors": (*duiding.connectors, "testbron")}))
    assert "zoek_testbron" not in tools_van(PROFIELEN["definitie"])
    # De dispatch: een module in het register, en `dispatch` voert de tool uit met de bron van die connector – zonder
    # één regel in `tools/__init__.py` (vroeger een tak, een singleton en een argument per connector).
    from agent.tools.connectortools import ConnectorModule

    class NepFout(RuntimeError):
        pass

    module = ConnectorModule(
        naam="testbron", tools=[{"name": "zoek_testbron", "description": "x", "input_schema": {"type": "object"}}],
        maak_bron=lambda _s: "de bron van het proces",
        dispatch=lambda n, a, bron, _g: (_ for _ in ()).throw(NepFout("weg")) if a.get("stuk") else f"{n}:{bron}",
        fout=NepFout, fout_van=lambda exc: f"fout:{exc}", foutredenen={})
    monkeypatch.setitem(tools.CONNECTORMODULES, "testbron", module)
    monkeypatch.setitem(tools._BY_NAME, "zoek_testbron", module.tools[0])
    monkeypatch.setattr(tools, "TOOLS", tools.TOOLS + module.tools)  # wat het register bij het importeren doet
    assert tools.dispatch("zoek_testbron", None, {}, aan, bronnen=["testbron"]) == "zoek_testbron:de bron van het proces"
    assert tools.dispatch("zoek_testbron", None, {}, aan, bronnen=["testbron"], testbron="nep") == "zoek_testbron:nep"
    assert tools.dispatch("zoek_testbron", None, {"stuk": 1}, aan, bronnen=["testbron"]) == "fout:weg"
    assert '"connector_uit"' in tools.dispatch("zoek_testbron", None, {}, aan, bronnen=[])


def test_het_register_kent_elke_connector_en_elke_reden_heeft_een_zin():
    """Eén module per beschrijving, met precies haar tools; en elke reden die een module uit een fout van zijn bron
    maakt, heeft een zin in het denkproces (`REDEN_ZIN`) – anders heet hij "gaf een fout"."""
    from agent.resultaat import REDEN_ZIN

    assert set(tools.CONNECTORMODULES) == set(bm.CONNECTORS)
    for naam, m in tools.CONNECTORMODULES.items():
        assert m.tool_namen == bm.CONNECTORS[naam].tools, naam
        assert set(m.foutredenen.values()) <= set(REDEN_ZIN), (naam, set(m.foutredenen.values()) - set(REDEN_ZIN))


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_elke_connector_heeft_een_live_proef(c: bm.ConnectorBeschrijving):
    """Een nepbron bevestigt niet wat de connector van de echte dienst aanneemt. Per connector staat er een live-proef
    in `tests/test_<naam>_live.py` met de marker `live`; `bronnenwacht.yml` draait die dagelijks (ADR-013, stap 6)."""
    pad = WORTEL / "tools" / "graph-qa" / "tests" / f"test_{c.naam}_live.py"
    assert pad.exists(), f"{c.naam}: geen live-proef in {pad.name}"
    tekst = pad.read_text(encoding="utf-8")
    assert "pytest.mark.live" in tekst and 'os.environ.get("BRONNEN_LIVE")' in tekst, (
        f"{pad.name}: de proef hoort de marker `live` te dragen en zich zonder BRONNEN_LIVE over te slaan")


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_de_tools_volgen_de_naamconventie(c: bm.ConnectorBeschrijving):
    """Eén vorm per connector: `zoek_<x>` vindt, `get_<x>` leest (de leestool). Zo herkent het model een connector
    aan zijn tools; met de tweede connector toetsen we of een voorvoegsel per dienst beter werkt (Anthropic)."""
    assert c.leestool.startswith("get_"), f"{c.naam}: de leestool heet get_…"
    assert all(t.startswith("zoek_") for t in c.tools - {c.leestool}), f"{c.naam}: een zoektool heet zoek_…"


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_een_invoerfout_noemt_een_geldig_voorbeeld(c: bm.ConnectorBeschrijving):
    """Een foutmelding over de invoer zegt wat er moet en hoe geldige invoer eruitziet, zodat het model zich herstelt
    (MCP: tool execution errors; Anthropic, *Writing tools for agents*)."""
    modules = [p for p in (WORTEL / "tools" / "graph-qa" / "agent" / "tools").glob("*.py")
               if any(f'"name": "{t}"' in p.read_text(encoding="utf-8") for t in c.tools)]
    assert modules, f"{c.naam}: geen module met zijn tools"
    for pad in modules:
        bron = pad.read_text(encoding="utf-8")
        meldingen = re.findall(r'fout\(\s*"(ongeldig[a-z_]*)",\s*((?:f?"[^"]*(?:\\"[^"]*)*"\s*)+)\)', bron)
        assert meldingen, f"{pad.name}: geen invoerfouten gevonden; klopt de toets nog?"
        for reden, tekst in meldingen:
            assert "bijvoorbeeld" in tekst, f"{pad.name}: '{reden}' noemt geen voorbeeld"


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_elke_tool_heeft_een_werkwoord_voor_het_denkproces(c: bm.ConnectorBeschrijving):
    """Acceptatie 8 nov 2026: Lex las kst-35496-F en het denkproces zei "raadpleegt de kennisgraaf"."""
    from agent.narratie import _toolregel

    assert set(c.werkwoorden) == set(c.tools), "elke tool van de connector een werkwoord, en niet meer"
    for tool, vormen in c.werkwoorden.items():
        assert vormen and all(isinstance(v, str) and v for v in vormen)
        assert "kennisgraaf" not in _toolregel({"name": tool, "input": {}})
        assert "{" not in _toolregel({"name": tool, "input": {}}), "zonder argumenten blijft er geen gat staan"


@pytest.mark.parametrize("c", BESCHRIJVINGEN, ids=IDS)
def test_de_capaciteit_spreekt_zichzelf_niet_tegen(c: bm.ConnectorBeschrijving):
    assert c.levert, "wat de leestool levert"
    assert not {w.split()[0] for w in c.levert} & {w.split()[0] for w in c.niet_in_tekst}


def test_de_algemene_stappen_noemen_de_bronnen_van_de_beurt():
    from agent import bronstand

    stand = bronstand.bepaal(Settings(), None)
    assert bronstand.waar(stand) == "de kennisgraaf"
    stand["kamerstukken"].update(aan=True, reden="aan")
    assert bronstand.waar(stand) == "de wetgeving en Kamerstukken"


def test_genoemde_stukken_staan_in_de_volgorde_van_de_tekst_ook_in_kleine_letters():
    """De plek komt uit het patroon: `find` op de canonieke vorm vond "ecli:nl:hr:2022:50" niet (-1) en zette hem vooraan."""
    gevonden = bm.genoemde_stukken("Vergelijk kst-33755-3 met ecli:nl:hr:2022:50")
    assert [i for _, i in gevonden] == ["kst-33755-3", "ECLI:NL:HR:2022:50"]
