"""Plugins van Lex: een methode die je per gesprek aan of uit zet, zoals een bron (plan docs/architectuur/plan-contenttoets.md).

Een plugin bundelt een skill, een agentprofiel, een sjabloon en een commando in de werkplek. Hij staat los van de
wetsanalyse: hij gebruikt alleen de brondata. Deze lijst is de enige bron; graph-qa, de api en de werkplek lezen hem.

Een plugin-skill staat niet in het vaste voorvoegsel van de centrale agent (`agent/skills.beschrijvingen` in graph-qa):
zo verandert er voor een gesprek zonder de plugin niets, ook niet aan de cache. De plugin werkt via zijn eigen route.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Plugin:
    naam: str
    label: str
    beschrijving: str
    #: De methode-skill onder `.claude/skills/`, met een eigen methoderol (`bronmodel.skill.EIGEN_ROLLEN`).
    skill: str
    #: Het agentprofiel onder `.claude/lex-agents/` dat het werk doet.
    profiel: str
    #: Het sjabloon waarmee dat profiel afrondt.
    sjabloon: str
    #: De actie op de beurt (`ChatRequest.actie`) en het commando in de werkplek.
    actie: str
    commando: str


CONTENTTOETS = Plugin(
    naam="contenttoets",
    label="Contenttoets",
    beschrijving="Toetst content, zoals een webtekst, op juistheid en volledigheid tegen de wet- en regelgeving in de kennisgraaf.",
    skill="contenttoets",
    profiel="contenttoets",
    sjabloon="antwoord_contenttoets",
    actie="contenttoets",
    commando="contenttoets",
)

PLUGINS: tuple[Plugin, ...] = (CONTENTTOETS,)
NAMEN: tuple[str, ...] = tuple(p.naam for p in PLUGINS)
#: De skills van een plugin: geen vaste methode van de centrale agent.
SKILLS: frozenset[str] = frozenset(p.skill for p in PLUGINS)


def plugin(naam: str) -> Plugin | None:
    return next((p for p in PLUGINS if p.naam == naam), None)
