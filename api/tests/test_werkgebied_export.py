"""Het werkgebied als één PDF: alles staat erin, met zijn status, en een citaat blijft letterlijk."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import subprocess
import threading
import types
from typing import Literal, Union, get_args, get_origin

import pytest

from app import annotatie_v2_store as store, bestandsnaam, markdown_opmaak, pdf_opmaak, werkgebied_export as export, werkgebieden
from app.werkgebied_rapport import (Begrippen, Rapport, Stand, Wettekst, deelvragen_regels, dossier_regels, niet_meegenomen_regels,
                                   rapport_regels)
from pydantic import BaseModel, ValidationError
from test_annotatie_v2 import ART, LAW, ONE, TWO, element, request, snapshot
from test_begrippen import _annoteer, _begrip, _beslis, _keur_alles_goed, _url, _werkgebied
from test_werkgebieden import ART2, LAW2, _bron, _nieuw, client, database, graaf, snapshot2  # noqa: F401

V = {"besluit": {"model": {"naam": "het model"}}}


async def _toestanden(wg: dict) -> dict:
    return {"peildatum": wg["peildatum"], "peildatum_standaard": wg["peildatum_standaard"], "volledig": True,
            "regelingen": [{"bwb_id": "BWBR0004770", "citeertitel": "Invorderingswet 1990", "geldig_vanaf": "2026-01-01",
                            "geldig_tot": None, "na_peildatum": False}]}


@pytest.fixture(autouse=True)
def toestanden(monkeypatch):
    monkeypatch.setattr(werkgebieden, "toestanden_van", _toestanden)


async def _gevuld(client) -> tuple[dict, dict]:
    ids = await _annoteer()
    wg = await _werkgebied(client)
    await _keur_alles_goed(ids)
    b = await _begrip(client, wg, [ids["lid1"]], naam="belastingschuldige")
    r = await client.patch(_url(wg, b), json={"verwachte_revisie": b["revisie"], "inhoud": {
        "naam": "belastingschuldige", "definitie": "Degene die schuldig is & blijft <altijd>.", "context": "Alleen hier."}})
    assert r.status_code == 200, r.text
    b = r.json()
    b = (await client.post(_url(wg, b, "koppelingen", "beoordelen"), json={
        "verwachte_revisie": b["revisie"], "koppeling_ids": [b["koppelingen"][0]["id"]], "beoordeling": "akkoord"})).json()
    r = await client.post(_url(wg, b, "accorderen"), json={"reden": "Getoetst aan de wet", "verwachte_revisie": b["revisie"]})
    assert r.status_code == 200, r.text
    await _begrip(client, wg, [ids["lid2"]], naam="aanslag")
    await _beslis(ids["lid2"], "heropen", snapshot())
    await _beslis(ids["lid2"], "reject", snapshot(), comment="Geen rechtssubject")
    return (await client.get(f"/v1/werkgebieden/{wg['id']}")).json(), ids


async def _data(wg: dict) -> dict:
    return await export.verzamel(wg["id"], "jurist-a", werkgebieden.resolve_bron, werkgebieden.toestanden_van)


def _teksten(data: dict) -> list[str]:
    return [t for _s, t in export.regels(data, V)]


def _tekst(pdf: bytes) -> str:
    return " ".join(subprocess.run(["pdftotext", "-", "-"], input=pdf, capture_output=True, check=True).stdout.decode().split())


async def test_de_delen_staan_op_volgorde_met_elke_bepaling_een_keer(client):
    wg, _ids = await _gevuld(client)
    regels = export.regels(await _data(wg), V)
    koppen = [t for s, t in regels if s == "Heading1"]
    assert koppen == ["1. Samenvatting", "2. Leeswijzer", "3. Werkgebied", "4. Deelvragen en bronnen", "5. Analyse per bepaling",
                      "6. Begrippen", "Bijlage A. Begripskaarten", "Bijlage B. Bronnenregister", "Bijlage C. Contextbepalingen",
                      "Bijlage D. Niet meegenomen", "Bijlage E. Verantwoording"]
    assert [i for i, (s, _t) in enumerate(regels) if s == pdf_opmaak.INHOUD]
    # Lid 1 heeft een emoji vooraan: de offsets tellen codepoints, en de tekst staat letterlijk en één keer.
    assert sum(s == "Citaat" and t == "😀 Alfa Alfa" for s, t in regels) == 1
    assert sum(s == "Citaat" and t == "Beta" for s, t in regels) == 1


async def test_elke_markering_staat_er_precies_een_keer_met_haar_status(client):
    wg, _ids = await _gevuld(client)
    data = await _data(wg)
    regels = export.regels(data, V)
    legenda = regels.index(("Heading1", "3. Werkgebied"))               # de legenda in de leeswijzer toont elke klasse
    koppen = [t for s, t in regels[legenda:] if s.startswith(pdf_opmaak.MARKERING)]
    assert len(koppen) == len(data["inventaris"]["elementen"]) + len(data["inventaris"]["afgewezen"]) == 3
    assert sum("beoordeeld: akkoord" in k for k in koppen) == 2 and sum(k.endswith("afgewezen") for k in koppen) == 1
    teksten = [t for _s, t in regels]
    afgewezen = teksten.index("Afgewezen markeringen")
    assert any("afgewezen" in t for t in teksten[afgewezen:])


async def test_een_voorstel_is_als_voorstel_te_herkennen(client):
    snap = snapshot()
    await store.batch(request(snap, [element(snap, ONE)]), snap, "lex")
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=ART))["werkgebied"]
    teksten = _teksten(await _data(wg))
    assert any(t.endswith("voorstel, nog niet beoordeeld") for t in teksten)


async def test_geen_modelvragen_hashes_of_beurtmeting(client):
    wg, ids = await _gevuld(client)
    data = await _data(wg)
    for e in data["inventaris"]["elementen"]:
        e["trace"] = {"vraag": "GEHEIME-MODELVRAAG", "beslissing": {"door": "model"}}
        e["geproduceerd_door"] = {"model": "model-x", "instellingen": {"meting": {"fasen": [{"fase": "BEURTMETING"}]}}}
    alles = "\n".join(_teksten(data))
    assert "GEHEIME-MODELVRAAG" not in alles and "BEURTMETING" not in alles and "model-x" not in alles
    assert not any(a["bron_hash"] in alles for e in data["inventaris"]["elementen"] for a in e["ankers"])
    assert "voorgesteld door Lex (het model)" in alles


async def test_citaat_draagt_vindplaats_en_jci_met_de_iri_als_terugval(client):
    wg, _ids = await _gevuld(client)
    data = await _data(wg)
    alles = "\n".join(_teksten(data))
    assert f"· {ONE}" in alles                                  # geen jci in de fixture: de bron-IRI
    data["bomen"]["BWBR0004770"] = copy.deepcopy(data["bomen"]["BWBR0004770"])
    for n in store.nodes_van(data["bomen"]["BWBR0004770"]).values():
        n["jci"] = f"jci1.3:c:BWBR0004770&artikel=9&{n['label']}"
        n["vindplaats"] = f"Artikel 9, {n['label']}"
    alles = "\n".join(_teksten(data))
    assert "jci1.3:c:BWBR0004770&artikel=9&Lid 1" in alles and "Artikel 9, Lid 1 · rol analyseren" in alles


async def test_een_gewijzigde_brontekst_staat_met_toen_en_nu_op_voorblad_en_plek(client, graaf):
    wg, _ids = await _gevuld(client)
    data = await _data(wg)
    for n in store.nodes_van(data["bomen"]["BWBR0004770"]).values():
        if n["bron_iri"] == ONE:
            n["tekst"] = "😀 Gamma Alfa"
    regels = export.regels(data, V)
    waarschuwingen = [t for s, t in regels if s == "Waarschuwing"]
    assert any("markering staat op tekst die veranderde" in w for w in waarschuwingen)
    assert any("Brontekst gewijzigd" in w and "Toen: “Alfa”" in w and "Nu: “Gamm”" in w for w in waarschuwingen)


async def test_een_veranderde_passage_bij_een_begrip_toont_toen_en_nu(client):
    wg, _ids = await _gevuld(client)
    data = await _data(wg)
    k = next(b for b in data["begrippen"] if b["inhoud"]["naam"] == "belastingschuldige")["koppelingen"][0]
    k["actualiteit"] = "gewijzigd"
    k["bewijs"] = {**k["bewijs"], "tekst": "Oude passage"}
    teksten = [t for s, t in export.regels(data, V) if s == "Waarschuwing"]
    assert any("Na bevestiging: de passage veranderde" in t and "Toen: “Oude passage”" in t and "Nu: “Alfa”" in t for t in teksten)
    assert any("toen en nu staan bij het begrip" in t for t in teksten)


async def test_een_onbereikbare_regeling_staat_op_voorblad_en_plek(client, graaf):
    wg, _ids = await _gevuld(client)
    graaf.weg = {LAW2}
    data = await _data(wg)
    assert data["inventaris"]["volledig"] is False
    regels = export.regels(data, V)
    waarschuwingen = [(i, t) for i, (s, t) in enumerate(regels) if s == "Waarschuwing"]
    eerste_deel = regels.index(("Heading1", "3. Werkgebied"))
    assert any(i < eerste_deel and t.startswith("Niet in dit dossier") for i, t in waarschuwingen)
    assert any(i > eerste_deel and t.startswith("De tekst ontbreekt") for i, t in waarschuwingen)


async def test_zonder_enige_regeling_geen_dossier(client, graaf, monkeypatch):
    wg, _ids = await _gevuld(client)

    async def weg(_doel):
        raise ConnectionError("graaf weg")

    monkeypatch.setattr(werkgebieden, "_resolve_bron", weg)
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/export")
    assert r.status_code == 503 and "brongraaf" in r.json()["detail"]


async def test_begrippen_op_status_met_herkomst_passages_en_accordering(client):
    wg, _ids = await _gevuld(client)
    regels = export.regels(await _data(wg), V)
    teksten = [t for _s, t in regels]
    assert teksten.index("Geaccordeerde begrippen (1)") < teksten.index("Conceptbegrippen (1)")
    assert "Degene die schuldig is & blijft <altijd>." in teksten
    assert "analysebegrip, geformuleerd, door de analist." in teksten
    assert any(t.startswith("Geaccordeerd door jurist-a") and "Reden: Getoetst aan de wet" in t for t in teksten)
    assert ("Meta", "Niet ingevuld.") in regels                  # het begrip zonder definitie


async def test_uitgesloten_bronnen_en_open_voorstellen_staan_apart(client):
    wg, _ids = await _gevuld(client)
    data = await _data(wg)
    vraag = data["overzicht"]["deelvragen"][0]
    basis = {"bron_iri": LAW + ":artikel:3", "bwb_id": "BWBR0004770", "rol": "kern", "bewijs_soorten": [], "zoekvragen": [],
             "overal": False, "elders_opgenomen": False, "reden": "", "besloten_door": None}
    vraag["kandidaten"] = [{**basis, "id": "k1", "label": "Artikel 3", "stand": "uitgesloten", "reden": "Te ruim", "besloten_door": "jurist-a"},
                           {**basis, "id": "k2", "label": "Artikel 4", "stand": "voorgesteld"},
                           {**basis, "id": "k3", "label": "Artikel 5", "stand": "niet_gekozen"}]
    vraag["telling"]["niet_gekozen"] = 1
    vraag["open_punten"] = [{"tekst": "De wet zwijgt hierover."}]
    data["overzicht"]["zonder_deelvraag"] = [{**basis, "id": "k4", "label": "Artikel 6", "stand": "voorgesteld"}]
    data["relaties"]["voorstellen"] = [{"van_naam": "a", "naar_naam": "b", "type": "inclusie"}]
    data["groepen"]["groepen"] = [{"besluit": "open", "voorstel": {"naam": "termijn"}, "kaart": None, "leden": [
        {"tekst": "zes weken", "vindplaats": "Artikel 9", "bron_iri": ONE}]}]
    regels = export.regels(data, V)
    voorstel = [t for s, t in regels if s == "Voorstel"]
    assert any("Artikel 3" in t and "door jurist-a" in t and "Reden: Te ruim" in t for _s, t in regels)
    assert "Voorstel voor een bron: Artikel 4 · kernbepaling · deelvraag 1" in voorstel
    assert "Voorstel voor een bron: Artikel 6 · kernbepaling · bij geen deelvraag" in voorstel
    assert "Voorstel voor een relatie: a omvat b" in voorstel and "Voorstel voor een begrip: termijn" in voorstel
    assert not any("Artikel 5" in t for _s, t in regels)
    assert ("Waarschuwing", "Open punt: De wet zwijgt hierover.") in regels
    assert any("1 voorstel van Lex is niet gekozen." in t for _s, t in regels)


async def test_een_regeling_zonder_einde_krijgt_geen_einddatum(client):
    wg, _ids = await _gevuld(client)
    data = await _data(wg)
    data["toestanden"]["regelingen"] = [
        {"bwb_id": "BWBR1", "citeertitel": "Open", "geldig_vanaf": "2026-01-01", "geldig_tot": "9999-12-31", "na_peildatum": False},
        {"bwb_id": "BWBR2", "citeertitel": "Dicht", "geldig_vanaf": "2026-01-01", "geldig_tot": "2026-12-31", "na_peildatum": False}]
    teksten = _teksten(data)
    assert "Open (BWBR1): geldt vanaf 1 januari 2026" in teksten
    assert "Dicht (BWBR2): geldt vanaf 1 januari 2026 tot 31 december 2026" in teksten


async def test_een_generiek_begrip_gaat_mee(client):
    wg, _ids = await _gevuld(client)
    data = await _data(wg)
    data["begrippen"][0]["kader"] = "generiek"
    assert any("generiek begrip" in t for t in _teksten(data))


async def test_verantwoording_telt_de_hele_audit_en_noemt_de_bronnen(client):
    wg, _ids = await _gevuld(client)
    data = await _data(wg)
    data["audit"] = data["audit"] * 40
    assert len(data["audit"]) > 100
    teksten = _teksten(data)
    assert any(t.endswith(f"{len(data['audit'])} handelingen in de audit, per soort:") for t in teksten)
    assert "Artikel 9" in "\n".join(teksten) and f"Rol analyseren · {ART}" in teksten


async def test_de_route_geeft_een_pdf_met_een_veilige_bestandsnaam(client):
    wg = await _nieuw(client, naam='Rekeningafspraken "één" / 2026')
    wg = (await _bron(client, wg, bron_iri=ART))["werkgebied"]
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/export")
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and r.headers["content-type"] == "application/pdf"
    assert re.fullmatch(r'attachment; filename="werkgebied-rekeningafspraken-een-2026-\d{8}-\d{6}\.pdf"', r.headers["content-disposition"])


async def test_de_route_kent_alleen_pdf_en_markdown_en_bestaande_werkgebieden(client):
    wg = await _nieuw(client)
    assert (await client.get(f"/v1/werkgebieden/{wg['id']}/export?formaat=docx")).status_code == 422
    assert (await client.get("/v1/werkgebieden/bestaat-niet/export")).status_code == 404


async def test_een_werkgebied_zonder_bronnen_geeft_toch_een_dossier(client):
    wg = await _nieuw(client)
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/export")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


async def test_het_zetten_gebeurt_niet_op_de_event_loop(client, monkeypatch):
    """Reportlab is puur Python: op de event loop houdt een groot dossier elk verzoek van de api vast."""
    wg, _ids = await _gevuld(client)
    lus, gezien = threading.get_ident(), []
    echt = export.pdf_export

    def spion(*a):
        gezien.append(threading.get_ident())
        return echt(*a)

    monkeypatch.setattr(export, "pdf_export", spion)
    assert (await client.get(f"/v1/werkgebieden/{wg['id']}/export")).status_code == 200
    assert gezien and lus not in gezien


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext ontbreekt voor onafhankelijke tekstextractie")
async def test_de_echte_pdf_is_letterlijk_met_inhoud_en_bladwijzers(client, graaf, monkeypatch):
    """De standaardletters van een PDF maakten van deze tekens stil een ■; `≥` verloor zijn spaties."""
    bijzonder = "Een bedrag ≥ € 10 – na 1‑1‑2026 → Māori § 3   “citaat” & <tag>"

    def boom(iri=ART, second="Beta"):
        snap = snapshot(iri, second=second)
        for n in snap["nodes"]:
            if n["bron_iri"] == TWO:
                n.update(tekst=bijzonder, bron_hash=hashlib.sha256(bijzonder.encode()).hexdigest())
        snap["snapshot_id"] = store.digest(snap["nodes"])
        return snap

    async def resolve(doel):
        return boom(doel["bron_iri"])

    monkeypatch.setattr(werkgebieden, "_resolve_bron", resolve)
    snap = boom()
    fragment = element(snap, TWO, 4, 22, toelichting="Tekens: ≥ en ā.")
    await store.batch(request(snap, [fragment]), snap, "lex")
    wg = await _nieuw(client, naam="Tekens")
    wg = (await _bron(client, wg, bron_iri=ART))["werkgebied"]

    r = await client.get(f"/v1/werkgebieden/{wg['id']}/export")
    tekst = _tekst(r.content)
    assert "■" not in tekst
    assert "Een bedrag ≥ € 10 – na 1‑1‑2026 → Māori § 3" in tekst and "“citaat” & <tag>" in tekst
    assert fragment["tekst"] in tekst and "Tekens: ≥ en ā." in tekst
    assert tekst.index("3. Werkgebied") < tekst.index("Aanleiding")             # eerst in de inhoudsopgave
    assert b"/Outlines" in r.content and b"/FontFile2" in r.content
    assert pdf_opmaak.aantal_paginas(r.content) >= 7                         # voorblad, inhoud en vijf delen


async def _spoor(data: dict) -> list[dict]:
    spoor: list[dict] = []
    pdf_opmaak.render(export.regels(data, V), spoor=spoor)
    return spoor


async def _met_begrippen(client, *namen: str) -> dict:
    """Een rapport met meer begrippen dan de fixture, in elke status een of meer."""
    wg, _ids = await _gevuld(client)
    data = await _data(wg)
    basis = next(b for b in data["begrippen"] if b["status"] == "concept")
    data["begrippen"] += [{**basis, "id": f"extra-{n}", "inhoud": {**basis["inhoud"], "naam": naam}} for n, naam in enumerate(namen)]
    data["begrippen"].append({**basis, "id": "weg", "status": "vervangen", "vervangen_door": "extra-0",
                              "inhoud": {**basis["inhoud"], "naam": "oud begrip"}})
    return data


async def test_elk_begrip_begint_op_een_eigen_pagina(client):
    data = await _met_begrippen(client, "termijn", "uitstel", "zekerheid")
    spoor = await _spoor(data)
    begrippen = [r for r in spoor if r["stijl"] == pdf_opmaak.BEGRIP]
    assert {r["tekst"] for r in begrippen} == {b["inhoud"]["naam"] for b in data["begrippen"]}
    assert len({r["pagina"] for r in begrippen}) == len(begrippen)
    for r in begrippen:
        # Bovenaan, of direct onder de kop van zijn groep: het eerste begrip van een groep deelt daarmee de pagina.
        ervoor = [x for x in spoor if x["pagina"] == r["pagina"] and spoor.index(x) < spoor.index(r)]
        assert r["bovenaan"] or all(x["stijl"] in ("Heading1", "Heading2", "Meta") for x in ervoor)


async def test_een_lang_begrip_loopt_door_en_het_volgende_begint_vers(client):
    data = await _met_begrippen(client, "termijn")
    lang = next(b for b in data["begrippen"] if b["inhoud"]["naam"] == "aanslag")
    lang["inhoud"] = {**lang["inhoud"], "uitleg": "\n\n".join(f"Alinea {n} van een lange uitleg." for n in range(120))}
    begrippen = [r for r in await _spoor(data) if r["stijl"] == pdf_opmaak.BEGRIP]
    op = {r["tekst"]: r for r in begrippen}
    assert op["termijn"]["pagina"] - op["aanslag"]["pagina"] >= 2 and op["termijn"]["bovenaan"]


async def test_een_groepskop_staat_nooit_alleen_en_er_is_geen_blanke_pagina(client):
    spoor = await _spoor(await _met_begrippen(client, "termijn", "uitstel"))
    laatste = max(r["pagina"] for r in spoor)
    # Pagina 1 is het getekende titelblad; een inhoudsopgave die doorloopt, heeft geen alinea's in het spoor.
    eerste = next(r["pagina"] for r in spoor if r["stijl"] == "Heading1")
    assert set(range(2, laatste + 1)) - {r["pagina"] for r in spoor} <= set(range(4, eerste))     # na colofon en begin inhoud
    for r in spoor:
        if r["stijl"] == "Heading2" and "begrippen (" in r["tekst"].lower():
            assert any(x["stijl"] == pdf_opmaak.BEGRIP and x["pagina"] == r["pagina"] for x in spoor)


async def test_voorstellen_en_afgewezen_hangen_niet_aan_het_vorige_stuk(client):
    spoor = await _spoor(await _met_begrippen(client, "termijn"))
    for kop in ("Afgewezen markeringen", "Open voorstellen van Lex voor begrippen"):
        assert any(r["tekst"] == kop and r["bovenaan"] for r in spoor), kop


async def test_elke_regeling_begint_op_een_nieuwe_pagina(client):
    wg, _ids = await _gevuld(client)
    data = await _data(wg)
    titels = [export._regeling_titel(b, data) for b in data["bomen"]]
    spoor = await _spoor(data)
    assert titels and all(any(r["tekst"] == t and r["bovenaan"] for r in spoor) for t in titels)


async def test_begrippen_staan_in_de_inhoudsopgave_artikelen_niet(client):
    spoor = await _spoor(await _met_begrippen(client, "termijn"))
    assert all(r["inhoud"] for r in spoor if r["stijl"] == pdf_opmaak.BEGRIP)
    assert not any(r["inhoud"] for r in spoor if r["stijl"] == "Heading3")
    assert any(r["inhoud"] for r in spoor if r["stijl"] == "Heading1")


async def test_de_begrippagina_heeft_altijd_dezelfde_kopjes(client):
    wg, _ids = await _gevuld(client)
    regels = export.regels(await _data(wg), V)
    begin = [i for i, (s, _t) in enumerate(regels) if s == pdf_opmaak.BEGRIP]
    einde = regels.index(("Heading1", "Bijlage B. Bronnenregister"))
    kopjes = ["Definitie", "Uitleg", "Toelichting", "Voorbeelden", "Waarop de definitie rust", "Passages", "Relaties", "Nog open", "Beoordeling"]
    assert len(begin) == 2
    for van, tot in zip(begin, [*begin[1:], einde]):
        assert [t for s, t in regels[van:tot] if s == "Heading4"] == kopjes


async def test_een_deelvraag_en_een_markering_blijven_bij_elkaar(client):
    wg, _ids = await _gevuld(client)
    regels = export.regels(await _data(wg), V)
    stijlen = [s for s, _t in regels]
    assert stijlen.count(pdf_opmaak.BLOK_BEGIN) == stijlen.count(pdf_opmaak.BLOK_EIND) >= 4
    open_ = 0
    for s in stijlen:                                             # nooit genest, en altijd weer dicht
        open_ += (s == pdf_opmaak.BLOK_BEGIN) - (s == pdf_opmaak.BLOK_EIND)
        assert open_ in (0, 1)
    assert open_ == 0
    assert pdf_opmaak.render(regels).startswith(b"%PDF")


def test_een_blok_dat_niet_op_een_pagina_past_loopt_door():
    regels = [(pdf_opmaak.BLOK_BEGIN, ""), ("Heading2", "Lang"), *[("BodyText", f"regel {n}") for n in range(200)], (pdf_opmaak.BLOK_EIND, "")]
    spoor: list[dict] = []
    pdf_opmaak.render(regels, spoor=spoor)
    assert len(spoor) == 201 and max(r["pagina"] for r in spoor) > 1


def test_een_breuk_op_een_lege_pagina_geeft_geen_blanke_pagina():
    regels = [(pdf_opmaak.PAGINA, ""), ("Heading1", "Een"), (pdf_opmaak.PAGINA, ""), (pdf_opmaak.PAGINA, ""), ("Heading1", "Twee")]
    spoor: list[dict] = []
    pdf_opmaak.render(regels, spoor=spoor)
    assert [(r["pagina"], r["bovenaan"]) for r in spoor] == [(1, True), (2, True)]


def test_het_spoor_is_van_de_laatste_ronde_van_de_inhoudsopgave():
    regels = [(pdf_opmaak.INHOUD, ""), (pdf_opmaak.PAGINA, ""), ("Heading1", "Een")]
    spoor: list[dict] = []
    pdf_opmaak.render(regels, spoor=spoor)
    assert len([r for r in spoor if r["tekst"] == "Een"]) == 1


def test_dossier_en_deelvragen_staan_in_het_rapport_met_hun_codes_en_komen_er_letterlijk_uit():
    wg = {"aanleiding": "Eerste alinea.\n\nTweede alinea.", "regelingen": [{"bwb_id": "BWBR1", "label": ""}], "bronnen": [
        {"id": "s1", "reden": "Kern"}], "deelvragen": [{"vraag": "Nog een vraag?", "status": "voorgesteld"}]}
    kandidaat = {"id": "k", "bron_iri": "urn:drie", "label": "Artikel 3", "rol": "kern", "overal": False, "besloten_door": None, "reden": ""}
    overzicht = {"modus": "deelvragen", "zonder_deelvraag": [], "zoekdekking": {"gezocht": True, "verouderd": True, "onvolledig": ["tekst"]},
                 "deelvragen": [{"nr": 1, "vraag": "Wie?", "status": "in_behandeling", "opnieuw_bekijken": False, "open_punten": [],
                                 "telling": {}, "bronnen": [{"bron_iri": "urn:negen", "label": "Artikel 9", "rol": "context", "selectie_id": "s1"}],
                                 "kandidaten": [{**kandidaat, "stand": "uitgesloten"}]}]}
    data = {"werkgebied": wg, "overzicht": overzicht}
    nodes = {"urn:negen": {"jci": "jci1.3:c:negen"}}
    dossier, deelvragen = export._dossier(data), export._deelvragen(data, nodes)

    assert deelvragen.deelvragen[0].status == "in_behandeling"           # de code; het label maakt de tekstlaag
    assert dossier_regels(dossier)[:5] == [
        ("Pagina", ""), ("Heading1", "3. Werkgebied"), ("Heading4", "Aanleiding"), ("BodyText", "Eerste alinea."), ("BodyText", "Tweede alinea.")]
    assert dossier_regels(dossier)[-1] == ("BodyText", "BWBR1 (BWBR1)")
    assert deelvragen_regels(deelvragen)[2:] == [
        ("BlokBegin", ""), ("Heading2", "Deelvraag 1"), ("BodyText", "Wie?"), ("Meta", "Stand: In behandeling · 1 bron"),
        ("BodyText", "Artikel 9 · context: Kern"), ("Meta", "jci1.3:c:negen"), ("BlokEind", "")]
    # Wat niet meedoet, staat in de bijlage.
    assert niet_meegenomen_regels(deelvragen, Wettekst(markeringen=0, beoordeeld=0), Begrippen())[:9] == [
        ("Heading2", "Uitgesloten bronnen"), ("BodyText", "Artikel 3 · uitgesloten voor deelvraag 1. Reden: niet vastgelegd"),
        ("Meta", "urn:drie"),
        ("Heading2", "Open voorstellen van Lex voor deelvragen en bronnen"),
        ("Meta", "Hierover is nog geen besluit genomen; ze horen niet tot de analyse."),
        ("Voorstel", "Voorstel voor een deelvraag: Nog een vraag?"),
        ("Heading2", "Zoekdekking"), ("BodyText", "Lex heeft gezocht, maar niet alles kon worden doorzocht: tekst."),
        ("Waarschuwing", "Het werkgebied veranderde na het zoeken.")]


async def test_het_rapport_overleeft_json_heen_en_terug(client):
    wg, _ids = await _gevuld(client)
    rapport = export.bouw_rapport(await _data(wg), V)
    terug = Rapport.model_validate_json(rapport.model_dump_json())
    assert terug == rapport and rapport_regels(terug) == rapport_regels(rapport)
    assert rapport.model_dump(mode="json")["schema_naam"] == "werkgebied-rapport-v2"


async def test_ook_de_json_draagt_geen_modelvragen_hashes_of_beurtmeting(client):
    wg, _ids = await _gevuld(client)
    data = await _data(wg)
    for e in data["inventaris"]["elementen"]:
        e["trace"] = {"vraag": "GEHEIME-MODELVRAAG", "beslissing": {"door": "model"}}
        e["geproduceerd_door"] = {"model": "model-x", "instellingen": {"meting": {"fasen": [{"fase": "BEURTMETING"}]}}}
    alles = export.bouw_rapport(data, V).model_dump_json()
    assert "GEHEIME-MODELVRAAG" not in alles and "BEURTMETING" not in alles and "model-x" not in alles
    assert not any(a["bron_hash"] in alles for e in data["inventaris"]["elementen"] for a in e["ankers"])


# Velden die de tekst bewust niet toont: sleutels, of een keuze tussen twee velden die de andere kant van de test laat zien.
_NIET_GETOOND = {"id", "iri", "regeling", "herkomst", "code", "definitie_herkomst", "definitie_door", "oordeel", "modus", "geldig_tot",
                 "alternatieven", "r.wettekst.regelingen.0.bwb_id"}


def _vul(soort, pad: str, ja: bool, spoor: list[str]):
    """Een waarde voor elk veld: elke tekst is zijn eigen pad, elke keuze wordt doorlopen."""
    if get_origin(soort) in (Union, types.UnionType):
        return _vul(next(a for a in get_args(soort) if a is not type(None)), pad, ja, spoor)
    if get_origin(soort) is list:
        element = get_args(soort)[0]
        return _varianten(element, pad, ja, spoor)
    if get_origin(soort) is Literal:
        return get_args(soort)[0]
    if soort is bool:
        return ja
    if soort is int:
        return 3
    if soort is str:
        if pad not in _NIET_GETOOND and not _NIET_GETOOND & set(pad.split(".")):
            spoor.append(pad)
        return pad
    return soort(**{naam: _vul(veld.annotation, f"{pad}.{naam}", ja, spoor) for naam, veld in soort.model_fields.items()
                    if veld.is_required() or naam not in ("door", "schema_naam", "versie")})


def _varianten(soort, pad: str, ja: bool, spoor: list[str]) -> list:
    """Een lijst krijgt een item per keuze in haar model: elke status, elke soort signaal."""
    if not (isinstance(soort, type) and issubclass(soort, BaseModel)):
        return [_vul(soort, f"{pad}.0", ja, spoor)]
    keuzes = [(n, get_args(v.annotation)) for n, v in soort.model_fields.items() if get_origin(v.annotation) is Literal and n != "door"]
    if not keuzes:
        return [_vul(soort, f"{pad}.0", ja, spoor)]
    naam, waarden = keuzes[0]
    return [_vul(soort, pad, ja, spoor).model_copy(update={naam: w}) for w in waarden]


async def test_de_reden_van_een_afwijzing_staat_bij_de_markering(client):
    wg, _ids = await _gevuld(client)
    regels = export.regels(await _data(wg), V)
    assert ("Meta", "Reden van afwijzing: Geen rechtssubject") in regels


async def test_een_heropende_markering_noemt_de_oude_afwijzing_niet(client):
    wg, _ids = await _gevuld(client)
    data = await _data(wg)
    e = data["inventaris"]["afgewezen"][0]
    assert export._reden_afwijzing({**e, "lifecycle": "human_approved"}) == ""


async def test_een_passage_noemt_wie_haar_beoordeelde(client):
    wg, _ids = await _gevuld(client)
    regels = export.regels(await _data(wg), V)
    assert any(s == "Meta" and t.startswith("Beoordeeld door ") for s, t in regels)


async def test_een_brondefinitie_draagt_haar_vindplaats_ook_zonder_fragmenten(client):
    wg, _ids = await _gevuld(client)
    data = await _data(wg)
    b = next(b for b in data["begrippen"] if b["inhoud"]["naam"] == "belastingschuldige")
    b["inhoud"] = {**b["inhoud"], "definitie_herkomst": "letterlijk"}
    b["definitie_onderbouwing"] = {"definitie_bron_iri": ONE, "definitie_vindplaats": "Artikel 9, eerste lid", "fragmenten": []}
    assert ("Meta", f"Vindplaats: Artikel 9, eerste lid · {ONE}") in export.regels(data, V)


async def test_elke_bron_in_deel_2_draagt_haar_bronreferentie_en_wie_haar_opnam(client):
    wg, _ids = await _gevuld(client)
    data = await _data(wg)
    regels = export.regels(data, V)
    begin = next(i for i, (_s, t) in enumerate(regels) if t == "4. Deelvragen en bronnen")
    eind = next(i for i, (_s, t) in enumerate(regels) if t == "5. Analyse per bepaling")
    bron = data["overzicht"]["deelvragen"][0]["bronnen"][0]
    assert ("Meta", bron["bron_iri"]) in regels[begin:eind]
    s = data["werkgebied"]["bronnen"][0]
    assert ("Meta", f"Opgenomen door {s['toegevoegd_door']} op {export.datum(s['toegevoegd'])}.") in regels


def test_elke_tekst_in_het_rapport_komt_in_de_uitvoer():
    """Een nieuw veld in het contract dat niemand toont, valt hier op: niets verdwijnt stil. Twee rondes, want een keuze
    laat soms het ene of het andere veld zien."""
    gevraagd: list[str] = []
    alles = ""
    for ja in (True, False):
        alles += "\n".join(t for _s, t in rapport_regels(_vul(Rapport, "r", ja, gevraagd)))
    assert sorted({m for m in gevraagd if m not in alles}) == []


def test_het_contract_kent_geen_onbekende_velden():
    with pytest.raises(ValidationError):
        Stand(op="2026-11-07", door="a", extra="b")


def _zonder_escape(tekst: str) -> str:
    return re.sub(r"\\(.)", r"\1", tekst)


async def test_markdown_en_pdf_hebben_dezelfde_inhoud(client):
    wg, _ids = await _gevuld(client)
    data = await _data(wg)
    tekst = _zonder_escape(export.markdown_export(data, V).decode())
    for stijl, regel in export.regels(data, V):
        if stijl == pdf_opmaak.TITELBLAD + "rij":                      # een rij wordt "- **Label:** waarde"
            label, _, waarde = regel.partition(": ")
            assert f"- **{label}:** {waarde}" in tekst, regel
        elif regel and stijl != "Waarschuwing":
            assert regel in tekst, regel


async def test_de_route_geeft_markdown_met_een_eigen_naam(client):
    wg, _ids = await _gevuld(client)
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/export?formaat=md")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/markdown") and r.text.startswith("# ")
    assert re.search(r'filename="werkgebied-.*-\d{8}-\d{6}\.md"', r.headers["content-disposition"])
    assert "## 6. Begrippen" in r.text and "## Bijlage A. Begripskaarten" in r.text and "|---" not in r.text


@pytest.mark.parametrize("wettekst", ["*vet* en _schuin_ en `code`", "# geen kop", "1. geen lijst", "- geen lijst", "> geen citaat",
                                      "a <b> [c](d) \\ e", "regel een\nregel twee"])
def test_wettekst_blijft_in_markdown_letterlijk_en_wordt_geen_opmaak(wettekst):
    uit = markdown_opmaak.markdown([("Citaat", wettekst)])
    assert all(r == ">" or r.startswith("> ") for r in uit.strip().split("\n"))
    regels = [r[2:] for r in uit.strip().split("\n") if r != ">"]
    assert _zonder_escape("\n".join(regels)) == wettekst
    los = markdown_opmaak.markdown([("BodyText", wettekst)]).strip()
    assert _zonder_escape(los) == wettekst and not re.match(r"(#|-|>|\d+\.)", los)


def test_markdown_zet_koppen_en_stijlen_om_zonder_tabellen():
    uit = markdown_opmaak.markdown([
        ("Title", "Titel"), (pdf_opmaak.PAGINA, ""), (pdf_opmaak.PAGINA, ""), (pdf_opmaak.INHOUD, ""), ("Heading1", "1. Dossier"), (pdf_opmaak.BLOK_BEGIN, ""),
        ("Heading4", "Kopje"), (pdf_opmaak.MARKERING + "Rechtssubject", "Rechtssubject"), ("Waarschuwing", "Pas op"), ("Voorstel", "Een voorstel"),
        (pdf_opmaak.BEGRIP, "termijn"), (pdf_opmaak.BLOK_EIND, "")])
    assert uit == ("# Titel\n\n---\n\n- 1\\. Dossier\n\n## 1. Dossier\n\n**Kopje**\n\n**Rechtssubject**\n\n**Let op:** Pas op\n\n"
                   "*Een voorstel*\n\n#### termijn\n")


def test_de_bestandsnaam_draagt_de_nederlandse_tijd_op_de_seconde():
    assert bestandsnaam.met_tijd("x", "pdf", "2026-11-07T13:32:05+00:00") == "x-20261107-143205.pdf"
    assert bestandsnaam.met_tijd("x", "pdf", "2026-07-07T13:32:05+00:00") == "x-20260707-153205.pdf"    # zomertijd
    assert bestandsnaam.met_tijd("x", "pdf", "2026-11-07T13:32:05+00:00") != bestandsnaam.met_tijd("x", "pdf", "2026-11-07T13:32:06+00:00")


def test_een_teken_buiten_fira_valt_per_teken_terug():
    assert pdf_opmaak.opgemaakt("a b") == 'a<font name="DejaVu"> </font>b'
    assert pdf_opmaak.opgemaakt("a & <b>") == "a &amp; &lt;b&gt;"


def test_ook_een_lange_onafgebroken_iri_past():
    regels = [("Heading3", "Kop"), ("Meta", "urn:bwb:" + "x" * 900), ("Markering:Onbekend", "Klasse")]
    assert pdf_opmaak.render(regels).startswith(b"%PDF")


def test_het_schemabestand_hoort_bij_het_contract():
    """Wie het contract wijzigt, maakt het bestand opnieuw: `werkgebied_rapport.schrijf_schema()`."""
    from app import werkgebied_rapport
    assert json.loads(werkgebied_rapport.SCHEMA_PAD.read_text()) == werkgebied_rapport.json_schema()


async def test_colofon_noemt_kenmerk_status_en_wie_het_opstelde(client):
    wg, _ids = await _gevuld(client)
    rapport = export.bouw_rapport(await _data(wg), V)
    assert rapport.document.kenmerk == f"WG-{wg['id'][:8]}-r{wg['revisie']}" and rapport.document.concept
    regels = rapport_regels(rapport)
    begin = regels.index(("Heading4", "Colofon"))
    assert regels[begin - 1] == ("Pagina", "")                        # het colofon heeft een eigen pagina
    colofon = [t for _s, t in regels[begin:begin + 14]]
    assert "Kenmerk: " + rapport.document.kenmerk in colofon
    assert any(t.startswith("Status: ") and "concept" in t for t in colofon)
    assert "Begrippen geaccordeerd door: " + ", ".join(rapport.verantwoording.accordeurs) in colofon


async def test_samenvatting_telt_in_een_vaste_volgorde(client):
    wg, _ids = await _gevuld(client)
    rapport = export.bouw_rapport(await _data(wg), V)
    k = rapport.samenvatting
    assert [(t.code, t.aantal) for t in k.begrippen] == [("geaccordeerd", 1), ("concept", 1)]
    assert [t.code for t in k.markeringen][0] == "beoordeeld" and k.markeringen[-1].code == "afgewezen"
    regels = rapport_regels(rapport)
    assert ("Heading1", "1. Samenvatting") in regels
    assert ("BodyText", "Begrippen – geaccordeerd: 1, concept: 1") in regels


async def test_het_besluitenlog_noemt_wie_wat_besloot_met_onderwerp_en_reden(client):
    wg, _ids = await _gevuld(client)
    rapport = export.bouw_rapport(await _data(wg), V)
    akkoord = [b for b in rapport.verantwoording.besluiten if b.actie == "begrip-geaccordeerd"]
    assert len(akkoord) == 1 and akkoord[0].onderwerp == "belastingschuldige" and akkoord[0].reden == "Getoetst aan de wet"
    assert [b.op for b in rapport.verantwoording.besluiten] == sorted(b.op for b in rapport.verantwoording.besluiten)
    regels = rapport_regels(rapport)
    assert any(s == "BodyText" and "begrip geaccordeerd: belastingschuldige" in t for s, t in regels)
    assert ("Meta", "Reden: Getoetst aan de wet") in regels
    # Werk van Lex is geen besluit: alleen geteld.
    assert not any(b.actie.endswith("-gestart") for b in rapport.verantwoording.besluiten)


async def test_het_rapport_begint_met_een_titelblad_en_dan_het_colofon(client):
    wg, _ids = await _gevuld(client)
    rapport = export.bouw_rapport(await _data(wg), V)
    regels = rapport_regels(rapport)
    blad = [(s.removeprefix(pdf_opmaak.TITELBLAD), t) for s, t in regels if s.startswith(pdf_opmaak.TITELBLAD)]
    assert regels[:len(blad)] == [(pdf_opmaak.TITELBLAD + v, t) for v, t in blad]       # alleen vooraan
    assert {v for v, _t in blad} <= set(pdf_opmaak.TITELBLAD_VELDEN)
    assert ("titel", wg["naam"]) in blad and ("rij", "Kenmerk: " + rapport.document.kenmerk) in blad
    assert any(v == "rij" and t.startswith("Status: ") for v, t in blad)
    assert regels[len(blad):len(blad) + 2] == [("Pagina", ""), ("Heading4", "Colofon")]
    md = markdown_opmaak.markdown(regels)
    assert md.startswith(f"# {wg['naam']}\n") and f"- **Kenmerk:** {rapport.document.kenmerk}" in md


def test_een_contextbepaling_zonder_markering_staat_in_de_bijlage_en_niet_in_de_analyse():
    from bronmodel.antwoord import Vindplaats
    from app.werkgebied_rapport import Artikel, Bepaling, Regeling, context_regels, wettekst_regels
    ctx = Bepaling(vindplaats=Vindplaats(iri="urn:c", label="Artikel 2, lid 1"), rol="context", tekst="Contexttekst.")
    hoofd = Bepaling(vindplaats=Vindplaats(iri="urn:h", label="Artikel 3"), rol="analyseren", tekst="Analysetekst.")
    w = Wettekst(markeringen=0, beoordeeld=0, regelingen=[Regeling(bwb_id="BWBR1", titel="Wet", artikelen=[Artikel(kop="Artikel 3", bepalingen=[hoofd])],
                                                                    context=[Artikel(kop="Artikel 2", bepalingen=[ctx])])])
    analyse, bijlage = wettekst_regels(w), context_regels(w)
    assert ("Citaat", "Analysetekst.") in analyse and ("Citaat", "Contexttekst.") not in analyse
    assert ("Citaat", "Contexttekst.") in bijlage and ("Heading3", "Artikel 2") in bijlage
    assert ("Meta", "De contextbepalingen zonder markering staan in de bijlage Contextbepalingen.") in analyse


async def test_de_leeswijzer_toont_elke_klasse_met_naam_en_de_bijlagen_hebben_letters(client):
    from app.jas_klassen import JAS_KLASSEN_VOLGORDE
    from app.werkgebied_rapport import BIJLAGEN
    wg, _ids = await _gevuld(client)
    regels = export.regels(await _data(wg), V)
    begin, eind = regels.index(("Heading1", "2. Leeswijzer")), regels.index(("Heading1", "3. Werkgebied"))
    assert [t for s, t in regels[begin:eind] if s.startswith(pdf_opmaak.MARKERING)] == list(JAS_KLASSEN_VOLGORDE)
    bijlagen = [t for s, t in regels if s == "Heading1" and t.startswith("Bijlage")]
    assert bijlagen == [f"Bijlage {letter}. {naam}" for letter, naam in zip("ABCDE", BIJLAGEN)]
    assert regels.index(("Heading1", "6. Begrippen")) < regels.index(("Heading1", bijlagen[0]))
