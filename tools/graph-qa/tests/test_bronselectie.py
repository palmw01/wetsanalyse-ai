"""De bronselectie per deelvraag in het gesprek (spoor J): kaartjes uit de stand bij de api, een klik die een
besluit wordt, en hervatten zonder checkpointer. Het scenario uit de opdracht: vier deelvragen, 1 → 2, naar 4
springen, een tussenvraag, herladen en hervatten.

De nep-api bootst `GET …/bronselectie` en de twee schrijfroutes na zoals `api/app/bronselectie.py` ze
definieert (de api-kant heeft eigen tests); elk kaartje wordt getoetst tegen `Vraagkaart` van de api."""
from __future__ import annotations

import asyncio
import copy
import importlib.util
import sys
from pathlib import Path

import pytest

from agent import bronselectie as bs
from agent.models import ChatRequest, IntakeActie

ROOT = Path(__file__).resolve().parents[3]
WID = "wg-1"
VRAGEN = ["Welke algemene betalingstermijn geldt?", "Welke termijnen gelden voor voorlopige aanslagen?",
          "Welke afwijkende betalingstermijnen bestaan er?", "Wanneer wordt iedere afzonderlijke termijn invorderbaar?"]


def _api_contracten():
    spec = importlib.util.spec_from_file_location("gesprek_contracts_bs", ROOT / "api" / "app" / "gesprek_contracts.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module          # anders lost Pydantic de uitgestelde annotaties niet op
    spec.loader.exec_module(module)
    return module


GC = _api_contracten()


class NepApi:
    """Genoeg van de api om de cyclus te draaien: voortgang per deelvraag, kandidaten per deelvraag, opnemen,
    loskoppelen, fase, afronden, beoordelen, heropenen; `volgende` en de poort zoals de api ze rekent."""

    def __init__(self, vragen=VRAGEN, kandidaten=None, gezocht=True):
        self.revisie = 1
        self.ids = [f"d{i + 1}" for i in range(len(vragen))] or [bs.ANALYSEVRAAG]
        self.vragen = dict(zip(self.ids, vragen or ["Wanneer is een aanslag invorderbaar?"]))
        self.modus = "deelvragen" if vragen else "analysevraag"
        self.rijen: dict[str, dict] = {}
        self.kandidaten = kandidaten or {}                  # id → {label, rol, bij: [did], afh_van?: id}
        self.opgenomen: dict[str, dict[str, str]] = {}      # did → {kid: rol}
        self.besluiten: dict[tuple[str, str], str] = {}
        self.gezocht = gezocht
        self.verouderd = False                              # de selectie veranderde na de laatste zoekopdracht
        self.zoekopdrachten = 0
        self.aanroepen: list[tuple] = []

    def _hoort(self, kid, did):
        k = self.kandidaten[kid]
        if self.modus == "analysevraag" or did in k.get("bij", []) or kid in self.opgenomen.get(did, {}):
            return True
        return bool(k.get("afh_van")) and k["afh_van"] in self.opgenomen.get(did, {}) and self.gezocht >= 2

    def _ov(self, na=""):
        vragen = []
        for nr, did in enumerate(self.ids, start=1):
            r = self.rijen.get(did) or {"status": "niet_gestart", "fase": "kern", "open_punten": [], "revisie": 0, "geopend": 0}
            lijst = []
            for kid, k in self.kandidaten.items():
                if not self._hoort(kid, did):
                    continue
                stand = "opgenomen" if kid in self.opgenomen.get(did, {}) else self.besluiten.get((kid, did), "voorgesteld")
                lijst.append({"id": kid, "bron_iri": f"urn:bwb:BWBR0004770:artikel:{kid}", "label": k["label"],
                              "bwb_id": "BWBR0004770", "rol": k["rol"], "bewijs": [], "bewijs_soorten": ["tekst"],
                              "stand": stand, "overal": False, "elders_opgenomen": False, "reden": "", "besloten_door": None})
            telling = {s: sum(1 for x in lijst if x["stand"] == s) for s in ("voorgesteld", "later", "uitgesloten")}
            telling["opgenomen"] = len(self.opgenomen.get(did, {}))
            redenen = ([f"Er staan nog {telling['voorgesteld']} voorstellen open."] if telling["voorgesteld"] else []) + (
                ["Er staan nog onderzoekspunten open."] if r["open_punten"] else [])
            vragen.append({"id": did, "nr": nr, "vraag": self.vragen[did], **{k: v for k, v in r.items() if k != "geopend"},
                           "geopend": r["geopend"] or None, "opnieuw_bekijken": False,
                           "klaar": r["status"] in ("voorlopig_afgerond", "beoordeeld"),
                           "bronnen": [{"selectie_id": k, "rol": rol} for k, rol in self.opgenomen.get(did, {}).items()],
                           "kandidaten": lijst, "telling": telling, "beoordelen": {"mag": not redenen, "redenen": redenen}})
        bezig = [v for v in vragen if v["status"] == "in_behandeling"]
        actief = max(bezig, key=lambda v: self.rijen[v["id"]]["geopend"])["id"] if bezig else None
        return {"werkgebied_id": WID, "naam": "Betalingstermijnen", "revisie": self.revisie, "modus": self.modus,
                "deelvragen": vragen, "actief": actief, "volgende": bs_volgende(vragen, na or actief),
                "alle_klaar": all(v["klaar"] for v in vragen), "zonder_deelvraag": [],
                "zoekdekking": {"gezocht": bool(self.gezocht), "verouderd": self.verouderd, "volledig": True, "onvolledig": [],
                                "reden": "", "run_id": "r1", "status": "klaar", "methoden": {}}}

    async def haal_bronselectie(self, werkgebied_id, na=""):
        assert werkgebied_id == WID
        return copy.deepcopy(self._ov(na))

    async def zet_bronselectie_status(self, werkgebied_id, did, actie):
        self.aanroepen.append(("status", did, actie["actie"]))
        r = self.rijen.get(did)
        if actie["actie"] == "openen":
            if r is None:
                r = self.rijen[did] = {"status": "in_behandeling", "fase": "kern", "open_punten": [], "revisie": 1, "geopend": 0}
            r["geopend"] = max((x["geopend"] for x in self.rijen.values()), default=0) + 1
        else:
            from agent.wetsanalyse_api import WetsanalyseApiFout
            if actie["verwachte_revisie"] != r["revisie"]:
                raise WetsanalyseApiFout("412", 412)
            doel = {"afronden": "voorlopig_afgerond", "beoordelen": "beoordeeld", "heropenen": "in_behandeling",
                    "fase": r["status"]}[actie["actie"]]
            if actie["actie"] == "beoordelen":
                assert self._ov()["deelvragen"][self.ids.index(did)]["beoordelen"]["mag"]
            r.update(status=doel, revisie=r["revisie"] + 1)
            if actie.get("fase"):
                r["fase"] = actie["fase"]
            if actie["actie"] in ("afronden", "beoordelen"):
                r["fase"] = "afronden"
            if actie.get("open_punten") is not None:
                r["open_punten"] = actie["open_punten"]
        return await self.haal_bronselectie(werkgebied_id, na=did)

    async def besluit_bronselectie(self, werkgebied_id, did, kid, besluit):
        self.aanroepen.append(("besluit", did, kid, besluit["besluit"]))
        if besluit["besluit"] in ("opnemen", "loskoppelen"):
            assert besluit["verwachte_revisie"] == self.revisie
            self.revisie += 1
            self.verouderd = True
        if besluit["besluit"] == "opnemen":
            self.opgenomen.setdefault(did, {})[kid] = besluit.get("rol") or ""
        elif besluit["besluit"] == "loskoppelen":
            self.opgenomen.get(did, {}).pop(kid, None)
        else:
            self.besluiten[(kid, did)] = {"later": "later", "uitsluiten": "uitgesloten"}[besluit["besluit"]]
        self.rijen.setdefault(did, {"status": "in_behandeling", "fase": "kern", "open_punten": [], "revisie": 1, "geopend": 0})
        return await self.haal_bronselectie(werkgebied_id, na=did)

    async def zoek(self, did):
        self.zoekopdrachten += 1
        self.verouderd = False
        self.gezocht = 2                                   # na opnemen: ook de afhankelijkheden
        return ""


def bs_volgende(vragen, na):
    ids = [v["id"] for v in vragen]
    start = ids.index(na) + 1 if na in ids else 0
    for v in vragen[start:] + vragen[:start]:
        if not v["klaar"] and v["id"] != na:
            return v["id"]
    return None


def _run(coro):
    return asyncio.run(coro)


def _geldig(kaart):
    """Elk kaartje moet de api door: anders staat het na herladen niet meer in het gesprek."""
    GC.Vraagkaart.model_validate(kaart)
    IntakeActie.model_validate({"intake_id": kaart["intake_id"], "stap": kaart["stap"],
                                "deelvraag_id": kaart["deelvraag_id"]})
    return kaart


def _klik(api, kaart, *keuzes, actie="antwoord", tekst=""):
    uit = _run(bs.verwerk(api, {"intake_id": kaart["intake_id"], "stap": kaart["stap"], "deelvraag_id": kaart["deelvraag_id"],
                                "actie": actie, "keuzes": list(keuzes), "tekst": tekst}, api.zoek))
    if uit.get("kaart"):
        _geldig(uit["kaart"])
    return uit


def _kandidaten():
    return {"k1": {"label": "Artikel 9 lid 1", "rol": "kern", "bij": ["d1"]},
            "k2": {"label": "Artikel 9 lid 3", "rol": "kern", "bij": ["d2"]},
            "k4": {"label": "Artikel 10", "rol": "kern", "bij": ["d4"]},
            "a1": {"label": "Artikel 1 (definities)", "rol": "afhankelijkheid", "afh_van": "k1"}}


def test_vier_deelvragen_van_1_naar_2_springen_naar_4_en_hervatten():
    api = NepApi(kandidaten=_kandidaten())
    uit = _run(bs.start(api, WID, api.zoek))
    kaart = _geldig(uit["kaart"])
    assert kaart["stap"] == "bs_kies" and [o["waarde"] for o in kaart["opties"]] == ["d1", "d2", "d3", "d4"]
    assert kaart["vooringevuld"] == ["d1"] and "4 deelvragen" in " ".join(uit["zinnen"])

    # Deelvraag 1: kernbepalingen, dan wat eraan hangt, dan afronden → Hoe wil je verder? met deelvraag 2.
    uit = _klik(api, kaart, "d1")
    assert (uit["kaart"]["stap"], [o["waarde"] for o in uit["kaart"]["opties"]]) == ("bs_bepalingen", ["k1"])
    uit = _klik(api, uit["kaart"], "k1")
    assert api.opgenomen["d1"] == {"k1": "analyseren"}
    assert uit["kaart"]["stap"] == "bs_afhankelijkheden" and [o["waarde"] for o in uit["kaart"]["opties"]] == ["a1"]
    uit = _klik(api, uit["kaart"], "a1")
    assert api.opgenomen["d1"]["a1"] == "context" and uit["kaart"]["stap"] == "bs_afronden"
    uit = _klik(api, uit["kaart"], "afronden")
    verder = uit["kaart"]
    assert verder["stap"] == "bs_verder" and verder["vraag"] == "Hoe wil je verder met de bronselectie?"
    assert [o["label"] for o in verder["opties"]][:2] == ["Verder met deelvraag 2", "Deelvraag 1 verder onderzoeken"]

    # Deelvraag 2: één voorstel voor later bewaren door het niet aan te vinken – het blijft een voorstel.
    uit = _klik(api, verder, "verder:d2")
    assert uit["kaart"]["deelvraag_id"] == "d2"
    uit = _klik(api, uit["kaart"], tekst="Onderzoek ook de bijzondere invorderbaarheid.")
    assert api.rijen["d2"]["open_punten"] == [{"tekst": "Onderzoek ook de bijzondere invorderbaarheid."}]
    assert "onderzoekspunt" in " ".join(uit["zinnen"])

    # Springen naar 4 vanuit het overzicht, zonder 2 af te ronden.
    uit = _klik(api, uit["kaart"], "overzicht")
    assert uit["kaart"]["stap"] == "bs_kies"
    uit = _klik(api, uit["kaart"], "d4")
    assert uit["kaart"]["deelvraag_id"] == "d4" and api.rijen["d2"]["status"] == "in_behandeling"

    # Een tussenvraag raakt de stand niet (de node schrijft niets); herladen of een ander gesprek is opnieuw
    # beginnen bij de api: Lex weet dat we bij 4 waren, en 2 heeft haar onderzoekspunt nog.
    uit = _run(bs.start(api, WID, api.zoek))
    assert uit["kaart"]["deelvraag_id"] == "d4" and "deelvraag 4" in " ".join(uit["zinnen"])
    assert api.rijen["d2"]["open_punten"] and api.opgenomen["d1"] == {"k1": "analyseren", "a1": "context"}


def test_een_genoemde_deelvraag_gaat_voor():
    api = NepApi(kandidaten=_kandidaten())
    uit = _run(bs.start(api, WID, api.zoek, vraag="ga verder met deelvraag 4"))
    assert uit["kaart"]["deelvraag_id"] == "d4"
    uit = _run(bs.start(api, WID, api.zoek, deelvraag_id="d2"))
    assert uit["kaart"]["deelvraag_id"] == "d2"


def test_zonder_deelvragen_is_er_geen_keuzekaart():
    api = NepApi(vragen=[], kandidaten={"k1": {"label": "Artikel 9", "rol": "kern"}})
    uit = _run(bs.start(api, WID, api.zoek))
    k = _geldig(uit["kaart"])
    assert (k["stap"], k["deelvraag_id"]) == ("bs_bepalingen", bs.ANALYSEVRAAG)
    assert "geen deelvragen" in " ".join(uit["zinnen"])
    uit = _klik(api, k, "k1")
    uit = _klik(api, uit["kaart"], "beoordelen")
    assert api.rijen[bs.ANALYSEVRAAG]["status"] == "beoordeeld"
    assert [o["waarde"] for o in uit["kaart"]["opties"]] == ["controle", "heropen:analysevraag"]
    controle = _klik(api, uit["kaart"], "controle")["zinnen"][0]
    assert bs.SLOT in controle and "volledig is" in controle


def test_beoordelen_kan_niet_met_open_voorstellen_en_de_controle_zegt_het():
    api = NepApi(vragen=VRAGEN[:1], kandidaten={"k1": {"label": "Artikel 9", "rol": "kern", "bij": ["d1"]},
                                                "k2": {"label": "Artikel 10", "rol": "kern", "bij": ["d1"]}})
    k = _run(bs.start(api, WID, api.zoek, deelvraag_id="d1"))["kaart"]
    uit = _klik(api, k, "k1")
    k = uit["kaart"]
    assert k["stap"] == "bs_afronden" and "beoordelen" not in [o["waarde"] for o in k["opties"]]
    assert "1 voorstel" in k["toelichting"] or "voorstellen open" in k["toelichting"]
    uit = _klik(api, k, "beoordelen")
    assert "kan nog niet" in " ".join(uit["zinnen"]) and api.rijen["d1"]["status"] == "in_behandeling"
    uit = _klik(api, k, "afronden")
    assert api.rijen["d1"]["status"] == "voorlopig_afgerond"
    tekst = _klik(api, uit["kaart"], "controle")["zinnen"][0] if any(
        o["waarde"] == "controle" for o in uit["kaart"]["opties"]) else bs.controle_tekst(_run(api.haal_bronselectie(WID)))
    assert "nog niet beoordeeld" in tekst and bs.SLOT not in tekst


def test_een_vinkje_weghalen_koppelt_los_en_een_dubbele_klik_doet_niets_dubbel():
    api = NepApi(vragen=VRAGEN[:2], kandidaten={"k1": {"label": "Artikel 9", "rol": "kern", "bij": ["d1", "d2"]}})
    k = _run(bs.start(api, WID, api.zoek, deelvraag_id="d1"))["kaart"]
    _klik(api, k, "k1")
    _klik(api, k, "k1")                                     # oud kaartje, nog eens: al opgenomen
    assert [a for a in api.aanroepen if a[0] == "besluit"] == [("besluit", "d1", "k1", "opnemen")]
    # Hetzelfde kaartje bij deelvraag 1, nu zonder vinkje: losgekoppeld, bij 2 niets.
    api.rijen["d1"]["fase"] = "kern"
    _klik(api, {**k, "deelvraag_id": "d1"})
    assert api.opgenomen["d1"] == {} and ("besluit", "d1", "k1", "loskoppelen") in api.aanroepen


def test_geen_kandidaten_slaat_door_naar_afronden_met_een_zin():
    api = NepApi(vragen=VRAGEN[:1], kandidaten={})
    uit = _run(bs.start(api, WID, api.zoek))
    assert uit["kaart"]["stap"] == "bs_kies"
    uit = _klik(api, uit["kaart"], "d1")
    assert uit["kaart"]["stap"] == "bs_afronden" and "geen kernbepalingen" in " ".join(uit["zinnen"])


def test_nog_niet_gezocht_zoekt_eerst_en_een_onvolledige_zoekopdracht_staat_op_het_kaartje():
    api = NepApi(vragen=VRAGEN[:1], kandidaten={"k1": {"label": "Artikel 9", "rol": "kern", "bij": ["d1"]}}, gezocht=False)
    _run(bs.start(api, WID, api.zoek, deelvraag_id="d1"))
    assert api.zoekopdrachten == 1
    ov = _run(api.haal_bronselectie(WID))
    ov["zoekdekking"].update(onvolledig=["deelvraag"], volledig=False)
    k = bs.kaart_bepalingen(WID, ov, ov["deelvragen"][0])
    assert "onvolledig" in k["toelichting"]


def test_meer_dan_acht_voorstellen_noemt_de_rest():
    api = NepApi(vragen=VRAGEN[:1], kandidaten={f"k{i}": {"label": f"Artikel {i}", "rol": "kern", "bij": ["d1"]}
                                                for i in range(11)})
    k = _run(bs.start(api, WID, api.zoek))["kaart"]
    k = _klik(api, k, "d1")["kaart"]
    assert len(k["opties"]) == bs.MAX_OPTIES and "Nog 3 voorstellen staan in het paneel" in k["toelichting"]


def test_afbreken_laat_de_stand_staan():
    api = NepApi(kandidaten=_kandidaten())
    k = _klik(api, _run(bs.start(api, WID, api.zoek))["kaart"], "d1")["kaart"]
    uit = _klik(api, k, actie="afbreken")
    assert "kaart" not in uit and api.rijen["d1"]["status"] == "in_behandeling"


def test_de_actie_en_de_klik_routeren_zonder_model():
    r = ChatRequest(question="Verder met de bronselectie", actie="bronselectie", werkgebied_id=WID)
    assert r.actie == "bronselectie"
    k = IntakeActie(intake_id=bs.intake_id(WID), stap="bs_kies", deelvraag_id="")
    assert k.is_bronselectie and bs.werkgebied_van(k.intake_id) == WID


@pytest.mark.parametrize("vraag,nr", [("ga verder met deelvraag 4", 4), ("Deelvraag 12 graag", 12), ("de bronnen", None)])
def test_deelvraag_nr(vraag, nr):
    assert bs.deelvraag_nr_in(vraag) == nr


# --- door de hele beurt: supervisor → bronselectie-worker → events ------------------------------------

def _beurt(tmp_path, nep, vraag, llm=None, **kw):
    from agent.agent import answer_stream
    from fakes import FakeGraph, FakeLLM, make_settings

    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"),
                             wetsanalyse_api_url="http://api", wetsanalyse_api_token="t")
    llm = llm or FakeLLM([])

    async def run():
        return [e async for e in answer_stream(vraag, "g1", settings=settings, llm=llm, graph=FakeGraph(),
                                               werkgebied_id=WID, agent_api=lambda s, u: nep, user_id="u", **kw)]
    return asyncio.run(run()), llm


def _kaart_uit(events):
    [k] = [e["vraagkaart"] for e in events if e["type"] == "vraagkaart"]
    return _geldig(k)


def test_de_suggestie_en_een_klik_gaan_zonder_model_naar_de_bronselectie(tmp_path):
    nep = NepApi(kandidaten=_kandidaten())
    e, llm = _beurt(tmp_path, nep, "Verder met de bronselectie", actie="bronselectie")
    k = _kaart_uit(e)
    assert k["stap"] == "bs_kies" and not llm.calls
    [a] = [x["artefact"] for x in e if x["type"] == "artefact"]
    GC.Artefact.model_validate(a)
    assert a["soort"] == "bronselectie" and a["ref"]["werkgebied_id"] == WID
    klik = IntakeActie(intake_id=k["intake_id"], stap="bs_kies", keuzes=["d1"])
    e, llm = _beurt(tmp_path, nep, "1. Welke algemene betalingstermijn geldt?", intake_actie=klik)
    k = _kaart_uit(e)
    assert (k["stap"], k["deelvraag_id"]) == ("bs_bepalingen", "d1") and not llm.calls
    assert [x["artefact"]["ref"] for x in e if x["type"] == "artefact"] == [{"werkgebied_id": WID, "deelvraag_id": "d1"}]


def test_de_vaste_zin_gaat_zonder_model_naar_de_bronselectie_en_niet_naar_het_samenstellen(tmp_path):
    from agent.werkgebied_intake import is_werkgebiedvraag

    zin = "Lex, help mij de bronnen bij dit werkgebied te bepalen."
    assert bs.is_bronselectievraag(zin) and not is_werkgebiedvraag(zin)
    assert is_werkgebiedvraag("Kunnen we een werkgebied samenstellen?")
    e, llm = _beurt(tmp_path, NepApi(kandidaten=_kandidaten()), zin)
    assert _kaart_uit(e)["stap"] == "bs_kies" and not llm.calls


def test_getypt_kiest_de_supervisor_de_bronselectie_met_een_taak(tmp_path):
    from fakes import FakeLLM, response, text_block

    nep = NepApi(kandidaten=_kandidaten())
    llm = FakeLLM([response([text_block("WORKERS: werkgebied\nSPECIALIST: algemeen\nTAAK: bronselectie\nPLAN: x")],
                            "end_turn")])
    e, llm = _beurt(tmp_path, nep, "Zullen we per deelvraag kijken wat erbij hoort?", llm=llm)
    assert _kaart_uit(e)["stap"] == "bs_kies" and len(llm.calls) == 1
