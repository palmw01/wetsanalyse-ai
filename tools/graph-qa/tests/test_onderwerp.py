"""Vraag Lex op een object (spoor F, F3b): het contract (`Onderwerp`, `actie`), het contextblok per soort
uit de api, de focus voor vervolgvragen en de weg naar supervisor en specialist."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.focus import als_context, bij_advies, bij_onderwerp
from agent.agents import register
from agent.models import ACTIE_TAAK, ChatRequest, Onderwerp
from agent.onderwerp import als_blok, haal
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block

API = Path(__file__).resolve().parents[3] / "api" / "app"

WG = {
    "id": "wg1", "naam": "Invordering",
    "deelvragen": [
        {"id": "dv1", "vraag": "Wanneer is een aanslag invorderbaar?", "status": "actief", "herkomst": "lex",
         "bronnen": ["s9"], "begrippen": ["b1"]},
        {"id": "dv2", "vraag": "Wie betaalt?", "status": "actief", "herkomst": "analist", "bronnen": [], "begrippen": []},
    ],
    "bronnen": [{"id": "s9", "bron_iri": "urn:bwb:BWBR0004770:artikel:9", "label": "Artikel 9 – Invorderingswet 1990",
                 "rol": "analyseren", "bereik": "onderliggend", "reden": "De kern van de termijn."}],
}
DEKKING = {"deelvragen": [{"id": "dv1", "vraag": "…", "stand": "geen_begrip",
                           "bronnen": [{"id": "s9", "label": "Artikel 9"}],
                           "begrippen": [{"id": "b1", "naam": "termijn", "status": "concept"}]}],
           "telling": {}, "totaal": 1}
KANDIDATEN = {"kandidaten": [{"id": "k1", "bron_iri": "urn:bwb:BWBR0004770:artikel:8", "label": "Artikel 8",
                              "rol": "afhankelijkheid", "status": "open", "reden": "",
                              "bewijs": [{"methode": "verwijzing_uit", "vanuit": "Artikel 9, lid 1",
                                          "detail": {"functie": "uitzondering", "anker": "artikel 8"}}]}]}
BEGRIP = {"id": "b1", "status": "concept",
          "inhoud": {"naam": "termijn", "alternatieve_termen": ["betalingstermijn"], "definitie": ""},
          "koppelingen": [{"beoordeling": "akkoord", "bewijs": {"tekst": "binnen een maand", "klasse": "Tijdsaanduiding",
                                                                  "vindplaats": "art. 9 lid 1"}},
                          {"beoordeling": "afgewezen", "bewijs": {"tekst": "WEG", "klasse": "x"}}]}
VOORSTELLEN = {"voorstellen": [{"veld": "definitie", "actie": "scherper", "status": "open"},
                               {"veld": "voorbeelden", "actie": "voorbeelden", "status": "afgewezen"}]}


class NepApi:
    def __init__(self, faal: set[str] | None = None):
        self.faal = faal or set()
        self.calls: list[str] = []

    async def _geef(self, naam, waarde):
        self.calls.append(naam)
        if naam in self.faal:
            raise RuntimeError(naam)
        if f"verwijderd:{naam}" in self.faal:
            # Echt gewist (de api geeft een 404 met de verwijderd-stand): net als een storing geen leeg blok.
            from agent.wetsanalyse_api import WetsanalyseApiFout
            raise WetsanalyseApiFout("GET → 404", 404)
        return waarde

    async def haal_werkgebied(self, wid):
        return await self._geef("werkgebied", WG)

    async def haal_deelvragen_dekking(self, wid):
        return await self._geef("dekking", DEKKING)

    async def haal_kandidaten(self, wid):
        return await self._geef("kandidaten", KANDIDATEN)

    async def haal_begrip(self, wid, bid):
        return await self._geef("begrip", BEGRIP)

    async def haal_kaartvoorstellen(self, wid, bid):
        return await self._geef("voorstellen", VOORSTELLEN)


def _blok(onderwerp: dict, api: NepApi | None = None) -> str:
    return asyncio.run(haal(api or NepApi(), onderwerp))


# --- Het contract ----------------------------------------------------------------------------------

def test_een_onderwerp_draagt_soort_en_ids_en_een_object_heeft_een_id():
    o = Onderwerp(soort="deelvraag", werkgebied_id="wg1", id="dv1", label="Wanneer?")
    assert o.model_dump() == {"soort": "deelvraag", "werkgebied_id": "wg1", "id": "dv1", "label": "Wanneer?"}
    assert Onderwerp(soort="werkgebied", werkgebied_id="wg1").id == ""
    with pytest.raises(ValidationError):
        Onderwerp(soort="begrip", werkgebied_id="wg1")
    with pytest.raises(ValidationError, match="soort"):
        Onderwerp(soort="markering", werkgebied_id="wg1", id="e1")  # blijft de adviesvraag
    with pytest.raises(ValidationError):
        Onderwerp(soort="bron", werkgebied_id="../x", id="s9")


@pytest.mark.parametrize("actie", sorted(ACTIE_TAAK))
def test_een_actie_is_een_taak_van_een_agent(actie):
    agent, taak = ACTIE_TAAK[actie]
    assert register.is_taak(agent, taak)
    r = ChatRequest(question="Zoek bepalingen", actie=actie, werkgebied_id="wg1")
    # Alleen het werkgebied (of zijn deelvragen) annoteren is een eigen stroom; de rest gaat langs de supervisor.
    annoteren = actie in ("werkgebied_annoteren", "deelvragen_annoteren")
    assert r.modus == ("werkgebied_annoteren" if annoteren else "auto")
    assert r.bereik == ("deelvragen" if actie == "deelvragen_annoteren" else "werkgebied")
    # Met het werkgebied uit het onderwerp, als de werkplek er niet al in staat.
    r = ChatRequest(question="…", actie=actie, onderwerp={"soort": "werkgebied", "werkgebied_id": "wg2"})
    assert r.werkgebied_id == "wg2"


def test_een_actie_sluit_modus_doel_en_kaartje_uit_en_vraagt_een_werkgebied():
    with pytest.raises(ValidationError, match="actie' of 'modus"):
        ChatRequest(question="x", actie="bronnen_zoeken", modus="advies", werkgebied_id="wg1")
    with pytest.raises(ValidationError, match="kiest zelf"):
        ChatRequest(question="x", actie="bronnen_zoeken", werkgebied_id="wg1",
                    doel={"bwbId": "BWBR0004770", "artikel": "9"})
    with pytest.raises(ValidationError, match="werkgebied_id"):
        ChatRequest(question="x", actie="werkgebied_annoteren")
    with pytest.raises(ValidationError, match="werkgebied_id"):
        ChatRequest(question="x", actie="dekking")
    with pytest.raises(ValidationError):
        ChatRequest(question="x", actie="iets_anders", werkgebied_id="wg1")


def test_bevestigd_mag_bij_de_acties_die_bevestiging_vragen():
    r = ChatRequest(question="x", actie="werkgebied_annoteren", werkgebied_id="wg1", bevestigd=3)
    assert r.is_werkgebied_annotatie and r.bevestigd == 3
    assert ChatRequest(question="x", actie="begrippen_meedenken", werkgebied_id="wg1", bevestigd=2).bevestigd == 2
    with pytest.raises(ValidationError, match="bevestigd"):
        ChatRequest(question="x", actie="bronnen_zoeken", werkgebied_id="wg1", bevestigd=1)


def test_alleen_het_werkgebied_annoteren_is_nog_een_harde_route():
    assert ChatRequest(question="hallo", actie="werkgebied_annoteren", werkgebied_id="wg1").is_werkgebied_annotatie
    # Een getypte vraag is nooit een harde route meer: de supervisor kiest.
    assert not ChatRequest(question="Annoteer het werkgebied", werkgebied_id="wg1").is_werkgebied_annotatie


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    import api.main as main

    gestart: list[dict] = []

    async def nep_stroom(question, conversation_id=None, **kw):
        gestart.append({"vraag": question, **kw})
        yield {"type": "done"}

    monkeypatch.setattr(main.settings, "graphdb_token", "test", raising=False)
    monkeypatch.setattr(main.settings, "graphdb_mcp_url", "https://graaf.test/mcp", raising=False)
    monkeypatch.setattr(main, "answer_stream", nep_stroom)
    monkeypatch.setattr(main, "runs", type(main.runs)())
    with TestClient(main.app) as c:
        yield c, main, gestart


def test_een_klik_op_een_suggestie_gaat_met_zijn_actie_de_beurt_in(client, monkeypatch):
    c, main, gestart = client
    monkeypatch.setattr(type(main.settings), "legt_zelf_vast", property(lambda _s: True))
    main.app.dependency_overrides[main._budget_check] = lambda: None
    try:
        r = c.post("/v1/runs", json={"question": "Stel begrippen voor bij dit werkgebied", "conversation_id": "g1",
                                     "actie": "begrippen_voorstellen",
                                     "onderwerp": {"soort": "werkgebied", "werkgebied_id": "wg1"}})
        assert r.status_code == 201
        for _ in range(50):
            if gestart:
                break
            asyncio.run(asyncio.sleep(0.02))
        [beurt] = gestart
        assert (beurt["actie"], beurt["werkgebied_id"], beurt["modus"]) == ("begrippen_voorstellen", "wg1", "auto")
    finally:
        main.app.dependency_overrides.clear()


def test_chat_weigert_een_actie_op_een_werkgebied(client):
    c, _main, _ = client
    r = c.post("/v1/chat", json={"question": "x", "actie": "begrippen_voorstellen", "werkgebied_id": "wg1"})
    assert r.status_code == 422


# --- Het blok per soort ----------------------------------------------------------------------------

def test_een_deelvraag_met_stand_en_wat_eraan_gekoppeld_is():
    blok = _blok({"soort": "deelvraag", "werkgebied_id": "wg1", "id": "dv1"})
    assert blok.startswith("\n\nAANGEWEZEN IN DE WERKPLEK") and "geen opdracht" in blok
    assert 'Deelvraag: "Wanneer is een aanslag invorderbaar?"' in blok and "voorgesteld door Lex" in blok
    assert "Stand: nog geen geaccordeerd begrip" in blok
    assert "- Artikel 9 – Invorderingswet 1990" in blok and "- termijn (concept)" in blok
    assert "ONDERWERP" not in blok, "dat woord draagt in de systeemprompt de onderwerp-afbakening"


def test_een_deelvraag_zonder_dekking_staat_er_toch():
    blok = _blok({"soort": "deelvraag", "werkgebied_id": "wg1", "id": "dv2"}, NepApi({"dekking"}))
    assert 'Deelvraag: "Wie betaalt?"' in blok and "Stand:" not in blok


def test_een_bronselectie_met_rol_reden_en_deelvragen():
    blok = _blok({"soort": "bron", "werkgebied_id": "wg1", "id": "s9"})
    assert "bronnode urn:bwb:BWBR0004770:artikel:9" in blok and "Rol: analyseren" in blok
    assert "Reden van opnemen: De kern van de termijn." in blok
    assert '- "Wanneer is een aanslag invorderbaar?"' in blok and "Wie betaalt?" not in blok


def test_een_kandidaat_met_het_bewijs():
    blok = _blok({"soort": "kandidaat", "werkgebied_id": "wg1", "id": "k1"})
    assert "Kandidaat van Lex: Artikel 8" in blok and "Voorgestelde rol: afhankelijkheid · besluit: open" in blok
    assert "- verwijzing_uit vanuit Artikel 9, lid 1 (functie: uitzondering)" in blok


def test_een_begrip_is_een_analyse_uitkomst_met_passages_en_open_voorstellen():
    blok = _blok({"soort": "begrip", "werkgebied_id": "wg1", "id": "b1"})
    assert "Begrip: termijn (status concept) – een analyse-uitkomst, geen wettelijke definitie" in blok
    assert "Alternatieve termen: betalingstermijn" in blok and "Definitie op de kaart: nog geen" in blok
    assert '"binnen een maand" · Tijdsaanduiding · art. 9 lid 1' in blok and "WEG" not in blok
    assert "- definitie (scherper)" in blok and "voorbeelden" not in blok


def test_het_werkgebied_zelf_vraagt_niets_extra_bij_de_api():
    api = NepApi()
    blok = _blok({"soort": "werkgebied", "werkgebied_id": "wg1", "label": "Invordering"}, api)
    assert "Werkgebied: Invordering – het werkgebied zelf" in blok and api.calls == []


@pytest.mark.parametrize("onderwerp,faal", [
    ({"soort": "deelvraag", "werkgebied_id": "wg1", "id": "weg", "label": "Oude vraag"}, set()),
    ({"soort": "begrip", "werkgebied_id": "wg1", "id": "b1", "label": "termijn"}, {"begrip"}),
    ({"soort": "kandidaat", "werkgebied_id": "wg1", "id": "k1", "label": "Artikel 8"}, {"kandidaten"}),
    ({"soort": "begrip", "werkgebied_id": "wg1", "id": "b1", "label": "termijn"}, {"verwijderd:begrip"}),
    ({"soort": "deelvraag", "werkgebied_id": "wg1", "id": "d1", "label": "Wie betaalt?"}, {"verwijderd:werkgebied"}),
])
def test_onbekend_of_een_storing_is_geen_leeg_blok(onderwerp, faal):
    blok = _blok(onderwerp, NepApi(faal))
    assert onderwerp["label"] in blok and "konden niet worden opgehaald" in blok


def test_zonder_api_noemt_het_blok_het_label():
    from agent.agent import _onderwerp_blok

    blok = asyncio.run(_onderwerp_blok(make_settings(), "u", {"soort": "bron", "werkgebied_id": "wg1", "id": "s9",
                                                                "label": "Artikel 9"}))
    assert blok == als_blok("bron", None, "Artikel 9")


# --- De focus --------------------------------------------------------------------------------------

def test_het_onderwerp_blijft_in_de_focus_voor_de_vervolgvraag():
    oud = {"bron_iri": "urn:bwb:x", "label": "art. 9", "element": {"id": "e1", "klasse": "Rechtsfeit", "tekst": "t"}}
    f = bij_onderwerp(oud, {"soort": "deelvraag", "werkgebied_id": "wg1", "id": "dv1", "label": "Wanneer?"})
    assert f["onderwerp"] == {"soort": "deelvraag", "werkgebied_id": "wg1", "id": "dv1", "label": "Wanneer?"}
    assert "element" not in f and f["bron_iri"] == "urn:bwb:x", "de markering vervalt, de bepaling blijft"
    assert "Aangewezen in de werkplek: deelvraag · Wanneer? (id dv1, werkgebied wg1)" in als_context(f, [])
    # Een markering aanwijzen vervangt het onderwerp weer.
    assert "onderwerp" not in bij_advies(f, {"element_id": "e2", "fragment": "x"})


def test_supervisor_en_specialist_krijgen_het_blok_en_de_focus_houdt_het_vast(monkeypatch, tmp_path):
    """Context, geen route: de supervisor kiest zoals altijd, met het blok in zijn systeemprompt."""
    from agent import agent as agent_mod
    from agent.agent import answer_stream

    gevraagd: list[dict] = []

    async def blok(settings, user_id, onderwerp):
        gevraagd.append(onderwerp)
        return als_blok("deelvraag", ['Deelvraag: "Wanneer is een aanslag invorderbaar?"'])

    monkeypatch.setattr(agent_mod, "_onderwerp_blok", blok)
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    llm = FakeLLM([response([text_block("WORKERS: antwoord\nSPECIALIST: duiding\nPLAN: uitleg")], "end_turn"),
                   response([text_block("Dat hangt af van de dagtekening.")], "end_turn"),
                   response([text_block("WORKERS: antwoord\nSPECIALIST: duiding\nPLAN: uitleg\nVRAAG: idem")], "end_turn"),
                   response([text_block("Nog steeds de dagtekening.")], "end_turn")])
    onderwerp = Onderwerp(soort="deelvraag", werkgebied_id="wg1", id="dv1", label="Wanneer?")

    async def run(vraag, o):
        return [e async for e in answer_stream(vraag, "g1", settings=settings, llm=llm, graph=FakeGraph(), onderwerp=o)]

    asyncio.run(run("Is deze deelvraag scherp genoeg?", onderwerp))
    assert gevraagd == [onderwerp.model_dump()]
    systemen = [str(c["system"]) for c in llm.calls]
    assert all("AANGEWEZEN IN DE WERKPLEK" in s for s in systemen), systemen
    # De vervolgvraag zonder chip: geen blok meer, wel de focus.
    asyncio.run(run("En hoe dan?", None))
    assert len(gevraagd) == 1
    vervolg = [str(c["system"]) for c in llm.calls[2:]]
    assert not any("AANGEWEZEN IN DE WERKPLEK" in s for s in vervolg)
    assert all("Aangewezen in de werkplek: deelvraag · Wanneer?" in s for s in vervolg), vervolg


# --- Drift tegen de api ----------------------------------------------------------------------------

def test_de_routes_die_het_blok_leest_bestaan_bij_de_api():
    """Een gewijzigd pad faalt in de werkplek niet hard maar stil (het blok zegt dan "niet opgehaald");
    daarom hier tegen de bron."""
    werkgebieden = (API / "werkgebieden.py").read_text()
    assert '"/{werkgebied_id}/deelvragen/dekking"' in werkgebieden and '"stand"' in (API / "werkgebied_deelvragen.py").read_text()
    assert '@router.get("/{begrip_id}")' in (API / "begrippen.py").read_text()
    assert '@router.get("/voorstellen")' in (API / "begrip_voorstellen.py").read_text()
    assert '@router.get("/kandidaten")' in (API / "bronnen_runs.py").read_text()
