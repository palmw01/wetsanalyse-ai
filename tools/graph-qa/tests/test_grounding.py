"""Grounding-verificatie en bron-curatie."""
from __future__ import annotations

import pytest

from agent.grounding import check_grounding, curate_sources
from agent.models import Source
from agent.provenance import citations_in, iter_refs

IW = "urn:bwb:BWBR0004770:artikel:9"
LEIDRAAD = "urn:bwb:BWBR0024096:artikel:26"


def _trace(text: str):
    return [("get_artikel", text)]


def test_citatie_in_trace_is_grounded():
    answer = "Zie artikel 9 van de Invorderingswet 1990 (BWBR0004770)."
    report = check_grounding(answer, _trace(f"<{IW}> bwb:tekst '...' ."))
    assert report.grounded is True
    assert report.unsupported == []


def test_verzonnen_citatie_wordt_gemarkeerd():
    answer = "Zie de niet-bestaande regeling BWBR9999999."
    report = check_grounding(answer, _trace(f"<{IW}>"))
    assert report.grounded is False
    assert any("BWBR9999999" in u for u in report.unsupported)


def test_grounding_op_bwb_granulariteit_geen_vals_alarm():
    # Antwoord noemt een jci met afwijkende opmaak; BWB-id staat wél in de trace → geen alarm.
    answer = "Vindplaats: jci1.3:c:BWBR0004770&artikel=9&lid=1"
    report = check_grounding(answer, _trace("resultaat met BWBR0004770 erin"))
    assert report.grounded is True


def test_prefix_bwb_wordt_niet_vals_gegrond():
    # L1: het antwoord noemt een prefix-id (BWBR0001) van het opgehaalde BWBR00012345. Exacte match
    # (geen substring) → terecht ongegrond.
    report = check_grounding("Volgens BWBR0001 geldt de termijn.", _trace("resultaat met BWBR00012345 erin"))
    assert report.grounded is False
    assert any("BWBR0001" in u for u in report.unsupported)


def test_curate_prefix_bwb_wordt_niet_meegesleept():
    # L1: een bron met langer id mag niet meeliften op een genoemde prefix-id.
    langer = "urn:bwb:BWBR00012345:artikel:1"
    sources = [Source(label=langer, uri=langer), Source(label=IW, uri=IW)]
    kept = [s.uri for s in curate_sources(sources, "Zie BWBR0001 en de Invorderingswet (BWBR0004770).")]
    assert IW in kept
    assert langer not in kept


def test_curate_beperkt_tot_genoemde_regeling():
    sources = [
        Source(label=IW, uri=IW),
        Source(label=LEIDRAAD, uri=LEIDRAAD),
    ]
    answer = "Alleen de Invorderingswet 1990 (BWBR0004770) is relevant."
    kept = curate_sources(sources, answer)
    uris = [s.uri for s in kept]
    assert IW in uris
    assert LEIDRAAD not in uris  # niet genoemde regeling valt weg


def test_curate_valt_terug_op_alles_zonder_bwb_in_antwoord():
    sources = [Source(label=IW, uri=IW)]
    kept = curate_sources(sources, "Een antwoord zonder enig BWB-id.")
    assert kept == sources


def test_jci_backslash_wordt_gestript():
    text = r'"jci1.3:c:BWBR0004770&artikel=9&z=2026-07-01\ " staat hier'
    uris = [uri for uri, _, jci in iter_refs(text) if jci]
    assert uris
    assert not any(u.endswith("\\") for u in uris)


@pytest.mark.parametrize("tekst", ["Gezocht op `urn:bwb:BWBR0004770:artikel:9` met subtree.",
                                   "Zie **urn:bwb:BWBR0004770:artikel:9**.",
                                   "`jci1.3:c:BWBR0004770&artikel=9`"])
def test_markdown_rond_een_vindplaats_hoort_er_niet_bij(tekst):
    """Acceptatie 7 nov 2026: "urn:bwb:BWBR0004770:artikel:9`" stond als niet-onderbouwde vindplaats in de grounding."""
    refs = citations_in(tekst)
    assert refs and not any(t in r for r in refs for t in "`*")


def test_een_artikelnummer_in_markdown_is_bekend():
    trace = [("get_artikel", '{"status": "ok", "resultaten": [{"iri": "urn:bwb:BWBR0004770:artikel:9", "tekst": "x"}]}')]
    rapport = check_grounding("Zie `urn:bwb:BWBR0004770:artikel:9`: artikel 9 regelt dit.", trace)
    assert rapport.unsupported == [] and not getattr(rapport, "onbevestigd", [])


def test_citations_in_negeert_vocabulaire_namespace():
    assert citations_in("?s <urn:bwb-ns:heeftLid> ?o") == []


# --- Niveau: gegrond / onbepaald / ongegrond -----------------------------------------------------
#
# `grounded` was een bool, en "geen enkele verwijzing genoemd" viel daarmee in dezelfde bak als
# "alles gecontroleerd en in orde". Dat is de gevaarlijkste soort meting: de afwezigheid van bewijs
# telde als bewijs van afwezigheid.

def test_antwoord_zonder_vindplaats_is_onbepaald_niet_gegrond():
    report = check_grounding(
        "De aanslag is invorderbaar zes weken na de dagtekening.",
        _trace(f"<{IW}> bwb:tekst 'iets' ."),
    )
    assert report.niveau == "onbepaald"
    assert report.cited == []
    # De bool blijft doen wat hij deed (er is niets AANGETROFFEN dat niet klopt) – het onderscheid
    # zit in het niveau, zodat de weergave er iets anders van kan maken dan groen.
    assert report.grounded is True


def test_gecontroleerde_verwijzing_is_gegrond():
    report = check_grounding("Zie BWBR0004770, artikel 9.", _trace("resultaat met urn:bwb:BWBR0004770:artikel:9"))
    assert report.niveau == "gegrond"


def test_verzonnen_verwijzing_is_ongegrond():
    report = check_grounding("Zie BWBR9999999.", _trace("resultaat met BWBR0004770"))
    assert report.niveau == "ongegrond"


# --- Citaatcontrole ------------------------------------------------------------------------------
#
# De agent belooft letterlijk te citeren, en de annotatieketen dwingt dat af. In het antwoordpad
# ontbrak die controle: een citaat met één woord verschil passeerde ongemerkt.

WETTEKST = _trace(
    "?lidtekst\nEen belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet."
)


def test_letterlijk_citaat_passeert():
    report = check_grounding(
        'De wet zegt: "Een belastingaanslag is invorderbaar zes weken na de dagtekening".',
        WETTEKST,
    )
    assert report.niet_letterlijk == []
    assert report.niveau == "gegrond" or report.niveau == "onbepaald"


def test_bijna_letterlijk_citaat_wordt_gemarkeerd():
    report = check_grounding(
        'De wet zegt: "Een belastingaanslag is invorderbaar binnen zes weken na de dagtekening".',
        WETTEKST,
    )
    assert report.niet_letterlijk, "een ingevoegd woord hoort op te vallen"
    assert report.niveau == "ongegrond"
    assert report.grounded is False


def test_citaat_met_afwijkende_witruimte_is_geen_afwijking():
    # Dezelfde normalisatie als bij een JAS-markering: layout mag verschillen, woorden niet.
    report = check_grounding(
        'Er staat:  "Een belastingaanslag   is invorderbaar\nzes weken na de dagtekening".',
        WETTEKST,
    )
    assert report.niet_letterlijk == []


def test_kort_aangehaald_begrip_wordt_niet_gecontroleerd():
    # "belastingschuldige" tussen quotes is een begrip, geen citaat van een passage. Daarop
    # controleren levert vals alarm bij elke verbuiging.
    report = check_grounding('Het begrip "de belastingschuldige" komt hier terug.', WETTEKST)
    assert report.niet_letterlijk == []
    assert report.niveau == "onbepaald"


# --- wat de tijdlijn erover zegt ------------------------------------------------------------------

def test_rapport_telt_hoeveel_citaten_zijn_nagelopen():
    """Zonder dat getal is niet te melden wát er is gecontroleerd."""
    answer = 'Er staat: "De ontvanger verleent uitstel van betaling" en "dat is de regel hier".'
    report = check_grounding(answer, _trace("De ontvanger verleent uitstel van betaling."))
    assert report.citaten == 2
    assert report.niet_letterlijk == ["dat is de regel hier"]


def test_melding_noemt_de_citaten_als_er_geen_vindplaats_is():
    """Artikelen in gewone taal, dus nul vindplaatsen – maar wél twee citaten die allebei kloppen.
    De melding "0 verwijzingen onderbouwd" zou dan lezen als
    een mislukte controle terwijl er juist iets gecontroleerd én goed bevonden was."""
    from agent.orchestrator import _grounding_melding

    answer = (
        'Volgens artikel 2 lid 1 onderdeel m geldt: "De ontvanger verleent uitstel van betaling" '
        'en verderop "indien de schuldenaar daarom verzoekt".'
    )
    bron = "urn:bwb:BWBR0004770:artikel:2 De ontvanger verleent uitstel van betaling indien de schuldenaar daarom verzoekt."
    report = check_grounding(answer, _trace(bron))

    assert report.cited == [] and report.niveau == "gegrond"
    assert _grounding_melding(report) == "brongetrouwheid: 2 citaten gecontroleerd"


def test_melding_zwijgt_niet_als_er_niets_te_controleren_viel():
    from agent.orchestrator import _grounding_melding

    report = check_grounding("Dat staat niet in de kennisgraaf.", _trace("iets anders"))
    assert report.niveau == "onbepaald"
    assert "niets te controleren" in _grounding_melding(report)


def test_melding_noemt_beide_soorten_als_ze_er_allebei_zijn():
    from agent.orchestrator import _grounding_melding

    answer = f'Zie {IW} (BWBR0004770): "De ontvanger verleent uitstel van betaling".'
    bron = f"<{IW}> bwb:tekst 'De ontvanger verleent uitstel van betaling.' ."
    melding = _grounding_melding(check_grounding(answer, _trace(bron)))
    assert "verwijzing" in melding and "1 citaat" in melding and "gecontroleerd" in melding


def test_curate_houdt_binnen_een_regeling_alleen_het_pad_van_de_geciteerde_vindplaats():
    """Een definitievraag haalt art. 2 lid 1 op met alle onderdelen; het antwoord gaat over k."""
    art = "urn:bwb:BWBR0004770:artikel:2"
    lid = f"{art}:lid:1"
    onderdelen = [f"{lid}:o:{c}" for c in "abcdefghijklmnopqrstuvwxyz"]
    sources = [Source(label=u, uri=u) for u in ["BWBR0004770", art, lid, *onderdelen, LEIDRAAD]]
    antwoord = ("Het begrip is gedefinieerd in artikel 2 lid 1 onderdeel k. "
                "Vindplaats: jci1.3:c:BWBR0004770&hoofdstuk=I&artikel=2&lid=1&o=k")
    kept = [s.uri for s in curate_sources(sources, antwoord)]
    assert kept == ["BWBR0004770", art, lid, f"{lid}:o:k"]


def test_curate_zonder_precieze_vindplaats_houdt_de_hele_regeling():
    lid = "urn:bwb:BWBR0004770:artikel:2:lid:1"
    sources = [Source(label=u, uri=u) for u in [lid, f"{lid}:o:a", f"{lid}:o:k"]]
    kept = curate_sources(sources, "Zie de Invorderingswet 1990 (BWBR0004770).")
    assert [s.uri for s in kept] == [s.uri for s in sources]


def test_curate_snoeit_alleen_binnen_de_regeling_met_een_precieze_vindplaats():
    iw_k = "urn:bwb:BWBR0004770:artikel:2:lid:1:o:k"
    iw_a = "urn:bwb:BWBR0004770:artikel:2:lid:1:o:a"
    awr = "urn:bwb:BWBR0002320:artikel:1"
    sources = [Source(label=u, uri=u) for u in [iw_k, iw_a, awr]]
    antwoord = "Zie jci1.3:c:BWBR0004770&artikel=2&lid=1&o=k en de AWR (BWBR0002320)."
    assert [s.uri for s in curate_sources(sources, antwoord)] == [iw_k, awr]


# ── elke citaatvorm, en wat niet is teruggevonden ───────────────────────────────────────────────

BRON_IW = [("get_lid", 'urn:bwb:BWBR0004770:artikel:9\n?tekst\n"Een belastingaanslag is invorderbaar zes weken na de dagtekening '
                       'van het aanslagbiljet, bedoeld in artikel 8."')]
ECHT = "Een belastingaanslag is invorderbaar zes weken na de dagtekening"
VALS = "Een belastingaanslag is invorderbaar drie weken na de verzending van het aanslagbiljet"


@pytest.mark.parametrize("antwoord", [
    f'Artikel 9: "{VALS}". BWBR0004770',
    f"Artikel 9: “{VALS}”. BWBR0004770",
    f"Artikel 9: „{VALS}”. BWBR0004770",
    f'Artikel 9: „{VALS}". BWBR0004770',
    f"Artikel 9: „{VALS}“. BWBR0004770",
    f'Artikel 9: "{VALS[:30]}\n{VALS[30:]}". BWBR0004770',
    'Artikel 9: "' + (VALS + " ") * 6 + '". BWBR0004770',
])
def test_elke_citaatvorm_wordt_getoetst(antwoord):
    rapport = check_grounding(antwoord, BRON_IW)
    assert rapport.niveau == "ongegrond" and rapport.niet_letterlijk and rapport.grounded is False


@pytest.mark.parametrize("antwoord", [f"Artikel 9 luidt:\n\n> {VALS}.\n\nBWBR0004770", "Artikel 999 lid 7 regelt dit. BWBR0004770"])
def test_een_signaal_is_nooit_gegrond_en_start_geen_correctie(antwoord):
    rapport = check_grounding(antwoord, BRON_IW)
    assert rapport.niveau == "onbepaald" and rapport.onbevestigd
    assert rapport.grounded is True, "een correctieronde op vals alarm beschadigt een goed antwoord"


@pytest.mark.parametrize("antwoord", [
    f"Artikel 9: „{ECHT}”. BWBR0004770",
    "Artikel 9: \"" + ECHT.replace("invorderbaar ", "invorderbaar\n") + "\". BWBR0004770",
    f"Artikel 9 luidt:\n\n> {ECHT}\n\nBWBR0004770",
    "Artikel 9 verwijst naar artikel 8. BWBR0004770",    # de wettekst noemt artikel 8, in geen enkele IRI
])
def test_wat_klopt_blijft_gegrond(antwoord):
    rapport = check_grounding(antwoord, BRON_IW)
    assert rapport.niveau == "gegrond" and not rapport.onbevestigd and not rapport.niet_letterlijk


def test_een_nummer_met_dubbele_punt_uit_de_iri_is_bekend():
    trace = [("get_lid", "urn:bwb:BWBR0005537:artikel:5%3A2:lid:1\nx")]
    assert check_grounding("Artikel 5:2 regelt dit. BWBR0005537", trace).onbevestigd == []
    jci = [("get_lid", "jci1.3:c:BWBR0005537&artikel=7:1&z=2026-01-01 x")]
    assert check_grounding("Artikel 7:1 regelt dit. BWBR0005537", jci).onbevestigd == []


def test_een_kale_nummerlijst_en_een_bepaling_zijn_bekend():
    trace = [("zoek", '{"bepalingen": "4, 5a"}'), ("get_bepaling", "urn:bwb:BWBR0024096:bepaling:9.1\nx")]
    assert check_grounding("Artikel 5a en artikel 9.1. BWBR0024096", trace).onbevestigd == []


def test_wat_eerder_is_opgehaald_telt_mee():
    """`controletrace`: eerst het bronregister, dan deze beurt."""
    trace = [("get_lid", "urn:bwb:BWBR0004770:artikel:36\nx"), *BRON_IW]
    assert check_grounding("Artikel 36 en artikel 9. BWBR0004770", trace).onbevestigd == []


def test_losse_aanhalingstekens_in_twee_alineas_zijn_geen_citaat():
    antwoord = 'Het woord " staat hier los en dit zijn nog wat woorden.\n\nEn hier nog een " in een andere alinea. BWBR0004770'
    assert check_grounding(antwoord, BRON_IW).citaten == 0


def test_de_overzichtsroute_toetst_hard_en_geeft_geen_signaal():
    rapport = check_grounding("Artikel 999 regelt dit.", BRON_IW, overzicht={"regelingen": []})
    assert "artikel 999" in rapport.unsupported and rapport.onbevestigd == []


def test_de_tijdlijn_zegt_wat_er_niet_is_teruggevonden():
    from agent.narratie import _grounding_melding

    assert "niet teruggevonden" in _grounding_melding(check_grounding("Artikel 999 regelt dit. BWBR0004770", BRON_IW))


def test_melding_zonder_aanhaling_heeft_geen_lege_telling():
    """De bepalingsroute toont tekst van de code: niets aangehaald. "brongetrouwheid:  gecontroleerd" las als een fout."""
    from agent.orchestrator import _grounding_melding

    from types import SimpleNamespace

    report = SimpleNamespace(niveau="gegrond", onbevestigd=[], unsupported=[], niet_letterlijk=[], cited=[], citaten=0)
    assert _grounding_melding(report) == "brongetrouwheid: gecontroleerd, niets aangehaald"
