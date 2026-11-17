"""De drie punten uit de meting van F02 na #1629 (16 nov 2026; meetverslag `centrale-agent-2026-11-16-f02`).

1. Na een rapport mag het antwoord elk stuk uit de rapporten tonen. Het rapport citeerde zes arresten, het antwoord toonde
   er vier (`extern.MAX_STUKKEN`), en HR 2018:1790 en 2023:1271 vielen weg.
2. De leemte zegt waarom een aanwijzing wegviel: boven de grens of niet gelezen. Er stond altijd "klopte niet".
3. Een genummerde kop in de tekst en het procesverloop van een uitspraak zijn geen citaat als er iets met inhoud
   overblijft. HR 2005:AS5040 toonde "1. Beschikkingen, bezwaar en geding voor het Hof" en drie alinea's over de
   procedure naast de dragende r.o. 3.3. De gerichte set staat in `tests/data/uitspraak_koppen_set.json`.

Nepbronnen in de echte vorm (`get_uitspraak` door de echte toollaag), zoals `test_a6_citaten.py`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import sjablonen, tools
from agent import subagent as sub
from agent.sjablonen import extern
from test_rechtspraak_tools import AAN, V_NU, Link, NepBron

SET = json.loads((Path(__file__).parents[1] / "data" / "uitspraak_koppen_set.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("geval", SET["koppen"], ids=lambda g: g["tekst"][:40])
def test_een_genummerde_kop_in_de_tekst(geval):
    assert extern.is_sectiekop(geval["tekst"]) is geval["kop"]
    if geval["kop"]:
        assert extern.is_kopregel(geval["tekst"])


@pytest.mark.parametrize("geval", SET["secties"], ids=lambda g: g["kop"][:40])
def test_de_kop_van_het_procesverloop(geval):
    assert extern.is_procesverloop(geval["kop"]) is geval["procesverloop"]


def _xml(ecli: str, paras: list[str], datum: str = "2005-10-21") -> bytes:
    inhoud = "".join(f"<para>{a}</para>" for a in paras)
    return f"""<open-rechtspraak xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:dcterms="http://purl.org/dc/terms/" xmlns:psi="http://psi.rechtspraak.nl/"
  xmlns="http://www.rechtspraak.nl/schema/rechtspraak-1.0">
<rdf:RDF><rdf:Description><dcterms:identifier>{ecli}</dcterms:identifier><dcterms:creator>Hoge Raad</dcterms:creator>
  <dcterms:date>{datum}</dcterms:date><dcterms:type>Uitspraak</dcterms:type></rdf:Description></rdf:RDF>
<inhoudsindicatie><para>Artikel 30 IW 1990. Invorderingsrente pas vast na een beschikking van de ontvanger.</para>
</inhoudsindicatie>
<uitspraak>{inhoud}</uitspraak></open-rechtspraak>""".encode()


OUD = "ECLI:NL:HR:2005:AS5040"
#: Het oude schema: de koppen staan als gewone alinea in de tekst.
OUDE_TEKST = [
    "1. Beschikkingen, bezwaar en geding voor het Hof",
    "Aan belanghebbende is ter zake van de betekening van een dwangbevel een bedrag aan kosten van vervolging in "
    "rekening gebracht, dat na bezwaar is verminderd.",
    "Het Hof heeft het beroep gegrond verklaard en de in rekening gebrachte kosten van vervolging verminderd tot nihil.",
    "2. Geding in cassatie",
    "De Staatssecretaris van Financiën heeft tegen de uitspraak van het Hof beroep in cassatie ingesteld.",
    "3. Beoordeling van het middel",
    "3.3. Welk bedrag van een betaling aan de rente wordt toegerekend, staat pas vast na de vaststelling door de "
    "ontvanger van het bedrag van de invorderingsrente bij voor bezwaar vatbare beschikking.",
]


def _trace(*stukken: tuple[str, list[str]]):
    docs = {e: _xml(e, p) for e, p in stukken}
    bron = NepBron([Link(e, f"{e} - Hoge Raad, 21-10-2005 / 40468", "Door computer herkende referentie", V_NU)
                    for e, _ in stukken], docs=docs)
    return [("get_uitspraak", tools.dispatch("get_uitspraak", None, {"id": e}, AAN, rechtspraak=bron)) for e, _ in stukken]


def _nrs(trace, i: int = 0) -> dict[str, int]:
    return {r["tekst"]: r["nr"] for r in json.loads(trace[i][1])["resultaten"]}


def test_kop_en_procesverloop_vallen_weg_naast_een_dragende_overweging():
    trace = _trace((OUD, OUDE_TEKST))
    nr = _nrs(trace)
    items = [{"id": OUD, "van_nr": nr[OUDE_TEKST[0]], "tot_nr": nr[OUDE_TEKST[2]], "kern": ""},
             {"id": OUD, "van_nr": nr[OUDE_TEKST[6]], "tot_nr": nr[OUDE_TEKST[6]], "kern": ""}]
    [blok] = [b for b in extern.blokken(items, trace, overgeslagen=[]) if b.soort == "extern"]
    assert [p.tekst for p in blok.passages] == [OUDE_TEKST[6]]


def test_wie_alleen_het_procesverloop_aanwijst_krijgt_het():
    trace = _trace((OUD, OUDE_TEKST))
    nr = _nrs(trace)
    items = [{"id": OUD, "van_nr": nr[OUDE_TEKST[1]], "tot_nr": nr[OUDE_TEKST[2]], "kern": ""}]
    [blok] = [b for b in extern.blokken(items, trace, overgeslagen=[]) if b.soort == "extern"]
    assert [p.tekst for p in blok.passages] == OUDE_TEKST[1:3]


def test_de_sectie_komt_uit_de_kop_in_de_tekst_of_uit_de_sectiekop():
    rijen = {1: {"tekst": "1. Het geding in feitelijke instantie", "kop": "Uitspraak"},
             2: {"tekst": "Belanghebbende heeft bezwaar gemaakt.", "kop": "Uitspraak"},
             3: {"tekst": "De Hoge Raad oordeelt als volgt over de rente.", "kop": "Uitspraak › 2 Beoordeling"},
             4: {"tekst": "Belanghebbende heeft beroep in cassatie ingesteld.", "kop": "Uitspraak › 1 Geding in cassatie"}}
    assert extern.secties(rijen) == {1: "1. Het geding in feitelijke instantie",
                                     2: "1. Het geding in feitelijke instantie", 3: "2 Beoordeling",
                                     4: "1 Geding in cassatie"}


ARRESTEN = [f"ECLI:NL:HR:2018:{n}" for n in range(1781, 1787)]
DRAGEND = ("De ontvanger stelt de invorderingsrente vast bij een voor bezwaar vatbare beschikking, en pas daarna is zij "
           "te betwisten.")


def _zes():
    return _trace(*((e, [DRAGEND]) for e in ARRESTEN))


def _invoer(trace):
    items = []
    for i, e in enumerate(ARRESTEN):
        n = _nrs(trace, i)[DRAGEND]
        items.append({"id": e, "van_nr": n, "tot_nr": n, "kern": "De ontvanger stelt de rente vast bij beschikking."})
    return {"kort_antwoord": "Zes arresten over de beschikking invorderingsrente.", "extern": items, "stukken": [],
            "twijfel": []}


def test_na_een_rapport_toont_het_antwoord_elk_stuk_uit_het_rapport():
    trace = _zes()
    state = {"subagenten": [{"profiel": "rechtspraak_lezen", "uitkomst": "klaar", "rapport": True,
                             "stukken": [[e, e] for e in ARRESTEN]}]}
    assert sub.stukkengrens(state) == 6
    antwoord = sjablonen.vul("antwoord_extern", _invoer(trace), trace, max_stukken=sub.stukkengrens(state))
    assert [b.id for b in antwoord.blokken if b.soort == "extern"] == ARRESTEN
    # Zonder rapport de gewone grens, en de leemte zegt dat het de grens was, met de stukken die wegvielen.
    zonder = sjablonen.vul("antwoord_extern", _invoer(trace), trace)
    assert len([b for b in zonder.blokken if b.soort == "extern"]) == extern.MAX_STUKKEN
    [leemte] = [b for b in zonder.blokken if b.soort == "leemte"]
    assert "boven de grens van 4 stukken" in leemte.tekst and ARRESTEN[-1] in leemte.tekst
    assert "klopte" not in leemte.tekst


def test_de_grens_na_een_rapport():
    def met(n: int, **extra):
        return {"subagenten": [{"uitkomst": "klaar", "rapport": True, "stukken": [[f"s{i}", ""] for i in range(n)]}],
                **extra}
    assert sub.stukkengrens(met(3)) is None, "binnen de gewone grens verandert niets"
    assert sub.stukkengrens(met(7)) == 7
    assert sub.stukkengrens(met(25)) == extern.MAX_STUKKEN_RAPPORT
    assert sub.stukkengrens(met(7, opdracht={"doel": "x"})) is None, "een subagent zelf niet"
    assert sub.stukkengrens({"subagenten": [{"uitkomst": "gestopt", "stukken": [[f"s{i}", ""] for i in range(7)]}]}) is None


def test_de_leemte_noemt_de_reden():
    grens = extern.boven_grens(["HR 1", "HR 2"], 4)
    assert extern.niet_getoond_tekst([grens]) == ("2 stukken boven de grens van 4 stukken per antwoord niet als citaat "
                                                  "getoond: HR 1 en HR 2.")
    gemengd = extern.niet_getoond_tekst([grens, "HR 3: alinea 9 is niet opgehaald."])
    assert "boven de grens" in gemengd and "Een aanwijzing in een bron naast de wet klopte niet" in gemengd
    assert "opgehaald" not in gemengd, "geen melding voor het model in het antwoord"
    assert extern.niet_getoond_tekst([extern.boven_alineagrens(48)]) == (
        "Alleen de eerste 48 aanwijzingen in een bron naast de wet zijn getoond.")
