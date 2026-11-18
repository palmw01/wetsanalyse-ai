"""De meting van de proef `model_kiest` (pilot LB3): welke sets ze meet en dat ze zonder commit niet start. Zonder model
en zonder graaf; de meting zelf draait alleen met akkoord, via `azure-infra` → `eval` → `bronselectie_model`."""
from __future__ import annotations

import pytest

from eval import bronselectie_model_meting as m


def test_de_sets_hebben_deelvragen_en_een_verwachting():
    sets = m.sets(m.lezer(True))
    assert [n for n, _ in sets] == [*m.SETS, *m.CASUSSEN]
    for naam, s in sets:
        assert s["deelvragen"], naam
        assert s["verwacht"], naam
        assert {v["deelvraag"] for v in s["verwacht"]} <= set(range(len(s["deelvragen"]))), naam


def test_zonder_commit_start_de_meting_niet(monkeypatch):
    monkeypatch.delenv("LEX_REVISIE", raising=False)
    with pytest.raises(SystemExit, match="LEX_REVISIE"):
        m.lezer(False)


def test_de_routes_bestaan():
    assert m.STANDAARD in m.ROUTES


def test_geen_eval_rekent_zelf_de_wortel_uit():
    """In het image staat een eval op `/app/eval/`: vier mappen omhoog bestaat daar niet en brak de meting bij het
    importeren (17 nov 2026, IndexError). De wortel komt uit één helper, `eval/wortel.py`."""
    from pathlib import Path

    evals = Path(__file__).resolve().parents[2] / "eval"
    fout = [p.name for p in evals.glob("*.py") if p.name != "wortel.py" and "parents[3]" in p.read_text(encoding="utf-8")]
    assert not fout, f"reken de wortel niet zelf uit, gebruik eval.wortel: {fout}"


def test_afval_per_bepaling(monkeypatch):
    """Per nodige bepaling waar ze afviel: niet gevonden, gevonden maar niet bij de 40, bij de 40 maar niet gekozen,
    gekozen. Een aanverwante bepaling telt niet."""
    import eval.bronselectie_eval as be

    monkeypatch.setattr(be, "_pool", lambda graaf, s, vraag, profiel=None: ["urn:bwb:X:artikel:2", "urn:bwb:X:artikel:3"])
    s = {"naam": "S", "deelvragen": ["v1"], "regelingen": ["X"],
         "verwacht": [{"deelvraag": 0, "bron_iri": f"urn:bwb:X:artikel:{n}", "rol": rol}
                      for n, rol in ((1, "kern"), (2, "kern"), (3, "afhankelijkheid"), (4, "kern"), (5, "aanverwant"))]}
    spoor = [{"set": "S", "vraag": "v1", "kandidaten": ["urn:bwb:X:artikel:3", "urn:bwb:X:artikel:4:lid:1"],
              "gekozen": ["urn:bwb:X:artikel:4:lid:1"], "terugval": False}]
    uit = m.afval(None, s, spoor)
    assert uit["telling"] == {"niet gevonden": 1, "gevonden, niet bij de 40": 1, "bij de 40, niet gekozen": 1,
                              "gekozen": 1}


def test_de_varianten_zijn_vlaggen_van_het_zoekprofiel():
    from agent.deelvraag_zoeken import Zoekprofiel
    velden = set(Zoekprofiel.__dataclass_fields__)
    assert all(set(v) <= velden for v in m.VARIANTEN.values())


def test_de_kandidatenroute_begrenst_en_kost_geen_model(monkeypatch):
    import eval.bronselectie_eval as be
    from agent import deelvraag_keuze

    gezien = {}

    def nep(graph, s, vraag, profiel, cache, limit=None, wetstermen=None):
        gezien["limit"] = limit
        return deelvraag_keuze.kandidaten([{"bron_iri": f"p{i}", "label": ""} for i in range(200)], [], maximaal=limit)

    monkeypatch.setattr(be, "kandidaten_voor", nep)
    uit = be.kandidaten_route(80)(None, {"naam": "S"}, "v")
    assert gezien["limit"] == 80 and len(uit) == 80 and not any(o["buiten"] for o in uit)


def test_de_variant_wetstermen_meet_de_vlag_en_vraagt_een_model(monkeypatch):
    """De proef tegen de woordenkloof (`Zoekprofiel.wetstermen`): de variant zet de vlag, een lijst met wetstermen heeft
    in `--kandidaten` een model nodig (sinds #1707 ook zonder variant), en de termen gaan naar de kandidaten."""
    import eval.bronselectie_eval as be

    assert m.VARIANTEN["wetstermen"] == {"wetstermen": True}
    assert m.met_model("wetstermen") and m.met_model("definitie_brug") and m.met_model("")
    assert not m.met_model("zonder_wetstermen")
    gezien = {}

    def nep(graph, s, vraag, profiel, cache, limit=None, wetstermen=None):
        gezien["wetstermen"], gezien["vlag"] = wetstermen, profiel.wetstermen
        return []

    monkeypatch.setattr(be, "kandidaten_voor", nep)
    import agent.wetstermen as wt
    monkeypatch.setattr(wt, "wetstermen", lambda *a, **k: ["navordering"])
    be.kandidaten_route(40, m.VARIANTEN["wetstermen"], llm=object(), model="m")(None, {"naam": "S", "regelingen": []}, "v")
    assert gezien == {"wetstermen": ["navordering"], "vlag": True}
    be.kandidaten_route(40, m.VARIANTEN["wetstermen"])(None, {"naam": "S", "regelingen": []}, "v")
    assert gezien["wetstermen"] == [], "zonder model geen vertaling"


def test_afval_van_een_variant_zoekt_met_haar_wetstermen(monkeypatch):
    import eval.bronselectie_eval as be

    def pool(graaf, s, vraag, profiel=None, wetstermen=None):
        return ["urn:bwb:X:artikel:16"] if wetstermen else []

    monkeypatch.setattr(be, "_pool", pool)
    s = {"naam": "S", "deelvragen": ["v1"], "regelingen": ["X"],
         "verwacht": [{"deelvraag": 0, "bron_iri": "urn:bwb:X:artikel:16", "rol": "kern"}]}
    spoor = [{"set": "S", "vraag": "v1", "kandidaten": [], "gekozen": [], "terugval": False}]
    assert m.afval(None, s, spoor)["telling"]["niet gevonden"] == 1
    spoor[0]["wetstermen"] = ["navordering"]
    assert m.afval(None, s, spoor)["telling"]["gevonden, niet bij de 40"] == 1

def test_de_verkeerde_deelvraag_telt_een_nodige_bepaling_die_elders_staat():
    """LB-08: 26a hoort bij deelvraag 1 en staat bij 3. Een bepaling die bij haar eigen deelvraag staat, of die nergens
    staat, of die aanverwant is, telt niet."""
    from eval.bronselectie_eval import verkeerde_deelvraag

    s = {"verwacht": [{"deelvraag": 0, "bron_iri": "urn:bwb:X:artikel:26a", "rol": "kern"},
                      {"deelvraag": 0, "bron_iri": "urn:bwb:X:artikel:26", "rol": "kern"},
                      {"deelvraag": 1, "bron_iri": "urn:bwb:X:artikel:28", "rol": "afhankelijkheid"},
                      {"deelvraag": 1, "bron_iri": "urn:bwb:X:artikel:40", "rol": "aanverwant"},
                      {"deelvraag": 2, "bron_iri": "urn:bwb:X:artikel:99", "rol": "kern"}]}
    opties = [["urn:bwb:X:artikel:26"], ["urn:bwb:X:artikel:26a:lid:1"],
              ["urn:bwb:X:artikel:26a", "urn:bwb:X:artikel:28", "urn:bwb:X:artikel:40"]]
    assert verkeerde_deelvraag(s, opties) == [
        {"bron_iri": "urn:bwb:X:artikel:26a", "hoort_bij": 0, "staat_bij": [1, 2]},
        {"bron_iri": "urn:bwb:X:artikel:28", "hoort_bij": 1, "staat_bij": [2]}]


def test_meet_intake_telt_de_verkeerde_deelvraag():
    from eval.bronselectie_eval import meet_intake

    s = {"naam": "S", "deelvragen": ["v1", "v2"], "uitgesloten": [],
         "verwacht": [{"deelvraag": 0, "bron_iri": "urn:bwb:X:artikel:1", "rol": "kern"}]}
    r = meet_intake(None, s, {"r": lambda g, s, vraag: [{"bron_iri": "urn:bwb:X:artikel:1"}] if vraag == "v2" else []})
    assert r["r"]["verkeerde_deelvraag"] == 1 and r["r"]["recall_nodig"] == 0


def test_de_route_per_werkgebied_kiest_één_keer_per_set(monkeypatch):
    """De eerste deelvraag van een set doet de aanroep met de vereniging van de kandidaten, de andere lezen haar
    uitkomst; het spoor noemt de vereniging als kandidaten."""
    import eval.bronselectie_eval as be
    from agent import deelvraag_keuze
    from fakes import FakeLLM, response, tool_block

    lijsten = {"v1": ["urn:bwb:X:artikel:26"], "v2": ["urn:bwb:X:artikel:26a"]}
    monkeypatch.setattr(be, "kandidaten_voor", lambda graph, s, vraag, profiel, cache, limit=None, wetstermen=None: deelvraag_keuze.kandidaten(
        [{"bron_iri": i, "label": "", "tekst": "t"} for i in lijsten[vraag]], []))
    llm = FakeLLM([response([tool_block("k1", "wijs_bepalingen_toe", {"toewijzingen": [
        {"nummer": 1, "deelvraag": 1, "rol": "kern"}, {"nummer": 2, "deelvraag": 1, "rol": "kern"}]})], "tool_use")])
    spoor: list = []
    route = be.model_kiest_route(llm, "m", {}, vlaggen={"wetstermen": False}, werkgebied=True, spoor=spoor)
    s = {"naam": "S", "deelvragen": ["v1", "v2"], "buiten": ""}
    assert [o["bron_iri"] for o in route(None, s, "v1")] == ["urn:bwb:X:artikel:26", "urn:bwb:X:artikel:26a"]
    assert route(None, s, "v2") == []
    assert len(llm.calls) == 1
    assert spoor[1]["kandidaten"] == ["urn:bwb:X:artikel:26", "urn:bwb:X:artikel:26a"] and spoor[1]["gekozen"] == []


def test_de_meting_kent_de_vlag_werkgebied():
    import inspect
    assert "--werkgebied" in inspect.getsource(m.main) and m.WERKGEBIED != m.MODEL
    assert not m.WERKGEBIED.startswith(m.MODEL)


def test_de_kandidatenlijst_vraagt_een_model_als_het_profiel_wetstermen_wil():
    assert m.met_model("") is True and m.met_model("rrf") is True
    assert m.met_model("zonder_wetstermen") is False


def test_de_rangdiagnose_telt_per_vak():
    assert m._vak(None) == "niet in de lijst" and m._vak(10) == "≤80"
    assert m._vak(81) == "81–120" and m._vak(150) == "121–200" and m._vak(400) == "201–400"
    assert "--rangen" in __import__("inspect").getsource(m.main)


def test_een_variant_kan_een_andere_grens_zetten():
    assert m.variant("kandidaten_120") == ({}, 120)
    assert m.variant("rrf") == ({"menging": "rrf"}, None)


def test_de_modelroute_geeft_de_grens_door(monkeypatch):
    import eval.bronselectie_eval as be

    gezien = []
    monkeypatch.setattr(be, "kandidaten_voor", lambda graph, s, vraag, profiel, cache, limit=None, wetstermen=None: (
        gezien.append(limit) or []))
    from agent import deelvraag_keuze

    monkeypatch.setattr(deelvraag_keuze, "kies", lambda *a, **k: [])
    route = be.model_kiest_route(None, "m", {}, vlaggen={"wetstermen": False}, limit=120)
    route(None, {"naam": "S", "deelvragen": ["v"], "buiten": ""}, "v")
    assert gezien == [120]


def test_de_meting_van_de_afhankelijkheden_telt_vanuit_de_verwachte_kern(monkeypatch):
    import agent.bronnen_vinden as bv

    assert m.afhankelijkheden_configuratie("standaard+verwijzing_in") == (*m.AFHANKELIJK_STANDAARD, "verwijzing_in")
    assert m.afhankelijkheden_configuratie("standaard+lid_verwijzing") == m.AFHANKELIJK_STANDAARD
    assert "lid_verwijzing" not in m.afhankelijkheden_configuratie("standaard-lid_verwijzing")
    assert m.afhankelijkheden_configuratie("alleen opschrift") == ("opschrift",)
    gezien = {}

    def vind(graaf, invoer, methoden):
        gezien["kern"] = [k["bron_iri"] for k in invoer["kern"]]
        return {"kandidaten": [{"bron_iri": "urn:bwb:X:artikel:16"}, {"bron_iri": "urn:bwb:X:artikel:24:lid:4"}]}

    monkeypatch.setattr(bv, "vind", vind)
    s = {"naam": "S", "deelvragen": ["v"], "verwacht": [
        {"deelvraag": 0, "rol": "kern", "bron_iri": "urn:bwb:X:artikel:24:lid:3"},
        {"deelvraag": 0, "rol": "afhankelijkheid", "bron_iri": "urn:bwb:X:artikel:24:lid:4"},
        {"deelvraag": 0, "rol": "afhankelijkheid", "bron_iri": "urn:bwb:X:artikel:16:lid:1"},
        {"deelvraag": 0, "rol": "afhankelijkheid", "bron_iri": "urn:bwb:X:artikel:20:lid:1"}]}
    r = m.afhankelijkheden_per_deelvraag(None, s, ("lid_verwijzing",))
    assert gezien["kern"] == ["urn:bwb:X:artikel:24:lid:3"]
    assert (r["nodig"], r["gevonden"], r["via_artikel"], r["kandidaten"]) == (3, 1, 1, 2)
    assert r["missers"] == ["DV1 bwb:X:artikel:20:lid:1"]


def test_de_keten_neemt_op_wat_juist_is_en_telt_de_afhankelijkheden_erbij(monkeypatch):
    import agent.bronnen_vinden as bv

    assert m.afhankelijkheden_configuratie("standaard-lid_verwijzing-beleidsregel") == tuple(
        x for x in m.AFHANKELIJK_STANDAARD if x not in ("lid_verwijzing", "beleidsregel"))
    gezien = []

    def vind(graaf, invoer, methoden):
        gezien.append(([k["bron_iri"] for k in invoer["kern"]], methoden))
        extra = [{"bron_iri": "urn:bwb:X:artikel:24:lid:4"}] if "lid_verwijzing" in methoden else []
        return {"kandidaten": [{"bron_iri": "urn:bwb:X:artikel:99"}, *extra]}

    monkeypatch.setattr(bv, "vind", vind)
    s = {"naam": "S", "deelvragen": ["v", "w"], "verwacht": [
        {"deelvraag": 0, "rol": "kern", "bron_iri": "urn:bwb:X:artikel:24:lid:3"},
        {"deelvraag": 0, "rol": "afhankelijkheid", "bron_iri": "urn:bwb:X:artikel:24:lid:4"},
        {"deelvraag": 0, "rol": "aanverwant", "bron_iri": "urn:bwb:X:artikel:30"},
        {"deelvraag": 1, "rol": "kern", "bron_iri": "urn:bwb:X:artikel:5"}]}
    # Het model koos bij de eerste deelvraag het kernlid en iets verkeerds, bij de tweede niets juists.
    spoor = [{"set": "S", "vraag": "v", "gekozen": ["urn:bwb:X:artikel:24:lid:3", "urn:bwb:X:artikel:77"],
              "kandidaten": ["urn:bwb:X:artikel:24:lid:3", "urn:bwb:X:artikel:77", "urn:bwb:X:artikel:30"]},
             {"set": "S", "vraag": "w", "gekozen": ["urn:bwb:X:artikel:6"], "kandidaten": ["urn:bwb:X:artikel:6"]}]
    configuraties = {"zonder": ("opbouw",), "met": ("opbouw", "lid_verwijzing")}
    r = m.keten(None, s, spoor, configuraties)
    # Alleen wat juist is, gaat de kern in; de tweede deelvraag draait niets.
    assert [k for k, _ in gezien] == [["urn:bwb:X:artikel:24:lid:3"]] * 2
    assert (r["nodig"], r["gekozen"]) == (3, 1)
    assert r["zonder"] == {"gevonden": 1, "kandidaten": 1}
    assert r["met"] == {"gevonden": 2, "kandidaten": 2}
    # Na de laatste configuratie mist alleen de tweede deelvraag (het model koos niets juists), die er niet op stond.
    assert r["missers"] == [{"deelvraag": 2, "bron_iri": "urn:bwb:X:artikel:5", "op_de_lijst": False}]
