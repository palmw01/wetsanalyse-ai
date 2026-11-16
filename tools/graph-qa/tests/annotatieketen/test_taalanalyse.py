"""De linguïstische analyselaag (ADR-001): providercontract, UD-afleidingen, geen stille terugval."""
from __future__ import annotations

import pytest

from agent.jas_pipeline.taal import (
    LinguisticAnalysis, Niveau, NullProvider, SpacyProvider, Token, Zin, bijzinnen, clausebereik, maak_provider,
    naamwoordgroepen, predicaten, spanopties,
)
from agent.jas_pipeline.taal.provider import tokens_en_zinnen

# --- een handgemaakte UD-parse: providerloos, dus deze tests gelden voor elke parser ----------------
#
#   Indien de verzekerde niet betaalt , is hij de boete verschuldigd .
#   0      1  2          3    4       5 6  7   8  9     10          11

_TEKST = "Indien de verzekerde niet betaalt, is hij de boete verschuldigd."
_RIJEN = [  # tekst, upos, head, deprel
    ("Indien", "SCONJ", 4, "mark"), ("de", "DET", 2, "det"), ("verzekerde", "NOUN", 4, "nsubj"),
    ("niet", "ADV", 4, "advmod"), ("betaalt", "VERB", 10, "advcl"), (",", "PUNCT", 4, "punct"),
    ("is", "AUX", 10, "cop"), ("hij", "PRON", 10, "nsubj"), ("de", "DET", 9, "det"),
    ("boete", "NOUN", 10, "obj"), ("verschuldigd", "ADJ", -1, "root"), (".", "PUNCT", 10, "punct"),
]


def _analyse(tekst: str = _TEKST, rijen=_RIJEN) -> LinguisticAnalysis:
    tokens, pos = [], 0
    for i, (w, upos, head, rel) in enumerate(rijen):
        start = tekst.index(w, pos)
        tokens.append(Token(i, w, start, start + len(w), 0, w.lower(), upos, "", (), head, rel))
        pos = start + len(w)
    return LinguisticAnalysis(tekst, tuple(tokens), (Zin(0, 0, len(tekst), (0, len(tokens))),), "hand")


def _teksten(a, cs):
    return {(c.soort, a.tekst[c.start:c.eind]) for c in cs}


def test_subboom_en_bereik():
    a = _analyse()
    assert a.subboom(4) == (0, 1, 2, 3, 4, 5)
    assert a.tekst[slice(*a.bereik(a.subboom(2)))] == "de verzekerde"


def test_subboom_overleeft_een_cyclische_parse():
    t = [Token(0, "a", 0, 1, 0, head=1, deprel="x"), Token(1, "b", 2, 3, 0, head=0, deprel="x")]
    a = LinguisticAnalysis("a b", tuple(t), (Zin(0, 0, 3, (0, 2)),), "hand")
    assert a.subboom(0) == (0, 1)


def test_naamwoordgroepen_kennen_kern_en_volle_groep():
    a = _analyse()
    assert {("np", "de verzekerde"), ("np", "hij"), ("np", "de boete")} <= _teksten(a, naamwoordgroepen(a))


def test_bijzin_draagt_zijn_voegwoord_en_geen_randinterpunctie():
    a = _analyse()
    [b] = bijzinnen(a)
    assert (a.tekst[b.start:b.eind], b.markeerder) == ("Indien de verzekerde niet betaalt", "indien")


def test_predicaat_is_hoofd_plus_koppelwerkwoord():
    a = _analyse()
    assert ("predicaat", "is hij de boete verschuldigd") in _teksten(a, predicaten(a))
    [p] = [p for p in predicaten(a) if p.soort == "predicaat" and p.kop == 10]
    assert p.tokens == (6, 10)       # onderbroken: 'is' … 'verschuldigd'


def test_spanopties_bevatten_de_grenzen_die_detectoren_nodig_hebben():
    a = _analyse()
    opties = {a.tekst[s:e] for s, e in spanopties(a)}
    assert {"de verzekerde", "Indien de verzekerde niet betaalt", "de boete",
            "Indien de verzekerde niet betaalt, is hij de boete verschuldigd"} <= opties


def test_gedegradeerde_analyse_levert_geen_constituenten_maar_wel_zinnen():
    a = NullProvider().analyseer(_TEKST)
    assert a.niveau is Niveau.TOKENS and a.gedegradeerd and a.fout
    assert naamwoordgroepen(a) == bijzinnen(a) == predicaten(a) == []
    assert {a.tekst[s:e] for s, e in spanopties(a)} == {_TEKST.rstrip(".")}


# --- terugval en providerkeuze ------------------------------------------------------------------

def test_null_tokens_zijn_letterlijk_en_in_codepoints():
    tekst = "De ontvanger 😀 handelt.\nb. binnen zes weken; zie art. 9 van de wet. Klaar."
    tokens, zinnen = tokens_en_zinnen(tekst)
    assert all(tekst[t.start:t.eind] == t.tekst for t in tokens)
    assert [t.tekst for t in tokens][:4] == ["De", "ontvanger", "😀", "handelt"]
    assert [tekst[z.start:z.eind] for z in zinnen] == [
        "De ontvanger 😀 handelt.", "b. binnen zes weken; zie art. 9 van de wet.", "Klaar."]


def test_ontbrekend_model_degradeert_zichtbaar_en_gooit_niet():
    a = SpacyProvider("bestaat_niet_xyz").analyseer("Een zin.")
    assert a.gedegradeerd and "bestaat_niet_xyz" in a.fout and a.provider == "spacy"
    assert [t.tekst for t in a.tokens] == ["Een", "zin", "."]


def test_maak_provider():
    assert maak_provider("null").naam == "null"
    assert maak_provider("spacy").model.startswith("nl_core_news_md")
    assert maak_provider("stanza:nl").naam == "stanza"
    with pytest.raises(ValueError):
        maak_provider("chatgpt")


# --- de echte parser (alleen als de `nlp`-extra geïnstalleerd is) ---------------------------------

@pytest.fixture(scope="module")
def spacy_md():
    pytest.importorskip("spacy")
    p = SpacyProvider("nl_core_news_md")
    if p.analyseer("x").gedegradeerd:
        pytest.skip("nl_core_news_md niet geïnstalleerd (uv sync --extra nlp)")
    return p


def test_spacy_offsets_letterlijk_en_deterministisch(spacy_md):
    tekst = "1. Indien de verzekerde niet binnen zes weken betaalt,\n\nis hij € 23 verschuldigd."
    a, b = spacy_md.analyseer(tekst), spacy_md.analyseer(tekst)
    assert not a.gedegradeerd and a.model.startswith("nl_core_news_md-")
    assert all(tekst[t.start:t.eind] == t.tekst for t in a.tokens)
    assert not any(t.tekst.isspace() for t in a.tokens)
    assert a.tokens == b.tokens
    assert all(0 <= t.head < len(a.tokens) or t.deprel == "root" for t in a.tokens)


def test_spacy_herkent_voorwaardelijke_voegwoorden(spacy_md):
    a = spacy_md.analyseer("Indien de belastingplichtige niet betaalt, is hij een boete verschuldigd.")
    assert next(t for t in a.tokens if t.tekst == "Indien").deprel == "mark"
    # "voor zover": 'voor' is de inleider; 'zover' hangt er als fixed of advmod bij, per zin anders.
    a = spacy_md.analyseer("De sanctie vervalt voor zover deze beoogt leed toe te voegen.")
    assert next(t for t in a.tokens if t.tekst == "voor").deprel == "mark"


def test_benchmark_gebruikt_alleen_de_ontwikkelsplit():
    from eval.taal_benchmark import ontwikkelcasussen
    casussen = ontwikkelcasussen()
    assert casussen and {c["split"] for c in casussen} == {"ontwikkeling"}
    assert not {c["familie"] for c in casussen} & {"BW6", "Omgevingswet"}


# --- de eigen clause van een predicaat -----------------------------------------------------------

def test_clausebereik_laat_de_voorwaarde_en_de_rand_weg():
    a = _analyse()
    assert a.tekst[slice(*clausebereik(a, 10))] == "is hij de boete verschuldigd"
    assert a.tekst[slice(*clausebereik(a, 4))] == "de verzekerde niet betaalt"


def test_clausebereik_gokt_niet_als_de_clause_onderbroken_is():
    #   Hij is , indien hij niet betaalt , de boete verschuldigd .
    #   0   1  2 3      4   5    6       7 8  9     10          11
    tekst = "Hij is, indien hij niet betaalt, de boete verschuldigd."
    rijen = [("Hij", "PRON", 10, "nsubj"), ("is", "AUX", 10, "cop"), (",", "PUNCT", 6, "punct"),
             ("indien", "SCONJ", 6, "mark"), ("hij", "PRON", 6, "nsubj"), ("niet", "ADV", 6, "advmod"),
             ("betaalt", "VERB", 10, "advcl"), (",", "PUNCT", 6, "punct"), ("de", "DET", 9, "det"),
             ("boete", "NOUN", 10, "obj"), ("verschuldigd", "ADJ", -1, "root"), (".", "PUNCT", 10, "punct")]
    assert clausebereik(_analyse(tekst, rijen), 10) is None


def test_clausebereik_houdt_een_nevengeschikt_gevolg_apart():
    #   De termijn vervalt en de boete vervalt .
    tekst = "De termijn vervalt en de boete vervalt."
    rijen = [("De", "DET", 1, "det"), ("termijn", "NOUN", 2, "nsubj"), ("vervalt", "VERB", -1, "root"),
             ("en", "CCONJ", 6, "cc"), ("de", "DET", 5, "det"), ("boete", "NOUN", 6, "nsubj"),
             ("vervalt", "VERB", 2, "conj"), (".", "PUNCT", 2, "punct")]
    a = _analyse(tekst, rijen)
    assert tekst[slice(*clausebereik(a, 2))] == "De termijn vervalt"
    assert tekst[slice(*clausebereik(a, 6))] == "de boete vervalt"


def test_clausebereik_laat_een_inversievoorwaarde_weg_ook_als_de_parse_haar_aan_het_predicaat_hangt():
    #   Is de dagtekening 15 maart , vervalt de termijn op 15 april .
    #   0  1  2           3  4     5 6       7  8       9  10 11    12
    tekst = "Is de dagtekening 15 maart, vervalt de termijn op 15 april."
    rijen = [("Is", "AUX", 6, "aux"), ("de", "DET", 2, "det"), ("dagtekening", "NOUN", 6, "nsubj"),
             ("15", "NUM", 2, "appos"), ("maart", "PROPN", 3, "flat"), (",", "PUNCT", 2, "punct"),
             ("vervalt", "VERB", -1, "root"), ("de", "DET", 8, "det"), ("termijn", "NOUN", 6, "nsubj"),
             ("op", "ADP", 10, "case"), ("15", "NUM", 6, "obl"), ("april", "PROPN", 10, "flat"),
             (".", "PUNCT", 6, "punct")]
    assert tekst[slice(*clausebereik(_analyse(tekst, rijen), 6))] == "vervalt de termijn op 15 april"


def test_clausebereik_zonder_parse_is_none():
    a = NullProvider().analyseer("Het besluit vervalt.")
    assert clausebereik(a, 0) is None
