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

from agent import bepaling_namen as bn, bronselectie as bs
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
                # Zoals de api: wat bij het beantwoorden van het kaartje niet gekozen werd, is niet gekozen.
                gehad = r["status"] in ("voorlopig_afgerond", "beoordeeld") or (
                    r["fase"] != "kern" if k["rol"] == "kern" else r["fase"] == "afronden")
                stand = "opgenomen" if kid in self.opgenomen.get(did, {}) else self.besluiten.get(
                    (kid, did), "niet_gekozen" if gehad else "voorgesteld")
                lijst.append({"id": kid, "bron_iri": f"urn:bwb:BWBR0004770:artikel:{kid}", "label": k["label"],
                              "bwb_id": "BWBR0004770", "rol": k["rol"], "bewijs": [], "bewijs_soorten": ["tekst"],
                              "stand": stand, "overal": False, "elders_opgenomen": False, "reden": "", "besloten_door": None})
            telling = {s: sum(1 for x in lijst if x["stand"] == s) for s in ("voorgesteld", "niet_gekozen", "uitgesloten")}
            telling["opgenomen"] = len(self.opgenomen.get(did, {}))
            doorlopen = r["status"] in ("voorlopig_afgerond", "beoordeeld") or r["fase"] == "afronden"
            redenen = ([] if doorlopen else ["De vragen bij deze deelvraag zijn nog niet doorlopen."]) + (
                ["Er staan nog onderzoekspunten open."] if r["open_punten"] else [])
            vragen.append({"id": did, "nr": nr, "vraag": self.vragen[did], **{k: v for k, v in r.items() if k != "geopend"},
                           "geopend": r["geopend"] or None, "opnieuw_bekijken": False,
                           "klaar": r["status"] in ("voorlopig_afgerond", "beoordeeld"),
                           "bronnen": [{"selectie_id": k, "bron_iri": f"urn:bwb:BWBR0004770:artikel:{k}", "label": k, "rol": rol}
                                       for k, rol in self.opgenomen.get(did, {}).items()],
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
            self.besluiten[(kid, did)] = {"uitsluiten": "uitgesloten"}[besluit["besluit"]]
        self.rijen.setdefault(did, {"status": "in_behandeling", "fase": "kern", "open_punten": [], "revisie": 1, "geopend": 0})
        return await self.haal_bronselectie(werkgebied_id, na=did)

    async def zoek_bepalingen(self, werkgebied_id, bwb_id, q):
        """Zoals `GET …/bepalingen`: de vindplaats in de echte boom, met het begin van de tekst; 999 bestaat niet."""
        self.aanroepen.append(("zoek", bwb_id, q))
        artikel, _, lid = q.partition(" lid ")
        if artikel == "999":
            return {"bwb_id": bwb_id, "treffers": []}
        iri = f"urn:bwb:{bwb_id}:artikel:{artikel}" + (f":lid:{lid}" if lid else "")
        return {"bwb_id": bwb_id, "treffers": [{"bron_iri": iri, "soort": "lid" if lid else "artikel",
                                                "vindplaats": f"Artikel {artikel}" + (f", lid {lid}" if lid else ""),
                                                "titel": "", "fragment": f"Tekst van {q}."}]}

    async def zoek_regelingen(self, werkgebied_id, q):
        return [{"bwb_id": "BWBR0004770", "citeertitel": "Invorderingswet 1990"}]

    async def voeg_bron_toe(self, werkgebied_id, bron):
        self.aanroepen.append(("werkgebied", bron["bron_iri"], bron["rol"]))
        assert bron["verwachte_revisie"] == self.revisie
        self.revisie += 1
        return {"selectie": {"label": bron["bron_iri"].rsplit(":artikel:", 1)[-1]}, "werkgebied": {"revisie": self.revisie}}

    async def voeg_bepaling_toe(self, werkgebied_id, did, bron):
        """Zoals `POST …/bronselectie/{d}/bronnen`, met de bron-IRI van een treffer."""
        self.aanroepen.append(("toevoegen", did, bron["bron_iri"], bron["rol"]))
        assert bron["verwachte_revisie"] == self.revisie
        self.revisie += 1
        self.verouderd = True
        sleutel = bron["bron_iri"].rsplit(":artikel:", 1)[-1]
        self.opgenomen.setdefault(did, {})[sleutel] = bron["rol"]
        self.rijen.setdefault(did, {"status": "in_behandeling", "fase": "kern", "open_punten": [], "revisie": 1, "geopend": 0})
        return await self.haal_bronselectie(werkgebied_id, na=did)

    async def haal_werkgebied(self, werkgebied_id):
        """Voor het kaartje van de gebeurtenis (`bs._vraag_gebeurtenis`): zonder regeling stelt Lex niets voor."""
        return {"id": WID, "naam": "Betalingstermijnen", "bronnen": []}

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


def _paneel(api, did, kid, rol):
    """Een besluit in het paneel naast het gesprek: rechtstreeks bij de api, buiten Lex om."""
    ov = _run(api.haal_bronselectie(WID))
    _run(api.besluit_bronselectie(WID, did, kid, {"besluit": "opnemen", "rol": rol, "verwachte_revisie": ov["revisie"]}))


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

    # Deelvraag 1: kernbepalingen, dan wat eraan hangt, dan afronden → Hoe wil je verder? met deelvraag 2. Het
    # kaartje is compact (3 nov 2026): het noemt wat er ligt, beslissen gebeurt in het paneel, *Klaar* gaat verder.
    uit = _klik(api, kaart, "d1")
    k = uit["kaart"]
    assert (k["stap"], k["weergave"], k["opties"], k["samenvatting"]) == \
        ("bs_bepalingen", "paneel", [], {"kandidaten": 1, "opgenomen": 0})
    assert "Ik vond 1 kandidaatbron" in k["toelichting"] and "paneel" in k["toelichting"]
    _paneel(api, "d1", "k1", "analyseren")
    uit = _klik(api, k, actie="klaar")
    assert api.opgenomen["d1"] == {"k1": "analyseren"}
    assert uit["kaart"]["stap"] == "bs_afhankelijkheden" and uit["kaart"]["samenvatting"]["kandidaten"] == 1
    _paneel(api, "d1", "a1", "context")
    uit = _klik(api, uit["kaart"], actie="klaar")
    assert api.opgenomen["d1"]["a1"] == "context" and uit["kaart"]["stap"] == "bs_afronden"
    uit = _klik(api, uit["kaart"], "afronden")
    verder = uit["kaart"]
    assert verder["stap"] == "bs_verder" and verder["vraag"] == "Hoe wil je verder met de bronselectie?"
    assert [o["label"] for o in verder["opties"]][:2] == ["Verder met deelvraag 2", "Deelvraag 1 verder onderzoeken"]

    # Deelvraag 2: het voorstel niet aanvinken (niet gekozen) en zelf een bepaling toevoegen als keuze.
    uit = _klik(api, verder, "verder:d2")
    assert uit["kaart"]["deelvraag_id"] == "d2" and uit["kaart"]["weergave"] == "paneel"
    # Typen blijft kunnen: een eigen bepaling komt erbij, en het kaartje blijft tot *Klaar*.
    _paneel(api, "d2", "k2", "analyseren")
    # Eerst de treffer met haar tekst, pas na het aanvinken toegevoegd; daarna het compacte kaartje weer.
    uit = _klik(api, uit["kaart"], tekst="artikel 10a lid 2")
    treffers = uit["kaart"]
    assert treffers["stap"] == "bs_toevoegen_treffers" and treffers["deelvraag_id"] == "d2"
    assert treffers["opties"][0]["omschrijving"] == "‘Tekst van 10a lid 2.’" and not any(a[0] == "toevoegen" for a in api.aanroepen)
    uit = _klik(api, treffers, *treffers["vooringevuld"])
    assert "k2" in api.opgenomen["d2"], "een getypte bepaling koppelt het paneelbesluit niet los"
    _run(api.besluit_bronselectie(WID, "d2", "k2", {"besluit": "loskoppelen",
                                                     "verwachte_revisie": _run(api.haal_bronselectie(WID))["revisie"]}))
    assert ("toevoegen", "d2", "urn:bwb:BWBR0004770:artikel:10a:lid:2", "analyseren") in api.aanroepen
    assert "Toegevoegd: 10a:lid:2." in uit["zinnen"] and uit["kaart"]["stap"] == "bs_bepalingen"
    uit = _klik(api, uit["kaart"], actie="klaar")
    # Wat bij *Klaar* onbeslist was, is niet gekozen.
    assert _run(api.haal_bronselectie(WID))["deelvragen"][1]["kandidaten"][0]["stand"] == "niet_gekozen"
    # Een onderzoekspunt noteer je bij het afronden.
    assert uit["kaart"]["stap"] == "bs_afronden"
    uit = _klik(api, uit["kaart"], tekst="Onderzoek ook de bijzondere invorderbaarheid.")
    assert api.rijen["d2"]["open_punten"] == [{"tekst": "Onderzoek ook de bijzondere invorderbaarheid."}]
    assert "onderzoekspunt" in " ".join(uit["zinnen"]) and uit["kaart"]["stap"] == "bs_afronden"

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


def test_niet_gekozen_houdt_beoordelen_niet_tegen_een_onderzoekspunt_wel():
    """Kiezen is het besluit: na het doorlopen van de vragen kan de deelvraag beoordeeld worden, ook als er
    voorstellen niet gekozen zijn. Een onderzoekspunt houdt haar uit *beoordeeld*, en de controle zegt het."""
    api = NepApi(vragen=VRAGEN[:1], kandidaten={"k1": {"label": "Artikel 9", "rol": "kern", "bij": ["d1"]},
                                                "k2": {"label": "Artikel 10", "rol": "kern", "bij": ["d1"]}})
    k = _run(bs.start(api, WID, api.zoek, deelvraag_id="d1"))["kaart"]
    _paneel(api, "d1", "k1", "analyseren")
    k = _klik(api, k, actie="klaar")["kaart"]
    assert k["stap"] == "bs_afronden" and "beoordelen" in [o["waarde"] for o in k["opties"]]
    assert "1 niet gekozen" in k["toelichting"]
    uit = _klik(api, k, tekst="Bijzondere invorderbaarheid nog nagaan.")
    k = uit["kaart"]
    assert "beoordelen" not in [o["waarde"] for o in k["opties"]] and "onderzoekspunten" in k["toelichting"]
    uit = _klik(api, k, "beoordelen")
    assert "kan nog niet" in " ".join(uit["zinnen"]) and api.rijen["d1"]["status"] == "in_behandeling"
    uit = _klik(api, k, "afronden")
    assert api.rijen["d1"]["status"] == "voorlopig_afgerond"
    tekst = _klik(api, uit["kaart"], "controle")["zinnen"][0]
    assert "nog niet beoordeeld" in tekst and bs.SLOT not in tekst


def test_een_oud_kaartje_met_vinkjes_beslist_niets():
    """Het compacte kaartje beslist niet (3 nov 2026): keuzes op een bepalingenkaartje raken de besluiten niet, en
    een antwoord zonder vinkjes koppelt niets los wat in het paneel is opgenomen."""
    api = NepApi(vragen=VRAGEN[:1], kandidaten={"k1": {"label": "Artikel 9", "rol": "kern", "bij": ["d1"]}})
    k = _run(bs.start(api, WID, api.zoek, deelvraag_id="d1"))["kaart"]
    _paneel(api, "d1", "k1", "analyseren")
    n = len(api.aanroepen)
    _klik(api, k)
    assert not [a for a in api.aanroepen[n:] if a[0] == "besluit"] and api.opgenomen["d1"] == {"k1": "analyseren"}


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


def test_het_kaartje_telt_alle_voorstellen():
    api = NepApi(vragen=VRAGEN[:1], kandidaten={f"k{i}": {"label": f"Artikel {i}", "rol": "kern", "bij": ["d1"]}
                                                for i in range(11)})
    k = _run(bs.start(api, WID, api.zoek))["kaart"]
    k = _klik(api, k, "d1")["kaart"]
    # Het compacte kaartje telt alles; de lijst zelf staat in het paneel.
    assert k["opties"] == [] and k["samenvatting"]["kandidaten"] == 11 and "Ik vond 11 kandidaatbronnen" in k["toelichting"]


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


def test_zelf_toevoegen_zonder_eenduidige_regeling_of_artikel_laat_het_kaartje_staan():
    kand = {"k1": {"label": "Artikel 9", "rol": "kern", "bij": ["d1"]}}
    api = NepApi(vragen=VRAGEN[:1], kandidaten=kand)
    k = _run(bs.start(api, WID, api.zoek, deelvraag_id="d1"))["kaart"]
    # Geen artikel in de tekst: het kaartje blijft, met een aanwijzing.
    uit = _klik(api, k, tekst="de bijzondere invorderbaarheid")
    assert uit["kaart"]["stap"] == "bs_toevoegen" and "geen artikel" in uit["kaart"]["toelichting"]
    # Een artikel dat niet in de graaf staat: gemeld, en opnieuw de vraag.
    uit = _klik(api, k, tekst="artikel 999")
    assert uit["kaart"]["stap"] == "bs_toevoegen" and "niet in de kennisgraaf" in uit["kaart"]["toelichting"]
    assert not any(a[0] == "toevoegen" for a in api.aanroepen)
    # Twee regelingen in het werkgebied en geen genoemd: Lex vraagt welke.
    assert "Bij welke regeling" in bn.bepalingen_uit_tekst("artikel 9", lambda _t: [], ["BWBR0002320", "BWBR0004770"])
    assert bn.bepalingen_uit_tekst("artikel 9 lid 1 en 2 IW", lambda _t: ["BWBR0004770"], []) == [
        {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "1"}, {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "2"}]
    assert bn.bepalingen_uit_tekst("artikel 5.2 en 5.3", lambda _t: ["BWBR0011353"], []) == [
        {"bwb_id": "BWBR0011353", "artikel": "5.2"}, {"bwb_id": "BWBR0011353", "artikel": "5.3"}]
    # Spoor L: één tekst mag meer bepalingen in meer regelingen noemen; elk stuk krijgt zijn eigen regeling, en een
    # Awb-nummer met een dubbele punt is één artikel.
    def vind(t):
        t = t.lower()
        return sorted({b for naam, b in (("invorderingswet", "BWBR0004770"), ("awb", "BWBR0005537")) if naam in t})
    assert bn.bepalingen_uit_tekst("artikel 9 lid 1 en 5 Invorderingswet 1990 en artikel 4:86 Awb", vind, []) == [
        {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "1"}, {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "5"},
        {"bwb_id": "BWBR0005537", "artikel": "4:86"}]
    # Een stuk zonder eigen regeling neemt de enige die de tekst noemt.
    assert bn.bepalingen_uit_tekst("artikel 9 lid 1 en artikel 10 Invorderingswet 1990", vind, []) == [
        {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "1"}, {"bwb_id": "BWBR0004770", "artikel": "10"}]
    # Twee regelingen genoemd en een stuk zonder: Lex weet niet welke, en vraagt het.
    assert "noem de regeling direct na het artikel" in bn.bepalingen_uit_tekst(
        "artikel 9 en artikel 4:86 Invorderingswet en Awb", vind, [])


def test_na_een_gewijzigd_werkgebied_zoekt_lex_eerst_opnieuw_ook_als_alles_af_is():
    api = NepApi(vragen=VRAGEN[:1], kandidaten={"k1": {"label": "Artikel 9", "rol": "kern", "bij": ["d1"]}})
    api.rijen["d1"] = {"status": "voorlopig_afgerond", "fase": "afronden", "open_punten": [], "revisie": 2, "geopend": 1}
    _run(bs.start(api, WID, api.zoek))
    assert api.zoekopdrachten == 0                                   # niets veranderd: niet opnieuw zoeken
    api.verouderd = True                                             # bv. het praktijkvoorbeeld is aangevuld
    uit = _run(bs.start(api, WID, api.zoek))
    assert api.zoekopdrachten == 1 and api.verouderd is False
    assert "Alle deelvragen zijn afgerond." in uit["zinnen"]


# --- de gebeurtenis vóór de bronnen (zoekvragen a–d) -------------------------------------------------

class GebeurtenisApi(NepApi):
    """De nep-api met een werkgebied dat een gebeurtenis draagt (`PATCH` zoals de api, met de revisietoets)."""

    def __init__(self, gebeurtenis="", **kw):
        super().__init__(**kw)
        self.gebeurtenis = gebeurtenis
        self.wijzigingen: list[dict] = []

    async def haal_bronselectie(self, werkgebied_id, na=""):
        return {**await super().haal_bronselectie(werkgebied_id, na), "gebeurtenis": self.gebeurtenis}

    async def haal_werkgebied(self, werkgebied_id):
        return {"id": WID, "naam": "Betalingstermijnen", "analysevraag": "Wanneer moet ik betalen?",
                "bronnen": [{"bwb_id": "BWBR0004770"}], "gebeurtenis": self.gebeurtenis}

    async def wijzig_werkgebied(self, werkgebied_id, wijziging):
        from agent.wetsanalyse_api import WetsanalyseApiFout
        if wijziging["verwachte_revisie"] != self.revisie:
            raise WetsanalyseApiFout("412", 412)
        self.wijzigingen.append(wijziging)
        self.gebeurtenis, self.revisie, self.verouderd = wijziging["gebeurtenis"], self.revisie + 1, True
        return await self.haal_werkgebied(werkgebied_id)


def _stel_voor(gevraagd):
    def stel_voor(werkgebied, regelingen):
        gevraagd.append(regelingen)
        return [{"gebeurtenis": "invordering", "koppen": ["Hoofdstuk II – Invordering (Invorderingswet 1990)"]},
                {"gebeurtenis": "uitstel van betaling", "koppen": ["Uitstel van betaling (Leidraad Invordering 2008)"]}]
    return stel_voor


def _klik_g(api, kaart, *keuzes, actie="antwoord", tekst="", stel_voor=None, toets=None):
    uit = _run(bs.verwerk(api, {"intake_id": kaart["intake_id"], "stap": kaart["stap"], "deelvraag_id": kaart["deelvraag_id"],
                                "actie": actie, "keuzes": list(keuzes), "tekst": tekst}, api.zoek, None, stel_voor, toets))
    if uit.get("kaart"):
        _geldig(uit["kaart"])
    return uit


def test_eerst_de_gebeurtenis_dan_de_deelvragen():
    """Zonder gebeurtenis en nog niet begonnen: eerst het kaartje met de voorstellen uit de koppen, de eerste
    aangevinkt; de aangewezen deelvraag reist mee. Kiezen slaat haar op (met de revisie) en gaat dan verder."""
    api, gevraagd = GebeurtenisApi(kandidaten=_kandidaten()), []
    uit = _run(bs.start(api, WID, api.zoek, deelvraag_id="d2", stel_voor=_stel_voor(gevraagd)))
    kaart = _geldig(uit["kaart"])
    assert (kaart["stap"], kaart["vraag"], kaart["deelvraag_id"]) == ("bs_gebeurtenis", "Om welke gebeurtenis gaat het?", "d2")
    assert [o["waarde"] for o in kaart["opties"]] == ["invordering", "uitstel van betaling"]
    assert kaart["vooringevuld"] == ["invordering"] and kaart["vrije_tekst"] and kaart["overslaanbaar"]
    assert "Invorderingswet 1990" in kaart["opties"][0]["omschrijving"] and gevraagd == [["BWBR0004770"]]
    uit = _klik_g(api, kaart, "uitstel van betaling", stel_voor=_stel_voor(gevraagd))
    assert api.wijzigingen == [{"verwachte_revisie": 1, "gebeurtenis": "uitstel van betaling"}]
    assert "*uitstel van betaling*" in uit["zinnen"][0]
    # Daarna gewoon verder bij de aangewezen deelvraag; het werkgebied veranderde, dus eerst opnieuw zoeken.
    assert uit["kaart"]["stap"] == "bs_bepalingen" and uit["kaart"]["deelvraag_id"] == "d2" and api.zoekopdrachten == 1
    # Een volgende start vraagt het niet nog eens.
    assert _run(bs.start(api, WID, api.zoek, stel_voor=_stel_voor(gevraagd)))["kaart"]["stap"] != "bs_gebeurtenis"


def test_een_eigen_term_gaat_voor_en_overslaan_slaat_niets_op():
    api, gevraagd = GebeurtenisApi(kandidaten=_kandidaten()), []
    kaart = _run(bs.start(api, WID, api.zoek, stel_voor=_stel_voor(gevraagd)))["kaart"]
    _klik_g(api, kaart, "invordering", tekst="  verrekening ", stel_voor=_stel_voor(gevraagd))
    assert api.gebeurtenis == "verrekening"

    api = GebeurtenisApi(kandidaten=_kandidaten())
    kaart = _run(bs.start(api, WID, api.zoek, stel_voor=_stel_voor(gevraagd)))["kaart"]
    uit = _klik_g(api, kaart, actie="overslaan", stel_voor=_stel_voor(gevraagd))
    assert api.wijzigingen == [] and uit["kaart"]["stap"] == "bs_kies"
    assert uit["zinnen"][0].startswith("Dan zoek ik zonder gebeurtenis")


def test_de_gebeurtenis_wordt_niet_steeds_gevraagd_wel_als_de_analist_erom_vraagt():
    """Begonnen zonder gebeurtenis: geen kaartje meer, tenzij de vraag het woord noemt (*Vraag Lex* bij het lege
    veld: "Bepaal de gebeurtenis en de bronnen"). Dan staat de huidige keuze bovenaan als ze geen voorstel is.
    Zonder voorstel én zonder vraag ook niets (de graaf hapert, geen regeling)."""
    api, gevraagd = GebeurtenisApi(kandidaten=_kandidaten()), []
    _run(api.zet_bronselectie_status(WID, "d1", {"actie": "openen"}))
    assert _run(bs.start(api, WID, api.zoek, stel_voor=_stel_voor(gevraagd)))["kaart"]["stap"] == "bs_bepalingen"
    kaart = _run(bs.start(api, WID, api.zoek, vraag="Bepaal de gebeurtenis en de bronnen",
                          stel_voor=_stel_voor(gevraagd)))["kaart"]
    assert kaart["stap"] == "bs_gebeurtenis"

    api = GebeurtenisApi(gebeurtenis="kwijtschelding", kandidaten=_kandidaten())
    kaart = _run(bs.start(api, WID, api.zoek, vraag="welke gebeurtenis?", stel_voor=_stel_voor(gevraagd)))["kaart"]
    assert kaart["opties"][0] == {"label": "kwijtschelding", "waarde": "kwijtschelding", "bron": {},
                                  "omschrijving": "nu gekozen"} and kaart["vooringevuld"] == ["kwijtschelding"]

    api = GebeurtenisApi(kandidaten=_kandidaten())
    assert _run(bs.start(api, WID, api.zoek, stel_voor=lambda wg, r: []))["kaart"]["stap"] == "bs_kies"


# --- de woordenkloof benoemen (PR 6) -------------------------------------------------------------------

def _toets(voorwerp=False, ontbrekend=(), brug=None):
    gezien = []

    def toets(werkgebied, regelingen, woorden, met_voorwerp):
        gezien.append((tuple(woorden), met_voorwerp))
        return {"voorwerp": voorwerp and met_voorwerp, "ontbrekend": [w for w in ontbrekend if w in woorden],
                "brug": brug or {}}
    toets.gezien = gezien
    return toets


def test_een_voorwerp_als_gebeurtenis_vraagt_om_de_handeling_ook_na_het_begin():
    """"Bankrekening" staat in geen kop: de keten a–d vindt vanaf een voorwerp niets. Het kaartje komt terug, ook als de
    analist al begon, met de handelingen waaronder de bepalingen met het woord vallen (Rekeningafspraken, 4 nov 2026)."""
    api = GebeurtenisApi(gebeurtenis="bankrekening", kandidaten=_kandidaten())
    _run(api.zet_bronselectie_status(WID, "d1", {"actie": "openen"}))

    def stel_voor(wg, regelingen):
        return [{"gebeurtenis": "uitbetaling", "koppen": ["Hoofdstuk IVA – Uitbetaling aan belastingschuldige"],
                 "voorwerp": "bankrekening", "onder_voorwerp": 6}]
    uit = _run(bs.start(api, WID, api.zoek, stel_voor=stel_voor, toets=_toets(voorwerp=True)))
    kaart = _geldig(uit["kaart"])
    assert kaart["stap"] == "bs_gebeurtenis"
    assert kaart["toelichting"].startswith("‘bankrekening’ staat in geen kop van de regelingen")
    assert "vallen onder: uitbetaling" in kaart["toelichting"]
    assert kaart["opties"][0]["omschrijving"] == "nu gekozen"            # de huidige keuze blijft zichtbaar
    # Geen voorwerp: geen kaartje, gewoon verder.
    api = GebeurtenisApi(gebeurtenis="uitbetaling", kandidaten=_kandidaten())
    _run(api.zet_bronselectie_status(WID, "d1", {"actie": "openen"}))
    assert _run(bs.start(api, WID, api.zoek, stel_voor=stel_voor, toets=_toets()))["kaart"]["stap"] == "bs_bepalingen"


def test_een_eigen_woord_dat_niet_in_de_wet_staat_benoemt_lex():
    """"Rekeningafspraak" is een begrip uit de uitvoering: Lex zegt het bij de start, met de woorden die het dossier
    ernaast zet, en bij een deelvraag zonder kernbepalingen nog eens – in plaats van alleen "0 bronnen"."""
    vragen = ["Wat is een rekeningafspraak?", "Onder welke voorwaarden kan iemand een betaling aan een derde laten doen?"]
    toets = _toets(ontbrekend=["rekeningafspraak"], brug={"rekeningafspraak": ["bankrekening", "uitbetaald", "derde"]})
    api = GebeurtenisApi(gebeurtenis="uitbetaling", vragen=vragen, kandidaten={})
    uit = _run(bs.start(api, WID, api.zoek, stel_voor=lambda wg, r: [], toets=toets))
    tekst = " ".join(uit["zinnen"])
    assert "‘rekeningafspraak’ staat niet in de regelingen van dit werkgebied" in tekst
    assert "In je dossier staat het naast bankrekening, uitbetaald, derde; daarmee zoek ik." in tekst
    assert "rekeningafspraak" in toets.gezien[-1][0] and "voorwaarden" not in toets.gezien[-1][0]
    # Deelvraag 1 zonder kernbepalingen: de zin komt terug bij die deelvraag.
    uit = _klik_g(api, uit["kaart"], "d1", stel_voor=lambda wg, r: [], toets=toets)
    assert "Bij deelvraag 1 vond ik geen kernbepalingen" in " ".join(uit["zinnen"])
    assert "‘rekeningafspraak’ staat niet in de regelingen" in " ".join(uit["zinnen"])


def test_andere_zoekcode_zoekt_opnieuw_bij_het_hervatten():
    """De laatste zoekopdracht liep met andere zoekcode (`zoekversie`): bij het hervatten zoekt Lex opnieuw, ook als het
    werkgebied gelijk bleef. Meldt de api geen versie (een oudere api), dan niet."""
    from agent.bronnen_run import ZOEKVERSIE

    class VersieApi(NepApi):
        versie = "zoud"

        async def haal_bronselectie(self, werkgebied_id, na=""):
            ov = await super().haal_bronselectie(werkgebied_id, na)
            ov["zoekdekking"]["zoekversie"] = self.versie
            return ov

        async def zoek(self, did):
            VersieApi.versie = ZOEKVERSIE
            return await super().zoek(did)

    api = VersieApi(kandidaten=_kandidaten())
    _run(api.zet_bronselectie_status(WID, "d1", {"actie": "openen"}))
    _run(bs.start(api, WID, api.zoek))
    assert api.zoekopdrachten == 1
    _run(bs.start(api, WID, api.zoek))                       # nu dezelfde versie: niet nog eens
    assert api.zoekopdrachten == 1


def test_voeg_een_bepaling_toe_vanuit_het_gesprek():
    """*Voeg een bepaling toe* (4 nov 2026): het zoeken hoort bij het gesprek, niet bij het artefact. Zonder
    deelvraag eerst bij welke, dan de bepaling, dan de treffers met tekst, en pas na het aanvinken toevoegen."""
    api = NepApi(vragen=VRAGEN[:2], kandidaten=_kandidaten())
    uit = _run(bs.vraag_toevoegen(api, WID))
    k = _geldig(uit["kaart"])
    assert k["stap"] == "bs_toevoegen" and [o["waarde"] for o in k["opties"]] == ["d1", "d2", bs.HEEL]
    k = _klik(api, k, "d2")["kaart"]
    assert k["stap"] == "bs_toevoegen" and k["deelvraag_id"] == "d2" and k["vrije_tekst"] and not k["opties"]
    # "als context" kiest de rol; twee bepalingen in één tekst geven twee treffers.
    k = _klik(api, k, tekst="artikel 9 lid 1 en 3 Invorderingswet als context")["kaart"]
    assert k["stap"] == "bs_toevoegen_treffers" and k["meerkeuze"]
    assert [o["label"] for o in k["opties"]] == ["Artikel 9, lid 1 – Invorderingswet 1990",
                                                 "Artikel 9, lid 3 – Invorderingswet 1990"]
    assert all(w.startswith("context|") for w in k["vooringevuld"])
    uit = _klik(api, k, k["vooringevuld"][0])
    assert api.opgenomen["d2"] == {"9:lid:1": "context"}
    assert uit["zinnen"][0] == "Toegevoegd als contextbron: 9:lid:1." and uit["deelvraag"] == "d2"
    # Er liep geen bronselectie, dus geen kaartje terug: het paneel opent op de deelvraag.
    assert uit.get("kaart") is None
    # Wat er al staat, is niet aangevinkt.
    k = _klik(api, _run(bs.vraag_toevoegen(api, WID, "d2"))["kaart"], tekst="artikel 9 lid 1 IW")["kaart"]
    assert k["vooringevuld"] == [] and k["opties"][0]["omschrijving"].startswith("Staat er al.")


def test_een_bepaling_bij_het_hele_werkgebied_en_terug_naar_de_lopende_deelvraag():
    api = NepApi(vragen=VRAGEN[:2], kandidaten=_kandidaten())
    lopend = _run(bs.start(api, WID, api.zoek, deelvraag_id="d1"))["kaart"]
    assert lopend["stap"] == "bs_bepalingen"
    k = _run(bs.vraag_toevoegen(api, WID))["kaart"]
    assert k["vooringevuld"] == ["d1"], "de deelvraag in behandeling staat voorop"
    k = _klik(api, _klik(api, k, bs.HEEL)["kaart"], tekst="artikel 3 IW")["kaart"]
    uit = _klik(api, k, *k["vooringevuld"])
    assert ("werkgebied", "urn:bwb:BWBR0004770:artikel:3", "analyseren") in api.aanroepen
    assert uit["kaart"]["stap"] == "bs_bepalingen" and uit["kaart"]["deelvraag_id"] == "d1"
    assert "We gaan verder waar we waren." in uit["zinnen"]


def test_bepaling_toevoegen_routeert_zonder_model():
    r = ChatRequest(question="Voeg een bepaling toe", actie="bepaling_toevoegen", werkgebied_id="wg1")
    assert r.actie == "bepaling_toevoegen"
    from agent.models import BRONSELECTIE_ACTIES
    assert "bepaling_toevoegen" in BRONSELECTIE_ACTIES
