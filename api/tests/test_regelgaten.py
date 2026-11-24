"""De volledigheidstoets van een afleidingsregel (ADR-018 besluit 7.6, bundel 5): de gaten van het regelobject en de
keten, met code, plek en melding uit de skill. Een gat is een signaal en blokkeert het accorderen niet."""
from __future__ import annotations

from app import regel_store
from app.jas_regelgaten import GATEN
from gedeelde_bron import ART, client, database, graaf  # noqa: F401
from test_regels import _begrip, _inhoud, _opzet, _url

LEEG = {"met_begrip": set(), "rollen": {}, "waarden": {}, "context": [], "labels": {}, "operatoren": [],
        "uitvoeren": set()}


def _codes(gaten) -> list[str]:
    return [g["code"] for g in gaten]


def _drager(eid, rol, eigenaar="urn:bwb:X:artikel:1:lid:1", beoordeling="open"):
    return {"element_id": eid, "rol": rol, "beoordeling": beoordeling, "bewijs": {"eigenaar_iri": eigenaar}}


def _regel(**invoer):
    return {"regelbegrip_id": "r", "uitvoer_begrip_id": "u", "invoer": [{"begrip_id": k, "rol": v} for k, v in invoer.items()]}


BEGRIPPEN = {"r": {"naam": "bepalen termijnbedrag"}, "u": {"naam": "termijnbedrag"},
             "p": {"naam": "drempel", "definitie": "Het bedrag van € 49."}, "i": {"naam": "aantal termijnen"}}


def test_elke_code_van_deze_toets_staat_in_de_skill():
    for code in ("uitvoer_zonder_begrip", "regelbegrip_zonder_bepalen", "parameter_zonder_tijdvak",
                 "parameterwaarde_in_definitie", "rust_op_contextbron", "operator_zonder_begrip", "impliciete_invoer"):
        assert GATEN[code]["plek"] == "regel"
    assert {GATEN[c]["plek"] for c in ("zelfde_uitvoer", "regelbegrip_meer_uitvoeren")} == {"keten"}


def test_een_volledige_regel_heeft_geen_gaten():
    g = {**LEEG, "met_begrip": {"uit"}, "rollen": {"i": {"duiding"}}, "waarden": {"p": [{"geldig_vanaf": "2026-01-01"}]}}
    begrippen = {**BEGRIPPEN, "p": {"naam": "drempel", "definitie": "Het bedrag waarboven de regel geldt."}}
    assert regel_store.regel_gaten(_regel(i="invoer", p="parameter"), [_drager("uit", "uitvoer")], begrippen, g) == []


def test_de_gaten_van_het_regelobject():
    g = {**LEEG, "context": ["urn:bwb:Y:artikel:9"], "labels": {"urn:bwb:Y:artikel:9": "Leidraad 9.1"},
         "operatoren": [{"id": "op", "tekst": "meer dan", "binnen": {"ar"}}]}
    dragers = [_drager("uit", "uitvoer"), _drager("ar", "grondslag", eigenaar="urn:bwb:Y:artikel:9:lid:1")]
    begrippen = {**BEGRIPPEN, "r": {"naam": "termijnbedrag berekenen"}}
    gaten = regel_store.regel_gaten(_regel(i="invoer", p="parameter"), dragers, begrippen, g)
    assert _codes(gaten) == ["uitvoer_zonder_begrip", "regelbegrip_zonder_bepalen", "impliciete_invoer",
                             "parameter_zonder_tijdvak", "parameterwaarde_in_definitie", "rust_op_contextbron",
                             "operator_zonder_begrip"]
    assert {g["plek"] for g in gaten} == {"regel"}
    tekst = {g["code"]: g["tekst"] for g in gaten}
    assert tekst["rust_op_contextbron"] == ("De regel rust op een bron met de rol context (Leidraad 9.1). Wordt dit een bron "
                                            "om te analyseren?")
    assert "drempel" in tekst["parameter_zonder_tijdvak"] and "\"meer dan\"" in tekst["operator_zonder_begrip"]


def test_een_invoer_die_een_andere_regel_afleidt_is_niet_impliciet():
    g = {**LEEG, "met_begrip": {"uit"}, "uitvoeren": {"i"}}
    assert regel_store.regel_gaten(_regel(i="invoer"), [_drager("uit", "uitvoer")], BEGRIPPEN, g) == []
    # Een afgewezen drager telt niet mee: zijn formulering is geen uitvoer meer.
    assert regel_store.regel_gaten(_regel(), [_drager("x", "uitvoer", beoordeling="afgewezen")], BEGRIPPEN, LEEG) == []


def test_de_keten_noemt_een_regelbegrip_met_meer_uitvoeren():
    def regel(id_, rb, uit):
        return {"id": id_, "status": "concept", "naam": "", "uitvoer": "", "begrippen": {},
                "inhoud": {"regelbegrip_id": rb, "uitvoer_begrip_id": uit, "invoer": [], "soort": "rekenregel",
                           "gevallen": [{}]}}
    k = regel_store.keten([regel("a", "rb", "x"), regel("b", "rb", "y"), regel("c", "rc", "x")])
    codes = sorted(s["code"] for s in k["signalen"])
    assert codes == ["regelbegrip_meer_uitvoeren", "zelfde_uitvoer"]
    [meer] = [s for s in k["signalen"] if s["code"] == "regelbegrip_meer_uitvoeren"]
    assert meer["begrip_id"] == "rb" and sorted(meer["regel_ids"]) == ["a", "b"]


async def test_de_api_geeft_de_gaten_bij_de_regel(client):
    """Door de api heen: een invoer die alleen op de afleidingsregel rust (rol `afgeleid`) en die geen regel afleidt, is
    impliciet. Zodra een tweede regel haar afleidt, verdwijnt het gat. De poort verandert er niet door."""
    wg, ids, b = await _opzet(client)
    tussen = await _begrip(client, wg, "resterende maanden", ids["ar"], rol="afgeleid")
    inhoud = _inhoud(b, invoer=[{"begrip_id": tussen["id"]}],
                     gevallen=[{"uitkomst": [{"soort": "begrip", "begrip_id": tussen["id"]}]}])
    r = await client.post(_url(wg), json={"inhoud": inhoud, "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})
    assert r.status_code == 201, r.text
    regel = r.json()
    assert _codes(regel["gaten"]) == ["impliciete_invoer"]
    assert "resterende maanden" in regel["gaten"][0]["tekst"]
    bepalen = await _begrip(client, wg, "bepalen resterende maanden", ids["ar"], rol="afgeleid")
    tweede = {**_inhoud(b), "regelbegrip_id": bepalen["id"], "uitvoer_begrip_id": tussen["id"]}
    r = await client.post(_url(wg), json={"inhoud": tweede, "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})
    assert r.status_code == 201, r.text
    regel = (await client.get(_url(wg, regel["id"]))).json()
    assert regel["gaten"] == []


# --- L-3a-2: het begrip zelf ------------------------------------------------------------------------------------------

def _k(klasse, rol="duiding"):
    return {"rol": rol, "beoordeling": "open", "bewijs": {"klasse": klasse}}


def test_een_homoniem_in_de_alternatieve_termen():
    from app.begrip_store import eenduidigheid
    punten = eenduidigheid({"naam": "aanslag", "alternatieve_termen": ["Termijn", "aanslagbiljet"]},
                           [_k("Rechtsobject")], {"termijn": "termijn", "belastingaanslag": "belastingaanslag"})
    assert punten == ['De alternatieve term "Termijn" is ook de naam van het begrip "termijn" in dit werkgebied: '
                      "een homoniem?"]


def test_een_waarde_in_de_definitie_van_een_parameter():
    from app.begrip_store import eenduidigheid
    par = {"naam": "drempel", "definitie": "Het bedrag van € 49 per jaar."}
    assert eenduidigheid(par, [_k("Parameter en parameterwaarde")], {}) == [
        "De definitie noemt een waarde; bij een parameter is de waarde een eigen begrip in een tijdvak."]
    # Een variabele mag een getal in de definitie hebben ("de 1e dag"); een afgewezen koppeling telt niet.
    assert eenduidigheid(par, [_k("Variabele en variabelewaarde")], {}) == []
    assert eenduidigheid(par, [{**_k("Parameter en parameterwaarde"), "beoordeling": "afgewezen"}], {}) == []


async def test_de_lijst_en_de_kaart_noemen_het_homoniem(client):
    wg, ids, b = await _opzet(client)
    url = f"/v1/werkgebieden/{wg['id']}/begrippen/{b['in']['id']}"
    begrip = (await client.get(url)).json()
    r = await client.patch(url, json={"verwachte_revisie": begrip["revisie"],
                                      "inhoud": {**begrip["inhoud"], "alternatieve_termen": ["termijnbedrag"]}})
    assert r.status_code == 200, r.text
    homoniem = 'De alternatieve term "termijnbedrag" is ook de naam van het begrip "termijnbedrag" in dit werkgebied: '
    assert any(p.startswith(homoniem) for p in (await client.get(url)).json()["aandachtspunten"])
    lijst = (await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen")).json()
    rij = next(x for x in (lijst.get("begrippen") or lijst) if x["id"] == b["in"]["id"])
    assert any(p.startswith(homoniem) for p in rij["aandachtspunten"])


def test_bepalen_van_het_heet_bepalen_met_de_uitvoer():
    """Besluit 5b van de eigenaar (plan lessen Termijnen-bibliotheek §7): "bepalen <uitvoer>", zonder "van de/het"."""
    g = {**LEEG, "met_begrip": {"uit"}}
    for naam, voorstel in (("bepalen van het termijnbedrag", "bepalen termijnbedrag"),
                           ("Bepalen van de vervaldag", "Bepalen vervaldag"),
                           ("bepalen van een termijn", "bepalen termijn")):
        gaten = regel_store.regel_gaten(_regel(), [_drager("uit", "uitvoer")], {**BEGRIPPEN, "r": {"naam": naam}}, g)
        assert _codes(gaten) == ["regelbegrip_bepalen_van"], naam
        assert f'"{voorstel}"' in gaten[0]["tekst"] and f'"{naam}"' in gaten[0]["tekst"]
    for naam in ("bepalen termijnbedrag", "bepalen termijn van betaling", "bepalen vandaag", "bepalen van"):
        assert regel_store.regelbegrip_voorstel(naam) is None, naam
