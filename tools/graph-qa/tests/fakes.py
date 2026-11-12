"""Fakes voor de poorten, zodat de agent-loop deterministisch en zonder netwerk test."""
from __future__ import annotations

from agent.berichten import BEURTCONTEXT_KOP

from collections.abc import Callable
import re
from types import SimpleNamespace
from typing import Any

from agent.config import Settings


def make_settings(**kw: Any) -> Settings:
    """Settings voor tests: in-memory checkpointer (geen db-file) tenzij overschreven."""
    kw.setdefault("checkpoint_db_path", None)
    # De nepmodellen spelen een vast script van één classificatiecall; de productiedefault
    # (klasseverzameling) wordt apart getest in test_baseline_proef.
    kw.setdefault("classifier_granulariteit", "universeel")
    # Gescripte nepmodellen spelen hun antwoorden op volgorde af; parallelle batches zouden die
    # volgorde willekeurig maken. Het parallelle pad heeft een eigen test (test_classificatie_parallel).
    kw.setdefault("classifier_parallel", 1)
    return Settings(**kw)


# ---- LLM-response bouwstenen (vorm van de Anthropic-response) ----

def text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def tool_block(id: str, name: str, input: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=id, name=name, input=input)


def response(content: list[SimpleNamespace], stop_reason: str) -> SimpleNamespace:
    return SimpleNamespace(content=content, stop_reason=stop_reason)


class _FakeStream:
    """Streamt de tekstblokken van één response als deltas (LLMStream-protocol)."""

    def __init__(self, resp: SimpleNamespace) -> None:
        self._resp = resp

    def __enter__(self) -> "_FakeStream":
        return self

    def __exit__(self, *_exc: Any) -> bool:
        return False

    @property
    def text_deltas(self):
        text = "".join(b.text for b in self._resp.content if b.type == "text")
        for i in range(0, len(text), 12):  # in brokjes, als een echte stream
            yield text[i:i + 12]

    def final_message(self) -> SimpleNamespace:
        return self._resp


class FakeLLM:
    """Speelt een vaste reeks responses af via create() én stream() (gedeelde index)."""

    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self._responses = list(responses)
        self.index = 0
        self.calls: list[dict[str, Any]] = []
        # Per aanroep wat de beurt als instructie meekreeg: de systeemprompt plus de context van de beurt (die staat sinds
        # ADR-015 als eerste blok van de vraag, `met_beurtcontext`). Apart van `calls`: die draagt de kwargs van de aanroeper,
        # zonder eigen sleutels erbij (`tests/test_llm_stap.py` eist dat). Waar het blok staat, toetst `test_prompt_caching`.
        self.prompts: list[str] = []

    def _next(self) -> SimpleNamespace:
        resp = self._responses[self.index]
        self.index += 1
        return resp

    def _leg_vast(self, kwargs: dict[str, Any]) -> None:
        """Onthoud de call, met `system` als één string.

        De aanroeper mag het systeemblok gesplitst aanleveren (`[stabiel, variabel]`) zodat de echte
        adapter er een prompt-cache-punt tussen kan zetten; wat het model uiteindelijk leest is de
        aaneenschakeling. Tests vragen naar dát – de splitsing zelf staat in `system_delen`.
        """
        systeem = kwargs.get("system")
        if isinstance(systeem, list):
            kwargs = {**kwargs, "system_delen": systeem, "system": "\n\n".join(d for d in systeem if d)}
        context = [b.get("text", "") for m in kwargs.get("messages") or [] if isinstance(m.get("content"), list)
                   for b in m["content"] if isinstance(b, dict) and str(b.get("text", "")).startswith(BEURTCONTEXT_KOP)]
        self.prompts.append("\n\n".join([str(kwargs.get("system") or ""), *context]))
        self.calls.append(kwargs)

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self._leg_vast(kwargs)
        return self._next()

    def stream(self, **kwargs: Any) -> _FakeStream:
        self._leg_vast(kwargs)
        return _FakeStream(self._next())


class KetenLLM(FakeLLM):
    """FakeLLM voor de annotatieketen (ADR-001): eerst de vaste `responses` (supervisor, ophaal-
    agent), daarna beantwoordt hij de classifier per kandidaat-label en de gerichte reviewer.

    De labels bestaan pas na de fusie, dus hij leest ze uit de prompt. `kies(toegestaan, fragment)`
    bepaalt per kandidaat de beslissing (default: de eerste toegestane klasse); `review` de actie van
    de reviewer (default HUMAN_REVIEW). `tool_aanroep=False` laat beide zonder tool-aanroep antwoorden.
    """

    _REGEL = re.compile(r'^(C\d{3}) \| "(.*?)" \| toegestaan: ([^|]+)', re.M)
    _GEVAL = re.compile(r"^(C\d{3}) \|", re.M)

    def __init__(self, responses: list[SimpleNamespace] | None = None, kies=None, review: str = "HUMAN_REVIEW",
                 tool_aanroep: bool = True) -> None:
        super().__init__(responses or [])
        self.kies = kies or (lambda toegestaan, fragment: toegestaan[0])
        self.review, self.tool_aanroep = review, tool_aanroep

    def create(self, **kwargs: Any) -> SimpleNamespace:
        if self.index < len(self._responses):
            return super().create(**kwargs)
        self._leg_vast(kwargs)
        naam = (kwargs.get("tools") or [{}])[0].get("name", "")
        if not self.tool_aanroep or naam not in {"classificeer", "beoordeel"}:
            return response([text_block("Ik kies niet.")], "end_turn")
        prompt = kwargs["messages"][0]["content"]
        if naam == "classificeer":
            items = [{"kandidaat": label, "optie": "",
                      "beslissing": self.kies([t.strip() for t in toegestaan.split(",")], fragment)}
                     for label, fragment, toegestaan in self._REGEL.findall(prompt)]
            invoer = {"beslissingen": items}
        else:
            invoer = {"oordelen": [{"geval": g, "actie": self.review, "klasse": ""}
                                   for g in self._GEVAL.findall(prompt.split("TWIJFELGEVALLEN:")[-1])]}
        return response([SimpleNamespace(type="tool_use", id="k1", name=naam, input=invoer)], "tool_use")


class FakeGraph:
    """GraphPort-fake: onthoudt de uitgevoerde SPARQL en geeft canned tekst terug."""

    def __init__(
        self,
        result: str = "",
        results: Callable[[str], str] | None = None,
    ) -> None:
        self._result = result
        self._results = results
        self.queries: list[str] = []
        self.semantic_queries: list[str] = []
        self.closed = False

    def initialize(self) -> dict[str, Any]:
        return {}

    def sparql(self, query: str) -> str:
        self.queries.append(query)
        if self._results is not None:
            return self._results(query)
        return self._result

    def semantic_search(self, query: str, limit: int = 10) -> str:
        self.semantic_queries.append(query)
        return self._result

    def close(self) -> None:
        self.closed = True


def agent_ctx(api, *, settings=None, run_id: str = "run9", gestopt: bool = False, **kw):
    """Een `agents.Context` voor tests: de meldingen komen in `ctx.meldingen`."""
    from agent.agents import Context

    meldingen: list[str] = []
    ctx = Context(api=api, settings=settings or make_settings(), user_id="u", run_id=run_id, gesprek_id="g1",
                  melding=meldingen.append, gestopt=lambda: gestopt, **kw)
    ctx.meldingen = meldingen
    return ctx


def vraag_van(bericht: dict) -> str:
    """De tekst die de jurist schreef, zonder de context van de beurt ervoor (`berichten.met_beurtcontext`)."""
    c = bericht.get("content")
    if isinstance(c, str):
        return c
    return "".join(b.get("text", "") for b in c or [] if isinstance(b, dict) and b.get("type") == "text"
                   and not str(b.get("text", "")).startswith(BEURTCONTEXT_KOP))
