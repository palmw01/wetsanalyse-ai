"""Bepalingen benoemen en opzoeken: een naam uit de echte boom (`_benoem`, `plek_uit_iri`) en de bepalingen die de
analist zelf noemde (`bepalingen_uit_tekst`). Zonder model."""
from __future__ import annotations

import re
from typing import Any, Callable

from .graph import queries
from .graph.results import parse_select
from .ports import GraphPort


def rijen(graph: GraphPort, query: str) -> list[dict[str, str]]:
    return parse_select(graph.sparql(query))


def bwb_van(iri: str) -> str:
    """De regeling van een bron-IRI; leeg buiten de namespace van de graaf."""
    rest = iri[len(queries.NS):] if iri.startswith(queries.NS) else ""
    return rest.split(":", 1)[0]


def plek_uit_iri(iri: str) -> str:
    """Een naam voor een bepaling waarvan de graaf geen label en de IRI geen vindplaats geeft – een wet-lokale
    divisie van een beleidsregel (`…:id:BWBR0024096%2FCirculaire.divisie26%2F…divisie26.3.9`): "divisie
    26.3.9", nooit de IRI zelf (die kwam anders in labels en in de afbakening van het dossier terecht). De
    tweeling van `plekNaam` in `frontend/lib/bronKandidaten.ts`."""
    from urllib.parse import unquote

    rest = re.sub(r"^urn:bwb:BWB[A-Z]\d+:?", "", iri)
    m = re.match(r"^id:(.+)$", rest)
    if m:
        delen = unquote(m.group(1)).split("/")
        # Een onderdeel (`…/Circulaire.divisie9/Tekst/Onderdeel._4`) heet naar zijn divisie: het volgnummer in
        # de IRI telt niet betrouwbaar, en een opsommingsteken heeft geen eigen nummer.
        if "Tekst" in delen:
            delen = delen[:delen.index("Tekst")]
        divisie = re.search(r"divisie([\d.]+[a-z]?)$", delen[-1], re.I) if delen else None
        return f"divisie {divisie.group(1)}" if divisie else (delen[-1] if len(delen) > 1 else rest)
    return rest or iri


def _benoem(graph: GraphPort, kandidaten: list[dict[str, Any]]) -> None:
    """"Artikel 30g, lid 2, onderdeel a – Algemene wet inzake rijksbelastingen" in plaats van het kale
    "Onderdeel a." uit de graaf; bij een divisie van een beleidsregel met haar titel: "Artikel 9.4 –
    Dagtekening aanslagbiljet – Leidraad Invordering 2008". De plek komt uit de graaf (`bwb:vindplaats`, de
    echte boom), anders uit de IRI (`bronmodel.vindplaats`, dezelfde regels als de bronnenlijst).

    Elke keer opnieuw uit de bron-IRI, nooit uit een label dat er al stond: `vind` benoemt kandidaten die
    `bepaling_opties` al benoemde, en dan kwam de regeling er twee keer achter. Een naam die niet te halen
    is, breekt niets."""
    from .overzicht import definitie_vindplaats
    from .plekken import plekken
    from .regelingnamen import regelingnamen

    namen = regelingnamen(graph, {k["bwb_id"] for k in kandidaten})
    graaf = plekken(graph, [k["bron_iri"] for k in kandidaten])
    for k in kandidaten:
        p = graaf.get(k["bron_iri"], {})
        plek = p.get("vindplaats") or definitie_vindplaats(k["bron_iri"]) or plek_uit_iri(k["bron_iri"])
        delen = [plek, p.get("titel", ""), namen.get(k["bwb_id"], "")]
        k["label"] = " – ".join(d for d in delen if d)


_NIEUW_ARTIKEL = re.compile(r"(?=\bart(?:ikel(?:en)?|\.)\s*\d)", re.I)


def bepalingen_uit_tekst(tekst: str, vind: Callable[[str], list[str]], regelingen: list[str]
                         ) -> list[dict[str, str]] | str:
    """Wat de analist zelf als keuze typte, ontleed tot verzoeken per artikel (en lid), die daarna in de graaf
    getoetst worden. Een tekst mag meer bepalingen in meer regelingen noemen ("artikel 9 lid 1 en 5
    Invorderingswet 1990 en artikel 4:86 Awb"): hij wordt geknipt vóór elk "artikel"/"art.", en elk stuk krijgt
    de regeling die het zelf noemt; anders de enige die de hele tekst noemt; anders de enige van het werkgebied.
    Geen artikel: een lege lijst; geen eenduidige regeling voor een stuk: de vraag om haar te noemen.

    `vind` geeft de regelingen die een tekst bij naam of afkorting noemt (`overzicht.regelingen_in_vraag`)."""
    from .aanwijzing import lees_aanwijzing
    from .werkgebied_intake import artikelen_in

    zoek = vind
    heel = zoek(tekst)
    stukken = [x.strip() for x in _NIEUW_ARTIKEL.split(tekst) if x.strip()]
    uit: list[dict[str, str]] = []
    for stuk in stukken:
        artikelen = artikelen_in(stuk)
        if not artikelen:
            continue
        eigen = zoek(stuk) if len(stukken) > 1 else heel
        bwb = eigen[0] if len(eigen) == 1 else heel[0] if not eigen and len(heel) == 1 \
            else regelingen[0] if not eigen and not heel and len(regelingen) == 1 else ""
        if not bwb:
            return ("Bij welke regeling hoort dat? Noem haar erbij, bijvoorbeeld ‘artikel 9 lid 2 Invorderingswet "
                    "1990’." if not eigen and not heel else
                    f"Ik weet niet bij welke regeling ‘{stuk[:80]}’ hoort; noem de regeling direct na het artikel.")
        leden = lees_aanwijzing(stuk).leden if len(artikelen) == 1 and re.search(r"\b(?:lid|leden)\b", stuk, re.I) else ()
        uit += [{"bwb_id": bwb, "artikel": artikelen[0], "lid": lid} for lid in leden] if leden \
            else [{"bwb_id": bwb, "artikel": a} for a in artikelen]
    # Twee keer dezelfde bepaling genoemd is één verzoek.
    return list({(v["bwb_id"], v["artikel"], v.get("lid", "")): v for v in uit}.values())
