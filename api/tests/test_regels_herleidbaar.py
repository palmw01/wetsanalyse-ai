"""Van een afleidingsregel terug naar de wettekst (rapport *regels-herleidbaarheid*, 20 nov 2026): de bronreferentie
per drager, een voorwaarde die naar een geval van een andere regel verwijst, en de gaten voor wat op niets rust."""
from __future__ import annotations

from app import annotatie_v2_store as store, regel_store
from test_regels import _begrip, _inhoud, _opzet, _url
from gedeelde_bron import ONE, client, database, graaf  # noqa: F401


def test_de_bronreferentie_verzint_geen_jci():
    assert store.bronreferentie({"bron_iri": "x", "jci": "jci1.3:c:B&artikel=9"})["soort"] == "jci"
    # Een Leidraad-divisie zonder jci heeft een werkend anker, geen afgeleide jci.
    ref = store.bronreferentie({"bron_iri": "x", "bron_url": "https://example.test/B/2026-07-01#d9_d9.1"})
    assert (ref["soort"], ref["jci"]) == ("anker", "")
    assert store.bronreferentie(None)["soort"] == "geen"


async def _regel(client, wg, b, ids, inhoud=None, dragers=None):
    r = await client.post(_url(wg), json={"inhoud": inhoud or _inhoud(b),
                                          "dragers": dragers or [{"element_id": ids["ar"], "rol": "grondslag"}]})
    assert r.status_code == 201, r.text
    return r.json()


async def test_een_drager_noemt_zijn_bronnode(client):
    wg, ids, b = await _opzet(client)
    regel = await _regel(client, wg, b, ids)
    d = regel["dragers"][0]
    assert d["bron"]["bron_iri"] == ONE == d["bewijs"]["eigenaar_iri"]
    assert d["bron"]["label"] == "Lid 1" and d["bron"]["soort"] in ("jci", "anker", "geen")
    smal = (await client.get(_url(wg, regel["id"], "dragers"))).json()["dragers"][0]
    assert smal["bron"] == d["bron"]


async def test_een_voorwaarde_verwijst_naar_een_geval_van_een_andere_regel(client):
    wg, ids, b = await _opzet(client)
    onder = await _regel(client, wg, b, ids)          # leidt `termijnbedrag` af
    boven_uit = await _begrip(client, wg, "uitbetaling", ids["ar"], rol="afgeleid")
    boven_regel = await _begrip(client, wg, "bepalen van de uitbetaling", ids["ar"], rol="afgeleid")

    def boven(geval_van, invoer=True):
        return {"soort": "beslisregel", "regelbegrip_id": boven_regel["id"], "uitvoer_begrip_id": boven_uit["id"],
                "invoer": [{"begrip_id": b["uit"]["id"]}] if invoer else [],
                "gevallen": [{"voorwaarden": {"delen": [{"tekst": "het termijnbedrag is bepaald", "geval_van": geval_van}]},
                              "uitkomst": [{"soort": "tekst", "tekst": "in één keer"}]}]}

    dragers = [{"element_id": ids["ar"], "rol": "grondslag"}]
    # Een onbekende regel, een geval dat de regel niet heeft: 422.
    r = await client.post(_url(wg), json={"inhoud": boven({"regel_id": "bestaat-niet"}), "dragers": dragers})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "verwijzing_onbekend"
    r = await client.post(_url(wg), json={"inhoud": boven({"regel_id": onder["id"], "geval": "lid 9"}), "dragers": dragers})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "verwijzing_onbekend"

    # Zonder de uitvoer als invoer is het een gat; de keten krijgt de pijl wel, met het geval.
    regel = await _regel(client, wg, b, ids, boven({"regel_id": onder["id"]}, invoer=False), dragers)
    assert "verwijzing_zonder_invoer" in {g["code"] for g in regel["gaten"]}
    assert "voorwaarde_zonder_markering" not in {g["code"] for g in regel["gaten"]}
    keten = (await client.get(_url(wg, "hierarchie"))).json()
    pijl = next(p for p in keten["pijlen"] if p["naar"] == regel["id"])
    assert (pijl["van"], pijl["via"], pijl["gevallen"]) == (onder["id"], "voorwaarde", [{"van_geval": "", "in_geval": ""}])
    assert keten["volgorde"].index(onder["id"]) < keten["volgorde"].index(regel["id"])

    # Met de uitvoer als invoer: één pijl via de invoer, met het geval erbij, en geen gat.
    regel = (await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"],
                                                             "inhoud": boven({"regel_id": onder["id"]})})).json()
    assert "verwijzing_zonder_invoer" not in {g["code"] for g in regel["gaten"]}
    pijlen = [p for p in (await client.get(_url(wg, "hierarchie"))).json()["pijlen"] if p["naar"] == regel["id"]]
    assert len(pijlen) == 1 and pijlen[0]["via"] == "invoer" and pijlen[0]["gevallen"]

    # Wordt de onderliggende regel afgewezen, dan is de verwijzing een gat, geen fout.
    await client.post(_url(wg, onder["id"], "afwijzen"), json={"verwachte_revisie": onder["revisie"], "reden": "Fout"})
    regel = (await client.get(_url(wg, regel["id"]))).json()
    assert "verwijzing_niet_geldig" in {g["code"] for g in regel["gaten"]}


async def test_wat_op_niets_rust_is_een_gat(client):
    wg, ids, b = await _opzet(client)
    inhoud = _inhoud(b)
    inhoud["gevallen"][0]["voorwaarden"] = {"delen": [{"tekst": "het bedrag is positief"}]}
    inhoud["gevallen"][0]["uitkomst"].append({"soort": "begrip", "begrip_id": b["regel"]["id"]})
    regel = await _regel(client, wg, b, ids, inhoud)
    codes = [g["code"] for g in regel["gaten"]]
    assert "voorwaarde_zonder_markering" in codes and "uitkomstbegrip_geen_invoer" in codes
    # Een gat blokkeert niet, en een voorwaarde zonder verwijzing draagt geen `geval_van: null`.
    assert "geval_van" not in regel["inhoud"]["gevallen"][0]["voorwaarden"]["delen"][0]


async def test_een_gelijke_patch_van_een_oude_regel_geeft_geen_revisie(client):
    wg, ids, b = await _opzet(client)
    inhoud = _inhoud(b)
    inhoud["gevallen"][0]["voorwaarden"] = {"delen": [{"tekst": "het bedrag is positief", "element_ids": [ids["var"]]}]}
    regel = await _regel(client, wg, b, ids, inhoud)
    r = await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"], "inhoud": regel["inhoud"]})
    assert r.status_code == 200 and r.json()["revisie"] == regel["revisie"]


def test_dragen_gaten_is_puur():
    inhoud = {"uitvoer_begrip_id": "u", "invoer": [{"begrip_id": "i"}],
              "gevallen": [{"label": "", "uitkomst": [{"soort": "begrip", "begrip_id": "i"}],
                            "voorwaarden": {"delen": [{"tekst": "t", "geval_van": {"regel_id": "r", "geval": ""}}]}}]}
    regels = {"r": {"status": "concept", "labels": [""], "uitvoer": "i", "naam": "bepalen van i"}}
    assert regel_store.dragen_gaten(inhoud, {}, regels) == []


def test_toets_voorbeeld_rekent_niet_maar_ziet_tegenspraak():
    inhoud = {"uitvoer_begrip_id": "u", "invoer": [{"begrip_id": "a", "rol": "invoer"}, {"begrip_id": "p", "rol": "parameter"}],
              "gevallen": [
                  {"label": "lid 5", "voorrang": 0, "uitkomst": [{"soort": "begrip", "begrip_id": "a"}],
                   "voorwaarden": {"delen": [{"tekst": "aantal volgens lid 5", "geval_van": {"regel_id": "R1", "geval": "lid 5"}}]}},
                  {"label": "lid 7", "voorrang": 1, "uitkomst": [{"soort": "tekst", "tekst": "x"}],
                   "voorwaarden": {"verband": "een_van", "delen": [
                       {"tekst": "aantal volgens lid 7", "geval_van": {"regel_id": "R1", "geval": "lid 7"}},
                       {"tekst": "iets anders"}]}}]}
    codes = lambda v: [b["code"] for b in regel_store.toets_voorbeeld(inhoud, v)]  # noqa: E731
    goed = {"geval": "lid 5", "invoer": "x", "uitkomst": "y", "waarden": [{"begrip_id": "a", "waarde": "3"}],
            "van_geval": [{"regel_id": "R1", "geval": "lid 5"}]}
    assert codes(goed) == []
    assert codes({**goed, "van_geval": [{"regel_id": "R1", "geval": "lid 6"}]}) == ["geval_past_niet"]
    # Lid 7 gaat voor, en geldt volgens het geval eronder: dan past lid 5 niet, en lid 7 gaat voor.
    assert "geval_past_niet" in codes({**goed, "van_geval": [{"regel_id": "R1", "geval": "lid 7"}]})
    assert codes({**goed, "waarden": [{"begrip_id": "p", "waarde": "6 weken"}]}) == ["invoer_ontbreekt"]
    assert codes({"geval": "lid 5", "invoer": "a is 3", "uitkomst": "3"}) == ["niet_narekenbaar"]
    # Een `een_van` met een onbekend deel is onbekend, geen tegenspraak.
    assert codes({"geval": "lid 7", "invoer": "x", "uitkomst": "x", "van_geval": [{"regel_id": "R1", "geval": "lid 6"}]}) == []


async def test_een_voorbeeld_met_waarden_per_invoerbegrip(client):
    wg, ids, b = await _opzet(client)
    regel = await _regel(client, wg, b, ids)
    vb = {"invoer": "bedrag 1200, 12 termijnen", "uitkomst": "100",
          "waarden": [{"begrip_id": b["in"]["id"], "waarde": "12"}]}
    r = await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"],
                                                        "inhoud": {**_inhoud(b), "voorbeelden": [vb]}})
    assert r.status_code == 200, r.text
    regel = r.json()
    smal = (await client.get(_url(wg, regel["id"], "voorbeelden"))).json()["voorbeelden"][0]
    assert smal["waarden"] == vb["waarden"] and smal["toets"] == []
    assert not any("niet na te rekenen" in s for s in regel["signalen"])
    # Een waarde voor een begrip dat geen invoer is: 422.
    fout = {**vb, "waarden": [{"begrip_id": b["uit"]["id"], "waarde": "100"}]}
    r = await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"],
                                                        "inhoud": {**_inhoud(b), "voorbeelden": [fout]}})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "waarde_geen_invoer"
    # Zonder waarden is het een signaal, geen poort.
    kaal = {"invoer": "bedrag 1200, 12 termijnen", "uitkomst": "100"}
    regel = (await client.patch(_url(wg, regel["id"]), json={"verwachte_revisie": regel["revisie"],
                                                             "inhoud": {**_inhoud(b), "voorbeelden": [kaal]}})).json()
    assert any("Voorbeeld 1 is niet na te rekenen" in s for s in regel["signalen"])
    assert "waarden" not in regel["inhoud"]["voorbeelden"][0]


async def test_het_werkgebied_draagt_zijn_regels_in_het_kort(client):
    wg, ids, b = await _opzet(client)
    leeg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()["regels"]
    assert leeg == {"telling": {}, "afgekapt": 0, "regels": []}
    regel = await _regel(client, wg, b, ids)
    kort = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()["regels"]
    assert kort["telling"] == {"concept": 1}
    assert kort["regels"] == [{"id": regel["id"], "naam": "bepalen van het termijnbedrag", "uitvoer": "termijnbedrag",
                               "status": "concept", "soort": "rekenregel", "brontype": "wet", "gevallen": 1}]


async def test_de_opvolging_met_namen_de_korte_vorm_en_korte_revisies(client):
    """Herhaalmeting na #1796: de namen van voorganger en opvolger staan bij de regel, de korte vorm noemt `opvolger_van`,
    en `…/revisies?vorm=kort` laat de inhoud per revisie weg."""
    wg, ids, b = await _opzet(client)
    oud = await _regel(client, wg, b, ids)
    nieuw = await _regel(client, wg, b, ids)
    r = await client.post(_url(wg, oud["id"], "afwijzen"),
                          json={"verwachte_revisie": oud["revisie"], "reden": "Samengevoegd", "opvolger_id": nieuw["id"]})
    assert r.status_code == 200, r.text
    oud, nieuw = r.json(), (await client.get(_url(wg, nieuw["id"]))).json()
    naam = "bepalen van het termijnbedrag"
    assert oud["opvolging"] == {"vervangen_door": {"id": nieuw["id"], "naam": naam}, "vervangt": []}
    assert nieuw["opvolging"] == {"vervangen_door": None, "vervangt": [{"id": oud["id"], "naam": naam}]}
    kort = (await client.get(_url(wg, nieuw["id"]) + "?vorm=kort")).json()
    assert kort["opvolger_van"] == oud["id"] and kort["opvolging"]["vervangt"][0]["naam"] == naam
    volledig = (await client.get(_url(wg, oud["id"], "revisies"))).json()["revisies"]
    smal = (await client.get(_url(wg, oud["id"], "revisies") + "?vorm=kort")).json()["revisies"]
    assert "inhoud" in volledig[0] and "inhoud" not in smal[0] and smal[0]["actie"] == "regel-vervangen"
