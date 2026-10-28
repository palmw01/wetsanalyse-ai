"""Eval van het betekenisonderzoek (spoor M): oud (alleen het manifest) tegenover nieuw (manifest +
onderzoek + dossier), offline en deterministisch, op de casussen uit `betekenisonderzoek_casus.json`.

Per casus:

- **context**: hoeveel bepalingen het model ziet (manifest; manifest + onderzoek) en hoeveel fragmenten;
- **bevindingen** en **open vragen** van het dossier;
- **markering**: worden de definities die Lex eerder gaf (de foutgevallen van 27-10-2026, hieronder
  letterlijk) nu gemarkeerd? Oud = `toetsen.signalen` zonder dossier, nieuw = met;
- **prompt**: de grootte van de scherper-prompt (tekens), oud en nieuw;
- **uitval**: wat het dossier zegt als het onderzoek een bron mist (budget) of de graaf onbereikbaar was.

Geen model, geen graaf, geen kosten. Het rapport is een meting van het mechanisme, geen kwaliteitsoordeel
over de definities: dat is aan een jurist.

    python -m eval.betekenisonderzoek_eval [--json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agent.begrippen_pipeline import betekenis, fragmenten, kaartacties as ka, toetsen
from agent.begrippen_pipeline.model import (
    Bron, Contextbron, Formulering, Fragment, Herkomst, Kaart, Manifest, Onderzoek, Ontbrekend, Reden, Rol,
)

CASUS = Path(__file__).with_name("betekenisonderzoek_casus.json")

# De definities die Lex vóór spoor M voorstelde (de opdracht van 27-10-2026), met de bron waarop ze rustten.
FOUTGEVALLEN = {
    "A": {"naam": "herziening", "termen": ["herziening"], "leden": ["e0"],
          "definitie": "De wijziging van een voorlopige aanslag inkomstenbelasting of vennootschapsbelasting met een "
                       "negatief bedrag tot een voorlopige aanslag met een positief bedrag.",
          "verwacht": ["ALGEMENE_NAAM_SPECIFIEKE_DEFINITIE"]},
    "B": {"naam": "belasting", "termen": ["belasting"], "leden": ["e0", "e1"],
          "definitie": "De inkomstenbelasting of vennootschapsbelasting die als grondslag voor de berekening van "
                       "belastingrente dient.",
          "verwacht": ["RECHTSGEVOLG_IN_DEFINITIE", "TEGENBEWIJS_IN_ONDERZOEK"]},
}


def laad() -> dict[str, Any]:
    return json.loads(CASUS.read_text(encoding="utf-8"))


def _bron(n: dict, cls=Bron, **extra):
    return cls(bron_iri=n["bron_iri"], tekst=n["tekst"], bron_hash=n["bron_hash"], label=n["label"],
               regeling="BWBR0002320", **extra)


def casus(data: dict, naam: str, ontbrekend: tuple[Ontbrekend, ...] = (),
          weglaten: int = 0) -> tuple[Manifest, Onderzoek]:
    """Manifest en onderzoek zoals de api ze zou bouwen: de andere leden van het artikel als context."""
    nodes = {n["bron_iri"]: n for n in data["nodes"]}
    fs = data["casus"][naam]["formuleringen"]
    m = Manifest(bronnen=tuple(_bron(nodes[i]) for i in sorted({f["bron_iri"] for f in fs})),
                 formuleringen=tuple(Formulering(element_id=f"e{i}", **f) for i, f in enumerate(fs)))
    art = fs[0]["bron_iri"].rsplit(":lid:", 1)[0]
    eigen = {b.bron_iri for b in m.bronnen}
    ctx = [_bron(n, Contextbron, rol=Rol.ONDERZOEK, reden=Reden.ZELFDE_ARTIKEL, voor=("e0",))
           for i, n in nodes.items() if i.startswith(art + ":") and n["tekst"] and i not in eigen]
    if weglaten:
        ontbrekend = (*ontbrekend, *(Ontbrekend(wat=b.bron_iri, reden="budget") for b in ctx[-weglaten:]))
        ctx = ctx[:-weglaten]
    return m, Onderzoek(manifest_id=m.id, bronnen=tuple(ctx), ontbrekend=ontbrekend)


def _kaart(fout: dict, m: Manifest, o: Onderzoek | None) -> Kaart:
    """De foutdefinitie als geformuleerde kaart, onderbouwd met het eerste fragment van haar eigen passage."""
    eerste = m.formulering(fout["leden"][0])
    fr = next(f for f in fragmenten.knip(m.bron(eerste.bron_iri)) if f.start <= eerste.start < f.eind)
    return Kaart(groep_id="G0", naam=fout["naam"], definitie=fout["definitie"], herkomst=Herkomst.GEFORMULEERD,
                 fragmenten=(Fragment(**fr.model_dump()),))


def meet_casus(data: dict, naam: str) -> dict[str, Any]:
    fout = FOUTGEVALLEN[naam]
    m, o = casus(data, naam)
    kant = ka.Kant(id="b", inhoud={"naam": fout["naam"]}, leden=tuple(fout["leden"]))
    frs_oud = ka.fragmenten_voor(m, [kant])
    frs_nieuw = ka.fragmenten_voor(m, [kant], onderzoek=o)
    d = betekenis.dossier(m, o, tuple(fout["leden"]), fout["termen"])
    kaart = _kaart(fout, m, o)
    oud = toetsen.signalen(kaart, [])
    nieuw = toetsen.signalen(kaart, [], d)
    prompt_oud = ka.prompt_scherper(m, kant, frs_oud)
    prompt_nieuw = ka.prompt_scherper(m, kant, frs_nieuw, d)
    return {
        "casus": naam, "omschrijving": data["casus"][naam]["omschrijving"],
        "context": {"oud": {"bepalingen": len(m.bronnen), "fragmenten": len(frs_oud)},
                    "nieuw": {"bepalingen": len(m.bronnen) + len(o.bronnen), "fragmenten": len(frs_nieuw)}},
        "bevindingen": [b.code for b in d.bevindingen], "vragen": list(d.vragen),
        "markering": {"oud": oud, "nieuw": nieuw, "verwacht": fout["verwacht"],
                      "gevonden": all(c in nieuw for c in fout["verwacht"]),
                      "oud_gevonden": all(c in oud for c in fout["verwacht"])},
        "prompt_tekens": {"oud": len(prompt_oud), "nieuw": len(prompt_nieuw)},
        "dossier_id": d.id,
    }


def meet_uitval(data: dict) -> dict[str, Any]:
    """Het dossier bij een te klein budget en bij een onbereikbare graaf: de meldingen, niet stil."""
    fout = FOUTGEVALLEN["A"]
    m, o = casus(data, "A", weglaten=3)
    d = betekenis.dossier(m, o, tuple(fout["leden"]), fout["termen"])
    m2, o2 = casus(data, "A", ontbrekend=(Ontbrekend(wat="verwijzingen vanaf de passages", reden="onbereikbaar"),))
    d2 = betekenis.dossier(m2, o2, tuple(fout["leden"]), fout["termen"])
    kaart = _kaart(fout, m, o)
    return {"budget": {"ontbrekend": list(d.ontbrekend), "signalen": toetsen.signalen(kaart, [], d),
                       "parallel_nog_herkend": bool(d.met(betekenis.PARALLEL))},
            "onbereikbaar": {"ontbrekend": list(d2.ontbrekend), "signalen": toetsen.signalen(kaart, [], d2)}}


def rapport() -> dict[str, Any]:
    data = laad()
    uit = {"vastgelegd_op": data["vastgelegd_op"], "casussen": [meet_casus(data, c) for c in sorted(FOUTGEVALLEN)],
           "uitval": meet_uitval(data)}
    # Determinisme: tweemaal dezelfde invoer, hetzelfde rapport.
    uit["deterministisch"] = [meet_casus(data, c) for c in sorted(FOUTGEVALLEN)] == uit["casussen"]
    return uit


def tekst(r: dict[str, Any]) -> str:
    regels = [f"# Betekenisonderzoek – oud tegenover nieuw (casussen van {r['vastgelegd_op']})", ""]
    for c in r["casussen"]:
        regels += [f"## Casus {c['casus']}: {c['omschrijving']}", "",
                   f"- context: {c['context']['oud']['bepalingen']} → {c['context']['nieuw']['bepalingen']} bepalingen, "
                   f"{c['context']['oud']['fragmenten']} → {c['context']['nieuw']['fragmenten']} fragmenten",
                   f"- bevindingen: {', '.join(c['bevindingen'])}",
                   f"- open vragen: {len(c['vragen'])}",
                   f"- foutdefinitie gemarkeerd (verwacht {', '.join(c['markering']['verwacht'])}): "
                   f"oud {'ja' if c['markering']['oud_gevonden'] else 'nee'}, nieuw {'ja' if c['markering']['gevonden'] else 'nee'}",
                   f"  - oud: {', '.join(c['markering']['oud']) or '–'}",
                   f"  - nieuw: {', '.join(c['markering']['nieuw']) or '–'}",
                   f"- scherper-prompt: {c['prompt_tekens']['oud']} → {c['prompt_tekens']['nieuw']} tekens", ""]
    u = r["uitval"]
    regels += ["## Uitval", "",
               f"- budget: {', '.join(u['budget']['ontbrekend'])}; signalen {', '.join(u['budget']['signalen'])}; "
               f"parallel nog herkend: {'ja' if u['budget']['parallel_nog_herkend'] else 'nee'}",
               f"- onbereikbaar: {', '.join(u['onbereikbaar']['ontbrekend'])}; signalen {', '.join(u['onbereikbaar']['signalen'])}",
               "", f"Deterministisch: {'ja' if r['deterministisch'] else 'NEE'}"]
    return "\n".join(regels)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    r = rapport()
    print(json.dumps(r, ensure_ascii=False, indent=1) if ap.parse_args().json else tekst(r))
    return 0 if r["deterministisch"] and all(c["markering"]["gevonden"] for c in r["casussen"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
