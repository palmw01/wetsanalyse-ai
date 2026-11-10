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
from agent.tools.begrip_tools import AFGELEIDE_TOOL_NAMEN
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


# De bronconnectors (ADR-013) lezen niet uit de graaf; hun contract toetst onderaan dezelfde harnas, met een nepbron.
GRAAFTOOLS = [t["name"] for t in tools.TOOLS if t["name"] not in AFGELEIDE_TOOL_NAMEN | tools.CONNECTOR_TOOLS]
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


@pytest.mark.parametrize("query", [
    'SELECT ?t WHERE { ?s ?p ?o . BIND("verzonnen wettekst" AS ?t) } LIMIT 5',
    'SELECT ?t WHERE { VALUES ?t { "verzonnen wettekst" } } LIMIT 5',
    'SELECT (CONCAT("verzonnen", "") AS ?t) WHERE { ?s ?p ?o } LIMIT 5',
    'SELECT ?t WHERE { ?s ?p ?o } GROUP BY (CONCAT("x", STR(?s)) AS ?t) LIMIT 5',
    'SELECT ?t WHERE { { SELECT (STR(?s) AS ?t) WHERE { ?s ?p ?o } } } LIMIT 5',
    'SELECT ?t WHERE { BIND(\\u0022verzonnen\\u0022 AS ?t) } LIMIT 5',
])
def test_raw_sparql_bedenkt_geen_waarden(query):
    from agent.resultaat import is_foutresultaat

    data = is_foutresultaat(_aanroep("raw_sparql", {"query": query}, WorstCaseGraaf()))
    assert data and data["reden"] == "eigen_waarden"


@pytest.mark.parametrize("query", [
    "SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE { ?s ?p ?o } LIMIT 5",
    "SELECT ?p (COUNT(*) AS ?n) (MIN(?o) AS ?eerste) WHERE { ?s ?p ?o } GROUP BY ?p LIMIT 5",
    "SELECT ?s WHERE { VALUES ?s { <urn:a> <urn:b> } ?s ?p ?o } LIMIT 5",
    'SELECT ?s WHERE { ?s ?p ?o . FILTER(CONTAINS(STR(?o), "als ?x")) } LIMIT 5',
    'SELECT ?s WHERE { ?s <urn:nummer> "25" } LIMIT 5',
])
def test_raw_sparql_laat_terechte_query_door(query):
    assert is_contract(_aanroep("raw_sparql", {"query": query}, WorstCaseGraaf())) is not None


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



# ── De bronconnectors (ADR-013): hetzelfde contract, tegen een nepbron per connector ──────────────────────────
#
# Een connectortool viel eerst buiten deze harnas, en daardoor heette een dossier van meer dan 300 stukken volledig
# na de eerste 300. Elke connector krijgt hier een nepbron die zich gedraagt als zijn dienst (paginering, totaal) en
# argumenten per tool; elke pagina haalt het contract en alle pagina's samen zijn precies de dataset.

from agent.adapters.sru_kamerstukken import Document, Record  # noqa: E402
from bronmodel.connectors import CONNECTORS  # noqa: E402


class NepSru:
    """De zoekdienst van KOOP: `n` stukken in één dossier, startRecord/maximumRecords zoals de dienst, en een document
    met `alineas` lange alinea's."""

    def __init__(self, n: int, alineas: int = 400, tabel: int = 0) -> None:
        # Met de metadata zoals KOOP ze levert, op het ruimst: een lange eigen titel, drie indieners, meer dossiers, en
        # elk vijfde stuk onopgemaakt met alleen een PDF en later gepubliceerd. Zo telt de begroting de echte rijen.
        def onopgemaakt(i: int) -> bool:
            return i > 1 and i % 5 == 0
        self.records = [Record(id=f"kst-99001-{i}", titel=f"Wet x; Stuk {i}", datum="2026-01-02",
                               gepubliceerd="2026-02-20" if onopgemaakt(i) else "2026-01-02",
                               vergaderjaar="2025-2026", dossiers=("99001", "99002", "99003") if i % 3 == 0 else ("99001",),
                               ondernummer=str(i), soort="Brief regering", documenttitel=f"Stuk {i} " + _LANG[:140],
                               dossiertitel="Wet x", kamer="Tweede Kamer der Staten-Generaal",
                               indieners=("A.B. de Vries", "C.D. Jansen", "E.F. van den Berg") if i % 2 else (),
                               documentstatus="Onopgemaakt" if onopgemaakt(i) else "Opgemaakt na onopgemaakt",
                               xml_url="" if onopgemaakt(i) else f"https://repository.overheid.nl/x/kst-99001-{i}.xml",
                               pdf_url=f"https://repository.overheid.nl/x/kst-99001-{i}.pdf") for i in range(1, n + 1)]
        als = "".join(f"<al>{i}. {_LANG[:1500]}</al>" for i in range(alineas))
        # Een CALS-tabel zoals KOOP ze schrijft: `tabel` rijen van vier kolommen, met een kop.
        rij = lambda i: "<row>" + "".join(f"<entry colname='c{k}'><al>{i}.{k} {_LANG[:60]}</al></entry>"
                                          for k in range(4)) + "</row>"
        tab = (f"<table><title>Tabel 1</title><tgroup cols='4'>" + "".join(f"<colspec colname='c{k}'/>" for k in range(4))
               + "<thead>" + rij("kop") + "</thead><tbody>" + "".join(rij(i) for i in range(tabel)) + "</tbody></tgroup></table>"
               if tabel else "")
        self.xml = (f"<kamerstuk><stuk><titel>MEMORIE VAN TOELICHTING</titel><divisie><kop><titel>Deel</titel></kop>"
                    f"{als}{tab}</divisie></stuk></kamerstuk>").encode()

    def zoek(self, cql, *, start=1, maximum=50):
        return len(self.records), self.records[start - 1:start - 1 + maximum]

    def document(self, ident):
        rec = next((r for r in self.records if r.id == ident), None)
        return Document(ident, self.xml, "h", record=rec)


class NepRechtspraak:
    """LiDO en de Rechtspraak: `n` uitspraken bij een artikel, verspreid over drie versies en met de langste titels die
    LiDO geeft, en een uitspraak met `alineas` lange alinea's."""

    def __init__(self, n: int, alineas: int = 400) -> None:
        from agent.adapters.lido_rechtspraak import Link
        versies = tuple(f"http://linkeddata.overheid.nl/terms/bwb/id/BWBR0004770/1/{j}-01-01/{j}-01-01"
                        for j in (2026, 2016, 2010))
        gerechten = ("Gerechtshof 's-Hertogenbosch", "Rechtbank Zeeland-West-Brabant", "Hoge Raad")
        codes = ("GHSHE", "RBZWB", "HR")
        self.links = tuple(Link(f"ECLI:NL:{codes[i % 3]}:2020:{i}",
                                f"ECLI:NL:{codes[i % 3]}:2020:{i} - {gerechten[i % 3]}, {(i % 28) + 1:02d}-0{(i % 9) + 1}-2020"
                                f" / {i}/0{i}, {i}/1{i} en {i}/2{i}", "Door computer herkende referentie", versies[i % 3])
                           for i in range(1, n + 1))
        self.versies = versies
        paras = "".join(f"<para>{i}. {_LANG[:1500]}</para>" for i in range(alineas))
        self.xml = ('<open-rechtspraak xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
                    'xmlns:dcterms="http://purl.org/dc/terms/" xmlns="http://www.rechtspraak.nl/schema/rechtspraak-1.0">'
                    '<rdf:RDF><rdf:Description><dcterms:identifier>ECLI:NL:HR:2020:1</dcterms:identifier>'
                    '<dcterms:date>2020-01-02</dcterms:date><dcterms:creator>Hoge Raad</dcterms:creator>'
                    '<dcterms:type>Uitspraak</dcterms:type></rdf:Description></rdf:RDF>'
                    f'<uitspraak><section><title>Beoordeling</title>{paras}</section></uitspraak></open-rechtspraak>').encode()

    def koppelingen(self, bwb_id, artikel, jci=""):
        from agent.adapters.lido_rechtspraak import Koppelingen
        return Koppelingen(self.links, self.versies, (), "ref", {})

    def document(self, ecli):
        from agent.adapters.lido_rechtspraak import Document as Uitspraak
        return Uitspraak(ecli, self.xml, "h", "2020-02-01")


#: Per connector: een nepbron per omvang, en per tool de argumenten en de omvang van de dataset die terug moet komen.
NEPBRONNEN = {"kamerstukken": NepSru, "rechtspraak": NepRechtspraak}
CONNECTOR_ARGS: dict[str, list[tuple[dict, str]]] = {
    "zoek_kamerstukken": [({"dossier": "99001"}, "dossier"), ({"woorden": "Invorderingswet"}, "dossier"),
                          ({"dossier": "99001", "woorden": "stuk"}, "dossier")],
    "get_kamerstuk": [({"id": "kst-99001-1"}, "alineas")],
    "zoek_uitspraken": [({"bwb_id": "BWBR0004770", "artikel": "9"}, "dossier"),
                        ({"bwb_id": "BWBR0004770", "artikel": "9", "volgorde": "oudste", "aantal": 25}, "dossier")],
    "get_uitspraak": [({"id": "ECLI:NL:HR:2020:1"}, "alineas")],
}
OMVANGEN = (1, 40, 300, 301, 1000, 1001, 1200)


def test_elke_connector_heeft_een_nepbron_en_elke_connectortool_argumenten():
    assert set(NEPBRONNEN) == set(CONNECTORS), "voeg een nepbron toe voor de nieuwe connector"
    assert set(CONNECTOR_ARGS) == set(tools.CONNECTOR_TOOLS), "voeg de nieuwe connectortool toe aan CONNECTOR_ARGS"


#: Wat een rij of een stuk mag dragen naast de metadata: de vindplaats en, bij een gelezen stuk, de versie.
VINDPLAATS_SLEUTELS = {"id", "label", "link", "bron_hash", "gevalideerd"}


@pytest.mark.parametrize("naam,args,soort", [(n, a, s) for n, lijst in CONNECTOR_ARGS.items() for a, s in lijst])
def test_rijen_en_stuk_dragen_de_metadatasleutels(naam: str, args: dict, soort: str):
    """Elke connector levert zijn metadata in de vaste sleutels (`METADATA_SLEUTELS`), en alleen die hij beschrijft: dan
    vult dezelfde code de lijst, de kop van een gelezen stuk en de werkplek. De rijen van een leestool zijn passages en
    vallen erbuiten; het stuk erboven niet."""
    from bronmodel.connectors import METADATA_SLEUTELS

    c = CONNECTORS[_connector(naam)]
    beschreven = {v.sleutel for v in c.metadata} | VINDPLAATS_SLEUTELS
    assert beschreven - VINDPLAATS_SLEUTELS <= set(METADATA_SLEUTELS)
    data = json.loads(tools.dispatch(naam, None, args, make_settings(**{f"connector_{c.naam}": True}),
                                     **{c.naam: NEPBRONNEN[c.naam](40, alineas=3)}))
    assert data["status"] == "ok", data
    if naam == c.leestool:
        assert set(data["stuk"]) <= beschreven, f"{naam}: stuk met {set(data['stuk']) - beschreven}"
        assert {"datum", "label"} <= set(data["stuk"])
    else:
        for rij in data["resultaten"]:
            assert set(rij) <= beschreven, f"{naam}: rij met {set(rij) - beschreven}"
            assert {"id", "label", "datum"} <= set(rij)


def _connector(naam: str) -> str:
    return next(c.naam for c in CONNECTORS.values() if naam in c.tools)


@pytest.mark.parametrize("omvang", OMVANGEN)
@pytest.mark.parametrize("naam,args,soort", [(n, a, s) for n, lijst in CONNECTOR_ARGS.items() for a, s in lijst])
def test_contract_van_een_connectortool(naam: str, args: dict, soort: str, omvang: int):
    c = _connector(naam)
    bron = NEPBRONNEN[c](omvang, alineas=omvang)
    instellingen = make_settings(**{f"connector_{c}": True})

    def roep(n: str, a: dict) -> str:
        return tools.dispatch(n, None, a, instellingen, **{c: bron})

    uit = roep(naam, args)
    data = is_contract(uit)
    assert data is not None, f"{naam} levert geen contract: {uit[:200]}"
    gezien: list[str] = []
    for _ in range(400):
        _pagina_haalt_het_contract(naam, uit, data)
        if naam == CONNECTORS[c].leestool:
            # Het leestoolcontract: het stuk met zijn vindplaats en de hash van wat gelezen is (één lezing per blok).
            assert {"id", "label", "link", "bron_hash"} <= set(data["stuk"]), f"{naam}: stuk mist velden: {data['stuk']}"
        gezien += [json.dumps(r, sort_keys=True, ensure_ascii=False) for r in data["resultaten"]]
        if data["volledig"]:
            break
        uit = roep(data["vervolg"]["tool"], data["vervolg"]["args"])
        data = is_contract(uit)
        assert data is not None, f"{naam}: vervolg levert geen contract: {uit[:200]}"
    else:
        pytest.fail(f"{naam}: na 400 vervolgen nog niet volledig")
    assert len(gezien) == len(set(gezien)), f"{naam}: een rij kwam twee keer langs"
    assert len(gezien) == omvang, f"{naam}: {len(gezien)} van de {omvang} kwamen langs"



@pytest.mark.parametrize("rijen", [1, 40, 400])
def test_openen_van_een_connectortool_haalt_hetzelfde_contract(rijen: int):
    """Een tabel staat als één rij met `openen` (verdieping, geen onvolledigheid). Wat `openen` aanroept, haalt hetzelfde
    contract, en alle pagina's samen zijn precies de tabel: de kop met de kolommen en elke rij één keer."""
    bron = NepSru(1, alineas=3, tabel=rijen)
    instellingen = make_settings(connector_kamerstukken=True)

    def roep(n: str, a: dict) -> dict:
        uit = tools.dispatch(n, None, a, instellingen, kamerstukken=bron)
        data = is_contract(uit)
        assert data is not None, uit[:200]
        _pagina_haalt_het_contract(n, uit, data)
        return data

    pagina = roep("get_kamerstuk", {"id": "kst-99001-1"})
    [tabel] = [r for r in pagina["resultaten"] if r.get("soort") == "tabel"]
    assert pagina["volledig"] and tabel["omvang"].startswith(f"{rijen} rij")
    data, gezien = roep(tabel["openen"]["tool"], tabel["openen"]["args"]), []
    for _ in range(400):
        gezien += data["resultaten"]
        if data["volledig"]:
            break
        data = roep(data["vervolg"]["tool"], data["vervolg"]["args"])
    assert [r["soort"] for r in gezien] == ["tabel"] + ["tabelrij"] * rijen
    assert len(gezien[0]["cellen"]) == 4 and len({r["nr"] for r in gezien}) == len(gezien)
    assert gezien[-1]["nr"] == tabel["tot_nr"]
