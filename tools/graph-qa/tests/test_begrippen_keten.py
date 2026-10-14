"""Beslistabel, groeperen en de keten zelf (ADR-004)."""
from __future__ import annotations

import json

import pytest

from agent.begrippen_pipeline import besluit, groeperen, keten
from agent.begrippen_pipeline.model import (
    Aandacht, Besluit, Bewijs, Hypothese, Kandidaat, Polariteit, Sterkte,
)
from agent.jas_pipeline.taal.provider import NullProvider
from eval import begrippen_eval as be


def _bw(code="X", pol=Polariteit.STEUN, st=Sterkte.STERK) -> Bewijs:
    return Bewijs(code=code, polariteit=pol, sterkte=st, regel="r", versie="1")


def _k(hyp, a, b, *bewijs) -> Kandidaat:
    return Kandidaat.maak(hyp, a, b, list(bewijs))


Z = Hypothese.ZELFDE_BETEKENIS
S, T, O = Polariteit.STEUN, Polariteit.TEGEN, Polariteit.ONBESLIST
STERK, MIDDEL, ZWAK = Sterkte.STERK, Sterkte.MIDDEL, Sterkte.ZWAK


@pytest.mark.parametrize("hyp, bewijs, uitkomst, rij", [
    (Z, [_bw(st=STERK)], Besluit.LINK, "Z-STERK-SCHOON"),
    (Z, [_bw(st=STERK), _bw(pol=T, st=STERK)], Besluit.NON_LINK, "Z-TEGEN-STERK"),
    (Z, [_bw(st=STERK), _bw(pol=T, st=MIDDEL)], Besluit.POSSIBLE_LINK, "Z-STERK-MET-TWIJFEL"),
    (Z, [_bw(st=STERK), _bw(pol=O, st=ZWAK)], Besluit.POSSIBLE_LINK, "Z-STERK-MET-TWIJFEL"),
    (Z, [_bw(st=ZWAK)], Besluit.POSSIBLE_LINK, "Z-ANDERS"),
    (Hypothese.HIERARCHIE, [_bw(st=STERK)], Besluit.LINK, "R-STERK"),
    (Hypothese.HIERARCHIE, [_bw(st=MIDDEL)], Besluit.POSSIBLE_LINK, "R-MIDDEL"),
    (Hypothese.HIERARCHIE, [_bw(st=ZWAK)], Besluit.NON_LINK, "R-TE-ZWAK"),
    (Hypothese.KWALIFICATIE, [_bw(st=STERK), _bw(pol=T, st=MIDDEL)], Besluit.NON_LINK, "R-TEGEN"),
])
def test_beslistabel(hyp, bewijs, uitkomst, rij):
    b = besluit.beslis(_k(hyp, "a", "b", *bewijs))
    assert (b.besluit, b.regel) == (uitkomst, rij)


def test_elke_familie_heeft_een_vangnetrij():
    leeg = besluit.Profiel(frozenset(), frozenset())
    for familie in ("zelfde", "relatie"):
        assert [r for r in besluit.TABEL if r.voor == familie][-1].past(leeg)


def test_een_relatie_volgens_de_wet_gaat_voor_op_een_groep():
    z = _k(Z, "a", "b", _bw())
    h = _k(Hypothese.HIERARCHIE, "a", "b", _bw())
    b = besluit.beslis_alle([z, h])
    assert (b[z.id].besluit, b[z.id].regel) == (Besluit.POSSIBLE_LINK, "Z-RELATIE-GAAT-VOOR")
    assert b[h.id].besluit is Besluit.LINK


def test_conflict_binnen_een_groep_wordt_geel_voorgelegd_niet_geknipt():
    ab, bc = _k(Z, "a", "b", _bw()), _k(Z, "b", "c", _bw())
    ac = _k(Z, "a", "c", _bw(), _bw(pol=T))
    ks = [ab, bc, ac]
    groepen, _, vragen = groeperen.groepeer(["a", "b", "c"], ks, besluit.beslis_alle(ks))
    assert len(groepen) == 1
    g = groepen[0]
    assert g.leden == ("a", "b", "c") and g.aandacht is Aandacht.GEEL and g.conflicten == (ac.id,)
    assert vragen == []


def test_vraag_eenmaal_per_paar_groepen_en_niet_als_beantwoord():
    ab = _k(Z, "a", "b", _bw())                         # a~b een groep
    ac, bc = _k(Z, "a", "c", _bw(st=ZWAK)), _k(Z, "b", "c", _bw(st=ZWAK))   # twee keer dezelfde vraag
    ad = _k(Z, "a", "d", _bw(st=ZWAK))
    bd = _k(Z, "b", "d", _bw(pol=T))                    # maar groep–d is al beantwoord
    ks = [ab, ac, bc, ad, bd]
    _, _, vragen = groeperen.groepeer(list("abcd"), ks, besluit.beslis_alle(ks))
    assert [(v.van, v.naar) for v in vragen] == [("a", "c")]


def test_relaties_tussen_leden_van_dezelfde_groep_tellen_een_keer():
    ab = _k(Z, "a", "b", _bw())
    ac = _k(Hypothese.HIERARCHIE, "a", "c", _bw(st=MIDDEL))
    bc = _k(Hypothese.HIERARCHIE, "b", "c", _bw(st=MIDDEL))
    ks = [ab, ac, bc]
    _, relaties, _ = groeperen.groepeer(list("abc"), ks, besluit.beslis_alle(ks))
    assert [(r.van, r.naar, r.aandacht) for r in relaties] == [("a", "c", Aandacht.GEEL)]


# --- de keten op de referentieset -----------------------------------------------------------

@pytest.fixture(scope="module")
def manifest():
    bronnen, cases, _ = be.laad()
    return be.manifest_uit(bronnen, cases)


@pytest.fixture(scope="module")
def uitkomst(manifest):
    pytest.importorskip("spacy")
    from agent.jas_pipeline.taal.provider import SpacyProvider
    p = SpacyProvider("nl_core_news_md")
    if p.analyseer("x").gedegradeerd:
        pytest.skip("nl_core_news_md niet geïnstalleerd (uv sync --extra nlp)")
    return keten.analyseer(manifest, p)


def _samen(u, a, b) -> bool:
    return any(a in g.leden and b in g.leden for g in u.groepen)


@pytest.mark.parametrize("a, b", [("f18", "f19"),     # homoniem 'termijnen'
                                  ("f01", "f22"),     # afwijkende kwalificatie (lid 3)
                                  ("f01", "f21"),     # gelijkgesteld is geen synoniem
                                  ("f01", "f03"),     # 'de aanslag' is een soort, geen synoniem
                                  ("f01", "f20")])    # beperkte term is een soort
def test_acceptatie_nooit_samengevoegd(uitkomst, a, b):
    assert not _samen(uitkomst, a, b)


def test_acceptatie_elke_groep_en_relatie_heeft_uitleg_met_regel(uitkomst):
    for x in (*uitkomst.groepen, *uitkomst.relaties, *uitkomst.vragen):
        assert x.uitleg and any("[begrip." in r for r in x.uitleg) and \
            any(r.startswith("besluit ") for r in x.uitleg)


def test_acceptatie_groepen_alleen_uit_link(uitkomst):
    besl = {b.kandidaat_id: b.besluit for b in uitkomst.beslissingen}
    assert all(besl[k] is Besluit.LINK for g in uitkomst.groepen for k in g.kandidaten)


def test_acceptatie_bitgelijk_bij_herhaling(manifest, uitkomst):
    from agent.jas_pipeline.taal.provider import SpacyProvider
    opnieuw = keten.analyseer(manifest, SpacyProvider("nl_core_news_md"))

    def dump(u):
        return json.dumps([[g.model_dump() for g in u.groepen], [r.model_dump() for r in u.relaties],
                           [v.model_dump() for v in u.vragen], [b.model_dump() for b in u.beslissingen]],
                          sort_keys=True, default=str)
    assert dump(opnieuw) == dump(uitkomst)


def test_meldingen_per_fase(manifest):
    gemeld = []
    keten.analyseer(manifest, NullProvider(), melding=lambda f, s, ms: gemeld.append(f))
    assert gemeld == ["Taalanalyse", "Signalen", "Groeperen"]


def test_zonder_parser_draait_de_keten_gedegradeerd_en_zegt_dat(manifest):
    u = keten.analyseer(manifest, NullProvider())
    assert u.meting["gedegradeerd"] == len(manifest.formuleringen)
    assert not _samen(u, "f18", "f19") and not _samen(u, "f01", "f22")
