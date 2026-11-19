"""Open punten in de api (L-X-1, ADR-018 §6): de vorm uit de skill, waar het aan hangt, de keuze van de jurist, de
status uit keuze en toetsen, revisies en audit, Lex leest mee in het werkgebied, het rapport, en het wissen."""
from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import func, select

from app import agent_toegang, db
from app.open_punt_contracts import SOORT_NAMEN, Soort
from gedeelde_bron import ART, _bron, _nieuw, client, database, graaf  # noqa: F401
from test_regels import _annoteer
from test_werkgebied_deelvragen import _dv

SKILL = Path(__file__).resolve().parents[2] / ".claude" / "skills" / "wetsanalyse" / "references" / "afleidingsregels.md"


def _url(wg, *rest) -> str:
    return "/".join([f"/v1/werkgebieden/{wg['id']}/open-punten", *rest])


def _keuze(hangt_aan, **extra) -> dict:
    return {"soort": "interpretatiekeuze", "vraag": "Saldering per termijn of over het jaar?", "hangt_aan": hangt_aan,
            "lezingen": [{"label": "A", "omschrijving": "Per termijn.", "grondslag": [{"soort": "bron", "id": ART}]},
                         {"label": "B", "omschrijving": "Over het jaar."}],
            "te_toetsen": [{"bronsoort": "wetsgeschiedenis", "omschrijving": "MvT bij lid 5"}], **extra}


async def _opzet(client):
    ids = await _annoteer()
    wg = (await _bron(client, await _nieuw(client), bron_iri=ART))["werkgebied"]
    return wg, ids


def test_de_soorten_zijn_die_van_de_skill():
    """De codes staan in de api, de namen in de skill (*Wat open blijft*): een vijfde soort of een andere naam is drift."""
    tekst = SKILL.read_text(encoding="utf-8")
    deel = tekst[tekst.index("## Wat open blijft"):]
    regel = re.search(r"de soort:\s*(?P<lijst>[^;\n]+)", deel)["lijst"]
    namen = [n.strip() for n in re.split(r",| of ", regel) if n.strip()]
    assert namen == [SOORT_NAMEN[s] for s in Soort]


def test_het_besluit_is_van_de_jurist_en_niet_van_het_agent_token():
    assert not agent_toegang.mag(agent_toegang.AGENT_CLIENT, "POST", "/werkgebieden/{a}/open-punten/{b}/besluit")
    assert not agent_toegang.mag(agent_toegang.AGENT_CLIENT, "POST", "/werkgebieden/{a}/open-punten")
    assert agent_toegang.mag("werkplek", "POST", "/werkgebieden/{a}/open-punten/{b}/besluit")


async def test_van_open_via_gekozen_naar_getoetst(client):
    wg, ids = await _opzet(client)
    r = await client.post(_url(wg), json={"inhoud": _keuze([{"soort": "markering", "id": ids["ar"]}]), "herkomst": "lex"})
    assert r.status_code == 201, r.text
    p = r.json()
    assert (p["status"], p["soort_naam"], p["herkomst"]) == ("open", "interpretatiekeuze", "lex")
    assert p["inhoud"]["hangt_aan"][0]["bestaat"] is True

    # Een lezing die er niet is, of een keuze zonder lezing, is een fout van de client.
    r = await client.post(_url(wg, p["id"], "besluit"), json={"verwachte_revisie": 1, "gekozen": "C"})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "lezing_onbekend"
    r = await client.post(_url(wg, p["id"], "besluit"),
                          json={"verwachte_revisie": 1, "gekozen": "B", "methode": "wetshistorisch",
                                "motivering": "De MvT spreekt van het jaar."})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["status"] == "gekozen" and p["keuze"]["gekozen"] == "B" and p["keuze"]["door"] == "jurist-a"
    assert p["keuze"]["methode"] == "wetshistorisch"

    # Toetsen afvinken via de inhoud: dan getoetst. De client zet de status nooit zelf.
    inhoud = {**p["inhoud"], "hangt_aan": [{"soort": "markering", "id": ids["ar"]}],
              "te_toetsen": [{"bronsoort": "wetsgeschiedenis", "omschrijving": "MvT bij lid 5", "getoetst": True,
                              "uitkomst": "De MvT bevestigt B."}]}
    r = await client.patch(_url(wg, p["id"]), json={"verwachte_revisie": p["revisie"], "inhoud": inhoud})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "getoetst"

    # Een verouderde revisie is een 412; leeg besluiten heropent.
    r = await client.post(_url(wg, p["id"], "besluit"), json={"verwachte_revisie": 1})
    assert r.status_code == 412
    r = await client.post(_url(wg, p["id"], "besluit"), json={"verwachte_revisie": r.json()["detail"]["revisie"]})
    assert r.status_code == 200 and r.json()["status"] == "open" and r.json()["keuze"] is None

    revs = (await client.get(_url(wg, p["id"], "revisies"))).json()["revisies"]
    assert [x["actie"] for x in revs] == ["open-punt-heropend", "open-punt-gewijzigd", "open-punt-besloten",
                                         "open-punt-aangemaakt"]
    a = db.werkgebied_audit
    async with db.get_engine().connect() as conn:
        acties = (await conn.execute(select(a.c.actie).where(a.c.werkgebied_id == wg["id"]))).scalars().all()
    assert {"open-punt-aangemaakt", "open-punt-besloten", "open-punt-heropend"} <= set(acties)


async def test_de_vorm_uit_de_skill_wordt_getoetst(client):
    wg, ids = await _opzet(client)
    aan = [{"soort": "markering", "id": ids["ar"]}]
    # Een interpretatiekeuze heeft ten minste twee lezingen; een toets die getoetst is, zegt wat hij opleverde.
    r = await client.post(_url(wg), json={"inhoud": _keuze(aan, lezingen=[{"label": "A", "omschrijving": "x"}])})
    assert r.status_code == 422
    r = await client.post(_url(wg), json={"inhoud": _keuze(aan, te_toetsen=[{"bronsoort": "jurisprudentie",
                                                                               "getoetst": True}])})
    assert r.status_code == 422
    # Waar het aan hangt, bestaat in dit werkgebied.
    r = await client.post(_url(wg), json={"inhoud": _keuze([{"soort": "regel", "id": "bestaat-niet"}])})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "onbekend"
    # Ontbrekend uitvoeringsbeleid zonder lezingen: besluiten is vastleggen hoe het verder gaat.
    beleid = {"soort": "ontbrekend_uitvoeringsbeleid", "vraag": "Afronding van het termijnbedrag?", "hangt_aan": aan}
    p = (await client.post(_url(wg), json={"inhoud": beleid})).json()
    r = await client.post(_url(wg, p["id"], "besluit"), json={"verwachte_revisie": 1})
    assert r.status_code == 200 and r.json()["revisie"] == 1          # niets te heropenen: geen revisie
    r = await client.post(_url(wg, p["id"], "besluit"), json={"verwachte_revisie": 1, "gekozen": "A"})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "geen_lezingen"
    r = await client.post(_url(wg, p["id"], "besluit"),
                          json={"verwachte_revisie": 1, "motivering": "Signaleren aan de uitvoering (activiteit 5)."})
    assert r.status_code == 200 and r.json()["status"] == "gekozen"


async def test_een_keuze_vervalt_als_haar_lezing_verdwijnt(client):
    wg, ids = await _opzet(client)
    aan = [{"soort": "markering", "id": ids["ar"]}]
    p = (await client.post(_url(wg), json={"inhoud": _keuze(aan)})).json()
    p = (await client.post(_url(wg, p["id"], "besluit"), json={"verwachte_revisie": 1, "gekozen": "B"})).json()
    inhoud = {**_keuze(aan), "lezingen": [{"label": "A", "omschrijving": "Per termijn."},
                                          {"label": "C", "omschrijving": "Per aanslag."}]}
    p = (await client.patch(_url(wg, p["id"]), json={"verwachte_revisie": p["revisie"], "inhoud": inhoud})).json()
    assert p["status"] == "open" and p["keuze"] is None


async def test_lijst_filters_en_een_verdwenen_aanhaking(client):
    """Eén punt kan meer dingen raken; filteren op een regel vindt ook het punt op een geval van die regel."""
    wg, ids = await _opzet(client)
    wg = await _dv(client, wg, "Wanneer is een voorlopige aanslag invorderbaar?")
    dv_id = wg["deelvragen"][0]["id"]
    onderzoek = {"soort": "onderzoekspunt", "vraag": "Geldt lid 5 ook voor het winstaandeel?",
                 "hangt_aan": [{"soort": "deelvraag", "id": dv_id}, {"soort": "markering", "id": ids["var"]}]}
    a = (await client.post(_url(wg), json={"inhoud": onderzoek})).json()
    b = (await client.post(_url(wg), json={"inhoud": _keuze([{"soort": "markering", "id": ids["ar"]}])})).json()
    lijst = (await client.get(_url(wg), params={"aan": "deelvraag", "aan_id": dv_id})).json()["open_punten"]
    assert [p["id"] for p in lijst] == [a["id"]]
    lijst = (await client.get(_url(wg), params={"soort": "interpretatiekeuze"})).json()["open_punten"]
    assert [p["id"] for p in lijst] == [b["id"]]
    assert (await client.get(_url(wg), params={"aan": "regel"})).status_code == 422

    # Lex leest mee in het werkgebied: kort, de open eerst.
    w = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    assert w["open_punten"]["telling"] == {"open": 2, "gekozen": 0, "getoetst": 0}
    assert {p["soort"] for p in w["open_punten"]["punten"]} == {"onderzoekspunt", "interpretatiekeuze"}
    assert w["open_punten"]["punten"][0]["nog_te_toetsen"] in ([], ["wetsgeschiedenis"])

    # Een markering die verdwijnt, laat het punt staan met `bestaat: false`.
    async with db.get_engine().begin() as conn:
        await conn.execute(db.annotatie_v2_elementen.delete().where(db.annotatie_v2_elementen.c.id == ids["var"]))
    p = (await client.get(_url(wg, a["id"]))).json()
    assert [x["bestaat"] for x in p["inhoud"]["hangt_aan"]] == [True, False]


async def test_het_rapport_heeft_een_hoofdstuk_open_punten():
    from app.werkgebied_rapport import OpenPunt, OpenPuntLezing, OpenPuntToets, open_punten_regels
    regels = open_punten_regels([OpenPunt(
        soort_naam="interpretatiekeuze", status="gekozen", vraag="Saldering?",
        hangt_aan=["regel R1"], lezingen=[OpenPuntLezing(label="A", omschrijving="Per termijn."),
                                          OpenPuntLezing(label="B", omschrijving="Over het jaar.", grondslag=["art. 9 lid 5"])],
        gekozen="B", methode="wetshistorisch", door="jurist-a",
        te_toetsen=[OpenPuntToets(bronsoort="jurisprudentie")])])
    tekst = [t for _, t in regels]
    assert "7. Open punten" in tekst and "Saldering?" in tekst
    assert "Soort: interpretatiekeuze · stand: gekozen · hangt aan: regel R1" in tekst
    assert "Lezing B (gekozen): Over het jaar." in tekst and "Grondslag: art. 9 lid 5" in tekst
    assert "Keuze: lezing B, wetshistorisch uitgelegd, door jurist-a." in tekst
    assert "Nog niet getoetst aan de jurisprudentie." in tekst
    assert "Er zijn geen open punten vastgelegd." in [t for _, t in open_punten_regels([])]


async def test_een_werkgebied_wissen_wist_zijn_open_punten(client):
    wg, ids = await _opzet(client)
    p = (await client.post(_url(wg), json={"inhoud": _keuze([{"soort": "markering", "id": ids["ar"]}])})).json()
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    r = await client.delete(f"/v1/werkgebieden/{wg['id']}", params={"verwachte_revisie": wg["revisie"]})
    assert r.status_code == 200, r.text
    async with db.get_engine().connect() as conn:
        for t, k in ((db.open_punten, "id"), (db.open_punt_revisies, "open_punt_id")):
            assert (await conn.execute(select(func.count()).select_from(t).where(t.c[k] == p["id"]))).scalar() == 0
