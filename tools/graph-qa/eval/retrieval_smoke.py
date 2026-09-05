"""Retrieval-smoke: raakt elke graaftool één keer de échte graaf, en komt er iets terug?

Waarom dit los van de gouden sets staat. De unit-tests draaien tegen een `FakeGraph`: die bewijst
dat een tool zijn bouwer aanroept en het resultaat doorgeeft, niet dat de query in de graaf iets
matcht. Precies dat gat liet `get_lid` maandenlang op `bwb:bevat` staan – een predicaat dat niet
bestaat – en `context()` zijn hele structuurtak verliezen. Beide waren syntactisch correct, beide
gaven nul rijen, geen van beide sloeg alarm.

`tests/test_predicaat_dekking.py` vangt de statische helft (een naam die de importer niet kent).
Deze smoke vangt de andere helft: een naam die wél bestaat maar in de praktijk niets oplevert,
omdat de relatie nooit wordt geschreven, de scope verkeerd staat of het pad niet klopt.

**Geen slaagcriterium op inhoud, wel op leegte.** Een tool die niets teruggeeft kan legitiem zijn
(niet elke wet heeft bijlagen), dus elke controle draagt een eigen verwachting: `hard` betekent
"hier hóórt data te staan, en niets betekent kapot"; `zacht` wordt gerapporteerd maar zakt niet.

De smoke praat rechtstreeks met de graaf – niet met een gedeployde graph-qa – en draait daarom in
de omgeving zelf (`azure-infra` → actie `eval`), niet op een werkplek.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import tools  # noqa: E402
from agent.adapters.graphdb_graph import make_graph  # noqa: E402
from agent.config import Settings  # noqa: E402
from agent.graph import queries  # noqa: E402
from agent.graph.results import parse_select  # noqa: E402

# Een regeling die er hoe dan ook is (Invorderingswet 1990) en een beleidsregel met divisies
# (Leidraad Invordering 2008). Die tweede is er expliciet bij omdat het decimale pad een eigen tak
# is die bij elke verwijzings- en contexttool anders loopt.
IW = "BWBR0004770"
LEIDRAAD = "BWBR0024096"
AWB = "BWBR0005537"
UITVOERINGSREGELING = "BWBR0004766"


@dataclass(frozen=True)
class Controle:
    """Eén tool-aanroep met een verwachting over het RESULTAAT, niet alleen over de leegte.

    `min_rijen`/`max_rijen` bestaan omdat "niet leeg" te weinig eist. Vijf van de zeven defecten die
    de eerste live-meting opleverde gaven gewoon rijen terug: `get_regeling_info` leverde er zes
    door een cartesisch product, `search_wetgeving` elke treffer dubbel door een superklasse-match.
    Een smoke die alleen op leegte let, keurt dat goed.
    """

    tool: str
    args: dict[str, Any]
    hard: bool = True
    min_rijen: int = 1
    max_rijen: int | None = None
    toelichting: str = ""


CONTROLES: tuple[Controle, ...] = (
    Controle("graph_schema", {}, toelichting="tellingen + vocabulaire + regelingen"),
    Controle("list_regelingen", {}, min_rijen=5),
    Controle("get_regeling_info", {"bwb_id": IW}, min_rijen=1, max_rijen=1,
             toelichting="precies ÉÉN rij; meer betekent een cartesisch product over "
                         "meerwaardige velden (afkortingen x ondertekenaars)"),
    Controle("search_wetgeving", {"query": "aansprakelijk", "limit": 5}, min_rijen=2, max_rijen=5,
             toelichting="max 5 want limit=5; meer betekent dat een knoop meerdere types matcht"),
    Controle("search_wetgeving", {"query": "bestuurder", "veld": "definieertBegrip", "limit": 5},
             hard=False, max_rijen=5,
             toelichting="veldgericht zoeken; leeg = het veld is niet geïndexeerd"),
    Controle("get_artikel", {"bwb_id": IW, "artikel": "36"}, min_rijen=8,
             toelichting="acht leden"),
    Controle("get_lid", {"bwb_id": IW, "artikel": "2", "lid": "1"},
             toelichting="definitielid – moet zijn ONDERDELEN meeleveren"),
    Controle("get_lid", {"bwb_id": AWB, "artikel": "5:2", "lid": "1"},
             toelichting="artikelnummer MET dubbele punt; 570 van de 572 Awb-artikelen hebben er "
                         "een, en die waren tot 5 sep 2026 onbereikbaar"),
    Controle("get_bepaling", {"bwb_id": LEIDRAAD, "nummer": "25.1"}, min_rijen=15,
             toelichting="container zonder eigen tekst; moet zijn 15 subdivisies noemen"),
    Controle("get_context", {"bwb_id": IW, "artikel": "36"}, min_rijen=10,
             toelichting="moet ook de bevat-door-tak vullen (was jarenlang leeg)"),
    Controle("get_context", {"bwb_id": LEIDRAAD, "nummer": "25.1"},
             toelichting="het divisie-pad; werkte vóór 4 sep 2026 helemaal niet"),
    Controle("follow_verwijzingen", {"bwb_id": IW, "artikel": "36"}, min_rijen=5,
             toelichting="verwijzingen hangen aan de LEDEN; op het artikel alleen waren het er 0"),
    Controle("verwijst_naar_deze", {"bwb_id": IW, "artikel": "36"}, min_rijen=20,
             toelichting="inkomende citaties op bepalingniveau"),
    Controle("referenced_by", {"bwb_id": IW, "artikel": "36"}, hard=False),
    Controle("inhoudsopgave", {"bwb_id": IW, "diepte": 1}, min_rijen=12, max_rijen=12,
             toelichting="de IW heeft twaalf hoofdstukken; méér rijen betekent type-inflatie "
                         "of een structuurdeel met meerdere ouders"),
    Controle("zoek_definitie", {"term": "bestuurder"},
             toelichting="bwb:definieertBegrip – nieuw ontsloten"),
    Controle("grondslagen", {"bwb_id": LEIDRAAD}, hard=False,
             toelichting="WTI-verrijking; leeg als BWB_IMPORT_WTI uit stond"),
    Controle("geldigheid", {"bwb_id": IW, "artikel": "36"}, max_rijen=3,
             toelichting="één bepaling; veel rijen betekent een cartesisch product"),
    Controle("bijlagen", {"bwb_id": AWB}, min_rijen=3,
             toelichting="de Awb heeft drie bijlagen; de IW geen – dáárom niet de IW"),
    Controle("bijlagen", {"bwb_id": UITVOERINGSREGELING, "nummer": "artikel 1cb"}, hard=False,
             toelichting="bijlage ZONDER nummer, alleen op label te vinden"),
    Controle("resolve_begrip", {"term": "invordering"}, hard=False,
             toelichting="SKOS-thesaurus; leeg als de WTI-import uit stond"),
)


def _rijen(resultaat: str) -> int:
    """Aantal datarijen in een SPARQL-TSV-antwoord; -1 als het geen tabel is."""
    try:
        return len(parse_select(resultaat))
    except Exception:  # noqa: BLE001 – de smoke mag nooit op zijn eigen parser stuklopen
        return -1


def draai(settings: Settings) -> tuple[list[dict[str, Any]], bool]:
    graph = make_graph(settings)
    uitkomsten: list[dict[str, Any]] = []
    geslaagd = True
    try:
        for c in CONTROLES:
            resultaat = tools.dispatch(c.tool, graph, dict(c.args), settings)
            fout = resultaat.startswith(f"Fout bij tool '{c.tool}'")
            rijen = _rijen(resultaat)
            oordeel = _beoordeel(c, resultaat, rijen, fout)
            geslaagd = geslaagd and oordeel["ok"]
            uitkomsten.append({"tool": c.tool, "args": c.args, "rijen": rijen, "hard": c.hard,
                               "toelichting": c.toelichting, **oordeel})
        uitkomsten.append(_structuurintegriteit(graph))
        geslaagd = geslaagd and uitkomsten[-1]["ok"]
    finally:
        graph.close()
    return uitkomsten, geslaagd


def _beoordeel(c: Controle, resultaat: str, rijen: int, fout: bool) -> dict[str, Any]:
    """Te weinig én te veel rijen zijn allebei een bevinding.

    "Niet leeg" is een te zwakke eis. Een cartesisch product over meerwaardige velden, of een
    knoop die door zijn superklassen meerdere keren matcht, levert méér rijen op dan er antwoorden
    zijn — en dat glipt door een leegte-controle heen. Beide defecten zaten er live in.
    """
    if fout:
        return {"ok": not c.hard, "fout": resultaat[:200], "reden": "tool gaf een fout"}
    if rijen < c.min_rijen:
        return {
            "ok": not c.hard,
            "fout": "",
            "reden": f"te weinig rijen: {rijen} < {c.min_rijen} verwacht",
        }
    if c.max_rijen is not None and rijen > c.max_rijen:
        # Te veel is ALTIJD hard: het is nooit een eigenschap van de data maar van de query.
        return {"ok": False, "fout": "", "reden": f"te veel rijen: {rijen} > {c.max_rijen}"}
    return {"ok": True, "fout": "", "reden": ""}


def _structuurintegriteit(graph: Any) -> dict[str, Any]:
    """Geen structuurdeel mag meer dan één ouder hebben.

    Dit is de guard op de IRI-collisie die op 4 sep 2026 aan het licht kwam: 16 van de 93 afdelingen
    en 5 van de 27 paragrafen vielen samen omdat hun sleutel alleen het laatste jci-segment droeg.
    Zo'n node draagt de titels, ouders én artikelen van meerdere afdelingen tegelijk — een verkeerde
    inhoudsopgave, en artikelen die aan de verkeerde afdeling hangen.

    Alleen tegen echte data te meten, vandaar hier en niet in de unit-tests.
    """
    sparql = queries.PREFIXES + f"""SELECT (COUNT(*) AS ?aantal) WHERE {{
  {{ SELECT ?s (COUNT(DISTINCT ?p) AS ?ouders) WHERE {{
      ?s a ?t .
      FILTER(?t IN (bwb:Hoofdstuk, bwb:Titeldeel, bwb:Afdeling, bwb:Paragraaf))
      FILTER(STRSTARTS(STR(?s), "{queries.NS}"))
      ?p {queries.BEVAT} ?s .
    }} GROUP BY ?s HAVING(COUNT(DISTINCT ?p) > 1) }}
}}"""
    try:
        rijen = parse_select(graph.sparql(sparql))
        aantal = int(rijen[0].get("aantal", "0")) if rijen else 0
    except Exception as exc:  # noqa: BLE001
        return {"tool": "structuurintegriteit", "args": {}, "rijen": -1, "hard": True,
                "ok": False, "fout": str(exc)[:200], "reden": "meting mislukt",
                "toelichting": "geen structuurdeel mag meer dan één ouder hebben"}
    return {
        "tool": "structuurintegriteit", "args": {}, "rijen": aantal, "hard": True,
        "ok": aantal == 0, "fout": "",
        "reden": "" if aantal == 0 else f"{aantal} structuurdelen met meer dan één ouder",
        "toelichting": "IRI-collisie: gelijk genummerde afdelingen/paragrafen zijn samengevallen",
    }


def rapporteer(uitkomsten: list[dict[str, Any]], geslaagd: bool) -> None:
    print("\n=== RETRIEVAL-SMOKE (elke graaftool één keer tegen de echte graaf) ===\n")
    print(f"{'':2} {'tool':22} {'rijen':>6}  argumenten")
    for u in uitkomsten:
        vlag = "ok" if u["ok"] else "XX"
        args = ", ".join(f"{k}={v}" for k, v in u["args"].items())
        print(f"{vlag:2} {u['tool']:22} {u['rijen']:>6}  {args}")
        if u["fout"]:
            print(f"      fout: {u['fout']}")
        if not u["ok"]:
            print(f"      {u.get('reden', 'onverwacht resultaat')}. {u['toelichting']}")
    hard = sum(1 for u in uitkomsten if u["hard"])
    print(f"\n{sum(1 for u in uitkomsten if u['ok'])}/{len(uitkomsten)} in orde "
          f"({hard} harde controles). Eindoordeel: {'GESLAAGD' if geslaagd else 'GEZAKT'}")
    print("\nEen lege HARDE controle betekent dat een tool syntactisch werkt maar niets matcht – "
          "dezelfde stille fout als bwb:bevat. Controleer het predicaat, de scope en het pad.")


def main() -> None:
    from eval.run_eval import _laad_env

    _laad_env()
    uitkomsten, geslaagd = draai(Settings.from_env())
    rapporteer(uitkomsten, geslaagd)
    sys.exit(0 if geslaagd else 1)


if __name__ == "__main__":
    main()
