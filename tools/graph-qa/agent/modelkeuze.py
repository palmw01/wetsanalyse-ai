"""De modelkeuzes: welk model een agentprofiel of stap van Lex draait, zoals de beheerder het koos.

Het model hoort op het agentprofiel, zoals `model:` bij een subagent van Claude Code (besluit gebruiker 15 nov 2026). De
beheerder kiest het in het beheer, zonder uitrol; de api bewaart het en geeft graph-qa per sleutel profiel en modelnaam
(`GET /v1/modelkeuzes`). De sleutels zijn die van `bronmodel.modelkeuzes`: `agent:<profiel>` per agentprofiel, `stap:<rol>`
per modelstap zonder profiel en `stap:subagent`. Lex neemt alleen de modelnaam over: endpoint en sleutel blijven die van
de straat.

- **Toegepast op één plek.** `llm_stap.aanroep` en `llm_stap.stroom` vragen `kies(sleutels, gevraagd)` vlak voor de
  aanroep, met de sleutels in volgorde van voorrang (`llm_stap._sleutels`): het agentprofiel van de aanroep
  (`kader["profiel_id"]`, gezet door de agentvorm), dan `stap:subagent` voor een subagent, dan `stap:<rol>`.
- **De voorrang.** Een keuze voor een van de sleutels wint (de eerste). Anders: vroeg de aanroeper het gewone model
  (`Settings.llm_model`), dan wordt dat het model van het standaardprofiel; een eigen env-knop (`LLM_MODEL_ROUTER`,
  `_OPHAAL`, `_LICHT`) blijft wat hij was. Zonder keuze en met een standaardprofiel gelijk aan `LLM_MODEL` verandert er
  dus niets.
- **Ververst per beurt, met een korte cache** (`ververs`, vanuit `api.main.start_beurt`, hoogstens elke `VERS_S`). Een
  onleesbare api houdt de vorige stand, en zonder stand geldt de env: een storing maakt van niemands keuze een fout.
- **Een model dat de straat niet heeft** (een 404, of een 400 die over het model gaat) valt terug op het gevraagde model,
  in dit proces voorgoed (`markeer_kapot`, `_KAPOT`), zodat een voorvoegsel niet tussen twee modellen wisselt. De
  logregel `modelprofiel_terugval` zegt het.
- **Wat de aanroep kreeg, staat op `model_aanroep`**: `modelprofiel` (de profielnaam, leeg als de env gold),
  `modelsleutel` (de sleutel die besliste) en `modelbron` (`keuze`, `standaard`, `env` of `terugval`).
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("graph_qa.modelkeuze")

#: Hoe lang een gelezen stand geldt. Een wijziging in het beheer is er dus binnen een minuut, bij de volgende beurt.
VERS_S = 60.0
#: Een beurt wacht hoogstens zo lang op de api; daarna geldt de vorige stand.
TIMEOUT_S = 3.0


@dataclass(frozen=True)
class Stand:
    #: `Settings.llm_model` op het moment van lezen: het model dat "de standaard" heet bij de aanroeper.
    basis: str = ""
    standaard: tuple[str, str] | None = None          # (profiel, model)
    #: Alleen wat de beheerder koos, per sleutel (`agent:<profiel>`, `stap:<rol>`).
    keuzes: dict[str, tuple[str, str]] = field(default_factory=dict)


_STAND: Stand | None = None
#: Wanneer de api het laatst gevraagd is, ook als dat mislukte: een api die weg is kost niet elke beurt `TIMEOUT_S`.
_GEPROBEERD: float | None = None
_KAPOT: set[str] = set()
_LOCK = threading.Lock()


def stand() -> Stand | None:
    return _STAND


def zet(nieuw: Stand | None) -> None:
    """De stand zetten (de api-lezer, en tests). `None` wist hem: dan geldt de env."""
    global _STAND
    with _LOCK:
        _STAND = nieuw


def vergeet() -> None:
    """Alles terug naar de env (tests)."""
    global _GEPROBEERD
    zet(None)
    _GEPROBEERD = None
    _KAPOT.clear()


def uit_antwoord(antwoord: dict[str, Any], basis: str) -> Stand:
    def keuze(w: Any) -> tuple[str, str] | None:
        if isinstance(w, dict) and isinstance(w.get("model"), str) and w["model"].startswith("claude-"):
            return str(w.get("profiel") or ""), w["model"]
        return None

    keuzes = {str(s): k for s, w in (antwoord.get("keuzes") or {}).items()
              if isinstance(w, dict) and w.get("bron") == "keuze" and (k := keuze(w))}
    return Stand(basis=basis, standaard=keuze(antwoord.get("standaard")), keuzes=keuzes)


def kies(sleutels: Sequence[str], gevraagd: str) -> tuple[str, dict[str, str]]:
    """(het model voor deze aanroep, de velden voor de logregel). De eerste sleutel met een keuze wint. Zonder stand:
    het gevraagde model, bron `env`."""
    s = _STAND
    if s is None:
        return gevraagd, {"modelbron": "env"}
    for sleutel in sleutels:
        if (k := s.keuzes.get(sleutel)) and k[1] not in _KAPOT:
            return k[1], {"modelprofiel": k[0], "modelsleutel": sleutel, "modelbron": "keuze"}
    if s.standaard and gevraagd == s.basis and s.standaard[1] not in _KAPOT:
        return s.standaard[1], {"modelprofiel": s.standaard[0], "modelbron": "standaard"}
    return gevraagd, {"modelbron": "env"}


def model_voor(sleutels: Sequence[str], gevraagd: str) -> str:
    """Het model dat deze aanroep nu krijgt: voor de herkomst (de annotatierun, het element), die het echte model noemt."""
    return kies(sleutels, gevraagd)[0]


def is_modelfout(fout: BaseException) -> bool:
    """Een fout die zegt dat de straat dit model niet heeft: een 404, of een 400 die het model noemt."""
    status = getattr(fout, "status_code", None)
    return status == 404 or (status == 400 and "model" in str(fout).lower())


def markeer_kapot(model: str, naar: str, sleutel: str, fout: BaseException) -> None:
    _KAPOT.add(model)
    logger.warning("modelprofiel_terugval", extra={"categorie": "technisch", "model": model, "naar": naar,
                                                    "modelsleutel": sleutel,
                                                    "http_status": getattr(fout, "status_code", None)})


async def ververs(settings: Any, *, nu: float | None = None) -> None:
    """Lees de stand bij de api als hij ouder is dan `VERS_S`. Gooit nooit."""
    if not getattr(settings, "legt_zelf_vast", False):
        return
    global _GEPROBEERD
    moment = time.monotonic() if nu is None else nu
    if _GEPROBEERD is not None and moment - _GEPROBEERD < VERS_S:
        return
    _GEPROBEERD = moment
    import asyncio

    from .wetsanalyse_api import WetsanalyseApi

    api = WetsanalyseApi(settings, "")
    try:
        antwoord = await asyncio.wait_for(api.modelkeuzes(), TIMEOUT_S)
        nieuw = uit_antwoord(antwoord, settings.llm_model)
        if nieuw != _STAND:
            logger.info("modelkeuzes", extra={"categorie": "technisch",
                                              "standaard": nieuw.standaard[1] if nieuw.standaard else "",
                                              "keuzes": {k: m for k, (_, m) in sorted(nieuw.keuzes.items())}})
        zet(nieuw)
    except Exception:  # noqa: BLE001 – een storing laat de vorige stand (of de env) staan
        logger.warning("modelkeuzes niet gelezen; de vorige stand of de env geldt",
                       extra={"categorie": "technisch"}, exc_info=True)
    finally:
        await api.aclose()
