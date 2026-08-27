"""Wat er sneuvelt als het promptvenster knelt: tool-ruis vóór gesprek.

Een SPARQL-resultaat kan duizenden tekens zijn. Woog dat even zwaar als proza, dan schoof het
venster op tool-ruis en viel juist de vroege vraagstelling — waar de beurt over gaat — er als eerste
uit. Oude tool-resultaten worden daarom eerst ingekort; de blokken zelf blijven staan, want een
`tool_use` zonder `tool_result` weigert Anthropic.
"""

from __future__ import annotations

from agent.berichten import _TOOLRESULT_KRIMP, _is_plain_user, _trim_messages


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
