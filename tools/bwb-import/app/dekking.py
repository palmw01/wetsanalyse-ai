"""De importpoort op de dekkingsmeting: `Stand`, `poortbesluit` en `meet` (offline door de writer).

De meting zelf – `bron_tekens`, `Dekking`, `STANDAARD_DREMPEL` – staat in `bronmodel.bwb.dekking`, zodat de
connector `wetgeving_live` (graph-qa) met dezelfde maat weigert als de importer.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from bronmodel.bwb.dekking import STANDAARD_DREMPEL, Dekking, bron_tekens

__all__ = ["STANDAARD_DREMPEL", "Dekking", "Poortbesluit", "Stand", "bron_tekens", "meet", "poortbesluit"]


@dataclass(frozen=True)
class Stand:
    """Wat er nu van een regeling in de graaf staat. Nul tekens = er staat niets."""

    tekens: int = 0
    wti: bool = False


@dataclass(frozen=True)
class Poortbesluit:
    """Mag deze graph de bestaande vervangen, en is er iets te melden? `reden` leeg = niets."""

    schrijven: bool
    reden: str | None = None


def poortbesluit(
    dekking: Dekking,
    stand: Stand,
    *,
    drempel: float,
    wti_mislukt: bool = False,
    overgeslagen: Sequence[str] = (),
) -> Poortbesluit:
    """Beslis vóór de PUT, want een named-graph PUT vervangt alles en een controle erna is te laat.

    De regel is **vervang nooit door minder**, en niet "bij een dip niet schrijven". GraphDB komt na
    een herstart leeg op; zou een dip dan de PUT tegenhouden, dan ontbreekt de hele regeling in
    plaats van een deel ervan. Tegen een lege graaf wint alles, behalve niets: een toestand zonder
    tekst is geen regeling en valt buiten dit besluit (`LegeToestand` in `app/main.py`).

    Een mislukte WTI vervangt geen verrijkte graph door een kale. Citeertitels en rechtsgebieden
    staan in dezelfde named graph, dus ze verdwijnen stil mee.

    Een mislukte bronmeting (`bron_tekens == 0`) is geen bewijs van een gat, maar ook geen bewijs
    van het tegendeel: dan telt alleen dat er niet minder mag komen te staan. `drempel == 0` zet
    alleen de dipregel uit.

    Structuur die de parser oversloeg weegt als een dip, ook bij volle dekking: de speling van de
    drempel is groot genoeg om een heel artikel te verbergen.
    """
    tekort = drempel > 0 and dekking.bron_tekens > 0 and dekking.verhouding < drempel
    onmeetbaar = dekking.bron_tekens <= 0
    probleem = dekking.regel()
    if overgeslagen:
        probleem = f"{probleem}; onbekende structuur overgeslagen: {', '.join(overgeslagen)}"
    if (tekort or onmeetbaar or overgeslagen) and dekking.graaf_tekens < stand.tekens:
        return Poortbesluit(
            False, f"{probleem}; de bestaande graph ({stand.tekens} tekens) blijft staan"
        )
    if wti_mislukt and stand.wti:
        return Poortbesluit(False, "WTI mislukt; de bestaande verrijkte graph blijft staan")
    if tekort or overgeslagen:
        return Poortbesluit(True, f"{probleem}; geschreven, er staat niets beters")
    if wti_mislukt:
        return Poortbesluit(True, "WTI mislukt; geschreven zonder verrijking")
    return Poortbesluit(True)


def meet(xml_pad: str | Path, geldig_vanaf: str | None = None) -> Dekking:
    """Parse en schrijf de wet offline, en leg het resultaat naast de bron.

    Importeert `parser`/`graphdb_writer` binnenin om een importcyclus te vermijden en om deze module
    bruikbaar te houden als alleen `bron_tekens` nodig is.
    """
    from bronmodel.bwb.parser import ToestandParser

    from .graphdb_writer import GraphDbWriter
    from .rdf_vocab import Vocab

    vocab = Vocab()
    wet = ToestandParser().parse(str(xml_pad))
    if geldig_vanaf:
        wet.geldig_vanaf = geldig_vanaf
    graaf, _ = GraphDbWriter(url="offline", repository="offline", vocab=vocab).build_graph(wet)
    graaf_tekens = sum(len(str(o)) for o in graaf.objects(None, vocab.ns.tekst))
    return Dekking(bwb_id=wet.bwb_id, bron_tekens=bron_tekens(xml_pad), graaf_tekens=graaf_tekens)


