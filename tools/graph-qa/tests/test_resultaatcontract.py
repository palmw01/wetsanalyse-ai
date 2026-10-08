"""Elke graaftool haalt het resultaatcontract (`agent/resultaat.py`), ook bij een worst-case graaf.

Een tool landt pas als hij:
- geldig contract-JSON levert (`status`, `volledig`, `aantal`, `resultaten`);
- binnen de begroting blijft, wat de graaf ook teruggeeft – begrenzen is zijn taak, niet die van de
  uitvoeringsgrens;
- bij `volledig: false` een `vervolg` noemt (en alleen dan), waarvan de argumenten geldig zijn tegen het
  schema van `vervolg.tool` – dat mag een andere tool zijn;
- elke `openen`-aanroep op een rij (verdieping, zoals een ingeklapt deel) geldig is tegen zijn tool;
- geen lege velden draagt, en `aantal` gelijk is aan het aantal resultaten;
- via `vervolg` de rest levert: geen rij twee keer, geen rij nooit – samen precies de dataset;
- bij paginering een deterministische ORDER BY gebruikt (anders schuift een rij tussen pagina's).

De graaf hieronder levert per query honderden rijen met lange waarden en respecteert LIMIT/OFFSET, zodat
paginering echt getoetst wordt en niet alleen de vorm.
"""
from __future__ import annotations

import json
import re

import pytest

from agent import tools
from agent.resultaat import BUDGET, is_contract
from agent.tools.annotatie_tools import ANNOTATIE_TOOL_NAMEN
from fakes import make_settings

IW = "BWBR0004770"
_RIJEN = 300
_LANG = "De ontvanger kan op verzoek uitstel van betaling verlenen onder door hem te stellen voorwaarden. " * 40

# Minimale geldige argumenten per graaftool.
ARGS: dict[str, dict] = {
    "search_wetgeving": {"query": "uitstel"},
    "zoek_opbouw": {"onderwerp": "invordering"},
    "overzicht_onderwerp": {"onderwerp": "invordering"},
    "semantic_search": {"query": "uitstel van betaling"},
    "get_artikel": {"bwb_id": IW, "artikel": "9"},
    "get_lid": {"bwb_id": IW, "artikel": "9", "lid": "1"},
    "get_bepaling": {"bwb_id": IW, "nummer": "9"},
    "list_regelingen": {},
    "get_regeling_info": {"bwb_id": IW},
    "follow_verwijzingen": {"bwb_id": IW, "artikel": "36"},
    "verwijst_naar_deze": {"bwb_id": IW, "artikel": "36"},
    "referenced_by": {"bwb_id": IW, "artikel": "36"},
    "inhoudsopgave": {"bwb_id": IW},
    "zoek_definitie": {"term": "bestuurder"},
    "grondslagen": {"bwb_id": IW},
    "geldigheid": {"bwb_id": IW, "artikel": "36"},
    "bijlagen": {"bwb_id": IW},
    "get_context": {"bwb_id": IW, "artikel": "36"},
    "resolve_begrip": {"term": "belasting"},
    "graph_schema": {},
    "raw_sparql": {"query": "SELECT ?s WHERE { ?s ?p ?o } ORDER BY ?s LIMIT 20"},
}


GRAAFTOOLS = [t["name"] for t in tools.TOOLS if t["name"] not in ANNOTATIE_TOOL_NAMEN]
# Gerangschikte lijsten: via `vervolg` moet de hele (fake) dataset langskomen.
PAGINEREND = {"search_wetgeving", "zoek_opbouw", "semantic_search", "verwijst_naar_deze", "zoek_definitie", "list_regelingen",
              "follow_verwijzingen", "referenced_by", "grondslagen", "get_context", "resolve_begrip"}


def test_elke_graaftool_heeft_testargumenten():
    assert set(GRAAFTOOLS) == set(ARGS), "voeg de nieuwe tool toe aan ARGS"


class WorstCaseGraaf:
    """Veel rijen, lange waarden, en LIMIT/OFFSET zoals GraphDB ze toepast."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def _waarde(self, var: str, i: int) -> str:
        if var == "niveau":
            return '"1"'
        if var == "ouder":
            return f'"urn:bwb:{IW}"'
        if var in {"deel", "node", "bron", "doel", "regeling", "iri", "s", "sub", "lid", "onderdeel"}:
            return f"<urn:bwb:{IW}:artikel:{i}>"
        if var in {"tekst", "nodetekst", "lidTekst", "subTekst"}:
            return json.dumps(_LANG)
        if var in {"soort"}:
            return '"Artikel"'
        if var in {"nummer"}:
            return f'"{i}"'
        if var in {"volgtOp"}:
            return f'"urn:bwb:{IW}:artikel:{i - 1}"' if i else ""
        return json.dumps(f"{var} {i} " * 8)

    def sparql(self, query: str) -> str:
        self.queries.append(query)
        m = re.search(r"SELECT\s+(?:DISTINCT\s+)?(.*?)\s+WHERE", query, re.S | re.I)
        # Gewone kolommen plus de `(EXPR AS ?x)`-kolommen, zoals GraphDB ze teruggeeft; de variabelen
        # binnen een expressie zijn geen kolom.
        kop = m.group(1) if m else "?s"
        zonder_expressies = re.sub(r"\((?:[^()]|\([^()]*\))*\)", " ", kop)
        variabelen = list(dict.fromkeys(
            re.findall(r"\?(\w+)", zonder_expressies) + re.findall(r"AS\s+\?(\w+)", kop)))
        limit = re.search(r"LIMIT\s+(\d+)", query)
        offset = re.search(r"OFFSET\s+(\d+)", query)
        start = int(offset.group(1)) if offset else 0
        eind = min(_RIJEN, start + int(limit.group(1))) if limit else _RIJEN
        kop = "\t".join(f"?{v}" for v in variabelen)
        rijen = ["\t".join(self._waarde(v, i) for v in variabelen) for i in range(start, eind)]
        return "\n".join([kop, *rijen]) + "\n"

    def semantic_search(self, query: str, limit: int = 10) -> str:
        n = min(_RIJEN, limit // 3)
        return "@prefix bwb: <urn:bwb-ns:> .\n\n" + "\n".join(
            f"<urn:bwb:{IW}:artikel:{i}> a bwb:Artikel, bwb:Citeerbaar ." for i in range(n))

    def initialize(self) -> dict:
        return {}

    def close(self) -> None:
        pass


def _geldig_tegen_schema(naam: str, args: dict) -> None:
    assert naam in {t["name"] for t in tools.TOOLS}, f"vervolg/openen noemt een onbekende tool: {naam}"
    schema = next(t for t in tools.TOOLS if t["name"] == naam)["input_schema"]
    props = schema["properties"]
    assert set(args) <= set(props), f"{naam}: vervolg noemt onbekende argumenten {set(args) - set(props)}"
    assert set(schema.get("required", [])) <= set(args), f"{naam}: vervolg mist verplichte argumenten"
    for k, v in args.items():
        soort = props[k].get("type")
        if soort == "integer":
            assert isinstance(v, int), f"{naam}.{k} moet een geheel getal zijn"
        elif soort == "string":
            assert isinstance(v, str), f"{naam}.{k} moet tekst zijn"


def _aanroep(naam: str, args: dict, graaf: WorstCaseGraaf) -> str:
    return tools.dispatch(naam, graaf, args, make_settings(similarity_index="bwb_similarity"))


@pytest.mark.parametrize("naam", GRAAFTOOLS)
def test_contract(naam: str):
    graaf = WorstCaseGraaf()
    uit = _aanroep(naam, ARGS[naam], graaf)
    data = is_contract(uit)
    assert data is not None, f"{naam} levert geen contract: {uit[:200]}"

    # Volg de vervolg-aanroepen: elke pagina haalt het contract, geen rij dubbel.
    gezien: set[str] = set()
    for _ in range(400):
        _pagina_haalt_het_contract(naam, uit, data)
        for rij in data["resultaten"]:
            sleutel = json.dumps(rij, sort_keys=True, ensure_ascii=False)
            assert sleutel not in gezien, f"{naam}: rij kwam twee keer langs: {sleutel[:120]}"
            gezien.add(sleutel)
        if data["volledig"]:
            break
        vervolg = data["vervolg"]
        uit = _aanroep(vervolg["tool"], vervolg["args"], graaf)
        data = is_contract(uit)
        assert data is not None, f"{naam}: vervolg levert geen contract: {uit[:200]}"
    else:
        pytest.fail(f"{naam}: na 400 vervolgen nog niet volledig")
    assert gezien, f"{naam}: geen enkele rij uit een graaf met {_RIJEN} rijen"
    if naam in PAGINEREND:
        assert len(gezien) == _RIJEN, f"{naam}: {len(gezien)} van de {_RIJEN} rijen kwamen langs"
    for q in graaf.queries:
        if re.search(r"\bOFFSET\b", q) or (naam in PAGINEREND and "LIMIT" in q):
            assert re.search(r"ORDER BY", q), f"{naam}: paginering zonder ORDER BY"


def _pagina_haalt_het_contract(naam: str, uit: str, data: dict) -> None:
    assert len(uit) <= BUDGET, f"{naam}: {len(uit)} tekens, begroting {BUDGET}"
    assert data["aantal"] == len(data["resultaten"]), f"{naam}: 'aantal' is niet len(resultaten)"
    assert ("vervolg" in data) is (not data["volledig"]), f"{naam}: vervolg hoort er te zijn als en alleen als volledig false is"
    if "vervolg" in data:
        _geldig_tegen_schema(data["vervolg"]["tool"], data["vervolg"]["args"])
    for rij in data["resultaten"]:
        assert all(v not in ("", None, [], {}) for v in rij.values()), f"{naam}: lege velden in {rij}"
        if "openen" in rij:
            _geldig_tegen_schema(rij["openen"]["tool"], rij["openen"]["args"])


def test_een_ondeelbare_eenheid_boven_de_begroting_wordt_een_fout_geen_inkorting():
    from agent.resultaat import is_foutresultaat

    class EenReuzenrij(WorstCaseGraaf):
        def sparql(self, query: str) -> str:
            self.queries.append(query)
            return "?bron\t?ankerTekst\n" + f"<urn:bwb:{IW}:artikel:1>\t" + json.dumps("x" * (BUDGET * 2)) + "\n"

    uit = _aanroep("verwijst_naar_deze", ARGS["verwijst_naar_deze"], EenReuzenrij())
    data = is_foutresultaat(uit)
    assert data is not None and data["reden"] == "ondeelbare_eenheid_te_groot", uit[:200]
    assert "x" * 100 not in uit, "geen ingekorte data in een foutresultaat"


def test_raw_sparql_is_streng_en_geeft_nooit_een_half_antwoord():
    from agent.resultaat import is_foutresultaat

    def reden(query: str, graaf=None) -> str:
        data = is_foutresultaat(_aanroep("raw_sparql", {"query": query}, graaf or WorstCaseGraaf()))
        return data["reden"] if data else ""

    assert reden("SELECT ?s WHERE { ?s ?p ?o }") == "limit_ontbreekt"
    assert reden("SELECT ?s WHERE { { SELECT ?s WHERE { ?s ?p ?o } LIMIT 5 } }") == "limit_ontbreekt", \
        "een LIMIT in een subquery begrenst het resultaat niet"
    assert reden("SELECT ?s WHERE { ?s ?p ?o } LIMIT 500") == "limit_te_hoog"
    assert reden("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o } LIMIT 5") == "alleen_select"
    # 200 rijen met lange waarden passen niet: een fout met de reden, geen ingekort antwoord.
    assert reden("SELECT ?tekst WHERE { ?s ?p ?tekst } ORDER BY ?s LIMIT 200") == "resultaat_te_groot"
    ok = is_contract(_aanroep("raw_sparql", {"query": "PREFIX bwb: <urn:bwb-ns:>\nSELECT ?s WHERE { ?s ?p ?o } "
                                                       "ORDER BY ?s LIMIT 5 OFFSET 10"}, WorstCaseGraaf()))
    assert ok is not None and ok["volledig"] is True and ok["aantal"] == 5
