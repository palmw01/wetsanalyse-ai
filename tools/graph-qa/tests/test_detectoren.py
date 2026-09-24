"""Deterministische detectoren (ADR-001 PR 6): elke regel met positief, negatief, rand en overlap."""
from __future__ import annotations

import pytest

from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles, kandidaten_van
from agent.jas_pipeline.detectoren.regels import RegelDetector, alle_regels, maskerregels, maskers
from agent.jas_pipeline.detectoren.structuur import DefinitieDetector
from agent.jas_pipeline.kandidaten import CandidateStatus
from agent.jas_pipeline.profielen import laad

REGELS = alle_regels()
CATEGORIEEN = ("positief", "negatief", "rand", "overlap")


def _grenzen(kandidaten) -> set[str]:
    """Alle tekstgrenzen die kandidaten aanreiken: de span zelf en elke spanoptie."""
    return {k.span.tekst for k in kandidaten} | {o.span.tekst for k in kandidaten for o in k.span_options}


def _van_regel(regel, tekst):
    bron = BronTekst.van_tekst("urn:test", tekst)
    return RegelDetector(regel.detector, (regel,)).detecteer(bron).kandidaten


@pytest.mark.parametrize("regel", REGELS, ids=lambda r: r.id)
def test_elke_regel_heeft_de_vier_testsoorten(regel):
    assert all(regel.tests.get(c) for c in CATEGORIEEN), f"{regel.id} mist {[c for c in CATEGORIEEN if not regel.tests.get(c)]}"


@pytest.mark.parametrize("regel,geval", [(r, g) for r in REGELS for c in ("positief", "rand") for g in r.tests.get(c, [])],
                         ids=lambda x: getattr(x, "id", None) or x.get("span", ""))
def test_positief_en_rand(regel, geval):
    assert geval["span"] in _grenzen(_van_regel(regel, geval["tekst"]))


@pytest.mark.parametrize("regel,geval", [(r, g) for r in REGELS for g in r.tests.get("negatief", [])],
                         ids=lambda x: getattr(x, "id", None) or x.get("tekst", ""))
def test_negatief_vuurt_niet(regel, geval):
    assert _van_regel(regel, geval["tekst"]) == ()


@pytest.mark.parametrize("regel,geval", [(r, g) for r in REGELS for g in r.tests.get("overlap", [])],
                         ids=lambda x: getattr(x, "id", None) or x.get("tekst", ""))
def test_overlap_laat_elke_kandidaat_bestaan(regel, geval):
    """Overlappende of geneste kandidaten verdringen elkaar niet – ook niet over detectoren heen."""
    alle = kandidaten_van(detecteer_alles(BronTekst.van_tekst("urn:test", geval["tekst"])))
    assert set(geval["spans"]) <= _grenzen(alle)


@pytest.mark.parametrize("masker", maskerregels(), ids=lambda m: m.id)
def test_maskers(masker):
    for geval in masker.tests["positief"]:
        bereiken = maskers(geval["tekst"])[masker.masker]
        assert geval["span"] in {geval["tekst"][s:e] for s, e in bereiken}


def test_masker_onderdrukt_een_nummer_in_een_verwijzing():
    """Geen kandidaat ligt binnen een verwijzing; een groter segment eromheen mag wel."""
    tekst = "bedoeld in artikel 10, tweede lid, bedraagt ten minste 5%."
    kandidaten = kandidaten_van(detecteer_alles(BronTekst.van_tekst("urn:test", tekst)))
    assert {"5%", "ten minste"} <= _grenzen(kandidaten)
    verwijzing = maskers(tekst)["verwijzing"]
    assert not any(ms <= k.span.start and k.span.eind <= me for k in kandidaten for ms, me in verwijzing)


# --- definities ---------------------------------------------------------------------------------

AWB = ("In deze wet wordt verstaan onder:\na. bestuurlijke sanctie: een door een bestuursorgaan "
       "opgelegde verplichting;\nb. herstelsanctie: een bestuurlijke sanctie.")


def test_definitie_onderdelen_onder_de_aanhef():
    ks = DefinitieDetector().detecteer(BronTekst.van_tekst("urn:test", AWB)).kandidaten
    assert [k.span.tekst for k in ks] == ["bestuurlijke sanctie: een door een bestuursorgaan opgelegde verplichting;",
                                          "herstelsanctie: een bestuurlijke sanctie."]
    assert ks[0].span_options[0].span.tekst.endswith("verplichting")      # zonder ';' als optie


def test_definitie_als_eigen_bronnode_via_de_aanhef_van_de_ouder():
    bron = BronTekst.van_tekst("urn:test:a", "bestuurlijke sanctie: een opgelegde verplichting;",
                               context="In deze wet wordt verstaan onder:")
    assert len(DefinitieDetector().detecteer(bron).kandidaten) == 1


def test_een_dubbele_punt_zonder_definitie_aanhef_is_geen_definitie():
    rvv = "Bij voetgangerslichten betekent:\na. groen licht: voetgangers mogen oversteken;"
    assert DefinitieDetector().detecteer(BronTekst.van_tekst("urn:test", rvv)).kandidaten == ()


def test_definitie_in_een_zin():
    ks = DefinitieDetector().detecteer(BronTekst.van_tekst(
        "urn:test", "Onder werkgever wordt verstaan: degene die loon verschuldigd is.")).kandidaten
    assert [k.span.tekst for k in ks] == ["Onder werkgever wordt verstaan: degene die loon verschuldigd is."]


# --- samenhang met de profielen en eigenschappen van de laag -----------------------------------

def test_elke_regel_staat_als_geimplementeerd_in_een_profiel_van_zijn_klassen():
    """Elke regel-id die een detector kan uitgeven staat als geïmplementeerd in een profiel, en omgekeerd."""
    from agent.jas_pipeline.detectoren import standaard_detectoren
    profielen = laad()
    in_profiel = {r["id"]: k for k, p in profielen.items() for r in p.candidate_rules if r["status"] == "geïmplementeerd"}
    uitgegeven = {rid for d in standaard_detectoren() for rid in d.REGELS}
    assert uitgegeven == set(in_profiel), (uitgegeven ^ set(in_profiel))
    for r in REGELS:                         # een YAML-regel hoort bij een profiel van een van zijn klassen
        assert in_profiel[r.id] in r.klassen, r.id


def test_elke_kandidaat_is_letterlijk_onbehandeld_en_draagt_zijn_regel():
    tekst = ("De dwangsom bedraagt de eerste veertien dagen € 23 per dag, vermeerderd met vijftig procent, "
             "binnen zes weken na de dagtekening in Nederland.")
    for k in kandidaten_van(detecteer_alles(BronTekst.van_tekst("urn:test", tekst))):
        assert tekst[k.span.start:k.span.eind] == k.span.tekst
        assert k.status is CandidateStatus.UNHANDLED
        assert all(e.regel.startswith("jas.") for e in k.evidence)


def test_detectie_is_deterministisch():
    tekst = "Indien de normpremie in het berekeningsjaar minder bedraagt dan € 1.000, binnen zes weken."
    a = detecteer_alles(BronTekst.van_tekst("urn:test", tekst))
    b = detecteer_alles(BronTekst.van_tekst("urn:test", tekst))
    assert a == b


def test_kandidaat_eval_meet_alleen_ontwikkelcasussen_en_noemt_het_geen_recall():
    from eval.kandidaat_eval import meet
    m = meet()
    assert m["referentie_status"] == "provisional"
    assert m["per_klasse"]["Tijdsaanduiding"]["candidate_recall"] == 1.0
    assert m["per_klasse"]["Brondefinitie"]["candidate_recall"] == 1.0
