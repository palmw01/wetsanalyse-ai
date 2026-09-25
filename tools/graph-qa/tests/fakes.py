"""Fakes voor de poorten, zodat de agent-loop deterministisch en zonder netwerk test."""
from __future__ import annotations

from collections.abc import Callable
import re
from types import SimpleNamespace
from typing import Any

from agent.config import Settings


def make_settings(**kw: Any) -> Settings:
    """Settings voor tests: in-memory checkpointer (geen db-file) tenzij overschreven."""
    kw.setdefault("checkpoint_db_path", None)
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
