"""
LLMPort-adapter voor Anthropic via Azure AI Foundry.

Hier zit de enige plek die de concrete Anthropic-client, de Azure-Foundry-details (base_url,
api-version) en de prompt-caching kent.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import anthropic

from ..config import Settings
from ..models import Verbruiksmeter
from ..ports import Systeem
from ..verzoekopbouw import opbouw

logger = logging.getLogger("graph_qa.llm")

# Onder deze lengte heeft cachen geen zin. Het minimum cachebare voorvoegsel is modelafhankelijk
# (1024 tokens op de sonnet-4.6-klasse); daaronder slaat de provider de cache stilzwijgend over —
# geen fout, alleen de duurdere write zonder ooit een hit. Nederlands tokeniseert op ~3,5 tekens per
# token, dus 4000 tekens ≈ 1150 tokens: net boven het minimum, bewust aan de veilige kant.
#
# De prompts van de classifier en de reviewer blijven hier meestal onder en verschillen per batch; in
# de meetmappen van de annotatieketen staat 0 cache-lees. Winst daar komt uit minder kandidaten.
_MIN_CACHE_TEKENS = 4000


class AnthropicLLM:
    """Dunne, blocking implementatie van LLMPort."""

    def __init__(self, settings: Settings) -> None:
        settings.require_llm()
        self._caching = settings.prompt_caching
        # Het cache-punt op het eind van de berichten (de top-level `cache_control`). Apart van `_caching`: weigert de
        # provider alleen dit, dan blijft het cache-punt op de systeemprompt staan.
        self._historie_caching = settings.prompt_caching
        # De TTL van het cachepunt op de systeemprompt (`Settings.prompt_cache_ttl`). `None` is de standaard van de
        # provider (5 minuten), en daarop valt de adapter terug als de provider een TTL weigert.
        self._ttl: str | None = None if settings.prompt_cache_ttl == "5m" else settings.prompt_cache_ttl
        # Eén meter per adapter, en de adapter wordt per beurt gebouwd – dus deze telt precies één
        # beurt op. `answer_stream` leest hem aan het eind uit en meldt het verbruik aan de api.
        self.meter = Verbruiksmeter()
        self._client = anthropic.Anthropic(
            api_key=settings.azure_foundry_api_key,
            base_url=settings.azure_foundry_base_url.rstrip("/"),
            default_query={"api-version": "2025-04-15"},
            # Beide expliciet: samen bepalen ze hoe lang één mislukte call kost, en dat product
            # duwt een eval-job over zijn tijdsbudget (120 s x 3 pogingen per call, bij een
            # provider die `overloaded_error` geeft). De SDK doet zelf exponentiële
            # backoff tussen de pogingen; dat willen we houden, alleen niet zó lang.
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    def _system(self, system: Systeem, *, caching: bool | None = None) -> Any:
        """Zet het systeemblok om naar de vorm die de provider wil, met een cache-punt.

        Prompt-caching is een **prefix-match**: de provider hasht de gerenderde prompt tot aan het
        cache-punt, dus alles wat vóór dat punt staat moet byte-voor-byte gelijk zijn tussen calls.
        Vandaar de splitsing: de aanroeper levert het stabiele deel (identiteit, JAS-klassen,
        specialist) apart van het variabele (het plan van deze beurt, de gespreksgeheugen-context),
        en het cache-punt gaat op het laatste stabiele blok.

        Wat dit oplevert: de antwoordroute herhaalt de systeemprompt bij élke tool-ronde, en als die
        boven `_MIN_CACHE_TEKENS` komt, is dat het profiel waarvoor caching bestaat. In de
        annotatieketen verschilt de prompt per batch, dus daar levert het niets op.

        Dit punt dekt ook de tools (die staan ervóór in de cache) en draagt de TTL uit de settings: met een uur overleeft
        het voorvoegsel de pauze waarin de jurist een antwoord leest. Het punt op de historie (top-level) houdt de
        standaard van 5 minuten; de API eist de langere TTL vóór de kortere.
        """
        aan = self._caching if caching is None else caching
        delen = [system] if isinstance(system, str) else [d for d in system if d]
        if not aan or not delen:
            return "\n\n".join(delen)

        stabiel = "\n\n".join(delen[:-1]) if len(delen) > 1 else delen[0]
        variabel = delen[-1] if len(delen) > 1 else ""
        if len(stabiel) < _MIN_CACHE_TEKENS:
            # Te kort om te cachen: één blok, geen cache-punt. Anders betaal je de (duurdere)
            # cache-write voor een voorvoegsel dat toch nooit als hit terugkomt.
            return "\n\n".join(d for d in (stabiel, variabel) if d)

        # De TTL alleen voor wie zelf een stabiel deel aanwijst (een lijst: supervisor, antwoordlus): die prompt komt
        # terug. Een losse string (classifier, kaartacties) is meestal eenmalig, en schrijven voor een uur kost 2×.
        lang = self._ttl if not isinstance(system, str) else None
        punt = {"type": "ephemeral", "ttl": lang} if lang else {"type": "ephemeral"}
        blokken: list[dict[str, Any]] = [{"type": "text", "text": stabiel, "cache_control": punt}]
        if variabel:
            blokken.append({"type": "text", "text": variabel})
        return blokken

    def _zonder_caching(self, exc: Exception, *, historie: bool = False) -> bool:
        """Weigerde de provider het cache-punt? Zet caching uit en meld het één keer.

        Prompt-caching is op Azure AI Foundry een beta-functie. Zou hij `cache_control` niet
        accepteren, dan faalt zónder deze terugval élke LLM-call – en daarmee de hele agent. De prijs
        van caching mag nooit "de dienst ligt plat" zijn.
        """
        if not self._caching or ("cache_control" not in str(exc) and "ttl" not in str(exc).lower()):
            return False
        # Een TTL die de provider niet kent: terug naar zijn standaard (5 minuten); de cachepunten blijven staan.
        if self._ttl and "ttl" in str(exc).lower():
            self._ttl = None
            logger.warning(
                "cache-TTL geweigerd door de provider; voortaan 5 minuten",
                extra={"categorie": "technisch", "fout": str(exc)[:200]},
            )
            return True
        # Droeg het verzoek het cache-punt op de historie, dan ligt het daaraan: het cache-punt op de systeemprompt nam
        # de provider al aan. Alleen dat ene gaat dan uit.
        if historie and self._historie_caching:
            self._historie_caching = False
            logger.warning(
                "historie-caching geweigerd door de provider; voortaan alleen de systeemprompt",
                extra={"categorie": "technisch", "fout": str(exc)[:200]},
            )
            return True
        self._caching = False
        logger.warning(
            "prompt-caching geweigerd door de provider; voortaan zonder cache-punt",
            extra={"categorie": "technisch", "fout": str(exc)[:200]},
        )
        return True

    def create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: Systeem,
        tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        tool_choice: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> Any:
        # Alleen meesturen wat gezet is: zonder deze twee is de aanroep exact wat hij was.
        extra: dict[str, Any] = {}
        if tool_choice is not None:
            extra["tool_choice"] = tool_choice
        if temperature is not None:
            extra["temperature"] = temperature
        begin = time.perf_counter()
        try:
            resp = self._client.messages.create(
                model=model, max_tokens=max_tokens, system=self._system(system),
                tools=tools, messages=messages, **extra,
            )
        except anthropic.BadRequestError as exc:
            if not self._zonder_caching(exc):
                raise
            resp = self._client.messages.create(
                model=model, max_tokens=max_tokens, system=self._system(system),
                tools=tools, messages=messages, **extra,
            )
        self.meter.tel_response(resp, ms=round((time.perf_counter() - begin) * 1000),
                                opbouw=opbouw(system=system, tools=tools, messages=messages))
        return resp

    def stream(
        self,
        *,
        model: str,
        max_tokens: int,
        system: Systeem,
        tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        historie_cache: bool = False,
    ) -> "_AnthropicStream":
        """`historie_cache`: ook een cache-punt op het eind van de berichten (F7, CL-4). Voor de toollus van de
        antwoordroute: elke ronde stuurt de hele historie opnieuw, en die is binnen een beurt een groeiend
        voorvoegsel. Elders niet: een prompt die niet terugkomt, betaalt alleen de duurdere cache-write."""
        # Bij streamen valt een weigering pas bij het openen van de stream (daar gaat de call de
        # deur uit), dus de terugval zit in `_AnthropicStream.__enter__` – met deze fabriek als
        # tweede poging. Die leest de vlaggen opnieuw: de terugval heeft er één uitgezet.
        def met_historie() -> bool:
            return historie_cache and self._caching and self._historie_caching

        def open_stream():
            extra: dict[str, Any] = {}
            if met_historie():
                extra["cache_control"] = {"type": "ephemeral"}
            return self._client.messages.stream(
                model=model, max_tokens=max_tokens,
                system=self._system(system, caching=self._caching),
                tools=tools, messages=messages, **extra,
            )

        return _AnthropicStream(
            open_stream(), opnieuw=open_stream,
            terugval=lambda exc, h=met_historie(): self._zonder_caching(exc, historie=h),
            meter=self.meter, opbouw=opbouw(system=system, tools=tools, messages=messages),
        )


class _AnthropicStream:
    """Dunne wrapper om de Anthropic MessageStream (LLMStream-protocol)."""

    def __init__(self, manager: Any, opnieuw: Any = None, terugval: Any = None,
                 meter: Any = None, opbouw: dict[str, Any] | None = None) -> None:
        self._manager = manager
        self._stream: Any = None
        self._opnieuw = opnieuw          # zelfde call, maar zonder cache-punt
        self._terugval = terugval        # beslist of de fout over caching ging
        self._meter = meter              # telt het verbruik van deze beurt op
        self._opbouw = opbouw            # waaruit het verzoek bestond (`verzoekopbouw`), voor de meter
        self._begin = 0.0                # het openen van de stream: daar gaat de call de deur uit

    def __enter__(self) -> "_AnthropicStream":
        self._begin = time.perf_counter()
        try:
            self._stream = self._manager.__enter__()
        except anthropic.BadRequestError as exc:
            if not (self._terugval and self._opnieuw and self._terugval(exc)):
                raise
            self._manager = self._opnieuw()
            self._stream = self._manager.__enter__()
        return self

    def __exit__(self, *exc: Any) -> Any:
        return self._manager.__exit__(*exc)

    @property
    def text_deltas(self) -> Any:
        return self._stream.text_stream

    def final_message(self) -> Any:
        """Het volledige antwoord. Hier komt ook het `usage`-blok van een streamende call binnen.

        `get_final_message()` is idempotent aan de SDK-kant, maar de meter is dat niet: twee keer
        aanroepen zou dubbel tellen. De aanroeper doet dit één keer per stream (zie `antwoord.py`);
        mocht dat ooit veranderen, dan hoort de ontdubbeling hier.
        """
        resp = self._stream.get_final_message()
        if self._meter is not None:
            self._meter.tel_response(resp, ms=round((time.perf_counter() - self._begin) * 1000), opbouw=self._opbouw)
        return resp
