"""Het modelprofiel per rol: welk model een rol van Lex draait, zoals de beheerder het koos.

De beheerder kiest per rol een modelprofiel (Instellingen → Beheer → Modelprofielen); de api bewaart de keuze en geeft
graph-qa alleen wat bruikbaar is (`GET /v1/modelrollen`: per rol het profiel en de modelnaam, en het standaardprofiel).
Lex neemt alleen de modelnaam over: endpoint en sleutel blijven die van de straat (besluit gebruiker 15 nov 2026). De
rollen zijn die van `bronmodel.modelrollen`: de waarden van `llm_stap.Rol` plus `subagent`.

- **Toegepast op één plek.** `llm_stap.aanroep` en `llm_stap.stroom` vragen `kies(sleutel, gevraagd)` vlak voor de
  aanroep, dus elke modelstap valt eronder zonder dat een aanroeper iets weet. De sleutel is de rol, of `subagent` voor
  een subagent (`kader["modelrol"]`, gezet door `agentvorm.Subagent`).
- **De voorrang.** Een keuze voor de rol wint. Anders: vroeg de aanroeper het gewone model (`Settings.llm_model`), dan
  wordt dat het model van het standaardprofiel; een eigen env-knop (`LLM_MODEL_ROUTER`, `_OPHAAL`, `_LICHT`) blijft wat
  hij was. Zonder keuze en met een standaardprofiel gelijk aan `LLM_MODEL` verandert er dus niets.
- **Ververst per beurt, met een korte cache** (`ververs`, vanuit `api.main.start_beurt`, hoogstens elke `VERS_S`). Een
  onleesbare api houdt de vorige stand, en zonder stand geldt de env: een storing maakt van niemands keuze een fout.
- **Een model dat de straat niet heeft** (een 404, of een 400 die over het model gaat) valt terug op het gevraagde model,
  in dit proces voorgoed (`markeer_kapot`, `_KAPOT`), zodat een voorvoegsel niet tussen twee modellen wisselt. De
  logregel `modelprofiel_terugval` zegt het.
- **Wat de rol kreeg, staat op `model_aanroep`**: `modelprofiel` (de profielnaam, leeg als de env gold) en `modelbron`
  (`rol`, `standaard` of `env`).
"""
from __future__ import annotations

import logging
import threading
import time
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
    rollen: dict[str, tuple[str, str]] = field(default_factory=dict)


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

    rollen = {str(r): k for r, w in (antwoord.get("rollen") or {}).items() if (k := keuze(w))}
    return Stand(basis=basis, standaard=keuze(antwoord.get("standaard")), rollen=rollen)


def kies(sleutel: str, gevraagd: str) -> tuple[str, dict[str, str]]:
    """(het model voor deze aanroep, de velden voor de logregel). Zonder stand: het gevraagde model, bron `env`."""
    s = _STAND
    if s is None:
        return gevraagd, {"modelbron": "env"}
    if (k := s.rollen.get(sleutel)) and k[1] not in _KAPOT:
        return k[1], {"modelprofiel": k[0], "modelbron": "rol"}
    if s.standaard and gevraagd == s.basis and s.standaard[1] not in _KAPOT:
        return s.standaard[1], {"modelprofiel": s.standaard[0], "modelbron": "standaard"}
    return gevraagd, {"modelbron": "env"}


def model_voor(sleutel: str, gevraagd: str) -> str:
    """Het model dat deze rol nu krijgt: voor de herkomst (de annotatierun, het element), die het echte model noemt."""
    return kies(sleutel, gevraagd)[0]


def is_modelfout(fout: BaseException) -> bool:
    """Een fout die zegt dat de straat dit model niet heeft: een 404, of een 400 die het model noemt."""
    status = getattr(fout, "status_code", None)
    return status == 404 or (status == 400 and "model" in str(fout).lower())


def markeer_kapot(model: str, naar: str, sleutel: str, fout: BaseException) -> None:
    _KAPOT.add(model)
    logger.warning("modelprofiel_terugval", extra={"categorie": "technisch", "model": model, "naar": naar,
                                                    "rol": sleutel,
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
        antwoord = await asyncio.wait_for(api.modelrollen(), TIMEOUT_S)
        nieuw = uit_antwoord(antwoord, settings.llm_model)
        if nieuw != _STAND:
            logger.info("modelrollen", extra={"categorie": "technisch",
                                              "standaard": nieuw.standaard[1] if nieuw.standaard else "",
                                              "rollen": {r: m for r, (_, m) in sorted(nieuw.rollen.items())}})
        zet(nieuw)
    except Exception:  # noqa: BLE001 – een storing laat de vorige stand (of de env) staan
        logger.warning("modelrollen niet gelezen; de vorige stand of de env geldt",
                       extra={"categorie": "technisch"}, exc_info=True)
    finally:
        await api.aclose()
