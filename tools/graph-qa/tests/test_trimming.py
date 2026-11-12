"""Wat er sneuvelt als het promptvenster knelt: tool-ruis vóór gesprek.

Een SPARQL-resultaat kan duizenden tekens zijn. Woog dat even zwaar als proza, dan schoof het
venster op tool-ruis en viel juist de vroege vraagstelling — waar de beurt over gaat — er als eerste
uit. Oude tool-resultaten worden daarom eerst ingekort; de blokken zelf blijven staan, want een
`tool_use` zonder `tool_result` weigert Anthropic.
"""

from __future__ import annotations

from agent.berichten import _TOOLRESULT_KRIMP, _is_plain_user, _msg_lengte, _trim_messages


def vraag(tekst: str) -> dict:
    return {"role": "user", "content": tekst}


def toolbeurt(id_: str, resultaat: str) -> list[dict]:
    """Een assistant die een tool aanroept plus het user-bericht met het resultaat."""
    return [
        {"role": "assistant", "content": [{"type": "tool_use", "id": id_, "name": "raw_sparql", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": id_, "content": resultaat}]},
    ]


def test_zonder_budgetdruk_verandert_er_niets():
    msgs = [vraag("Wat regelt artikel 36?"), *toolbeurt("t1", "x" * 100)]
    assert _trim_messages(msgs, 100_000) == msgs


def test_een_oud_tool_resultaat_wordt_ingekort_niet_weggegooid():
    msgs = [vraag("Wat regelt artikel 36?"), *toolbeurt("t1", "y" * 20_000),
            vraag("En lid 2?"), *toolbeurt("t2", "z" * 200)]
    uit = _trim_messages(msgs, 5_000)

    # Het blok staat er nog — anders blijft de tool_use van t1 als wees achter.
    resultaten = [blok for m in uit if isinstance(m.get("content"), list)
                  for blok in m["content"] if blok.get("type") == "tool_result"]
    ids = {r["tool_use_id"] for r in resultaten}
    assert "t1" in ids, "het oude tool_result mag niet verdwijnen, alleen krimpen"

    oud = next(r for r in resultaten if r["tool_use_id"] == "t1")
    assert len(oud["content"]) < 20_000
    assert oud["content"].startswith("y" * 100)      # het begin blijft leesbaar
    assert "ingekort" in oud["content"]              # en het is zichtbaar afgekapt


def test_de_recentste_beurt_blijft_ongemoeid():
    """Daar werkt het model nú mee; die mag niet afgekapt worden."""
    msgs = [vraag("Eerste vraag"), *toolbeurt("t1", "y" * 20_000),
            vraag("Tweede vraag"), *toolbeurt("t2", "z" * 3_000)]
    uit = _trim_messages(msgs, 8_000)
    recent = [blok for m in uit if isinstance(m.get("content"), list)
              for blok in m["content"]
              if blok.get("type") == "tool_result" and blok["tool_use_id"] == "t2"]
    assert recent and recent[0]["content"] == "z" * 3_000


def test_het_venster_begint_altijd_op_een_platte_vraag():
    """De integriteitsregel die al gold, blijft gelden: nooit een orphan tool_result vooraan."""
    msgs = [vraag("Eerste vraag"), *toolbeurt("t1", "y" * 9_000),
            vraag("Tweede vraag"), *toolbeurt("t2", "z" * 9_000)]
    uit = _trim_messages(msgs, 4_000)
    assert _is_plain_user(uit[0])


def test_inkorten_maakt_ruimte_voor_meer_gesprek():
    """De hele reden voor deze regel: bij gelijk budget passen er meer beurten in."""
    msgs = [vraag(f"Vraag {i}") for i in range(3)]
    msgs = [vraag("Waar gaat dit over?"), *toolbeurt("t1", "y" * 30_000), *msgs]
    uit = _trim_messages(msgs, 6_000)
    teksten = [m["content"] for m in uit if isinstance(m.get("content"), str)]
    assert "Vraag 2" in teksten
    # Zonder inkorten zou het venster op het tool-resultaat zijn opgegaan en zou de oorspronkelijke
    # vraag er als eerste uit vallen; met inkorten past hij er nog bij.
    assert len(uit) > 3
    assert _TOOLRESULT_KRIMP < 30_000


def test_een_vers_groot_resultaat_wordt_niet_ingekort():
    """Het resultaat waar het model nú mee werkt, blijft heel – ook als het alleen al het halve
    budget overschrijdt. Werd het ingekort met "vraag het opnieuw op", dan zocht het model opnieuw,
    kreeg weer een ingekort resultaat, en zo door tot de beurtlimiet."""
    msgs = [vraag("Eerste vraag"), *toolbeurt("t1", "y" * 25_000),
            vraag("Welke rechtssubjecten ken je nog meer?"), *toolbeurt("t2", "z" * 30_000)]
    # Het budget geldt voor de historie vóór de lopende beurt (25k): bij 20k krimpt het oude resultaat.
    uit = _trim_messages(msgs, 20_000)
    vers = [blok for m in uit if isinstance(m.get("content"), list)
            for blok in m["content"]
            if blok.get("type") == "tool_result" and blok["tool_use_id"] == "t2"]
    assert vers and vers[0]["content"] == "z" * 30_000
    oud = [blok for m in uit if isinstance(m.get("content"), list)
           for blok in m["content"]
           if blok.get("type") == "tool_result" and blok["tool_use_id"] == "t1"]
    assert oud and "ingekort" in oud[0]["content"], "het oude resultaat mag wel krimpen"



def test_de_lopende_beurt_telt_niet_mee_in_het_budget_van_de_historie():
    """Nameting context 12 nov 2026: bij 51k tekens in de lopende beurt viel het hele gesprek weg (23 → 11
    berichten) en werd de beurt opnieuw geschreven. De historie past in haar budget, dus ze blijft staan."""
    historie = [vraag("Eerste vraag"), *toolbeurt("t1", "y" * 5_000), {"role": "assistant", "content": "antwoord"}]
    beurt = [vraag("Tweede vraag")] + [b for i in range(6) for b in toolbeurt(f"n{i}", "z" * 10_000)]
    uit = _trim_messages(historie + beurt, 40_000, "Tweede vraag")
    assert uit == historie + beurt


def _gesprek(beurten: int) -> list[dict]:
    msgs: list[dict] = []
    for i in range(beurten):
        msgs += [vraag(f"Vraag {i}"), *toolbeurt(f"t{i}", chr(97 + i % 26) * 6_000), {"role": "assistant", "content": f"Antwoord {i}"}]
    return msgs


def test_per_beurt_verandert_alleen_het_eind_van_het_venster():
    """Wat de cache per beurt opnieuw moet schrijven: alles vanaf het eerste bericht dat anders is dan in het venster
    van de vorige beurt. Het minimum is de nieuwe beurt zelf (~6k tekens hier). De oude code schoof het beschermde
    deel en de voorkant bij elke beurt op en schreef gemiddeld ~29k van een venster van ~36k opnieuw."""
    herschreven = []
    for n in range(8, 40):
        nu = _trim_messages(_gesprek(n) + [vraag("nieuw")], 40_000, "nieuw")[:-1]
        straks = _trim_messages(_gesprek(n + 1) + [vraag("nieuw")], 40_000, "nieuw")[:-1]
        k = 0
        while k < min(len(nu), len(straks)) and nu[k] == straks[k]:
            k += 1
        herschreven.append(sum(_msg_lengte(m) for m in straks[k:]))
        assert sum(_msg_lengte(m) for m in nu) <= 40_000
    assert sum(herschreven) / len(herschreven) < 12_000


def _beurt(i: int, resultaten: int, omvang: int) -> list[dict]:
    uit = [vraag(f"Vraag {i}")]
    for r in range(resultaten):
        uit += toolbeurt(f"t{i}_{r}", chr(97 + (i + r) % 26) * omvang)
    return uit + [{"role": "assistant", "content": "A" * 600}]


def test_de_cache_leest_de_historie_via_de_cachepunten_van_de_vorige_beurt():
    """Nameting G4 (12 nov 2026): de voorkant van het venster liep terug, want het knippunt hing af van de laatste beurt,
    die de beurt erna krimpt. Hier telt alleen wat de cache echt kan hergebruiken: het voorvoegsel tot een cachepunt van
    de vorige beurt (`met_beurtcontext`) dat byte-gelijk is gebleven. Ook met een grote eerste beurt (83k in G4)."""
    from agent.berichten import met_beurtcontext

    for groot_eerst in (False, True):
        historie: list[dict] = []
        vorige = None
        begins: list[str] = []
        geschreven: list[int] = []
        for i in range(14):
            historie += _beurt(i, 6 if groot_eerst and i == 0 else 3, 13_000 if groot_eerst and i == 0 else 4_000)
            venster = _trim_messages(historie + [vraag("nieuw")], 40_000, "nieuw")
            venster, punten = met_beurtcontext(venster, "nieuw", "CONTEXT")
            hist = venster[:-1]
            begins.append(hist[0]["content"])
            if vorige is not None:
                oud, oude_punten = vorige
                gelezen = max((sum(_msg_lengte(m) for m in hist[:p + 1]) for p in oude_punten
                               if p < len(hist) and hist[:p + 1] == oud[:p + 1]), default=0)
                geschreven.append(sum(_msg_lengte(m) for m in hist) - gelezen)
            vorige = (hist, punten)
        nummers = [int(b.split()[-1]) for b in begins]
        assert nummers == sorted(nummers), f"de voorkant liep terug: {begins}"
        # Per beurt de nieuwe beurt (~13k) plus de vorige beurt gekrompen; het oude venster schreef 34–36k.
        assert sum(geschreven) / len(geschreven) < 18_000, geschreven


def test_van_een_oude_beurt_blijven_vraag_en_antwoord_over():
    """Nameting G5 (12 nov 2026): een oude beurt met haar tussenrondes was gekrompen nog 8–19k tekens, en het venster knipte
    bijna elke beurt. Nu blijven de vraag en het laatste antwoord, met het resultaat dat bij dat antwoord hoort (een
    sjabloonaanroep); de tussenrondes gaan weg als hele paren, dus geen los resultaat. De lopende beurt blijft heel."""
    sjabloon = [{"role": "assistant", "content": [{"type": "tool_use", "id": "s1", "name": "antwoord_duiding", "input": {}}]},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "s1", "content": "gevuld"}]}]
    oud = [vraag("Eerste vraag"), *toolbeurt("t1", "y" * 20_000), *toolbeurt("t2", "z" * 20_000), *sjabloon]
    lopend = [vraag("Tweede vraag"), *toolbeurt("t3", "w" * 30_000)]
    uit = _trim_messages(oud + lopend, 20_000, "Tweede vraag")
    assert uit[:3] == [vraag("Eerste vraag"), *sjabloon]
    assert uit[3:] == lopend
    ids = [b.get("tool_use_id") for m in uit if isinstance(m["content"], list) for b in m["content"]
           if b.get("type") == "tool_result"]
    assert ids == ["s1", "t3"], "de tussenrondes zijn weg, als hele paren"
