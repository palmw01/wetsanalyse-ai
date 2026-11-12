"""Een wijziging van de methode voorstellen vanuit de werkplek (ADR-014 §4, C7): een concept-PR, geen directe wijziging.

Besluit van de gebruiker (12 nov 2026): een wijziging gaat via de PR als poort, niet via een overlay. Een beheerder met
2FA bewerkt een methodesectie. De api toetst die met dezelfde validator als de generator
(`bronmodel.methodesectie`) en opent op deze repo een **concept-PR**. Actief wordt de wijziging pas na review, de poort,
de merge en de uitrol, dus er is nooit een tweede waarheid naast het image.

Alleen op acceptatie: de vlag `CATALOGUS_VOORSTELLEN` staat standaard uit (`main.bicep:catalogusVoorstellen`, met een
poort-guard), en zonder `GITHUB_PR_TOKEN` en `GITHUB_REPO` gebeurt er niets. Het token heeft alleen schrijfrecht op deze
ene repo (contents en pull requests).
"""
from __future__ import annotations

import base64
import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx
from bronmodel.methodesectie import SECTIE_ID, SectieFout, lees_sectie, vervang_sectie
from pydantic import BaseModel, Field

from .config import get_settings

logger = logging.getLogger(__name__)

API = "https://api.github.com"
BASIS = "master"
#: Alleen methodetekst in een skill mag een voorstel worden: een reference van een skill, geen code of configuratie.
PAD = re.compile(r"\.claude/skills/[a-z][a-z0-9-]*/references/[a-z0-9-]+\.md")
TIJDGRENS_S = 20.0
#: Alleen voor tests: een vervangend transport voor de GitHub-API (httpx.MockTransport).
_TRANSPORT: httpx.AsyncBaseTransport | None = None


class VoorstelIn(BaseModel):
    onderdeel_id: str = Field(pattern=r"^[a-z]+/[a-z0-9_.-]+$", max_length=120)
    bestand: str = Field(max_length=200)
    sectie: str = Field(max_length=60)
    tekst: str = Field(min_length=1, max_length=8000)
    toelichting: str = Field(default="", max_length=2000)


class VoorstelUit(BaseModel):
    pr_url: str
    branch: str
    pr_nummer: int


class VoorstelFout(Exception):
    """Een voorstel dat niet kan: `status` is de HTTP-status voor de werkplek, `detail` een zin voor de beheerder."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status, self.detail = status, detail


@dataclass(frozen=True)
class Stand:
    aan: bool
    reden: str = ""


def stand() -> Stand:
    s = get_settings()
    if not s.catalogus_voorstellen:
        return Stand(False, "Voorstellen vanuit de werkplek staan in deze omgeving uit.")
    if not s.github_pr_token or not s.github_repo:
        return Stand(False, "Voorstellen staan aan, maar het token of de repo voor de pull request ontbreekt.")
    return Stand(True)


def _toets(v: VoorstelIn) -> None:
    if not PAD.fullmatch(v.bestand):
        raise VoorstelFout(422, "Alleen methodetekst in een skill (references/*.md) kan een voorstel worden.")
    if not SECTIE_ID.fullmatch(v.sectie):
        raise VoorstelFout(422, f"Ongeldig sectie-ID: {v.sectie}")


def _branchnaam(v: VoorstelIn, nieuw: str) -> str:
    kort = hashlib.sha256(f"{v.bestand}\n{v.sectie}\n{nieuw}".encode()).hexdigest()[:10]
    return f"claude/catalogus-voorstel-{v.sectie}-{kort}"


def _pr_tekst(v: VoorstelIn, door: str, oud: str, nieuw: str) -> str:
    return "\n".join([
        f"Voorstel uit de werkplek (*Werkwijze van Lex*), door **{door}**, voor `{v.onderdeel_id}`.",
        "",
        f"- Bestand: `{v.bestand}`",
        f"- Sectie: `{v.sectie}`",
        "",
        "**Toelichting van de beheerder**",
        "",
        v.toelichting.strip() or "_geen_",
        "",
        "**Tekst nu**",
        "",
        "```text", oud, "```",
        "",
        "**Voorgestelde tekst**",
        "",
        "```text", nieuw, "```",
        "",
        "**Voor de reviewer**",
        "",
        "- Deze tekst gaat letterlijk als methodetekst naar Lex: de wijziging verandert zijn gedrag. Meet volgens ADR-010",
        "  voor je merget, en leg de keuze vast in het beslisregister van de skill.",
        "- Licentie: is dit eigen tekst, of letterlijk uit een bron die dat toestaat (`lex_letterlijk: \"ja\"` met",
        "  `BRON.md`)? Het boek en de BRM-readers mogen niet letterlijk in deze publieke repo.",
        "- Draai `uv run python scripts/genereer_jas_klassen.py` in `tools/graph-qa` en commit `agent/methodepakket.py`.",
        "",
        "Dit is een concept-PR: er verandert niets in een omgeving tot de PR gemerged en uitgerold is.",
    ])


async def dien_in(v: VoorstelIn, door: str, *, transport: httpx.AsyncBaseTransport | None = None) -> VoorstelUit:
    """Haal het bestand van `master`, vervang de sectie, en open een concept-PR op een eigen branch."""
    st = stand()
    if not st.aan:
        raise VoorstelFout(404, st.reden)
    _toets(v)
    s = get_settings()
    kop = {"Authorization": f"Bearer {s.github_pr_token}", "Accept": "application/vnd.github+json",
           "X-GitHub-Api-Version": "2022-11-28"}
    repo = s.github_repo
    async with httpx.AsyncClient(base_url=API, headers=kop, timeout=TIJDGRENS_S, transport=transport or _TRANSPORT) as c:
        r = await c.get(f"/repos/{repo}/contents/{v.bestand}", params={"ref": BASIS})
        if r.status_code == 404:
            raise VoorstelFout(404, f"{v.bestand} bestaat niet op {BASIS}.")
        _ok(r)
        bestand: dict[str, Any] = r.json()
        tekst = base64.b64decode(bestand["content"]).decode("utf-8")
        try:
            oud = lees_sectie(tekst, v.sectie)
            nieuw_bestand = vervang_sectie(tekst, v.sectie, v.tekst)
            nieuw = lees_sectie(nieuw_bestand, v.sectie)
        except SectieFout as e:
            raise VoorstelFout(422, str(e)) from e
        if nieuw == oud:
            raise VoorstelFout(409, "De voorgestelde tekst is gelijk aan de tekst nu.")

        branch = _branchnaam(v, nieuw)
        ref = await c.get(f"/repos/{repo}/git/ref/heads/{BASIS}")
        _ok(ref)
        maak = await c.post(f"/repos/{repo}/git/refs",
                            json={"ref": f"refs/heads/{branch}", "sha": ref.json()["object"]["sha"]})
        if maak.status_code == 422:
            raise VoorstelFout(409, "Precies dit voorstel staat al open.")
        _ok(maak)
        put = await c.put(f"/repos/{repo}/contents/{v.bestand}", json={
            "message": f"skill: voorstel voor sectie {v.sectie} ({v.onderdeel_id})\n\nVoorgesteld door {door} vanuit de werkplek.",
            "content": base64.b64encode(nieuw_bestand.encode("utf-8")).decode("ascii"),
            "sha": bestand["sha"], "branch": branch})
        _ok(put)
        pr = await c.post(f"/repos/{repo}/pulls", json={
            "title": f"skill: voorstel voor de methodesectie '{v.sectie}'", "head": branch, "base": BASIS,
            "body": _pr_tekst(v, door, oud, nieuw), "draft": True})
        _ok(pr)
        uit = pr.json()
    logger.info("catalogusvoorstel ingediend", extra={"onderdeel": v.onderdeel_id, "sectie": v.sectie,
                                                    "door": door, "pr": uit.get("number")})
    return VoorstelUit(pr_url=uit["html_url"], branch=branch, pr_nummer=uit["number"])


def _ok(r: httpx.Response) -> None:
    if r.status_code >= 400:
        logger.warning("github_verzoek_mislukt", extra={"status": r.status_code, "pad": r.request.url.path})
        raise VoorstelFout(502, f"GitHub weigerde het verzoek ({r.status_code}). Probeer het later opnieuw.")
