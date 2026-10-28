"""Lex denkt mee over de begripsvoorstellen (spoor D, fase C): het model op twijfelparen en kaarten.

Bovenop de laatste klare begrippenrun van het werkgebied (`begrippen_run.py`, levering 3a). De
model-laag zelf is zuiver (`begrippen_pipeline/verdieping.py`, `classificatie.py`, `kaart.py`); deze
module voert hem uit in batches, met de api als geheugen:

1. **Zonder `bevestigd`** noemt Lex wat er te doen is – twijfelpunten en begrippen zonder
   definitie –, de schatting en het budget, en de uitkomst draagt een `bevestiging`. Kost het
   model niets (geen twijfelpunten, elke definitie letterlijk), dan rekent hij meteen, zonder model.
2. **Met `bevestigd: n`** alleen als `n` de actuele werkvoorraad van de api is.
3. **Per batch**: stop- en budgetcontrole, het model in een thread, het verbruik geboekt op
   `<run>.v<n>`, en de batch naar de api (`PUT …/batches/{id}`), die de garanties opnieuw toetst.
   Een batch die al klaar is (dezelfde inhoudelijke id) slaat hij over: zo **hervat** een nieuwe run
   waar een vorige stopte, en geeft hij dezelfde uitkomst.
4. **Als alle batches klaar zijn**: hergroeperen, de kaarten, en de uitkomst naar de api
   (`PUT …/verdieping`). Een fout in één batch stopt de rest niet, maar dan blijft de verdieping
   open: Lex zegt hoeveel er klaar is, en een volgende run doet de rest.

De keten draait hier opnieuw op het bewaarde manifest (deterministisch); wijken de groepen of vragen af
van wat de api bewaarde – andere code sinds de voorstellen –, dan stopt hij met die melding.

Sinds F3c is dit de taak `meedenken` van de begrippen-agent (`verdieping_kern`, `agents/begrippen.py`):
de supervisor kiest hem, of een klik op de suggestie of de bevestigingsknop. Er is geen tekstpatroon meer.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from .agents import Context, Uitkomst, geweigerd
from .begrippen_beurt import begrippen_artefact
from .begrippen_pipeline import classificatie, kaart as kaart_mod, verdieping as vd
from .begrippen_pipeline.keten import analyseer
from .begrippen_pipeline.model import Aandacht, Kaart, ModelOordeel, Oordeel
from .begrippen_run import manifest_uit, onderzoek_uit, voorstel
from .reeks import _budget_poort
from .wetsanalyse_api import WetsanalyseApi, WetsanalyseApiFout

logger = logging.getLogger("graph_qa.begrippen_verdieping")


def _getal(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _meervoud(n: int, een: str, meer: str) -> str:
    return f"{n} {een if n == 1 else meer}"


def voorstel_tekst(naam: str, wv: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    """De tekst vóór de bevestiging, en de bevestiging zelf."""
    vragen, kaarten, n = len(wv.get("vragen") or []), len(wv.get("kaarten") or []), int(wv.get("aantal") or 0)
    delen = [x for x in (_meervoud(vragen, "twijfelpunt", "twijfelpunten") if vragen else "",
                         _meervoud(kaarten, "begrip zonder definitie", "begrippen zonder definitie") if kaarten else "") if x]
    zinnen = [f"In werkgebied *{naam}* kan ik meedenken over {' en '.join(delen)}."]
    if wv.get("batches"):
        zinnen.append(f"{_meervoud(len(wv['batches']), 'batch is', 'batches zijn')} al klaar; ik ga verder waar ik bleef.")
    schat, budget = wv.get("schatting"), wv.get("budget") or {}
    zin = (f"Naar schatting kost dat ~{_getal(schat['totaal'])} tokens" if schat else
           "Een schatting kan ik nog niet geven: er is nog geen eerdere verdieping van jou om op te baseren")
    zin += f"; je hebt nog {_getal(int(budget.get('resterend') or 0))} tokens." if budget.get("actief") else "."
    zinnen.append(zin)
    zinnen.append("Ik beslis niets: bij een twijfelpunt geef ik advies, en een definitie die ik formuleer staat "
                  "geel, met de passages waarop ze rust. Bevestig om te starten.")
    return " ".join(zinnen), {"soort": "begrippen_verdiepen", "werkgebied_id": str(wv.get("werkgebied_id") or ""),
                              "aantal": n, "schatting": schat["totaal"] if schat else None}


def samenvatting(naam: str, her: vd.Hergroepering, kaarten: dict[str, Any]) -> str:
    """Uit de getallen, geen model."""
    tel = {o: sum(1 for x in her.oordelen if x.oordeel is o) for o in Oordeel}
    model_groepen = sum(1 for g in her.groepen if g.aandacht is Aandacht.GEEL)
    herkomst = {h: sum(1 for k in kaarten.values() if (k.herkomst.value if k.herkomst else "") == h)
                for h in ("letterlijk", "samengesteld", "geformuleerd")}
    zonder = sum(1 for k in kaarten.values() if not k.definitie)
    zinnen = [f"Klaar met meedenken in werkgebied *{naam}*."]
    if her.oordelen:
        zinnen.append(f"Van {_meervoud(len(her.oordelen), 'twijfelpunt', 'twijfelpunten')} lijken er volgens mij "
                      f"{tel[Oordeel.ZELFDE_BETEKENIS]} hetzelfde begrip; bij de rest staat mijn advies bij de vraag.")
    if kaarten:
        zinnen.append(f"Definities: {herkomst['letterlijk']} letterlijk uit de wet, {herkomst['samengesteld']} "
                      f"samengesteld uit de bron, {herkomst['geformuleerd']} door mij geformuleerd, {zonder} zonder.")
    if model_groepen:
        zinnen.append(f"{_meervoud(model_groepen, 'voorstel staat', 'voorstellen staan')} geel: beoordeel die eerst.")
    return " ".join(zinnen) + " Open de voorstellen om ze te beoordelen."


def _groep_contract(g, manifest, uitkomst, model_links: set[str]) -> dict[str, Any]:
    return {"id": g.id, "leden": list(g.leden), "aandacht": g.aandacht.value, "uitleg": list(g.uitleg),
            "conflicten": list(g.conflicten), "voorstel": voorstel(manifest, uitkomst, g.leden),
            "door": "model" if set(g.kandidaten) & model_links else "regel"}


async def verdieping_kern(ctx: Context, werkgebied_id: str, bevestigd: int | None = None) -> Uitkomst:
    """Meedenken (taak `meedenken` van de begrippen-agent). Zonder `bevestigd` het voorstel met een
    bevestiging; met `bevestigd` gelijk aan de werkvoorraad de batches. Is er niets voor het model, dan
    rekent hij meteen, zonder model."""
    api, taak = ctx.api, "meedenken"
    settings, run_id, gesprek_id = ctx.settings, ctx.run_id, ctx.gesprek_id
    try:
        naam = str((await api.haal_werkgebied(werkgebied_id)).get("naam") or "zonder naam")
        ctx.melding(f"Werkgebied {naam}: wat er te verdiepen is")
        wv = {"werkgebied_id": werkgebied_id, **await api.haal_verdieping(werkgebied_id)}
    except WetsanalyseApiFout as fout:
        if fout.status != 404:
            raise
        return geweigerd(taak, "Dit werkgebied bestaat niet (meer).")
    api_run = wv.get("run")
    if not api_run:
        return geweigerd(taak, f"In werkgebied *{naam}* zijn nog geen begripsvoorstellen om over mee te denken. "
                               "Vraag eerst om begrippen.")
    artefact = begrippen_artefact(werkgebied_id, str(api_run["id"]), naam)
    if wv.get("verdiept"):
        return Uitkomst(taak=taak, artefact=artefact, tekst=f"Over de voorstellen in werkgebied *{naam}* heb ik al "
                                                            "meegedacht; open ze om ze te beoordelen.")
    aantal = int(wv.get("aantal") or 0)
    met_model = bevestigd is not None and bevestigd == aantal
    if aantal and not met_model:
        tekst, bevestiging = voorstel_tekst(naam, wv)
        if bevestigd is not None:
            tekst = f"De werkvoorraad veranderde: nu {aantal} in plaats van {bevestigd}. Ik ben niet begonnen. " + tekst
        return Uitkomst(taak=taak, status="bevestiging", tekst=tekst, bevestiging=bevestiging,
                        meting={"aantal": aantal, "model": False})

    # -- rekenen ------------------------------------------------------------------------------
    data = await api.haal_begrippen_run(werkgebied_id, str(api_run["id"]))
    manifest = manifest_uit(data["manifest"])
    onderzoek = onderzoek_uit(data.get("onderzoek"), manifest)
    ctx.melding(f"De keten opnieuw op {len(manifest.formuleringen)} passages"
                + (f" en {len(onderzoek.bronnen)} bepalingen als context" if onderzoek else ""))
    uitkomst = await asyncio.to_thread(analyseer, manifest, ctx.provider, None, onderzoek)
    bewaard = data.get("uitkomst") or {}
    if sorted(g.id for g in uitkomst.groepen) != sorted(bewaard.get("groep_ids", [])) or \
            sorted(v.kandidaat_id for v in uitkomst.vragen) != sorted(v["kandidaat_id"] for v in bewaard.get("vragen", [])):
        return Uitkomst(taak=taak, status="fout", reden="De begrippenketen geeft nu andere voorstellen dan toen ze "
                        "werden gemaakt. Vraag eerst opnieuw om begrippen; daarna kan ik meedenken.")

    model = settings.llm_model
    klaar = {b["id"]: b for b in wv.get("batches") or []}
    budget_toegestaan = ctx.budget_toegestaan
    if budget_toegestaan is None and settings.legt_zelf_vast and ctx.user_id:
        budget_toegestaan = _budget_poort(settings, ctx.user_id)
    teller = {"n": len(klaar), "fout": 0, "gestopt": "", "nieuw": 0}

    async def batch(soort: str, ids: list[str], versie: str, reken: Callable[[Any], Any],
                    bewaar: Callable[[Any], dict[str, Any]], lees: Callable[[dict], Any]) -> Any | None:
        """Eén batch: uit de api als hij klaar is, anders rekenen, boeken en bewaren. None = niet gedaan."""
        bid = vd.batch_id(soort, ids, versie, model)
        if bid in klaar:
            return lees(klaar[bid]["resultaat"])
        if not met_model or teller["gestopt"]:
            return None
        if ctx.gestopt():
            teller["gestopt"] = "gestopt"
            return None
        if budget_toegestaan is not None and not await budget_toegestaan():
            teller["gestopt"] = "budget_op"
            return None
        llm = (ctx.maak_llm or _anthropic)(settings)
        try:
            uit = await asyncio.to_thread(reken, llm)
        except Exception:  # noqa: BLE001 – een fout in één batch stopt de rest niet
            logger.exception("verdieping: batch faalde", extra={"categorie": "technisch", "run_id": run_id})
            teller["fout"] += 1
            await _boek(api, llm, model, gesprek_id, f"{run_id}.v{teller['n']}")
            teller["n"] += 1
            return None
        tokens = await _boek(api, llm, model, gesprek_id, f"{run_id}.v{teller['n']}")
        teller["n"] += 1
        await api.zet_begrippen_batch(werkgebied_id, str(api_run["id"]), bid,
                                      {"soort": soort, "ids": ids, "model": model, "promptversie": versie,
                                       "tokens": tokens, **bewaar(uit)})
        teller["nieuw"] += 1
        return uit

    # Klare batches leest hij altijd terug; nieuw rekenen alleen na bevestiging. Zonder model blijft
    # een vraag zonder oordeel en een kaart zoals de keten haar gaf – dat is dan geen onvolledigheid.
    oordelen: list[ModelOordeel] = []
    compleet = True
    vbatches = classificatie.batches(vd.te_vergelijken(uitkomst))
    for i, b in enumerate(vbatches, 1):
        if met_model:
            ctx.melding(f"Twijfelpunten {i}/{len(vbatches)}")
        uit = await batch("vraag", [v.kandidaat_id for v in b], classificatie.promptversie(),
                          lambda llm, b=b: classificatie.vergelijk(llm, model, manifest, b),
                          lambda os_: {"oordelen": [o.model_dump(mode="json") for o in os_]},
                          lambda r: [ModelOordeel(**o) for o in r["oordelen"]])
        if uit is not None:
            oordelen += uit
        elif met_model:
            compleet = False
    her = vd.hergroepeer(manifest, uitkomst, oordelen) if compleet else None
    kaarten: dict[str, Any] = {}
    if her is not None:
        kaarten, opdrachten = vd.kaartopdrachten(manifest, uitkomst, her.groepen, onderzoek)
        geel = {g.id: g.aandacht is Aandacht.GEEL for g in her.groepen}
        kbatches = kaart_mod.batches(opdrachten)
        for i, b in enumerate(kbatches, 1):
            if met_model:
                ctx.melding(f"Begripskaarten {i}/{len(kbatches)}")
            uit = await batch("kaart", [o.kaart.groep_id for o in b], kaart_mod.promptversie(),
                              lambda llm, b=b: kaart_mod.vul(llm, model, manifest, b, geel),
                              lambda ks: {"kaarten": [k.model_dump(mode="json") for k in ks]},
                              lambda r: [Kaart(**k) for k in r["kaarten"]])
            if uit is not None:
                kaarten.update({k.groep_id: k for k in uit})
            elif met_model:
                compleet = False

    meting = {"batches": teller["n"], "nieuw": teller["nieuw"], "model": met_model}
    if not compleet or her is None:
        waarom = {"budget_op": " – je tokenbudget is op", "gestopt": " – gestopt op verzoek"}.get(teller["gestopt"], "")
        fout = f" {_meervoud(teller['fout'], 'batch mislukte', 'batches mislukten')}." if teller["fout"] else ""
        return Uitkomst(taak=taak, artefact=artefact, meting=meting,
                        tekst=(f"Ik ben niet helemaal klaar{waarom}: {teller['nieuw']} nieuwe batches bewaard.{fout} "
                               "Vraag het opnieuw; ik ga verder waar ik bleef."))

    model_links = {o.kandidaat_id for o in oordelen if o.oordeel is Oordeel.ZELFDE_BETEKENIS}
    await api.zet_verdieping(werkgebied_id, str(api_run["id"]), {
        "manifest_id": manifest.id, "model": model,
        "groepen": [_groep_contract(g, manifest, uitkomst, model_links) for g in her.groepen],
        "kaarten": [k.model_dump(mode="json") for k in kaarten.values()],
        "oordelen": [o.model_dump(mode="json") for o in her.oordelen],
        "vragen": [v.kandidaat_id for v in her.vragen],
        "meting": {"batches": teller["n"], "nieuw": teller["nieuw"], "met_model": met_model,
                   "promptversie": {"vraag": classificatie.promptversie(), "kaart": kaart_mod.promptversie()}}})
    return Uitkomst(taak=taak, artefact=artefact, tekst=samenvatting(naam, her, kaarten), meting=meting,
                    voorstellen=[g.id for g in her.groepen])


def _anthropic(settings) -> Any:
    from .adapters.anthropic_llm import AnthropicLLM
    return AnthropicLLM(settings)


async def _boek(api: WetsanalyseApi, llm: Any, model: str, gesprek_id: str, run_id: str) -> int:
    """Boek het verbruik van één batch (best-effort, idempotent op `run_id`); geeft het totaal."""
    meter = getattr(llm, "meter", None)
    if meter is None or meter.totaal <= 0:
        return 0
    try:
        await api.boek_verbruik(meter.als_dict(), model=model, gesprek_id=gesprek_id, run_id=run_id)
    except Exception:  # noqa: BLE001 – boekhouding mag de batch niet laten mislukken
        logger.warning("verdieping: verbruik niet geboekt", extra={"run_id": run_id}, exc_info=True)
    return meter.totaal
