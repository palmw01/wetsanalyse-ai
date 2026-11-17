"""Brondefinitie: "Onder X wordt verstaan", een term in een opsomming, en een verwijzing volgen (S4); en de keten
neemt een definitie uit de context over vóór het model eraan te pas komt (S2)."""
from __future__ import annotations

import json

from agent import begrip_kaart as bk
from agent import begrippen_verdieping as bv
from agent.begrippen_pipeline import definities
from agent.begrippen_pipeline.kaart import naam_en_letterlijk
from agent.begrippen_pipeline.model import Bron, Contextbron, Formulering, Manifest, Onderzoek, Taalanalyse
from fakes import FakeGraph

WET, ANDER = "urn:bwb:BWBR0000001", "urn:bwb:BWBR0000002"


def _tsv(kop, rijen):
    def cel(v):
        return f"<{v}>" if v.startswith("urn:") else json.dumps(v, ensure_ascii=False)
    return "\t".join(f"?{k}" for k in kop) + "\n" + "".join("\t".join(cel(v) for v in r) + "\n" for r in rijen)


def invoer(naam):
    return {"begrip": {"inhoud": {"naam": naam}}, "selecties": [{"bron_iri": f"{WET}:artikel:9"}]}


def graaf(*, begrip=(), onder=(), verwijzing=(), doel=()):
    def antwoord(q):
        if "bwb:definieertBegrip ?begrip" in q and "?begrip ?tekst" in q:
            return _tsv(["node", "begrip", "tekst", "aanhef"], begrip)
        if "SELECT DISTINCT ?node ?tekst" in q:
            return _tsv(["node", "tekst"], onder)
        if "?naar ?anker" in q:
            return _tsv(["naar", "anker"], verwijzing)
        if "VALUES ?node" in q:
            return _tsv(["node", "tekst", "aanhef"], doel)
        return ""
    return FakeGraph(results=antwoord)


def test_onder_x_wordt_verstaan_is_een_brondefinitie_zonder_graafbegrip():
    g = graaf(onder=[[f"{ANDER}:artikel:1%3A2:lid:1", "Onder belanghebbende wordt verstaan: degene wiens belang is betrokken."]])
    uit = bk.zoek_brondefinities(g, invoer("belanghebbende"))
    assert uit.voorstellen[0]["definitie"]["definitie"].startswith("degene wiens belang")


def test_mede_verstaan_blijft_geen_definitie():
    g = graaf(onder=[[f"{ANDER}:artikel:1:lid:1", "Onder aanslag wordt mede verstaan: de naheffing."]])
    assert bk.zoek_brondefinities(g, invoer("aanslag")).voorstellen == []


def test_een_term_in_een_opsomming_telt_een_langer_woord_niet():
    rij = [f"{WET}:artikel:2:o:i", "directeur, inspecteur of ontvanger", "directeur, inspecteur of ontvanger: de functionaris;",
           "Deze wet verstaat onder:"]
    lang = [f"{WET}:artikel:2:o:j", "rijksontvanger", "rijksontvanger: iemand anders;", "Deze wet verstaat onder:"]
    uit = bk.zoek_brondefinities(graaf(begrip=[rij, lang]), invoer("ontvanger"))
    assert [v["definitie"]["definitie"] for v in uit.voorstellen] == ["de functionaris"]


DOOR = [f"{WET}:artikel:2:o:n", "ontvanger", "ontvanger: de ontvanger, bedoeld in artikel 2, eerste lid, onderdeel i, van de Wet B;",
        "Deze wet verstaat onder:"]
DOEL = f"{ANDER}:artikel:2:lid:1:o:i"


def test_een_doorverwijzing_wordt_de_definitie_waarnaar_ze_wijst():
    g = graaf(begrip=[DOOR], verwijzing=[[f"{ANDER}:artikel:2", "artikel 2, eerste lid, onderdeel i, van de Wet B"]],
              doel=[[DOEL, "directeur, inspecteur of ontvanger: de functionaris;", "Deze wet verstaat onder:"]])
    v = bk.zoek_brondefinities(g, invoer("ontvanger")).voorstellen
    assert len(v) == 1 and v[0]["definitie"]["definitie"] == "de functionaris"
    assert v[0]["definitie"]["definitie_bron_iri"] == DOEL and v[0]["aandacht"] == "geel"
    assert "verwijst" in v[0]["motivatie"]


def test_een_doorverwijzing_die_niet_te_volgen_is_krijgt_nooit_groen():
    v = bk.zoek_brondefinities(graaf(begrip=[DOOR]), invoer("ontvanger")).voorstellen
    assert v[0]["aandacht"] == "geel" and v[0]["aandachtspunten"] == ["DEFINITIE_VERWIJST_DOOR"]


def test_doelen_lezen_lid_en_onderdeel_uit_de_ankertekst():
    assert bk.doelen("urn:x:artikel:2", "artikel 2, eerste lid, onderdeel i") == [
        "urn:x:artikel:2:lid:1:o:i", "urn:x:artikel:2:lid:1", "urn:x:artikel:2"]
    assert bk.doelen("urn:x:artikel:2:lid:3", "derde lid") == ["urn:x:artikel:2:lid:3"]


def test_verwijst_door_is_alleen_de_term_zelf():
    assert definities.verwijst_door("de ontvanger, bedoeld in artikel 2", ["ontvanger"])
    assert definities.verwijst_door("bank als bedoeld in artikel 1", ["bank"])
    assert not definities.verwijst_door("de ambtenaar, bedoeld in artikel 2", ["ontvanger"])
    assert not definities.verwijst_door("de functionaris die is aangewezen", ["ontvanger"])


# --- de keten: de definitie staat er al vóór het model --------------------------------------------

def _manifest(iri=f"{WET}:artikel:9"):
    tekst = "De ontvanger stelt vast."
    return Manifest(bronnen=[Bron(bron_iri=iri, tekst=tekst, bron_hash="h", label="Artikel 9")],
                    formuleringen=[Formulering(element_id="e1", bron_iri=iri, start=3, eind=12, tekst="ontvanger",
                                               jas_klasse="Rechtssubject")])


def _onderzoek(m, iri, tekst, aanhef="Deze wet verstaat onder:"):
    return Onderzoek(manifest_id=m.id, bronnen=[Contextbron(bron_iri=iri, tekst=tekst, bron_hash="h2", label="Artikel 2",
                                                            aanhef=aanhef, reden="definitie_in_regeling", rol="onderzoek")], begrippen=[], ontbrekend=[])


TAAL = {"e1": Taalanalyse(element_id="e1", term="ontvanger", kern="ontvanger")}


def test_een_definitie_in_de_context_wordt_letterlijk_overgenomen():
    m = _manifest()
    o = _onderzoek(m, f"{WET}:artikel:2:o:i", "ontvanger: de functionaris;")
    v = naam_en_letterlijk(m, TAAL, [], ("e1",), o)
    assert v["definitie"] == "de functionaris" and v["definitie_bron_iri"].endswith(":o:i")


def test_buiten_het_bereik_of_als_doorverwijzing_niet():
    m = _manifest()
    assert "definitie" not in naam_en_letterlijk(m, TAAL, [], ("e1",), _onderzoek(m, f"{ANDER}:artikel:2", "ontvanger: de functionaris;"))
    assert "definitie" not in naam_en_letterlijk(m, TAAL, [], ("e1",), _onderzoek(m, f"{WET}:artikel:2", "ontvanger: de ontvanger, bedoeld in artikel 3;"))


# --- de verdieping: eerst de brondefinitie ---------------------------------------------------------

class Opdracht:
    def __init__(self, naam):
        from agent.begrippen_pipeline.model import Kaart
        self.kaart = Kaart(groep_id=f"G{naam}", naam=naam)


def test_een_begrip_met_een_brondefinitie_gaat_niet_naar_het_model():
    g = graaf(begrip=[[f"{WET}:artikel:2:o:a", "aanslag", "aanslag: het besluit;", "Deze wet verstaat onder:"]])
    rest, gevonden = bv.brondefinitie_eerst(g, [{"bron_iri": f"{WET}:artikel:9"}], [Opdracht("aanslag"), Opdracht("kaas")])
    assert [o.kaart.naam for o in rest] == ["kaas"]
    assert "Zoek de brondefinitie" in gevonden["Gaanslag"].motivatie and gevonden["Gaanslag"].definitie == ""


def test_een_treffer_elders_is_geen_reden_om_het_model_over_te_slaan():
    g = graaf(begrip=[[f"{ANDER}:artikel:2:o:a", "aanslag", "aanslag: iets anders;", "Dit besluit verstaat onder:"]])
    rest, gevonden = bv.brondefinitie_eerst(g, [{"bron_iri": f"{WET}:artikel:9"}], [Opdracht("aanslag")])
    assert len(rest) == 1 and gevonden == {}


def test_een_haperende_graaf_laat_alles_naar_het_model_gaan():
    class Stuk:
        def sparql(self, q):
            raise RuntimeError("weg")
    rest, gevonden = bv.brondefinitie_eerst(Stuk(), [], [Opdracht("aanslag")])
    assert len(rest) == 1 and gevonden == {}


def test_het_voorstel_noemt_de_bandbreedte_uit_de_meting():
    tekst, _ = bv.voorstel_tekst("Proef", {"vragen": ["a"], "kaarten": [], "aantal": 1,
                                           "schatting": {"totaal": 1000, "hoog": 2500, "basis": 7}})
    assert "~1.000" in tekst and "~2.500" in tekst and "7 batches" in tekst
