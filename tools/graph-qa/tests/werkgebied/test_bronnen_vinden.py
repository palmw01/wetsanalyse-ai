"""Bronnen vinden met Lex (spoor D, fase A): de ontdekmethoden, de functie van een verwijzing, de run
en de bronnenroute in het gesprek.

Bewaakt:
1. de functie van een verwijzing per patroon, op letterlijke formuleringen;
2. per methode: rol, bewijs, wat al in de selectie staat valt weg, het plafond geeft `volledig: false`,
   een falende methode laat de rest staan;
3. de uitkomst past in het api-contract (`api/app/bronnen_run_contracts.py`, uit de bron gelezen);
4. het verloop van run en route tegen een nep-api, en de grens met de overzichtsvraag.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from agent import bepaling_namen, bronnen_run, bronnen_vinden, deelvraag_zoeken, overzicht, zoektermen
from agent.bronnen_vinden import vind, verwijzingsfunctie
from agent.models import ChatRequest
from agent.runstore import Run
from fakes import FakeGraph, agent_ctx, make_settings

IW = "urn:bwb:BWBR0004770"
ART9, L1 = f"{IW}:artikel:9", f"{IW}:artikel:9:lid:1"
ART8, ART10, ART2K = f"{IW}:artikel:8", f"{IW}:artikel:10", f"{IW}:artikel:2:lid:1:o:k"
AWR = "urn:bwb:BWBR0002320:artikel:11"
H2 = f"{IW}:hoofdstuk:II"


# --- 1. de functie van een verwijzing ------------------------------------------------------------

@pytest.mark.parametrize("tekst, anker, functie", [
    ("In afwijking van artikel 9, eerste lid, is een belastingaanslag direct invorderbaar.", "artikel 9", "uitzondering"),
    ("Met uitzondering van artikel 10 is deze afdeling van toepassing.", "artikel 10", "uitzondering"),
    ("Bij ministeriële regeling kunnen regels worden gesteld omtrent de toepassing van artikel 9.", "artikel 9", "delegatie"),
    ("De belastingaanslag, bedoeld in artikel 11 van de Algemene wet inzake rijksbelastingen, wordt ...",
     "artikel 11 van de Algemene wet inzake rijksbelastingen", "toepassing"),
    ("Artikel 8 is van overeenkomstige toepassing.", "Artikel 8", "onbekend"),
    ("De ontvanger stelt de belastingschuldige in kennis.", "artikel 9", "onbekend"),
])
def test_de_functie_van_een_verwijzing(tekst, anker, functie):
    assert verwijzingsfunctie(tekst, anker) == functie


def test_een_verwijzing_uit_een_definitie_is_een_definitie():
    assert verwijzingsfunctie("belastingaanslag: aanslag als bedoeld in artikel 11", "artikel 11", definieert=True) == "definitie"


# --- 2. de methoden --------------------------------------------------------------------------------

def _tsv(kop: list[str], rijen: list[list[str]]) -> str:
    def cel(v: str) -> str:
        return f"<{v}>" if v.startswith("urn:") else json.dumps(v, ensure_ascii=False)
    return "\t".join(f"?{k}" for k in kop) + "\n" + "".join("\t".join(cel(v) for v in r) + "\n" for r in rijen)


UITGAAND = _tsv(["kern", "vanuit", "tekst", "anker", "naar", "label", "def"], [
    [ART9, L1, "In afwijking van artikel 8 is een belastingaanslag invorderbaar.", "artikel 8", ART8, "Artikel 8", ""],
    [ART9, L1, "De aanslag, bedoeld in artikel 11 AWR, wordt ...", "artikel 11 AWR", AWR, "Artikel 11", ""],
    [ART9, L1, "Zie lid 1.", "lid 1", L1, "Lid 1", ""],                          # binnen de kern: weg
])
INKOMEND = _tsv(["kern", "doel", "bron", "tekst", "anker", "label", "def"], [
    [ART9, L1, ART10, "Artikel 9 is van toepassing.", "Artikel 9", "Artikel 10", ""],
])
TEKSTEN = _tsv(["kern", "deel", "tekst"], [
    [ART9, L1, "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet."],
])
DEFINITIES = _tsv(["node", "begrip", "label"], [
    [ART2K, "belastingaanslag", "Onderdeel k"], [f"{IW}:artikel:2:lid:1:o:i", "belastingschuldige", "Onderdeel i"],
])
OPBOUW = _tsv(["kern", "artikel", "ouder", "buur", "label"], [
    [ART9, ART9, H2, ART8, "Artikel 8"], [ART9, ART9, H2, ART10, "Artikel 10"],
])


class Graaf(FakeGraph):
    def __init__(self, faal: str = "", **vervang: str) -> None:
        super().__init__(results=self._antwoord)
        self.faal, self.vervang = faal, vervang

    def _antwoord(self, q: str) -> str:
        if "bwb:opschrift" in q:                                   # regelingnamen
            return _tsv(["r", "citeertitel", "opschrift"], [["urn:bwb:BWBR0002320", "Algemene wet inzake rijksbelastingen", ""]])
        soort = ("uitgaand" if "?vanuit bwb:heeftVerwijzing" in q else "inkomend" if "?bron bwb:heeftVerwijzing" in q
                 else "definities" if "?node bwb:definieertBegrip" in q else "opbouw" if "?buur a bwb:Artikel" in q
                 else "teksten" if "?deel bwb:tekst ?tekst" in q else "")
        if not soort:
            raise AssertionError(f"onverwachte query: {q[:200]}")
        if soort == self.faal:
            raise RuntimeError("graaf hapert")
        return self.vervang.get(soort) or {"uitgaand": UITGAAND, "inkomend": INKOMEND, "definities": DEFINITIES,
                                           "opbouw": OPBOUW, "teksten": TEKSTEN}[soort]


INVOER = {"naam": "Invorderbaarheid", "analysevraag": "Wanneer is een belastingaanslag invorderbaar?",
          "kern": [{"bron_iri": ART9, "label": "Artikel 9", "bwb_id": "BWBR0004770", "bereik": "onderliggend"}],
          "context": []}


@pytest.fixture
def geen_overzicht(monkeypatch):
    monkeypatch.setattr(overzicht, "bouw_overzicht", lambda *_a, **_k: {"volledig": True, "regelingen": [],
                                                                         "onderwerp_tekst": "invorderbaar"})


def _per_iri(uit: dict) -> dict:
    return {k["bron_iri"]: k for k in uit["kandidaten"]}


ALLE = ("overzicht", "verwijzing_uit", "verwijzing_in", "definitie", "opbouw")


def test_de_standaard_volgt_de_meting():
    assert bronnen_vinden.standaard_voor(INVOER) == ("verwijzing_uit", "definitie", "opschrift", "lid_verwijzing", "beleidsregel", "artikelleden", "opbouw")
    assert bronnen_vinden.standaard_voor({**INVOER, "kern": []}) == ("overzicht",)


def test_elke_methode_levert_kandidaten_met_bewijs(geen_overzicht):
    uit = vind(Graaf(), INVOER, methoden=ALLE)
    k = _per_iri(uit)
    assert L1 not in k and ART9 not in k                                    # in de selectie: weg
    # Artikel 8: verwezen met "in afwijking van" (afhankelijkheid) én in hetzelfde deel (aanverwant).
    assert k[ART8]["rol"] == "afhankelijkheid"
    assert {b["methode"] for b in k[ART8]["bewijs"]} == {"verwijzing_uit", "opbouw"}
    assert next(b for b in k[ART8]["bewijs"] if b["methode"] == "verwijzing_uit")["detail"]["functie"] == "uitzondering"
    assert k[AWR]["rol"] == "afhankelijkheid" and k[AWR]["bwb_id"] == "BWBR0002320"
    # Een leesbare vindplaats met de regeling, niet het kale label uit de graaf.
    assert k[AWR]["label"] == "Artikel 11 – Algemene wet inzake rijksbelastingen"
    assert k[ART2K]["label"].startswith("Artikel 2, lid 1, onderdeel k")
    # Artikel 10 verwijst naar de kern én staat in hetzelfde deel: aanverwant.
    assert k[ART10]["rol"] == "aanverwant" and len(k[ART10]["bewijs"]) == 2
    # Alleen de definitie van een term die letterlijk in de kern staat.
    assert k[ART2K]["rol"] == "afhankelijkheid" and k[ART2K]["bewijs"][0]["detail"] == {"begrip": "belastingaanslag"}
    assert f"{IW}:artikel:2:lid:1:o:i" not in k
    assert all(m["volledig"] for m in uit["meting"].values())
    assert set(uit["meting"]) == set(ALLE)
    # Sterkste rol eerst.
    assert [x["rol"] for x in uit["kandidaten"]] == sorted((x["rol"] for x in uit["kandidaten"]),
                                                           key=bronnen_vinden.ROL_VOLGORDE.get)


def test_het_overzicht_levert_kernbepalingen(monkeypatch):
    ov = {"volledig": True, "onderwerp_tekst": "invorderbaar", "regelingen": [
        {"delen": [{"bepalingen": [{"iri": ART8, "label": "Artikel 8", "naam": "art. 8"},
                                   {"iri": ART9, "label": "Artikel 9", "naam": "art. 9"}]}], "ook_genoemd": []}]}
    gevraagd = {}
    monkeypatch.setattr(overzicht, "bouw_overzicht", lambda g, vraag, **kw: gevraagd.update(vraag=vraag, **kw) or ov)
    vroeger = replace(deelvraag_zoeken.STANDAARD_PROFIEL, overzicht_streng=False)
    uit = vind(Graaf(), INVOER, methoden=("overzicht",), profiel=vroeger)
    assert gevraagd["vraag"] == INVOER["analysevraag"]
    # Geen onderwerp in "Wanneer is … invorderbaar?": zonder `overzicht_streng` is de naam van het werkgebied het onderwerp.
    assert gevraagd["onderwerp"] == "Invorderbaarheid"
    assert _per_iri(uit)[ART8]["rol"] == "kern" and ART9 not in _per_iri(uit)
    # De standaard sinds stap 8: een naam van één woord is geen onderwerp, en het overzicht levert aanverwant.
    uit = vind(Graaf(), INVOER, methoden=("overzicht",))
    assert gevraagd["onderwerp"] == INVOER["analysevraag"] and _per_iri(uit)[ART8]["rol"] == "aanverwant"
    vind(Graaf(), {**INVOER, "analysevraag": "Welke artikelen gaan over invorderingsrente?"}, methoden=("overzicht",))
    assert gevraagd["onderwerp"] == "invorderingsrente"


@pytest.mark.parametrize("vraag, onderwerp", [
    ("Wanneer is een aanslag invorderbaar?", "een aanslag invorderbaar"),
    ("Wie is de belastingschuldige?", "de belastingschuldige"),
    ("Onder welke voorwaarden kan uitstel worden verleend?", "uitstel worden verleend"),
    ("Welke artikelen gaan over invorderingsrente?", "invorderingsrente"),
    ("Wat?", ""),
])
def test_het_onderwerp_van_een_deelvraag(vraag, onderwerp):
    assert zoektermen.onderwerp_van_deelvraag(vraag) == onderwerp


# --- bepalingen bij één deelvraag (F3f): de intake en de deelvragen-agent delen `bepaling_opties` ---

IWB = "BWBR0004770"
L9_2, ART12_1 = f"{IW}:artikel:9:lid:2", f"{IW}:artikel:12:lid:1"
FTS_KOP = ["node", "score", "soort", "label", "tekst", "jci", "bwbId", "citeertitel"]


def _fts(*rijen, soort=""):
    return _tsv(FTS_KOP, [[n, "1.0", soort, "", t, "", b, ""] for n, t, b in rijen])


TREFFER_RIJEN = {
    "Lid": ((L1, "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet.", IWB),
                (L9_2, "In afwijking van het eerste lid is een navorderingsaanslag invorderbaar één maand na de dagtekening.", IWB),
                (ART12_1, "De kosten van vervolging zijn invorderbaar.", IWB),
                ("urn:bwb:BWBR0002320:artikel:30:lid:1", "Een belastingaanslag ...", "BWBR0002320")),
    # Artikel 9 zelf valt weg: er is een lid van geraakt. Artikel 10 heeft geen geraakt lid.
    "Artikel": ((ART9, "Een belastingaanslag is invorderbaar ...", IWB),
                (ART10, "In afwijking van artikel 9 is een belastingaanslag terstond invorderbaar.", IWB)),
    # Een onderdeel telt voor zijn lid.
    "Onderdeel": ((f"{IW}:artikel:8:lid:1:o:a", "de aanslag wordt bekendgemaakt door het aanslagbiljet;", IWB),),
    "Divisie": (),
}
TREFFERS = {soort: _fts(*rijen) for soort, rijen in TREFFER_RIJEN.items()}


def _per_term(q: str) -> str:
    """De query op één term (zonder knooptype): de treffers van alle soorten waarvan de tekst die term draagt,
    met hun soort – zoals de index ze teruggeeft."""
    term = re.search(r"tekst:\(+([0-9a-zà-ÿ]+)", q).group(1)
    stam = zoektermen._stamdeel(term)
    return _tsv(FTS_KOP, [[n, "1.0", soort, "", t, "", b, ""] for soort, rijen in TREFFER_RIJEN.items()
                          for n, t, b in rijen if stam in t.casefold()])


class BepalingGraaf(FakeGraph):
    def __init__(self, faal: bool = False) -> None:
        super().__init__(results=self._antwoord)
        self.faal = faal

    def _antwoord(self, q: str) -> str:
        if "bwb:opschrift" in q:
            return _tsv(["r", "citeertitel", "opschrift"], [[f"urn:bwb:{IWB}", "Invorderingswet 1990", ""]])
        if "definieertBegrip:" in q:
            return _tsv(["node", "begrip", "label", "tekst", "jci", "bwbId", "citeertitel"],
                        [[ART2K, "belastingaanslag", "", "belastingaanslag: aanslag als bedoeld in ...", "", IWB, ""]])
        if "VALUES ?bepaling" in q:
            return _tsv(["bepaling", "deel", "soort", "label"], [[L1, H2, "Hoofdstuk", "Hoofdstuk II – Invordering"]])
        if self.faal:
            raise RuntimeError("graaf hapert")
        return next((t for soort, t in TREFFERS.items() if f"?node a bwb:{soort} ." in q), None) or _per_term(q)


DOSSIER = {"analysevraag": "Wanneer is een aanslag invorderbaar?",
           "praktijkvoorbeeld": "Een aanslagbiljet met dagtekening 1 maart."}


def _opties(graaf=None, **kw):
    from agent.zoektermen import uitsluitstammen

    args = {"regelingen": [IWB], "deelvraag": "Wanneer is een belastingaanslag invorderbaar?", "dossier": DOSSIER,
            "buiten": uitsluitstammen("de kosten van vervolging")} | kw
    return deelvraag_zoeken.bepaling_opties(graaf or BepalingGraaf(), **args)


def test_bepalingen_bij_een_deelvraag_op_lid_niveau_en_in_vaste_volgorde():
    uit = _opties()
    # Volgorde: RRF over de lijsten van de index, de kop en het dossier; de definitie van een term is ook een
    # lijst. Een andere regeling valt weg; een artikel met een geraakt lid ook; een onderdeel telt voor zijn lid.
    assert [o["bron_iri"] for o in uit] == [L1, ART10, f"{IW}:artikel:2:lid:1", L9_2, ART12_1]
    # De rangschikking van F3f (21 okt 2026) blijft als profiel bestaan, voor de meting.
    assert [o["bron_iri"] for o in _opties(profiel=deelvraag_zoeken.F3F)] == \
        [L1, ART10, L9_2, f"{IW}:artikel:2:lid:1", ART12_1]
    # Artikel 8 lid 1 raakt alleen het dossier, niet de deelvraag: bij een deelvraag geen optie, anders vulde
    # het dossier elk kaartje tot het maximum (spoor K). Bij de analysevraag telt het dossier wel.
    assert f"{IW}:artikel:8:lid:1" not in [o["bron_iri"] for o in uit]
    assert f"{IW}:artikel:8:lid:1" in [o["bron_iri"] for o in _opties(deelvraag=None)]
    eerste = uit[0]
    assert eerste["label"] == "Artikel 9, lid 1 – Invorderingswet 1990" and not eerste["buiten"]
    assert eerste["omschrijving"].startswith("Een belastingaanslag is invorderbaar zes weken")
    assert eerste["omschrijving"].endswith("raakt: belastingaanslag, invorderbaar, aanslag, aanslagbiljet, dagtekening")
    # Hetzelfde gesprek, dezelfde opties.
    assert _opties() == uit


@pytest.mark.parametrize("tekst, verwacht", [
    ("Het bezwaar- of beroepschrift wordt ondertekend", True),       # positief: de ellips
    ("Het bezwaarschrift wordt ondertekend", True),                  # positief: voluit
    ("Het bezwaar wordt behandeld door de inspecteur", False),       # negatief: alleen het eerste deel
    ("aan- en verkoop van een bezwaar- of beroepschrift", True),     # rand: twee ellipsen in één zin
])
def test_een_ellips_raakt_de_samenstelling_voluit(tekst, verwacht):
    assert bool(zoektermen._raakt(["bezwaarschrift"], tekst, ellips=True)) is verwacht
    # Zonder de vlag (F3f) raakt de ellips niet: zo bleef 6:5 Awb buiten beeld.
    assert not zoektermen._raakt(["bezwaarschrift"], "Het bezwaar- of beroepschrift", ellips=False)


def test_samenstellingen_zoeken_op_hun_delen_en_raken_de_kop():
    assert ("belasting", "aanslag") in zoektermen.splitsingen("belastingaanslag")
    assert zoektermen.splitsingen("termijn") == []                 # te kort om te knippen
    lucene = deelvraag_zoeken._term_lucene("bezwaarschrift", "", deelvraag_zoeken.STANDAARD_PROFIEL)
    assert "(bezwaar AND *schrift*)" in lucene
    assert deelvraag_zoeken._term_lucene("bezwaarschrift", "", deelvraag_zoeken.F3F).count("AND") == 0
    assert zoektermen.kop_raakt("bezwaarschrift", "Algemene bepalingen over bezwaar en beroep")
    assert zoektermen.kop_raakt("belastingaanslag", "Afdeling 2 – De aanslag")
    assert not zoektermen.kop_raakt("bezwaarschrift", "Hoofdstuk II – Invordering")


def test_een_onderdeel_telt_voor_de_bepaling_uit_de_graaf():
    """De IRI van een Leidraad-onderdeel zegt niet waar het staat (`…:artikel:9:o:d` hangt onder divisie 9.2,
    `…divisie9%2FTekst%2FOnderdeel._4` onder `…:artikel:9`). Het doel komt daarom uit `bwb:inBepaling`; de
    IRI-knip is alleen de terugval, en alleen voor een wet."""
    d92 = "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.2"
    o_d = "urn:bwb:BWBR0024096:artikel:9:o:d"
    assert deelvraag_zoeken._doel_van(f"{IW}:artikel:8:lid:1:o:a") == f"{IW}:artikel:8:lid:1"
    assert deelvraag_zoeken._doel_van(d92 + "%2FTekst%2FOnderdeel._1") == d92 + "%2FTekst%2FOnderdeel._1"

    class LeidraadGraaf(BepalingGraaf):
        def _antwoord(self, q: str) -> str:
            if "bwb:inBepaling" in q:
                return _tsv(["node", "vindplaats", "titel", "bepaling"],
                            [[o_d, "Artikel 9.2, onderdeel d", "", d92]] +
                            ([[d92, "Artikel 9.2", "Afwijking", ""]] if d92 in q else []))
            if "?node a bwb:Onderdeel ." in q:
                return _fts((o_d, "de belastingschuldige is invorderbaar …", "BWBR0024096"))
            if "?node a bwb:" in q or "tekst:(" in q and "?node a" not in q:
                return _tsv(FTS_KOP, [])
            return super()._antwoord(q)

    uit = _opties(LeidraadGraaf(), regelingen=["BWBR0024096"], buiten=[])
    assert [o["bron_iri"] for o in uit] == [d92]
    assert uit[0]["label"] == "Artikel 9.2 – Afwijking"     # vindplaats en titel uit de graaf, één keer


def test_een_subdivisie_valt_binnen_haar_divisie():
    """De eval telde divisie 25.2.1 niet als treffer bij een verwachte 25.2 (meetlogboek 3 nov 2026)."""
    d = "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie25%2FCirculaire.divisie25.2"
    assert bronnen_vinden.in_selectie(d + "%2FCirculaire.divisie25.2.1", [d])
    assert not bronnen_vinden.in_selectie(d + "1", [d])                       # 25.21 is geen 25.2
    assert not bronnen_vinden._binnen(f"{IW}:artikel:9%2Fx", f"{IW}:artikel:9")  # alleen bij een id:-knoop


def test_een_naam_komt_er_maar_een_keer_bij():
    """`vind` benoemt kandidaten die `bepaling_opties` al benoemde; de regeling kwam er dan twee keer achter
    ("Onderdeel._11 – Leidraad Invordering 2008 – Leidraad Invordering 2008")."""
    k = [{"bron_iri": L1, "bwb_id": IWB, "label": ""}]
    bepaling_namen._benoem(BepalingGraaf(), k)
    eerst = k[0]["label"]
    bepaling_namen._benoem(BepalingGraaf(), k)
    assert k[0]["label"] == eerst == "Artikel 9, lid 1 – Invorderingswet 1990"


def test_wat_buiten_de_afbakening_raakt_valt_niet_stil_weg():
    """Het invorderingsgeval: 'de kosten van vervolging' valt erbuiten. Een lid dat daar meer over gaat dan
    over de deelvraag staat onderaan, gemarkeerd, en telt niet mee voor het maximum."""
    uit = _opties(limit=2)
    assert [o["bron_iri"] for o in uit] == [L1, ART10, ART12_1]
    assert uit[-1]["buiten"] and uit[-1]["omschrijving"] == deelvraag_zoeken.BUITEN_TEKST
    # Zonder uitsluiting is hetzelfde lid gewoon een optie.
    assert not [o for o in _opties(buiten=[]) if o["buiten"]]


def test_zonder_deelvraag_zoekt_lex_op_de_analysevraag_en_een_storing_is_leeg():
    assert _opties(deelvraag=None)[0]["bron_iri"] in (L1, ART10)
    assert _opties(BepalingGraaf(faal=True)) == []
    assert _opties(deelvraag="Wat?", dossier={}) == []


def test_de_deelvragen_agent_zoekt_per_deelvraag_met_dezelfde_functie():
    dv = [{"id": "d1", "vraag": "Wanneer is een belastingaanslag invorderbaar?"}, {"id": "d2", "vraag": "Wat?"}]
    invoer = {**INVOER, "deelvragen": dv, "dossier": {"afbakening": "Regelingen: Invorderingswet 1990.\n"
                                                                      "Buiten de afbakening: kosten van vervolging."}}
    assert bronnen_vinden.standaard_voor(invoer)[-1] == "deelvraag"
    # Met deelvragen draait het overzicht niet (`overzicht_streng`, aan sinds stap 8): de deelvragen zijn het vertrekpunt.
    assert bronnen_vinden.standaard_voor({**invoer, "kern": []}) == ("deelvraag",)
    uit = vind(BepalingGraaf(), invoer, methoden=("deelvraag",))
    k = _per_iri(uit)
    # Met een kern: binnen de regeling van de kern; wat al in de selectie valt, valt weg. Een treffer bij een deelvraag
    # blijft een kernbepaling van die deelvraag (4 nov 2026; voorheen aanverwant, buiten het kernkaartje).
    assert L1 not in k and L9_2 not in k and k[ART10]["rol"] == "kern"
    assert k[ART10]["bewijs"][0]["detail"] == {"deelvraag_id": "d1", "vraag": dv[0]["vraag"],
                                               "raakt": ["belastingaanslag", "invorderbaar"]}
    assert k[ART12_1]["bewijs"][0]["detail"]["buiten"] is True
    assert uit["meting"]["deelvraag"]["aantal"] == len(k)
    # Zonder kern: kern.
    uit = vind(BepalingGraaf(), {**invoer, "kern": []}, methoden=("deelvraag",))
    assert {x["rol"] for x in uit["kandidaten"]} == {"kern"}
    assert zoektermen.buiten_uit_afbakening(invoer["dossier"]["afbakening"]) == "kosten van vervolging."


def test_een_geraakt_plafond_is_onvolledig(geen_overzicht, monkeypatch):
    monkeypatch.setattr(bronnen_vinden, "MAX_PER_METHODE", 1)
    uit = vind(Graaf(), INVOER, methoden=("verwijzing_uit",))
    assert uit["meting"]["verwijzing_uit"]["volledig"] is False


def test_een_falende_methode_laat_de_rest_staan(geen_overzicht):
    uit = vind(Graaf(faal="inkomend"), INVOER, methoden=ALLE)
    assert (uit["meting"]["verwijzing_in"]["aantal"], uit["meting"]["verwijzing_in"]["volledig"]) == (0, False)
    assert ART8 in _per_iri(uit)


def test_zonder_kern_alleen_het_overzicht(geen_overzicht):
    g = Graaf()
    uit = vind(g, {**INVOER, "kern": []})
    assert uit["kandidaten"] == [] and g.queries == []


# --- 3. het api-contract ----------------------------------------------------------------------------

def test_de_uitkomst_past_in_het_api_contract(geen_overzicht):
    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "api"))
    try:
        from app.bronnen_run_contracts import BronnenUitkomst
    except ImportError:
        pytest.skip("api-pakket niet importeerbaar in deze omgeving")
    finally:
        sys.path.pop(0)
    uit = vind(Graaf(), INVOER)
    BronnenUitkomst(invoer_id="I1", **uit)
    # De methode deelvraag kent de api ook.
    BronnenUitkomst(invoer_id="I1", kandidaten=[{"bron_iri": ART8, "rol": "aanverwant", "bewijs": [
        {"methode": "deelvraag", "detail": {"deelvraag_id": "d1"}}]}], meting={"deelvraag": {"aantal": 1}})


# --- 4. run en route --------------------------------------------------------------------------------

def test_het_request_model():
    # Geen tekstpatroon meer: zoeken is een taak van de deelvragen-agent, of een klik op de suggestie.
    r = ChatRequest(question="Zoek bepalingen", actie="bronnen_zoeken", werkgebied_id="wg1")
    assert r.actie == "bronnen_zoeken" and r.modus == "auto"
    with pytest.raises(ValueError):
        ChatRequest(question="x", modus="bronnen", werkgebied_id="wg1")
    with pytest.raises(ValueError):
        ChatRequest(question="x", actie="bronnen_zoeken")


class NepApi:
    def __init__(self, run_status: str = "wacht", weiger: tuple[int, dict] | None = None):
        self.run_status, self.weiger = run_status, weiger
        self.berichten: list[dict] = []
        self.uitkomst: dict | None = None
        self.mislukt: str | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        pad, m = request.url.path, request.method
        if pad == "/v1/werkgebieden/wg1" and m == "GET":
            return httpx.Response(200, json={"id": "wg1", "naam": "Invorderbaarheid"})
        if pad == "/v1/werkgebieden/wg1/bronnen-runs" and m == "POST":
            if self.weiger:
                return httpx.Response(self.weiger[0], json={"detail": self.weiger[1]})
            return httpx.Response(200, json={"id": "r1", "status": self.run_status})
        if pad.endswith("/bronnen-runs/r1") and m == "GET":
            return httpx.Response(200, json={"id": "r1", "invoer_id": "I1", "invoer": INVOER,
                                             "status": "klaar" if self.uitkomst else "loopt"})
        if pad.endswith("/loopt"):
            return httpx.Response(200, json={})
        if pad.endswith("/uitkomst"):
            self.uitkomst = json.loads(request.content)
            return httpx.Response(200, json={"status": "klaar"})
        if pad.endswith("/mislukt"):
            self.mislukt = json.loads(request.content)["reden"]
            return httpx.Response(200, json={})
        if pad.endswith("/kandidaten"):
            ks = [{**k, "status": "voorgesteld"} for k in (self.uitkomst or {}).get("kandidaten", [])]
            return httpx.Response(200, json={"run": {"meting": (self.uitkomst or {}).get("meting")}, "kandidaten": ks})
        if pad == "/v1/gesprekken/g1/berichten":
            self.berichten.append(json.loads(request.content))
            return httpx.Response(201, json={"id": 1})
        return httpx.Response(500)


@pytest.fixture
def nep(monkeypatch, geen_overzicht):
    def maak(**kw) -> NepApi:
        api = NepApi(**kw)
        echte = bronnen_run.WetsanalyseApi

        class MetTransport(echte):
            def __init__(self, settings, user_id):
                super().__init__(settings, user_id)
                self._client = httpx.AsyncClient(transport=httpx.MockTransport(api))

        monkeypatch.setattr(bronnen_run, "WetsanalyseApi", MetTransport)
        monkeypatch.setattr(bronnen_run, "PEIL_S", 0.0)
        return api
    return maak


def _settings():
    return make_settings(wetsanalyse_api_url="http://api.test", wetsanalyse_api_token="t", qa_api_token="q")


def _stroom(run: Run, graph=None) -> list[dict]:
    async def verzamel():
        return [e async for e in bronnen_run.bronnen_stroom("wg1", "r1", run, settings=_settings(), user_id="jurist",
                                                            graph=graph or Graaf())]
    return asyncio.run(verzamel())


def test_de_run_zoekt_en_zet_de_kandidaten_terug(nep):
    api = nep()
    events = _stroom(Run(run_id="x", conversation_id="werkgebied:wg1:bronnen"))
    assert [e["type"] for e in events][-2:] == ["opgeslagen", "done"]
    assert any("Verwijzingen vanuit de kern" in e.get("message", "") for e in events)
    assert api.uitkomst["invoer_id"] == "I1" and {k["bron_iri"] for k in api.uitkomst["kandidaten"]} >= {ART8, AWR}


def test_een_onbereikbare_graaf_is_een_mislukte_run(nep, monkeypatch):
    api = nep()

    class Kapot(Graaf):
        def sparql(self, query):
            raise RuntimeError("weg")

    def ook_weg(*_a, **_k):
        raise RuntimeError("weg")

    # Elke methode faalt, ook het overzicht: geen lege uitkomst maar een storing.
    monkeypatch.setattr(overzicht, "bouw_overzicht", ook_weg)
    events = _stroom(Run(run_id="x", conversation_id="c"), graph=Kapot())
    assert events[-1]["type"] == "error" and events[-1]["soort"] == "graaf"
    assert api.uitkomst is None and api.mislukt


def test_een_falende_methode_haalt_de_run_niet_onderuit(nep):
    api = nep()
    _stroom(Run(run_id="x", conversation_id="c"), graph=Graaf(faal="opbouw"))
    assert api.uitkomst["meting"]["opbouw"]["volledig"] is False
    assert all("fout" not in m for m in api.uitkomst["meting"].values())


def _zoek_run():
    async def draai():
        api = bronnen_run.WetsanalyseApi(_settings(), "jurist")
        try:
            ctx = agent_ctx(api, settings=_settings(), run_id="b1", graph=Graaf())
            return await bronnen_run.zoek_run(ctx, "wg1"), ctx.meldingen
        finally:
            await api.aclose()
    return asyncio.run(draai())


def test_zoek_run_zoekt_en_meldt_per_methode(nep):
    api = nep()
    fout, meldingen = _zoek_run()
    assert fout == "" and api.uitkomst is not None
    assert any("Verwijzingen vanuit de kern" in m for m in meldingen)


def test_zoek_run_zegt_waarom_er_geen_vertrekpunt_is(nep):
    nep(weiger=(409, {"fout": "geen_vertrekpunt", "melding": "…"}))
    fout, _ = _zoek_run()
    assert "analysevraag" in fout


def test_open_telt_vervallen_en_opgenomen_niet_mee():
    assert bronnen_run.is_open({"status": "voorgesteld"})
    assert not bronnen_run.is_open({"status": "voorgesteld", "vervallen": True})
    assert not bronnen_run.is_open({"status": "voorgesteld", "in_selectie": True})
    assert not bronnen_run.is_open({"status": "uitgesloten"})


def test_een_divisie_zonder_label_krijgt_een_naam_en_nooit_de_iri():
    """Spoor H: anders kwam de IRI in het label van de kandidaat en in de afbakening van het dossier."""
    from agent.bepaling_namen import plek_uit_iri
    iri = "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie26%2FCirculaire.divisie26.3%2FCirculaire.divisie26.3.9"
    assert plek_uit_iri(iri) == "divisie 26.3.9"
    assert "urn:bwb" not in plek_uit_iri("urn:bwb:BWBR0024096:id:BWBR0024096%2FTekst%2FOnderdeel._3")
    assert plek_uit_iri("urn:bwb:BWBR0004770") == "urn:bwb:BWBR0004770"


@pytest.mark.parametrize("tekst, buiten", [
    ("Regelingen: Invorderingswet 1990.\nBuiten de afbakening: kosten van vervolging.", "kosten van vervolging."),
    ("Alleen de Invorderingswet 1990, niet de Leidraad Invordering", "de Leidraad Invordering"),
    ("Het gaat om de betalingstermijnen. De kosten van vervolging vallen buiten de afbakening.",
     "De kosten van vervolging"),
    ("Het gaat om de betalingstermijnen. Buiten beschouwing blijft de bestuurdersaansprakelijkheid.",
     "de bestuurdersaansprakelijkheid"),
    ("Invordering van aanslagen, met uitzondering van de kosten van vervolging; ook de rente.",
     "de kosten van vervolging"),
    ("Regelingen: Invorderingswet 1990.", ""),
    ("Het gaat niet later dan de vervaldag om de aanslag.", ""),
])
def test_buiten_komt_ook_uit_een_vrij_bewerkte_afbakening(tekst, buiten):
    """*Vul het dossier aan* bewaart de afbakening zoals de analist haar typte; ook zonder de vaste regel moet de
    bronnenrun weglaten wat erbuiten valt – en nooit wat er wél bij hoort."""
    assert zoektermen.buiten_uit_afbakening(tekst) == buiten


def test_om_de_beurt_per_regeling_wet_eerst():
    """`per_regeling`: de plaatsen gaan om de beurt naar de regelingen, de hoogste soort eerst; een regeling die
    op is slaat haar beurt over, en binnen een regeling blijft de volgorde staan."""
    from agent.deelvraag_zoeken import om_de_beurt

    lr = [{"bwb_id": "BWBR0024096", "iri": f"l{i}"} for i in range(5)]
    iw = [{"bwb_id": "BWBR0004770", "iri": f"w{i}"} for i in range(2)]
    uit = om_de_beurt(lr + iw, {"BWBR0004770": 0, "BWBR0024096": 3}, ["BWBR0024096", "BWBR0004770"])
    assert [k["iri"] for k in uit] == ["w0", "l0", "w1", "l1", "l2", "l3", "l4"]
    # Eén regeling: niets te verdelen.
    assert om_de_beurt(lr, {}, ["BWBR0024096"]) == lr
    # Zonder soort (graaf hapert): de volgorde van het werkgebied.
    assert [k["iri"] for k in om_de_beurt(lr[:2] + iw[:1], {}, ["BWBR0024096", "BWBR0004770"])] == ["l0", "w0", "l1"]


# --- het dossier zoekt mee (meetlogboek `bronselectie-2026-11-04-dossier`): vier vlaggen, standaard uit ---

def _profiel(**vlaggen):
    from dataclasses import replace

    return replace(deelvraag_zoeken.STANDAARD_PROFIEL, **vlaggen)


def test_aanleiding_en_doel_leveren_alleen_met_de_vlag_dossiertermen():
    dossier = {**DOSSIER, "aanleiding": "Veel verzuimboetes", "doel": "Een werkinstructie"}
    args = {"regelingen": [IWB], "deelvraag": "Wanneer is een belastingaanslag invorderbaar?", "dossier": dossier}
    zonder = deelvraag_zoeken.kandidatenpool(BepalingGraaf(), **args)["dossiertermen"]
    met = deelvraag_zoeken.kandidatenpool(BepalingGraaf(), **args, profiel=_profiel(dossier_velden=True))
    assert "verzuimboetes" not in zonder and "werkinstructie" not in zonder
    assert {"verzuimboetes", "werkinstructie"} <= set(met["dossiertermen"])


def test_dossierlijsten_zoeken_mee_maar_een_optie_raakt_de_deelvraag():
    """Met `dossier_lijsten` is elke dossierterm een eigen lijst uit de index: artikel 8 lid 1 komt via
    "aanslagbiljet" uit het praktijkvoorbeeld in de pool. Een optie bij de deelvraag wordt het niet: het raakt
    geen deelvraagterm, en anders vulde het dossier elk kaartje (spoor K)."""
    p = _profiel(dossier_lijsten=True)
    args = {"regelingen": [IWB], "deelvraag": "Wanneer is een belastingaanslag invorderbaar?", "dossier": DOSSIER}
    pool = deelvraag_zoeken.kandidatenpool(BepalingGraaf(), **args, profiel=p)
    l8 = pool["gevonden"][f"{IW}:artikel:8:lid:1"]
    assert any(lijst.startswith("dossier:") for lijst in l8["rang"]) and "aanslagbiljet" in l8["dossier_index"]
    assert l8["index_termen"] == []                        # een dossierterm is geen deelvraagterm
    assert f"{IW}:artikel:8:lid:1" not in [o["bron_iri"] for o in _opties(profiel=p)]


@pytest.mark.parametrize("iri, omgeving", [
    (f"{IW}:artikel:36:lid:2", f"{IW}:artikel:36"),
    (f"{IW}:artikel:36:lid:5:o:a", f"{IW}:artikel:36"),
    (f"{IW}:artikel:10", f"{IW}:artikel:10"),
    ("urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie36%2FCirculaire.divisie36.5%2FCirculaire.divisie36.5.1",
     "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie36"),
])
def test_de_omgeving_is_het_artikel_of_de_eerste_divisie(iri, omgeving):
    assert deelvraag_zoeken.omgeving_van(iri) == omgeving


def test_de_omgeving_weegt_een_dossierterm_naar_zijn_zeldzaamheid():
    """"ontvanger" staat in elke omgeving en zegt niets; "bestuurder" alleen in artikel 36, dat dus vooraan
    staat. Een omgeving die alleen gewone woorden raakt, krijgt geen rang."""
    def k(iri, tekst):
        return {"iri": iri, "teksten": [tekst], "kop": ""}

    kandidaten = [k(f"{IW}:artikel:36:lid:1", "De bestuurder is aansprakelijk; de ontvanger stelt aansprakelijk."),
                  k(f"{IW}:artikel:36:lid:2", "Het lichaam doet mededeling aan de ontvanger."),
                  k(f"{IW}:artikel:2:lid:1", "De ontvanger is de ambtenaar."),
                  k(f"{IW}:artikel:25:lid:1", "De ontvanger kan uitstel verlenen.")]
    rang = deelvraag_zoeken._omgeving_rang(kandidaten, ["ontvanger", "bestuurder"], True)
    assert rang == {f"{IW}:artikel:36:lid:1": 1, f"{IW}:artikel:36:lid:2": 1}


class GelijkenisGraaf(BepalingGraaf):
    """De similarity-index vindt een lid zonder de woorden van de deelvraag, en een lid buiten de regelingen."""
    L7 = f"{IW}:artikel:7:lid:1"

    def __init__(self, faal_index: bool = False) -> None:
        super().__init__()
        self.faal_index = faal_index

    def semantic_search(self, query: str, limit: int = 10) -> str:
        self.semantic_queries.append(query)
        if self.faal_index:
            raise RuntimeError("index hapert")
        return (f'<{self.L7}> a bwb:Lid;\n  bwb:tekst "De ontvanger maakt het bedrag bekend."@nl .\n\n'
                '<urn:bwb:BWBR0002320:artikel:30:lid:2> a bwb:Lid;\n  bwb:tekst "Iets anders."@nl .\n')


def test_gelijkenis_overbrugt_de_woorden_van_de_deelvraag_binnen_de_regelingen():
    p = _profiel(gelijkenis=True)
    g = GelijkenisGraaf()
    uit = [o["bron_iri"] for o in _opties(g, profiel=p)]
    # De deelvraag en het praktijkvoorbeeld zoeken samen; een treffer telt als raak, ook zonder de woorden.
    assert g.semantic_queries == ["Wanneer is een belastingaanslag invorderbaar? Een aanslagbiljet met dagtekening 1 maart."]
    assert GelijkenisGraaf.L7 in uit and "urn:bwb:BWBR0002320:artikel:30:lid:2" not in uit
    assert GelijkenisGraaf.L7 not in [o["bron_iri"] for o in _opties(GelijkenisGraaf())]
    # Een haperende index kost alleen die lijst.
    assert _opties(GelijkenisGraaf(faal_index=True), profiel=p) == _opties(GelijkenisGraaf())


# --- zoekvraag a: de grondslag van de gekozen gebeurtenis ---------------------------------------------

def test_met_een_gebeurtenis_zoekt_de_run_de_grondslag():
    """De analist koos een gebeurtenis: dan draait `grondslag` mee (zoals `deelvraag` met deelvragen), rol kern, met
    zoekvraag, gebeurtenis, signaal en kop in het bewijs. Zonder gebeurtenis verandert de standaard niet."""
    from test_zoekvragen import IW, UR, Wereld

    kern = [{"bron_iri": f"urn:bwb:{IW}:artikel:25", "label": "", "bwb_id": IW, "bereik": "onderliggend"}]
    invoer = {"naam": "N", "analysevraag": "V?", "kern": kern,
              "context": [{"bron_iri": f"urn:bwb:{UR}:artikel:7", "label": "", "bwb_id": UR, "bereik": "onderliggend"}]}
    assert "grondslag" not in bronnen_vinden.standaard_voor(invoer)
    assert "grondslag" not in bronnen_vinden.standaard_voor({**invoer, "dossier": {"gebeurtenis": "  "}})
    met = {**invoer, "dossier": {"gebeurtenis": "kwijtschelding",
                                 "afbakening": "Buiten de afbakening: de hersteloperatie toeslagen."}}
    assert bronnen_vinden.standaard_voor(met)[-1] == "grondslag"
    uit = vind(Wereld(), met, ("grondslag",))
    assert uit["meting"]["grondslag"]["volledig"] is True
    iris = [k["bron_iri"] for k in uit["kandidaten"]]
    assert f"urn:bwb:{IW}:artikel:26:lid:1" in iris and f"urn:bwb:{IW}:artikel:26a:lid:1" not in iris
    k = next(k for k in uit["kandidaten"] if k["bron_iri"] == f"urn:bwb:{IW}:artikel:26:lid:1")
    assert k["rol"] == "kern" and k["bewijs"][0]["methode"] == "grondslag"
    assert {x: k["bewijs"][0]["detail"][x] for x in ("zoekvraag", "gebeurtenis", "signaal")} == \
        {"zoekvraag": "a", "gebeurtenis": "kwijtschelding", "signaal": "kan worden"}
    assert k["bewijs"][0]["detail"]["kop"].startswith("Afdeling 3")


def test_met_een_gebeurtenis_kiest_de_deelvraag_in_de_pool():
    """Zoekvragen a–d, PR 5: de methode `deelvraag` neemt met een gekozen gebeurtenis de opties uit de pool, met de
    zoekvraag, het signaal en de route in het bewijs. Zonder bronselectie zijn de regelingen van de gebeurtenis het
    bereik (Rekeningafspraken zocht anders in de hele graaf)."""
    from test_zoekvragen import Omgeving, UR

    invoer = {"naam": "Kwijtschelding", "analysevraag": "Wanneer?", "kern": [], "context": [],
              "deelvragen": [{"id": "d1", "vraag": "Wat kan iemand doen als het verzoek wordt afgewezen?"},
                             {"id": "d2", "vraag": "Wat wordt verstaan onder vermogen?"}],
              "dossier": {"gebeurtenis": "kwijtschelding"}}
    uit = vind(Omgeving(), invoer, ("deelvraag",))
    per = {}
    for k in uit["kandidaten"]:
        for b in k["bewijs"]:
            per.setdefault(b["detail"]["deelvraag_id"], []).append((k["bron_iri"].split(":", 2)[2], b["detail"]))
    d1 = dict(per["d1"])
    assert d1[f"{UR}:artikel:25:lid:1"]["zoekvraag"] == "c" and d1[f"{UR}:artikel:25:lid:1"]["route"] == "zoekvragen"
    assert f"{UR}:artikel:12:lid:1" in dict(per["d2"])
    assert all(iri.split(":")[0] in (UR, "BWBR0024096", "BWBR0004770") for iri, _ in per["d1"] + per["d2"])


# --- een model kiest per deelvraag (Zoekprofiel.model_kiest, meting bronselectie-2026-11-17-model) ------------------

class _Meter:
    def __init__(self) -> None:
        self.totaal = 0

    def als_dict(self) -> dict:
        return {"invoer": self.totaal, "uitvoer": 0, "cache_lees": 0, "cache_schrijf": 0, "calls": 1}


class _Model:
    def __init__(self) -> None:
        self.meter = _Meter()


def _stroom_met_model(monkeypatch, api, *, budget: bool, gekozen: list[dict] | None):
    from agent import bronnen_vinden

    monkeypatch.setitem(INVOER, "deelvragen", [{"id": "d1", "vraag": "Wanneer is een aanslag invorderbaar?"}])
    model = _Model()

    def kies(graph, vraag, regelingen, dossier, buiten, p, gebeurtenis, wetstermen=None):
        assert bronnen_vinden._MODEL.get()[0] is model
        model.meter.totaal = 1234
        return gekozen

    monkeypatch.setattr(bronnen_vinden, "_model_kiest", kies)
    geboekt: list[dict] = []

    async def boek(_api, llm, modelnaam, gesprek_id, run_id):
        geboekt.append({"run_id": run_id, "totaal": llm.meter.totaal})
        return llm.meter.totaal

    from agent import verbruik
    monkeypatch.setattr(verbruik, "boek", boek)

    async def toegestaan() -> bool:
        return budget

    async def verzamel():
        return [e async for e in bronnen_run.bronnen_stroom(
            "wg1", "r1", Run(run_id="x", conversation_id="werkgebied:wg1:bronnen"), settings=_settings(),
            user_id="jurist", graph=Graaf(), maak_llm=lambda _s: model, budget_toegestaan=toegestaan)]
    return asyncio.run(verzamel()), geboekt


def test_het_model_kiest_per_deelvraag_en_het_verbruik_wordt_geboekt(nep, monkeypatch):
    api = nep()
    gekozen = [{"bron_iri": ART8, "label": "Artikel 8", "rol": "kern", "bron": "woorden"},
               {"bron_iri": AWR, "label": "AWR", "rol": "afhankelijkheid", "bron": "pool"}]
    events, geboekt = _stroom_met_model(monkeypatch, api, budget=True, gekozen=gekozen)
    assert [e["type"] for e in events][-2:] == ["opgeslagen", "done"]
    per = {k["bron_iri"]: k for k in api.uitkomst["kandidaten"]}
    model_bewijs = [b for b in per[AWR]["bewijs"] if b["detail"].get("route") == "model"]
    assert model_bewijs and model_bewijs[0]["detail"]["deelvraag_id"] == "d1"
    assert per[AWR]["rol"] in ("afhankelijkheid", "kern")
    assert len(geboekt) == 1 and geboekt[0]["run_id"] == "bronnen-r1"


def test_zonder_budget_kiest_geen_model_en_start_niets(nep, monkeypatch):
    api = nep()
    events, geboekt = _stroom_met_model(monkeypatch, api, budget=False, gekozen=[])
    assert events[-1] == {"type": "error", "message": "Je tokenbudget voor deze periode is op.", "soort": "budget"}
    assert api.mislukt == "Het tokenbudget is op." and not geboekt


class BelangGraaf(BepalingGraaf):
    """Artikel 9 lid 2 wordt vaak genoemd, artikel 12 lid 1 één keer; de rest nooit."""

    def __init__(self, faal_belang: bool = False) -> None:
        super().__init__()
        self.faal_belang = faal_belang
        self.belang_vragen = 0

    def _antwoord(self, q: str) -> str:
        if "COUNT(DISTINCT ?bron)" in q:
            self.belang_vragen += 1
            if self.faal_belang:
                raise RuntimeError("graaf hapert")
            return _tsv(["bepaling", "aantal"], [[L9_2, "40"], [ART12_1, "1"]])
        return super()._antwoord(q)


def test_het_belang_van_verwijzingen_staat_standaard_aan():
    from dataclasses import replace

    graaf = BelangGraaf()
    assert deelvraag_zoeken.STANDAARD_PROFIEL.belang is True
    _opties(graaf)
    assert graaf.belang_vragen == 1
    uit = BelangGraaf()
    _opties(uit, profiel=replace(deelvraag_zoeken.STANDAARD_PROFIEL, belang=False))
    assert uit.belang_vragen == 0


def test_met_het_belang_gaat_een_genoemde_bepaling_omhoog():
    from dataclasses import replace

    zonder = [o["bron_iri"] for o in _opties(profiel=replace(deelvraag_zoeken.STANDAARD_PROFIEL, belang=False))]
    met = [o["bron_iri"] for o in _opties(BelangGraaf())]
    assert set(met) == set(zonder)
    # Het belang is één lijst in de fusie, geen gewicht: het verschuift, het verdringt niet.
    assert met.index(L9_2) < zonder.index(L9_2) and met[0] == zonder[0]


def test_een_haperende_graaf_kost_alleen_het_belang():
    from dataclasses import replace

    zonder = replace(deelvraag_zoeken.STANDAARD_PROFIEL, belang=False)
    assert [o["bron_iri"] for o in _opties(BelangGraaf(faal_belang=True))] == \
        [o["bron_iri"] for o in _opties(profiel=zonder)]


# --- de methode opschrift (acceptatie 18 nov 2026, LB-08) ----------------------------------------------------------

AWIR = "urn:bwb:BWBR0018472"
_OPSCHRIFTEN = [{"artikel": f"{AWIR}:artikel:{n}", "titel": t, "label": f"Artikel {n}"} for n, t in (
    ("3", "Partner"), ("4", "Kind"), ("16", "Voorschot op tegemoetkoming"),
    ("20", "Herziening tegemoetkoming wegens alsnog beschikbaar komen of wijziging fiscale gegevens na toekenning"),
    ("21", "Herziening tegemoetkoming in het nadeel van belanghebbende om andere reden"),
    ("21a", "Herziening tegemoetkoming in het voordeel van belanghebbende om andere reden"),
    ("22", "Uitbetaling voorschot"), ("24", "Uitbetaling tegemoetkoming"),
    ("26", "Terugvordering is verschuldigd door belanghebbende"), ("29", "Rente bij te late betaling terugvordering"),
    ("30", "Verrekening"))]
_KERN = [f"{AWIR}:artikel:24:lid:2", f"{AWIR}:artikel:26:lid:1"]
_TEKSTEN = [{"kern": _KERN[0], "deel": _KERN[0], "tekst": "Indien voorschotten zijn verleend, worden deze verrekend met de tegemoetkoming."},
            {"kern": _KERN[1], "deel": _KERN[1], "tekst": "Indien een herziening van een tegemoetkoming of een herziening van een "
             "voorschot leidt tot een terug te vorderen bedrag dan wel een verrekening van een voorschot met een tegemoetkoming "
             "daartoe leidt, is de belanghebbende het bedrag van de terugvordering in zijn geheel verschuldigd."}]


def test_opschrift_vindt_het_artikel_waarvan_de_kern_de_kop_noemt():
    from agent.bronnen_vinden import opschriften_in

    uit = {o["artikel"].rsplit(":", 1)[1]: o for o in opschriften_in(_TEKSTEN, _OPSCHRIFTEN, _KERN, [])}
    # 16 (voorschot + tegemoetkoming), 20/21/21a (herziening + tegemoetkoming), 30 (verrekening). Niet 24 en 26 zelf, niet
    # 22 ("uitbetaling" staat er niet), niet 3 of 4, en niet 29 ("rente" staat er niet).
    assert sorted(uit) == ["16", "20", "21", "21a", "30"]
    assert uit["16"]["kop"] == "voorschot tegemoetkoming" and uit["16"]["deel"] == _KERN[0]


def test_opschrift_houdt_zich_aan_de_afbakening_en_aan_een_onderscheidende_kop():
    from agent import bronnen_vinden as bv

    assert "30" not in {o["artikel"].rsplit(":", 1)[1] for o in bv.opschriften_in(_TEKSTEN, _OPSCHRIFTEN, _KERN, ["verreken"])}
    veel = _OPSCHRIFTEN + [{"artikel": f"{AWIR}:artikel:21b", "titel": "Herziening tegemoetkoming bij overlijden"}]
    assert not {"20", "21", "21a", "21b"} & {o["artikel"].rsplit(":", 1)[1]
                                             for o in bv.opschriften_in(_TEKSTEN, veel, _KERN, [])}


def test_de_kop_van_een_opschrift():
    from agent.bronnen_vinden import opschrift_kop

    assert opschrift_kop("Voorschot op tegemoetkoming") == ("voorschot", "tegemoetkoming")
    assert opschrift_kop("Rente bij te late betaling terugvordering") == ("rente", "betaling")
    assert opschrift_kop("Partner") == ("partner",) and opschrift_kop("Kind") == ()


def test_opschrift_staat_standaard_aan_met_een_kern():
    from agent.bronnen_vinden import standaard_voor

    assert "opschrift" in standaard_voor({"kern": [{"bron_iri": _KERN[0]}]})
    assert "opschrift" not in standaard_voor({"kern": []})


# --- de methode lid_verwijzing (acceptatie 18 nov 2026) -----------------------------------------------------------

def test_verwijzingen_naar_een_lid_van_hetzelfde_artikel():
    from agent.bronnen_vinden import lid_verwijzingen

    assert set(lid_verwijzingen("In afwijking in zoverre van het derde lid is ook na de instemming, bedoeld in dat lid")) == {3}
    assert set(lid_verwijzingen("Het eerste lid is niet van toepassing")) == {1}
    assert set(lid_verwijzingen("Voor de toepassing van het tweede en vierde lid wordt")) == {2, 4}
    assert set(lid_verwijzingen("het derde tot en met vijfde lid")) == {3, 4, 5}
    assert set(lid_verwijzingen("het eerste lid van dit artikel")) == {1}
    # Een lid van een ander artikel telt niet.
    assert not lid_verwijzingen("krachtens artikel 25, derde tot en met vijfde, achtste lid")
    assert not lid_verwijzingen("In afwijking van artikel 4:93, vierde lid, van de Algemene wet bestuursrecht")
    assert not lid_verwijzingen("bedoeld in het eerste lid van artikel 7")
    assert not lid_verwijzingen("de artikelen 8.9, eerste of tweede lid, of 8.9a")


class LedenGraaf(FakeGraph):
    """Iw 24: lid 3 is kern, lid 4 noemt het derde lid, lid 5 noemt het (in een onderdeel), lid 7 noemt niets."""

    def __init__(self) -> None:
        super().__init__(results=self._antwoord)

    def _antwoord(self, q: str) -> str:
        a = f"{IW}:artikel:24"
        if "heeftOnderdeel+" in q and "?artikel bwb:heeftLid ?lid" in q:
            return _tsv(["lid", "tekst"], [[f"{a}:lid:5", "binnen een week na de in het derde lid bedoelde kennisgeving"]])
        if "?artikel bwb:heeftLid ?lid" in q:
            return _tsv(["artikel", "lid", "tekst"], [
                [a, f"{a}:lid:2", "De verrekening is ook mogelijk ingeval de termijn, bedoeld in artikel 9, nog niet is verstreken"],
                [a, f"{a}:lid:3", "Verrekening is niet mogelijk ... De ontvanger is verplicht ... met toepassing van het tweede lid"],
                [a, f"{a}:lid:4", "In afwijking in zoverre van het derde lid is ook na de instemming verrekening mogelijk"],
                [a, f"{a}:lid:5", ""],
                [a, f"{a}:lid:7", "De ontvanger maakt de verrekening onverwijld bekend."]])
        return _tsv(["x"], [])


def test_lid_verwijzing_vindt_de_leden_die_het_kernlid_noemen_en_die_het_noemt():
    a = f"{IW}:artikel:24"
    invoer = {"naam": "N", "analysevraag": "V?", "context": [],
              "kern": [{"bron_iri": f"{a}:lid:3", "label": "", "bwb_id": IW.split(":")[-1], "bereik": "onderliggend"}]}
    uit = vind(LedenGraaf(), invoer, methoden=("lid_verwijzing",))
    k = _per_iri(uit)
    assert set(k) == {f"{a}:lid:2", f"{a}:lid:4", f"{a}:lid:5"}
    assert all(x["rol"] == "afhankelijkheid" for x in k.values())
    assert k[f"{a}:lid:4"]["bewijs"][0]["detail"]["richting"] == "noemt de kern"
    assert k[f"{a}:lid:2"]["bewijs"][0]["detail"]["richting"] == "de kern noemt het"
    assert "lid_verwijzing" in bronnen_vinden.STANDAARD  # meting 18 nov 2026


LR = "urn:bwb:BWBR0024096"


def _ld(*pad: str) -> str:
    """Een onderdeel van de Leidraad in de IRI-vorm van de importer (`…:id:BWBR0024096%2FCirculaire.divisie49%2F…`)."""
    return f"{LR}:id:BWBR0024096%2F" + "%2F".join(f"Circulaire.divisie{p}" for p in pad)


class BeleidsGraaf(FakeGraph):
    """Iw 49 met de Leidraad bij artikel 49 en 9: 49.3 (een container) met 49.3.1 "Wanneer in gebreke", 49.6 zonder
    passend opschrift, 9.1 dat artikel 9 lid 5 noemt, en 36.4.1 en 36.6.1 in het artikel van de Leidraad waarin de kern
    zelf staat."""

    def __init__(self) -> None:
        super().__init__(results=self._antwoord)

    def _antwoord(self, q: str) -> str:
        if "bwb:verwijstNaar ?artikel" in q:
            rijen = []
            if f"<{LR}:artikel:49>" not in q and f"<{IW}:artikel:49>" in q:
                a = f"{LR}:artikel:49"
                rijen += [[a, _ld("49", "49.3"), "De aansprakelijkstelling – in gebreke zijn", "49.3", ""],
                          [a, _ld("49", "49.3", "49.3.1"), "Wanneer in gebreke", "49.3.1", ""],
                          [a, _ld("49", "49.3", "49.3.2"), "In gebreke zijn en versnelde invordering", "49.3.2", ""],
                          [a, _ld("49", "49.6"), "Volgorde van uitwinning", "49.6", ""]]
            if f"<{IW}:artikel:9>" in q:
                a = f"{LR}:artikel:9"
                rijen += [[a, _ld("9", "9.1"), "Afwijking van de betalingstermijnen", "9.1", f"{IW}:artikel:9:lid:5"],
                          [a, _ld("9", "9.4"), "Dagtekening aanslagbiljet", "9.4", ""]]
            if _ld("36", "36.4", "36.4.1") in q:
                a = f"{LR}:artikel:36"
                rijen += [[a, _ld("36", "36.4", "36.4.1"), "Wanneer kennelijk onbehoorlijk bestuur", "36.4.1", ""],
                          [a, _ld("36", "36.6", "36.6.1"), "Onbehoorlijk bestuur en bewijslast", "36.6.1", ""]]
            return _tsv(["regel", "onderdeel", "titel", "label", "naar"], rijen)
        if "?kern ?deel ?tekst" in q:
            return _tsv(["kern", "deel", "tekst"], [
                [f"{IW}:artikel:49:lid:1", f"{IW}:artikel:49:lid:1",
                 "Aansprakelijkstelling geschiedt … niet vóór het tijdstip waarop de belastingschuldige in gebreke is"],
                [f"{IW}:artikel:9:lid:5", f"{IW}:artikel:9:lid:5", "In afwijking van het eerste lid is een voorlopige aanslag"],
                [_ld("36", "36.4", "36.4.1"), _ld("36", "36.4", "36.4.1"),
                 "De vraag of sprake is van kennelijk onbehoorlijk bestuur"]])
        return _tsv(["x"], [])


def _kern(*iris: str) -> dict:
    return {"naam": "N", "analysevraag": "V?", "context": [],
            "kern": [{"bron_iri": i, "label": "", "bwb_id": i.split(":")[2], "bereik": "onderliggend"} for i in iris]}


def test_beleidsregel_vindt_het_onderdeel_bij_het_artikel_van_de_kern():
    uit = vind(BeleidsGraaf(), _kern(f"{IW}:artikel:49:lid:1", f"{IW}:artikel:9:lid:5"), methoden=("beleidsregel",))
    k = _per_iri(uit)
    # 49.3.1: de kop van het opschrift ("gebreke") staat in de kern; van 49.3 en 49.3.1 blijft het binnenste over.
    # 49.3.2 noemt "versnelde", dat de kern niet noemt; 49.6 en 9.4 passen niet.
    assert set(k) == {_ld("49", "49.3", "49.3.1"), _ld("9", "9.1")}
    assert all(x["rol"] == "afhankelijkheid" for x in k.values())
    b = k[_ld("49", "49.3", "49.3.1")]["bewijs"][0]
    assert b["methode"] == "beleidsregel" and b["detail"]["grond"] == "opschrift" and b["detail"]["kop"] == "gebreke"
    assert b["detail"]["beleidsregel"] == f"{LR}:artikel:49"
    # 9.1 noemt artikel 9 lid 5 zelf.
    assert k[_ld("9", "9.1")]["bewijs"][0]["detail"]["grond"] == "noemt de kern"
    assert k[_ld("9", "9.1")]["bewijs"][0]["vanuit"] == f"{IW}:artikel:9:lid:5"


def test_beleidsregel_vindt_een_onderdeel_naast_de_kern_in_dezelfde_beleidsregel():
    uit = vind(BeleidsGraaf(), _kern(_ld("36", "36.4", "36.4.1")), methoden=("beleidsregel",))
    assert set(_per_iri(uit)) == {_ld("36", "36.6", "36.6.1")}


def test_beleidsregel_zonder_beleidsregel_bij_de_kern_vraagt_wel_maar_vindt_niets():
    uit = vind(BeleidsGraaf(), _kern(f"{IW}:artikel:24:lid:1"), methoden=("beleidsregel",))
    assert uit["kandidaten"] == [] and uit["meting"]["beleidsregel"]["volledig"]


def test_artikel_van():
    from agent.bronnen_vinden import artikel_van

    assert artikel_van(f"{IW}:artikel:24:lid:3") == f"{IW}:artikel:24"
    assert artikel_van(f"{IW}:artikel:24") == f"{IW}:artikel:24"
    assert artikel_van(_ld("36", "36.4")) == _ld("36", "36.4")


def test_artikelleden_stelt_de_andere_leden_van_het_artikel_van_een_kernlid_voor():
    a = f"{IW}:artikel:24"
    invoer = {"naam": "N", "analysevraag": "V?", "context": [],
              "kern": [{"bron_iri": f"{a}:lid:3", "label": "", "bwb_id": IW.split(":")[-1], "bereik": "onderliggend"}]}
    uit = vind(LedenGraaf(), invoer, methoden=("artikelleden",))
    k = _per_iri(uit)
    assert set(k) == {f"{a}:lid:2", f"{a}:lid:4", f"{a}:lid:5", f"{a}:lid:7"}
    assert all(x["rol"] == "aanverwant" and x["bewijs"][0]["vanuit"] == f"{a}:lid:3" for x in k.values())
    assert "artikelleden" in bronnen_vinden.STANDAARD  # ketenmeting 18 nov 2026


def test_artikelleden_zonder_kernlid_doet_niets():
    uit = vind(LedenGraaf(), {"naam": "N", "analysevraag": "V?", "context": [],
                              "kern": [{"bron_iri": f"{IW}:artikel:24", "label": "", "bwb_id": "BWBR0004770",
                                        "bereik": "onderliggend"}]}, methoden=("artikelleden",))
    assert uit["kandidaten"] == [] and uit["meting"]["artikelleden"].get("zonder_vraag")
