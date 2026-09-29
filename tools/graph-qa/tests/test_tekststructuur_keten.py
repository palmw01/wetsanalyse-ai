"""De herstelde kandidaten door classificatie, validatie, review en de emitter."""
import json
import re
from types import SimpleNamespace

import pytest

from agent.jas_pipeline.classificatie import TOOL as CLASSIFIER
from agent.jas_pipeline.detectoren import standaard_detectoren
from agent.jas_pipeline.kandidaten import GEEN_ANNOTATIE
from agent.jas_pipeline.review import TOOL as REVIEWER
from fakes import response
import test_hybride_keten as keten


class StructuurLLM(keten.KetenLLM):
    def __init__(self, fragment, klasse, route):
        super().__init__()
        self.fragment, self.klasse, self.route = fragment, klasse, route
        self.target = ""

    def create(self, **kw):
        if self._responses:
            return super().create(**kw)
        self.calls.append(kw)
        tool = kw["tools"][0]["name"]
        prompt = kw["messages"][0]["content"]
        if tool == CLASSIFIER:
            items = []
            for label, fragment, toegestaan in re.findall(
                    r'^(C\d+) \| "(.*?)" \| toegestaan: ([^|]+)', prompt, re.M):
                keuze = GEEN_ANNOTATIE
                if fragment == self.fragment:
                    self.target = label
                    assert self.klasse in toegestaan
                    if self.route == "review":
                        continue  # bewuste abstain → gerichte review
                    if self.route == "classificatie":
                        keuze = self.klasse
                items.append({"kandidaat": label, "beslissing": keuze, "optie": ""})
            payload = {"beslissingen": items}
        else:
            assert tool == REVIEWER and self.target and self.fragment in prompt
            payload = {"oordelen": [{"geval": self.target, "actie": "CHANGE", "klasse": self.klasse}]}
        return response([SimpleNamespace(type="tool_use", id="s1", name=tool, input=payload)], "tool_use")


@pytest.mark.parametrize("tekst,fragment,klasse", [
    ("Hij moet volgens artikel 3:4 € 1.000 betalen. Daarna mag hij gaan.",
     "Hij moet volgens artikel 3:4 € 1.000 betalen.", "Rechtsbetrekking"),
    ("Hij moet volgens art. 4 en artikel 9.1 betalen.",
     "Hij moet volgens art. 4 en artikel 9.1 betalen.", "Rechtsbetrekking"),
    ("In deze wet wordt verstaan onder: a. aanvraag: het verzoek; b. besluit: de beslissing.",
     "aanvraag: het verzoek;", "Brondefinitie"),
    ("Bij voetgangerslichten betekent: a. groen licht: voetgangers mogen oversteken;",
     "groen licht", "Voorwaarde"),
])
@pytest.mark.parametrize("route", ["classificatie", "review", "afwijzing"])
def test_gehele_keten_bewaart_fragment_klasse_en_bijdragen(monkeypatch, tekst, fragment, klasse, route):
    monkeypatch.setattr(keten, "LID_TSV", json.dumps(f'?nummer\t?tekst\t?jci\n"1"\t"{tekst}"@nl\t"jci"'))
    llm = StructuurLLM(fragment, klasse, route)
    events = keten._draai(llm, deterministisch_accepteren=False)
    assert llm.target, "de classifier moet het volledige herstelde fragment ontvangen"
    register = next(e["dekking"]["beslissingen"] for e in events if e["type"] == "dekking")
    [besluit] = [b for b in register if b["label"] == llm.target]
    assert tekst[besluit["start"]:besluit["eind"]] == fragment
    bijdragen = besluit["detectiebijdragen"]
    assert bijdragen
    versies = {d.naam: d.versie for d in standaard_detectoren()}
    assert all(b["versie"] == versies[b["detector"]] and b["bewijs"] for b in bijdragen)
    elementen = [v for v in keten._elementen(events) if v["trace"]["kandidaat"]["label"] == llm.target]
    if route == "afwijzing":
        assert besluit["status"] == "REJECTED" and not elementen
    else:
        [v] = elementen
        assert (v["tekst"], v["klasse"]) == (fragment, klasse)
        [anker] = v["ankers"]
        assert tekst[anker["start"]:anker["eind"]] == fragment
        assert all(x["ernst"] != "fout" for x in v["trace"]["validatie"])
        if route == "review":
            assert besluit["classifier_reden"] == "CLASSIFIER_OMITTED"
            assert any(c["tools"][0]["name"] == REVIEWER for c in llm.calls if c.get("tools"))
    meting = next(e["run"]["instellingen"]["meting"] for e in events if e["type"] == "run")
    assert meting["tekstgrenzen_versie"] == meting["tekststructuur_versie"] == "1"
    overgeslagen = [r for r in meting["detectorresultaten"] if r["overgeslagen"]]
    assert len(overgeslagen) == 5
    assert all(r["versie"] == versies[r["detector"]] and r["reden"] and r["kandidaten"] == 0 for r in overgeslagen)
