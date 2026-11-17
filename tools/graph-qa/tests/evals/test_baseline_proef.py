"""Het baselineharnas zonder modelaanroepen: plan, identieke verzoeken en keuzecriterium."""
from eval import baseline_proef as bp
from eval.invordering_proef import ROOT


def test_plan_voert_alleen_contextvarianten_met_context_uit():
    plan = bp.plan(ROOT)
    uitgevoerd = {(x["casus"], x["variant"]) for x in plan["pogingen"]}
    for sleutel, zonder in plan["identiek_aan"].items():
        casus, variant = sleutel.split("/")
        assert (casus, variant) not in uitgevoerd and bp.ZONDER_CONTEXT[variant] == zonder
    for casus, variant in uitgevoerd:
        if variant in bp.ZONDER_CONTEXT:
            c = next(c for c in bp.casussen()["casussen"] if c["id"] == casus)
            assert bp.context_van(c).blok()
    assert plan["primaire_pogingen"] == len(plan["pogingen"]) == 3 * len({(c, v) for c, v in uitgevoerd})


def test_identieke_contextvariant_geeft_byte_identiek_verzoek():
    from agent.jas_pipeline.classificatie import userprompt
    c = next(c for c in bp.casussen()["casussen"] if c["id"] == "IW-9-1")
    assert userprompt([], "x", context=bp.context_van(c).blok()) == userprompt([], "x")


def _stab(**kw):
    return {c: {v: {"doorsnede_door_unie": kw.get(v, 1.0)} for v in bp.VARIANTEN} for c in "abcdefgh"}


def test_keuzecriterium():
    tot = {"UC": {"contractfouten": 5, "kosten_per_run_usd": 0.03}, "KC": {"contractfouten": 0, "kosten_per_run_usd": 0.08}}
    assert bp.beslis(tot, _stab())["granulariteit"] == "klasseverzameling"
    duur = {**tot, "KC": {"contractfouten": 0, "kosten_per_run_usd": 0.1}}
    assert bp.beslis(duur, _stab())["granulariteit"] == "universeel"
    assert bp.beslis(tot, _stab(KC=0.5))["granulariteit"] == "universeel"
    assert bp.beslis(tot, _stab(UC=0.5))["context_vraagt_bevestiging"]


def test_productiedefault_volgt_het_baselinecriterium():
    from agent.config import Settings
    s = Settings(checkpoint_db_path=None)
    assert s.classifier_granulariteit == "klasseverzameling" and s.broncontext
